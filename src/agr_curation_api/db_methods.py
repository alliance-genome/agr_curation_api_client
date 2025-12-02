"""Direct database access methods for AGR Curation API Client.

This module provides direct database access through SQL queries,
adapted from agr_genedescriptions/pipelines/alliance/ateam_db_helper.py
"""

import logging
from os import environ
from typing import List, Optional, Dict, Any, Set
from sqlalchemy.engine import Engine

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import ValidationError

from .models import Gene, Allele, OntologyTermResult, DiseaseAnnotation
from .exceptions import AGRAPIError

logger = logging.getLogger(__name__)

# Constants for entity and topic mapping (from agr_literature_service ateam_db_helpers)
CURIE_PREFIX_LIST = ["FB", "MGI", "RGD", "SGD", "WB", "XenBase", "ZFIN"]
TOPIC_CATEGORY_ATP = "ATP:0000002"


class DatabaseConfig:
    """Configuration for database connection."""

    def __init__(self) -> None:
        """Initialize database configuration from environment variables."""
        self.username = environ.get("PERSISTENT_STORE_DB_USERNAME", "unknown")
        self.password = environ.get("PERSISTENT_STORE_DB_PASSWORD", "unknown")
        self.host = environ.get("PERSISTENT_STORE_DB_HOST", "localhost")
        self.port = environ.get("PERSISTENT_STORE_DB_PORT", "5432")
        self.database = environ.get("PERSISTENT_STORE_DB_NAME", "unknown")

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
        """Get or create database engine.

        Uses pool_pre_ping to detect and reconnect stale connections,
        which is important for long-running test suites over SSM tunnels.
        """
        if self._engine is None:
            self._engine = create_engine(
                self.config.connection_string,
                pool_pre_ping=True,  # Verify connection is alive before each use
            )
        return self._engine

    def _get_session_factory(self) -> sessionmaker[Session]:
        """Get or create session factory."""
        if self._session_factory is None:
            engine = self._get_engine()
            self._session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
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
        include_obsolete: bool = False,
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
            obsolete_filter = (
                ""
                if include_obsolete
                else """
                slota.obsolete = false
            AND
                be.obsolete = false
            AND"""
            )

            sql_query = text(
                f"""
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
            """
            )

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {"species_taxon": taxon_curie}).fetchall()

            genes = []
            for row in rows:
                try:
                    # Create minimal Gene object from database results
                    gene_data = {
                        "primaryExternalId": row[0],
                        "curie": row[0],  # Use primaryExternalId as curie
                        "geneSymbol": {"displayText": row[1], "formatText": row[1]},
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
        self, taxon_curie: str, limit: Optional[int] = None, offset: Optional[int] = None
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
            sql_query = text(
                """
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
            """
            )

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {"species_taxon": taxon_curie}).fetchall()
            return [{"gene_id": row[0], "gene_symbol": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_gene(self, gene_id: str) -> Optional[Gene]:
        """Get a specific gene by ID from the database.

        This uses direct SQL queries to fetch complete gene information
        including symbol, full name, systematic name, gene type, and taxon.

        Args:
            gene_id: Gene CURIE or primary external ID (e.g., 'WB:WBGene00001044')

        Returns:
            Gene object with complete information, or None if not found

        Example:
            # Get a specific gene
            gene = db_methods.get_gene('WB:WBGene00001044')
            if gene:
                print(f"Symbol: {gene.geneSymbol.displayText}")
                print(f"Full name: {gene.geneFullName.displayText if gene.geneFullName else 'N/A'}")
        """
        session = self._create_session()
        try:
            # Query to get complete gene information
            sql_query = text(
                """
            SELECT
                be.primaryexternalid,
                be.curie,
                be.obsolete,
                be.internal,
                taxon.curie as taxon_curie,
                gt.name as genetype_name,
                symbol.displaytext as gene_symbol,
                symbol.formattext as gene_symbol_format,
                fullname.displaytext as gene_fullname,
                fullname.formattext as gene_fullname_format,
                sysname.displaytext as gene_systematic_name,
                sysname.formattext as gene_systematic_name_format
            FROM
                biologicalentity be
                JOIN gene g ON be.id = g.id
                LEFT JOIN ontologyterm taxon ON be.taxon_id = taxon.id
                LEFT JOIN ontologyterm gt ON g.genetype_id = gt.id
                LEFT JOIN slotannotation symbol ON g.id = symbol.singlegene_id
                    AND symbol.slotannotationtype = 'GeneSymbolSlotAnnotation'
                    AND symbol.obsolete = false
                LEFT JOIN slotannotation fullname ON g.id = fullname.singlegene_id
                    AND fullname.slotannotationtype = 'GeneFullNameSlotAnnotation'
                    AND fullname.obsolete = false
                LEFT JOIN slotannotation sysname ON g.id = sysname.singlegene_id
                    AND sysname.slotannotationtype = 'GeneSystematicNameSlotAnnotation'
                    AND sysname.obsolete = false
            WHERE
                be.primaryexternalid = :gene_id
            LIMIT 1
            """
            )

            row = session.execute(sql_query, {"gene_id": gene_id}).fetchone()

            if row is None:
                return None

            # Build Gene object from query results
            gene_data = {
                "primaryExternalId": row[0],
                "curie": row[1] or row[0],  # Use primaryExternalId as fallback
                "obsolete": row[2],
                "internal": row[3],
                "taxon": row[4],
            }

            # Add gene type if available
            if row[5]:
                gene_data["geneType"] = {"name": row[5]}

            # Add gene symbol if available
            if row[6]:
                gene_data["geneSymbol"] = {"displayText": row[6], "formatText": row[7] or row[6]}

            # Add gene full name if available
            if row[8]:
                gene_data["geneFullName"] = {"displayText": row[8], "formatText": row[9] or row[8]}

            # Add gene systematic name if available
            if row[10]:
                gene_data["geneSystematicName"] = {"displayText": row[10], "formatText": row[11] or row[10]}

            try:
                gene = Gene(**gene_data)
                return gene
            except ValidationError as e:
                logger.warning(f"Failed to parse gene data from DB for {gene_id}: {e}")
                return None

        except Exception as e:
            raise AGRAPIError(f"Database query failed for gene {gene_id}: {str(e)}")
        finally:
            session.close()

    def get_alleles_by_taxon(
        self,
        taxon_curie: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        wb_extraction_subset: bool = False,
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
                sql_query = text(
                    """
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
                """
                )

                # Add pagination if specified
                if limit is not None:
                    sql_query = text(str(sql_query) + f" LIMIT {limit}")
                if offset is not None:
                    sql_query = text(str(sql_query) + f" OFFSET {offset}")

                rows = session.execute(sql_query).fetchall()
            else:
                # Standard allele query
                sql_query = text(
                    """
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
                """
                )

                # Add pagination if specified
                if limit is not None:
                    sql_query = text(str(sql_query) + f" LIMIT {limit}")
                if offset is not None:
                    sql_query = text(str(sql_query) + f" OFFSET {offset}")

                rows = session.execute(sql_query, {"taxon_curie": taxon_curie}).fetchall()

            alleles = []
            for row in rows:
                try:
                    # Create minimal Allele object from database results
                    allele_data = {
                        "primaryExternalId": row[0],
                        "curie": row[0],  # Use primaryExternalId as curie
                        "alleleSymbol": {"displayText": row[1], "formatText": row[1]},
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
        self, taxon_curie: str, limit: Optional[int] = None, offset: Optional[int] = None
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
            sql_query = text(
                """
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
            """
            )

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {"taxon_curie": taxon_curie}).fetchall()
            return [{"allele_id": row[0], "allele_symbol": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_allele(self, allele_id: str) -> Optional[Allele]:
        """Get a specific allele by ID from the database.

        This uses direct SQL queries to fetch complete allele information
        including symbol, full name, collection, extinction status, and taxon.

        Args:
            allele_id: Allele CURIE or primary external ID (e.g., 'WB:WBVar00250000')

        Returns:
            Allele object with complete information, or None if not found

        Example:
            # Get a specific allele
            allele = db_methods.get_allele('WB:WBVar00250000')
            if allele:
                print(f"Symbol: {allele.alleleSymbol.displayText}")
                print(f"Full name: {allele.alleleFullName.displayText if allele.alleleFullName else 'N/A'}")
                print(f"Is extinct: {allele.isExtinct}")
        """
        session = self._create_session()
        try:
            # Query to get complete allele information
            sql_query = text(
                """
            SELECT
                be.primaryexternalid,
                be.curie,
                be.obsolete,
                be.internal,
                taxon.curie as taxon_curie,
                a.isextinct,
                coll.name as collection_name,
                symbol.displaytext as allele_symbol,
                symbol.formattext as allele_symbol_format,
                fullname.displaytext as allele_fullname,
                fullname.formattext as allele_fullname_format
            FROM
                biologicalentity be
                JOIN allele a ON be.id = a.id
                LEFT JOIN ontologyterm taxon ON be.taxon_id = taxon.id
                LEFT JOIN vocabularyterm coll ON a.incollection_id = coll.id
                LEFT JOIN slotannotation symbol ON a.id = symbol.singleallele_id
                    AND symbol.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                    AND symbol.obsolete = false
                LEFT JOIN slotannotation fullname ON a.id = fullname.singleallele_id
                    AND fullname.slotannotationtype = 'AlleleFullNameSlotAnnotation'
                    AND fullname.obsolete = false
            WHERE
                be.primaryexternalid = :allele_id
            LIMIT 1
            """
            )

            row = session.execute(sql_query, {"allele_id": allele_id}).fetchone()

            if row is None:
                return None

            # Build Allele object from query results
            allele_data = {
                "primaryExternalId": row[0],
                "curie": row[1] or row[0],  # Use primaryExternalId as fallback
                "obsolete": row[2],
                "internal": row[3],
                "taxon": row[4],
                "isExtinct": row[5],
            }

            # Add collection name if available (not in standard Allele model, but useful)
            # Note: This may need to be added to the Allele model or handled separately

            # Add allele symbol if available
            if row[7]:
                allele_data["alleleSymbol"] = {"displayText": row[7], "formatText": row[8] or row[7]}

            # Add allele full name if available
            if row[9]:
                allele_data["alleleFullName"] = {"displayText": row[9], "formatText": row[10] or row[9]}

            try:
                allele = Allele(**allele_data)
                return allele
            except ValidationError as e:
                logger.warning(f"Failed to parse allele data from DB for {allele_id}: {e}")
                return None

        except Exception as e:
            raise AGRAPIError(f"Database query failed for allele {allele_id}: {str(e)}")
        finally:
            session.close()

    # Expression annotation methods
    def get_expression_annotations(self, taxon_curie: str) -> List[Dict[str, str]]:
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
            sql_query = text(
                """
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
            """
            )
            rows = session.execute(sql_query, {"taxon_id": taxon_curie}).fetchall()
            return [{"gene_id": row[0], "gene_symbol": row[1], "anatomy_id": row[2]} for row in rows]
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Ontology methods
    def get_ontology_pairs(self, curie_prefix: str) -> List[Dict[str, Any]]:
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
            sql_query = text(
                """
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
            """
            )
            rows = session.execute(sql_query, {"curieprefix": f"{curie_prefix}%"}).fetchall()
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
                    "rel_type": row[8],
                }
                for row in rows
            ]
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
            sql_query = text(
                """
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
            """
            )
            rows = session.execute(sql_query).fetchall()
            return [(row[0], row[1]) for row in rows]
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Disease annotation methods
    def get_disease_annotations(self, taxon_curie: str) -> List[Dict[str, str]]:
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
            union_query = text(
                """
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
            """
            )

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
                    results.append(
                        {
                            "gene_id": gene_id,
                            "gene_symbol": gene_symbol,
                            "do_id": do_id,
                            "relationship_type": relationship_type,
                        }
                    )
                    seen.add(key)
            return results
        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Ortholog methods
    def get_best_human_orthologs_for_taxon(self, taxon_curie: str) -> Dict[str, tuple]:
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
            sql_query = text(
                """
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
            """
            )
            rows = session.execute(sql_query, {"taxon_curie": taxon_curie}).mappings().all()

            from collections import defaultdict

            gene_orthologs = defaultdict(list)
            for row in rows:
                gene_id = row["gene_id"]
                ortho_info = [row["ortho_id"], row["ortho_symbol"], row["ortho_full_name"]]
                method_count = row["method_count"]
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
        self, entity_type: str, entity_names: List[str], taxon_curie: str
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

            if entity_type == "gene":
                sql_query = text(
                    """
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
                """
                )
            elif entity_type == "allele":
                sql_query = text(
                    """
                SELECT DISTINCT be.primaryexternalid, sa.obsolete, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleallele_id
                JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE sa.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                AND UPPER(sa.displaytext) IN :entity_name_list
                AND ot.curie = :taxon
                """
                )
            elif entity_type in ["agm", "agms", "strain", "genotype", "fish"]:
                sql_query = text(
                    """
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
                """
                )
            elif "targeting reagent" in entity_type:
                sql_query = text(
                    """
                SELECT DISTINCT be.primaryexternalid, be.obsolete, str.name
                FROM biologicalentity be
                JOIN sequencetargetingreagent str ON be.id = str.id
                JOIN ontologyterm ot ON be.taxon_id = ot.id
                WHERE UPPER(str.name) IN :entity_name_list
                AND ot.curie = :taxon
                """
                )
            elif entity_type == "construct":
                sql_query = text(
                    """
                SELECT DISTINCT r.primaryexternalid, sa.obsolete, sa.displaytext
                FROM reagent r
                JOIN slotannotation sa ON r.id = sa.singleconstruct_id
                WHERE sa.slotannotationtype IN (
                    'ConstructFullNameSlotAnnotation',
                    'ConstructSymbolSlotAnnotation'
                )
                AND UPPER(sa.displaytext) IN :entity_name_list
                """
                )
                rows = session.execute(sql_query, {"entity_name_list": tuple(entity_names_upper)}).fetchall()
                return [{"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2]} for row in rows]
            else:
                raise AGRAPIError(f"Unknown entity_type '{entity_type}'")

            rows = session.execute(
                sql_query, {"entity_name_list": tuple(entity_names_upper), "taxon": taxon_curie}
            ).fetchall()

            return [{"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def search_entities(
        self, entity_type: str, search_pattern: str, taxon_curie: str, include_synonyms: bool = True, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search entities with partial matching and synonym support.

        This method enables flexible searching where partial matches are supported
        (e.g., "rut" will find "rutabaga"). Results are ordered by relevance:
        exact match > starts with > contains.

        Args:
            entity_type: Type of entity ('gene', 'allele', 'agm', 'construct')
            search_pattern: Search term (e.g., 'rut', 'rutabaga')
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:7227' for Drosophila)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of dictionaries with keys:
                - entity_curie: Primary external ID
                - is_obsolete: Whether entity is obsolete
                - entity: Matched display text
                - match_type: Type of match ('exact', 'starts_with', 'contains')
                - relevance: Relevance score (1=exact, 2=starts with, 3=contains)

        Example:
            # Find Drosophila genes matching "rut"
            results = db.search_entities(
                'gene', 'rut', 'NCBITaxon:7227'
            )
            # Returns: rutabaga gene (FB:FBgn0003301) with synonym matches

        Notes:
            - Case-insensitive search
            - Searches symbols, full names, systematic names, and synonyms
            - Performance: Uses tiered search strategy (exact → prefix → contains)
                - Tier 1 (Exact): UPPER(displaytext) = 'PATTERN' (uses B-tree index, 5-20ms)
                - Tier 2 (Prefix): UPPER(displaytext) LIKE 'PATTERN%' (uses B-tree index, 5-20ms)
                - Tier 3 (Contains): UPPER(displaytext) LIKE '%PATTERN%' (sequential scan, ~990ms)
            - Most queries hit Tier 1 or 2 (5-10x faster on average)
            - Tier 3 fallback ensures comprehensive results
            - Functional index on UPPER(displaytext) enables Tier 1 and 2 optimization

            Performance Characteristics:
            - Best case (exact match): 5-20ms (50-200x faster)
            - Good case (prefix match): 10-40ms (25-100x faster)
            - Worst case (contains only): ~1000ms (similar to previous performance)
            - Average case: ~100-200ms (5-10x faster)

            TODO - Future Enhancements:
            - This method is currently DATABASE-ONLY (no API or GraphQL implementation)
            - May be unified with ABC autocomplete functionality (pending discussion)
            - API/GraphQL implementations may be added later for complete data source fallback
            - When unified, should follow the db -> graphql -> api fallback pattern used in client.py
            - Phase 2 optimization: Add pg_trgm extension for 50-100x improvement (all queries 10-30ms)
        """
        if not search_pattern:
            return []

        session = self._create_session()
        try:
            entity_type = entity_type.lower()
            search_upper = search_pattern.upper()

            # Build SlotAnnotation types list based on entity type
            if entity_type == "gene":
                annotation_types = [
                    "'GeneSymbolSlotAnnotation'",
                    "'GeneSystematicNameSlotAnnotation'",
                    "'GeneFullNameSlotAnnotation'",
                ]
                if include_synonyms:
                    annotation_types.append("'GeneSynonymSlotAnnotation'")
            elif entity_type == "allele":
                annotation_types = ["'AlleleSymbolSlotAnnotation'"]
                if include_synonyms:
                    annotation_types.extend(["'AlleleFullNameSlotAnnotation'", "'AlleleSynonymSlotAnnotation'"])
            elif entity_type in ["agm", "agms", "strain", "genotype", "fish"]:
                annotation_types = ["'AgmFullNameSlotAnnotation'", "'AgmSecondaryIdSlotAnnotation'"]
                if include_synonyms:
                    annotation_types.append("'AgmSynonymSlotAnnotation'")
            else:
                raise AGRAPIError(f"Unsupported entity_type for search: '{entity_type}'")

            annotation_types_str = ", ".join(annotation_types)
            results = []

            # Tier 1: Try exact match first (fast - uses B-tree index)
            exact_results = self._search_exact_match(
                session, entity_type, search_upper, taxon_curie, annotation_types_str
            )
            results.extend(exact_results)

            # If we have enough results, return early
            if len(results) >= limit:
                return results[:limit]

            # Tier 2: Try prefix match (fast - uses B-tree index)
            exclude_curies = {r["entity_curie"] for r in results}
            remaining_limit = limit - len(results)
            prefix_results = self._search_prefix_match(
                session, entity_type, search_upper, taxon_curie, annotation_types_str, exclude_curies, remaining_limit
            )
            results.extend(prefix_results)

            # If we have enough results, return early
            if len(results) >= limit:
                return results[:limit]

            # Tier 3: Fall back to contains match (slow - sequential scan)
            exclude_curies = {r["entity_curie"] for r in results}
            remaining_limit = limit - len(results)
            contains_results = self._search_contains_match(
                session, entity_type, search_upper, taxon_curie, annotation_types_str, exclude_curies, remaining_limit
            )
            results.extend(contains_results)

            return results[:limit]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def _search_exact_match(
        self, session: Session, entity_type: str, search_upper: str, taxon_curie: str, annotation_types_str: str
    ) -> List[Dict[str, Any]]:
        """Tier 1: Exact match search using B-tree index.

        Uses UPPER(displaytext) = 'PATTERN' which can use the functional B-tree index.
        Expected performance: 5-20ms

        Args:
            session: SQLAlchemy session
            entity_type: Type of entity ('gene', 'allele', 'agm')
            search_upper: Uppercase search pattern
            taxon_curie: NCBI Taxon CURIE
            annotation_types_str: Comma-separated annotation types (already quoted)

        Returns:
            List of matching entities with structure:
                - entity_curie: Primary external ID
                - is_obsolete: Whether entity is obsolete
                - entity: Matched display text
                - match_type: Always 'exact'
                - relevance: Always 1
        """
        if entity_type == "gene":
            entity_id_field = "singlegene_id"
            entity_table = "gene g"
            join_condition = "g.id = sa.singlegene_id"
            entity_alias = "g"
        elif entity_type == "allele":
            entity_id_field = "singleallele_id"
            entity_table = "allele a"
            join_condition = "a.id = sa.singleallele_id"
            entity_alias = "a"
        elif entity_type in ["agm", "agms", "strain", "genotype", "fish"]:
            entity_id_field = "singleagm_id"
            entity_table = "affectedgenomicmodel agm"
            join_condition = "agm.id = sa.singleagm_id"
            entity_alias = "agm"
        else:
            return []

        sql_query = text(
            f"""
            SELECT DISTINCT ON (be.primaryexternalid)
                be.primaryexternalid,
                sa.obsolete,
                sa.displaytext,
                'exact' as match_type,
                1 as relevance
            FROM slotannotation sa
            JOIN {entity_table} ON {join_condition}
            JOIN biologicalentity be ON be.id = {entity_alias}.id
            JOIN ontologyterm ot ON be.taxon_id = ot.id
            WHERE sa.slotannotationtype IN ({annotation_types_str})
            AND sa.obsolete = false
            AND UPPER(sa.displaytext) = :search_exact
            AND sa.{entity_id_field} IS NOT NULL
            AND ot.curie = :taxon
            ORDER BY be.primaryexternalid, sa.displaytext
        """
        )

        rows = session.execute(sql_query, {"search_exact": search_upper, "taxon": taxon_curie}).fetchall()

        return [
            {"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2], "match_type": row[3], "relevance": row[4]}
            for row in rows
        ]

    def _search_prefix_match(
        self,
        session: Session,
        entity_type: str,
        search_upper: str,
        taxon_curie: str,
        annotation_types_str: str,
        exclude_curies: Set[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Tier 2: Prefix match search using B-tree index.

        Uses UPPER(displaytext) LIKE 'PATTERN%' which can use the functional B-tree index.
        Expected performance: 5-20ms

        Args:
            session: SQLAlchemy session
            entity_type: Type of entity ('gene', 'allele', 'agm')
            search_upper: Uppercase search pattern
            taxon_curie: NCBI Taxon CURIE
            annotation_types_str: Comma-separated annotation types (already quoted)
            exclude_curies: Set of entity CURIEs to exclude (from exact matches)
            limit: Maximum results to return

        Returns:
            List of matching entities with structure:
                - entity_curie: Primary external ID
                - is_obsolete: Whether entity is obsolete
                - entity: Matched display text
                - match_type: Always 'starts_with'
                - relevance: Always 2
        """
        if entity_type == "gene":
            entity_id_field = "singlegene_id"
            entity_table = "gene g"
            join_condition = "g.id = sa.singlegene_id"
            entity_alias = "g"
        elif entity_type == "allele":
            entity_id_field = "singleallele_id"
            entity_table = "allele a"
            join_condition = "a.id = sa.singleallele_id"
            entity_alias = "a"
        elif entity_type in ["agm", "agms", "strain", "genotype", "fish"]:
            entity_id_field = "singleagm_id"
            entity_table = "affectedgenomicmodel agm"
            join_condition = "agm.id = sa.singleagm_id"
            entity_alias = "agm"
        else:
            return []

        # Build exclusion clause
        if exclude_curies:
            exclude_clause = "AND be.primaryexternalid NOT IN :exclude_curies"
        else:
            exclude_clause = ""

        sql_query = text(
            f"""
            SELECT DISTINCT ON (be.primaryexternalid)
                be.primaryexternalid,
                sa.obsolete,
                sa.displaytext,
                'starts_with' as match_type,
                2 as relevance
            FROM slotannotation sa
            JOIN {entity_table} ON {join_condition}
            JOIN biologicalentity be ON be.id = {entity_alias}.id
            JOIN ontologyterm ot ON be.taxon_id = ot.id
            WHERE sa.slotannotationtype IN ({annotation_types_str})
            AND sa.obsolete = false
            AND UPPER(sa.displaytext) LIKE :search_starts
            AND UPPER(sa.displaytext) != :search_exact
            AND sa.{entity_id_field} IS NOT NULL
            AND ot.curie = :taxon
            {exclude_clause}
            ORDER BY be.primaryexternalid, sa.displaytext
            LIMIT :limit
        """
        )

        params = {
            "search_starts": f"{search_upper}%",
            "search_exact": search_upper,
            "taxon": taxon_curie,
            "limit": limit,
        }
        if exclude_curies:
            params["exclude_curies"] = tuple(exclude_curies)

        rows = session.execute(sql_query, params).fetchall()

        return [
            {"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2], "match_type": row[3], "relevance": row[4]}
            for row in rows
        ]

    def _search_contains_match(
        self,
        session: Session,
        entity_type: str,
        search_upper: str,
        taxon_curie: str,
        annotation_types_str: str,
        exclude_curies: Set[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Tier 3: Contains match search using MATERIALIZED CTE.

        Uses UPPER(displaytext) LIKE '%PATTERN%' which CANNOT use B-tree index.
        Requires sequential scan. Expected performance: ~990ms

        Args:
            session: SQLAlchemy session
            entity_type: Type of entity ('gene', 'allele', 'agm')
            search_upper: Uppercase search pattern
            taxon_curie: NCBI Taxon CURIE
            annotation_types_str: Comma-separated annotation types (already quoted)
            exclude_curies: Set of entity CURIEs to exclude (from exact/prefix matches)
            limit: Maximum results to return

        Returns:
            List of matching entities with structure:
                - entity_curie: Primary external ID
                - is_obsolete: Whether entity is obsolete
                - entity: Matched display text
                - match_type: Always 'contains'
                - relevance: Always 3
        """
        if entity_type == "gene":
            entity_id_field = "singlegene_id"
            entity_table = "gene"
            entity_alias = "g"
        elif entity_type == "allele":
            entity_id_field = "singleallele_id"
            entity_table = "allele"
            entity_alias = "a"
        elif entity_type in ["agm", "agms", "strain", "genotype", "fish"]:
            entity_id_field = "singleagm_id"
            entity_table = "affectedgenomicmodel"
            entity_alias = "agm"
        else:
            return []

        # Build exclusion clause
        if exclude_curies:
            exclude_clause = "AND be.primaryexternalid NOT IN :exclude_curies"
        else:
            exclude_clause = ""

        # Use MATERIALIZED CTE to force displaytext lookup first
        sql_query = text(
            f"""
            WITH matching_slots AS MATERIALIZED (
                SELECT
                    sa.{entity_id_field},
                    sa.displaytext,
                    sa.obsolete
                FROM slotannotation sa
                WHERE sa.slotannotationtype IN ({annotation_types_str})
                AND sa.obsolete = false
                AND UPPER(sa.displaytext) LIKE :search_contains
                AND UPPER(sa.displaytext) NOT LIKE :search_starts
                AND sa.{entity_id_field} IS NOT NULL
            )
            SELECT DISTINCT ON (be.primaryexternalid)
                be.primaryexternalid,
                ms.obsolete,
                ms.displaytext,
                'contains' as match_type,
                3 as relevance
            FROM matching_slots ms
            JOIN {entity_table} {entity_alias} ON {entity_alias}.id = ms.{entity_id_field}
            JOIN biologicalentity be ON be.id = {entity_alias}.id
            JOIN ontologyterm ot ON be.taxon_id = ot.id
            WHERE ot.curie = :taxon
            {exclude_clause}
            ORDER BY be.primaryexternalid, ms.displaytext
            LIMIT :limit
        """
        )

        params = {
            "search_contains": f"%{search_upper}%",
            "search_starts": f"{search_upper}%",
            "taxon": taxon_curie,
            "limit": limit,
        }
        if exclude_curies:
            params["exclude_curies"] = tuple(exclude_curies)

        rows = session.execute(sql_query, params).fetchall()

        return [
            {"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2], "match_type": row[3], "relevance": row[4]}
            for row in rows
        ]

    def get_ontology_term(self, curie: str) -> Optional["OntologyTermResult"]:
        """Get a specific ontology term by CURIE from the database.

        This performs a direct lookup by CURIE with synonym aggregation.

        Args:
            curie: Ontology term CURIE (e.g., 'WBbt:0005062', 'GO:0005634')

        Returns:
            OntologyTermResult object with term details and synonyms, or None if not found

        Example:
            term = db.get_ontology_term('WBbt:0005062')
            if term:
                print(f"Name: {term.name}")
                print(f"Synonyms: {', '.join(term.synonyms)}")
        """

        session = self._create_session()
        try:
            sql_query = text(
                """
            SELECT
                ot.curie,
                ot.name,
                ot.namespace,
                ot.definition,
                ot.ontologytermtype,
                ARRAY_AGG(DISTINCT s.name) FILTER (WHERE s.name IS NOT NULL) as synonyms
            FROM
                ontologyterm ot
                LEFT JOIN ontologyterm_synonym ots ON ot.id = ots.ontologyterm_id
                LEFT JOIN synonym s ON ots.synonyms_id = s.id
            WHERE
                ot.curie = :curie
            AND
                ot.obsolete = false
            GROUP BY
                ot.curie, ot.name, ot.namespace, ot.definition, ot.ontologytermtype
            """
            )

            row = session.execute(sql_query, {"curie": curie}).fetchone()

            if row is None:
                return None

            return OntologyTermResult(
                curie=row[0],
                name=row[1],
                namespace=row[2] or "",
                definition=row[3],
                ontology_type=row[4],
                synonyms=row[5] or [],
            )

        except Exception as e:
            raise AGRAPIError(f"Database query failed for ontology term {curie}: {str(e)}")
        finally:
            session.close()

    def get_ontology_terms(self, curies: List[str]) -> Dict[str, Optional["OntologyTermResult"]]:
        """Get multiple ontology terms by their CURIEs from the database.

        This performs a bulk lookup by CURIEs with synonym aggregation. More efficient
        than calling get_ontology_term multiple times as it uses a single SQL query.

        Args:
            curies: List of ontology term CURIEs (e.g., ['WBbt:0005062', 'GO:0005634'])

        Returns:
            Dictionary mapping CURIEs to OntologyTermResult objects (or None if not found)

        Example:
            terms = db.get_ontology_terms(['WBbt:0005062', 'GO:0005634'])
            for curie, term in terms.items():
                if term:
                    print(f"{curie}: {term.name}")
                else:
                    print(f"{curie}: Not found")
        """
        if not curies:
            return {}

        session = self._create_session()
        try:
            sql_query = text(
                """
            SELECT
                ot.curie,
                ot.name,
                ot.namespace,
                ot.definition,
                ot.ontologytermtype,
                ARRAY_AGG(DISTINCT s.name) FILTER (WHERE s.name IS NOT NULL) as synonyms
            FROM
                ontologyterm ot
                LEFT JOIN ontologyterm_synonym ots ON ot.id = ots.ontologyterm_id
                LEFT JOIN synonym s ON ots.synonyms_id = s.id
            WHERE
                ot.curie = ANY(:curies)
            AND
                ot.obsolete = false
            GROUP BY
                ot.curie, ot.name, ot.namespace, ot.definition, ot.ontologytermtype
            """
            )

            rows = session.execute(sql_query, {"curies": curies}).fetchall()

            # Initialize results with None for all requested CURIEs
            results: Dict[str, Optional["OntologyTermResult"]] = {curie: None for curie in curies}

            # Populate results with found terms
            for row in rows:
                results[row[0]] = OntologyTermResult(
                    curie=row[0],
                    name=row[1],
                    namespace=row[2] or "",
                    definition=row[3],
                    ontology_type=row[4],
                    synonyms=row[5] or [],
                )

            return results

        except Exception as e:
            raise AGRAPIError(f"Database query failed for ontology terms: {str(e)}")
        finally:
            session.close()

    def search_ontology_terms(
        self, term: str, ontology_type: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search ontology terms with partial matching and synonym support.

        This method enables flexible searching where partial matches are supported
        (e.g., "linker" will find "linker cell"). Results are ordered by relevance:
        exact match > starts with > contains.

        Args:
            term: Search term (e.g., 'linker cell', 'L3 larval stage')
            ontology_type: Ontology term type (e.g., 'WBBTTerm', 'GOTerm', 'WBLSTerm')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            # Find C. elegans anatomy terms matching "linker"
            results = db.search_ontology_terms('linker', 'WBBTTerm')

        Notes:
            - Case-insensitive search
            - Searches term names and synonyms (if enabled)
            - Performance: Uses tiered search strategy (exact → prefix → contains)
                - Tier 1 (Exact): UPPER(name) = 'PATTERN' (uses B-tree index, 5-20ms)
                - Tier 2 (Prefix): UPPER(name) LIKE 'PATTERN%' (uses B-tree index, 5-20ms)
                - Tier 3 (Contains): UPPER(name) LIKE '%PATTERN%' (sequential scan, ~990ms)
            - Most queries hit Tier 1 or 2 (5-10x faster on average)
            - Tier 3 fallback ensures comprehensive results

            TODO - Future Enhancements:
            - Phase 2 optimization: Add pg_trgm extension for 50-100x improvement (all queries 10-30ms)
        """

        if not term:
            return []

        session = self._create_session()
        try:
            search_upper = term.upper()
            results = []

            # If exact_match is True, only do Tier 1
            if exact_match:
                exact_results = self._search_ontology_exact(session, search_upper, ontology_type, include_synonyms)
                results.extend(exact_results)
            else:
                # Tier 1: Try exact match first (fast - uses B-tree index)
                exact_results = self._search_ontology_exact(session, search_upper, ontology_type, include_synonyms)
                results.extend(exact_results)

                # If we have enough results, return early
                if len(results) >= limit:
                    return results[:limit]

                # Tier 2: Try prefix match (fast - uses B-tree index)
                exclude_curies = {r.curie for r in results}
                remaining_limit = limit - len(results)
                prefix_results = self._search_ontology_prefix(
                    session, search_upper, ontology_type, include_synonyms, exclude_curies, remaining_limit
                )
                results.extend(prefix_results)

                # If we have enough results, return early
                if len(results) >= limit:
                    return results[:limit]

                # Tier 3: Fall back to contains match (slow - sequential scan)
                exclude_curies = {r.curie for r in results}
                remaining_limit = limit - len(results)
                contains_results = self._search_ontology_contains(
                    session, search_upper, ontology_type, include_synonyms, exclude_curies, remaining_limit
                )
                results.extend(contains_results)

            return results[:limit]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def _search_ontology_exact(
        self, session: Session, search_upper: str, ontology_type: str, include_synonyms: bool
    ) -> List["OntologyTermResult"]:
        """Tier 1: Exact match search for ontology terms using B-tree index.

        Uses UPPER(name) = 'PATTERN' which can use the functional B-tree index.
        Expected performance: 5-20ms

        Args:
            session: SQLAlchemy session
            search_upper: Uppercase search pattern
            ontology_type: Ontology term type (e.g., 'WBBTTerm')
            include_synonyms: Whether to include synonym matches

        Returns:
            List of OntologyTermResult objects
        """

        if include_synonyms:
            sql_query = text(
                """
                WITH matching_terms AS (
                    SELECT DISTINCT ot.id, ot.curie, ot.name, ot.namespace, ot.definition, ot.ontologytermtype
                    FROM ontologyterm ot
                    LEFT JOIN ontologyterm_synonym ots ON ot.id = ots.ontologyterm_id
                    LEFT JOIN synonym s ON ots.synonyms_id = s.id
                    WHERE ot.ontologytermtype = :ontology_type
                    AND ot.obsolete = false
                    AND (UPPER(ot.name) = :search_exact OR UPPER(s.name) = :search_exact)
                )
                SELECT
                    mt.curie,
                    mt.name,
                    mt.namespace,
                    mt.definition,
                    mt.ontologytermtype,
                    ARRAY_AGG(DISTINCT s.name) FILTER (WHERE s.name IS NOT NULL) as synonyms
                FROM matching_terms mt
                LEFT JOIN ontologyterm_synonym ots ON mt.id = ots.ontologyterm_id
                LEFT JOIN synonym s ON ots.synonyms_id = s.id
                GROUP BY mt.curie, mt.name, mt.namespace, mt.definition, mt.ontologytermtype
                ORDER BY mt.name
            """
            )
        else:
            sql_query = text(
                """
                SELECT
                    ot.curie,
                    ot.name,
                    ot.namespace,
                    ot.definition,
                    ot.ontologytermtype,
                    ARRAY[]::text[] as synonyms
                FROM ontologyterm ot
                WHERE ot.ontologytermtype = :ontology_type
                AND ot.obsolete = false
                AND UPPER(ot.name) = :search_exact
                ORDER BY ot.name
            """
            )

        rows = session.execute(sql_query, {"search_exact": search_upper, "ontology_type": ontology_type}).fetchall()

        return [
            OntologyTermResult(
                curie=row[0],
                name=row[1],
                namespace=row[2] or "",
                definition=row[3],
                ontology_type=row[4],
                synonyms=row[5] or [],
            )
            for row in rows
        ]

    def _search_ontology_prefix(
        self,
        session: Session,
        search_upper: str,
        ontology_type: str,
        include_synonyms: bool,
        exclude_curies: Set[str],
        limit: int,
    ) -> List["OntologyTermResult"]:
        """Tier 2: Prefix match search for ontology terms using B-tree index.

        Uses UPPER(name) LIKE 'PATTERN%' which can use the functional B-tree index.
        Expected performance: 5-20ms

        Args:
            session: SQLAlchemy session
            search_upper: Uppercase search pattern
            ontology_type: Ontology term type
            include_synonyms: Whether to include synonym matches
            exclude_curies: Set of CURIEs to exclude (from exact matches)
            limit: Maximum results to return

        Returns:
            List of OntologyTermResult objects
        """

        # Build exclusion clause
        if exclude_curies:
            exclude_clause = "AND ot.curie NOT IN :exclude_curies"
        else:
            exclude_clause = ""

        if include_synonyms:
            sql_query = text(
                f"""
                WITH matching_terms AS (
                    SELECT DISTINCT ot.id, ot.curie, ot.name, ot.namespace, ot.definition, ot.ontologytermtype
                    FROM ontologyterm ot
                    LEFT JOIN ontologyterm_synonym ots ON ot.id = ots.ontologyterm_id
                    LEFT JOIN synonym s ON ots.synonyms_id = s.id
                    WHERE ot.ontologytermtype = :ontology_type
                    AND ot.obsolete = false
                    AND (UPPER(ot.name) LIKE :search_starts OR UPPER(s.name) LIKE :search_starts)
                    AND (UPPER(ot.name) != :search_exact AND (s.name IS NULL OR UPPER(s.name) != :search_exact))
                    {exclude_clause}
                    LIMIT :limit
                )
                SELECT
                    mt.curie,
                    mt.name,
                    mt.namespace,
                    mt.definition,
                    mt.ontologytermtype,
                    ARRAY_AGG(DISTINCT s.name) FILTER (WHERE s.name IS NOT NULL) as synonyms
                FROM matching_terms mt
                LEFT JOIN ontologyterm_synonym ots ON mt.id = ots.ontologyterm_id
                LEFT JOIN synonym s ON ots.synonyms_id = s.id
                GROUP BY mt.curie, mt.name, mt.namespace, mt.definition, mt.ontologytermtype
                ORDER BY mt.name
            """
            )
        else:
            sql_query = text(
                f"""
                SELECT
                    ot.curie,
                    ot.name,
                    ot.namespace,
                    ot.definition,
                    ot.ontologytermtype,
                    ARRAY[]::text[] as synonyms
                FROM ontologyterm ot
                WHERE ot.ontologytermtype = :ontology_type
                AND ot.obsolete = false
                AND UPPER(ot.name) LIKE :search_starts
                AND UPPER(ot.name) != :search_exact
                {exclude_clause}
                ORDER BY ot.name
                LIMIT :limit
            """
            )

        params = {
            "search_starts": f"{search_upper}%",
            "search_exact": search_upper,
            "ontology_type": ontology_type,
            "limit": limit,
        }
        if exclude_curies:
            params["exclude_curies"] = tuple(exclude_curies)

        rows = session.execute(sql_query, params).fetchall()

        return [
            OntologyTermResult(
                curie=row[0],
                name=row[1],
                namespace=row[2] or "",
                definition=row[3],
                ontology_type=row[4],
                synonyms=row[5] or [],
            )
            for row in rows
        ]

    def _search_ontology_contains(
        self,
        session: Session,
        search_upper: str,
        ontology_type: str,
        include_synonyms: bool,
        exclude_curies: Set[str],
        limit: int,
    ) -> List["OntologyTermResult"]:
        """Tier 3: Contains match search for ontology terms.

        Uses UPPER(name) LIKE '%PATTERN%' which CANNOT use B-tree index.
        Requires sequential scan. Expected performance: ~990ms

        Args:
            session: SQLAlchemy session
            search_upper: Uppercase search pattern
            ontology_type: Ontology term type
            include_synonyms: Whether to include synonym matches
            exclude_curies: Set of CURIEs to exclude (from exact/prefix matches)
            limit: Maximum results to return

        Returns:
            List of OntologyTermResult objects
        """

        if include_synonyms:
            # Build exclusion clause for CTE query (use mt.curie since we're in the outer query)
            if exclude_curies:
                exclude_clause = "AND mt.curie NOT IN :exclude_curies"
            else:
                exclude_clause = ""

            sql_query = text(
                f"""
                WITH matching_terms AS MATERIALIZED (
                    SELECT DISTINCT
                        ot.id,
                        ot.curie,
                        ot.name,
                        ot.namespace,
                        ot.definition,
                        ot.ontologytermtype
                    FROM ontologyterm ot
                    LEFT JOIN ontologyterm_synonym ots ON ot.id = ots.ontologyterm_id
                    LEFT JOIN synonym s ON ots.synonyms_id = s.id
                    WHERE ot.ontologytermtype = :ontology_type
                    AND ot.obsolete = false
                    AND (UPPER(ot.name) LIKE :search_contains OR UPPER(s.name) LIKE :search_contains)
                    AND (UPPER(ot.name) NOT LIKE :search_starts AND (s.name IS NULL OR UPPER(s.name) NOT LIKE :search_starts))
                )
                SELECT
                    mt.curie,
                    mt.name,
                    mt.namespace,
                    mt.definition,
                    mt.ontologytermtype,
                    ARRAY_AGG(DISTINCT s.name) FILTER (WHERE s.name IS NOT NULL) as synonyms
                FROM matching_terms mt
                LEFT JOIN ontologyterm_synonym ots ON mt.id = ots.ontologyterm_id
                LEFT JOIN synonym s ON ots.synonyms_id = s.id
                WHERE true
                {exclude_clause}
                GROUP BY mt.curie, mt.name, mt.namespace, mt.definition, mt.ontologytermtype
                ORDER BY mt.name
                LIMIT :limit
            """
            )
        else:
            # Build exclusion clause for direct query (use ot.curie since no CTE)
            if exclude_curies:
                exclude_clause = "AND ot.curie NOT IN :exclude_curies"
            else:
                exclude_clause = ""

            sql_query = text(
                f"""
                SELECT
                    ot.curie,
                    ot.name,
                    ot.namespace,
                    ot.definition,
                    ot.ontologytermtype,
                    ARRAY[]::text[] as synonyms
                FROM ontologyterm ot
                WHERE ot.ontologytermtype = :ontology_type
                AND ot.obsolete = false
                AND UPPER(ot.name) LIKE :search_contains
                AND UPPER(ot.name) NOT LIKE :search_starts
                {exclude_clause}
                ORDER BY ot.name
                LIMIT :limit
            """
            )

        params = {
            "search_contains": f"%{search_upper}%",
            "search_starts": f"{search_upper}%",
            "ontology_type": ontology_type,
            "limit": limit,
        }
        if exclude_curies:
            params["exclude_curies"] = tuple(exclude_curies)

        rows = session.execute(sql_query, params).fetchall()

        return [
            OntologyTermResult(
                curie=row[0],
                name=row[1],
                namespace=row[2] or "",
                definition=row[3],
                ontology_type=row[4],
                synonyms=row[5] or [],
            )
            for row in rows
        ]

    def search_anatomy_terms(
        self, term: str, data_provider: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search anatomy ontology terms with organism-aware type mapping.

        Convenience wrapper that automatically maps data_provider to the correct
        anatomy ontology type (WBBTTerm for WB, UBERONTerm for FB, etc.).

        Args:
            term: Search term (e.g., 'linker cell', 'pharynx')
            data_provider: Data provider code ('WB', 'FB', 'ZFIN', 'MGI', 'RGD', 'SGD', 'XB')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            # Find C. elegans anatomy terms matching "linker"
            results = db.search_anatomy_terms('linker', 'WB')
            # Returns: [OntologyTermResult(curie='WBbt:0005062', name='linker cell', ...)]

        Raises:
            AGRAPIError: If data_provider is not supported
        """
        # Map data_provider to anatomy ontology type
        provider_to_anatomy_type = {
            "WB": "WBBTTerm",  # C. elegans - WormBase Anatomy
            "FB": "UBERONTerm",  # D. melanogaster - Uberon (cross-species anatomy)
            "ZFIN": "ZFATerm",  # D. rerio (zebrafish) - ZFIN Anatomy
            "MGI": "EMAPATerm",  # M. musculus (mouse) - Mouse Anatomy (embryonic)
            "RGD": "UBERONTerm",  # R. norvegicus (rat) - Uberon (cross-species)
            "SGD": "UBERONTerm",  # S. cerevisiae (yeast) - Uberon (cross-species)
            "XB": "XBATerm",  # X. laevis (xenopus) - Xenbase Anatomy (FIXED TYPO)
        }

        # Additional anatomy ontology support (can be accessed directly)
        # MATerm - Mouse Adult Anatomy
        # BTOTerm - BRENDA Tissue Ontology
        # CLTerm - Cell Ontology
        # XBEDTerm - Xenopus Embryonic Development

        ontology_type = provider_to_anatomy_type.get(data_provider.upper())
        if not ontology_type:
            raise AGRAPIError(
                f"Unsupported data_provider for anatomy search: '{data_provider}'. "
                f"Supported: {', '.join(provider_to_anatomy_type.keys())}"
            )

        return self.search_ontology_terms(
            term=term,
            ontology_type=ontology_type,
            exact_match=exact_match,
            include_synonyms=include_synonyms,
            limit=limit,
        )

    def search_life_stage_terms(
        self, term: str, data_provider: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search life stage ontology terms with organism-aware type mapping.

        Convenience wrapper that automatically maps data_provider to the correct
        life stage ontology type (WBLSTerm for WB, FBDVTerm for FB, etc.).

        Args:
            term: Search term (e.g., 'L3 larval stage', 'adult')
            data_provider: Data provider code ('WB', 'FB', 'ZFIN', 'MGI', 'XB')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            # Find C. elegans life stages matching "L3"
            results = db.search_life_stage_terms('L3', 'WB')
            # Returns: [OntologyTermResult(curie='WBls:0000035', name='L3 larval stage', ...)]

        Raises:
            AGRAPIError: If data_provider is not supported
        """
        # Map data_provider to life stage ontology type
        provider_to_stage_type = {
            "WB": "WBLSTerm",  # C. elegans - WormBase Life Stage
            "FB": "FBDVTerm",  # D. melanogaster - FlyBase Development
            "ZFIN": "ZFSTerm",  # D. rerio (zebrafish) - ZFIN Stages
            "MGI": "MMUSDVTerm",  # M. musculus (mouse) - Mouse Developmental Stages (FIXED CASING)
            "XB": "XBSTerm",  # X. laevis (xenopus) - Xenbase Stages
        }

        # Additional life stage ontology support (can be accessed directly)
        # XBEDTerm - Xenopus Embryonic Development

        ontology_type = provider_to_stage_type.get(data_provider.upper())
        if not ontology_type:
            raise AGRAPIError(
                f"Unsupported data_provider for life stage search: '{data_provider}'. "
                f"Supported: {', '.join(provider_to_stage_type.keys())}"
            )

        return self.search_ontology_terms(
            term=term,
            ontology_type=ontology_type,
            exact_match=exact_match,
            include_synonyms=include_synonyms,
            limit=limit,
        )

    def search_go_terms(
        self,
        term: str,
        go_aspect: Optional[str] = None,
        exact_match: bool = False,
        include_synonyms: bool = True,
        limit: int = 20,
    ) -> List["OntologyTermResult"]:
        """Search Gene Ontology terms with optional aspect filtering.

        Args:
            term: Search term (e.g., 'nucleus', 'apoptosis')
            go_aspect: Optional GO aspect to filter by:
                - 'cellular_component' (e.g., nucleus, cytoplasm)
                - 'biological_process' (e.g., apoptosis, cell division)
                - 'molecular_function' (e.g., kinase activity, binding)
                If None, searches all GO aspects (default)
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance,
            filtered by namespace if go_aspect is specified

        Example:
            # Find cellular component GO terms matching "nucleus"
            results = db.search_go_terms('nucleus', go_aspect='cellular_component')
            # Returns: [OntologyTermResult(curie='GO:0005634', name='nucleus', ...)]

        Notes:
            - GO terms are organism-agnostic (same terms used across all species)
            - If go_aspect is specified, results are filtered by namespace after search
        """
        # Search all GO terms
        results = self.search_ontology_terms(
            term=term,
            ontology_type="GOTerm",
            exact_match=exact_match,
            include_synonyms=include_synonyms,
            limit=limit * 2 if go_aspect else limit,  # Get more results if we need to filter
        )

        # Filter by GO aspect if specified
        if go_aspect:
            aspect_to_namespace = {
                "cellular_component": "cellular_component",
                "biological_process": "biological_process",
                "molecular_function": "molecular_function",
            }

            target_namespace = aspect_to_namespace.get(go_aspect.lower())
            if not target_namespace:
                raise AGRAPIError(
                    f"Invalid go_aspect: '{go_aspect}'. " f"Valid options: {', '.join(aspect_to_namespace.keys())}"
                )

            results = [r for r in results if r.namespace == target_namespace]
            results = results[:limit]  # Apply limit after filtering

        return results

    def search_disease_terms(
        self, term: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search Disease Ontology (DO) terms.

        Args:
            term: Search term (e.g., 'diabetes', 'cancer')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            results = db.search_disease_terms('diabetes')
            # Returns: [OntologyTermResult(curie='DOID:9351', name='diabetes mellitus', ...)]
        """
        return self.search_ontology_terms(
            term=term, ontology_type="DOTerm", exact_match=exact_match, include_synonyms=include_synonyms, limit=limit
        )

    def search_phenotype_terms(
        self,
        term: str,
        organism: Optional[str] = None,
        exact_match: bool = False,
        include_synonyms: bool = True,
        limit: int = 20,
    ) -> List["OntologyTermResult"]:
        """Search phenotype ontology terms with optional organism filtering.

        Args:
            term: Search term (e.g., 'lethality', 'sterile')
            organism: Optional organism filter:
                - 'human' or 'HP' → HPTerm (Human Phenotype)
                - 'mouse' or 'MP' → MPTerm (Mammalian Phenotype)
                - 'worm' or 'WB' → WBPhenotypeTerm (C. elegans)
                If None, searches all phenotype types (default)
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            # Search human phenotypes
            results = db.search_phenotype_terms('seizure', organism='human')
            # Search all phenotype ontologies
            results = db.search_phenotype_terms('lethality')
        """
        organism_to_phenotype_type = {
            "human": "HPTerm",
            "hp": "HPTerm",
            "mouse": "MPTerm",
            "mp": "MPTerm",
            "worm": "WBPhenotypeTerm",
            "wb": "WBPhenotypeTerm",
        }

        if organism:
            ontology_type = organism_to_phenotype_type.get(organism.lower())
            if not ontology_type:
                raise AGRAPIError(
                    f"Unsupported organism for phenotype search: '{organism}'. "
                    f"Supported: {', '.join(set(organism_to_phenotype_type.values()))}"
                )
            return self.search_ontology_terms(
                term=term,
                ontology_type=ontology_type,
                exact_match=exact_match,
                include_synonyms=include_synonyms,
                limit=limit,
            )
        else:
            # Search all phenotype types and combine results
            all_results = []
            for onto_type in ["HPTerm", "MPTerm", "WBPhenotypeTerm"]:
                results = self.search_ontology_terms(
                    term=term,
                    ontology_type=onto_type,
                    exact_match=exact_match,
                    include_synonyms=include_synonyms,
                    limit=limit,
                )
                all_results.extend(results)

            # Sort by relevance (exact matches first) and deduplicate
            seen_curies = set()
            unique_results = []
            for result in all_results:
                if result.curie not in seen_curies:
                    seen_curies.add(result.curie)
                    unique_results.append(result)

            return unique_results[:limit]

    def search_chemical_terms(
        self, term: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search Chemical Entities of Biological Interest (ChEBI) terms.

        Args:
            term: Search term (e.g., 'glucose', 'dopamine', 'ethanol')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            results = db.search_chemical_terms('dopamine')
            # Returns: [OntologyTermResult(curie='CHEBI:18243', name='dopamine', ...)]
        """
        return self.search_ontology_terms(
            term=term,
            ontology_type="CHEBITerm",
            exact_match=exact_match,
            include_synonyms=include_synonyms,
            limit=limit,
        )

    def search_evidence_terms(
        self, term: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search Evidence and Conclusion Ontology (ECO) terms.

        Args:
            term: Search term (e.g., 'experimental evidence', 'sequence similarity')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            results = db.search_evidence_terms('experimental')
            # Returns evidence code terms from ECO
        """
        return self.search_ontology_terms(
            term=term, ontology_type="ECOTerm", exact_match=exact_match, include_synonyms=include_synonyms, limit=limit
        )

    def search_taxon_terms(
        self, term: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search NCBI Taxonomy terms.

        Args:
            term: Search term (e.g., 'Caenorhabditis elegans', 'human', 'mouse')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            results = db.search_taxon_terms('elegans')
            # Returns: [OntologyTermResult(curie='NCBITaxon:6239', name='Caenorhabditis elegans', ...)]
        """
        return self.search_ontology_terms(
            term=term,
            ontology_type="NCBITaxonTerm",
            exact_match=exact_match,
            include_synonyms=include_synonyms,
            limit=limit,
        )

    def search_sequence_terms(
        self, term: str, exact_match: bool = False, include_synonyms: bool = True, limit: int = 20
    ) -> List["OntologyTermResult"]:
        """Search Sequence Ontology (SO) terms.

        Args:
            term: Search term (e.g., 'exon', 'intron', 'promoter')
            exact_match: If True, only return exact matches (default: False)
            include_synonyms: Include synonym fields in search (default: True)
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of OntologyTermResult objects sorted by relevance

        Example:
            results = db.search_sequence_terms('exon')
            # Returns: [OntologyTermResult(curie='SO:0000147', name='exon', ...)]
        """
        return self.search_ontology_terms(
            term=term, ontology_type="SOTerm", exact_match=exact_match, include_synonyms=include_synonyms, limit=limit
        )

    def map_entity_curies_to_info(self, entity_type: str, entity_curies: List[str]) -> List[Dict[str, Any]]:
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

            if entity_type in ["gene", "allele"]:
                entity_table_name = entity_type
                sql_query = text(
                    f"""
                SELECT DISTINCT be.primaryexternalid, be.obsolete, be.primaryexternalid
                FROM biologicalentity be, {entity_table_name} ent_tbl
                WHERE be.id = ent_tbl.id
                AND UPPER(be.primaryexternalid) IN :entity_curie_list
                """
                )
            elif entity_type == "construct":
                sql_query = text(
                    """
                SELECT DISTINCT r.primaryexternalid, r.obsolete, r.primaryexternalid
                FROM reagent r, construct c
                WHERE r.id = c.id
                AND UPPER(r.primaryexternalid) IN :entity_curie_list
                """
                )
            elif entity_type in ["agm", "agms", "strain", "genotype", "fish"]:
                sql_query = text(
                    """
                SELECT DISTINCT be.primaryexternalid, be.obsolete, be.primaryexternalid
                FROM biologicalentity be, affectedgenomicmodel agm
                WHERE be.id = agm.id
                AND UPPER(be.primaryexternalid) IN :entity_curie_list
                """
                )
            elif "targeting reagent" in entity_type:
                sql_query = text(
                    """
                SELECT DISTINCT be.primaryexternalid, be.obsolete, be.primaryexternalid
                FROM biologicalentity be, sequencetargetingreagent str
                WHERE be.id = str.id
                AND UPPER(be.primaryexternalid) IN :entity_curie_list
                """
                )
            else:
                raise AGRAPIError(f"Unknown entity_type '{entity_type}'")

            rows = session.execute(sql_query, {"entity_curie_list": tuple(entity_curies_upper)}).fetchall()
            return [{"entity_curie": row[0], "is_obsolete": row[1], "entity": row[2]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def map_curies_to_names(self, category: str, curies: List[str]) -> Dict[str, str]:
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

            if category == "gene":
                sql_query = text(
                    """
                SELECT be.primaryexternalid, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singlegene_id
                WHERE be.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'GeneSymbolSlotAnnotation'
                """
                )
            elif "allele" in category:
                sql_query = text(
                    """
                SELECT be.primaryexternalid, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleallele_id
                WHERE be.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'AlleleSymbolSlotAnnotation'
                """
                )
            elif category in ["affected genome model", "agm", "strain", "genotype", "fish"]:
                sql_query = text(
                    """
                SELECT DISTINCT be.primaryexternalid, sa.displaytext
                FROM biologicalentity be
                JOIN slotannotation sa ON be.id = sa.singleagm_id
                WHERE be.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'AgmFullNameSlotAnnotation'
                """
                )
            elif "construct" in category:
                sql_query = text(
                    """
                SELECT r.primaryexternalid, sa.displaytext
                FROM reagent r
                JOIN slotannotation sa ON r.id = sa.singleconstruct_id
                WHERE r.primaryexternalid IN :curies
                AND sa.slotannotationtype = 'ConstructSymbolSlotAnnotation'
                """
                )
            elif category in ["species", "ecoterm"]:
                curies_upper = [curie.upper() for curie in curies]
                sql_query = text(
                    """
                SELECT curie, name
                FROM ontologyterm
                WHERE UPPER(curie) IN :curies
                """
                )
                rows = session.execute(sql_query, {"curies": tuple(curies_upper)}).fetchall()
                return {row[0]: row[1] for row in rows}
            else:
                # Return identity mapping for unknown categories
                return {curie: curie for curie in curies}

            rows = session.execute(sql_query, {"curies": tuple(curies)}).fetchall()
            return {row[0]: row[1] for row in rows}

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # ATP/Topic ontology methods (from agr_literature_service ateam_db_helpers.py)
    def search_atp_topics(
        self, topic: Optional[str] = None, mod_abbr: Optional[str] = None, limit: int = 10
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
                sql_query = text(
                    """
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
                """
                )
                rows = session.execute(
                    sql_query,
                    {
                        "search_query": search_query,
                        "topic_category_atp": TOPIC_CATEGORY_ATP,
                        "mod_abbr": f"{mod_abbr}_tag",
                        "limit": limit,
                    },
                ).fetchall()
            elif topic:
                search_query = f"%{topic.upper()}%"
                sql_query = text(
                    """
                SELECT DISTINCT ot.curie, ot.name
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                WHERE ot.ontologytermtype = 'ATPTerm'
                AND UPPER(ot.name) LIKE :search_query
                AND ot.obsolete = false
                AND ancestor.curie = :topic_category_atp
                LIMIT :limit
                """
                )
                rows = session.execute(
                    sql_query, {"search_query": search_query, "topic_category_atp": TOPIC_CATEGORY_ATP, "limit": limit}
                ).fetchall()
            elif mod_abbr:
                sql_query = text(
                    """
                SELECT DISTINCT ot.curie, ot.name
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                JOIN ontologyterm_subsets s ON ot.id = s.ontologyterm_id
                WHERE ot.ontologytermtype = 'ATPTerm'
                AND ancestor.curie = :topic_category_atp
                AND s.subsets = :mod_abbr
                """
                )
                rows = session.execute(
                    sql_query, {"topic_category_atp": TOPIC_CATEGORY_ATP, "mod_abbr": f"{mod_abbr}_tag"}
                ).fetchall()
            else:
                return []

            return [{"curie": row[0], "name": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_atp_descendants(self, ancestor_curie: str, direct_children_only: bool = False) -> List[Dict[str, str]]:
        """Get descendants of an ATP ontology term.

        Args:
            ancestor_curie: ATP CURIE (e.g., 'ATP:0000002')
            direct_children_only: If True, return only direct children (distance=1).
                         If False (default), return all descendants (transitive).

        Returns:
            List of dictionaries with curie and name keys

        Example:
            # Get all descendants (transitive)
            descendants = db_methods.get_atp_descendants('ATP:0000002')

            # Get only direct children
            children = db_methods.get_atp_descendants('ATP:0000002', direct_children_only=True)
        """
        session = self._create_session()
        try:
            distance_filter = "AND otc.distance = 1" if direct_children_only else ""
            sql_query = text(
                f"""
            SELECT DISTINCT ot.curie, ot.name
            FROM ontologyterm ot
            JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
            JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
            WHERE ot.ontologytermtype = 'ATPTerm'
            AND ot.obsolete = false
            AND ancestor.curie = :ancestor_curie
            {distance_filter}
            """
            )
            rows = session.execute(sql_query, {"ancestor_curie": ancestor_curie}).fetchall()
            return [{"curie": row[0], "name": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_ontology_ancestors_or_descendants(self, ontology_node: str, direction: str = "descendants") -> List[str]:
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
            if direction == "descendants":
                sql_query = text(
                    """
                SELECT DISTINCT ot.curie
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id
                WHERE ancestor.curie = :ontology_node
                AND ot.obsolete = False
                """
                )
            else:  # ancestors
                sql_query = text(
                    """
                SELECT DISTINCT ot.curie
                FROM ontologyterm ot
                JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id
                JOIN ontologyterm descendant ON descendant.id = otc.closureobject_id
                WHERE descendant.curie = :ontology_node
                AND ot.obsolete = False
                """
                )

            rows = session.execute(sql_query, {"ontology_node": ontology_node}).fetchall()
            return [row[0] for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Species search methods (from agr_literature_service ateam_db_helpers.py)
    def search_species(self, species: str, limit: int = 10) -> List[Dict[str, str]]:
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
                sql_query = text(
                    """
                SELECT curie, name
                FROM ontologyterm
                WHERE ontologytermtype = 'NCBITaxonTerm'
                AND UPPER(curie) LIKE :search_query
                LIMIT :limit
                """
                )
            else:
                search_query = f"%{species.upper()}%"
                sql_query = text(
                    """
                SELECT curie, name
                FROM ontologyterm
                WHERE ontologytermtype = 'NCBITaxonTerm'
                AND UPPER(name) LIKE :search_query
                LIMIT :limit
                """
                )

            rows = session.execute(sql_query, {"search_query": search_query, "limit": limit}).fetchall()
            return [{"curie": row[0], "name": row[1]} for row in rows]

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    # Disease Annotation Methods

    def get_disease_annotations_by_gene(
        self,
        gene_id: str,
        include_evidence_codes: bool = True,
    ) -> List[DiseaseAnnotation]:
        """Get disease annotations for a specific gene.

        Args:
            gene_id: Gene CURIE or primary external ID (e.g., 'WB:WBGene00001044')
            include_evidence_codes: Whether to fetch evidence codes for each annotation

        Returns:
            List of DiseaseAnnotation objects

        Example:
            annotations = db_methods.get_disease_annotations_by_gene('WB:WBGene00001044')
            for ann in annotations:
                print(f"{ann.disease_name}: {ann.relation}")
        """
        session = self._create_session()
        try:
            sql_query = text(
                """
            SELECT
                da.id,
                da.curie as annotation_curie,
                da.uniqueid as unique_id,
                da.primaryexternalid as primary_external_id,
                da.modinternalid as mod_internal_id,
                da.negated,
                da.datecreated,
                da.dateupdated,
                be.primaryexternalid as subject_id,
                symbol.displaytext as subject_symbol,
                taxon.curie as subject_taxon,
                disease_ot.curie as disease_curie,
                disease_ot.name as disease_name,
                relation_vt.name as relation_name,
                ref.curie as reference_curie,
                org.abbreviation as data_provider,
                sex_vt.name as genetic_sex,
                anntype_vt.name as annotation_type,
                gda.sgdstrainbackground_id
            FROM diseaseannotation da
            JOIN genediseaseannotation gda ON gda.id = da.id
            JOIN biologicalentity be ON be.id = gda.diseaseannotationsubject_id
            JOIN ontologyterm disease_ot ON disease_ot.id = da.diseaseannotationobject_id
            LEFT JOIN vocabularyterm relation_vt ON relation_vt.id = da.relation_id
            LEFT JOIN informationcontententity ref ON ref.id = da.evidenceitem_id
            LEFT JOIN organization org ON org.id = da.dataprovider_id
            LEFT JOIN vocabularyterm sex_vt ON sex_vt.id = da.geneticsex_id
            LEFT JOIN vocabularyterm anntype_vt ON anntype_vt.id = da.annotationtype_id
            LEFT JOIN ontologyterm taxon ON taxon.id = be.taxon_id
            LEFT JOIN slotannotation symbol ON be.id = symbol.singlegene_id
                AND symbol.slotannotationtype = 'GeneSymbolSlotAnnotation'
                AND symbol.obsolete = false
            WHERE da.obsolete = false
              AND da.internal = false
              AND be.primaryexternalid = :gene_id
            ORDER BY da.id
            """
            )

            rows = session.execute(sql_query, {"gene_id": gene_id}).fetchall()

            annotations = []
            for row in rows:
                evidence_codes = []
                if include_evidence_codes:
                    evidence_codes = self._get_disease_annotation_evidence_codes(session, row[0])

                try:
                    annotation = DiseaseAnnotation(
                        id=row[0],
                        curie=row[1],
                        unique_id=row[2],
                        primary_external_id=row[3],
                        mod_internal_id=row[4],
                        negated=row[5] or False,
                        date_created=row[6],
                        date_updated=row[7],
                        subject_id=row[8],
                        subject_symbol=row[9],
                        subject_taxon=row[10],
                        subject_type="gene",
                        disease_curie=row[11],
                        disease_name=row[12],
                        relation=row[13],
                        reference_curie=row[14],
                        data_provider=row[15],
                        genetic_sex=row[16],
                        annotation_type=row[17],
                        evidence_codes=evidence_codes,
                    )
                    annotations.append(annotation)
                except ValidationError as e:
                    logger.warning(f"Failed to parse disease annotation {row[0]}: {e}")

            return annotations

        except Exception as e:
            raise AGRAPIError(f"Database query failed for gene {gene_id}: {str(e)}")
        finally:
            session.close()

    def get_disease_annotations_by_taxon(
        self,
        taxon_curie: str,
        annotation_type: str = "gene",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_evidence_codes: bool = False,
    ) -> List[DiseaseAnnotation]:
        """Get disease annotations for all entities of a taxon.

        Args:
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')
            annotation_type: Type of annotations to return: 'gene', 'allele', 'agm', or 'all'
            limit: Maximum number of annotations to return
            offset: Number of annotations to skip (for pagination)
            include_evidence_codes: Whether to fetch evidence codes (slower)

        Returns:
            List of DiseaseAnnotation objects

        Example:
            # Get C. elegans gene disease annotations
            annotations = db_methods.get_disease_annotations_by_taxon(
                'NCBITaxon:6239',
                annotation_type='gene',
                limit=100
            )
        """
        if annotation_type == "all":
            # Combine all three types
            gene_anns = self.get_disease_annotations_by_taxon(
                taxon_curie, "gene", limit, offset, include_evidence_codes
            )
            allele_anns = self.get_disease_annotations_by_taxon(
                taxon_curie, "allele", limit, offset, include_evidence_codes
            )
            agm_anns = self.get_disease_annotations_by_taxon(
                taxon_curie, "agm", limit, offset, include_evidence_codes
            )
            return gene_anns + allele_anns + agm_anns

        session = self._create_session()
        try:
            if annotation_type == "gene":
                sql_query, params = self._build_gene_disease_query(limit, offset)
            elif annotation_type == "allele":
                sql_query, params = self._build_allele_disease_query(limit, offset)
            elif annotation_type == "agm":
                sql_query, params = self._build_agm_disease_query(limit, offset)
            else:
                raise ValueError(f"Invalid annotation_type: {annotation_type}")

            params["taxon_curie"] = taxon_curie
            rows = session.execute(sql_query, params).fetchall()

            annotations = []
            for row in rows:
                evidence_codes = []
                if include_evidence_codes:
                    evidence_codes = self._get_disease_annotation_evidence_codes(session, row[0])

                try:
                    annotation = self._build_disease_annotation_from_row(
                        row, annotation_type, evidence_codes
                    )
                    annotations.append(annotation)
                except ValidationError as e:
                    logger.warning(f"Failed to parse disease annotation {row[0]}: {e}")

            return annotations

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_disease_annotations_raw(
        self,
        taxon_curie: str,
        annotation_type: str = "gene",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get disease annotations as raw dictionaries.

        This is a lightweight alternative that returns dictionaries instead
        of Pydantic models for better performance with large datasets.

        Args:
            taxon_curie: NCBI Taxon CURIE
            annotation_type: Type of annotations: 'gene', 'allele', or 'agm'
            limit: Maximum number of annotations to return
            offset: Number of annotations to skip

        Returns:
            List of dictionaries with disease annotation data
        """
        session = self._create_session()
        try:
            if annotation_type == "gene":
                sql_query, params = self._build_gene_disease_query(limit, offset)
            elif annotation_type == "allele":
                sql_query, params = self._build_allele_disease_query(limit, offset)
            elif annotation_type == "agm":
                sql_query, params = self._build_agm_disease_query(limit, offset)
            else:
                raise ValueError(f"Invalid annotation_type: {annotation_type}")

            params["taxon_curie"] = taxon_curie
            rows = session.execute(sql_query, params).fetchall()

            results = []
            for row in rows:
                result = {
                    "id": row[0],
                    "annotation_curie": row[1],
                    "negated": row[5] or False,
                    "subject_id": row[8],
                    "subject_symbol": row[9],
                    "subject_taxon": row[10],
                    "subject_type": annotation_type,
                    "disease_curie": row[11],
                    "disease_name": row[12],
                    "relation": row[13],
                    "reference_curie": row[14],
                    "data_provider": row[15],
                }
                results.append(result)

            return results

        except Exception as e:
            raise AGRAPIError(f"Database query failed: {str(e)}")
        finally:
            session.close()

    def get_disease_annotations_by_disease(
        self,
        disease_curie: str,
        annotation_type: str = "all",
        limit: Optional[int] = None,
    ) -> List[DiseaseAnnotation]:
        """Get all annotations for a specific disease.

        Args:
            disease_curie: Disease Ontology CURIE (e.g., 'DOID:4')
            annotation_type: Type of annotations: 'gene', 'allele', 'agm', or 'all'
            limit: Maximum number of annotations to return

        Returns:
            List of DiseaseAnnotation objects for the disease
        """
        session = self._create_session()
        try:
            type_filter = ""
            if annotation_type == "gene":
                type_filter = "AND EXISTS (SELECT 1 FROM genediseaseannotation gda WHERE gda.id = da.id)"
            elif annotation_type == "allele":
                type_filter = "AND EXISTS (SELECT 1 FROM allelediseaseannotation ada WHERE ada.id = da.id)"
            elif annotation_type == "agm":
                type_filter = "AND EXISTS (SELECT 1 FROM agmdiseaseannotation agmda WHERE agmda.id = da.id)"

            # Build LIMIT clause with parameter
            params: dict[str, Any] = {"disease_curie": disease_curie}
            limit_clause = ""
            if limit is not None:
                limit_clause = "LIMIT :limit_val"
                params["limit_val"] = limit

            sql_query = text(
                f"""
            SELECT
                da.id,
                da.curie as annotation_curie,
                da.uniqueid,
                da.primaryexternalid,
                da.modinternalid,
                da.negated,
                da.datecreated,
                da.dateupdated,
                disease_ot.curie as disease_curie,
                disease_ot.name as disease_name,
                relation_vt.name as relation_name,
                ref.curie as reference_curie,
                org.abbreviation as data_provider
            FROM diseaseannotation da
            JOIN ontologyterm disease_ot ON disease_ot.id = da.diseaseannotationobject_id
            LEFT JOIN vocabularyterm relation_vt ON relation_vt.id = da.relation_id
            LEFT JOIN informationcontententity ref ON ref.id = da.evidenceitem_id
            LEFT JOIN organization org ON org.id = da.dataprovider_id
            WHERE da.obsolete = false
              AND da.internal = false
              AND disease_ot.curie = :disease_curie
              {type_filter}
            ORDER BY da.id
            {limit_clause}
            """
            )

            rows = session.execute(sql_query, params).fetchall()

            annotations = []
            for row in rows:
                try:
                    annotation = DiseaseAnnotation(
                        id=row[0],
                        curie=row[1],
                        unique_id=row[2],
                        primary_external_id=row[3],
                        mod_internal_id=row[4],
                        negated=row[5] or False,
                        date_created=row[6],
                        date_updated=row[7],
                        disease_curie=row[8],
                        disease_name=row[9],
                        relation=row[10],
                        reference_curie=row[11],
                        data_provider=row[12],
                    )
                    annotations.append(annotation)
                except ValidationError as e:
                    logger.warning(f"Failed to parse disease annotation {row[0]}: {e}")

            return annotations

        except Exception as e:
            raise AGRAPIError(f"Database query failed for disease {disease_curie}: {str(e)}")
        finally:
            session.close()

    def _get_disease_annotation_evidence_codes(
        self, session: Session, annotation_id: int
    ) -> List[str]:
        """Get evidence codes for a disease annotation.

        Args:
            session: Active database session
            annotation_id: Disease annotation ID

        Returns:
            List of ECO CURIEs
        """
        sql_query = text(
            """
        SELECT ot.curie
        FROM diseaseannotation_ontologyterm dao
        JOIN ontologyterm ot ON ot.id = dao.evidencecodes_id
        WHERE dao.diseaseannotation_id = :annotation_id
        """
        )
        rows = session.execute(sql_query, {"annotation_id": annotation_id}).fetchall()
        return [row[0] for row in rows]

    def _build_gene_disease_query(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> tuple[Any, dict]:
        """Build SQL query for gene disease annotations.

        Returns:
            Tuple of (query, params) where params includes taxon_curie placeholder
        """
        params: dict[str, Any] = {}

        # Build LIMIT/OFFSET clauses with parameters
        limit_clause = ""
        offset_clause = ""
        if limit is not None:
            limit_clause = "LIMIT :limit_val"
            params["limit_val"] = limit
        if offset is not None:
            offset_clause = "OFFSET :offset_val"
            params["offset_val"] = offset

        query = text(
            f"""
        SELECT
            da.id,
            da.curie as annotation_curie,
            da.uniqueid as unique_id,
            da.primaryexternalid as primary_external_id,
            da.modinternalid as mod_internal_id,
            da.negated,
            da.datecreated,
            da.dateupdated,
            be.primaryexternalid as subject_id,
            symbol.displaytext as subject_symbol,
            taxon.curie as subject_taxon,
            disease_ot.curie as disease_curie,
            disease_ot.name as disease_name,
            relation_vt.name as relation_name,
            ref.curie as reference_curie,
            org.abbreviation as data_provider,
            sex_vt.name as genetic_sex,
            anntype_vt.name as annotation_type,
            sgd_be.primaryexternalid as sgd_strain_background_id
        FROM diseaseannotation da
        JOIN genediseaseannotation gda ON gda.id = da.id
        JOIN biologicalentity be ON be.id = gda.diseaseannotationsubject_id
        JOIN ontologyterm disease_ot ON disease_ot.id = da.diseaseannotationobject_id
        JOIN ontologyterm taxon ON taxon.id = be.taxon_id
        LEFT JOIN vocabularyterm relation_vt ON relation_vt.id = da.relation_id
        LEFT JOIN informationcontententity ref ON ref.id = da.evidenceitem_id
        LEFT JOIN organization org ON org.id = da.dataprovider_id
        LEFT JOIN vocabularyterm sex_vt ON sex_vt.id = da.geneticsex_id
        LEFT JOIN vocabularyterm anntype_vt ON anntype_vt.id = da.annotationtype_id
        LEFT JOIN slotannotation symbol ON be.id = symbol.singlegene_id
            AND symbol.slotannotationtype = 'GeneSymbolSlotAnnotation'
            AND symbol.obsolete = false
        LEFT JOIN biologicalentity sgd_be ON sgd_be.id = gda.sgdstrainbackground_id
        WHERE da.obsolete = false
          AND da.internal = false
          AND taxon.curie = :taxon_curie
        ORDER BY da.id
        {limit_clause}
        {offset_clause}
        """
        )
        return query, params

    def _build_allele_disease_query(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> tuple[Any, dict]:
        """Build SQL query for allele disease annotations.

        Returns:
            Tuple of (query, params) where params includes taxon_curie placeholder
        """
        params: dict[str, Any] = {}

        # Build LIMIT/OFFSET clauses with parameters
        limit_clause = ""
        offset_clause = ""
        if limit is not None:
            limit_clause = "LIMIT :limit_val"
            params["limit_val"] = limit
        if offset is not None:
            offset_clause = "OFFSET :offset_val"
            params["offset_val"] = offset

        query = text(
            f"""
        SELECT
            da.id,
            da.curie as annotation_curie,
            da.uniqueid as unique_id,
            da.primaryexternalid as primary_external_id,
            da.modinternalid as mod_internal_id,
            da.negated,
            da.datecreated,
            da.dateupdated,
            be.primaryexternalid as subject_id,
            symbol.displaytext as subject_symbol,
            taxon.curie as subject_taxon,
            disease_ot.curie as disease_curie,
            disease_ot.name as disease_name,
            relation_vt.name as relation_name,
            ref.curie as reference_curie,
            org.abbreviation as data_provider,
            sex_vt.name as genetic_sex,
            anntype_vt.name as annotation_type,
            inferred_gene_be.primaryexternalid as inferred_gene_id
        FROM diseaseannotation da
        JOIN allelediseaseannotation ada ON ada.id = da.id
        JOIN biologicalentity be ON be.id = ada.diseaseannotationsubject_id
        JOIN ontologyterm disease_ot ON disease_ot.id = da.diseaseannotationobject_id
        JOIN ontologyterm taxon ON taxon.id = be.taxon_id
        LEFT JOIN vocabularyterm relation_vt ON relation_vt.id = da.relation_id
        LEFT JOIN informationcontententity ref ON ref.id = da.evidenceitem_id
        LEFT JOIN organization org ON org.id = da.dataprovider_id
        LEFT JOIN vocabularyterm sex_vt ON sex_vt.id = da.geneticsex_id
        LEFT JOIN vocabularyterm anntype_vt ON anntype_vt.id = da.annotationtype_id
        LEFT JOIN slotannotation symbol ON be.id = symbol.singleallele_id
            AND symbol.slotannotationtype = 'AlleleSymbolSlotAnnotation'
            AND symbol.obsolete = false
        LEFT JOIN biologicalentity inferred_gene_be ON inferred_gene_be.id = ada.inferredgene_id
        WHERE da.obsolete = false
          AND da.internal = false
          AND taxon.curie = :taxon_curie
        ORDER BY da.id
        {limit_clause}
        {offset_clause}
        """
        )
        return query, params

    def _build_agm_disease_query(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> tuple[Any, dict]:
        """Build SQL query for AGM disease annotations.

        Returns:
            Tuple of (query, params) where params includes taxon_curie placeholder
        """
        params: dict[str, Any] = {}

        # Build LIMIT/OFFSET clauses with parameters
        limit_clause = ""
        offset_clause = ""
        if limit is not None:
            limit_clause = "LIMIT :limit_val"
            params["limit_val"] = limit
        if offset is not None:
            offset_clause = "OFFSET :offset_val"
            params["offset_val"] = offset

        query = text(
            f"""
        SELECT
            da.id,
            da.curie as annotation_curie,
            da.uniqueid as unique_id,
            da.primaryexternalid as primary_external_id,
            da.modinternalid as mod_internal_id,
            da.negated,
            da.datecreated,
            da.dateupdated,
            be.primaryexternalid as subject_id,
            NULL as subject_symbol,
            taxon.curie as subject_taxon,
            disease_ot.curie as disease_curie,
            disease_ot.name as disease_name,
            relation_vt.name as relation_name,
            ref.curie as reference_curie,
            org.abbreviation as data_provider,
            sex_vt.name as genetic_sex,
            anntype_vt.name as annotation_type,
            inferred_gene_be.primaryexternalid as inferred_gene_id,
            inferred_allele_be.primaryexternalid as inferred_allele_id
        FROM diseaseannotation da
        JOIN agmdiseaseannotation agmda ON agmda.id = da.id
        JOIN biologicalentity be ON be.id = agmda.diseaseannotationsubject_id
        JOIN ontologyterm disease_ot ON disease_ot.id = da.diseaseannotationobject_id
        JOIN ontologyterm taxon ON taxon.id = be.taxon_id
        LEFT JOIN vocabularyterm relation_vt ON relation_vt.id = da.relation_id
        LEFT JOIN informationcontententity ref ON ref.id = da.evidenceitem_id
        LEFT JOIN organization org ON org.id = da.dataprovider_id
        LEFT JOIN vocabularyterm sex_vt ON sex_vt.id = da.geneticsex_id
        LEFT JOIN vocabularyterm anntype_vt ON anntype_vt.id = da.annotationtype_id
        LEFT JOIN biologicalentity inferred_gene_be ON inferred_gene_be.id = agmda.inferredgene_id
        LEFT JOIN biologicalentity inferred_allele_be ON inferred_allele_be.id = agmda.inferredallele_id
        WHERE da.obsolete = false
          AND da.internal = false
          AND taxon.curie = :taxon_curie
        ORDER BY da.id
        {limit_clause}
        {offset_clause}
        """
        )
        return query, params

    def _build_disease_annotation_from_row(
        self, row: Any, annotation_type: str, evidence_codes: List[str]
    ) -> DiseaseAnnotation:
        """Build a DiseaseAnnotation object from a database row.

        Args:
            row: Database row tuple
            annotation_type: Type of annotation ('gene', 'allele', 'agm')
            evidence_codes: List of evidence code CURIEs

        Returns:
            DiseaseAnnotation object
        """
        annotation_data = {
            "id": row[0],
            "curie": row[1],
            "unique_id": row[2],
            "primary_external_id": row[3],
            "mod_internal_id": row[4],
            "negated": row[5] or False,
            "date_created": row[6],
            "date_updated": row[7],
            "subject_id": row[8],
            "subject_symbol": row[9],
            "subject_taxon": row[10],
            "subject_type": annotation_type,
            "disease_curie": row[11],
            "disease_name": row[12],
            "relation": row[13],
            "reference_curie": row[14],
            "data_provider": row[15],
            "genetic_sex": row[16],
            "annotation_type": row[17],
            "evidence_codes": evidence_codes,
        }

        # Handle type-specific fields
        if annotation_type == "gene" and len(row) > 18:
            annotation_data["sgd_strain_background_id"] = row[18]
        elif annotation_type == "allele" and len(row) > 18:
            annotation_data["inferred_gene_id"] = row[18]
        elif annotation_type == "agm" and len(row) > 18:
            annotation_data["inferred_gene_id"] = row[18]
            if len(row) > 19:
                annotation_data["inferred_allele_id"] = row[19]

        return DiseaseAnnotation(**annotation_data)

    def close(self) -> None:
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._session_factory = None
