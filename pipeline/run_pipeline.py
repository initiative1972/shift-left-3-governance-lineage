"""Run the governance pipeline on DuckDB and emit OpenLineage events.

For each task we:
  1. execute the SQL against the local DuckDB warehouse,
  2. read the resulting (ground-truth) schema back from DuckDB,
  3. emit a START + COMPLETE OpenLineage event with input/output datasets,
     schema facets, and a column-lineage facet on the output.

The events go to lineage/events.jsonl (always) and to Marquez (if MARQUEZ_URL
is set). The compliance report is generated separately from the event log.

Usage:
    python -m pipeline.run_pipeline
"""

from __future__ import annotations

import os

import duckdb

from pipeline.lineage import DatasetRef, LineageEmitter
from pipeline.transforms import TASKS

NAMESPACE = "governance-demo"
DB_PATH = "governance.duckdb"
EVENTS_PATH = "lineage/events.jsonl"

# Raw source datasets (CSV files) and their schemas, so ingestion lineage has
# a typed upstream node to point at.
RAW_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "raw_customers": [
        ("customer_id", "VARCHAR"), ("full_name", "VARCHAR"), ("email", "VARCHAR"),
        ("dob", "VARCHAR"), ("tax_file_number", "VARCHAR"), ("created_at", "VARCHAR"),
    ],
    "raw_accounts": [
        ("account_id", "VARCHAR"), ("customer_id", "VARCHAR"),
        ("account_type", "VARCHAR"), ("opened_date", "VARCHAR"),
    ],
    "raw_transactions": [
        ("transaction_id", "VARCHAR"), ("account_id", "VARCHAR"),
        ("amount", "VARCHAR"), ("currency", "VARCHAR"), ("txn_date", "VARCHAR"),
    ],
}


def schema_of(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    rows = con.execute(f"describe {table}").fetchall()
    return [(r[0], r[1]) for r in rows]


def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = duckdb.connect(DB_PATH)
    emitter = LineageEmitter(NAMESPACE, EVENTS_PATH)

    print(f"Running governance pipeline ({len(TASKS)} jobs)...")
    for task in TASKS:
        con.execute(task.sql)
        out_schema = schema_of(con, task.output)

        inputs = []
        for name in task.inputs:
            if name in RAW_SCHEMAS:
                inputs.append(DatasetRef(name=name, fields=RAW_SCHEMAS[name]))
            else:
                inputs.append(DatasetRef(name=name, fields=schema_of(con, name)))

        output = DatasetRef(
            name=task.output,
            fields=out_schema,
            column_lineage=task.column_lineage,
        )
        emitter.emit_job(task.job, inputs, [output])

    con.close()
    print(f"\nDone. Lineage events written to {EVENTS_PATH}")
    print("Generate the compliance report with: make report")


if __name__ == "__main__":
    main()
