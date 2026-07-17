# Material parse prompt

MATERIAL_PARSE_PROMPT = """
You normalize a user's free-text material answer for CNC DXF export.

Rules:
- Return a single canonical material string as used in CAD metadata (e.g. "3-Schicht", "MDF").
- Match the closest known material when the list is provided.
- Preserve hyphens and casing from known materials when possible.
- Do not add explanation.

User input: {user_text}
Known materials in file (if any): {known_materials}

Return JSON only: { "material": "<canonical string>" }
"""
