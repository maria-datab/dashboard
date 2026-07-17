"""
HTTP helpers used by app.py (not routes themselves).

Keeps request parsing and response shaping in one place so route handlers stay short.
"""

from typing import Any

import config


def parse_input_lists(payload: object) -> dict[str, list[float]]:
    """
    Validate POST /solve JSON body.

    Expected shape:
      { "inputLists": { "BoxDepth": [100, 120], "BoxHeight": [...], "BoxWidth": [...] } }

    Each list is one value per CSV row (variation). All CSV columns must have the same length
    (checked later in compute_service when merging for Grasshopper).

    Raises ValueError → app returns 400.
    """
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    input_lists = payload.get("inputLists")
    if not isinstance(input_lists, dict):
        raise ValueError('"inputLists" must be an object')

    parsed: dict[str, list[float]] = {}
    for name, values in input_lists.items():
        if not isinstance(name, str):
            raise ValueError("Input parameter names must be strings")
        if not isinstance(values, list):
            raise ValueError(f'"{name}" must be an array of numbers')
        parsed[name] = [float(value) for value in values]

    return parsed


def parse_quantities(payload: object, row_count: int) -> list[int]:
    raw = payload.get("quantities") if isinstance(payload, dict) else None
    if raw is None:
        return [1] * row_count
    if not isinstance(raw, list):
        raise ValueError('"quantities" must be an array of integers')
    quantities: list[int] = []
    for value in raw:
        try:
            qty = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError('"quantities" must contain integers') from exc
        if qty < 1:
            raise ValueError('"quantities" values must be at least 1')
        quantities.append(qty)
    if len(quantities) < row_count:
        quantities.extend([1] * (row_count - len(quantities)))
    return quantities[:row_count]


def parse_solve_request(
    payload: object,
) -> tuple[dict[str, list[float]], list[int] | None, list[int]]:
    """
    Validate POST /solve JSON body.

    Optional variationIndices: 0-based row indices to compute. When omitted, all rows run.
    An empty array skips per-box compute and runs full-set nesting only.
    Full inputLists are still required (used for full-set nesting).
    Optional quantities: per-row counts (default 1 each).
    """
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    input_lists = parse_input_lists(payload)
    row_count = len(input_lists.get(config.CSV_GH_INPUT_NAMES[0], []))
    quantities = parse_quantities(payload, row_count)

    raw_indices = payload.get("variationIndices")
    if raw_indices is None:
        return input_lists, None, quantities

    if not isinstance(raw_indices, list):
        raise ValueError('"variationIndices" must be an array of integers')

    variation_indices: list[int] = []
    seen: set[int] = set()

    for raw_index in raw_indices:
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise ValueError('"variationIndices" must contain integers') from exc
        if index < 0 or index >= row_count:
            raise ValueError(f"variationIndices contains out-of-range index {index}")
        if index in seen:
            continue
        seen.add(index)
        variation_indices.append(index)

    return input_lists, variation_indices, quantities


def normalize_csv_analyze_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Pad inputLists and variationNames to a single row count (max array length).

    Shorter arrays are padded with None for numeric columns and '' for names so
    the frontend can show missing cells instead of silently misaligning rows.
    """
    input_lists = result.get("inputLists") or {}
    variation_names = result.get("variationNames") or []

    lengths = [len(variation_names)]
    for name in config.CSV_GH_INPUT_NAMES:
        lengths.append(len(input_lists.get(name) or []))
    row_count = max(lengths) if lengths else 0

    def pad(values: list[Any] | None, fill: Any) -> list[Any]:
        padded = list(values or [])
        if len(padded) < row_count:
            padded.extend([fill] * (row_count - len(padded)))
        return padded[:row_count]

    return {
        "inputLists": {
            name: pad(input_lists.get(name), None) for name in config.CSV_GH_INPUT_NAMES
        },
        "variationNames": [f"Box {index + 1}" for index in range(row_count)],
        "variationCount": row_count,
    }


def format_solve_job_response(job: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """
    Turn internal job dict into JSON for GET .../solve/<jobId>.

    The frontend polls this and reads variationResults, completedVariations, etc.
    We only expose geometry + warnings per row (not the full internal job blob).
    """
    stage = spec["stage"]
    by_variation = job.get("stageResults", {}).get(stage, {}).get("byVariation", {})
    variation_results = {
        index: {
            "geometryPayload": entry["geometryPayload"],
            "warnings": entry.get("warnings", []),
        }
        for index, entry in by_variation.items()
    }

    stage_results = job.get("stageResults", {})
    response: dict[str, Any] = {
        "jobId": job["jobId"],
        "definitionId": job.get("definitionId"),
        "status": job["status"],
        "stage": stage,
        "variationCount": job.get("variationCount", 0),
        "currentVariationIndex": job.get("currentVariationIndex"),
        "completedVariations": job.get("completedVariations", []),
        "failedVariations": job.get("failedVariations", {}),
        "variationResults": variation_results,
        "perBoxNesting": stage_results.get("perBoxNesting", {}),
        "fullSetNesting": stage_results.get("fullSetNesting", {}),
        "jobWarnings": job.get("jobWarnings", []),
    }

    if job["status"] == "failed":
        response["error"] = job.get("error")

    return response
