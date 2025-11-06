"""Direct database access methods for AGR Curation API Client.

This module provides direct database access through SQL queries,
adapted from agr_genedescriptions/pipelines/alliance/ateam_db_helper.py
"""

import logging
from os import environ
from typing import List, Optional, Dict, Any
from sqlalchemy.engine import Engine

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import ValidationError

from .models import Gene, Allele
from .exceptions import AGRAPIError

logger = logging.getLogger(__name__)

# Constants for entity and topic mapping (from agr_literature_service ateam_db_helpers)
CURIE_PREFIX_LIST = ["FB", "MGI", "RGD", "SGD", "WB", "XenBase", "ZFIN"]
TOPIC_CATEGORY_ATP = "ATP:0000002"


class DatabaseConfig:
    """Configuration for database connection."""

    def __init__(self) -> None:
        """Initialize database configuration from environment variables."""
        self.username = environ.get('PERSISTENT_STORE_DB_USERNAME', 'unknown')
        self.password = environ.get('PERSISTENT_STORE_DB_PASSWORD', 'unknown')
        self.host = environ.get('PERSISTENT_STORE_DB_HOST', 'localhost')
        self.port = environ.get('PERSISTENT_STORE_DB_PORT', '5432')
        self.database = environ.get('PERSISTENT_STORE_DB_NAME', 'unknown')

    @property
    def connection_string(self) -> str:
        """Get SQLAlchemy connection string."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class DatabaseMethods:
    """Direct database access methods for AGR entities."""

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        """Initialize database methods.

        Args:
            config: Database configuration (defaults to environment variables)
        """
        self.config = config or DatabaseConfig()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker[Session]] = None

    def _get_engine(self) -> Engine:
        """Get or create database engine."""
        if self._engine is None:
            self._engine = create_engine(self.config.connection_string)
        return self._engine

    def _get_session_factory(self) -> sessionmaker[Session]:
        """Get or create session factory."""
        if self._session_factory is None:
            engine = self._get_engine()
            self._session_factory = sessionmaker(
                bind=engine,
                autoflush=False,
                autocommit=False
            )
        return self._session_factory

    def _create_session(self) -> Session:
        """Create a new database session."""
        session_factory = self._get_session_factory()
        return session_factory()

    def get_genes_by_taxon(
        self,
        taxon_curie: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_obsolete: bool = False
    ) -> List[Gene]:
        """Get genes from the database by taxon.

        This uses direct SQL queries for efficient data retrieval,
        returning minimal gene information (ID and symbol).

        Args:
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')
            limit: Maximum number of genes to return
            offset: Number of genes to skip (for pagination)
            include_obsolete: If False, filter out obsolete genes (default: False)

        Returns:
            List of Gene objects with basic information

        Example:
            # Get C. elegans genes
            genes = db_methods.get_genes_by_taxon('NCBITaxon:6239', limit=100)
        """
        session = self._create_session()
        try:
            # Build WHERE clause based on include_obsolete parameter
            obsolete_filter = "" if include_obsolete else """
                slota.obsolete = false
            AND
                be.obsolete = false
            AND"""

            sql_query = text(f"""
            SELECT
                be.primaryexternalid as "primaryExternalId",
                slota.displaytext as geneSymbol
            FROM
                biologicalentity be
                JOIN slotannotation slota ON be.id = slota.singlegene_id
                JOIN ontologyterm taxon ON be.taxon_id = taxon.id
            WHERE
                {obsolete_filter}
                slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
            AND
                taxon.curie = :species_taxon
            ORDER BY
                be.primaryexternalid
            """)

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {'species_taxon': taxon_curie}).fetchall()

            genes = []
            for row in rows:
                try:
                    # Create minimal Gene object from database results
                    gene_data = {
                        'primaryExternalId': row[0],
                        'curie': row[0],  # Use primaryExternalId as curie
                        'geneSymbol': {
                            'displayText': row[1],
                            'formatText': row[1]
                        }
                    }
                    gene = Gene(**gene_data)
                    genes.append(gene)
                except ValidationError as e:
                    logger.warning(f"Failed to parse gene data from DB: {e}")

            return genes

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_genes_raw(
        self,
        taxon_curie: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get genes as raw dictionary data.

        This is a lightweight alternative that returns dictionaries instead
        of Pydantic models.

        Args:
            taxon_curie: NCBI Taxon CURIE
            limit: Maximum number of genes to return
            offset: Number of genes to skip

        Returns:
            List of dictionaries with gene_id and gene_symbol keys
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT
                be.primaryexternalid as geneId,
                slota.displaytext as geneSymbol
            FROM
                biologicalentity be
                JOIN slotannotation slota ON be.id = slota.singlegene_id
                JOIN ontologyterm taxon ON be.taxon_id = taxon.id
            WHERE
                slota.obsolete = false
            AND
                be.obsolete = false
            AND
                slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
            AND
                taxon.curie = :species_taxon
            ORDER BY
                be.primaryexternalid
            """)

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {'species_taxon': taxon_curie}).fetchall()
            return [{"gene_id": row[0], "gene_symbol": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_alleles_by_taxon(
        self,
        taxon_curie: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        wb_extraction_subset: bool = False
    ) -> List[Allele]:
        """Get alleles from the database by taxon.

        This uses direct SQL queries for efficient data retrieval,
        returning minimal allele information (ID and symbol).

        Args:
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')
            limit: Maximum number of alleles to return
            offset: Number of alleles to skip (for pagination)
            wb_extraction_subset: If True, apply WB-specific filtering for allele extraction:
                - Only WB alleles (WB:WBVar prefix, excludes transgenes)
                - Excludes Million_mutation_project collection alleles
                - Excludes fallback WBVar symbols
                - Forces taxon to NCBITaxon:6239 (C. elegans)

        Returns:
            List of Allele objects with basic information

        Example:
            # Get C. elegans alleles
            alleles = db_methods.get_alleles_by_taxon('NCBITaxon:6239', limit=100)

            # Get WB alleles for extraction (with filtering)
            alleles = db_methods.get_alleles_by_taxon(
                'NCBITaxon:6239',
                limit=1000,
                wb_extraction_subset=True
            )
        """
        session = self._create_session()
        try:
            if wb_extraction_subset:
                # Special query for WB allele extraction
                sql_query = text("""
                SELECT DISTINCT
                    be.primaryexternalid,
                    sa.displaytext
                FROM
                    biologicalentity be
                    JOIN slotannotation sa ON be.id = sa.singleallele_id
                    JOIN allele al ON be.id = al.id
                    JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE
                    sa.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                AND NOT EXISTS (
                    SELECT 1
                    FROM vocabularyterm vt
                    WHERE vt.id = al.incollection_id
                      AND vt.name ILIKE 'Million_mutation_project'
                )
                AND sa.displaytext NOT ILIKE 'WBVar%'
                AND be.primaryexternalid LIKE 'WB:WBVar%'
                AND ot.curie = 'NCBITaxon:6239'
                ORDER BY
                    be.primaryexternalid
                """)

                # Add pagination if specified
                if limit is not None:
                    sql_query = text(str(sql_query) + f" LIMIT {limit}")
                if offset is not None:
                    sql_query = text(str(sql_query) + f" OFFSET {offset}")

                rows = session.execute(sql_query).fetchall()
            else:
                # Standard allele query
                sql_query = text("""
                SELECT
                    be.primaryexternalid as "primaryExternalId",
                    slota.displaytext as alleleSymbol
                FROM
                    biologicalentity be
                    JOIN allele a ON be.id = a.id
                    JOIN slotannotation slota ON a.id = slota.singleallele_id
                    JOIN ontologyterm taxon ON be.taxon_id = taxon.id
                WHERE
                    slota.obsolete = false
                AND
                    be.obsolete = false
                AND
                    slota.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                AND
                    taxon.curie = :taxon_curie
                ORDER BY
                    be.primaryexternalid
                """)

                # Add pagination if specified
                if limit is not None:
                    sql_query = text(str(sql_query) + f" LIMIT {limit}")
                if offset is not None:
                    sql_query = text(str(sql_query) + f" OFFSET {offset}")

                rows = session.execute(sql_query, {'taxon_curie': taxon_curie}).fetchall()

            alleles = []
            for row in rows:
                try:
                    # Create minimal Allele object from database results
                    allele_data = {
                        'primaryExternalId': row[0],
                        'curie': row[0],  # Use primaryExternalId as curie
                        'alleleSymbol': {
                            'displayText': row[1],
                            'formatText': row[1]
                        }
                    }
                    allele = Allele(**allele_data)
                    alleles.append(allele)
                except ValidationError as e:
                    logger.warning(f"Failed to parse allele data from DB: {e}")

            return alleles

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_alleles_raw(
        self,
        taxon_curie: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get alleles as raw dictionary data.

        This is a lightweight alternative that returns dictionaries instead
        of Pydantic models.

        Args:
            taxon_curie: NCBI Taxon CURIE
            limit: Maximum number of alleles to return
            offset: Number of alleles to skip

        Returns:
            List of dictionaries with allele_id and allele_symbol keys
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT
                be.primaryexternalid as alleleId,
                slota.displaytext as alleleSymbol
            FROM
                biologicalentity be
                JOIN allele a ON be.id = a.id
                JOIN slotannotation slota ON a.id = slota.singleallele_id
                JOIN ontologyterm taxon ON be.taxon_id = taxon.id
            WHERE
                slota.obsolete = false
            AND
                be.obsolete = false
            AND
                slota.slotannotationtype = 'AlleleSymbolSlotAnnotation'
            AND
                taxon.curie = :taxon_curie
            ORDER BY
                be.primaryexternalid
            """)

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {'taxon_curie': taxon_curie}).fetchall()
            return [{"allele_id": row[0], "allele_symbol": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Expression annotation methods
    def get_expression_annotations(
        self,
        taxon_curie: str
    ) -> List[Dict[str, str]]:
        """Get expression annotations from the A-team database.

        Args:
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')

        Returns:
            List of dictionaries containing gene_id, gene_symbol, and anatomy_id

        Example:
            annotations = db_methods.get_expression_annotations('NCBITaxon:6239')
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT
                be.primaryexternalid geneId,
                slota.displaytext geneSymbol,
                ot.curie anatomyId
            FROM
                geneexpressionannotation gea JOIN expressionpattern ep ON gea.expressionpattern_id = ep.id
                                             JOIN anatomicalsite asi ON ep.whereexpressed_id = asi.id
                                             JOIN ontologyterm ot ON asi.anatomicalstructure_id = ot.id
                                             JOIN gene g ON gea.expressionannotationsubject_id = g.id
                                             JOIN biologicalentity be ON g.id = be.id
                                             JOIN ontologyterm ot_taxon ON be.taxon_id = ot_taxon.id
                                             JOIN slotannotation slota ON g.id = slota.singlegene_id
            WHERE
                slota.obsolete = false
            AND
                be.obsolete = false
            AND
                slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
            AND
                ot.curie <> 'WBbt:0000100'
            AND ot_taxon.curie = :taxon_id
            """)
            rows = session.execute(sql_query, {'taxon_id': taxon_curie}).fetchall()
            return [{"gene_id": row[0], "gene_symbol": row[1], "anatomy_id": row[2]} for row in rows]
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Ontology methods
    def get_ontology_pairs(
        self,
        curie_prefix: str
    ) -> List[Dict[str, Any]]:
        """Get ontology term parent-child relationships.

        Args:
            curie_prefix: Ontology CURIE prefix (e.g., 'DOID', 'GO')

        Returns:
            List of dictionaries containing parent-child ontology term relationships

        Example:
            pairs = db_methods.get_ontology_pairs('DOID')
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT DISTINCT
                otp.curie parentCurie,
                otp.name parentName,
                otp.namespace parentType,
                otp.obsolete parentIsObsolete,
                otc.curie childCurie,
                otc.name childName,
                otc.namespace childType,
                otc.obsolete childIsObsolete,
                jsonb_array_elements_text(otpc.closuretypes) AS relType
            FROM
                ontologyterm otc JOIN ontologytermclosure otpc ON otc.id = otpc.closuresubject_id
                                 JOIN ontologyterm otp ON otpc.closureobject_id = otp.id
            WHERE
                otp.curie LIKE :curieprefix
            AND
                otpc.distance = 1
            AND
                otpc.closuretypes in ('["part_of"]', '["is_a"]')
            """)
            rows = session.execute(sql_query, {'curieprefix': f"{curie_prefix}%"}).fetchall()
            return [
                {
                    "parent_curie": row[0],
                    "parent_name": row[1],
                    "parent_type": row[2],
                    "parent_is_obsolete": row[3],
                    "child_curie": row[4],
                    "child_name": row[5],
                    "child_type": row[6],
                    "child_is_obsolete": row[7],
                    "rel_type": row[8]
                } for row in rows]
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Species/Data Provider methods
    def get_data_providers(self) -> List[tuple]:
        """Get data providers from the A-team database.

        Returns:
            List of tuples containing (species_display_name, taxon_curie)

        Example:
            providers = db_methods.get_data_providers()
            # [('Caenorhabditis elegans', 'NCBITaxon:6239'), ...]
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT
                s.displayName, t.curie
            FROM
                species s
            JOIN
                ontologyterm t ON s.taxon_id = t.id
            WHERE
                s.obsolete = false
            AND
                s.assembly_curie is not null
            """)
            rows = session.execute(sql_query).fetchall()
            return [(row[0], row[1]) for row in rows]
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Disease annotation methods
    def get_disease_annotations(
        self,
        taxon_curie: str
    ) -> List[Dict[str, str]]:
        """Get direct and indirect disease ontology (DO) annotations.

        This retrieves disease annotations from multiple sources:
        - Direct: gene -> DO term (via genediseaseannotation)
        - Indirect from allele: gene from inferredgene_id or asserted genes
        - Indirect from AGM: gene from inferredgene_id or asserted genes
        - Disease via orthology: gene -> DO term via human orthologs

        Args:
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')

        Returns:
            List of dictionaries containing gene_id, gene_symbol, do_id, relationship_type

        Example:
            annotations = db_methods.get_disease_annotations('NCBITaxon:6239')
        """
        session = self._create_session()
        try:
            # Combined query using UNION to get all disease annotations in one go
            union_query = text("""
                -- Direct gene -> DO term annotations
                SELECT
                    be.primaryexternalid AS "geneId",
                    slota.displaytext AS "geneSymbol",
                    ot.curie AS "doId",
                    rel.name AS "relationshipType"
                FROM
                    diseaseannotation da
                JOIN genediseaseannotation gda ON da.id = gda.id
                JOIN gene g ON gda.diseaseannotationsubject_id = g.id
                JOIN biologicalentity be ON g.id = be.id
                JOIN ontologyterm ot ON da.diseaseannotationobject_id = ot.id
                JOIN slotannotation slota ON g.id = slota.singlegene_id AND slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
                JOIN vocabularyterm rel ON da.relation_id = rel.id
                WHERE
                    da.obsolete = false
                AND da.negated = false
                AND ot.namespace = 'disease_ontology'
                AND be.taxon_id = (SELECT id FROM ontologyterm WHERE curie = :taxon_id)

                UNION

                -- Allele disease annotations: inferred gene (at most one)
                SELECT
                    be.primaryexternalid AS "geneId",
                    slota.displaytext AS "geneSymbol",
                    ot.curie AS "doId",
                    rel.name AS "relationshipType"
                FROM
                    allelediseaseannotation ada
                JOIN diseaseannotation da ON ada.id = da.id
                JOIN biologicalentity be ON ada.inferredgene_id = be.id
                JOIN slotannotation slota ON be.id = slota.singlegene_id AND slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
                JOIN ontologyterm ot ON da.diseaseannotationobject_id = ot.id
                JOIN vocabularyterm rel ON da.relation_id = rel.id
                WHERE
                    da.obsolete = false
                AND da.negated = false
                AND ot.namespace = 'disease_ontology'
                AND be.taxon_id = (SELECT id FROM ontologyterm WHERE curie = :taxon_id)
                AND ada.inferredgene_id IS NOT NULL

                UNION

                -- Allele disease annotations: asserted gene (only if exactly one)
                SELECT
                    be.primaryexternalid AS "geneId",
                    slota.displaytext AS "geneSymbol",
                    ot.curie AS "doId",
                    rel.name AS "relationshipType"
                FROM
                    allelediseaseannotation ada
                JOIN diseaseannotation da ON ada.id = da.id
                JOIN allelediseaseannotation_gene adg ON ada.id = adg.allelediseaseannotation_id
                JOIN biologicalentity be ON adg.assertedgenes_id = be.id
                JOIN slotannotation slota ON be.id = slota.singlegene_id AND slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
                JOIN ontologyterm ot ON da.diseaseannotationobject_id = ot.id
                JOIN vocabularyterm rel ON da.relation_id = rel.id
                WHERE
                    da.obsolete = false
                AND da.negated = false
                AND ot.namespace = 'disease_ontology'
                AND be.taxon_id = (SELECT id FROM ontologyterm WHERE curie = :taxon_id)
                AND ada.id IN (
                    SELECT adg2.allelediseaseannotation_id
                    FROM allelediseaseannotation_gene adg2
                    GROUP BY adg2.allelediseaseannotation_id
                    HAVING COUNT(*) = 1
                )

                UNION

                -- AGM disease annotations: inferred gene (at most one)
                SELECT
                    be.primaryexternalid AS "geneId",
                    slota.displaytext AS "geneSymbol",
                    ot.curie AS "doId",
                    rel.name AS "relationshipType"
                FROM
                    agmdiseaseannotation agmda
                JOIN diseaseannotation da ON agmda.id = da.id
                JOIN biologicalentity be ON agmda.inferredgene_id = be.id
                JOIN slotannotation slota ON be.id = slota.singlegene_id AND slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
                JOIN ontologyterm ot ON da.diseaseannotationobject_id = ot.id
                JOIN vocabularyterm rel ON da.relation_id = rel.id
                WHERE
                    da.obsolete = false
                AND da.negated = false
                AND ot.namespace = 'disease_ontology'
                AND be.taxon_id = (SELECT id FROM ontologyterm WHERE curie = :taxon_id)
                AND agmda.inferredgene_id IS NOT NULL

                UNION

                -- AGM disease annotations: asserted gene (only if exactly one)
                SELECT
                    be.primaryexternalid AS "geneId",
                    slota.displaytext AS "geneSymbol",
                    ot.curie AS "doId",
                    rel.name AS "relationshipType"
                FROM
                    agmdiseaseannotation agmda
                JOIN diseaseannotation da ON agmda.id = da.id
                JOIN agmdiseaseannotation_gene agmg ON agmda.id = agmg.agmdiseaseannotation_id
                JOIN biologicalentity be ON agmg.assertedgenes_id = be.id
                JOIN slotannotation slota ON be.id = slota.singlegene_id AND slota.slotannotationtype = 'GeneSymbolSlotAnnotation'
                JOIN ontologyterm ot ON da.diseaseannotationobject_id = ot.id
                JOIN vocabularyterm rel ON da.relation_id = rel.id
                WHERE
                    da.obsolete = false
                AND da.negated = false
                AND ot.namespace = 'disease_ontology'
                AND be.taxon_id = (SELECT id FROM ontologyterm WHERE curie = :taxon_id)
                AND agmda.id IN (
                    SELECT agmg2.agmdiseaseannotation_id
                    FROM agmdiseaseannotation_gene agmg2
                    GROUP BY agmg2.agmdiseaseannotation_id
                    HAVING COUNT(*) = 1
                )

                UNION

                -- Disease via orthology annotations: gene -> DO term via human orthologs
                SELECT
                    be_subject.primaryexternalid AS "geneId",
                    slota_subject.displaytext AS "geneSymbol",
                    ot.curie AS "doId",
                    'implicated_via_orthology' AS "relationshipType"
                FROM
                    genetogeneorthology ggo
                JOIN genetogeneorthologygenerated gtog ON ggo.id = gtog.id AND gtog.strictfilter = true
                JOIN gene g_subject ON ggo.subjectgene_id = g_subject.id
                JOIN gene g_human ON ggo.objectgene_id = g_human.id
                JOIN biologicalentity be_subject ON g_subject.id = be_subject.id
                JOIN biologicalentity be_human ON g_human.id = be_human.id
                JOIN genediseaseannotation gda ON g_human.id = gda.diseaseannotationsubject_id
                JOIN diseaseannotation da ON gda.id = da.id
                JOIN ontologyterm ot ON da.diseaseannotationobject_id = ot.id
                JOIN vocabularyterm rel ON da.relation_id = rel.id
                JOIN slotannotation slota_subject ON g_subject.id = slota_subject.singlegene_id AND slota_subject.slotannotationtype = 'GeneSymbolSlotAnnotation'
                WHERE
                    da.obsolete = false
                AND da.negated = false
                AND ot.namespace = 'disease_ontology'
                AND be_subject.taxon_id = (SELECT id FROM ontologyterm WHERE curie = :taxon_id)
                AND be_human.taxon_id = (SELECT id FROM ontologyterm WHERE curie = 'NCBITaxon:9606')
                AND rel.name = 'is_implicated_in'
                AND slota_subject.obsolete = false
                AND be_subject.obsolete = false
            """)

            # Execute the combined query
            rows = session.execute(union_query, {"taxon_id": taxon_curie}).mappings().all()

            # UNION automatically removes duplicates, but we'll still use seen set to be safe
            seen = set()
            results = []
            for row in rows:
                gene_id = row["geneId"]
                gene_symbol = row["geneSymbol"]
                do_id = row["doId"]
                relationship_type = row["relationshipType"]
                key = (gene_id, gene_symbol, do_id, relationship_type)
                if key not in seen:
                    results.append({
                        "gene_id": gene_id,
                        "gene_symbol": gene_symbol,
                        "do_id": do_id,
                        "relationship_type": relationship_type
                    })
                    seen.add(key)
            return results
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Ortholog methods
    def get_best_human_orthologs_for_taxon(
        self,
        taxon_curie: str
    ) -> Dict[str, tuple]:
        """Get the best human orthologs for all genes from a given species.

        Args:
            taxon_curie: The taxon curie of the species for which to find orthologs

        Returns:
            Dictionary mapping each gene ID to a tuple:
            (list of best human orthologs, bool indicating if any orthologs were excluded)
            Each ortholog is represented as a list: [ortholog_id, ortholog_symbol, ortholog_full_name]

        Example:
            orthologs = db_methods.get_best_human_orthologs_for_taxon('NCBITaxon:6239')
            # {'WBGene00000001': ([['HGNC:123', 'GENE1', 'Gene 1 full name']], False), ...}
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT
                subj_be.primaryexternalid AS gene_id,
                subj_slota.displaytext AS gene_symbol,
                obj_be.primaryexternalid AS ortho_id,
                obj_slota.displaytext AS ortho_symbol,
                obj_full_name_slota.displaytext AS ortho_full_name,
                COUNT(DISTINCT pm.predictionmethodsmatched_id) AS method_count
            FROM genetogeneorthology gto
            JOIN genetogeneorthologygenerated gtog ON gto.id = gtog.id AND gtog.strictfilter = true
            JOIN genetogeneorthologygenerated_predictionmethodsmatched pm ON gtog.id = pm.genetogeneorthologygenerated_id
            JOIN gene subj_gene ON gto.subjectgene_id = subj_gene.id
            JOIN biologicalentity subj_be ON subj_gene.id = subj_be.id
            JOIN slotannotation subj_slota ON subj_gene.id = subj_slota.singlegene_id AND subj_slota.slotannotationtype = 'GeneSymbolSlotAnnotation' AND subj_slota.obsolete = false
            JOIN gene obj_gene ON gto.objectgene_id = obj_gene.id
            JOIN biologicalentity obj_be ON obj_gene.id = obj_be.id
            JOIN slotannotation obj_slota ON obj_gene.id = obj_slota.singlegene_id AND obj_slota.slotannotationtype = 'GeneSymbolSlotAnnotation' AND obj_slota.obsolete = false
            JOIN slotannotation obj_full_name_slota ON obj_gene.id = obj_full_name_slota.singlegene_id AND obj_full_name_slota.slotannotationtype = 'GeneFullNameSlotAnnotation' AND obj_full_name_slota.obsolete = false
            JOIN ontologyterm obj_taxon ON obj_be.taxon_id = obj_taxon.id
            JOIN ontologyterm subj_taxon ON subj_be.taxon_id = subj_taxon.id
            WHERE subj_taxon.curie = :taxon_curie
              AND obj_taxon.curie = 'NCBITaxon:9606'
              AND subj_slota.obsolete = false
              AND obj_slota.obsolete = false
              AND subj_be.obsolete = false
              AND obj_be.obsolete = false
            GROUP BY gto.subjectgene_id, gto.objectgene_id, subj_be.primaryexternalid, subj_slota.displaytext, obj_be.primaryexternalid, obj_slota.displaytext, obj_full_name_slota.displaytext
            """)
            rows = session.execute(sql_query, {'taxon_curie': taxon_curie}).mappings().all()

            from collections import defaultdict
            gene_orthologs = defaultdict(list)
            for row in rows:
                gene_id = row['gene_id']
                ortho_info = [row['ortho_id'], row['ortho_symbol'], row['ortho_full_name']]
                method_count = row['method_count']
                gene_orthologs[gene_id].append((ortho_info, method_count))

            result = {}
            for gene_id, ortho_list in gene_orthologs.items():
                if not ortho_list:
                    continue
                max_count = max(x[1] for x in ortho_list)
                best_orthos = [x[0] for x in ortho_list if x[1] == max_count]
                excluded = len(ortho_list) > len(best_orthos)
                result[gene_id] = (best_orthos, excluded)
            return result
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Entity mapping methods (from agr_literature_service ateam_db_helpers.py)
    def map_entity_names_to_curies(
        self,
        entity_type: str,
        entity_names: List[str],
        taxon_curie: str
    ) -> List[Dict[str, Any]]:
        """Map entity names to their CURIEs by searching slot annotations.

        Args:
            entity_type: Type of entity ('gene', 'allele', 'agm', 'construct', 'targeting reagent')
            entity_names: List of entity names/symbols to search for
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')

        Returns:
            List of dictionaries with entity_curie, is_obsolete, entity (name) keys

        Example:
            results = db_methods.map_entity_names_to_curies('gene', ['ACT1', 'CDC42'], 'NCBITaxon:559292')
        """
        if not entity_names:
            return []

        session = self._create_session()
        try:
            entity_type = entity_type.lower()
            entity_names_upper = [name.upper() for name in entity_names]

            if entity_type == 'gene':
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, sa.obsolete, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singlegene_id
                JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE sa.slotannotationtype IN (
                    'GeneSymbolSlotAnnotation',
                    'GeneSystematicNameSlotAnnotation',
                    'GeneFullNameSlotAnnotation'
                )
                AND UPPER(sa.displaytext) IN :entity_name_list
                AND ot.curie = :taxon
                """)
            elif entity_type == 'allele':
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, sa.obsolete, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleallele_id
                JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE sa.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                AND UPPER(sa.displaytext) IN :entity_name_list
                AND ot.curie = :taxon
                """)
            elif entity_type in ['agm', 'agms', 'strain', 'genotype', 'fish']:
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, sa.obsolete, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleagm_id
                JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE sa.slotannotationtype IN (
                    'AgmFullNameSlotAnnotation',
                    'AgmSecondaryIdSlotAnnotation',
                    'AgmSynonymSlotAnnotation'
                )
                AND UPPER(sa.displaytext) IN :entity_name_list
                AND ot.curie = :taxon
                """)
            elif 'targeting reagent' in entity_type:
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, be.obsolete, str.name
                FROM biologicalentity be
                JOIN sequencetargetingreagent str ON be.id = str.id
                JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE UPPER(str.name) IN :entity_name_list
                AND ot.curie = :taxon
                """)
            elif entity_type == 'construct':
                sql_query = text("""
                SELECT DISTINCT r.primaryexternalid, sa.obsolete, sa.displaytext
                FROM reagent r
                JOIN slotannotation sa ON r.id = sa.singleconstruct_id
                WHERE sa.slotannotationtype IN (
                    'ConstructFullNameSlotAnnotation',
                    'ConstructSymbolSlotAnnotation'
                )
                AND UPPER(sa.displaytext) IN :entity_name_list
                """)
                rows = session.execute(sql_query, {'entity_name_list': tuple(entity_names_upper)}).fetchall()
                return [{"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2]} for row in rows]
            else:
                raise AGRAPIError(f"Unknown entity_type '{entity_type}'")

            rows = session.execute(sql_query, {
                'entity_name_list': tuple(entity_names_upper),
                'taxon': taxon_curie
            }).fetchall()

            return [{"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def map_entity_curies_to_info(
        self,
        entity_type: str,
        entity_curies: List[str]
    ) -> List[Dict[str, Any]]:
        """Map entity CURIEs to their basic information.

        Args:
            entity_type: Type of entity ('gene', 'allele', 'agm', 'construct', 'targeting reagent')
            entity_curies: List of entity CURIEs to look up

        Returns:
            List of dictionaries with entity_curie, is_obsolete keys

        Example:
            results = db_methods.map_entity_curies_to_info('gene', ['SGD:S000000001', 'SGD:S000000002'])
        """
        if not entity_curies:
            return []

        session = self._create_session()
        try:
            entity_type = entity_type.lower()
            entity_curies_upper = [curie.upper() for curie in entity_curies]

            if entity_type in ['gene', 'allele']:
                entity_table_name = entity_type
                sql_query = text(f"""
                SELECT DISTINCT be.primaryexternalid, be.obsolete, be.primaryexternalid
                FROM biologicalentity be, {entity_table_name} ent_tbl
                WHERE be.id = ent_tbl.id
                AND UPPER(be.primaryexternalid) IN :entity_curie_list
                """)
            elif entity_type == 'construct':
                sql_query = text("""
                SELECT DISTINCT r.primaryexternalid, r.obsolete, r.primaryexternalid
                FROM reagent r, construct c
                WHERE r.id = c.id
                AND UPPER(r.primaryexternalid) IN :entity_curie_list
                """)
            elif entity_type in ['agm', 'agms', 'strain', 'genotype', 'fish']:
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, be.obsolete, be.primaryexternalid
                FROM biologicalentity be, affectedgenomicmodel agm
                WHERE be.id = agm.id
                AND UPPER(be.primaryexternalid) IN :entity_curie_list
                """)
            elif 'targeting reagent' in entity_type:
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, be.obsolete, be.primaryexternalid
                FROM biologicalentity be, sequencetargetingreagent str
                WHERE be.id = str.id
                AND UPPER(be.primaryexternalid) IN :entity_curie_list
                """)
            else:
                raise AGRAPIError(f"Unknown entity_type '{entity_type}'")

            rows = session.execute(sql_query, {'entity_curie_list': tuple(entity_curies_upper)}).fetchall()
            return [{"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def map_curies_to_names(
        self,
        category: str,
        curies: List[str]
    ) -> Dict[str, str]:
        """Map entity CURIEs to their display names.

        Args:
            category: Category of entity ('gene', 'allele', 'construct', 'agm', 'species', etc.)
            curies: List of CURIEs to map

        Returns:
            Dictionary mapping CURIE to display name

        Example:
            mapping = db_methods.map_curies_to_names('gene', ['SGD:S000000001'])
            # {'SGD:S000000001': 'ACT1'}
        """
        if not curies:
            return {}

        session = self._create_session()
        try:
            category = category.lower()

            if category == 'gene':
                sql_query = text("""
                SELECT be.primaryexternalid, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singlegene_id
                WHERE be.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'GeneSymbolSlotAnnotation'
                """)
            elif 'allele' in category:
                sql_query = text("""
                SELECT be.primaryexternalid, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleallele_id
                WHERE be.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                """)
            elif category in ['affected genome model', 'agm', 'strain', 'genotype', 'fish']:
                sql_query = text("""
                SELECT DISTINCT be.primaryexternalid, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleagm_id
                WHERE be.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'AgmFullNameSlotAnnotation'
                """)
            elif 'construct' in category:
                sql_query = text("""
                SELECT r.primaryexternalid, sa.displaytext
                FROM reagent r
                JOIN slotannotation sa ON r.id = sa.singleconstruct_id
                WHERE r.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'ConstructSymbolSlotAnnotation'
                """)
            elif category in ['species', 'ecoterm']:
                curies_upper = [curie.upper() for curie in curies]
                sql_query = text("""
                SELECT curie, name
                FROM ontologyterm
                WHERE UPPER(curie) IN :curies
                """)
                rows = session.execute(sql_query, {'curies': tuple(curies_upper)}).fetchall()
                return {row[0]: row[1] for row in rows}
            else:
                # Return identity mapping for unknown categories
                return {curie: curie for curie in curies}

            rows = session.execute(sql_query, {'curies': tuple(curies)}).fetchall()
            return {row[0]: row[1] for row in rows}

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # ATP/Topic ontology methods (from agr_literature_service ateam_db_helpers.py)
    def search_atp_topics(
        self,
        topic: Optional[str] = None,
        mod_abbr: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Search ATP ontology for topics.

        Args:
            topic: Topic name to search for (partial match, case-insensitive)
            mod_abbr: MOD abbreviation to filter by (e.g., 'WB', 'SGD')
            limit: Maximum number of results to return

        Returns:
            List of dictionaries with curie and name keys

        Example:
            topics = db_methods.search_atp_topics(topic='development', mod_abbr='WB')
        """
        session = self._create_session()
        try:
            if topic and mod_abbr:
                search_query = f"%{topic.upper()}%"
                sql_query = text("""
                SELECT DISTINCT ot.curie, ot.name
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                JOIN ontologyterm_subsets s ON ot.id = s.ontologyterm_id
                WHERE ot.ontologytermtype = 'ATPTerm'
                AND UPPER(ot.name) LIKE :search_query
                AND ot.obsolete = false
                AND ancestor.curie = :topic_category_atp
                AND s.subsets = :mod_abbr
                LIMIT :limit
                """)
                rows = session.execute(sql_query, {
                    'search_query': search_query,
                    'topic_category_atp': TOPIC_CATEGORY_ATP,
                    'mod_abbr': f'{mod_abbr}_tag',
                    'limit': limit
                }).fetchall()
            elif topic:
                search_query = f"%{topic.upper()}%"
                sql_query = text("""
                SELECT DISTINCT ot.curie, ot.name
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                WHERE ot.ontologytermtype = 'ATPTerm'
                AND UPPER(ot.name) LIKE :search_query
                AND ot.obsolete = false
                AND ancestor.curie = :topic_category_atp
                LIMIT :limit
                """)
                rows = session.execute(sql_query, {
                    'search_query': search_query,
                    'topic_category_atp': TOPIC_CATEGORY_ATP,
                    'limit': limit
                }).fetchall()
            elif mod_abbr:
                sql_query = text("""
                SELECT DISTINCT ot.curie, ot.name
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                JOIN ontologyterm_subsets s ON ot.id = s.ontologyterm_id
                WHERE ot.ontologytermtype = 'ATPTerm'
                AND ancestor.curie = :topic_category_atp
                AND s.subsets = :mod_abbr
                """)
                rows = session.execute(sql_query, {
                    'topic_category_atp': TOPIC_CATEGORY_ATP,
                    'mod_abbr': f'{mod_abbr}_tag'
                }).fetchall()
            else:
                return []

            return [{"curie": row[0], "name": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_atp_descendants(
        self,
        ancestor_curie: str
    ) -> List[Dict[str, str]]:
        """Get all descendants of an ATP ontology term.

        Args:
            ancestor_curie: ATP CURIE (e.g., 'ATP:0000002')

        Returns:
            List of dictionaries with curie and name keys

        Example:
            descendants = db_methods.get_atp_descendants('ATP:0000002')
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT DISTINCT ot.curie, ot.name
            FROM ontologyterm ot
            JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
            JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
            WHERE ot.ontologytermtype = 'ATPTerm'
            AND ot.obsolete = false
            AND ancestor.curie = :ancestor_curie
            """)
            rows = session.execute(sql_query, {'ancestor_curie': ancestor_curie}).fetchall()
            return [{"curie": row[0], "name": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_ontology_ancestors_or_descendants(
        self,
        ontology_node: str,
        direction: str = 'descendants'
    ) -> List[str]:
        """Get ancestors or descendants of an ontology node.

        Args:
            ontology_node: Ontology term CURIE
            direction: 'ancestors' or 'descendants'

        Returns:
            List of CURIEs

        Example:
            desc = db_methods.search_ontology_ancestors_or_descendants('GO:0008150', 'descendants')
        """
        session = self._create_session()
        try:
            if direction == 'descendants':
                sql_query = text("""
                SELECT DISTINCT ot.curie
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                WHERE ancestor.curie = :ontology_node
                AND ot.obsolete = False
                """)
            else:  # ancestors
                sql_query = text("""
                SELECT DISTINCT ot.curie
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm descendant ON descendant.id = otc.closureobject_id
                WHERE descendant.curie = :ontology_node
                AND ot.obsolete = False
                """)

            rows = session.execute(sql_query, {'ontology_node': ontology_node}).fetchall()
            return [row[0] for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Species search methods (from agr_literature_service ateam_db_helpers.py)
    def search_species(
        self,
        species: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Search for species by name or CURIE.

        Args:
            species: Species name or CURIE prefix to search for
            limit: Maximum number of results

        Returns:
            List of dictionaries with curie and name keys

        Example:
            results = db_methods.search_species('elegans')
        """
        session = self._create_session()
        try:
            if species.upper().startswith("NCBITAXON"):
                search_query = f"{species.upper()}%"
                sql_query = text("""
                SELECT curie, name
                FROM ontologyterm
                WHERE ontologytermtype = 'NCBITaxonTerm'
                AND UPPER(curie) LIKE :search_query
                LIMIT :limit
                """)
            else:
                search_query = f"%{species.upper()}%"
                sql_query = text("""
                SELECT curie, name
                FROM ontologyterm
                WHERE ontologytermtype = 'NCBITaxonTerm'
                AND UPPER(name) LIKE :search_query
                LIMIT :limit
                """)

            rows = session.execute(sql_query, {'search_query': search_query, 'limit': limit}).fetchall()
            return [{"curie": row[0], "name": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def close(self) -> None:
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._session_factory = None
