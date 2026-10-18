"""Export every table in a DuckDB database to a single Markdown file.

For each table it writes the column schema and all rows as Markdown tables.

Usage:
    python src/export_duckdb_to_md.py --db governance.duckdb --out governance-duckdb.md
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import duckdb


def md_escape(value) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="governance.duckdb")
    parser.add_argument("--out", default="governance-duckdb.md")
    args = parser.parse_args()

    con = duckdb.connect(args.db, read_only=True)
    tables = [r[0] for r in con.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'main' order by table_name"
    ).fetchall()]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = []
    w = lines.append

    w(f"# DuckDB export — `{args.db}`")
    w("")
    w(f"*Generated: {now}*")
    w("")
    w(f"Database contains **{len(tables)}** table(s): "
      + ", ".join(f"`{t}`" for t in tables))
    w("")
    w("> Synthetic demonstration data only. No real, customer, or employer data.")
    w("")

    for table in tables:
        cols = con.execute(f"describe {table}").fetchall()  # name, type, null, key, default, extra
        col_names = [c[0] for c in cols]
        rows = con.execute(f"select * from {table}").fetchall()

        w(f"## `{table}`  ({len(rows)} rows)")
        w("")

        # Schema
        w("**Schema**")
        w("")
        w("| Column | Type | Nullable |")
        w("|---|---|---|")
        for c in cols:
            nullable = c[2] if len(c) > 2 and c[2] is not None else ""
            w(f"| {md_escape(c[0])} | {md_escape(c[1])} | {md_escape(nullable)} |")
        w("")

        # Data
        w("**Data**")
        w("")
        w("| " + " | ".join(col_names) + " |")
        w("|" + "|".join(["---"] * len(col_names)) + "|")
        for row in rows:
            w("| " + " | ".join(md_escape(v) for v in row) + " |")
        w("")

    con.close()

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Wrote {args.out} ({len(tables)} tables)")


if __name__ == "__main__":
    main()
