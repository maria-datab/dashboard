# Rhino Python script
# Finds closed curves and text objects, groups Nr/Anz/Mat labels,
# assigns each label group to one closed curve,
# exports each required quantity as DXF with two blue layers,
# writes CSV reports,
# then deletes the temporary export layers.

import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System
import os
import re
import csv
import math

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

MATERIAL_TO_EXPORT = "3-Schicht"

LAYER_ROUGH = "OUTSIDE_MASS_T201_Z10"
LAYER_FINAL = "OUTSIDE_MASS_FINAL_T202_ZM02"

CSV_EXPORTS = "exported_dxf_files.csv"
CSV_PARTS = "parts_overview.csv"
CSV_WARNINGS = "assignment_warnings.csv"
CSV_ASSIGNMENT = "text_assignment_debug.csv"

KEEP_TEMP_LAYERS_FOR_DEBUG = False


# ------------------------------------------------------------
# BASIC HELPERS
# ------------------------------------------------------------

def normalize_value(value):
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def normalize_material(value):
    return normalize_value(value).lower()


def safe_filename(name):
    name = normalize_value(name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)

    if not name:
        name = "UNNAMED"

    return name


def ensure_layer(layer_name, color=None):
    index = sc.doc.Layers.FindByFullPath(layer_name, -1)

    if index >= 0:
        layer = sc.doc.Layers[index]

        if color is not None:
            layer.Color = color
            sc.doc.Layers.Modify(layer, index, True)

        return index

    layer = Rhino.DocObjects.Layer()
    layer.Name = layer_name

    if color is not None:
        layer.Color = color

    return sc.doc.Layers.Add(layer)


def delete_layer_if_exists(layer_name):
    index = sc.doc.Layers.FindByFullPath(layer_name, -1)

    if index >= 0:
        sc.doc.Layers.Delete(index, True)


def get_text_string(obj):
    geo = obj.Geometry

    if hasattr(geo, "PlainText"):
        return geo.PlainText

    if hasattr(geo, "Text"):
        return geo.Text

    if hasattr(geo, "RichText"):
        return geo.RichText

    return ""


def get_text_point(obj):
    geo = obj.Geometry

    if hasattr(geo, "Plane"):
        return geo.Plane.Origin

    bbox = geo.GetBoundingBox(True)
    return bbox.Center


def average_points(points):
    if not points:
        return rg.Point3d.Origin

    x = sum(p.X for p in points) / float(len(points))
    y = sum(p.Y for p in points) / float(len(points))
    z = sum(p.Z for p in points) / float(len(points))

    return rg.Point3d(x, y, z)


def closest_distance_to_curve(curve, point):
    success, t = curve.ClosestPoint(point)

    if not success:
        return float("inf")

    pt = curve.PointAt(t)
    return pt.DistanceTo(point)


def curve_area(curve):
    amp = rg.AreaMassProperties.Compute(curve)

    if amp:
        return abs(amp.Area)

    return float("inf")


def curve_center(curve):
    bbox = curve.GetBoundingBox(True)
    return bbox.Center


def point_is_inside_curve(curve, point):
    tol = sc.doc.ModelAbsoluteTolerance

    plane_success, plane = curve.TryGetPlane()

    if not plane_success:
        plane = rg.Plane.WorldXY

    containment = curve.Contains(point, plane, tol)

    return containment == rg.PointContainment.Inside or \
           containment == rg.PointContainment.Coincident


# ------------------------------------------------------------
# TEXT PARSING
# ------------------------------------------------------------

def classify_text(text):
    """
    Returns NR, ANZ, MAT, or empty string.

    Accepts:
    Nr.: 4000
    NR: 4000
    Anz.: 2
    Mat.: 3-Schicht
    """
    if not text:
        return ""

    match = re.match(r"^\s*(NR|ANZ|MAT)\s*\.?\s*:", text, re.IGNORECASE)

    if not match:
        return ""

    return match.group(1).upper()


