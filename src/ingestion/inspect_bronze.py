"""Quick look at what has landed in Bronze (Day 6 exercise).

    python -m src.ingestion.inspect_bronze

Prints run count, aircraft per run, and a few decoded sample rows so you
learn the 17-field state vector before writing Silver in Week 3.
"""
import json
from pathlib import Path

from src.common.config import get_settings

STATE_FIELDS = [
    "icao24", "callsign", "origin_country", "time_position", "last_contact",
    "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
    "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk",
    "spi", "position_source",
]


def main() -> None:
    root = Path(get_settings().bronze_root)
    files = sorted(root.rglob("run_*.json"))
    if not files:
        print(f"No Bronze files under {root}. Run the ingestor first.")
        return

    total = 0
    for path in files:
        meta = json.loads(path.read_text())["metadata"]
        total += meta["record_count"]
        print(f"{meta['ingested_at']}  aircraft={meta['record_count']:>5}  "
              f"credits_left={meta['rate_limit_remaining']}")
    print(f"\n{len(files)} runs, {total} state rows in total\n")

    states = json.loads(files[-1].read_text())["payload"].get("states") or []
    print("Sample decoded rows from latest run:")
    for row in states[:3]:
        print(dict(zip(STATE_FIELDS, row)))


if __name__ == "__main__":
    main()
