"""Minimal OpenLineage event emitter.

Design decision: we construct spec-compliant OpenLineage 2.0.2 RunEvents as plain
dicts and (a) always append them to a local JSONL file, and (b) optionally POST
them to a Marquez backend if MARQUEZ_URL is set.

Why not only the `openlineage-python` client? Two reasons that matter for a
*governance* project:
  1. Transparency — the emitted events are plain, inspectable JSON. An auditor
     (or a reviewer of this repo) can read exactly what evidence is produced.
  2. Zero version coupling — the compliance report reads the JSONL, so report
     generation never depends on a client library's object model.
The official client is a drop-in alternative (see README · engineering decisions).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

try:  # optional — only needed to push to Marquez
    import requests
except ImportError:  # pragma: no cover
    requests = None

PRODUCER = "https://github.com/<your-username>/shift-left-governance-lineage"
SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
SCHEMA_FACET_URL = "https://openlineage.io/spec/facets/1-1-1/SchemaDatasetFacet.json"
COLUMN_LINEAGE_FACET_URL = (
    "https://openlineage.io/spec/facets/1-2-0/ColumnLineageDatasetFacet.json"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DatasetRef:
    """A dataset with an optional schema and (for outputs) column lineage."""

    name: str
    fields: list[tuple[str, str]] = field(default_factory=list)  # (name, type)
    # output_field -> list of (input_dataset, input_field); plus a transformation type
    column_lineage: dict = field(default_factory=dict)

    def to_event_dataset(self, namespace: str) -> dict:
        facets: dict = {}
        if self.fields:
            facets["schema"] = {
                "_producer": PRODUCER,
                "_schemaURL": SCHEMA_FACET_URL,
                "fields": [{"name": n, "type": t} for n, t in self.fields],
            }
        if self.column_lineage:
            facets["columnLineage"] = {
                "_producer": PRODUCER,
                "_schemaURL": COLUMN_LINEAGE_FACET_URL,
                "fields": {
                    out_field: {
                        "inputFields": [
                            {"namespace": namespace, "name": ds, "field": fld}
                            for (ds, fld) in spec["inputs"]
                        ],
                        "transformationType": spec.get("transformationType", "IDENTITY"),
                    }
                    for out_field, spec in self.column_lineage.items()
                },
            }
        return {"namespace": namespace, "name": self.name, "facets": facets}


class LineageEmitter:
    def __init__(
        self,
        namespace: str,
        file_path: str,
        marquez_url: Optional[str] = None,
    ) -> None:
        self.namespace = namespace
        self.file_path = file_path
        self.marquez_url = marquez_url or os.environ.get("MARQUEZ_URL")
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        # Fresh run — truncate the event log so the report reflects this run only.
        open(file_path, "w", encoding="utf-8").close()

    def _write(self, event: dict) -> None:
        with open(self.file_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        if self.marquez_url and requests is not None:
            try:
                requests.post(
                    f"{self.marquez_url.rstrip('/')}/api/v1/lineage",
                    json=event,
                    timeout=5,
                )
            except Exception as exc:  # pragma: no cover - best-effort to Marquez
                print(f"  (warning: could not POST to Marquez: {exc})")

    def emit_job(
        self,
        job_name: str,
        inputs: list[DatasetRef],
        outputs: list[DatasetRef],
    ) -> None:
        """Emit a START then a COMPLETE event for one job run."""
        run_id = str(uuid.uuid4())
        job = {"namespace": self.namespace, "name": job_name}
        in_ds = [d.to_event_dataset(self.namespace) for d in inputs]
        out_ds = [d.to_event_dataset(self.namespace) for d in outputs]

        for state in ("START", "COMPLETE"):
            self._write(
                {
                    "eventType": state,
                    "eventTime": _now(),
                    "producer": PRODUCER,
                    "schemaURL": SCHEMA_URL,
                    "run": {"runId": run_id},
                    "job": job,
                    "inputs": in_ds,
                    "outputs": out_ds,
                }
            )
        print(f"  emitted lineage for job '{job_name}' "
              f"({', '.join(d.name for d in inputs)} -> {', '.join(d.name for d in outputs)})")