def parse_field(text, key):
    """
    Parses fields from combined multiline text.

    Example:
    Nr.: 4008
    Anz.: 3
    Mat.: 3-Schicht
    """
    key_clean = key.replace(".", "")

    pattern = (
        r"{0}\s*\.?\s*:\s*"
        r"(.*?)"
        r"(?=(?:NR|ANZ|MAT)\s*\.?\s*:|$)"
    ).format(re.escape(key_clean))

    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if not match:
        return ""

    value = match.group(1).strip()
    value = re.sub(r"[\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_part_info(text):
    nr = parse_field(text, "NR")
    anz = parse_field(text, "ANZ")
    mat = parse_field(text, "MAT")

    name = safe_filename(nr)

    qty_match = re.search(r"\d+", anz)
    quantity = int(qty_match.group(0)) if qty_match else 1

    material = mat.strip()

    return name, quantity, material


def make_text_record(obj):
    text = get_text_string(obj)
    point = get_text_point(obj)
    key = classify_text(text)

    return {
        "id": str(obj.Id),
        "object": obj,
        "text": text,
        "point": point,
        "key": key
    }


def greedy_match_nearest(anchor_records, candidate_records):
    """
    One-to-one nearest matching.
    Used to bind ANZ and MAT texts to their nearest NR text.
    """
    pairs = []

    for anchor in anchor_records:
        for candidate in candidate_records:
            d = anchor["point"].DistanceTo(candidate["point"])
            pairs.append((d, anchor["id"], candidate["id"]))

    pairs.sort(key=lambda x: x[0])

    anchor_to_candidate = {}
    used_candidates = set()

    for d, anchor_id, candidate_id in pairs:
        if anchor_id in anchor_to_candidate:
            continue

        if candidate_id in used_candidates:
            continue

        anchor_to_candidate[anchor_id] = candidate_id
        used_candidates.add(candidate_id)

    return anchor_to_candidate, used_candidates


def build_label_groups(text_objects):
    """
    Groups separate Nr / Anz / Mat text entities before assigning to curves.
    """
    all_records = []
    ignored_records = []

    for obj in text_objects:
        rec = make_text_record(obj)

        if rec["key"] in ("NR", "ANZ", "MAT"):
            all_records.append(rec)
        else:
            ignored_records.append(rec)

    nr_records = [r for r in all_records if r["key"] == "NR"]
    anz_records = [r for r in all_records if r["key"] == "ANZ"]
    mat_records = [r for r in all_records if r["key"] == "MAT"]

    by_id = {}

    for rec in all_records:
        by_id[rec["id"]] = rec

    nr_to_anz, used_anz = greedy_match_nearest(nr_records, anz_records)
    nr_to_mat, used_mat = greedy_match_nearest(nr_records, mat_records)

    groups = []
    grouping_debug = []

    order = {
        "NR": 0,
        "ANZ": 1,
        "MAT": 2
    }

    for nr in nr_records:
        group_records = [nr]

        anz_id = nr_to_anz.get(nr["id"])
        mat_id = nr_to_mat.get(nr["id"])

        if anz_id and anz_id in by_id:
            group_records.append(by_id[anz_id])

        if mat_id and mat_id in by_id:
            group_records.append(by_id[mat_id])

        group_records.sort(key=lambda r: order.get(r["key"], 99))

        combined_text = "\n".join(r["text"] for r in group_records)
        center = average_points([r["point"] for r in group_records])

        group = {
            "id": nr["id"],
            "records": group_records,
            "text": combined_text,
            "point": center
        }

        groups.append(group)

        grouping_debug.append([
            nr["id"],
            ",".join(r["key"] for r in group_records),
            combined_text.replace("\n", " | ")
        ])

    for rec in anz_records:
        if rec["id"] not in used_anz:
            grouping_debug.append([
                rec["id"],
                "ORPHAN_ANZ",
                rec["text"].replace("\n", " | ")
            ])

    for rec in mat_records:
        if rec["id"] not in used_mat:
            grouping_debug.append([
                rec["id"],
                "ORPHAN_MAT",
                rec["text"].replace("\n", " | ")
            ])

    return groups, grouping_debug, ignored_records


def assign_label_groups_to_curves(curve_objects, label_groups):
    """
    Assigns label groups to curves one-to-one.

    Priority:
    1. Label point inside a closed curve
    2. Nearest curve distance
    """
    assignment = {}
    debug_rows = []

    curve_areas = {}
    curve_centers = {}

    for curve_obj in curve_objects:
        curve_id = str(curve_obj.Id)
        assignment[curve_id] = None
        curve_areas[curve_id] = curve_area(curve_obj.Geometry)
        curve_centers[curve_id] = curve_center(curve_obj.Geometry)

    pairs = []

    for gi, group in enumerate(label_groups):
        point = group["point"]

        for ci, curve_obj in enumerate(curve_objects):
            curve = curve_obj.Geometry
            curve_id = str(curve_obj.Id)

            inside = point_is_inside_curve(curve, point)

            if inside:
                priority = 0
                area_score = curve_areas.get(curve_id, float("inf"))
                distance = point.DistanceTo(curve_centers[curve_id])
                method = "inside"
            else:
                priority = 1
                area_score = float("inf")
                distance = closest_distance_to_curve(curve, point)
                method = "nearest"

            pairs.append((
                priority,
                area_score,
                distance,
                gi,
                ci,
                method
            ))

    pairs.sort(key=lambda x: (x[0], x[1], x[2]))

    used_groups = set()
    used_curves = set()

    for priority, area_score, distance, gi, ci, method in pairs:
        if gi in used_groups:
            continue

        if ci in used_curves:
            continue

        group = label_groups[gi]
        curve_obj = curve_objects[ci]
        curve_id = str(curve_obj.Id)

        assignment[curve_id] = group

        used_groups.add(gi)
        used_curves.add(ci)

        debug_rows.append([
            group["id"],
            curve_id,
            method,
            distance,
            group["text"].replace("\n", " | ")
        ])

    for gi, group in enumerate(label_groups):
        if gi not in used_groups:
            debug_rows.append([
                group["id"],
                "",
                "UNASSIGNED_GROUP",
                "",
                group["text"].replace("\n", " | ")
            ])

    return assignment, debug_rows


# ------------------------------------------------------------
# CSV
# ------------------------------------------------------------

def write_csv(path, rows, headers):
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)

            for row in rows:
                writer.writerow(["" if value is None else str(value) for value in row])

    except TypeError:
        with open(path, "w") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)

            for row in rows:
                writer.writerow(["" if value is None else str(value) for value in row])


