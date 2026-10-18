"""Pipeline task definitions: the SQL run on DuckDB plus the declared column
lineage for each output. In production you'd parse lineage from the SQL; here we
declare it explicitly so the mapping is obvious and auditable.

Each task: job name, the SQL that produces the output table, input dataset names,
and a column-lineage map (output_field -> {inputs: [(dataset, field)], type}).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    job: str
    output: str
    inputs: list[str]
    sql: str
    column_lineage: dict


def _identity(dataset: str, fields: list[str]) -> dict:
    """Column lineage for a straight 1:1 copy of columns from one dataset."""
    return {
        f: {"inputs": [(dataset, f)], "transformationType": "IDENTITY"} for f in fields
    }


TASKS: list[Task] = [
    # ---- Ingestion (raw CSV -> staging), identity column lineage -------------
    Task(
        job="ingest_customers",
        output="stg_customers",
        inputs=["raw_customers"],
        sql="""
            create or replace table stg_customers as
            select
                customer_id,
                full_name,
                email,
                cast(dob as date) as dob,
                tax_file_number,
                cast(created_at as timestamp) as created_at
            from read_csv_auto('seeds/raw_customers.csv', header=true)
        """,
        column_lineage=_identity(
            "raw_customers",
            ["customer_id", "full_name", "email", "dob", "tax_file_number", "created_at"],
        ),
    ),
    Task(
        job="ingest_accounts",
        output="stg_accounts",
        inputs=["raw_accounts"],
        sql="""
            create or replace table stg_accounts as
            select
                account_id,
                customer_id,
                account_type,
                cast(opened_date as date) as opened_date
            from read_csv_auto('seeds/raw_accounts.csv', header=true)
        """,
        column_lineage=_identity(
            "raw_accounts", ["account_id", "customer_id", "account_type", "opened_date"]
        ),
    ),
    Task(
        job="ingest_transactions",
        output="stg_transactions",
        inputs=["raw_transactions"],
        sql="""
            create or replace table stg_transactions as
            select
                transaction_id,
                account_id,
                cast(amount as decimal(18, 2)) as amount,
                currency,
                cast(txn_date as date) as txn_date
            from read_csv_auto('seeds/raw_transactions.csv', header=true)
        """,
        column_lineage=_identity(
            "raw_transactions",
            ["transaction_id", "account_id", "amount", "currency", "txn_date"],
        ),
    ),
    # ---- Customer master (carries all PII) -----------------------------------
    Task(
        job="build_dim_customer",
        output="dim_customer",
        inputs=["stg_customers"],
        sql="""
            create or replace table dim_customer as
            select
                customer_id,
                full_name,
                email,
                dob,
                tax_file_number
            from stg_customers
        """,
        column_lineage=_identity(
            "stg_customers",
            ["customer_id", "full_name", "email", "dob", "tax_file_number"],
        ),
    ),
    # ---- Transaction fact (joins accounts to attribute customer_id) ----------
    Task(
        job="build_fct_transactions",
        output="fct_transactions",
        inputs=["stg_transactions", "stg_accounts"],
        sql="""
            create or replace table fct_transactions as
            select
                t.transaction_id,
                t.account_id,
                a.customer_id,
                t.amount,
                t.currency,
                t.txn_date
            from stg_transactions as t
            left join stg_accounts as a on t.account_id = a.account_id
        """,
        column_lineage={
            "transaction_id": {"inputs": [("stg_transactions", "transaction_id")], "transformationType": "IDENTITY"},
            "account_id": {"inputs": [("stg_transactions", "account_id")], "transformationType": "IDENTITY"},
            "customer_id": {"inputs": [("stg_accounts", "customer_id")], "transformationType": "IDENTITY"},
            "amount": {"inputs": [("stg_transactions", "amount")], "transformationType": "IDENTITY"},
            "currency": {"inputs": [("stg_transactions", "currency")], "transformationType": "IDENTITY"},
            "txn_date": {"inputs": [("stg_transactions", "txn_date")], "transformationType": "IDENTITY"},
        },
    ),
    # ---- Customer 360 mart: PII (full_name, email) flows here from dim_customer
    Task(
        job="build_customer_360",
        output="customer_360",
        inputs=["dim_customer", "fct_transactions"],
        sql="""
            create or replace table customer_360 as
            select
                c.customer_id,
                c.full_name,
                c.email,
                coalesce(sum(f.amount), 0) as total_spend,
                count(f.transaction_id) as txn_count
            from dim_customer as c
            left join fct_transactions as f on c.customer_id = f.customer_id
            group by 1, 2, 3
        """,
        column_lineage={
            "customer_id": {"inputs": [("dim_customer", "customer_id")], "transformationType": "IDENTITY"},
            "full_name": {"inputs": [("dim_customer", "full_name")], "transformationType": "IDENTITY"},
            "email": {"inputs": [("dim_customer", "email")], "transformationType": "IDENTITY"},
            "total_spend": {"inputs": [("fct_transactions", "amount")], "transformationType": "AGGREGATION"},
            "txn_count": {"inputs": [("fct_transactions", "transaction_id")], "transformationType": "AGGREGATION"},
        },
    ),
]
