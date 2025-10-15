"""Direct database access methods for AGR Curation API Client.

This module provides direct database access through SQL queries,
adapted from agr_genedescriptions/pipelines/alliance/ateam_db_helper.py
"""

import logging
from os import environ
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import ValidationError

from .models import Gene, Allele
from .exceptions import AGRAPIError

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Configuration for database connection."""

    def __init__(self):
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

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """Initialize database methods.

        Args:
            config: Database configuration (defaults to environment variables)
        """
        self.config = config or DatabaseConfig()
        self._engine = None
        self._session_factory = None

    def _get_engine(self):
        """Get or create database engine."""
        if self._engine is None:
            self._engine = create_engine(self.config.connection_string)
        return self._engine

    def _get_session_factory(self):
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
        offset: Optional[int] = None
    ) -> List[Allele]:
        """Get alleles from the database by taxon.

        This uses direct SQL queries for efficient data retrieval,
        returning minimal allele information (ID and symbol).

        Args:
            taxon_curie: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')
            limit: Maximum number of alleles to return
            offset: Number of alleles to skip (for pagination)

        Returns:
            List of Allele objects with basic information

        Example:
            # Get C. elegans alleles
            alleles = db_methods.get_alleles_by_taxon('NCBITaxon:6239', limit=100)
        """
        session = self._create_session()
        try:
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

    def get_alleles_by_data_provider(
        self,
        data_provider: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Allele]:
        """Get alleles from the database by data provider.

        Args:
            data_provider: Data provider abbreviation (e.g., 'WB', 'MGI')
            limit: Maximum number of alleles to return
            offset: Number of alleles to skip

        Returns:
            List of Allele objects with basic information
        """
        session = self._create_session()
        try:
            sql_query = text("""
            SELECT
                be.primaryexternalid as "primaryExternalId",
                slota.displaytext as alleleSymbol
            FROM
                biologicalentity be
                JOIN allele a ON be.id = a.id
                JOIN slotannotation slota ON a.id = slota.singleallele_id
                JOIN dataprovider dp ON be.dataprovider_id = dp.id
            WHERE
                slota.obsolete = false
            AND
                be.obsolete = false
            AND
                slota.slotannotationtype = 'AlleleSymbolSlotAnnotation'
            AND
                dp.abbreviation = :data_provider
            ORDER BY
                be.primaryexternalid
            """)

            # Add pagination if specified
            if limit is not None:
                sql_query = text(str(sql_query) + f" LIMIT {limit}")
            if offset is not None:
                sql_query = text(str(sql_query) + f" OFFSET {offset}")

            rows = session.execute(sql_query, {'data_provider': data_provider}).fetchall()

            alleles = []
            for row in rows:
                try:
                    allele_data = {
                        'primaryExternalId': row[0],
                        'curie': row[0],
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

    def close(self):
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._session_factory = None