# ------------------------------------------------------------
# DXF WRITER BASED ON YOUR UPLOADED EXPORT CODE
# ------------------------------------------------------------

_dxf_buf = []
_dxf_handle = [0x40]


def dxf_g(code, value):
    """
    Append one DXF group code/value pair.
    """
    _dxf_buf.append("%3d" % code)

    if isinstance(value, float):
        s = "%.15g" % value

        if "." not in s and "e" not in s.lower():
            s += ".0"

        _dxf_buf.append(s)
    else:
        _dxf_buf.append(str(value))


def dxf_nh():
    """
    Next unique DXF handle.
    """
    _dxf_handle[0] += 1
    return format(_dxf_handle[0], "X")


def dxf_reset():
    global _dxf_buf
    _dxf_buf = []
    _dxf_handle[0] = 0x40


def dxf_head(etype, layer, owner):
    dxf_g(0, etype)
    dxf_g(5, dxf_nh())
    dxf_g(330, owner)
    dxf_g(100, "AcDbEntity")
    dxf_g(8, layer)


def dxf_write_line(p0, p1, layer, owner):
    dxf_head("LINE", layer, owner)
    dxf_g(100, "AcDbLine")
    dxf_g(10, p0.X)
    dxf_g(20, p0.Y)
    dxf_g(30, p0.Z)
    dxf_g(11, p1.X)
    dxf_g(21, p1.Y)
    dxf_g(31, p1.Z)


def dxf_write_circle(center, radius, layer, owner):
    dxf_head("CIRCLE", layer, owner)
    dxf_g(100, "AcDbCircle")
    dxf_g(10, center.X)
    dxf_g(20, center.Y)
    dxf_g(30, center.Z)
    dxf_g(40, radius)


