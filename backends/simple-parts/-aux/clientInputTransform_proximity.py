#!/usr/bin/env python3
"""
Read client DXF, assign Nr/Anz/Mat labels to closed curves,
export quantity-based CNC DXFs and CSV reports.

Usage:
    1) Set INPUT_DXF, OUTPUT_DIR and other values in SETTINGS.
    2) Run: python clientInputTransform_independent.py

OUTPUT_DIR must already exist.
"""

import os
import re
import csv
import math
import sys

from dxf_writer import point3d, point3d_distance_to, write_primitives_to_dxf

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

DEFAULT_TOLERANCE = 0.01

# Source DXF file:
INPUT_DXF = "G:\\Shared drives\\CEB\\Projects\\SimpleParts\\test\\rhino-independent-code\\input\\ClientInputExample.dxf"

# Output folder for DXF and CSV files (must already exist):
OUTPUT_DIR = "G:\\Shared drives\\CEB\\Projects\\SimpleParts\\test\\rhino-independent-code\\output"


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

#removed helpers:
#ensure_layer
#delete_layer_if_exists
#get_text_string
#get_text_point

# ------------------------------------------------------------
# GEOMETRY HELPERS
# ------------------------------------------------------------

def average_points(points):
    if not points:
        return point3d()

    x = sum(p["X"] for p in points) / float(len(points))
    y = sum(p["Y"] for p in points) / float(len(points))
    z = sum(p["Z"] for p in points) / float(len(points))

    return point3d(x, y, z)


def _distance_point_to_segment_sq(px, py, x0, y0, x1, y1):
    dx = x1 - x0
    dy = y1 - y0

    if dx == 0.0 and dy == 0.0:
        ddx = px - x0
        ddy = py - y0
        return ddx * ddx + ddy * ddy

    t = ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    proj_x = x0 + t * dx
    proj_y = y0 + t * dy
    ddx = px - proj_x
    ddy = py - proj_y

    return ddx * ddx + ddy * ddy


def closest_distance_to_curve(curve, point):
    boundary_xy = curve["boundary_xy"]

    if not boundary_xy:
        return float("inf")

    px = point["X"]
    py = point["Y"]
    min_dist_sq = float("inf")
    n = len(boundary_xy)

    for i in range(n):
        x0, y0 = boundary_xy[i]
        x1, y1 = boundary_xy[(i + 1) % n]
        dist_sq = _distance_point_to_segment_sq(px, py, x0, y0, x1, y1)

        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq

    return math.sqrt(min_dist_sq)


def curve_center(curve):
    boundary_xy = curve["boundary_xy"]

    if not boundary_xy:
        return point3d()

    xs = [p[0] for p in boundary_xy]
    ys = [p[1] for p in boundary_xy]

    return point3d(
        (min(xs) + max(xs)) * 0.5,
        (min(ys) + max(ys)) * 0.5,
        0.0,
    )


def curve_area(curve):
    boundary_xy = curve["boundary_xy"]

    if len(boundary_xy) < 3:
        return float("inf")

    area = 0.0
    n = len(boundary_xy)

    for i in range(n):
        x0, y0 = boundary_xy[i]
        x1, y1 = boundary_xy[(i + 1) % n]
        area += x0 * y1 - x1 * y0

    return abs(area) * 0.5


def point_is_inside_curve(curve, point, tol=1e-9):
    boundary_xy = curve["boundary_xy"]
    px = point["X"]
    py = point["Y"]

    if len(boundary_xy) >= 2:
        tol_sq = tol * tol
        n = len(boundary_xy)

        for i in range(n):
            x0, y0 = boundary_xy[i]
            x1, y1 = boundary_xy[(i + 1) % n]

            if _distance_point_to_segment_sq(px, py, x0, y0, x1, y1) <= tol_sq:
                return True

    if len(boundary_xy) < 3:
        return False

    inside = False
    n = len(boundary_xy)
    j = n - 1

    for i in range(n):
        xi, yi = boundary_xy[i]
        xj, yj = boundary_xy[j]

        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside

        j = i

    return inside


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


def greedy_match_nearest(anchor_records, candidate_records):
    """
    One-to-one nearest matching.
    Used to bind ANZ and MAT texts to their nearest NR text.
    """
    pairs = []

    for anchor in anchor_records:
        for candidate in candidate_records:
            d = point3d_distance_to(anchor["point"], candidate["point"])
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

    for obj in text_objects:
        rec = {
            "id": obj["id"],
            "text": obj["text"],
            "point": obj["point"],
            "key": classify_text(obj["text"]),
        }

        if rec["key"] in ("NR", "ANZ", "MAT"):
            all_records.append(rec)

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

    return groups, grouping_debug


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
        curve_id = curve_obj["id"]
        assignment[curve_id] = None
        curve_areas[curve_id] = curve_area(curve_obj)
        curve_centers[curve_id] = curve_center(curve_obj)

    pairs = []

    for gi, group in enumerate(label_groups):
        point = group["point"]

        for ci, curve_obj in enumerate(curve_objects):
            curve = curve_obj
            curve_id = curve_obj["id"]

            inside = point_is_inside_curve(curve, point)

            if inside:
                priority = 0
                area_score = curve_areas.get(curve_id, float("inf"))
                distance = point3d_distance_to(point, curve_centers[curve_id])
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
        curve_id = curve_obj["id"]

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
# DXF READER
# ------------------------------------------------------------

