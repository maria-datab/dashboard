"""Metadata override parsing and post-GH reinsertion helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

META_FIELDS = ("nr", "mat", "anz")
FIELD_ALIASES = {
    "nr": ("nr", "Nr"),
    "mat": ("mat", "Mat"),
    "anz": ("anz", "Anz"),
}


def _trim(value: Any) -> str:
    return str(value or "").strip()


def _read_override_field(entry: dict[str, Any], field: str) -> str:
    for alias in FIELD_ALIASES[field]:
        if alias not in entry or entry[alias] is None:
            continue
        text = _trim(entry[alias])
        if text:
            return text
    return ""


def normalize_metadata_overrides(data: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    if not isinstance(data, dict):
        return {}

    result: dict[str, dict[str, str]] = {}
    for key, value in data.items():
        part_key = _trim(key)
        if not part_key or not isinstance(value, dict):
            continue
        entry: dict[str, str] = {}
        for field in META_FIELDS:
            text = _read_override_field(value, field)
            if text:
                entry[field] = text
        if entry:
            result[part_key] = entry
    return result


def parse_metadata_overrides_json(raw: str | None) -> dict[str, dict[str, str]]:
    if raw is None or not str(raw).strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("metadataOverrides must be a JSON object")
    return normalize_metadata_overrides(data)


def merge_post_injection_with_overrides(
    initial_part_keys: list[str] | None,
    post_injection_names: list[str] | None,
    post_injection_amount: list[str] | None,
    metadata_overrides: dict[str, dict[str, str]] | None,
) -> tuple[list[str] | None, list[str] | None]:
    """Apply override map to GH PostInjection lists by InitialPartKeys index."""
    if not initial_part_keys or not metadata_overrides:
        return post_injection_names, post_injection_amount

    names = list(post_injection_names or [])
    amounts = list(post_injection_amount or [])
    changed = False

    for index, raw_key in enumerate(initial_part_keys):
        part_key = _trim(raw_key)
        if not part_key:
            continue
        override = metadata_overrides.get(part_key)
        if not override:
            continue

        if override.get("nr") is not None:
            while len(names) <= index:
                names.append("")
            names[index] = override["nr"]
            changed = True

        if override.get("anz") is not None:
            while len(amounts) <= index:
                amounts.append("")
            amounts[index] = override["anz"]
            changed = True

    if not changed:
        return post_injection_names, post_injection_amount
    return names or None, amounts or None


def apply_label_overrides_to_nesting_dxf(
    dxf_path: str,
    *,
    original_names: list[str] | None,
    merged_names: list[str] | None,
) -> None:
    """Replace Text-layer labels when GH did not apply MetadataOverrides."""
    if not original_names or not merged_names:
        return

    replacements: dict[str, str] = {}
    for old_name, new_name in zip(original_names, merged_names):
        old_text = _trim(old_name)
        new_text = _trim(new_name)
        if old_text and new_text and old_text != new_text:
            replacements[old_text] = new_text

    if not replacements:
        return

    import ezdxf

    doc = ezdxf.readfile(dxf_path)
    updated = False
    for entity in doc.modelspace():
        if entity.dxftype() == "TEXT":
            current = _trim(entity.dxf.text)
            replacement = replacements.get(current)
            if replacement:
                entity.dxf.text = replacement
                updated = True
        elif entity.dxftype() == "MTEXT":
            current = _trim(entity.text)
            replacement = replacements.get(current)
            if replacement:
                entity.text = replacement
                updated = True

    if updated:
        doc.saveas(dxf_path)


def write_metadata_overrides_sidecar(
    folder: str | None,
    metadata_overrides: dict[str, dict[str, str]] | None,
) -> None:
    """Persist overrides beside CSV export output for GH file-based readers."""
    if not folder or not metadata_overrides:
        return
    target = Path(folder) / "metadata_overrides.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(metadata_overrides, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