def dxf_write_arc(center, radius, start_deg, end_deg, layer, owner, normal=None):
    dxf_head("ARC", layer, owner)
    dxf_g(100, "AcDbCircle")
    dxf_g(10, center.X)
    dxf_g(20, center.Y)
    dxf_g(30, center.Z)
    dxf_g(40, radius)
    dxf_g(100, "AcDbArc")
    dxf_g(50, start_deg)
    dxf_g(51, end_deg)

    if normal and (
        abs(normal.X) > 1e-9 or
        abs(normal.Y) > 1e-9 or
        abs(normal.Z - 1.0) > 1e-9
    ):
        dxf_g(210, normal.X)
        dxf_g(220, normal.Y)
        dxf_g(230, normal.Z)


def dxf_write_lwpolyline(pts_2d, closed, elevation, layer, owner):
    dxf_head("LWPOLYLINE", layer, owner)
    dxf_g(100, "AcDbPolyline")
    dxf_g(90, len(pts_2d))
    dxf_g(70, 1 if closed else 0)
    dxf_g(43, 0.0)
    dxf_g(38, elevation)
    dxf_g(39, 0.0)

    for x, y in pts_2d:
        dxf_g(10, float(x))
        dxf_g(20, float(y))


def dxf_pts_to_entity(pts, is_closed, layer, owner, tol):
    """
    Write points as flat LWPOLYLINE if possible, otherwise 3D LINE segments.
    """
    if not pts or len(pts) < 2:
        return

    zs = [p.Z for p in pts]

    if (max(zs) - min(zs)) < tol:
        pts_2d = [(p.X, p.Y) for p in pts]

        if is_closed and len(pts_2d) > 1:
            if pts[0].DistanceTo(pts[-1]) <= tol:
                pts_2d = pts_2d[:-1]

        if len(pts_2d) >= 2:
            dxf_write_lwpolyline(pts_2d, is_closed, zs[0], layer, owner)

    else:
        for i in range(len(pts) - 1):
            dxf_write_line(pts[i], pts[i + 1], layer, owner)

        if is_closed and len(pts) > 1:
            dxf_write_line(pts[-1], pts[0], layer, owner)


def dxf_arc_to_entity(arc, layer, owner):
    """
    Write Rhino Arc as DXF CIRCLE or ARC.
    """
    if arc.IsCircle:
        dxf_write_circle(arc.Center, arc.Radius, layer, owner)
    else:
        cx = arc.Center.X
        cy = arc.Center.Y

        start_deg = math.degrees(
            math.atan2(arc.StartPoint.Y - cy, arc.StartPoint.X - cx)
        ) % 360.0

        end_deg = math.degrees(
            math.atan2(arc.EndPoint.Y - cy, arc.EndPoint.X - cx)
        ) % 360.0

        if arc.Plane.Normal.Z < 0:
            start_deg, end_deg = end_deg, start_deg

        dxf_write_arc(
            arc.Center,
            arc.Radius,
            start_deg,
            end_deg,
            layer,
            owner
        )


def dxf_curve_midpoint(curve):
    """
    Safe midpoint for arc reconstruction.
    """
    try:
        success, t = curve.NormalizedLengthParameter(0.5)

        if success:
            return curve.PointAt(t)
    except:
        pass

    try:
        domain = curve.Domain
        t = 0.5 * (domain.T0 + domain.T1)
        return curve.PointAt(t)
    except:
        return curve.PointAtStart


