"""Runtime settings loaded from PRESSROOM_* environment variables and an optional .env file."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for pressroom.

    Values are resolved in this order (highest wins):
    1. Environment variables prefixed with ``PRESSROOM_``
    2. A ``.env`` file in the current working directory
    3. The defaults defined here
    """

    model_config = SettingsConfigDict(
        env_prefix="PRESSROOM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    db_path: Path = Field(
        default=Path("./data/pressroom.sqlite"),
        description="Path to the SQLite database file.",
    )
    user_agent: str = Field(
        default="pressroom/0.1 (+https://github.com/gregor2018github/ProjectPressroom)",
        description="User-Agent header sent with every outbound HTTP request.",
    )
    fetch_timeout: int = Field(
        default=15,
        ge=1,
        description="Per-request HTTP timeout in seconds.",
    )
    fetch_concurrency: int = Field(
        default=4,
        ge=1,
        description="Maximum number of feeds fetched in parallel.",
    )
    log_level: str = Field(
        default="INFO",
        description="Python logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL.",
    )
    dev: bool = Field(
        default=False,
        description="When True, opens CORS for the Vite dev server at http://localhost:5173.",
    )


settings: Settings = Settings()
