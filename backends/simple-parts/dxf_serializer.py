import base64
import os
import tempfile
from pathlib import Path


def encode_file_to_base64(filepath: str) -> str:
    """Read a file's raw bytes and return its base64-encoded string."""
    raw_bytes = Path(filepath).read_bytes()
    return base64.b64encode(raw_bytes).decode("ascii")


def _append_branch_layers_to_doc(doc, msp, layer_b64: dict[str, str]) -> None:
    """Decode one branch's per-layer base64 DXFs and append entities to doc."""
    import os
    import tempfile

    import ezdxf

    from layer_scheme import (
        GH_OUTPUT_SHEETS,
        LAYER_BORES,
        LAYER_INSIDE,
        LAYER_OUTSIDE,
        LAYER_PLATE,
        LAYER_TEXT,
    )

    layer_order = (
        (LAYER_OUTSIDE, LAYER_OUTSIDE),
        (LAYER_INSIDE, LAYER_INSIDE),
        (LAYER_BORES, LAYER_BORES),
        (LAYER_TEXT, LAYER_TEXT),
        (GH_OUTPUT_SHEETS, LAYER_PLATE),
    )
    for gh_key, dxf_layer in layer_order:
        payload = layer_b64.get(gh_key, "")
        if not str(payload).strip():
            continue
        if dxf_layer not in doc.layers:
            doc.layers.add(dxf_layer)
        fd, temp_path = tempfile.mkstemp(suffix=".dxf")
        try:
            os.write(fd, base64.b64decode(payload))
            os.close(fd)
            fd = None
            src = ezdxf.readfile(temp_path)
        finally:
            if fd is not None:
                os.close(fd)
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        for entity in src.modelspace():
            copied = entity.copy()
            copied.dxf.layer = dxf_layer
            msp.add_entity(copied)


def merge_summoned_layer_dxfs(layer_b64: dict[str, str], output_path: str) -> None:
    """Decode per-layer base64 DXF strings and write one multi-layer flat DXF."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    _append_branch_layers_to_doc(doc, msp, layer_b64)
    doc.saveas(output_path)


def merge_summoned_layer_dxfs_multi(
    branches: list[dict[str, str]],
    output_path: str,
) -> None:
    """Merge every data-tree branch into one multi-layer flat DXF."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for branch_layers in branches:
        _append_branch_layers_to_doc(doc, msp, branch_layers)
    doc.saveas(output_path)


def normalize_summoned_layers_for_export(path: str) -> None:
    """Remap GH flat-output curve layers so boundary_detection admits them."""
    import ezdxf
    from boundary_detection import CURVE_TYPES
    from layer_scheme import ADMITTED_LAYERS, LAYER_PLATE, LAYER_TEXT, SKIP_LAYER_RE

    preserved_layers = ADMITTED_LAYERS | {LAYER_TEXT, LAYER_PLATE}

    doc = ezdxf.readfile(path)
    changed = False
    for entity in doc.modelspace():
        if entity.dxftype() not in CURVE_TYPES:
            continue
        layer = entity.dxf.layer or "0"
        if layer in preserved_layers or SKIP_LAYER_RE.search(layer):
            continue
        entity.dxf.layer = "Outside"
        changed = True
    if changed:
        doc.saveas(path)


def apply_nesting_layer_colors(doc) -> None:
    """Set nesting layer RGB + ACI colors; entities on those layers use BYLAYER color."""
    from layer_scheme import NESTING_LAYER_ACI, NESTING_LAYER_RGB

    for layer_name, rgb in NESTING_LAYER_RGB.items():
        if layer_name not in doc.layers:
            continue
        layer = doc.layers.get(layer_name)
        layer.rgb = rgb
        aci = NESTING_LAYER_ACI.get(layer_name)
        if aci is not None:
            layer.dxf.color = aci

    for entity in doc.modelspace():
        if entity.dxf.layer in NESTING_LAYER_RGB:
            entity.dxf.color = 256


def apply_nesting_layer_colors_to_path(path: str) -> None:
    import ezdxf

    doc = ezdxf.readfile(path)
    apply_nesting_layer_colors(doc)
    doc.saveas(path)


def exclude_layers(doc, layer_names: set[str]) -> None:
    """Remove entities on the given layers and their layer-table entries."""
    if not layer_names:
        return
    msp = doc.modelspace()
    for entity in list(msp):
        if entity.dxf.layer in layer_names:
            msp.delete_entity(entity)
    for layer_name in layer_names:
        if layer_name in doc.layers:
            doc.layers.remove(layer_name)


def is_3d_dxf(path: str) -> bool:
    """True when modelspace has solids or polyface meshes (3D summon path)."""
    import ezdxf

    doc = ezdxf.readfile(path)
    for entity in doc.modelspace():
        dxftype = entity.dxftype()
        if dxftype in ("SOLID", "3DFACE"):
            return True
        if dxftype == "POLYLINE" and entity.is_poly_face_mesh:
            return True
    return False


DEFAULT_UNASSIGNED_TEXT_HEIGHT = 50.0


def _decode_base64_dxf(b64_text: str):
    import os
    import tempfile

    import ezdxf

    payload = str(b64_text or "").strip()
    if not payload:
        return None
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".dxf")
        os.write(fd, base64.b64decode(payload))
        os.close(fd)
        fd = None
        return ezdxf.readfile(temp_path)
    except Exception:
        return None
    finally:
        if fd is not None:
            os.close(fd)
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _append_text_labels(doc, texts: list[str] | None, text_points: list[dict] | None) -> None:
    from layer_scheme import LAYER_TEXT

    if not texts or not text_points:
        return

    if LAYER_TEXT not in doc.layers:
        doc.layers.add(LAYER_TEXT)

    msp = doc.modelspace()
    count = min(len(texts), len(text_points))
    for index in range(count):
        text = str(texts[index] or "").strip()
        if not text:
            continue
        point = text_points[index] or {}
        x = point.get("x")
        y = point.get("y")
        if x is None or y is None:
            continue
        z = float(point.get("z") or 0.0)
        msp.add_text(
            text,
            dxfattribs={
                "layer": LAYER_TEXT,
                "insert": (float(x), float(y), z),
                "height": DEFAULT_UNASSIGNED_TEXT_HEIGHT,
            },
        )


def write_unassigned_dxf(
    b64_geometry: str,
    output_path: str,
    *,
    texts: list[str] | None = None,
    text_points: list[dict] | None = None,
) -> bool:
    """Decode GH UnassignedDXF geometry, join connected curves, append labels."""
    from boundary_detection import apply_curve_join_to_document

    doc = _decode_base64_dxf(b64_geometry)
    if doc is None:
        return False

    apply_curve_join_to_document(doc)
    _append_text_labels(doc, texts, text_points)
    doc.saveas(output_path)
    return True


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "input.dxf"
    encoded = encode_file_to_base64(path)
    out_path = path.rsplit(".", 1)[0] + "_b64.txt"
    Path(out_path).write_text(encoded, encoding="ascii")
    print(f"Encoded {len(encoded)} chars, written to {out_path}")