def dxf_export_curve(curve, layer, owner):
    """
    Dispatch Rhino curve to DXF entity writer.
    Based on your uploaded exporter, adapted for automatic batch export.
    """
    tol = sc.doc.ModelAbsoluteTolerance

    if tol <= 0.0:
        tol = 0.01

    # PolyCurve: recurse into segments
    if isinstance(curve, rg.PolyCurve):
        for i in range(curve.SegmentCount):
            dxf_export_curve(curve.SegmentCurve(i), layer, owner)
        return

    # LineCurve
    if isinstance(curve, rg.LineCurve):
        dxf_write_line(curve.Line.From, curve.Line.To, layer, owner)
        return

    # ArcCurve
    if isinstance(curve, rg.ArcCurve):
        dxf_arc_to_entity(curve.Arc, layer, owner)
        return

    # PolylineCurve
    if isinstance(curve, rg.PolylineCurve):
        pts = [curve.Point(i) for i in range(curve.PointCount)]
        dxf_pts_to_entity(pts, curve.IsClosed, layer, owner, tol)
        return

    # Linear Nurbs / generic curve
    try:
        if curve.IsLinear(tol):
            dxf_write_line(curve.PointAtStart, curve.PointAtEnd, layer, owner)
            return
    except:
        pass

    # Arc-like Nurbs / generic curve
    try:
        if curve.IsArc(tol):
            mid = dxf_curve_midpoint(curve)
            arc = rg.Arc(curve.PointAtStart, mid, curve.PointAtEnd)

            if arc.IsValid:
                dxf_arc_to_entity(arc, layer, owner)
                return
    except:
        pass

    # Tessellate everything else
    try:
        pl = curve.ToPolyline(0, 0, 0.1, 0.0, 0.0, 0.0, 0.0, tol, True)

        if pl is not None:
            dxf_export_curve(pl, layer, owner)
            return

    except:
        pass

    # Last-resort sampling. The emergency exit. Not elegant, but neither is CNC at 17:59.
    try:
        length = curve.GetLength()
    except:
        length = 1000.0

    n = max(16, min(1000, int(length / max(tol, 0.01))))

    try:
        params = curve.DivideByCount(n, True)

        if params:
            pts = [curve.PointAt(t) for t in params]
            dxf_pts_to_entity(pts, curve.IsClosed, layer, owner, tol)

    except:
        pass


def dxf_write_header(bbox):
    dxf_g(0, "SECTION")
    dxf_g(2, "HEADER")

    dxf_g(9, "$ACADVER")
    dxf_g(1, "AC1015")

    dxf_g(9, "$DWGCODEPAGE")
    dxf_g(3, "ANSI_1252")

    dxf_g(9, "$INSBASE")
    dxf_g(10, 0.0)
    dxf_g(20, 0.0)
    dxf_g(30, 0.0)

    dxf_g(9, "$EXTMIN")
    dxf_g(10, bbox.Min.X)
    dxf_g(20, bbox.Min.Y)
    dxf_g(30, bbox.Min.Z)

    dxf_g(9, "$EXTMAX")
    dxf_g(10, bbox.Max.X)
    dxf_g(20, bbox.Max.Y)
    dxf_g(30, bbox.Max.Z)

    dxf_g(9, "$LTSCALE")
    dxf_g(40, 1.0)

    dxf_g(9, "$MEASUREMENT")
    dxf_g(70, 1)

    dxf_g(0, "ENDSEC")


def dxf_write_tables(ms_rec, ps_rec, layers):
    """
    layers: list of (dxf_name, aci_color)
    """
    dxf_g(0, "SECTION")
    dxf_g(2, "TABLES")

    # LTYPE
    dxf_g(0, "TABLE")
    dxf_g(2, "LTYPE")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTable")
    dxf_g(70, 1)

    dxf_g(0, "LTYPE")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTableRecord")
    dxf_g(100, "AcDbLinetypeTableRecord")
    dxf_g(2, "CONTINUOUS")
    dxf_g(70, 0)
    dxf_g(3, "Solid line")
    dxf_g(72, 65)
    dxf_g(73, 0)
    dxf_g(40, 0.0)

    dxf_g(0, "ENDTAB")

    # LAYER
    all_layers = [("0", 7)] + layers

    dxf_g(0, "TABLE")
    dxf_g(2, "LAYER")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTable")
    dxf_g(70, len(all_layers))

    for name, color in all_layers:
        dxf_g(0, "LAYER")
        dxf_g(5, dxf_nh())
        dxf_g(100, "AcDbSymbolTableRecord")
        dxf_g(100, "AcDbLayerTableRecord")
        dxf_g(2, name)
        dxf_g(70, 0)
        dxf_g(62, color)
        dxf_g(6, "CONTINUOUS")

    dxf_g(0, "ENDTAB")

    # Required empty tables
    for tbl in ("STYLE", "VIEW", "UCS"):
        dxf_g(0, "TABLE")
        dxf_g(2, tbl)
        dxf_g(5, dxf_nh())
        dxf_g(100, "AcDbSymbolTable")
        dxf_g(70, 0)
        dxf_g(0, "ENDTAB")

    # APPID
    dxf_g(0, "TABLE")
    dxf_g(2, "APPID")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTable")
    dxf_g(70, 1)

    dxf_g(0, "APPID")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTableRecord")
    dxf_g(100, "AcDbRegAppTableRecord")
    dxf_g(2, "ACAD")
    dxf_g(70, 0)

    dxf_g(0, "ENDTAB")

    # DIMSTYLE
    dxf_g(0, "TABLE")
    dxf_g(2, "DIMSTYLE")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTable")
    dxf_g(70, 0)
    dxf_g(100, "AcDbDimStyleTable")
    dxf_g(0, "ENDTAB")

    # BLOCK_RECORD
    dxf_g(0, "TABLE")
    dxf_g(2, "BLOCK_RECORD")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbSymbolTable")
    dxf_g(70, 2)

    dxf_g(0, "BLOCK_RECORD")
    dxf_g(5, ms_rec)
    dxf_g(100, "AcDbSymbolTableRecord")
    dxf_g(100, "AcDbBlockTableRecord")
    dxf_g(2, "*MODEL_SPACE")

    dxf_g(0, "BLOCK_RECORD")
    dxf_g(5, ps_rec)
    dxf_g(100, "AcDbSymbolTableRecord")
    dxf_g(100, "AcDbBlockTableRecord")
    dxf_g(2, "*PAPER_SPACE")

    dxf_g(0, "ENDTAB")
    dxf_g(0, "ENDSEC")


