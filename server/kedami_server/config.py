"""Launch settings, passed by Electron main through the environment."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int
    token: str
    data_dir: Path
    allowed_origins: tuple[str, ...]


def from_env() -> Settings:
    missing = [name for name in ("KEDAMI_PORT", "KEDAMI_TOKEN", "KEDAMI_DATA_DIR") if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"missing environment variables: {', '.join(missing)}")
    origins = os.environ.get("KEDAMI_ALLOWED_ORIGINS", "")
    return Settings(
        port=int(os.environ["KEDAMI_PORT"]),
        token=os.environ["KEDAMI_TOKEN"],
        data_dir=Path(os.environ["KEDAMI_DATA_DIR"]).resolve(),
        allowed_origins=tuple(o for o in origins.split(",") if o),
    )


@dataclass(frozen=True)
class ModelRole:
    model: str
    max_tokens: int
    effort: str | None = None
    # Re-run a safety-declined request on Anthropic's recommended fallback model.
    fallbacks: bool = False


# Every model call names one of these roles. See architecture/system.md, Model roles.
MODEL_ROLES = {
    "generate": ModelRole(model="claude-sonnet-5-5", max_tokens=64000, effort="high", fallbacks=True),
    "small_check": ModelRole(model="claude-haiku-4-5", max_tokens=4000),
}
