"""
Schema comparison utilities for PostgreSQL databases.
"""

from typing import Any, Dict, List, Optional

import psycopg2


def get_schema_info(
    conn_config: dict, tables_filter: Optional[List[str]] = None
) -> dict:
    """
    Extract schema information from a PostgreSQL database.

    Returns dict with:
    - tables: {table_name: {columns: [...], constraints: [...], indexes: [...]}}
    """
    conn = psycopg2.connect(**conn_config)
    try:
        with conn.cursor() as cur:
            # Get all tables
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """
            )
            tables = [row[0] for row in cur.fetchall()]

            if tables_filter:
                tables = [t for t in tables if t in tables_filter]

            schema: Dict[str, Any] = {"tables": {}}

            for table in tables:
                # Get columns
                cur.execute(
                    """
                    SELECT
                        column_name,
                        data_type,
                        character_maximum_length,
                        numeric_precision,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """,
                    (table,),
                )

                columns = []
                for row in cur.fetchall():
                    columns.append(
                        {
                            "name": row[0],
                            "type": row[1],
                            "max_length": row[2],
                            "precision": row[3],
                            "nullable": row[4] == "YES",
                            "default": row[5],
                        }
                    )

                # Get indexes
                cur.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = %s
                    ORDER BY indexname
                """,
                    (table,),
                )

                indexes = [
                    {"name": row[0], "definition": row[1]} for row in cur.fetchall()
                ]

                # Get constraints
                cur.execute(
                    """
                    SELECT
                        tc.constraint_name,
                        tc.constraint_type,
                        kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = 'public' AND tc.table_name = %s
                    ORDER BY tc.constraint_name
                """,
                    (table,),
                )

                constraints = []
                for row in cur.fetchall():
                    constraints.append(
                        {"name": row[0], "type": row[1], "column": row[2]}
                    )

                schema["tables"][table] = {
                    "columns": columns,
                    "indexes": indexes,
                    "constraints": constraints,
                }

            return schema
    finally:
        conn.close()


def compare_schemas(
    alpha_config: dict,
    prod_config: dict,
    tables_filter: Optional[List[str]] = None,
) -> dict:
    """
    Compare schemas between alpha and production databases.

    Returns diff showing:
    - added_tables: Tables in alpha but not in production
    - removed_tables: Tables in production but not in alpha
    - modified_tables: Tables with column/constraint changes
    - added_indexes: Indexes in alpha but not production
    - removed_indexes: Indexes in production but not alpha
    """
    alpha_schema = get_schema_info(alpha_config, tables_filter)
    prod_schema = get_schema_info(prod_config, tables_filter)

    alpha_tables = set(alpha_schema["tables"].keys())
    prod_tables = set(prod_schema["tables"].keys())

    diff: Dict[str, Any] = {
        "added_tables": sorted(list(alpha_tables - prod_tables)),
        "removed_tables": sorted(list(prod_tables - alpha_tables)),
        "modified_tables": {},
        "added_indexes": [],
        "removed_indexes": [],
    }

    # Compare common tables
    common_tables = alpha_tables & prod_tables
    for table in sorted(common_tables):
        alpha_table = alpha_schema["tables"][table]
        prod_table = prod_schema["tables"][table]

        table_diff: Dict[str, Any] = {}

        # Compare columns
        alpha_cols = {c["name"]: c for c in alpha_table["columns"]}
        prod_cols = {c["name"]: c for c in prod_table["columns"]}

        added_cols = set(alpha_cols.keys()) - set(prod_cols.keys())
        removed_cols = set(prod_cols.keys()) - set(alpha_cols.keys())

        if added_cols:
            table_diff["added_columns"] = sorted(list(added_cols))
        if removed_cols:
            table_diff["removed_columns"] = sorted(list(removed_cols))

        # Check for modified columns (type changes, etc.)
        common_cols = set(alpha_cols.keys()) & set(prod_cols.keys())
        modified_cols = {}
        for col in sorted(common_cols):
            changes = {}
            if alpha_cols[col]["type"] != prod_cols[col]["type"]:
                changes["type"] = {
                    "old": prod_cols[col]["type"],
                    "new": alpha_cols[col]["type"],
                }
            if alpha_cols[col]["nullable"] != prod_cols[col]["nullable"]:
                changes["nullable"] = {
                    "old": prod_cols[col]["nullable"],
                    "new": alpha_cols[col]["nullable"],
                }
            if changes:
                modified_cols[col] = changes

        if modified_cols:
            table_diff["modified_columns"] = modified_cols

        # Compare indexes
        alpha_idx = {i["name"] for i in alpha_table["indexes"]}
        prod_idx = {i["name"] for i in prod_table["indexes"]}

        added_idx = alpha_idx - prod_idx
        removed_idx = prod_idx - alpha_idx

        if added_idx:
            diff["added_indexes"].extend(
                sorted([f"{table}.{idx}" for idx in added_idx])
            )
        if removed_idx:
            diff["removed_indexes"].extend(
                sorted([f"{table}.{idx}" for idx in removed_idx])
            )

        if table_diff:
            diff["modified_tables"][table] = table_diff

    # Sort the index lists
    diff["added_indexes"] = sorted(diff["added_indexes"])
    diff["removed_indexes"] = sorted(diff["removed_indexes"])

    return diff


def format_diff_report(diff: dict) -> str:
    """Format diff as human-readable report."""
    lines = []

    if diff["added_tables"]:
        lines.append(f"TABLES IN ALPHA ONLY (not in production) [{len(diff['added_tables'])}]:")
        for t in diff["added_tables"]:
            lines.append(f"  + {t}")
        lines.append("")

    if diff["removed_tables"]:
        lines.append(f"TABLES IN PRODUCTION ONLY (not in alpha) [{len(diff['removed_tables'])}]:")
        for t in diff["removed_tables"]:
            lines.append(f"  - {t}")
        lines.append("")

    if diff["modified_tables"]:
        lines.append(f"MODIFIED TABLES [{len(diff['modified_tables'])}]:")
        for table, changes in sorted(diff["modified_tables"].items()):
            lines.append(f"  {table}:")
            if "added_columns" in changes:
                lines.append("    Columns in alpha only:")
                for col in changes["added_columns"]:
                    lines.append(f"      + {col}")
            if "removed_columns" in changes:
                lines.append("    Columns in production only:")
                for col in changes["removed_columns"]:
                    lines.append(f"      - {col}")
            if "modified_columns" in changes:
                lines.append("    Changed columns:")
                for col, change in sorted(changes["modified_columns"].items()):
                    lines.append(f"      ~ {col}: {change}")
        lines.append("")

    if diff["added_indexes"]:
        lines.append(f"INDEXES IN ALPHA ONLY (not in production) [{len(diff['added_indexes'])}]:")
        for idx in diff["added_indexes"]:
            lines.append(f"  + {idx}")
        lines.append("")

    if diff["removed_indexes"]:
        lines.append(f"INDEXES IN PRODUCTION ONLY (not in alpha) [{len(diff['removed_indexes'])}]:")
        for idx in diff["removed_indexes"]:
            lines.append(f"  - {idx}")
        lines.append("")

    if not any(
        [
            diff["added_tables"],
            diff["removed_tables"],
            diff["modified_tables"],
            diff["added_indexes"],
            diff["removed_indexes"],
        ]
    ):
        lines.append("No schema differences detected.")

    return "\n".join(lines)
