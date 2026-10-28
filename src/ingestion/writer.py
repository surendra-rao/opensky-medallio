"""Bronze writer: stores the raw API payload, untouched, inside a metadata envelope.

Layout (Hive-style partitions, so Spark can read it directly in Week 3):
    data/bronze/opensky/states/date=YYYY-MM-DD/hour=HH/run_<epoch>_<runid>.json

Week 2 adds a MinioWriter with the same `write()` signature; the runner
won't need to change.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.ingestion.opensky_client import ApiResponse


def build_envelope(resp: ApiResponse, run_id: str, ingested_at: datetime) -> dict:
    states = resp.body.get("states") or []  # API returns null when no aircraft
    return {
        "metadata": {
            "run_id": run_id,
            "source": "opensky/states/all",
            "ingested_at": ingested_at.isoformat(),
            "api_time": resp.body.get("time"),
            "http_status": resp.status_code,
            "record_count": len(states),
            "rate_limit_remaining": resp.rate_limit_remaining,
            "elapsed_ms": resp.elapsed_ms,
        },
        "payload": resp.body,  # exactly as received
    }


class LocalBronzeWriter:
    def __init__(self, root: Path):
        self.root = Path(root)

    def partition_path(self, ingested_at: datetime) -> Path:
        return (self.root / "opensky" / "states"
                / f"date={ingested_at:%Y-%m-%d}" / f"hour={ingested_at:%H}")

    def write(self, resp: ApiResponse, ingested_at: datetime | None = None) -> Path:
        ingested_at = ingested_at or datetime.now(timezone.utc)
        run_id = uuid.uuid4().hex[:8]
        folder = self.partition_path(ingested_at)
        folder.mkdir(parents=True, exist_ok=True)

        target = folder / f"run_{int(ingested_at.timestamp())}_{run_id}.json"
        tmp = target.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(build_envelope(resp, run_id, ingested_at), f)
        os.replace(tmp, target)  # atomic: readers never see half-written files
        return target
