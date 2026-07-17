# Rhino.Compute client for simple-parts-summon2d-nesting (flatten, nest, merge to 2D DXF).

import json
import re
import threading
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from urllib import error, request

import config
from dxf_serializer import encode_file_to_base64, merge_summoned_layer_dxfs
from metadata_overrides import write_metadata_overrides_sidecar

_GRASSHOPPER_CALL_LOCK = threading.Lock()

GH_SCALAR_PATH = "{0}"


def _normalize_csv_folder(csv_folder: str | None) -> str:
    """Forward slashes only — GH treats CSVFolder as regex on Windows paths."""
    if not csv_folder or not str(csv_folder).strip():
        return ""
    return Path(str(csv_folder)).as_posix()


class ComputeServiceError(RuntimeError):
    """Rhino.Compute failure or bad GH response — becomes HTTP 500 in app.py."""


class ComputeService:
    def __init__(
        self,
        compute_base_url: str,
        compute_api_key: str,
        definition_path: Path,
        request_timeout_seconds: float = 120.0,
    ) -> None:
        self.compute_base_url = compute_base_url.rstrip("/")
        self.compute_api_key = compute_api_key
        self.definition_path = definition_path
        self.request_timeout_seconds = request_timeout_seconds

    def solve_summon2d(
        self,
        file_path: str,
        filename: str | None = None,
        *,
        run_nesting: bool = True,
        geometry_mode: int = 0,
    ) -> dict[str, str]:
        """Send base64 CAD file to GH; return per-layer base64 flat DXFs."""
        response_data = self._solve_summon2d_response(
            file_path,
            filename=filename,
            run_nesting=run_nesting,
            geometry_mode=geometry_mode,
        )
        return self._extract_layer_outputs(response_data)

    def solve_summon2d_with_meshes3d(
        self,
        file_path: str,
        filename: str | None = None,
        *,
        run_nesting: bool = True,
        geometry_mode: int = 0,
        sheet_width: int | None = None,
        sheet_height: int | None = None,
        sheet_thickness: int | None = None,
        metadata_overrides: dict[str, Any] | None = None,
        csv_folder: str | None = None,
    ) -> tuple[
        list[dict[str, str]],
        list[dict[str, Any]] | None,
        list[str] | None,
        list[dict[str, Any]] | None,
        dict[str, list[str]],
        list[dict[str, Any]] | None,
        str | None,
        list[str] | None,
        list[dict[str, Any]] | None,
        str | None,
        list[str] | None,
        list[str] | None,
        list[str] | None,
    ]:
        """Run summon2d once; return layers, meshes, text, CSV, and part association lists."""
        response_data = self._solve_summon2d_response(
            file_path,
            filename=filename,
            run_nesting=run_nesting,
            geometry_mode=geometry_mode,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            sheet_thickness=sheet_thickness,
            metadata_overrides=metadata_overrides,
            csv_folder=csv_folder,
        )
        return (
            self._extract_layer_outputs_by_branch(response_data),
            self._extract_meshes_3d(
                response_data, param_name=config.SUMMON_ASSIGNED_BREPS_OUTPUT
            ),
            self._extract_string_leaves(
                response_data, config.SUMMON_INPUT_TEXT_OUTPUT
            ),
            self._extract_point_leaves(
                response_data, config.SUMMON_INPUT_TEXT_PT_OUTPUT
            ),
            self._extract_unassigned(response_data),
            self._extract_meshes_3d(
                response_data, param_name=config.SUMMON_UNASSIGNED_BREPS_OUTPUT
            ),
            self._try_extract_output_text(
                response_data, config.SUMMON_UNASSIGNED_DXF_OUTPUT
            ),
            self._extract_string_leaves(
                response_data, config.SUMMON_UNASSIGNED_TEXT_OUTPUT
            ),
            self._extract_point_leaves(
                response_data, config.SUMMON_UNASSIGNED_TEXT_PT_OUTPUT
            ),
            self._extract_nesting_csv_static(response_data),
            self._extract_initial_part_keys(response_data),
            *self._extract_post_injection_metadata(response_data),
        )

    def solve_preview_only(
        self,
        file_path: str,
        filename: str | None = None,
        *,
        geometry_mode: int = 0,
    ) -> dict[str, Any]:
        """Run GH with Run=false; return preview mesh JSON from 2D or 3D viewer content."""
        response_data = self._solve_summon2d_response(
            file_path,
            filename=filename,
            run_nesting=False,
            geometry_mode=geometry_mode,
        )
        param_name = (
            config.SUMMON_3D_VIEWER_CONTENT_OUTPUT
            if geometry_mode == 1
            else config.SUMMON_2D_VIEWER_CONTENT_OUTPUT
        )
        meshes3d, initial_part_keys, input_text, input_text_pt = self._extract_mesh_preview(
            response_data, param_name
        )
        post_injection_names, post_injection_amount = self._extract_post_injection_metadata(
            response_data
        )
        return {
            "meshes3d": meshes3d,
            "initialPartKeys": initial_part_keys,
            "postInjectionNames": post_injection_names,
            "postInjectionAmount": post_injection_amount,
            "inputText": input_text,
            "inputTextPt": input_text_pt,
        }

    def solve_meshes3d_only(
        self, file_path: str, filename: str | None = None, *, geometry_mode: int = 1
    ) -> list[dict[str, Any]] | None:
        """Run GH with Run=false; return preview mesh JSON for the given geometry mode."""
        result = self.solve_preview_only(
            file_path, filename=filename, geometry_mode=geometry_mode
        )
        meshes3d = result.get("meshes3d")
        return meshes3d if isinstance(meshes3d, list) else None

    def _extract_preview_input_text(
        self, response_data: dict[str, Any]
    ) -> tuple[list[str] | None, list[dict[str, Any]] | None]:
        input_text = self._extract_string_leaves(
            response_data, config.SUMMON_INPUT_TEXT_OUTPUT
        )
        input_text_pt = self._extract_point_leaves(
            response_data, config.SUMMON_INPUT_TEXT_PT_OUTPUT
        )
        return input_text, input_text_pt

    def _extract_initial_part_keys(
        self, response_data: dict[str, Any]
    ) -> list[str] | None:
        return self._extract_string_leaves(
            response_data, config.SUMMON_INITIAL_PART_KEYS_OUTPUT
        )

    def _extract_post_injection_metadata(
        self, response_data: dict[str, Any]
    ) -> tuple[list[str] | None, list[str] | None]:
        """Parallel to InitialPartKeys — associated name (nr) and amount (anz) per part."""
        names = self._extract_string_leaves(
            response_data, config.SUMMON_POST_INJECTION_NAMES_OUTPUT
        )
        amounts = self._extract_string_leaves(
            response_data, config.SUMMON_POST_INJECTION_AMOUNT_OUTPUT
        )
        return names, amounts

    def _extract_mesh_preview(
        self,
        response_data: dict[str, Any],
        param_name: str,
    ) -> tuple[
        list[dict[str, Any]] | None,
        list[str] | None,
        list[str] | None,
        list[dict[str, Any]] | None,
    ]:
        meshes3d = self._extract_meshes_3d(response_data, param_name=param_name)
        initial_part_keys = self._extract_initial_part_keys(response_data)
        input_text, input_text_pt = self._extract_preview_input_text(response_data)
        return meshes3d, initial_part_keys, input_text, input_text_pt

    def _solve_summon2d_response(
        self,
        file_path: str,
        filename: str | None = None,
        *,
        run_nesting: bool = True,
        geometry_mode: int = 0,
        sheet_width: int | None = None,
        sheet_height: int | None = None,
        sheet_thickness: int | None = None,
        metadata_overrides: dict[str, Any] | None = None,
        csv_folder: str | None = None,
    ) -> dict[str, Any]:
        if not self.definition_path.is_file():
            raise ComputeServiceError(f"Definition not found at {self.definition_path}")

        csv_folder = _normalize_csv_folder(csv_folder)
        serialized = encode_file_to_base64(file_path)
        filename = filename or Path(file_path).name
        values = [
            {
                "ParamName": config.SUMMON_FILE_PARAM,
                "InnerTree": {
                    GH_SCALAR_PATH: [{"type": "System.String", "data": serialized}]
                },
            },
            {
                "ParamName": config.SUMMON_FILENAME_PARAM,
                "InnerTree": {
                    GH_SCALAR_PATH: [{"type": "System.String", "data": filename}]
                },
            },
            {
                "ParamName": config.SUMMON_RUN_PARAM,
                "InnerTree": {
                    GH_SCALAR_PATH: [{"type": "System.Boolean", "data": run_nesting}]
                },
            },
            {
                "ParamName": config.SUMMON_GEOMETRY_MODE_PARAM,
                "InnerTree": {
                    GH_SCALAR_PATH: [
                        {"type": "System.Int32", "data": int(geometry_mode)}
                    ]
                },
            },
        ]
        if sheet_width is not None and sheet_height is not None:
            values.extend(
                [
                    {
                        "ParamName": "SheetWidth",
                        "InnerTree": {
                            GH_SCALAR_PATH: [
                                {"type": "System.Int32", "data": int(sheet_width)}
                            ]
                        },
                    },
                    {
                        "ParamName": "SheetHeight",
                        "InnerTree": {
                            GH_SCALAR_PATH: [
                                {"type": "System.Int32", "data": int(sheet_height)}
                            ]
                        },
                    },
                    {
                        "ParamName": "SheetThickness",
                        "InnerTree": {
                            GH_SCALAR_PATH: [
                                {"type": "System.Int32", "data": int(sheet_thickness)}
                            ]
                        },
                    },
                ]
            )
        if run_nesting:
            write_metadata_overrides_sidecar(csv_folder, metadata_overrides)
            values.append(
                {
                    "ParamName": config.SUMMON_METADATA_OVERRIDES_PARAM,
                    "InnerTree": {
                        GH_SCALAR_PATH: [
                            {
                                "type": "System.String",
                                "data": json.dumps(
                                    metadata_overrides or {},
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ),
                            }
                        ]
                    },
                }
            )
            values.append(
                {
                    "ParamName": config.SUMMON_CSV_FOLDER_PARAM,
                    "InnerTree": {
                        GH_SCALAR_PATH: [
                            {"type": "System.String", "data": csv_folder or ""}
                        ]
                    },
                }
            )
            values.append(
                {
                    "ParamName": config.SUMMON_CSV_RUN_PARAM,
                    "InnerTree": {
                        GH_SCALAR_PATH: [{"type": "System.Boolean", "data": True}]
                    },
                }
            )
        payload = self._compute_post(
            "/grasshopper",
            {
                "algo": self._bytes_to_base64(self.definition_path.read_bytes()),
                "pointer": None,
                "values": values,
            },
        )
        return self._finalize_solve_response(payload)

    def summon_flat_dxf(
        self, input_path: str, output_path: str, filename: str | None = None
    ) -> str:
        layer_b64 = self.solve_summon2d(input_path, filename=filename)
        merge_summoned_layer_dxfs(layer_b64, output_path)
        return output_path

    def _extract_layer_outputs(self, payload: dict[str, Any]) -> dict[str, str]:
        branches = self._extract_layer_outputs_by_branch(payload)
        return branches[0]

    def _extract_layer_outputs_by_branch(
        self, payload: dict[str, Any]
    ) -> list[dict[str, str]]:
        paths = self._collect_sorted_branch_paths(payload)
        branches: list[dict[str, str]] = []
        for path in paths:
            branch_layers: dict[str, str] = {}
            for param_name in config.SUMMON_LAYER_OUTPUTS:
                text = self._extract_text_at_path_static(payload, param_name, path)
                if text:
                    branch_layers[param_name] = text
            if branch_layers:
                branches.append(branch_layers)
        if not branches:
            names = ", ".join(config.SUMMON_LAYER_OUTPUTS)
            detail = self._summarize_gh_messages(payload)
            if "Cast Dxf Sheets" in detail:
                raise ComputeServiceError(
                    "Zero parts nested / too large for sheet. Retry with a bigger sheet size"
                )
            msg = f"Compute returned no data for any layer output ({names})"
            if detail:
                msg = f"{msg}. {detail}"
            raise ComputeServiceError(msg)
        return branches

    @staticmethod
    def _collect_sorted_branch_paths(payload: dict[str, Any]) -> list[str]:
        paths: set[str] = set()
        for param_name in config.SUMMON_LAYER_OUTPUTS:
            for output in payload.get("values") or payload.get("Values") or []:
                if output.get("ParamName") != param_name:
                    continue
                inner_tree = output.get("InnerTree") or {}
                paths.update(inner_tree.keys())
        return sorted(paths)

    @staticmethod
    def _extract_text_at_path_static(
        payload: dict[str, Any], param_name: str, path: str
    ) -> str | None:
        for output in payload.get("values") or payload.get("Values") or []:
            if output.get("ParamName") != param_name:
                continue
            inner_tree = output.get("InnerTree") or {}
            branch = inner_tree.get(path)
            if not isinstance(branch, list):
                return None
            for leaf in branch:
                if not isinstance(leaf, dict):
                    continue
                data = leaf.get("data")
                if data is None:
                    continue
                value = ComputeService._strip_wrapping_quotes(str(data)).strip()
                if value:
                    return value
        return None

    def _extract_meshes_3d(
        self,
        payload: dict[str, Any],
        param_name: str | None = None,
    ) -> list[dict[str, Any]] | None:
        param_name = param_name or config.SUMMON_3D_VIEWER_CONTENT_OUTPUT
        optional = param_name in (
            config.SUMMON_ASSIGNED_BREPS_OUTPUT,
            config.SUMMON_UNASSIGNED_BREPS_OUTPUT,
        )
        meshes: list[dict[str, Any]] = []
        leaf_count = 0
        for data in self._iter_output_leaf_data(payload, param_name):
            leaf_count += 1
            meshes.extend(self._mesh_dicts_from_leaf(data))
        if not meshes:
            if optional or leaf_count == 0:
                return None
            raise ComputeServiceError(
                f"{param_name} JSON must be a mesh array or {{'meshes': [...]}}"
            )
        return meshes

    @staticmethod
    def _iter_output_leaf_data(payload: dict[str, Any], param_name: str):
        for leaf in ComputeService._iter_output_ordered_leaves(payload, param_name):
            yield leaf

    @staticmethod
    def _iter_output_ordered_leaves(payload: dict[str, Any], param_name: str):
        for output in payload.get("values") or payload.get("Values") or []:
            if output.get("ParamName") != param_name:
                continue
            inner_tree = output.get("InnerTree") or {}
            for path in sorted(inner_tree.keys()):
                branch = inner_tree[path]
                if not isinstance(branch, list):
                    continue
                for leaf in branch:
                    if isinstance(leaf, dict):
                        yield leaf

    @staticmethod
    def _coerce_leaf_parsed(data: Any) -> Any | None:
        if isinstance(data, dict):
            parsed: Any = data
        elif isinstance(data, str):
            text = data.strip()
            if not text:
                return None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return None
        else:
            return None

        while isinstance(parsed, str):
            text = parsed.strip()
            if not text:
                return None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                break
        return parsed if isinstance(parsed, (dict, list)) else None

    def _extract_geometry_leaves(
        self,
        payload: dict[str, Any],
        param_name: str,
    ) -> list[dict[str, Any]] | None:
        leaves: list[dict[str, Any]] = []
        for leaf in self._iter_output_leaf_data(payload, param_name):
            parsed = self._geometry_dict_from_leaf(leaf)
            if parsed is not None:
                leaves.append(parsed)
        return leaves or None

    def _extract_string_leaves(
        self,
        payload: dict[str, Any],
        param_name: str,
    ) -> list[str] | None:
        values: list[str] = []
        for leaf in self._iter_output_ordered_leaves(payload, param_name):
            data = leaf.get("data")
            if data is None:
                continue
            value = self._strip_wrapping_quotes(str(data))
            if value:
                values.append(value)
        return values or None

    def _extract_point_leaves(
        self,
        payload: dict[str, Any],
        param_name: str,
    ) -> list[dict[str, Any]] | None:
        points: list[dict[str, Any]] = []
        for leaf in self._iter_output_ordered_leaves(payload, param_name):
            point = self._point_dict_from_leaf(leaf)
            if point is not None:
                points.append(point)
        return points or None

    @staticmethod
    def _geometry_dict_from_leaf(leaf: dict[str, Any]) -> dict[str, Any] | None:
        data = leaf.get("data")
        if data is None:
            return None
        parsed = ComputeService._coerce_leaf_parsed(data)
        if isinstance(parsed, dict):
            return parsed
        return None

    @staticmethod
    def _point_dict_from_parsed(parsed: Any) -> dict[str, Any] | None:
        if isinstance(parsed, list) and len(parsed) >= 2:
            z = parsed[2] if len(parsed) > 2 else 0.0
            return {"x": float(parsed[0]), "y": float(parsed[1]), "z": float(z or 0.0)}
        if not isinstance(parsed, dict):
            return None
        if "archive3dm" in parsed and "data" in parsed:
            return parsed
        x = parsed.get("X", parsed.get("x"))
        y = parsed.get("Y", parsed.get("y"))
        if x is None or y is None:
            return None
        z = parsed.get("Z", parsed.get("z", 0.0))
        return {"x": float(x), "y": float(y), "z": float(z or 0.0)}

    @staticmethod
    def _point_dict_from_leaf(leaf: dict[str, Any]) -> dict[str, Any] | None:
        data = leaf.get("data")
        if data is None:
            return None
        parsed = ComputeService._coerce_leaf_parsed(data)
        if parsed is not None:
            point = ComputeService._point_dict_from_parsed(parsed)
            if point is not None:
                return point
        if isinstance(data, dict):
            return ComputeService._point_dict_from_parsed(data)
        if isinstance(data, str):
            text = data.strip()
            if not text:
                return None
            try:
                return ComputeService._point_dict_from_parsed(json.loads(text))
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _mesh_dicts_from_leaf(leaf: dict[str, Any]) -> list[dict[str, Any]]:
        data = leaf.get("data")
        if data is None:
            return []
        parsed = ComputeService._coerce_leaf_parsed(data)
        if parsed is None:
            return []
        normalized = ComputeService._normalize_parsed_meshes(parsed)
        if normalized is not None:
            return normalized
        if isinstance(parsed, dict) and ComputeService._is_rhino3dm_mesh_json(parsed):
            return [parsed]
        if isinstance(parsed, dict) and parsed.get("type") == "BufferGeometry":
            return [parsed]
        return []

    def _extract_all_output_texts(self, payload: dict[str, Any], param_name: str) -> list[str]:
        return self._extract_all_output_texts_static(payload, param_name)

    def _extract_unassigned(self, payload: dict[str, Any]) -> dict[str, list[str]]:
        return self._extract_unassigned_static(payload)

    @staticmethod
    def _strip_wrapping_quotes(value: str) -> str:
        trimmed = str(value).strip()
        while len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in "\"'":
            trimmed = trimmed[1:-1].strip()
        return trimmed

    @staticmethod
    def _format_unassigned_reason(reason: str) -> str:
        trimmed = ComputeService._strip_wrapping_quotes(reason)
        normalized = trimmed.casefold()
        fit_in_sheet = "failed nesting, most likely parts that could not be fit in a sheet"
        if normalized == fit_in_sheet or (
            "could not be fit" in normalized and "sheet" in normalized
        ):
            return "These parts could not be fit into sheet"
        return trimmed

    @staticmethod
    def _extract_unassigned_ids_static(payload: dict[str, Any]) -> list[str]:
        for param_name in (
            config.SUMMON_UNASSIGNED_ID_OUTPUT,
            config.SUMMON_UNASSIGNED_ID_OUTPUT_FALLBACK,
        ):
            ids = [
                ComputeService._strip_wrapping_quotes(id_value)
                for id_value in ComputeService._extract_all_output_values_static(
                    payload, param_name
                )
            ]
            # Drop GH quantity-only phantoms like "(x)" / "(x2)" with no part name.
            ids = [
                id_value
                for id_value in ids
                if id_value and not re.fullmatch(r"\(x\d*\)", id_value, flags=re.IGNORECASE)
            ]
            if ids:
                return ids
        return []

    @staticmethod
    def _extract_unassigned_static(payload: dict[str, Any]) -> dict[str, list[str]]:
        ids = ComputeService._extract_unassigned_ids_static(payload)
        reasons = [
            ComputeService._format_unassigned_reason(reason)
            for reason in ComputeService._extract_all_output_values_static(
                payload, config.SUMMON_UNASSIGNED_REASON_OUTPUT
            )
        ]
        reasons = [reason for reason in reasons if reason]
        return {"ids": ids, "reasons": list(dict.fromkeys(reasons))}

    @staticmethod
    def _parse_mesh_json_text(raw: str) -> Any:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComputeServiceError(
                f"{config.SUMMON_3D_VIEWER_CONTENT_OUTPUT} output is not valid JSON: {exc}"
            ) from exc

    @staticmethod
    def _is_rhino3dm_mesh_json(parsed: dict[str, Any]) -> bool:
        return "archive3dm" in parsed and "data" in parsed

    @staticmethod
    def _normalize_parsed_meshes(parsed: Any) -> list[dict[str, Any]] | None:
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            meshes = parsed.get("meshes")
            if isinstance(meshes, list):
                return meshes
            if ComputeService._is_rhino3dm_mesh_json(parsed) or parsed.get("type") == "BufferGeometry":
                return [parsed]
        return None

    @staticmethod
    def _extract_all_output_texts_static(payload: dict[str, Any], param_name: str) -> list[str]:
        return [
            value
            for value in ComputeService._extract_all_output_values_static(payload, param_name)
            if value
        ]

    @staticmethod
    def _extract_all_output_values_static(payload: dict[str, Any], param_name: str) -> list[str]:
        values: list[str] = []
        for output in payload.get("values") or payload.get("Values") or []:
            if output.get("ParamName") != param_name:
                continue
            inner_tree = output.get("InnerTree") or {}
            for branch in inner_tree.values():
                for leaf in branch:
                    data = leaf.get("data")
                    if data is None:
                        continue
                    value = str(data).strip()
                    if value:
                        values.append(value)
        return values

    @staticmethod
    def _count_output_leaves_static(payload: dict[str, Any], param_name: str) -> int:
        count = 0
        for output in payload.get("values") or payload.get("Values") or []:
            if output.get("ParamName") != param_name:
                continue
            inner_tree = output.get("InnerTree") or {}
            for branch in inner_tree.values():
                count += len(branch)
        return count

    @staticmethod
    def _summarize_gh_messages(payload: dict[str, Any]) -> str:
        messages: list[str] = []
        for key in ("errors", "Errors", "warnings", "Warnings"):
            messages.extend(str(message) for message in (payload.get(key) or []))
        if not messages:
            return ""
        unique = list(dict.fromkeys(messages))
        sample = unique[:3]
        suffix = f" (+{len(unique) - len(sample)} more)" if len(unique) > len(sample) else ""
        return "Grasshopper: " + "; ".join(sample) + suffix

    def _try_extract_output_text(self, payload: dict[str, Any], param_name: str) -> str | None:
        return self._try_extract_output_text_static(payload, param_name)

    @staticmethod
    def _try_extract_output_text_static(payload: dict[str, Any], param_name: str) -> str | None:
        texts = ComputeService._extract_all_output_texts_static(payload, param_name)
        return texts[0] if texts else None

    @staticmethod
    def _try_extract_unquoted_output_text_static(
        payload: dict[str, Any], param_name: str
    ) -> str | None:
        text = ComputeService._try_extract_output_text_static(payload, param_name)
        if text is None:
            return None
        return ComputeService._strip_wrapping_quotes(text)

    @staticmethod
    def _extract_nesting_csv_static(payload: dict[str, Any]) -> str | None:
        text = ComputeService._try_extract_output_text_static(
            payload, config.SUMMON_NESTING_CSV_OUTPUT
        )
        if text is None:
            return None
        trimmed = ComputeService._strip_wrapping_quotes(text)
        return (
            trimmed.replace("\\r\\n", "\r\n")
            .replace("\\n", "\n")
            .replace("\\r", "\r")
        )

    def _compute_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        endpoint = f"{self.compute_base_url}{path if path.startswith('/') else f'/{path}'}"
        req = request.Request(
            endpoint,
            data=body,
            headers=self._compute_headers(),
            method="POST",
        )
        call_lock = _GRASSHOPPER_CALL_LOCK if path == "/grasshopper" else nullcontext()
        try:
            with call_lock:
                with request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            parsed = self._parse_grasshopper_response(detail)
            if parsed is not None:
                return parsed
            hint = self._local_compute_setup_hint()
            msg = f"Compute call failed {exc.code} on {path}: {detail or exc.reason}"
            if hint:
                msg = f"{msg}. {hint}"
            raise ComputeServiceError(msg) from exc
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

    def _fetch_active_children(self) -> str | None:
        try:
            req = request.Request(
                f"{self.compute_base_url}/activechildren",
                headers=self._compute_headers(),
                method="GET",
            )
            with request.urlopen(req, timeout=5) as response:
                return response.read().decode("utf-8", errors="ignore")
        except (error.URLError, OSError):
            return None

    @staticmethod
    def _expected_geometry_exe_exists() -> bool:
        geometry_exe = Path(
            r"C:\Users\maria\Documents\dataB\compute\compute.geometry\compute.geometry.exe"
        )
        return geometry_exe.is_file()

    def _local_compute_setup_hint(self) -> str:
        if "127.0.0.1" not in self.compute_base_url and "localhost" not in self.compute_base_url:
            return ""
        children = self._fetch_active_children()
        if children == "0" or not self._expected_geometry_exe_exists():
            return (
                "Local Rhino Compute has no geometry workers. Deploy compute.geometry.exe to "
                "C:\\Users\\maria\\Documents\\dataB\\compute\\compute.geometry\\ and restart "
                "rhino.compute.exe with --spawn-on-startup."
            )
        return ""

    @staticmethod
    def _bytes_to_base64(payload: bytes) -> str:
        import base64

        return base64.b64encode(payload).decode("ascii")


def create_service() -> ComputeService:
    return ComputeService(
        compute_base_url=config.COMPUTE_BASE_URL,
        compute_api_key=config.COMPUTE_API_KEY,
        definition_path=config.definition_gh_path(),
        request_timeout_seconds=config.COMPUTE_TIMEOUT_SECONDS,
    )
