"""
Simple-parts backend configuration.

Loads the unified backends/.env (SIMPLE_PARTS_* / shared ANTHROPIC_API_KEY).
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

_BACK_DIR = Path(__file__).resolve().parent
_BACKENDS_ROOT = _BACK_DIR.parent
if str(_BACKENDS_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKENDS_ROOT))

from shared.config_helpers import env_bool, env_float, env_int, env_str  # noqa: E402

load_dotenv(_BACKENDS_ROOT / ".env")

ANTHROPIC_API_KEY = env_str("ANTHROPIC_API_KEY") or None

PORT = env_int("SIMPLE_PARTS_PORT", 5001)
FLASK_HOST = env_str("SIMPLE_PARTS_FLASK_HOST", "127.0.0.1")
FLASK_DEBUG = env_bool("SIMPLE_PARTS_FLASK_DEBUG", True)

SCAN_TARGET_LONG_EDGE = env_int("SIMPLE_PARTS_SCAN_TARGET_LONG_EDGE", 1568)
SCAN_MIN_LONG_EDGE = env_int("SIMPLE_PARTS_SCAN_MIN_LONG_EDGE", 1200)
SCAN_ENHANCE_CONTRAST = env_bool("SIMPLE_PARTS_SCAN_ENHANCE_CONTRAST", True)

RUN_LOCALLY = env_bool("SIMPLE_PARTS_RUN_LOCALLY", True)

if RUN_LOCALLY:
    COMPUTE_BASE_URL = env_str(
        "SIMPLE_PARTS_COMPUTE_BASE_URL_LOCAL", "http://127.0.0.1:5000"
    ).rstrip("/")
    COMPUTE_API_KEY = env_str("SIMPLE_PARTS_COMPUTE_API_KEY_LOCAL", "")
else:
    COMPUTE_BASE_URL = env_str(
        "SIMPLE_PARTS_COMPUTE_BASE_URL_PROD", "http://13.63.222.45"
    ).rstrip("/")
    COMPUTE_API_KEY = env_str("SIMPLE_PARTS_COMPUTE_API_KEY_PROD", "")

COMPUTE_TIMEOUT_SECONDS = env_float("SIMPLE_PARTS_COMPUTE_TIMEOUT_SECONDS", 180.0)

# Directory on the Rhino.Compute host for CSV export when RUN_LOCALLY=false.
# Forward slashes only — GH may treat this as regex on Windows paths.
COMPUTE_CSV_TEMP_BASE = (
    env_str("SIMPLE_PARTS_COMPUTE_CSV_TEMP_BASE", "C:/Temp/simple-parts-nesting")
    .rstrip("/\\")
    .replace("\\", "/")
)


def nest_csv_folder(job_id: str, local_output_dir: Path | str) -> str:
    """CSVFolder param for GH: local job dir, or Compute-side temp per job."""
    if RUN_LOCALLY:
        return Path(local_output_dir).resolve().as_posix()
    job = str(job_id).strip()
    return f"{COMPUTE_CSV_TEMP_BASE}/{job}" if job else COMPUTE_CSV_TEMP_BASE


_definitions_raw = env_str("SIMPLE_PARTS_DEFINITIONS_DIR", "definitions")
_definitions_path = Path(_definitions_raw)
DEFINITIONS_DIR = (
    _definitions_path
    if _definitions_path.is_absolute()
    else _BACK_DIR / _definitions_path
)
DEFAULT_DEFINITION_ID = env_str(
    "SIMPLE_PARTS_DEFAULT_DEFINITION_ID", "simple-parts-summon2d-nesting"
)

SUMMON_FILE_PARAM = "serialized_file"
SUMMON_FILENAME_PARAM = "file_name"
SUMMON_RUN_PARAM = "Run"
SUMMON_GEOMETRY_MODE_PARAM = "GeometryMode"
SUMMON_LAYER_OUTPUTS = ("Outside", "Inside", "Bores", "Text", "Sheets")
SUMMON_2D_VIEWER_CONTENT_OUTPUT = "2DViewerContent"
SUMMON_3D_VIEWER_CONTENT_OUTPUT = "3DViewerContent"
SUMMON_INITIAL_PART_KEYS_OUTPUT = "InitialPartKeys"
SUMMON_POST_INJECTION_NAMES_OUTPUT = "PostInjectionNames"
SUMMON_POST_INJECTION_AMOUNT_OUTPUT = "PostInjectionAmount"
SUMMON_METADATA_OVERRIDES_PARAM = "MetadataOverrides"
SUMMON_CSV_FOLDER_PARAM = "CSVFolder"
SUMMON_CSV_RUN_PARAM = "CSVRun"
SUMMON_ASSIGNED_BREPS_OUTPUT = "AssignedBreps"
SUMMON_UNASSIGNED_BREPS_OUTPUT = "UnassignedBreps"
SUMMON_INPUT_TEXT_OUTPUT = "InputText"
SUMMON_INPUT_TEXT_PT_OUTPUT = "InputTextPt"
SUMMON_UNASSIGNED_REASON_OUTPUT = "UnassignedReason"
SUMMON_UNASSIGNED_ID_OUTPUT = "UnassignedIds"
SUMMON_UNASSIGNED_ID_OUTPUT_FALLBACK = "UnassignedId"
SUMMON_UNASSIGNED_DXF_OUTPUT = "UnassignedDXF"
SUMMON_UNASSIGNED_TEXT_OUTPUT = "UnassignedText"
SUMMON_UNASSIGNED_TEXT_PT_OUTPUT = "UnassignedTextPt"
SUMMON_NESTING_CSV_OUTPUT = "NestingCSV"


def definition_gh_path(definition_id: str | None = None) -> Path:
    definition_id = definition_id or DEFAULT_DEFINITION_ID
    return DEFINITIONS_DIR / f"{definition_id}.gh"
