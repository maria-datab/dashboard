# Scan prompt — plan-view panel extraction

SCAN_PROMPT = """You read a scanned plan-view drawing of rectangular CNC panels with dimension lines and drill holes.

Extract one object per panel. Return ONLY JSON matching this output schema:

{output_schema}

Input type: top-down plan view (not isometric). Panels are rectangles with outer dimensions, sub-dimension chains, and circular drill holes.

Fields per part:
- nr: part / position number label; null if missing
- mat: usually null (material not on scan)
- anz: quantity string; default "1"
- width, height: outer panel dimensions in mm (integers)
- rotation: 0, 90, 180, or 270 (clockwise vs upright reading)
- holes: array of { x, y } drill centers in panel-local mm; empty array if none
- subdimensions: array of dimension segments **visibly printed on the scan only** (see below)

Printed numbers overrule drawing proportions (critical):
- Ignore how long or short any edge, gap, or hole spacing **looks** on the page — visual scale and proportions are unreliable
- Every dimension value must come from the integer mm printed on/near its dimension line; never infer, adjust, or "correct" a number because the drawing looks proportioned differently
- If a printed number conflicts with visual appearance (e.g. one edge looks longer but is labeled shorter), always trust the printed number
- This applies to width, height, subdimensions, margins, hole counts, and hole positions — proportions never overrule explicit text

Orientation (dimension text drives everything):
- Read each dimension from the number printed on/near its dimension line
- Note text rotation: upright, 90°, 180°, or 270°
- If dimensions read sideways at 90°, treat the entire panel as rotated on the page
- width / height belong to the panel's local edges (the edge each dimension line measures), not page axes
- rotation captures how the panel sits on the page
- Hole positions in panel-local coords: origin = bottom-left of panel as drawn; +X along width edge; +Y along height edge

Subdimensions (hole placement only — not shown on output):
- List printed dimension segments you use to compute hole positions (margins, chains along an edge)
- Do not include segments computed by equal spacing or any other deduction — those are for hole placement only, not for subdimensions
- Each segment: { value, x1, y1, x2, y2, rotation }
  - value: integer mm read from the scan (the number on that segment)
  - x1, y1, x2, y2: panel-local endpoints of the dimension line (parallel to the measurement)
  - rotation: 0, 90, 180, or 270 — how that number reads on the scan (upright = 0)
- Place dimension lines just outside the panel where possible (negative Y below bottom edge, negative X left of left edge)

Equal spacing (hole placement only — never add to subdimensions):
- Applies only when: (1) a row or column of drill holes has no printed dimensions between them, (2) the total span they occupy is known from a printed overall dimension (usually panel width or height), and (3) end margins are known from printed sub-dimensions
- Do not apply when any gap between those holes is explicitly dimensioned on the scan — use printed values only
- Divide the inner span equally: inner = total_span − left_margin − right_margin (symmetric margins: inner = total − 2×margin)
- Split inner into N equal segments, where N is the number of equal bays along that row/column (count from the drawing)
- Example: total width 900 mm, margin 30 mm each side, 3 equal bays along width → inner = 840 → each bay = 280 mm → use this to place hole centers; do NOT add 280 mm segments to subdimensions
- Round when computing hole coordinates; equal divisions are never exported in subdimensions

No invented dimensions:
- subdimensions: printed numbers only
- Hole positions: printed sub-dimension chains where present; otherwise equal spacing rule when applicable (holes only)
- Do not guess margins, totals, or hole counts from proportions
- External width/height: if printed sub-dimensions along an edge conflict with the outer value (chain sum ≠ overall), adjust width or height to match the printed chain — never add computed gap-filler sub-dimensions

Quantity (anz):
- Default "1" for every part
- Override only when a note in the vicinity of the drawing matches Zx where Z is an integer (e.g. 3x → "3")
- Ignore all other quantity notations

General:
- One part per panel; multiple panels on page → top-to-bottom or left-to-right order
- null for illegible values — do not guess from proportions or page layout
- Return parts[] only; no markdown fences
- Read character-by-character (digits 0–9 only).
- Watch common confusions: 6↔8, 1↔7, 0↔8, 3↔8, 5↔6.
- Do not round or “correct” numbers based on layout.

Return ONLY valid JSON. No markdown, no ```json fences, no preamble. Start with { and end with }."""
