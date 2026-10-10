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
    "transcribe": ModelRole(model="claude-opus-5-5", max_tokens=32000, effort="medium", fallbacks=True),
    "second_solve": ModelRole(model="claude-opus-5-5", max_tokens=64000, effort="high", fallbacks=True),
    "solution": ModelRole(model="claude-opus-5-5", max_tokens=32000, effort="high", fallbacks=True),
    "small_check": ModelRole(model="claude-haiku-4-5", max_tokens=4000),
}


@dataclass(frozen=True)
class ModelPrice:
    """List prices in US dollars per million tokens."""

    input: float
    output: float
    # Writing a 5-minute cache entry, the only kind the server asks for.
    cache_write: float
    cache_read: float


# What the usage log prices calls with. See architecture/system.md, Usage log.
MODEL_PRICES = {
    "claude-sonnet-5-5": ModelPrice(input=2.00, output=10.00, cache_write=2.50, cache_read=0.20),
    "claude-opus-5-5": ModelPrice(input=4.00, output=20.00, cache_write=5.00, cache_read=0.20),
    "claude-haiku-4-5": ModelPrice(input=1.00, output=5.00, cache_write=1.25, cache_read=0.10),
}
