"""Entry point for Bronze ingestion.

    python -m src.ingestion.run_ingest            # one run
    python -m src.ingestion.run_ingest --loop     # every POLL_INTERVAL_SECONDS until Ctrl+C

In Week 2 Airflow calls `ingest_once()` directly, so the --loop mode is
only for local testing this week.
"""
import argparse
import time

from src.common.config import get_settings
from src.common.logger import get_logger
from src.ingestion.opensky_client import OpenSkyClient, OpenSkyError
from src.ingestion.writer import LocalBronzeWriter

log = get_logger("ingest")


def ingest_once(client: OpenSkyClient, writer: LocalBronzeWriter) -> bool:
    try:
        resp = client.get_states()
    except OpenSkyError as exc:
        log.error("Run skipped: %s", exc)
        return False
    path = writer.write(resp)
    count = len(resp.body.get("states") or [])
    log.info("Saved %s aircraft -> %s (credits left: %s, %sms)",
             count, path, resp.rate_limit_remaining, resp.elapsed_ms)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSky -> Bronze ingestion")
    parser.add_argument("--loop", action="store_true", help="keep polling on an interval")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_credentials:
        log.warning("No OPENSKY_CLIENT_ID/SECRET found - running anonymously (400 credits/day)")

    client = OpenSkyClient(settings)
    writer = LocalBronzeWriter(settings.bronze_root)

    if not args.loop:
        ingest_once(client, writer)
        return

    log.info("Polling every %ss. Press Ctrl+C to stop.", settings.poll_interval_seconds)
    try:
        while True:
            started = time.monotonic()
            ingest_once(client, writer)
            time.sleep(max(0, settings.poll_interval_seconds - (time.monotonic() - started)))
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()
