"""Central configuration, read from environment variables (.env file locally)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class BoundingBox:
    """Geographic box for the /states/all query (default: India)."""
    lamin: float = 6.0
    lomin: float = 68.0
    lamax: float = 37.0
    lomax: float = 98.0

    def as_params(self) -> dict:
        return {"lamin": self.lamin, "lomin": self.lomin,
                "lamax": self.lamax, "lomax": self.lomax}


@dataclass(frozen=True)
class Settings:
    client_id: str = field(default_factory=lambda: os.getenv("OPENSKY_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("OPENSKY_CLIENT_SECRET", ""))
    token_url: str = field(default_factory=lambda: os.getenv(
        "OPENSKY_TOKEN_URL",
        "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
    ))
    api_base_url: str = field(default_factory=lambda: os.getenv(
        "OPENSKY_API_BASE_URL", "https://opensky-network.org/api"))
    bronze_root: Path = field(default_factory=lambda: Path(os.getenv("BRONZE_ROOT", "data/bronze")))
    poll_interval_seconds: int = field(default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "300")))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    bbox: BoundingBox = field(default_factory=BoundingBox)

    @property
    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret)


def get_settings() -> Settings:
    return Settings()