def dxf_write_blocks(ms_rec, ps_rec):
    dxf_g(0, "SECTION")
    dxf_g(2, "BLOCKS")

    for rec, name in [(ms_rec, "*MODEL_SPACE"), (ps_rec, "*PAPER_SPACE")]:
        dxf_g(0, "BLOCK")
        dxf_g(5, dxf_nh())
        dxf_g(330, rec)
        dxf_g(100, "AcDbEntity")
        dxf_g(8, "0")
        dxf_g(100, "AcDbBlockBegin")
        dxf_g(2, name)
        dxf_g(70, 0)
        dxf_g(10, 0.0)
        dxf_g(20, 0.0)
        dxf_g(30, 0.0)
        dxf_g(3, name)
        dxf_g(1, "")

        dxf_g(0, "ENDBLK")
        dxf_g(5, dxf_nh())
        dxf_g(330, rec)
        dxf_g(100, "AcDbEntity")
        dxf_g(8, "0")
        dxf_g(100, "AcDbBlockEnd")

    dxf_g(0, "ENDSEC")


def dxf_write_objects():
    dxf_g(0, "SECTION")
    dxf_g(2, "OBJECTS")
    dxf_g(0, "DICTIONARY")
    dxf_g(5, dxf_nh())
    dxf_g(100, "AcDbDictionary")
    dxf_g(281, 1)
    dxf_g(0, "ENDSEC")


def dxf_sanitize_layer_name(name):
    for ch in '<>/\\:;"?*|=\'':
        name = name.replace(ch, "_")

    name = name.replace("::", "-")

    return name or "DEFAULT"


def write_curves_to_dxf(path, curve_layer_items):
    """
    Writes a DXF using the uploaded DXF writer logic.

    curve_layer_items:
        [(Rhino.Geometry.Curve, layer_name), ...]
    """
    if not curve_layer_items:
        return False

    try:
        bbox = rg.BoundingBox.Empty
        layer_map = {}
        work_items = []

        for curve, layer_name in curve_layer_items:
            if curve is None:
                continue

            if not isinstance(curve, rg.Curve):
                continue

            bbox.Union(curve.GetBoundingBox(True))

            dxf_layer_name = dxf_sanitize_layer_name(layer_name)

            # Blue ACI = 5
            if dxf_layer_name not in layer_map:
                layer_map[dxf_layer_name] = 5

            work_items.append((curve, dxf_layer_name))

        if not work_items:
            return False

        dxf_reset()

        ms_rec = dxf_nh()
        ps_rec = dxf_nh()

        layers_list = sorted(layer_map.items())

        dxf_write_header(bbox)
        dxf_write_tables(ms_rec, ps_rec, layers_list)
        dxf_write_blocks(ms_rec, ps_rec)

        dxf_g(0, "SECTION")
        dxf_g(2, "ENTITIES")

        for curve, layer_name in work_items:
            dxf_export_curve(curve, layer_name, ms_rec)

        dxf_g(0, "ENDSEC")

        dxf_write_objects()
        dxf_g(0, "EOF")

        content = "\r\n".join(_dxf_buf) + "\r\n"

        with open(path, "wb") as f:
            f.write(content.encode("ascii", "ignore"))

        return os.path.exists(path) and os.path.getsize(path) > 500

    except Exception as e:
        print("DXF writer failed for {}: {}".format(path, e))
        return False


