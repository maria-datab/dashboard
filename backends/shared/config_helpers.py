"""
Shared environment-reading helpers. Both backends import from here.
Usage: from shared.config_helpers import env_bool, env_int, env_str, env_float
"""
import os


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def env_float(name: str, default: float = 0.0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()
