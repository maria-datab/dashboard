import json
import os
import re
import tempfile
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, jsonify, request, send_file
from werkzeug.datastructures import FileStorage

import config
from boundary_detection import read_embedded_geometry
from compute_service import ComputeServiceError, create_service
from dxf_serializer import (
    apply_nesting_layer_colors_to_path,
    merge_summoned_layer_dxfs,
    merge_summoned_layer_dxfs_multi,
    normalize_summoned_layers_for_export,
    write_unassigned_dxf,
)
from dxf_to_pdf import load_branch_doc, render_branch_dxfs_to_pdf
from llm import parse_chat_intent
from metadata_overrides import (
    apply_label_overrides_to_nesting_dxf,
    merge_post_injection_with_overrides,
    parse_metadata_overrides_json,
    write_metadata_overrides_sidecar,
)
from routes._paths import JOBS_DIR

bp = Blueprint("core", __name__)

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _resolve_download_name(requested: str | None, default: str) -> str:
    name = os.path.basename(requested or "").strip()
    name = _UNSAFE_FILENAME_CHARS.sub("-", name)
    if not name:
        return default
    if not name.lower().endswith(".dxf"):
        name = f"{name}.dxf"
    return name


def _resolve_zip_download_name(requested: str | None, default: str) -> str:
    name = os.path.basename(requested or "").strip()
    name = _UNSAFE_FILENAME_CHARS.sub("-", name)
    if not name:
        return default
    for ext in (".zip", ".dxf"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    return f"{name}.zip"


def _branch_dxf_entry_name(zip_download_name: str, index: int) -> str:
    base = zip_download_name
    if base.lower().endswith(".zip"):
        base = base[:-4]
    return f"{base}_{index}.dxf"


def _pdf_entry_name(zip_download_name: str) -> str:
    base = zip_download_name
    if base.lower().endswith(".zip"):
        base = base[:-4]
    return f"{base}.pdf"


def _csv_entry_name(zip_download_name: str) -> str:
    base = zip_download_name
    if base.lower().endswith(".zip"):
        base = base[:-4]
    return f"{base}.csv"


def _list_branch_dxf_paths(job_id: str) -> list[str]:
    branches_dir = os.path.join(JOBS_DIR, job_id, "output", "branches")
    if os.path.isdir(branches_dir):
        paths: list[tuple[int, str]] = []
        for name in os.listdir(branches_dir):
            if not name.endswith(".dxf"):
                continue
            stem = name[:-4]
            if stem.isdigit():
                paths.append((int(stem), os.path.join(branches_dir, name)))
        if paths:
            return [path for _, path in sorted(paths)]

    result_path = os.path.join(JOBS_DIR, job_id, "output", "result.dxf")
    if os.path.isfile(result_path):
        return [result_path]
    return []


@bp.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    return jsonify(
        parse_chat_intent(
            body.get("message", ""),
            body.get("chatStep", "idle"),
            body.get("parts", []),
            body.get("knownMaterials"),
        )
    )


def _input_suffix(filename: str) -> str:
    suffix = Path(filename or "input.dxf").suffix.lower()
    return suffix if suffix in (".dxf", ".3dm", ".dwg") else ".dxf"


def _parse_run_nesting() -> bool:
    return request.form.get("run", "true").lower() in ("1", "true", "yes")


def _parse_geometry_mode() -> int:
    raw = str(request.form.get("geometryMode", "0")).strip().lower()
    return 1 if raw in ("1", "true") else 0


def _parse_metadata_overrides() -> tuple[dict[str, dict[str, str]] | None, tuple | None]:
    raw = request.form.get("metadataOverrides", "{}")
    try:
        return parse_metadata_overrides_json(raw), None
    except json.JSONDecodeError:
        return None, (jsonify({"error": "metadataOverrides must be valid JSON"}), 400)
    except ValueError as exc:
        return None, (jsonify({"error": str(exc)}), 400)


def _solve_hops(upload, *, run_nesting: bool = True):
    filename = os.path.basename(upload.filename or "input.dxf")
    suffix = _input_suffix(filename)
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    summoned_path = None
    job_id = str(uuid4())
    try:
        upload.save(path)
        service = create_service()
        geometry_mode = _parse_geometry_mode()
        if not run_nesting:
            preview = service.solve_preview_only(
                path, filename=filename, geometry_mode=geometry_mode
            )
            return preview, None

        try:
            sheet_width = int(float(request.form["sheetWidth"]))
            sheet_height = int(float(request.form["sheetHeight"]))
            sheet_thickness = int(float(request.form["sheetThickness"]))
            if sheet_width <= 0 or sheet_height <= 0 or sheet_thickness <= 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return None, (
                jsonify({"error": "Missing or invalid sheetWidth/sheetHeight/sheetThickness"}),
                400,
            )

        metadata_overrides, metadata_err = _parse_metadata_overrides()
        if metadata_err:
            return None, metadata_err

        job_dir = os.path.join(JOBS_DIR, job_id)
        output_dir = os.path.join(job_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        Path(os.path.join(job_dir, f"input{suffix}")).write_bytes(Path(path).read_bytes())
        csv_folder = config.nest_csv_folder(job_id, output_dir)
        write_metadata_overrides_sidecar(csv_folder, metadata_overrides)

        summoned_fd, summoned_path = tempfile.mkstemp(suffix=".dxf")
        os.close(summoned_fd)
        (
            layer_branches,
            assigned_meshes3d,
            input_text,
            input_text_pt,
            unassigned_data,
            unassigned_meshes3d,
            unassigned_dxf_b64,
            unassigned_text,
            unassigned_text_pt,
            nesting_csv,
            initial_part_keys,
            post_injection_names,
            post_injection_amount,
        ) = service.solve_summon2d_with_meshes3d(
            path,
            filename=filename,
            run_nesting=True,
            geometry_mode=geometry_mode,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            sheet_thickness=sheet_thickness,
            metadata_overrides=metadata_overrides,
            csv_folder=csv_folder,
        )
        nesting_csv_path = os.path.join(output_dir, "nesting.csv")
        if not str(nesting_csv or "").strip() and os.path.isfile(nesting_csv_path):
            nesting_csv = Path(nesting_csv_path).read_text(encoding="utf-8")
        unassigned_ids = unassigned_data["ids"]
        unassigned_reasons = unassigned_data["reasons"]
        original_post_injection_names = post_injection_names
        post_injection_names, post_injection_amount = merge_post_injection_with_overrides(
            initial_part_keys,
            post_injection_names,
            post_injection_amount,
            metadata_overrides,
        )
        merge_summoned_layer_dxfs_multi(layer_branches, summoned_path)
        normalize_summoned_layers_for_export(summoned_path)
        apply_nesting_layer_colors_to_path(summoned_path)
        apply_label_overrides_to_nesting_dxf(
            summoned_path,
            original_names=original_post_injection_names,
            merged_names=post_injection_names,
        )
        geometry_data = read_embedded_geometry(summoned_path)
        dxf_text = Path(summoned_path).read_text(encoding="utf-8", errors="replace")
        first_branch = layer_branches[0] if layer_branches else {}
        routing = {
            name: {
                "hasData": bool(str(first_branch.get(name, "")).strip()),
                "dataLength": len(first_branch.get(name, "")),
            }
            for name in config.SUMMON_LAYER_OUTPUTS
        }
        routing["branchCount"] = len(layer_branches)
        assigned_meshes3d_json = (
            json.dumps(assigned_meshes3d, separators=(",", ":")) if assigned_meshes3d else ""
        )
        routing[config.SUMMON_ASSIGNED_BREPS_OUTPUT] = {
            "hasData": bool(assigned_meshes3d),
            "dataLength": len(assigned_meshes3d_json),
        }
        routing[config.SUMMON_UNASSIGNED_BREPS_OUTPUT] = {
            "hasData": bool(unassigned_meshes3d),
            "dataLength": len(unassigned_meshes3d or []),
        }
        routing[config.SUMMON_INPUT_TEXT_OUTPUT] = {
            "hasData": bool(input_text),
            "dataLength": len(input_text or []),
        }
        routing[config.SUMMON_INPUT_TEXT_PT_OUTPUT] = {
            "hasData": bool(input_text_pt),
            "dataLength": len(input_text_pt or []),
        }
        routing[config.SUMMON_UNASSIGNED_ID_OUTPUT] = {
            "hasData": bool(unassigned_ids),
            "dataLength": len(unassigned_ids),
        }
        routing[config.SUMMON_UNASSIGNED_REASON_OUTPUT] = {
            "hasData": bool(unassigned_reasons),
            "dataLength": len(unassigned_reasons),
        }
        routing[config.SUMMON_UNASSIGNED_DXF_OUTPUT] = {
            "hasData": bool(str(unassigned_dxf_b64 or "").strip()),
            "dataLength": len(unassigned_dxf_b64 or ""),
        }
        routing[config.SUMMON_UNASSIGNED_TEXT_OUTPUT] = {
            "hasData": bool(unassigned_text),
            "dataLength": len(unassigned_text or []),
        }
        routing[config.SUMMON_UNASSIGNED_TEXT_PT_OUTPUT] = {
            "hasData": bool(unassigned_text_pt),
            "dataLength": len(unassigned_text_pt or []),
        }
        routing[config.SUMMON_NESTING_CSV_OUTPUT] = {
            "hasData": bool(str(nesting_csv or "").strip()),
            "dataLength": len(nesting_csv or ""),
        }
        routing[config.SUMMON_INITIAL_PART_KEYS_OUTPUT] = {
            "hasData": bool(initial_part_keys),
            "dataLength": len(initial_part_keys or []),
        }
        routing[config.SUMMON_POST_INJECTION_NAMES_OUTPUT] = {
            "hasData": bool(post_injection_names),
            "dataLength": len(post_injection_names or []),
        }
        routing[config.SUMMON_POST_INJECTION_AMOUNT_OUTPUT] = {
            "hasData": bool(post_injection_amount),
            "dataLength": len(post_injection_amount or []),
        }
        routing["metadataOverridesReceived"] = {
            "hasData": bool(metadata_overrides),
            "dataLength": len(metadata_overrides or {}),
        }

        branches_dir = os.path.join(output_dir, "branches")
        os.makedirs(branches_dir, exist_ok=True)
        Path(os.path.join(output_dir, "result.dxf")).write_text(dxf_text, encoding="utf-8")
        for index, branch_layers in enumerate(layer_branches):
            branch_path = os.path.join(branches_dir, f"{index}.dxf")
            merge_summoned_layer_dxfs(branch_layers, branch_path)
            normalize_summoned_layers_for_export(branch_path)
            apply_nesting_layer_colors_to_path(branch_path)
        unassigned_dxf_path = os.path.join(output_dir, "unassigned.dxf")
        has_unassigned_dxf = write_unassigned_dxf(
            unassigned_dxf_b64 or "",
            unassigned_dxf_path,
            texts=unassigned_text,
            text_points=unassigned_text_pt,
        )
        if nesting_csv is not None and str(nesting_csv).strip():
            Path(nesting_csv_path).write_text(nesting_csv, encoding="utf-8")

        return {
            "jobId": job_id,
            "dxfText": dxf_text,
            "assignedMeshes3d": assigned_meshes3d,
            "initialPartKeys": initial_part_keys,
            "postInjectionNames": post_injection_names,
            "postInjectionAmount": post_injection_amount,
            "inputText": input_text,
            "inputTextPt": input_text_pt,
            "boundaries": geometry_data["boundaries"],
            "blockInserts": geometry_data["blockInserts"],
            "schemeOutliers": geometry_data["schemeOutliers"],
            "unassignedIds": unassigned_ids,
            "unassignedReasons": unassigned_reasons,
            "unassignedMeshes3d": unassigned_meshes3d,
            "hasUnassignedDxf": has_unassigned_dxf,
            "metadataOverridesReceived": metadata_overrides,
            "routing": routing,
        }, None
    except ComputeServiceError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    finally:
        if os.path.isfile(path):
            os.remove(path)
        if summoned_path and os.path.isfile(summoned_path):
            os.remove(summoned_path)


@bp.post("/api/compute/summon-preview")
def compute_summon_preview():
    upload = request.files.get("file")
    if not upload:
        return jsonify({"error": "Missing file"}), 400
    payload, err = _solve_hops(upload, run_nesting=_parse_run_nesting())
    if err:
        return err
    return jsonify(payload)


@bp.post("/api/hops/solve")
def hops_solve():
    upload = request.files.get("file")
    if not upload:
        return jsonify({"error": "Missing file"}), 400
    payload, err = _solve_hops(upload, run_nesting=_parse_run_nesting())
    if err:
        return err
    return jsonify(payload)


@bp.post("/api/jobs/<job_id>/nest-unassigned")
def nest_unassigned_job(job_id):
    unassigned_path = os.path.join(JOBS_DIR, job_id, "output", "unassigned.dxf")
    if not os.path.isfile(unassigned_path):
        return jsonify({"error": "Unassigned DXF not found"}), 404

    upload = FileStorage(
        stream=BytesIO(Path(unassigned_path).read_bytes()),
        filename="unassigned.dxf",
    )
    payload, err = _solve_hops(upload, run_nesting=True)
    if err:
        return err
    if (
        payload.get("unassignedIds")
        or payload.get("hasUnassignedDxf")
        or payload.get("unassignedMeshes3d")
    ):
        return jsonify({
            "error": "Parts still could not be fit into sheet",
            "unassignedIds": payload.get("unassignedIds") or [],
            "unassignedReasons": payload.get("unassignedReasons") or [],
        }), 409
    return jsonify(payload)


@bp.get("/api/jobs/<job_id>/download")
def download_job(job_id):
    branch_paths = _list_branch_dxf_paths(job_id)
    if not branch_paths:
        return jsonify({"error": "Job not found"}), 404

    download_name = _resolve_zip_download_name(request.args.get("filename"), "nesting.zip")
    exclude = {x for x in request.args.get("excludeLayers", "").split(",") if x}

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, branch_path in enumerate(branch_paths):
            entry_name = _branch_dxf_entry_name(download_name, index)
            if exclude:
                doc = load_branch_doc(branch_path, exclude)
                stream = StringIO()
                doc.write(stream)
                archive.writestr(entry_name, stream.getvalue().encode("utf-8"))
            else:
                archive.write(branch_path, arcname=entry_name)

        try:
            pdf_bytes = render_branch_dxfs_to_pdf(branch_paths, exclude_layers=exclude)
        except Exception as exc:
            return jsonify({"error": f"PDF generation failed: {exc}"}), 500
        archive.writestr(_pdf_entry_name(download_name), pdf_bytes)

        nesting_csv_path = os.path.join(JOBS_DIR, job_id, "output", "nesting.csv")
        if os.path.isfile(nesting_csv_path):
            archive.writestr(
                _csv_entry_name(download_name),
                Path(nesting_csv_path).read_bytes(),
            )
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )


@bp.get("/api/jobs/<job_id>/download/preview")
def download_preview_dxf(job_id):
    output_dir = os.path.join(JOBS_DIR, job_id, "output")
    use_raw = request.args.get("raw", "").lower() in ("1", "true", "yes")
    preview_path = os.path.join(
        output_dir, "preview-raw.dxf" if use_raw else "preview.dxf"
    )
    if not os.path.isfile(preview_path):
        preview_path = os.path.join(output_dir, "preview.dxf")
    if not os.path.isfile(preview_path):
        return jsonify({"error": "Preview DXF not found"}), 404

    default_name = "preview-raw.dxf" if use_raw else "preview.dxf"
    download_name = _resolve_download_name(request.args.get("filename"), default_name)
    return send_file(
        preview_path,
        mimetype="application/dxf",
        as_attachment=True,
        download_name=download_name,
    )


@bp.get("/api/jobs/<job_id>/download/unassigned")
def download_unassigned_job(job_id):
    unassigned_path = os.path.join(JOBS_DIR, job_id, "output", "unassigned.dxf")
    if not os.path.isfile(unassigned_path):
        return jsonify({"error": "Unassigned DXF not found"}), 404

    download_name = _resolve_download_name(request.args.get("filename"), "unassigned.dxf")
    return send_file(
        unassigned_path,
        mimetype="application/dxf",
        as_attachment=True,
        download_name=download_name,
    )
