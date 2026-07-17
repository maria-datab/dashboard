"""Tier-0 curve geometry read helpers (extracted from main.py for dev core)."""

import math

METADATA_KEYS = frozenset({"Nr", "Mat", "Anz"})
XDATA_VALUE_CODES = frozenset({1000, 1040, 1070, 1071})


def _point3d(x, y, z=0.0):
    return (float(x), float(y), float(z))


def _point3d_distance_to(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.hypot(dx, dy, dz)


def get_entity_xdata_tags(entity):
    try:
        xdata = entity.xdata
    except AttributeError:
        return []
    if not xdata:
        return []

    data = getattr(xdata, "data", None)
    if not data:
        return []

    app_name = next(iter(data))
    try:
        tags = entity.get_xdata(app_name)
    except (AttributeError, KeyError):
        return []

    return [(tag.code, tag.value) for tag in tags]


def read_curve_metadata(entity):
    tags = get_entity_xdata_tags(entity)
    if not tags:
        return {}

    metadata = {}
    for i, (code, value) in enumerate(tags):
        if code != 1000 or value not in METADATA_KEYS:
            continue
        if i + 1 >= len(tags):
            continue
        next_code, next_val = tags[i + 1]
        if next_code not in XDATA_VALUE_CODES:
            continue
        metadata[value] = str(next_val).strip()

    return metadata


def _dxf_point3d(vec):
    return _point3d(float(vec.x), float(vec.y), float(getattr(vec, "z", 0.0) or 0.0))


def flatten_entity_xy(entity, tolerance):
    from ezdxf import path as ezpath

    p = ezpath.make_path(entity)
    return [(float(v.x), float(v.y)) for v in p.flattening(distance=tolerance)]


def entity_export_primitives(entity, tolerance):
    dxftype = entity.dxftype()

    if dxftype == "LINE":
        return [
            ("LINE", _dxf_point3d(entity.dxf.start), _dxf_point3d(entity.dxf.end))
        ]

    if dxftype == "CIRCLE":
        return [
            (
                "CIRCLE",
                _dxf_point3d(entity.dxf.center),
                float(entity.dxf.radius),
            )
        ]

    if dxftype == "ARC":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        cx = float(center.x)
        cy = float(center.y)
        start_deg = math.degrees(
            math.atan2(float(entity.start_point.y) - cy, float(entity.start_point.x) - cx)
        ) % 360.0
        end_deg = math.degrees(
            math.atan2(float(entity.end_point.y) - cy, float(entity.end_point.x) - cx)
        ) % 360.0

        return [
            ("ARC", _dxf_point3d(center), radius, start_deg, end_deg)
        ]

    if dxftype == "LWPOLYLINE":
        pts_2d = [(float(x), float(y)) for x, y, *_ in entity.get_points("xyseb")]
        z = float(getattr(entity.dxf, "elevation", 0.0) or 0.0)
        closed = bool(entity.closed)

        if closed and len(pts_2d) > 1 and pts_2d[0] == pts_2d[-1]:
            pts_2d = pts_2d[:-1]

        return [("LWPOLYLINE", pts_2d, closed, z)]

    if dxftype in ("POLYLINE", "POLYLINE3D"):
        pts = [_dxf_point3d(v.dxf.location) for v in entity.vertices]
        closed = bool(entity.is_closed)

        if closed and len(pts) > 1 and _point3d_distance_to(pts[0], pts[-1]) <= tolerance:
            pts = pts[:-1]

        return [("POLYLINE3D", pts, closed)]

    boundary = flatten_entity_xy(entity, tolerance)

    if len(boundary) < 2:
        return []

    pts = [_point3d(x, y, 0.0) for x, y in boundary]
    return [("POLYLINE3D", pts, True)]
