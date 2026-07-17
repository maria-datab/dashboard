IMAGE_TABLE_PROMPT = """You read a photo of a handwritten table, whiteboard list, or isometric box sketch with handwritten dimensions for a Grasshopper compute pipeline.

Extract one row per box variation. Return ONLY JSON matching the reference schema.

Canonical numeric fields (mm, whole integers):
- BoxDepth (150–450 valid; return out-of-range values anyway)
- BoxHeight (600–2600 valid)
- BoxWidth (800–1000 valid)

Reading rules:
- Tables: map columns to BoxDepth, BoxHeight, BoxWidth (aliases: Depth, Height, Width, D, H, W)
- Lists like "300 × 2100 × 900" or "300x2100x900": order is Depth × Height × Width
- Isometric sketches: assign each visible number using drawing geometry:
  1. BoxHeight — number on the vertical dimension line (parallel to the box's vertical edges). Usually the tallest measurement.
  2. BoxDepth — number on the dimension line along the receding top edge (shorter top edge going away — often upper-left in isometric view).
  3. BoxWidth — number on the dimension line along the front top edge (longer top edge facing the viewer — often upper-right).
  If labels say Depth/Height/Width or D/H/W, use those over geometry.
  If assignment is ambiguous, prefer ranges (Depth smallest, Height vertical span, Width front span) but return the numbers you actually read — do not clamp or swap to force valid ranges.
  Multiple boxes on one page → one row per box, top-to-bottom (or left-to-right if side by side).
- Strip units (mm, cm, etc.) and round to integer mm
- Use null for illegible or missing values — do NOT guess or infer from proportions or other values
- One index across all three arrays
- Quantity can be stated in parenthesis as "xQ" where Q is an integer: if not stated, understood as single box

Output shape:
- inputLists: { "BoxDepth": [...], "BoxHeight": [...], "BoxWidth": [...] }
- variationNames: optional labels from the image (e.g. Box 1)

Reference Schema:
{reference_schema}

Return ONLY valid JSON. No markdown, no ```json fences, no preamble. Start with { and end with }."""
