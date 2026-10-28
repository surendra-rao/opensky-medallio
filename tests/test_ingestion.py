"""Unit tests with a fake HTTP session - no network or credentials needed."""
import json
from datetime import datetime, timezone

import pytest

from src.common.config import Settings
from src.ingestion.opensky_client import OpenSkyClient, OpenSkyError
from src.ingestion.writer import LocalBronzeWriter

SAMPLE_BODY = {
    "time": 1793200000,
    "states": [
        ["800a1b", "AIC101  ", "India", 1793199995, 1793199999, 78.43, 17.24,
         10668.0, False, 230.5, 45.0, 0.0, None, 10900.0, "1234", False, 0],
        ["800c2d", "IGO6E22 ", "India", 1793199990, 1793199998, 72.87, 19.09,
         None, True, 0.0, 0.0, None, None, None, None, False, 0],
    ],
}


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    """Returns queued responses in order and records calls."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def anon_settings(**overrides):
    return Settings(client_id="", client_secret="", max_retries=3, **overrides)


def make_client(responses):
    session = FakeSession(responses)
    return OpenSkyClient(anon_settings(), session=session, sleep=lambda s: None), session


def test_success_returns_body_and_credits():
    client, _ = make_client([FakeResponse(200, SAMPLE_BODY, {"X-Rate-Limit-Remaining": "3990"})])
    resp = client.get_states()
    assert resp.status_code == 200
    assert len(resp.body["states"]) == 2
    assert resp.rate_limit_remaining == 3990


def test_retries_on_server_error_then_succeeds():
    client, session = make_client([FakeResponse(503), FakeResponse(200, SAMPLE_BODY)])
    assert client.get_states().status_code == 200
    assert session.calls == 2


def test_429_waits_then_succeeds():
    waits = []
    session = FakeSession([
        FakeResponse(429, headers={"X-Rate-Limit-Retry-After-Seconds": "5"}),
        FakeResponse(200, SAMPLE_BODY),
    ])
    client = OpenSkyClient(anon_settings(), session=session, sleep=waits.append)
    client.get_states()
    assert waits == [5]


def test_429_with_long_wait_skips_run():
    client, _ = make_client([
        FakeResponse(429, headers={"X-Rate-Limit-Retry-After-Seconds": "3600"})])
    with pytest.raises(OpenSkyError):
        client.get_states()


def test_bad_request_is_not_retried():
    client, session = make_client([FakeResponse(400)])
    with pytest.raises(OpenSkyError):
        client.get_states()
    assert session.calls == 1


def test_writer_creates_partitioned_file_with_metadata(tmp_path):
    client, _ = make_client([FakeResponse(200, SAMPLE_BODY, {"X-Rate-Limit-Remaining": "100"})])
    resp = client.get_states()
    when = datetime(2026, 10, 29, 14, 5, tzinfo=timezone.utc)

    path = LocalBronzeWriter(tmp_path).write(resp, ingested_at=when)

    assert "date=2026-10-29" in str(path) and "hour=14" in str(path)
    saved = json.loads(path.read_text())
    assert saved["metadata"]["record_count"] == 2
    assert saved["metadata"]["api_time"] == 1793200000
    assert saved["payload"] == SAMPLE_BODY  # raw payload untouched
    assert not list(tmp_path.rglob("*.tmp"))  # atomic write left no temp file


def test_writer_handles_null_states(tmp_path):
    client, _ = make_client([FakeResponse(200, {"time": 1, "states": None})])
    path = LocalBronzeWriter(tmp_path).write(client.get_states())
    assert json.loads(path.read_text())["metadata"]["record_count"] == 0
