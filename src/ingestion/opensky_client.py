"""Thin client for the OpenSky /states/all endpoint.

Handles:
  * Bearer auth (or anonymous if no credentials are configured)
  * 401 -> refresh token once and retry
  * 429 -> wait X-Rate-Limit-Retry-After-Seconds (capped) and retry
  * 5xx / network errors -> exponential backoff retry
It returns the raw JSON body plus response metadata; no parsing here,
because Bronze must store exactly what the API sent.
"""
import time
from dataclasses import dataclass

import requests

from src.common.config import Settings
from src.common.logger import get_logger
from src.ingestion.auth import TokenManager

log = get_logger(__name__)

MAX_429_WAIT_SECONDS = 120


class OpenSkyError(Exception):
    """Raised when the API cannot be reached after all retries."""


@dataclass
class ApiResponse:
    body: dict
    status_code: int
    rate_limit_remaining: int | None
    elapsed_ms: int


class OpenSkyClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None,
                 token_manager: TokenManager | None = None, sleep=time.sleep):
        self.settings = settings
        self.session = session or requests.Session()
        self.tokens = token_manager or (TokenManager(settings, self.session)
                                        if settings.has_credentials else None)
        self._sleep = sleep  # injectable so tests don't actually wait

    def _headers(self) -> dict:
        if self.tokens is None:
            return {}
        return {"Authorization": f"Bearer {self.tokens.get_token()}"}

    def get_states(self) -> ApiResponse:
        url = f"{self.settings.api_base_url}/states/all"
        params = self.settings.bbox.as_params()
        refreshed_after_401 = False

        for attempt in range(1, self.settings.max_retries + 1):
            start = time.monotonic()
            try:
                resp = self.session.get(url, params=params, headers=self._headers(),
                                        timeout=self.settings.request_timeout)
            except requests.RequestException as exc:
                log.warning("Attempt %s: network error %s", attempt, exc)
                self._backoff(attempt)
                continue

            elapsed_ms = int((time.monotonic() - start) * 1000)
            remaining = resp.headers.get("X-Rate-Limit-Remaining")

            if resp.status_code == 200:
                return ApiResponse(
                    body=resp.json(),
                    status_code=200,
                    rate_limit_remaining=int(remaining) if remaining is not None else None,
                    elapsed_ms=elapsed_ms,
                )

            if resp.status_code == 401 and self.tokens and not refreshed_after_401:
                log.warning("401 Unauthorized - refreshing token and retrying")
                self.tokens.invalidate()
                refreshed_after_401 = True
                continue

            if resp.status_code == 429:
                wait = int(resp.headers.get("X-Rate-Limit-Retry-After-Seconds", 60))
                if wait > MAX_429_WAIT_SECONDS:
                    raise OpenSkyError(
                        f"Rate limit exhausted; retry after {wait}s. Skipping this run.")
                log.warning("429 Too Many Requests - waiting %ss", wait)
                self._sleep(wait)
                continue

            if resp.status_code >= 500:
                log.warning("Attempt %s: server error %s", attempt, resp.status_code)
                self._backoff(attempt)
                continue

            # Other 4xx: our request is wrong, retrying won't help
            raise OpenSkyError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        raise OpenSkyError(f"Failed after {self.settings.max_retries} attempts")

    def _backoff(self, attempt: int) -> None:
        self._sleep(min(2 ** attempt, 30))
