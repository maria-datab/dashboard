"""Rhino-style curve join for closed part boundaries and foreign LINE flagging."""

import math

from layer_scheme import ADMITTED_LAYERS, SKIP_LAYER_RE
from outlier_detection import (
    classify_closing_lines,
    find_scheme_outliers,
    flag_foreign_line_outliers,
    infer_closing_layer,
)

CURVE_TYPES = frozenset({
    "LINE", "LWPOLYLINE", "POLYLINE", "POLYLINE3D",
    "CIRCLE", "ARC", "ELLIPSE", "SPLINE",
})

MIN_BBOX_DIM = 10.0
MAX_BBOX_DIM = 5000.0


def _snap_key(pt, tolerance):
    return (round(pt[0] / tolerance), round(pt[1] / tolerance))


def _points_close(a, b, tolerance):
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def _polyline_length(pts):
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        total += math.hypot(dx, dy)
    return total


def _bbox_dims(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def _bbox_in_detectable_range(pts):
    if len(pts) < 2:
        return False
    width, height = _bbox_dims(pts)
    if width < MIN_BBOX_DIM or height < MIN_BBOX_DIM:
        return False
    if width > MAX_BBOX_DIM or height > MAX_BBOX_DIM:
        return False
    return True


def _is_admitted_layer(layer):
    return (layer or "0") in ADMITTED_LAYERS


def _should_skip_join_layer(layer):
    return bool(SKIP_LAYER_RE.search(layer or ""))


def _include_in_boundary_join(entity):
    """Admitted-layer curves plus foreign LINEs that may close open Outside chains."""
    dxftype = entity.dxftype()
    if dxftype not in CURVE_TYPES:
        return False
    layer = entity.dxf.layer or "0"
    if _should_skip_join_layer(layer):
        return False
    if _is_admitted_layer(layer):
        return True
    return dxftype == "LINE"


def _include_in_export_join(entity):
    """All joinable curves on non-skip layers (unassigned DXF export)."""
    if entity.dxftype() not in CURVE_TYPES:
        return False
    layer = entity.dxf.layer or "0"
    return not _should_skip_join_layer(layer)


def _entity_native_closed(entity):
    dxftype = entity.dxftype()
    if dxftype in ("CIRCLE", "ELLIPSE"):
        return True
    if dxftype == "LWPOLYLINE":
        return bool(entity.closed)
    if dxftype in ("POLYLINE", "POLYLINE3D"):
        return bool(entity.is_closed)
    return False


def _collect_edges(msp, flatten_fn, tolerance, include_fn=_include_in_boundary_join):
    edges = []
    node_map = {}

    for entity in msp:
        if entity.dxftype() not in CURVE_TYPES:
            continue
        layer = entity.dxf.layer or "0"
        if not include_fn(entity):
            continue

        pts = flatten_fn(entity, tolerance)
        if len(pts) < 2:
            continue

        native_closed = _entity_native_closed(entity)
        if native_closed and _points_close(pts[0], pts[-1], tolerance) and len(pts) > 1:
            pts = pts[:-1]

        start_key = _snap_key(pts[0], tolerance)
        end_key = _snap_key(pts[-1], tolerance)

        idx = len(edges)
        edges.append({
            "handle": str(entity.dxf.handle),
            "layer": layer,
            "entity_type": entity.dxftype(),
            "pts": pts,
            "start_key": start_key,
            "end_key": end_key,
            "native_closed": native_closed,
        })

        node_map.setdefault(start_key, []).append((idx, "start"))
        node_map.setdefault(end_key, []).append((idx, "end"))

    return edges, node_map


def _pick_next_edge(node_map, node_key, used):
    for edge_idx, _end_name in node_map.get(node_key, []):
        if edge_idx in used:
            continue
        return edge_idx
    return None


def _orient_edge(edge, connect_key, tolerance):
    if edge["start_key"] == connect_key:
        return edge["pts"], edge["end_key"]
    if edge["end_key"] == connect_key:
        pts = list(reversed(edge["pts"]))
        return pts, edge["start_key"]
    sk = _snap_key(edge["pts"][0], tolerance)
    ek = _snap_key(edge["pts"][-1], tolerance)
    if sk == connect_key:
        return edge["pts"], ek
    return list(reversed(edge["pts"])), sk


def _merge_chain_pts(chain_indices, edges, tolerance):
    if not chain_indices:
        return []

    first = edges[chain_indices[0]]
    merged = list(first["pts"])
    tail_key = first["end_key"]

    for idx in chain_indices[1:]:
        edge = edges[idx]
        pts, tail_key = _orient_edge(edge, tail_key, tolerance)
        if _points_close(merged[-1], pts[0], tolerance):
            merged.extend(pts[1:])
        else:
            merged.extend(pts)

    return merged


def _walk_chains(edges, node_map):
    used = set()
    chains = []

    for start_idx in range(len(edges)):
        if start_idx in used:
            continue

        chain = [start_idx]
        used.add(start_idx)

        while True:
            tail_key = edges[chain[-1]]["end_key"]
            nxt = _pick_next_edge(node_map, tail_key, used)
            if nxt is None:
                break
            chain.append(nxt)
            used.add(nxt)

        while True:
            head_key = edges[chain[0]]["start_key"]
            prev = _pick_next_edge(node_map, head_key, used)
            if prev is None:
                break
            chain.insert(0, prev)
            used.add(prev)

        chains.append(chain)

    return chains


def _chain_members(chain, edges):
    members = []
    seen_handles = set()
    for idx in chain:
        edge = edges[idx]
        if edge["handle"] in seen_handles:
            continue
        seen_handles.add(edge["handle"])
        members.append({
            "handle": edge["handle"],
            "layer": edge["layer"],
            "entity_type": edge["entity_type"],
        })
    return members


def _finalize_chain(chain, edges, tolerance, *, closed_only):
    pts = _merge_chain_pts(chain, edges, tolerance)
    if len(pts) < 2:
        return None

    is_closed = _points_close(pts[0], pts[-1], tolerance)
    if not is_closed and len(chain) == 1 and edges[chain[0]]["native_closed"]:
        is_closed = True

    if closed_only:
        if not is_closed or len(pts) < 3:
            return None
        if not _points_close(pts[0], pts[-1], tolerance):
            pts = pts + [pts[0]]
    elif is_closed:
        if len(pts) < 3:
            return None
        if not _points_close(pts[0], pts[-1], tolerance):
            pts = pts + [pts[0]]

    members = _chain_members(chain, edges)
    return {
        "member_indices": chain,
        "pts": pts,
        "members": members,
        "is_closed": is_closed,
        "is_composite": len(members) > 1,
    }


def _build_chains(edges, node_map, tolerance, *, closed_only=True):
    result = []
    for chain in _walk_chains(edges, node_map):
        item = _finalize_chain(chain, edges, tolerance, closed_only=closed_only)
        if item:
            result.append(item)
    return result


def _majority_layer(members, edges_by_handle):
    if not members:
        return None

    layers = {}
    for member in members:
        layer = member["layer"]
        entry = layers.setdefault(layer, {"count": 0, "length": 0.0})
        entry["count"] += 1
        for edge in edges_by_handle.get(member["handle"], []):
            entry["length"] += _polyline_length(edge["pts"])

    def sort_key(item):
        layer, stats = item
        return (-stats["count"], -stats["length"], layer)

    return sorted(layers.items(), key=sort_key)[0][0]


def _dedupe_boundaries(boundaries):
    if len(boundaries) <= 1:
        return boundaries

    handle_sets = [frozenset(b["member_handles"]) for b in boundaries]
    drop = set()

    for i, hs_i in enumerate(handle_sets):
        if i in drop:
            continue
        for j, hs_j in enumerate(handle_sets):
            if i == j or j in drop:
                continue
            if hs_i < hs_j:
                drop.add(i)
                break

    return [b for idx, b in enumerate(boundaries) if idx not in drop]


def _boundary_id(member_handles):
    return sorted(member_handles)[0]


def _merge_metadata(entity_by_handle, member_handles, read_metadata_fn):
    nr = mat = anz = ""
    for handle in member_handles:
        entity = entity_by_handle.get(handle)
        if not entity:
            continue
        meta = read_metadata_fn(entity)
        if not nr and meta.get("Nr"):
            nr = meta["Nr"]
        if not mat and meta.get("Mat"):
            mat = meta["Mat"]
        if not anz and meta.get("Anz"):
            anz = meta["Anz"]
    return nr, mat, anz


def _export_primitives_for_boundary(member_handles, entity_by_handle, pts, export_fn, tolerance):
    if len(member_handles) == 1:
        entity = entity_by_handle.get(member_handles[0])
        if entity:
            primitives = export_fn(entity, tolerance)
            if primitives:
                return primitives

    pts_2d = [(float(x), float(y)) for x, y in pts]
    if len(pts_2d) > 1 and _points_close(pts_2d[0], pts_2d[-1], tolerance):
        pts_2d = pts_2d[:-1]
    if len(pts_2d) < 2:
        return []
    return [("LWPOLYLINE", pts_2d, True, 0.0)]


def find_boundaries(doc, tolerance=0.01):
    """
    Detect closed part boundaries via Rhino-style join at coincident endpoints.
    Returns boundary dicts with id, members, pts, layer outliers, and export primitives.
    """
    from curve_geometry import (
        entity_export_primitives as _entity_export_primitives,
        flatten_entity_xy as _flatten_entity_xy,
        read_curve_metadata,
    )

    msp = doc.modelspace()
    edges, node_map = _collect_edges(msp, _flatten_entity_xy, tolerance)
    chains = _build_chains(edges, node_map, tolerance)

    edges_by_handle = {}
    for edge in edges:
        edges_by_handle.setdefault(edge["handle"], []).append(edge)

    entity_by_handle = {}
    for entity in msp:
        if entity.dxftype() in CURVE_TYPES:
            entity_by_handle[str(entity.dxf.handle)] = entity

    pending = []
    all_preliminary_outliers = []
    for chain in chains:
        if not _bbox_in_detectable_range(chain["pts"]):
            continue

        member_handles = [m["handle"] for m in chain["members"]]
        preliminary_majority = _majority_layer(chain["members"], edges_by_handle)
        preliminary_outliers = flag_foreign_line_outliers(
            chain["members"], preliminary_majority,
        )
        all_preliminary_outliers.extend(preliminary_outliers)
        nr, mat, anz = _merge_metadata(
            entity_by_handle, member_handles, read_curve_metadata,
        )
        export_primitives = _export_primitives_for_boundary(
            member_handles,
            entity_by_handle,
            chain["pts"],
            _entity_export_primitives,
            tolerance,
        )
        if not export_primitives:
            continue

        pending.append({
            "id": _boundary_id(member_handles),
            "member_handles": member_handles,
            "members": chain["members"],
            "is_composite": len(member_handles) > 1,
            "preliminary_majority": preliminary_majority,
            "preliminary_outliers": preliminary_outliers,
            "pts": chain["pts"],
            "export_primitives": export_primitives,
            "nr": nr,
            "mat": mat,
            "anz": anz,
        })

    closing_layer = infer_closing_layer(
        all_preliminary_outliers, edges_by_handle, _polyline_length,
    )

    raw = []
    for item in pending:
        if closing_layer:
            majority, outliers = classify_closing_lines(
                item["members"], closing_layer, edges_by_handle, _majority_layer,
            )
        else:
            majority = item["preliminary_majority"]
            outliers = item["preliminary_outliers"]

        raw.append({
            "id": item["id"],
            "member_handles": item["member_handles"],
            "members": item["members"],
            "is_composite": item["is_composite"],
            "majority_layer": majority,
            "layer_outliers": outliers,
            "has_layer_outliers": bool(outliers),
            "pts": item["pts"],
            "export_primitives": item["export_primitives"],
            "nr": item["nr"],
            "mat": item["mat"],
            "anz": item["anz"],
        })

    return _dedupe_boundaries(raw)


def resolve_preview_join_tolerance(doc, base=0.01, scale=1e-5):
    """Adaptive endpoint snap tolerance from modelspace curve extents."""
    from curve_geometry import flatten_entity_xy

    xs = []
    ys = []
    for entity in doc.modelspace():
        if entity.dxftype() not in CURVE_TYPES:
            continue
        for x, y in flatten_entity_xy(entity, base):
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return base
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    return max(base, diag * scale)


def find_join_chains(doc, tolerance=0.01):
    """
    Find endpoint-connected curve chains for DXF export join (open and closed).
    Returns (chains, edges_by_handle).
    """
    from curve_geometry import flatten_entity_xy as _flatten_entity_xy

    msp = doc.modelspace()
    edges, node_map = _collect_edges(
        msp,
        _flatten_entity_xy,
        tolerance,
        include_fn=_include_in_export_join,
    )
    chains = _build_chains(edges, node_map, tolerance, closed_only=False)

    edges_by_handle = {}
    for edge in edges:
        edges_by_handle.setdefault(edge["handle"], []).append(edge)

    for chain in chains:
        chain["member_handles"] = [m["handle"] for m in chain["members"]]

    return chains, edges_by_handle


def _extract_entity_xdata(source):
    try:
        xdata = source.xdata
    except AttributeError:
        return []
    if not xdata:
        return []

    data = getattr(xdata, "data", None)
    if not data:
        return []

    payload = []
    for app_name in data:
        try:
            tags = source.get_xdata(app_name)
            payload.append((app_name, [(tag.code, tag.value) for tag in tags]))
        except (AttributeError, KeyError, ValueError):
            continue
    return payload


def _apply_entity_xdata(target, xdata_payload):
    for app_name, tags in xdata_payload:
        try:
            target.set_xdata(app_name, tags)
        except (AttributeError, KeyError, ValueError):
            continue


def _copy_entity_xdata(source, target):
    _apply_entity_xdata(target, _extract_entity_xdata(source))


def apply_curve_join_to_document(doc, tolerance=0.01) -> int:
    """
    Join composite endpoint-connected curve chains in-place (Rhino Join behavior).
    Returns the number of joined groups written.
    """
    from curve_geometry import read_curve_metadata

    chains, edges_by_handle = find_join_chains(doc, tolerance)
    composites = [chain for chain in chains if chain["is_composite"]]
    if not composites:
        return 0

    msp = doc.modelspace()
    entity_by_handle = {}
    for entity in msp:
        if entity.dxftype() in CURVE_TYPES:
            entity_by_handle[str(entity.dxf.handle)] = entity

    replacements = []
    to_delete = []

    for chain in composites:
        member_handles = chain["member_handles"]
        sources = [
            entity_by_handle[handle]
            for handle in member_handles
            if handle in entity_by_handle
        ]
        if not sources:
            continue

        layer = _majority_layer(chain["members"], edges_by_handle) or "0"
        pts_2d = [(float(x), float(y)) for x, y in chain["pts"]]
        is_closed = chain["is_closed"]
        if is_closed and len(pts_2d) > 1 and _points_close(pts_2d[0], pts_2d[-1], tolerance):
            pts_2d = pts_2d[:-1]
        if len(pts_2d) < 2:
            continue

        xdata_source = None
        for handle in member_handles:
            entity = entity_by_handle.get(handle)
            if entity and read_curve_metadata(entity):
                xdata_source = entity
                break
        if xdata_source is None:
            xdata_source = sources[0]

        style_source = sources[0]
        color = getattr(style_source.dxf, "color", None)
        linetype = getattr(style_source.dxf, "linetype", None)
        xdata_payload = _extract_entity_xdata(xdata_source)
        replacements.append({
            "points": pts_2d,
            "layer": layer,
            "closed": is_closed,
            "xdata_payload": xdata_payload,
            "color": color,
            "linetype": linetype,
        })
        to_delete.extend(sources)

    if not replacements:
        return 0

    for entity in to_delete:
        msp.delete_entity(entity)

    joined = 0
    for item in replacements:
        if item["layer"] not in doc.layers:
            doc.layers.add(item["layer"])

        attribs = {"layer": item["layer"]}
        color = item["color"]
        if color not in (None, 256):
            attribs["color"] = color
        linetype = item["linetype"]
        if linetype:
            attribs["linetype"] = linetype

        poly = msp.add_lwpolyline(item["points"], format="xy", dxfattribs=attribs)
        if item["closed"]:
            poly.closed = True
        _apply_entity_xdata(poly, item["xdata_payload"])
        joined += 1

    return joined


def boundaries_for_api(doc, tolerance=0.01, raw=None):
    """Closed boundaries from join detection, JSON-ready for the frontend."""
    boundaries = []
    for b in (raw if raw is not None else find_boundaries(doc, tolerance)):
        pts = [{"x": float(x), "y": float(y)} for x, y in b["pts"]]
        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        boundaries.append({
            "id": b["id"],
            "memberHandles": b["member_handles"],
            "members": [
                {
                    "handle": m["handle"],
                    "layer": m["layer"],
                    "entityType": m["entity_type"],
                }
                for m in b["members"]
            ],
            "isComposite": b["is_composite"],
            "majorityLayer": b["majority_layer"],
            "layerOutliers": b["layer_outliers"],
            "hasLayerOutliers": b["has_layer_outliers"],
            "pts": pts,
            "bbox": {
                "minX": min_x,
                "maxX": max_x,
                "minY": min_y,
                "maxY": max_y,
                "centerX": (min_x + max_x) * 0.5,
                "centerY": (min_y + max_y) * 0.5,
            },
            "nr": b.get("nr") or "",
            "mat": b.get("mat") or "",
            "anz": b.get("anz") or "",
        })
    return boundaries


def load_dxf_document(path):
    """Load a DXF, recovering minor corruption when ezdxf allows it."""
    import ezdxf

    try:
        return ezdxf.readfile(path)
    except Exception:
        from ezdxf.recover import readfile

        doc, _auditor = readfile(path)
        return doc


def read_embedded_geometry(path, tolerance=0.01):
    """
    Part boundaries and related geometry from curve XData only.
    No text-label association — used for flattened 3D summon output.
    """
    from block_detection import find_block_inserts

    doc = load_dxf_document(path)
    return {
        "boundaries": boundaries_for_api(doc, tolerance),
        "blockInserts": find_block_inserts(doc),
        "schemeOutliers": find_scheme_outliers(doc),
    }
