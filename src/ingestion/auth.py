"""OAuth2 client-credentials token handling for OpenSky.

The token is short-lived (~30 min). We cache it in memory and refresh it
shortly before it expires, so a long-running ingestor never sends an
expired token.
"""
import time

import requests

from src.common.config import Settings
from src.common.logger import get_logger

log = get_logger(__name__)

REFRESH_MARGIN_SECONDS = 60  # refresh 1 minute before expiry


class TokenManager:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def _fetch_token(self) -> None:
        resp = self.session.post(
            self.settings.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            },
            timeout=self.settings.request_timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + int(body.get("expires_in", 1800))
        log.info("Fetched new OpenSky token (valid %ss)", body.get("expires_in"))

    def get_token(self) -> str:
        if self._token is None or time.time() >= self._expires_at - REFRESH_MARGIN_SECONDS:
            self._fetch_token()
        return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        """Force a refresh on next call (used after a 401)."""
        self._token = None
