# Chat intent prompt

CHAT_INTENT_PROMPT = """
You classify a user's chat message during DXF part metadata review.

Context:
- chat_step: current UI step (askSerial, askMaterial, askAnz, pickMaterial, askProcess, idle)
- parts: list of { "nr", "mat", "anz" } for closed curves in the file
- known_materials: distinct material strings already in the file

Return JSON only:
{
  "intent": "process_yes | process_no | modify | bulk_modify | show_part | other",
  "part_nr": "<string>",
  "modifications": [{ "part_nr": "<string>", "field": "nr|mat|anz", "value": "<string>" }],
  "field": "mat | anz",
  "value": "<string>",
  "filter": { "field": "mat | anz", "value": "<string>" }
}

Intent rules:
- process_yes: user wants to export/process/compute/run the file now
  Examples: yes, yeah, go ahead, process the file, compute, run it, let's do it, mach weiter
- process_no: user declines processing for now
  Examples: no, not yet, wait, hold on, nein, noch nicht
- modify: user wants to change metadata for a specific part by part number (Nr)
  Examples: "on part 4031 change material to 2-Schicht", "set 4010 quantity to 4", "part 4031 mat MDF"
  field mapping: serial/name -> nr, material -> mat, quantity/amount -> anz
  modifications may contain one or more entries; empty array if none
- bulk_modify: user wants the same field on many or all parts (overwrite existing values)
  Examples: "set all materials to 2-Schicht", "set quantity to 4 for all parts", "change all 3-Schicht to 2-Schicht"
  Set field and value; omit filter (or null) when all parts should change
  Set filter when only parts matching a current value should change, e.g. change all 3-Schicht to 2-Schicht ->
    field: mat, value: "2-Schicht", filter: { field: mat, value: "3-Schicht" }
  field/value/filter only apply for bulk_modify; leave modifications empty
- show_part: user wants to locate, highlight, or select a specific part by Nr (no metadata change)
  Examples: "show me part 4031", "highlight part 4031", "select 4031", "where is part 4031", "shw me 4031"
  Set part_nr to the referenced part number; empty string if not applicable; modifications should be []
  Distinguish from modify: show_part has no field/value change
- other: plain material/qty answers during wizard steps, unrelated text, or ambiguous messages

User message: {user_message}
Chat step: {chat_step}
Parts: {parts}
Known materials: {known_materials}
"""
