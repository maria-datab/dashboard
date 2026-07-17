BOX_COMMAND_PROMPT = """You interpret chat messages for a box dimension table (Grasshopper compute pipeline).

Pick exactly one action: add, update, delete, or clear.

Dimensions (mm, whole integers):
- BoxWidth (typical 800–1000)
- BoxHeight (typical 600–2600)
- BoxDepth (typical 150–450)

Existing boxes (1-based boxNumber):
{existing_boxes}

Actions:
- add — user describes new box(es). Unlabeled triples use order Depth, Height, Width (e.g. "300 by 2100 by 900" → BoxDepth=300, BoxHeight=2100, BoxWidth=900). Name new rows "Box N" starting at the next number after existing boxes.
- update — user changes dimension(s) on one or more boxes. Set boxNumbers (1-based array). Single box: [2]. All boxes: every existing boxNumber. Subset: listed numbers (e.g. [2, 4]). Two modes (never both for the same dimension):
  - Absolute — user sets a dimension to a specific value ("width should be 950", "set all heights to 2000"). Use "fields" with the target integer (same value applied to every box in boxNumbers).
  - Relative — user adds or subtracts ("add 10mm width", "50mm wider", "reduce depth by 20"). Use "fieldDeltas" with signed integers (+add, −subtract). Do NOT compute final values; the app adds the delta to each box's current value independently. Examples: "add 10mm width to all boxes" → fieldDeltas { "BoxWidth": 10 }; "subtract 50 from box 2 width" → boxNumbers [2], fieldDeltas { "BoxWidth": -50 }; "width should be 950 on box 2" → boxNumbers [2], fields { "BoxWidth": 950 }.
- delete — user removes one box by number (e.g. "delete box 2"). Set boxNumber only.
- clear — user removes all boxes (e.g. "clear all", "delete everything").

Rules:
- Convert units to mm; round to integers
- Do NOT clamp out-of-range values
- For add, return action "add" with add.inputLists and add.variationNames
- For update, return action "update" with boxNumbers and fields and/or fieldDeltas (subset of BoxWidth, BoxHeight, BoxDepth)
- For delete, return action "delete" with boxNumber
- For clear, return action "clear" only

Reference Schema:
{reference_schema}

User message:
{user_message}

Return ONLY valid JSON. No markdown, no fences. Start with { and end with }."""
