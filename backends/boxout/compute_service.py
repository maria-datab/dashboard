# Runs Grasshopper definitions via Rhino Compute — one variation at a time

import base64
import json
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib import error, request

import config

# Grasshopper path for a single value (not a list)
GH_SCALAR_PATH = "{0}"


class ComputeServiceError(RuntimeError):
    """Rhino.Compute failure or bad GH response — becomes HTTP 500 in app.py."""


class ComputeService:
    """
    One instance per Flask app.

    Holds:
      - connection settings (Compute URL, API key, timeout)
      - _jobs: all active/finished tickets in RAM
      - _lock: thread-safe access to _jobs
    """

    def __init__(
        self,
        compute_base_url: str,
        compute_api_key: str,
        joined_definition_path: Path,
        multibox_definition_path: Path,
        multibox_nested_definition_path: Path,
        per_box_nesting_definition_path: Path,
        request_timeout_seconds: float = 120.0,
    ) -> None:
        self.compute_base_url = compute_base_url.rstrip("/")
        self.compute_api_key = compute_api_key
        self.joined_definition_path = joined_definition_path
        self.multibox_definition_path = multibox_definition_path
        self.multibox_nested_definition_path = multibox_nested_definition_path
        self.per_box_nesting_definition_path = per_box_nesting_definition_path
        self.request_timeout_seconds = request_timeout_seconds
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def healthcheck(self) -> dict[str, Any]:
        """Metadata for GET /health: Compute URL + each definition file status."""
        definitions = []
        for definition_id in config.list_definition_ids():
            path = config.definition_gh_path(definition_id)
            definitions.append(
                {
                    **config.definition_public_dict(definition_id),
                    "path": str(path),
                }
            )
        return {
            "computeBaseUrl": self.compute_base_url,
            "definitionsDir": str(config.DEFINITIONS_DIR),
            "defaultDefinitionId": config.DEFAULT_DEFINITION_ID,
            "definitions": definitions,
        }

    def get_definition_default_params(self, definition_id: str) -> list[dict[str, Any]]:
        definition_path = config.definition_gh_path(definition_id)
        if not definition_path.is_file():
            raise ComputeServiceError(f"Definition not found at {definition_path}")

        definition_bytes = definition_path.read_bytes()
        defaults = self._fetch_definition_defaults(definition_bytes)
        csv_names = set(config.CSV_GH_INPUT_NAMES)

        return [
            {"name": name, "value": leaf["data"]}
            for name, leaf in sorted(defaults.items())
            if name not in csv_names
        ]

    def start_job(
        self,
        definition_id: str,
        input_lists: dict[str, list[float]],
        variation_indices: list[int] | None = None,
        quantities: list[int] | None = None,
    ) -> str:
        spec = self._get_definition(definition_id)
        config.require_definition_enabled(spec)

        variation_count = len(input_lists.get(config.CSV_GH_INPUT_NAMES[0], []))
        if quantities is None:
            quantities = [1] * variation_count
        job_id = str(uuid.uuid4())
        job = {
            "jobId": job_id,
            "definitionId": definition_id,
            "status": "running",
            "latestStage": spec["stage"],
            "variationCount": variation_count,
            "currentVariationIndex": None,
            "completedVariations": [],
            "failedVariations": {},
            "stageResults": {
                spec["stage"]: {"byVariation": {}},
                "perBoxNesting": {
                    "byVariation": {},
                    "kSheetNr": None,
                    "fSheetNr": None,
                },
                "fullSetNesting": {
                    "kSheetNr": None,
                    "fSheetNr": None,
                    "geometryPayload": None,
                },
            },
            "jobWarnings": [],
            "inputLists": input_lists,
            "quantities": quantities,
            "variationIndices": variation_indices,
            "error": None,
            "createdAt": time.time(),
            "updatedAt": time.time(),
        }
        with self._lock:
            self._jobs[job_id] = job

        worker = threading.Thread(
            target=self._run_sequential_job,
            args=(job_id, definition_id),
            daemon=True,
        )
        worker.start()
        return job_id

    def get_job(
        self, job_id: str, definition_id: str | None = None
    ) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if definition_id is not None and job.get("definitionId") != definition_id:
                return None
            return deepcopy(job)

    def _run_sequential_job(self, job_id: str, definition_id: str) -> None:
        """
        Run Grasshopper once per CSV row, in order (0, 1, 2, ...).

        For joint-wiz, also runs per-box nesting per row and full-set nesting once
        at the end. Updates the ticket after each row so polls can show progress.
        """
        spec = self._get_definition(definition_id)
        stage = spec["stage"]
        csv_names = config.CSV_GH_INPUT_NAMES

        try:
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                input_lists = deepcopy(job["inputLists"])
                quantities = list(job.get("quantities") or [])

            variation_count = len(input_lists.get(csv_names[0], []))
            if variation_count == 0:
                raise ComputeServiceError("CSV must provide at least one variation")
            if len(quantities) < variation_count:
                quantities.extend([1] * (variation_count - len(quantities)))
            quantities = quantities[:variation_count]

            with self._lock:
                requested_indices = self._jobs[job_id].get("variationIndices")

            if requested_indices is None:
                indices_to_run = list(range(variation_count))
            else:
                indices_to_run = list(requested_indices)

            for variation_index in indices_to_run:
                with self._lock:
                    job = self._jobs.get(job_id)
                    if not job:
                        return
                    job["currentVariationIndex"] = variation_index
                    job["updatedAt"] = time.time()

                row_lists = self._input_lists_for_variation(
                    input_lists, variation_index, csv_names
                )
                try:
                    per_box_same_as_joined = (
                        self.joined_definition_path.resolve()
                        == self.per_box_nesting_definition_path.resolve()
                    )
                    joined_payload = self._solve_definition(
                        self.joined_definition_path,
                        row_lists,
                        csv_names,
                    )
                    self._set_variation_result(
                        job_id, variation_index, joined_payload, stage
                    )

                    nesting_payload = (
                        joined_payload
                        if per_box_same_as_joined
                        else self._solve_definition(
                            self.per_box_nesting_definition_path,
                            row_lists,
                            csv_names,
                        )
                    )
                    k = self._extract_output_scalar(nesting_payload, "K_SheetNr")
                    f = self._extract_output_scalar(nesting_payload, "F_SheetNr")
                    with self._lock:
                        job = self._jobs.get(job_id)
                        if not job:
                            return
                        by_var = job["stageResults"]["perBoxNesting"]["byVariation"]
                        by_var[str(variation_index)] = {"kSheetNr": k, "fSheetNr": f}
                        k_total, f_total = self._weighted_per_box_nesting_totals(
                            by_var, quantities
                        )
                        job["stageResults"]["perBoxNesting"]["kSheetNr"] = k_total
                        job["stageResults"]["perBoxNesting"]["fSheetNr"] = f_total
                        job["updatedAt"] = time.time()
                except Exception as exc:  # noqa: BLE001
                    with self._lock:
                        job = self._jobs.get(job_id)
                        if not job:
                            return
                        job["failedVariations"][str(variation_index)] = str(exc)
                        job["updatedAt"] = time.time()

            self._run_full_set_nesting(job_id, input_lists, quantities)

            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job["status"] = "completed"
                job["currentVariationIndex"] = None
                job["latestStage"] = f"{stage}_ready"
                job["updatedAt"] = time.time()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job["status"] = "failed"
                job["latestStage"] = "failed"
                job["error"] = str(exc)
                job["currentVariationIndex"] = None
                job["updatedAt"] = time.time()

    def _run_full_set_nesting(
        self,
        job_id: str,
        input_lists: dict[str, list[float]],
        quantities: list[int],
    ) -> None:
        expanded = self._expand_input_lists_by_quantity(
            input_lists, quantities, config.CSV_GH_INPUT_NAMES
        )
        csv_names = config.CSV_GH_INPUT_NAMES
        count_payload = self._solve_definition(
            self.multibox_definition_path, expanded, csv_names
        )
        preview_payload = self._solve_definition(
            self.multibox_nested_definition_path, expanded, csv_names
        )
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            full_set = job["stageResults"]["fullSetNesting"]
            full_set["kSheetNr"] = self._extract_output_scalar(count_payload, "K_SheetNr")
            full_set["fSheetNr"] = self._extract_output_scalar(count_payload, "F_SheetNr")
            full_set["geometryPayload"] = preview_payload
            job["updatedAt"] = time.time()

    @staticmethod
    def _expand_input_lists_by_quantity(
        input_lists: dict[str, list[float]],
        quantities: list[int],
        csv_input_names: tuple[str, ...],
    ) -> dict[str, list[float]]:
        expanded = {name: [] for name in csv_input_names}
        row_count = len(input_lists.get(csv_input_names[0], []))
        for index in range(row_count):
            qty = quantities[index] if index < len(quantities) else 1
            if qty < 1:
                qty = 1
            for _ in range(qty):
                for name in csv_input_names:
                    expanded[name].append(input_lists[name][index])
        return expanded

    @staticmethod
    def _weighted_per_box_nesting_totals(
        by_variation: dict[str, dict[str, int | None]],
        quantities: list[int],
    ) -> tuple[int, int]:
        k_total = 0
        f_total = 0
        for index_str, entry in by_variation.items():
            qty = quantities[int(index_str)] if int(index_str) < len(quantities) else 1
            k_total += (entry.get("kSheetNr") or 0) * qty
            f_total += (entry.get("fSheetNr") or 0) * qty
        return k_total, f_total

    @staticmethod
    def _input_lists_for_variation(
        input_lists: dict[str, list[float]],
        variation_index: int,
        csv_input_names: tuple[str, ...],
    ) -> dict[str, list[float]]:
        return {
            name: [input_lists[name][variation_index]]
            for name in csv_input_names
        }

    def _set_variation_result(
        self,
        job_id: str,
        variation_index: int,
        payload: dict[str, Any],
        stage: str,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            by_variation = job["stageResults"][stage]["byVariation"]
            by_variation[str(variation_index)] = {
                "geometryPayload": payload,
                "warnings": payload.get("warnings", []),
            }
            if variation_index not in job["completedVariations"]:
                job["completedVariations"].append(variation_index)
            job["updatedAt"] = time.time()

    def _solve_definition(
        self,
        definition_path: Path,
        input_lists: dict[str, list[float]],
        csv_input_names: tuple[str, ...],
    ) -> dict[str, Any]:
        definition_bytes = definition_path.read_bytes()
        definition_defaults = self._fetch_definition_defaults(definition_bytes)
        merged = self._merge_gh_input_lists(
            input_lists, definition_defaults, csv_input_names
        )
        values = self._build_input_trees(merged)
        response_data = self._compute_post(
            "/grasshopper",
            {"algo": self._bytes_to_base64(definition_bytes), "pointer": None, "values": values},
        )
        return self._finalize_solve_response(response_data)

    def _fetch_definition_defaults(self, definition: bytes) -> dict[str, dict[str, Any]]:
        io_payload = self._compute_post("/io", {"algo": self._bytes_to_base64(definition)})
        defaults: dict[str, dict[str, Any]] = {}

        for input_item in io_payload.get("Inputs", []):
            inner_tree = ((input_item.get("Default") or {}).get("InnerTree")) or {}
            leaf = self._first_default_leaf(inner_tree)
            if leaf is None:
                continue
            defaults[input_item["Name"]] = leaf

        if not defaults:
            raise ComputeServiceError("Could not read Hops default values from definition /io")
        return defaults

    @staticmethod
    def _is_geometry_leaf(leaf: dict[str, Any]) -> bool:
        leaf_type = str(leaf.get("type") or "")
        if "Geometry" in leaf_type:
            return True

        raw_value = leaf.get("data")
        if isinstance(raw_value, dict):
            return "archive3dm" in raw_value or "opennurbs" in raw_value

        if isinstance(raw_value, str):
            stripped = raw_value.strip()
            return stripped.startswith("{") and (
                "archive3dm" in stripped or "opennurbs" in stripped
            )

        return False

    @staticmethod
    def _parse_numeric_scalar(raw_value: Any) -> int:
        return int(round(float(raw_value)))

    @staticmethod
    def _extract_output_scalar(payload: dict[str, Any], param_name: str) -> int | None:
        for output in payload.get("values") or payload.get("Values") or []:
            if output.get("ParamName") != param_name:
                continue
            inner_tree = output.get("InnerTree") or {}
            for branch in inner_tree.values():
                for leaf in branch:
                    if ComputeService._is_geometry_leaf(leaf):
                        continue
                    try:
                        return ComputeService._parse_numeric_scalar(leaf.get("data"))
                    except (TypeError, ValueError):
                        continue
        return None

    @staticmethod
    def _normalize_default_leaf(raw_leaf: dict[str, Any]) -> dict[str, Any]:
        if ComputeService._is_geometry_leaf(raw_leaf):
            return {
                "type": raw_leaf.get("type") or "Rhino.Geometry.CommonObject",
                "data": raw_leaf.get("data"),
            }

        leaf_type = raw_leaf.get("type") or "System.Int32"
        raw_value = raw_leaf.get("data")

        if leaf_type.endswith("Boolean") or isinstance(raw_value, bool):
            if isinstance(raw_value, bool):
                data = raw_value
            else:
                data = str(raw_value).strip().lower() in ("1", "true", "yes", "on")
            return {"type": "System.Boolean", "data": data}

        if isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in ("true", "false"):
                return {"type": "System.Boolean", "data": lowered == "true"}

        parsed = ComputeService._parse_numeric_scalar(raw_value)
        return {"type": leaf_type, "data": parsed}

    def _first_default_leaf(self, inner_tree: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
        for branch in inner_tree.values():
            if not branch:
                continue
            return self._normalize_default_leaf(branch[0])
        return None

    def _merge_gh_input_lists(
        self,
        csv_lists: dict[str, list[float]],
        defaults: dict[str, dict[str, Any]],
        csv_input_names: tuple[str, ...],
    ) -> dict[str, list[dict[str, Any]]]:
        merged: dict[str, list[dict[str, Any]]] = {}
        csv_names = set(csv_input_names)

        for name, leaf in defaults.items():
            if name in csv_names:
                continue
            merged[name] = [leaf]

        lengths = [len(csv_lists.get(name, [])) for name in csv_input_names]
        count = lengths[0] if lengths else 0
        if count == 0:
            raise ComputeServiceError("CSV must provide at least one variation")
        if any(length != count for length in lengths):
            details = ", ".join(
                f"{name}={len(csv_lists.get(name, []))}" for name in csv_input_names
            )
            raise ComputeServiceError(f"CSV lists must align: {details}")

        for name in csv_input_names:
            merged[name] = [
                {"type": "System.Int32", "data": int(round(float(value)))}
                for value in csv_lists.get(name, [])
            ]

        return merged

    def _build_input_trees(
        self, merged_inputs: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "ParamName": name,
                "InnerTree": {GH_SCALAR_PATH: leaves},
            }
            for name, leaves in merged_inputs.items()
        ]

    def _compute_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        endpoint = f"{self.compute_base_url}{path if path.startswith('/') else f'/{path}'}"
        req = request.Request(
            endpoint,
            data=body,
            headers=self._compute_headers(),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            parsed = self._parse_grasshopper_response(detail)
            if parsed is not None:
                return parsed
            raise ComputeServiceError(
                f"Compute call failed {exc.code} on {path}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise ComputeServiceError(f"Compute call failed on {path}: {exc.reason}") from exc

    @staticmethod
    def _parse_grasshopper_response(raw_body: str) -> dict[str, Any] | None:
        if not raw_body.strip():
            return None
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        if "values" in parsed or "Values" in parsed:
            return parsed
        return None

    @staticmethod
    def _finalize_solve_response(response_data: dict[str, Any]) -> dict[str, Any]:
        values = response_data.get("values") or response_data.get("Values") or []
        errors = response_data.get("errors") or response_data.get("Errors") or []
        if not errors:
            return response_data
        if values:
            warnings = list(response_data.get("warnings") or response_data.get("Warnings") or [])
            warnings.extend(str(message) for message in errors)
            response_data["warnings"] = warnings
            response_data.pop("errors", None)
            response_data.pop("Errors", None)
            return response_data
        raise ComputeServiceError("; ".join(str(message) for message in errors))

    def _compute_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.compute_api_key:
            headers["RhinoComputeKey"] = self.compute_api_key
        return headers

    @staticmethod
    def _bytes_to_base64(payload: bytes) -> str:
        return base64.b64encode(payload).decode("ascii")

    def _get_definition(self, definition_id: str) -> dict[str, Any]:
        try:
            return config.get_definition(definition_id)
        except config.DefinitionNotFoundError as exc:
            raise ComputeServiceError(f'Unknown definition "{definition_id}"') from exc


def create_service() -> ComputeService:
    """Build service from config.py / .env settings."""
    return ComputeService(
        compute_base_url=config.COMPUTE_BASE_URL,
        compute_api_key=config.COMPUTE_API_KEY,
        joined_definition_path=config.definition_gh_path("joint-wiz"),
        multibox_definition_path=config.MULTIBOX_DEFINITION_PATH,
        multibox_nested_definition_path=config.MULTIBOX_NESTED_DEFINITION_PATH,
        per_box_nesting_definition_path=config.PER_BOX_NESTING_DEFINITION_PATH,
        request_timeout_seconds=config.COMPUTE_TIMEOUT_SECONDS,
    )
