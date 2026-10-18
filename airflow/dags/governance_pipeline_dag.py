"""Airflow DAG variant of the governance pipeline.

This is the orchestration-grade version of `pipeline/run_pipeline.py`. Each
transform becomes a task; the DAG dependency graph mirrors the data lineage.

In a real deployment you would additionally install
`apache-airflow-providers-openlineage`, which auto-emits OpenLineage events for
supported operators. Because our transforms talk to DuckDB directly, we emit the
column-level lineage ourselves (reusing the same emitter as the standalone
runner) so the compliance evidence is identical in both modes.

Run the standalone version (`make demo`) for the quick reproducible demo; use
this DAG when you want to show it inside Airflow + the OpenLineage provider.
"""

from __future__ import annotations

import os
from datetime import datetime

import duckdb

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:  # pragma: no cover - Airflow is an optional, heavy dependency
    DAG = None
    PythonOperator = None

from pipeline.lineage import DatasetRef, LineageEmitter
from pipeline.run_pipeline import DB_PATH, EVENTS_PATH, NAMESPACE, RAW_SCHEMAS, schema_of
from pipeline.transforms import TASKS

# A single emitter/connection per run would normally be managed via XCom or a
# hook; kept module-level here for readability of the illustrative DAG.
_TASK_BY_NAME = {t.job: t for t in TASKS}


def run_task(job_name: str) -> None:
    task = _TASK_BY_NAME[job_name]
    con = duckdb.connect(DB_PATH)
    emitter = LineageEmitter(NAMESPACE, EVENTS_PATH)
    con.execute(task.sql)
    out_schema = schema_of(con, task.output)
    inputs = [
        DatasetRef(name=n, fields=RAW_SCHEMAS[n]) if n in RAW_SCHEMAS
        else DatasetRef(name=n, fields=schema_of(con, n))
        for n in task.inputs
    ]
    output = DatasetRef(name=task.output, fields=out_schema, column_lineage=task.column_lineage)
    emitter.emit_job(task.job, inputs, [output])
    con.close()


if DAG is not None:
    with DAG(
        dag_id="governance_pipeline",
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        tags=["governance", "lineage", "openlineage"],
    ) as dag:
        operators = {
            t.job: PythonOperator(
                task_id=t.job,
                python_callable=run_task,
                op_kwargs={"job_name": t.job},
            )
            for t in TASKS
        }
        # Wire dependencies from the task graph (output->input relationships).
        output_to_job = {t.output: t.job for t in TASKS}
        for t in TASKS:
            for inp in t.inputs:
                if inp in output_to_job:
                    operators[output_to_job[inp]] >> operators[t.job]
