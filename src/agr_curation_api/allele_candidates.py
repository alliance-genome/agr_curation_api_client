"""Bounded, evidence-rich allele discovery. Ranking is not identity resolution."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text


def _limit(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _prepare(session: Any) -> None:
    session.execute(
        text("SELECT set_config('statement_timeout', :timeout, true)"),
        {"timeout": str(_limit("AGR_ALLELE_QUERY_TIMEOUT_MS", 15000))},
    )


_DETAIL_SQL = """
SELECT be.id AS database_id, COALESCE(NULLIF(be.primaryexternalid, ''), NULLIF(be.curie, '')) AS curie,
       taxon.curie AS taxon,
       (SELECT sa.displaytext FROM slotannotation sa WHERE sa.singleallele_id=be.id
        AND sa.slotannotationtype='AlleleSymbolSlotAnnotation' AND NOT sa.obsolete AND NOT sa.internal
        ORDER BY sa.id LIMIT 1) AS symbol,
       (SELECT sa.displaytext FROM slotannotation sa WHERE sa.singleallele_id=be.id
        AND sa.slotannotationtype='AlleleFullNameSlotAnnotation' AND NOT sa.obsolete AND NOT sa.internal
        ORDER BY sa.id LIMIT 1) AS name,
       ARRAY(SELECT DISTINCT sa.displaytext FROM slotannotation sa WHERE sa.singleallele_id=be.id
        AND sa.slotannotationtype='AlleleSynonymSlotAnnotation' AND NOT sa.obsolete AND NOT sa.internal
        AND sa.displaytext IS NOT NULL ORDER BY sa.displaytext LIMIT :annotation_probe) AS synonyms,
       ARRAY(SELECT DISTINCT vt.name FROM slotannotation sa
        JOIN slotannotation_vocabularyterm sv ON sv.slotannotation_id=sa.id
        JOIN vocabularyterm vt ON vt.id=sv.functionalimpacts_id
        WHERE sa.singleallele_id=be.id AND sa.slotannotationtype='AlleleFunctionalImpactSlotAnnotation'
        AND NOT sa.obsolete AND NOT sa.internal AND NOT vt.obsolete AND vt.name IS NOT NULL
        ORDER BY vt.name LIMIT :annotation_probe) AS functional_impacts,
       (SELECT COALESCE(jsonb_agg(m), '[]'::jsonb) FROM (
        SELECT DISTINCT ot.curie, ot.name FROM slotannotation sa
        JOIN slotannotation_ontologyterm so ON so.slotannotation_id=sa.id
        JOIN ontologyterm ot ON ot.id=so.mutationtypes_id
        WHERE sa.singleallele_id=be.id AND sa.slotannotationtype='AlleleMutationTypeSlotAnnotation'
        AND NOT sa.obsolete AND NOT sa.internal AND NOT ot.obsolete
        ORDER BY ot.curie, ot.name LIMIT :annotation_probe) m) AS mutation_types,
       (SELECT COALESCE(jsonb_agg(g), '[]'::jsonb) FROM (
        SELECT DISTINCT COALESCE(NULLIF(gb.primaryexternalid, ''), NULLIF(gb.curie, '')) AS curie,
          gs.displaytext AS symbol, rel.name AS relation
        FROM allelegeneassociation aga JOIN biologicalentity gb ON gb.id=aga.allelegeneassociationobject_id
        JOIN gene ON gene.id=gb.id JOIN vocabularyterm rel ON rel.id=aga.relation_id
        LEFT JOIN slotannotation gs ON gs.singlegene_id=gb.id AND gs.slotannotationtype='GeneSymbolSlotAnnotation'
          AND NOT gs.obsolete AND NOT gs.internal
        WHERE aga.alleleassociationsubject_id=be.id AND rel.name='is_allele_of'
          AND NOT aga.obsolete AND NOT aga.internal AND NOT gb.obsolete AND NOT gb.internal
          AND gb.taxon_id=be.taxon_id
        ORDER BY curie, gs.displaytext, rel.name LIMIT :annotation_probe) g) AS genes
