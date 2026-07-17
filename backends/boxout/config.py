"""
Configuration for the Flask backend.

WHAT TO EDIT:
  - `backends/.env` — ports, Rhino.Compute URL, API keys (copy from backends/.env.example).
  - `DEFINITIONS` dict below — register each Grasshopper `.gh` file in `definitions/`.

This module loads the unified backends/.env on import. Other files do `import config`
and read settings from here (do not call load_dotenv elsewhere).
"""

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Folder that contains this file (backends/boxout/)
_BACKEND_DIR = Path(__file__).resolve().parent
_BACKENDS_ROOT = _BACKEND_DIR.parent
if str(_BACKENDS_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKENDS_ROOT))

from shared.config_helpers import env_bool, env_float, env_int, env_str  # noqa: E402

# Unified env at backends/.env
load_dotenv(_BACKENDS_ROOT / ".env")


def _resolve_path(raw: str) -> Path:
    """Turn a path from .env into an absolute Path under boxout when relative."""
    path = Path(raw)
    if not path.is_absolute():
        path = _BACKEND_DIR / path
    return path


# --- Settings from backends/.env (BOXOUT_* / shared) ---

PORT = env_int("BOXOUT_PORT", 5000)
FLASK_DEBUG = env_bool("BOXOUT_FLASK_DEBUG", True)
FLASK_HOST = env_str("BOXOUT_FLASK_HOST", "127.0.0.1")

COMPUTE_BASE_URL = env_str("BOXOUT_COMPUTE_BASE_URL", "http://127.0.0.1:6500")
COMPUTE_API_KEY = env_str("BOXOUT_COMPUTE_API_KEY")
COMPUTE_TIMEOUT_SECONDS = env_float("BOXOUT_COMPUTE_TIMEOUT_SECONDS", 120.0)

DEFINITIONS_DIR = _resolve_path(env_str("BOXOUT_DEFINITIONS_DIR", "definitions"))
DEFAULT_DEFINITION_ID = env_str("BOXOUT_DEFAULT_DEFINITION_ID", "joint-wiz")

PER_BOX_NESTING_DEFINITION_PATH = DEFINITIONS_DIR / "doorBoxOut_PerBox.gh"
MULTIBOX_DEFINITION_PATH = DEFINITIONS_DIR / "doorBoxOut_MultiBox.gh"
MULTIBOX_NESTED_DEFINITION_PATH = DEFINITIONS_DIR / "doorBoxOut_MultiBox_Nested.gh"

ANTHROPIC_API_KEY = env_str("ANTHROPIC_API_KEY")

# Parameter names that come from the CSV upload (not from Grasshopper defaults)
CSV_GH_INPUT_NAMES = ("BoxDepth", "BoxHeight", "BoxWidth")

# --- Grasshopper definitions registry ---
#
# Each key is the URL segment: /definitions/<key>/solve
#
# Fields per entry:
#   label    — human name for docs/UI
#   gh_file  — filename inside definitions/
#   stage    — stored in job results (e.g. "joined"); used in API responses
#   enabled  — if False, POST solve returns 501 until you set True
#
DEFINITIONS: dict[str, dict[str, Any]] = {
    "joint-wiz": {
        "label": "JointWiz",
        "gh_file": "doorBoxOut_PerBox.gh",
        "stage": "joined",
        "enabled": True,
    },
}


class DefinitionNotFoundError(KeyError):
    """URL used an id that is not in DEFINITIONS."""


class DefinitionNotEnabledError(RuntimeError):
    """Solve was requested on a definition with enabled: False."""


def get_definition(definition_id: str) -> dict[str, Any]:
    """Look up one definition; raises DefinitionNotFoundError if missing."""
    entry = DEFINITIONS.get(definition_id)
    if entry is None:
        raise DefinitionNotFoundError(definition_id)
    return {"id": definition_id, **entry}


def list_definition_ids() -> list[str]:
    """All registered definition ids (order matches DEFINITIONS dict)."""
    return list(DEFINITIONS.keys())


def definition_gh_path(definition_id: str) -> Path:
    """Full path to the .gh file on disk for this definition."""
    spec = get_definition(definition_id)
    return DEFINITIONS_DIR / spec["gh_file"]


def require_definition_enabled(spec: dict[str, Any]) -> None:
    """Block solve until you set enabled: True in DEFINITIONS."""
    if not spec.get("enabled", True):
        raise DefinitionNotEnabledError(
            f'Definition "{spec["id"]}" is registered but not enabled yet'
        )


def definition_public_dict(definition_id: str) -> dict[str, Any]:
    """JSON-friendly summary for GET /definitions and /health."""
    spec = get_definition(definition_id)
    path = definition_gh_path(definition_id)
    return {
        "id": spec["id"],
        "label": spec["label"],
        "stage": spec["stage"],
        "ghFile": spec["gh_file"],
        "enabled": spec.get("enabled", True),
        "definitionFound": path.is_file(),
        "routes": {
            "definitionDefaults": f"/definitions/{spec['id']}/definition-defaults",
            "solve": f"/definitions/{spec['id']}/solve",
            "solveStatus": f"/definitions/{spec['id']}/solve/<jobId>",
        },
    }