def export_two_layer_dxf(filepath, curve_geo):
    """
    Export the same curve twice:
    once on OUTSIDE_MASS_T201_Z10
    once on OUTSIDE_MASS_FINAL_T202_ZM02
    """
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass

    curve_layer_items = [
        (curve_geo.DuplicateCurve(), LAYER_ROUGH),
        (curve_geo.DuplicateCurve(), LAYER_FINAL)
    ]

    success = write_curves_to_dxf(filepath, curve_layer_items)

    if success:
        return "OK_CUSTOM_DXF_WRITER"

    return "FAILED"


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    export_folder = rs.BrowseForFolder(
        message="Choose folder for exported DXF and CSV files"
    )

    if not export_folder:
        print("No export folder selected. Script cancelled.")
        return

    # Collect original closed curves.
    curve_objects = []

    for obj in sc.doc.Objects:
        if obj.ObjectType != Rhino.DocObjects.ObjectType.Curve:
            continue

        layer = sc.doc.Layers[obj.Attributes.LayerIndex]
        layer_name = layer.FullPath

        if layer_name == LAYER_ROUGH or layer_name == LAYER_FINAL:
            continue

        curve = obj.Geometry

        if curve and curve.IsClosed:
            curve_objects.append(obj)

    # Collect text objects.
    text_objects = []

    for obj in sc.doc.Objects:
        if obj.ObjectType == Rhino.DocObjects.ObjectType.Annotation:
            text = get_text_string(obj)

            if text and text.strip():
                text_objects.append(obj)

    if not curve_objects:
        print("No closed curves found.")
        return

    if not text_objects:
        print("No text entities found.")
        return

    # Temporary blue export layers in Rhino document.
    blue = System.Drawing.Color.Blue

    rough_layer_index = ensure_layer(LAYER_ROUGH, blue)
    final_layer_index = ensure_layer(LAYER_FINAL, blue)

    label_groups, grouping_debug, ignored_texts = build_label_groups(text_objects)

    curve_assignment, assignment_debug = assign_label_groups_to_curves(
        curve_objects,
        label_groups
    )

    exported_rows = []
    parts_rows = []
    warning_rows = []

    exported_count = 0
    failed_export_count = 0
    skipped_count = 0

    for curve_obj in curve_objects:
        curve_id = str(curve_obj.Id)
        group = curve_assignment.get(curve_id)

        if group:
            combined_text = group["text"]
        else:
            combined_text = ""

        name, quantity, material = parse_part_info(combined_text)

        missing = []

        if not name or name == "UNNAMED":
            name = "UNNAMED_{}".format(curve_id[:8])
            missing.append("NR")

        if not parse_field(combined_text, "ANZ"):
            missing.append("ANZ")

        if not material:
            missing.append("MAT")

        if quantity < 1:
            quantity = 1

        if missing:
            warning_rows.append([
                curve_id,
                name,
                quantity,
                material,
                ", ".join(missing),
                combined_text.replace("\n", " | ")
            ])

        parts_rows.append([
            name,
            quantity,
            material,
            curve_id,
            combined_text.replace("\n", " | ")
        ])

        if normalize_material(material) != normalize_material(MATERIAL_TO_EXPORT):
            skipped_count += 1
            continue

        curve_geo = curve_obj.Geometry.DuplicateCurve()

        # Create visible temporary copies on the two required blue layers.
        attr_rough = Rhino.DocObjects.ObjectAttributes()
        attr_final = Rhino.DocObjects.ObjectAttributes()

        attr_rough.LayerIndex = rough_layer_index
        attr_final.LayerIndex = final_layer_index

        try:
            attr_rough.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
            attr_final.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
        except:
            pass

        rough_id = sc.doc.Objects.AddCurve(curve_geo.DuplicateCurve(), attr_rough)
        final_id = sc.doc.Objects.AddCurve(curve_geo.DuplicateCurve(), attr_final)

        if rough_id == System.Guid.Empty or final_id == System.Guid.Empty:
            warning_rows.append([
                curve_id,
                name,
                quantity,
                material,
                "COPY_FAILED",
                combined_text.replace("\n", " | ")
            ])
            continue

        sc.doc.Views.Redraw()

        for i in range(1, quantity + 1):
            filename = "{}_{}.dxf".format(name, i)
            filepath = os.path.join(export_folder, filename)

            status = export_two_layer_dxf(filepath, curve_geo)

            exported_rows.append([
                filename,
                filepath,
                name,
                i,
                quantity,
                material,
                LAYER_ROUGH,
                LAYER_FINAL,
                status
            ])

            if status.startswith("OK"):
                exported_count += 1
            else:
                failed_export_count += 1

    sc.doc.Objects.UnselectAll()
    sc.doc.Views.Redraw()

    exports_csv_path = os.path.join(export_folder, CSV_EXPORTS)
    parts_csv_path = os.path.join(export_folder, CSV_PARTS)
    warnings_csv_path = os.path.join(export_folder, CSV_WARNINGS)
    assignment_csv_path = os.path.join(export_folder, CSV_ASSIGNMENT)

    write_csv(
        exports_csv_path,
        exported_rows,
        [
            "DXF Filename",
            "Full Path",
            "Part Name",
            "Export Number",
            "Total Quantity",
            "Material",
            "Layer 1",
            "Layer 2",
            "Status"
        ]
    )

    write_csv(
        parts_csv_path,
        parts_rows,
        [
            "Part Name",
            "Quantity",
            "Material",
            "Original Curve GUID",
            "Assigned Text"
        ]
    )

    write_csv(
        warnings_csv_path,
        warning_rows,
        [
            "Original Curve GUID",
            "Part Name",
            "Quantity",
            "Material",
            "Problem",
            "Assigned Text"
        ]
    )

    assignment_rows = []

    for row in assignment_debug:
        assignment_rows.append(row)

    for row in grouping_debug:
        assignment_rows.append([
            row[0],
            "",
            "TEXT_GROUP",
            row[1],
            row[2]
        ])

    write_csv(
        assignment_csv_path,
        assignment_rows,
        [
            "Label Group / Text GUID",
            "Assigned Curve GUID",
            "Assignment Method",
            "Distance / Group Keys",
            "Text"
        ]
    )

    if not KEEP_TEMP_LAYERS_FOR_DEBUG:
        sc.doc.Objects.UnselectAll()
        delete_layer_if_exists(LAYER_ROUGH)
        delete_layer_if_exists(LAYER_FINAL)
        sc.doc.Views.Redraw()

    print("Done.")
    print("Closed curves found: {}".format(len(curve_objects)))
    print("Text entities found: {}".format(len(text_objects)))
    print("Label groups built from NR texts: {}".format(len(label_groups)))
    print("DXFs exported: {}".format(exported_count))
    print("DXFs failed: {}".format(failed_export_count))
    print("Parts skipped because material is not '{}': {}".format(
        MATERIAL_TO_EXPORT,
        skipped_count
    ))
    print("CSV export list: {}".format(exports_csv_path))
    print("CSV parts overview: {}".format(parts_csv_path))
    print("CSV warnings: {}".format(warnings_csv_path))
    print("CSV assignment debug: {}".format(assignment_csv_path))

    if KEEP_TEMP_LAYERS_FOR_DEBUG:
        print("Temporary layers kept for debugging.")
    else:
        print("Temporary layers deleted:")
        print(" - {}".format(LAYER_ROUGH))
        print(" - {}".format(LAYER_FINAL))


if __name__ == "__main__":
    main()