FROM biologicalentity be JOIN allele a ON a.id=be.id
LEFT JOIN ontologyterm taxon ON taxon.id=be.taxon_id
WHERE NOT be.obsolete AND NOT be.internal AND {identity_filter}
ORDER BY be.primaryexternalid
"""


def _details(session: Any, identifiers: Sequence[Any], *, by_database_id: bool = False) -> List[Dict[str, Any]]:
    annotation_limit = _limit("AGR_ALLELE_ANNOTATION_LIMIT", 20)
    rows = (
        session.execute(
            text(
                _DETAIL_SQL.format(
                    identity_filter=(
                        "be.id = ANY(:identifiers)"
                        if by_database_id
                        else "(be.primaryexternalid = ANY(:identifiers) OR be.curie = ANY(:identifiers))"
                    )
                )
            ),
            {"identifiers": list(identifiers), "annotation_probe": annotation_limit + 1},
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        candidate = dict(row)
        capped = []
        for field in ("synonyms", "functional_impacts", "mutation_types", "genes"):
            values = [value for value in (candidate.get(field) or []) if value is not None]
            if len(values) > annotation_limit:
                capped.append(field)
            candidate[field] = values[:annotation_limit]
        candidate["annotations_capped"] = capped
        result.append(candidate)
    return result


def get_allele_candidate_details(db: Any, identifiers: Sequence[str]) -> List[Dict[str, Any]]:
    """Fetch active/public allele facts in one bounded batch; missing facts stay empty."""
    identifiers = list(dict.fromkeys(value.strip() for value in identifiers if value.strip()))
    if not identifiers:
        return []
    if len(identifiers) > _limit("AGR_ALLELE_DISCOVERY_MAX", 1000):
        raise ValueError("Too many allele identifiers; split the detail request into bounded batches")
    session = db._create_session()
    try:
        _prepare(session)
        rows = _details(session, identifiers)
        for row in rows:
            row.pop("database_id", None)
        return rows
    finally:
        session.close()


def search_allele_candidates(
    db: Any,
    search_pattern: str,
    *,
    taxon_curie: Optional[str] = None,
    gene_identifier: Optional[str] = None,
    attribution_hint: Optional[str] = None,
    functional_impact_hint: Optional[str] = None,
    include_synonyms: bool = True,
    limit: Optional[int] = None,
    discovery_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Discover literal matches or alleles of an explicitly supplied exact gene ID/symbol.

    Attribution/full-name text and structured functional impact are soft priorities,
    never completeness filters. Counts describe the bounded discovered set, not an
    exact database total when discovery_capped is true. No candidate is confirmed.
    """
    search_pattern = search_pattern.strip()
    gene_identifier = (gene_identifier or "").strip() or None
    attribution_hint = (attribution_hint or "").strip() or None
    functional_impact_hint = (functional_impact_hint or "").strip() or None
    if not search_pattern and not gene_identifier:
        raise ValueError("Supply a literal allele query or explicit gene identity")
    maximum = _limit("AGR_ALLELE_DISCOVERY_MAX", 1000)
    limit = limit if limit is not None else _limit("AGR_ALLELE_DISPLAY_LIMIT", 20)
    budget = discovery_limit if discovery_limit is not None else _limit("AGR_ALLELE_DISCOVERY_LIMIT", 200)
    if (
        not isinstance(budget, int)
        or not 1 <= budget <= maximum
        or not isinstance(limit, int)
        or not 1 <= limit <= maximum
    ):
        raise ValueError("Allele display/discovery limits must be positive and within AGR_ALLELE_DISCOVERY_MAX")
    # Escape LIKE metacharacters: the query is literal text, not caller-supplied SQL patterns.
    escaped = search_pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    params = {
        "query": search_pattern,
        "prefix": escaped + "%",
        "contains": "%" + escaped + "%",
        "taxon": taxon_curie,
        "gene": gene_identifier,
        "synonyms": include_synonyms,
        "probe": budget + 1,
    }
    # A supplied gene should drive indexed per-allele name lookup, rather than
    # scanning all short substring matches and applying the gene filter afterward.
    # OFFSET 0 keeps PostgreSQL from flattening the lateral lookup back into the
    # global substring scan; selected_gene_ids materializes only exact gene matches.
    names_from = (
        """gene_scope scope JOIN LATERAL (
          SELECT annotations.* FROM slotannotation annotations
          WHERE annotations.singleallele_id=scope.id OFFSET 0
        ) sa ON TRUE"""
        if gene_identifier
        else "slotannotation sa"
    )
    sql = text("""
    WITH selected_gene_ids AS MATERIALIZED (
      SELECT id FROM biologicalentity WHERE primaryexternalid=:gene
      UNION SELECT id FROM biologicalentity WHERE curie=:gene
      UNION SELECT singlegene_id FROM slotannotation
        WHERE slotannotationtype='GeneSymbolSlotAnnotation' AND NOT obsolete AND NOT internal
          AND upper(displaytext)=upper(:gene)
    ), gene_scope AS (
      SELECT DISTINCT aga.alleleassociationsubject_id AS id FROM allelegeneassociation aga
      JOIN selected_gene_ids selected ON selected.id=aga.allelegeneassociationobject_id
      JOIN biologicalentity gb ON gb.id=aga.allelegeneassociationobject_id
      JOIN gene ON gene.id=gb.id JOIN vocabularyterm rel ON rel.id=aga.relation_id
      JOIN biologicalentity ab ON ab.id=aga.alleleassociationsubject_id
      WHERE :gene IS NOT NULL AND rel.name='is_allele_of'
        AND NOT aga.obsolete AND NOT aga.internal AND NOT gb.obsolete AND NOT gb.internal
        AND gb.taxon_id=ab.taxon_id
    ), matches AS (
      SELECT be.id, 0 AS literal_rank, :query AS matched_text FROM biologicalentity be
      WHERE :query <> '' AND (be.primaryexternalid=:query OR be.curie=:query)
      UNION ALL
      SELECT sa.singleallele_id, CASE WHEN upper(sa.displaytext)=upper(:query) THEN 1
             WHEN upper(sa.displaytext) LIKE upper(:prefix) THEN 2 ELSE 3 END, sa.displaytext
      FROM {names_from} WHERE :query <> '' AND sa.singleallele_id IS NOT NULL
        AND NOT sa.obsolete AND NOT sa.internal AND upper(sa.displaytext) LIKE upper(:contains)
        AND (sa.slotannotationtype IN ('AlleleSymbolSlotAnnotation','AlleleFullNameSlotAnnotation')
          OR (:synonyms AND sa.slotannotationtype='AlleleSynonymSlotAnnotation'))
      UNION ALL
      SELECT id, 4, :gene FROM gene_scope
    ), distinct_matches AS (
      SELECT DISTINCT ON (id) id, literal_rank, matched_text FROM matches ORDER BY id, literal_rank, matched_text
    )
    SELECT be.id AS database_id, m.literal_rank, m.matched_text
    FROM distinct_matches m JOIN biologicalentity be ON be.id=m.id JOIN allele a ON a.id=be.id
    LEFT JOIN ontologyterm taxon ON taxon.id=be.taxon_id
    WHERE NOT be.obsolete AND NOT be.internal AND (:taxon IS NULL OR taxon.curie=:taxon)
      AND (:gene IS NULL OR be.id IN (SELECT id FROM gene_scope))
    ORDER BY m.literal_rank, COALESCE(NULLIF(be.primaryexternalid, ''), NULLIF(be.curie, '')), be.id LIMIT :probe
    """.format(names_from=names_from))
    session = db._create_session()
    try:
        _prepare(session)
        discovered = [dict(row) for row in session.execute(sql, params).mappings().all()]
        capped = len(discovered) > budget
        discovered = discovered[:budget]
        candidates = (
            _details(session, [row["database_id"] for row in discovered], by_database_id=True) if discovered else []
        )
        ranks = {row["database_id"]: row["literal_rank"] for row in discovered}
        matched = {row["database_id"]: row["matched_text"] for row in discovered}
        for candidate in candidates:
            reasons = []
            if ranks[candidate["database_id"]] < 2:
                reasons.append("exact_identifier_or_name")
            if gene_identifier and any(
                gene_identifier.casefold() in {(g.get("curie") or "").casefold(), (g.get("symbol") or "").casefold()}
                for g in candidate["genes"]
            ):
                reasons.append("verified_is_allele_of")
            if attribution_hint and attribution_hint.casefold() in (candidate.get("name") or "").casefold():
                reasons.append("full_name_attribution_text")
            if functional_impact_hint and functional_impact_hint.casefold() in {
                v.casefold() for v in candidate["functional_impacts"]
            }:
                reasons.append("structured_functional_impact")
            candidate["match_reasons"] = reasons
            candidate["match_type"] = {
                0: "exact_id",
                1: "exact",
                2: "starts_with",
                3: "contains",
                4: "gene_association",
            }[ranks[candidate["database_id"]]]
            candidate["matched_text"] = matched[candidate["database_id"]]
            candidate["identity_status"] = "unconfirmed"
        candidates.sort(
            key=lambda c: (
                ranks[c["database_id"]] if ranks[c["database_id"]] < 2 else 2,
                -len(c["match_reasons"]),
                ranks[c["database_id"]],
                c["curie"] or "",
                c["database_id"],
            )
        )
        for candidate in candidates:
            candidate.pop("database_id", None)
        return {
            "candidates": candidates[:limit],
            "coverage": {
                "discovered_count": len(discovered),
                "returned_count": min(len(candidates), limit),
                "discovery_limit": budget,
                "display_limit": limit,
                "discovery_capped": capped,
                "display_capped": len(candidates) > limit,
                "database_total": None,
                "detail_missing_count": len(discovered) - len(candidates),
            },
        }
    finally:
        session.close()
