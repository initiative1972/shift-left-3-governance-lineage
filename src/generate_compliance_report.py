"""Generate an auditable compliance report by merging:
  - ODCS contract metadata (who classified what, as what)  [contracts/*.yaml]
  - OpenLineage events (who touched what, when, and how data flows) [lineage/events.jsonl]

It produces:
  - a CPS 234 information-asset classification register,
  - a PII propagation map (where each classified field actually flows),
  - GOVERNANCE GAPS: fields that carry PII by lineage but are not declared as PII,
  - processing evidence (jobs/runs that touched classified data),
  - declared AI-usage context.

With --strict, it exits non-zero when governance gaps are found, so it can act
as a CI gate: "no undeclared PII may reach a mart."

Usage:
    python src/generate_compliance_report.py [--strict]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

import yaml

CONTRACTS_GLOB = "contracts/*.yaml"
EVENTS_PATH = "lineage/events.jsonl"
REPORT_MD = "reports/compliance-report.md"
REPORT_HTML = "reports/compliance-report.html"

# Column transformations through which classified data is carried unchanged.
CARRYING_TRANSFORMS = {"IDENTITY", "DIRECT"}


# ---------------------------------------------------------------------------
# 1. Load contracts -> declared classifications
# ---------------------------------------------------------------------------
def load_contracts() -> tuple[dict, set, dict]:
    """Return (declared, contract_datasets, ai_usage).

    declared[(dataset, field)] = {classification, sensitivity, restricted, contract}
    contract_datasets = set of dataset names that have a contract
    ai_usage[dataset] = list of {property, value}
    """
    declared: dict = {}
    contract_datasets: set = set()
    ai_usage: dict = defaultdict(list)

    for path in sorted(glob.glob(CONTRACTS_GLOB)):
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        contract_name = os.path.basename(path)

        for cp in doc.get("customProperties", []) or []:
            # dataset-level AI usage applies to the contract's schema datasets
            for schema in doc.get("schema", []):
                ds = schema.get("physicalName") or schema.get("name")
                ai_usage[ds].append(cp)

        for schema in doc.get("schema", []):
            ds = schema.get("physicalName") or schema.get("name")
            contract_datasets.add(ds)
            for prop in schema.get("properties", []):
                tags = prop.get("tags", []) or []
                sensitivity = next(
                    (t.split(":", 1)[1] for t in tags if t.startswith("sensitivity:")),
                    "-",
                )
                declared[(ds, prop["name"])] = {
                    "classification": prop.get("classification", "unclassified"),
                    "sensitivity": sensitivity,
                    "restricted": "restricted" in tags,
                    "contract": contract_name,
                }
    return declared, contract_datasets, ai_usage


# ---------------------------------------------------------------------------
# 2. Load lineage events -> graph
# ---------------------------------------------------------------------------
def load_lineage() -> dict:
    jobs: dict = defaultdict(lambda: {"inputs": set(), "outputs": set(), "runs": set(), "times": []})
    # undirected adjacency over "carrying" column edges: node = (dataset, field)
    adjacency: dict = defaultdict(set)
    dataset_fields: dict = defaultdict(set)
    dataset_producers: dict = defaultdict(set)
    dataset_consumers: dict = defaultdict(set)

    if not os.path.exists(EVENTS_PATH):
        raise SystemExit(f"No lineage events at {EVENTS_PATH}. Run the pipeline first.")

    with open(EVENTS_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            jname = ev["job"]["name"]
            job = jobs[jname]
            job["runs"].add(ev["run"]["runId"])
            job["times"].append(ev["eventTime"])

            for ds in ev.get("inputs", []):
                job["inputs"].add(ds["name"])
                dataset_consumers[ds["name"]].add(jname)
                for f in ds.get("facets", {}).get("schema", {}).get("fields", []):
                    dataset_fields[ds["name"]].add(f["name"])

            for ds in ev.get("outputs", []):
                job["outputs"].add(ds["name"])
                dataset_producers[ds["name"]].add(jname)
                for f in ds.get("facets", {}).get("schema", {}).get("fields", []):
                    dataset_fields[ds["name"]].add(f["name"])

                cl = ds.get("facets", {}).get("columnLineage", {}).get("fields", {})
                for out_field, spec in cl.items():
                    out_node = (ds["name"], out_field)
                    if spec.get("transformationType", "IDENTITY") in CARRYING_TRANSFORMS:
                        for inf in spec.get("inputFields", []):
                            in_node = (inf["name"], inf["field"])
                            adjacency[out_node].add(in_node)
                            adjacency[in_node].add(out_node)

    return {
        "jobs": jobs,
        "adjacency": adjacency,
        "dataset_fields": dataset_fields,
        "dataset_producers": dataset_producers,
        "dataset_consumers": dataset_consumers,
    }


# ---------------------------------------------------------------------------
# 3. Propagate PII along carrying edges
# ---------------------------------------------------------------------------
def propagate_pii(declared: dict, adjacency: dict) -> dict:
    """BFS from declared-PII nodes over carrying edges.

    Returns effective[(dataset, field)] = origin (dataset, field) it came from.
    """
    effective: dict = {}
    seeds = [node for node, meta in declared.items() if meta["classification"] == "PII"]
    for seed in seeds:
        stack = [seed]
        while stack:
            node = stack.pop()
            if node in effective:
                continue
            effective[node] = seed
            for nbr in adjacency.get(node, ()):
                if nbr not in effective:
                    stack.append(nbr)
    return effective


# ---------------------------------------------------------------------------
# 4. Build report
# ---------------------------------------------------------------------------
def build_report(declared, contract_datasets, ai_usage, lineage, effective):
    jobs = lineage["jobs"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Governance gaps
    gaps = []  # (dataset, field, origin, severity, note)
    for node, origin in sorted(effective.items()):
        ds, field = node
        meta = declared.get(node)
        if meta and meta["classification"] == "PII":
            continue  # correctly declared
        if ds not in contract_datasets:
            gaps.append((ds, field, origin, "INFO",
                         "PII present in an ungoverned dataset (no contract)."))
        else:
            gaps.append((ds, field, origin, "HIGH",
                         "Field carries PII (via lineage) but is NOT classified in its contract."))

    lines: list[str] = []
    w = lines.append
    w("# Automated Compliance Evidence Report")
    w("")
    w(f"*Generated: {now}*  ·  *Source: ODCS contracts + OpenLineage events*")
    w("")
    w("> Continuous, automated evidence of data classification, lineage and processing — "
      "the kind of artefact an auditor asks for, produced by the pipeline itself.")
    w("")
    w(f"- Jobs observed: **{len(jobs)}**")
    w(f"- Declared classified fields: **{sum(1 for m in declared.values() if m['classification'] != 'unclassified')}**")
    w(f"- Fields carrying PII (by lineage): **{len(effective)}**")
    high = sum(1 for g in gaps if g[3] == 'HIGH')
    w(f"- **Governance gaps (HIGH): {high}**")
    w("")

    # A. CPS 234 register
    w("## 1. Information Asset Classification Register (CPS 234)")
    w("")
    w("| Dataset | Field | Classification | Sensitivity | Restricted | Source contract |")
    w("|---|---|---|---|---|---|")
    for (ds, field), m in sorted(declared.items()):
        if m["classification"] == "unclassified":
            continue
        w(f"| {ds} | {field} | {m['classification']} | {m['sensitivity']} | "
          f"{'yes' if m['restricted'] else '-'} | {m['contract']} |")
    w("")

    # B. PII propagation
    w("## 2. PII Propagation Map (where classified data actually flows)")
    w("")
    by_origin = defaultdict(list)
    for node, origin in effective.items():
        by_origin[origin].append(node)
    for origin in sorted(by_origin):
        ods, ofield = origin
        reach = sorted({ds for (ds, _f) in by_origin[origin]})
        w(f"- **{ods}.{ofield}** ({declared[origin]['classification']}, "
          f"sensitivity {declared[origin]['sensitivity']}) flows to: "
          f"{', '.join(reach)}")
    w("")

    # C. Governance gaps (the money shot)
    w("## 3. Governance Gaps Detected")
    w("")
    if not gaps:
        w("No gaps detected. Every field carrying PII is correctly classified.")
    else:
        w("| Severity | Dataset | Field | Inherited from | Finding |")
        w("|---|---|---|---|---|")
        for ds, field, origin, sev, note in gaps:
            w(f"| {sev} | {ds} | {field} | {origin[0]}.{origin[1]} | {note} |")
    w("")

    # D. Processing evidence
    w("## 4. Processing Evidence (jobs that touched classified data)")
    w("")
    w("| Job | Runs | Inputs | Outputs | Touched classified fields |")
    w("|---|---|---|---|---|")
    for jname, j in sorted(jobs.items()):
        touched = sorted({
            f"{ds}.{field}"
            for (ds, field) in effective
            if ds in (j["inputs"] | j["outputs"])
        })
        w(f"| {jname} | {len(j['runs'])} | {', '.join(sorted(j['inputs'])) or '-'} | "
          f"{', '.join(sorted(j['outputs'])) or '-'} | {', '.join(touched) or '-'} |")
    w("")

    # E. AI usage
    w("## 5. Declared AI-Usage Context (ODCS v3.2.0)")
    w("")
    if not ai_usage:
        w("No AI-usage context declared.")
    else:
        for ds, props in sorted(ai_usage.items()):
            w(f"- **{ds}**")
            for p in props:
                w(f"  - `{p['property']}`: {p['value']}")
    w("")

    w("---")
    w("*This report is generated automatically from version-controlled contracts "
      "and emitted lineage. It is evidence of control operation, not legal or "
      "compliance advice. Synthetic data only.*")

    return "\n".join(lines), high


def to_html(md: str) -> str:
    # Deliberately tiny: wrap the markdown in a styled <pre> plus a heading.
    # (Keeps the project dependency-light; swap for a markdown lib if desired.)
    body = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Compliance Evidence Report</title>"
        "<style>body{font-family:system-ui,Segoe UI,Arial;margin:2rem;max-width:1000px}"
        "pre{white-space:pre-wrap;line-height:1.45;font-size:14px}</style></head>"
        f"<body><pre>{body}</pre></body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero if HIGH governance gaps are found")
    args = parser.parse_args()

    declared, contract_datasets, ai_usage = load_contracts()
    lineage = load_lineage()
    effective = propagate_pii(declared, lineage["adjacency"])
    report, high_gaps = build_report(
        declared, contract_datasets, ai_usage, lineage, effective
    )

    os.makedirs("reports", exist_ok=True)
    with open(REPORT_MD, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    with open(REPORT_HTML, "w", encoding="utf-8") as fh:
        fh.write(to_html(report))

    print(f"Report written to {REPORT_MD} and {REPORT_HTML}")
    print(f"HIGH governance gaps detected: {high_gaps}")
    if args.strict and high_gaps:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