def _dxf_point3d(vec):
    return point3d(float(vec.x), float(vec.y), float(getattr(vec, "z", 0.0) or 0.0))


def _flatten_entity_xy(entity, tolerance):
    from ezdxf import path as ezpath

    p = ezpath.make_path(entity)
    return [(float(v.x), float(v.y)) for v in p.flattening(distance=tolerance)]


def _entity_boundary_xy(entity, tolerance):
    dxftype = entity.dxftype()

    if dxftype == "CIRCLE":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        cx = float(center.x)
        cy = float(center.y)
        segments = 32

        return [
            (
                cx + radius * math.cos(2.0 * math.pi * i / segments),
                cy + radius * math.sin(2.0 * math.pi * i / segments),
            )
            for i in range(segments)
        ]

    if dxftype == "ARC":
        return _flatten_entity_xy(entity, tolerance)

    if dxftype == "LWPOLYLINE":
        pts = [(float(x), float(y)) for x, y, *_ in entity.get_points("xyseb")]

        if entity.closed and pts and pts[0] != pts[-1]:
            pts = pts + [pts[0]]

        return pts

    if dxftype in ("POLYLINE", "POLYLINE3D"):
        pts = [
            (float(v.dxf.location.x), float(v.dxf.location.y))
            for v in entity.vertices
        ]

        if entity.is_closed and pts and pts[0] != pts[-1]:
            pts = pts + [pts[0]]

        return pts

    return _flatten_entity_xy(entity, tolerance)


def _entity_export_primitives(entity, tolerance):
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

        if closed and len(pts) > 1 and point3d_distance_to(pts[0], pts[-1]) <= tolerance:
            pts = pts[:-1]

        return [("POLYLINE3D", pts, closed)]

    boundary = _flatten_entity_xy(entity, tolerance)

    if len(boundary) < 2:
        return []

    pts = [point3d(x, y, 0.0) for x, y in boundary]
    return [("POLYLINE3D", pts, True)]


def _entity_is_closed_boundary(entity):
    dxftype = entity.dxftype()

    if dxftype == "CIRCLE":
        return True

    if dxftype == "LWPOLYLINE":
        return bool(entity.closed)

    if dxftype in ("POLYLINE", "POLYLINE3D"):
        return bool(entity.is_closed)

    if dxftype == "ELLIPSE":
        return True

    return False


def read_dxf(path, tolerance=DEFAULT_TOLERANCE):
    """
    Load closed boundary curves and text labels from a client DXF file.

    Returns (curve_objects, text_objects).
    """
    import ezdxf

    try:
        doc = ezdxf.readfile(path)
    except Exception:
        from ezdxf.recover import readfile

        doc, auditor = readfile(path)

        if auditor.has_errors:
            print("Warning: DXF recovered with errors in {}".format(path))

    msp = doc.modelspace()

    curve_objects = []
    text_objects = []

    for entity in msp:
        layer = entity.dxf.layer

        if entity.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE", "POLYLINE3D", "CIRCLE", "ARC", "ELLIPSE", "SPLINE"):
            if not _entity_is_closed_boundary(entity):
                continue

            boundary_xy = _entity_boundary_xy(entity, tolerance)

            if len(boundary_xy) < 3:
                continue

            curve_objects.append({
                "id": str(entity.dxf.handle),
                "layer": layer,
                "boundary_xy": boundary_xy,
                "export_primitives": _entity_export_primitives(entity, tolerance),
            })

        elif entity.dxftype() == "TEXT":
            text = (entity.dxf.text or "").strip()

            if text:
                text_objects.append({
                    "id": str(entity.dxf.handle),
                    "text": text,
                    "point": _dxf_point3d(entity.dxf.insert),
                })

        elif entity.dxftype() == "MTEXT":
            text = entity.plain_text().strip()

            if text:
                text_objects.append({
                    "id": str(entity.dxf.handle),
                    "text": text,
                    "point": _dxf_point3d(entity.dxf.insert),
                })

    return curve_objects, text_objects


# ------------------------------------------------------------
# CSV
# ------------------------------------------------------------

CSV_HEADERS_EXPORTS = [
    "DXF Filename",
    "Full Path",
    "Part Name",
    "Export Number",
    "Total Quantity",
    "Material",
    "Layer 1",
    "Layer 2",
    "Status",
]

CSV_HEADERS_PARTS = [
    "Part Name",
    "Quantity",
    "Material",
    "Original Curve DXF Handle",
    "Assigned Text",
]

CSV_HEADERS_WARNINGS = [
    "Original Curve DXF Handle",
    "Part Name",
    "Quantity",
    "Material",
    "Problem",
    "Assigned Text",
]

