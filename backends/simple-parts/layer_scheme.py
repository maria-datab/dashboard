"""Shared DXF layer names for part boundary scheme (Outside / Inside / Bores)."""

import re

LAYER_OUTSIDE = "Outside"
LAYER_INSIDE = "Inside"
LAYER_BORES = "Bores"
LAYER_TEXT = "Text"
GH_OUTPUT_SHEETS = "Sheets"
LAYER_PLATE = "PLATE"

DXF_LAYER_BY_GH_OUTPUT = {
    GH_OUTPUT_SHEETS: LAYER_PLATE,
}

ADMITTED_LAYERS = frozenset({LAYER_OUTSIDE, LAYER_INSIDE, LAYER_BORES})

# Match frontend --color-part-* in styles.css / NESTING_LAYER_COLOR preview.
NESTING_LAYER_RGB = {
    LAYER_OUTSIDE: (255, 0, 0),
    LAYER_INSIDE: (0x17, 0x64, 0x98),
    LAYER_BORES: (0xFF, 0x8C, 0x00),
    LAYER_TEXT: (0x18, 0x85, 0x00),
}

# ACI fallback for BYLAYER entities (dxf-vuer resolves layer colorIndex, not RGB).
NESTING_LAYER_ACI = {
    LAYER_OUTSIDE: 1,
    LAYER_INSIDE: 5,
    LAYER_BORES: 30,
    LAYER_TEXT: 3,
}

SKIP_LAYER_RE = re.compile(r"defpoints|bemassung", re.IGNORECASE)