CSV_HEADERS_ASSIGNMENT = [
    "Label Group/Text DXF Handle",
    "Assigned Curve DXF Handle",
    "Assignment Method",
    "Distance / Group Keys",
    "Text",
]


def write_all_csv_reports(
    export_folder,
    exported_rows,
    parts_rows,
    warning_rows,
    assignment_debug,
    grouping_debug,
):
    """Write all four CSV reports to export_folder. Returns path dict."""
    def write_report(path, rows, headers):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)

            for row in rows:
                writer.writerow(["" if value is None else str(value) for value in row])

    assignment_rows = [list(row) for row in assignment_debug]

    for row in grouping_debug:
        assignment_rows.append([row[0], "", "TEXT_GROUP", row[1], row[2]])

    paths = {
        "exports": os.path.join(export_folder, CSV_EXPORTS),
        "parts": os.path.join(export_folder, CSV_PARTS),
        "warnings": os.path.join(export_folder, CSV_WARNINGS),
        "assignment": os.path.join(export_folder, CSV_ASSIGNMENT),
    }

    write_report(paths["exports"], exported_rows, CSV_HEADERS_EXPORTS)
    write_report(paths["parts"], parts_rows, CSV_HEADERS_PARTS)
    write_report(paths["warnings"], warning_rows, CSV_HEADERS_WARNINGS)
    write_report(paths["assignment"], assignment_rows, CSV_HEADERS_ASSIGNMENT)

    return paths


# ------------------------------------------------------------
# EXPORT PIPELINE + CLI
# ------------------------------------------------------------

def export_two_layer_dxf(filepath, export_primitives, tolerance):
    """Export the same curve on both CNC layers."""
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass

    primitive_layer_items = [
        (export_primitives, LAYER_ROUGH),
        (export_primitives, LAYER_FINAL),
    ]

    success = write_primitives_to_dxf(
        filepath,
        primitive_layer_items,
        tol=tolerance,
    )

    if success:
        return "OK_CUSTOM_DXF_WRITER"

    return "FAILED"


def run(input_path, output_dir, material_filter, tolerance):
    if not os.path.isfile(input_path):
        print("Input file not found: {}".format(input_path))
        return 1

    curve_objects, text_objects = read_dxf(input_path, tolerance)

    if not curve_objects:
        print("No closed curves found.")
        return 1

    if not text_objects:
        print("No text entities found.")
        return 1

    label_groups, grouping_debug = build_label_groups(text_objects)

    curve_assignment, assignment_debug = assign_label_groups_to_curves(
        curve_objects,
        label_groups,
    )

    exported_rows = []
    parts_rows = []
    warning_rows = []

    exported_count = 0
    failed_export_count = 0
    skipped_count = 0

    for curve_obj in curve_objects:
        curve_id = curve_obj["id"]
        group = curve_assignment.get(curve_id)
        combined_text = group["text"] if group else ""

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
                combined_text.replace("\n", " | "),
            ])

        parts_rows.append([
            name,
            quantity,
            material,
            curve_id,
            combined_text.replace("\n", " | "),
        ])

        if normalize_material(material) != normalize_material(material_filter):
            skipped_count += 1
            continue

        if not curve_obj["export_primitives"]:
            warning_rows.append([
                curve_id,
                name,
                quantity,
                material,
                "NO_EXPORT_GEOMETRY",
                combined_text.replace("\n", " | "),
            ])
            continue

        for i in range(1, quantity + 1):
            filename = "{}_{}.dxf".format(name, i)
            filepath = os.path.join(output_dir, filename)

            status = export_two_layer_dxf(
                filepath,
                curve_obj["export_primitives"],
                tolerance,
            )

            exported_rows.append([
                filename,
                filepath,
                name,
                i,
                quantity,
                material,
                LAYER_ROUGH,
                LAYER_FINAL,
                status,
            ])

            if status.startswith("OK"):
                exported_count += 1
            else:
                failed_export_count += 1

    csv_paths = write_all_csv_reports(
        output_dir,
        exported_rows,
        parts_rows,
        warning_rows,
        assignment_debug,
        grouping_debug,
    )

    print("Done.")
    print("Closed curves found: {}".format(len(curve_objects)))
    print("Text entities found: {}".format(len(text_objects)))
    print("Label groups built from NR texts: {}".format(len(label_groups)))
    print("DXFs exported: {}".format(exported_count))
    print("DXFs failed: {}".format(failed_export_count))
    print("Parts skipped because material is not '{}': {}".format(
        material_filter,
        skipped_count,
    ))
    print("CSV export list: {}".format(csv_paths["exports"]))
    print("CSV parts overview: {}".format(csv_paths["parts"]))
    print("CSV warnings: {}".format(csv_paths["warnings"]))
    print("CSV assignment debug: {}".format(csv_paths["assignment"]))

    return 0 if failed_export_count == 0 else 1


def main():
    return run(INPUT_DXF, OUTPUT_DIR, MATERIAL_TO_EXPORT, DEFAULT_TOLERANCE)


if __name__ == "__main__":
    sys.exit(main())
