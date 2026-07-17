# Rhino Python script
# Reads Nr/Anz/Mat text labels from the document,
# assigns them to closed curves using the same logic as the exporter,
# then stamps serial / amount / material as UserText on each curve.

import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import scriptcontext as sc
import re

# ------------------------------------------------------------
# HELPERS (minimal subset from the exporter)
# ------------------------------------------------------------

def normalize_value(value):
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).strip()

def safe_filename(name):
    name = normalize_value(name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    if not name:
        name = "UNNAMED"
    return name

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
    return curve.PointAt(t).DistanceTo(point)

def curve_area(curve):
    amp = rg.AreaMassProperties.Compute(curve)
    if amp:
        return abs(amp.Area)
    return float("inf")

def curve_center(curve):
    return curve.GetBoundingBox(True).Center

def point_is_inside_curve(curve, point):
    tol = sc.doc.ModelAbsoluteTolerance
    plane_success, plane = curve.TryGetPlane()
    if not plane_success:
        plane = rg.Plane.WorldXY
    containment = curve.Contains(point, plane, tol)
    return containment in (
        rg.PointContainment.Inside,
        rg.PointContainment.Coincident
    )

# ------------------------------------------------------------
# TEXT PARSING (identical to exporter)
# ------------------------------------------------------------

def classify_text(text):
    if not text:
        return ""
    match = re.match(r"^\s*(NR|ANZ|MAT)\s*\.?\s*:", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).upper()

def parse_field(text, key):
    key_clean = key.replace(".", "")
    pattern = (
        r"{0}\s*\.?\s*:\s*(.*?)"
        r"(?=(?:NR|ANZ|MAT)\s*\.?\s*:|$)"
    ).format(re.escape(key_clean))
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.sub(r"[\r\n]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def parse_part_info(text):
    nr  = parse_field(text, "NR")
    anz = parse_field(text, "ANZ")
    mat = parse_field(text, "MAT")

    name = safe_filename(nr)

    qty_match = re.search(r"\d+", anz)
    quantity = int(qty_match.group(0)) if qty_match else 1
    if quantity < 1:
        quantity = 1

    return name, quantity, mat.strip()

# ------------------------------------------------------------
# GROUPING + ASSIGNMENT (identical logic to exporter)
# ------------------------------------------------------------

def make_text_record(obj):
    text  = get_text_string(obj)
    point = get_text_point(obj)
    key   = classify_text(text)
    return {"id": str(obj.Id), "object": obj, "text": text, "point": point, "key": key}

def greedy_match_nearest(anchor_records, candidate_records):
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
    all_records = []
    for obj in text_objects:
        rec = make_text_record(obj)
        if rec["key"] in ("NR", "ANZ", "MAT"):
            all_records.append(rec)

    nr_records  = [r for r in all_records if r["key"] == "NR"]
    anz_records = [r for r in all_records if r["key"] == "ANZ"]
    mat_records = [r for r in all_records if r["key"] == "MAT"]

    by_id = {r["id"]: r for r in all_records}

    nr_to_anz, _ = greedy_match_nearest(nr_records, anz_records)
    nr_to_mat, _ = greedy_match_nearest(nr_records, mat_records)

    order = {"NR": 0, "ANZ": 1, "MAT": 2}
    groups = []

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
        groups.append({"id": nr["id"], "records": group_records,
                       "text": combined_text, "point": center})
    return groups

def assign_label_groups_to_curves(curve_objects, label_groups):
    curve_areas   = {str(o.Id): curve_area(o.Geometry)   for o in curve_objects}
    curve_centers = {str(o.Id): curve_center(o.Geometry) for o in curve_objects}

    pairs = []
    for gi, group in enumerate(label_groups):
        point = group["point"]
        for ci, curve_obj in enumerate(curve_objects):
            curve    = curve_obj.Geometry
            curve_id = str(curve_obj.Id)
            inside   = point_is_inside_curve(curve, point)
            if inside:
                priority   = 0
                area_score = curve_areas[curve_id]
                distance   = point.DistanceTo(curve_centers[curve_id])
            else:
                priority   = 1
                area_score = float("inf")
                distance   = closest_distance_to_curve(curve, point)
            pairs.append((priority, area_score, distance, gi, ci))

    pairs.sort(key=lambda x: (x[0], x[1], x[2]))

    assignment   = {str(o.Id): None for o in curve_objects}
    used_groups  = set()
    used_curves  = set()

    for priority, area_score, distance, gi, ci in pairs:
        if gi in used_groups or ci in used_curves:
            continue
        curve_id = str(curve_objects[ci].Id)
        assignment[curve_id] = label_groups[gi]
        used_groups.add(gi)
        used_curves.add(ci)

    return assignment

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    # Collect closed curves (skip the two export layers)
    SKIP_LAYERS = {"OUTSIDE_MASS_T201_Z10", "OUTSIDE_MASS_FINAL_T202_ZM02"}

    curve_objects = []
    for obj in sc.doc.Objects:
        if obj.ObjectType != Rhino.DocObjects.ObjectType.Curve:
            continue
        layer_name = sc.doc.Layers[obj.Attributes.LayerIndex].FullPath
        if layer_name in SKIP_LAYERS:
            continue
        if obj.Geometry and obj.Geometry.IsClosed:
            curve_objects.append(obj)

    # Collect text objects
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

    label_groups = build_label_groups(text_objects)
    assignment   = assign_label_groups_to_curves(curve_objects, label_groups)

    stamped  = 0
    skipped  = 0
    warnings = []

    for curve_obj in curve_objects:
        curve_id     = str(curve_obj.Id)
        group        = assignment.get(curve_id)
        combined_text = group["text"] if group else ""

        name, quantity, material = parse_part_info(combined_text)

        missing = []
        if not name or name == "UNNAMED":
            missing.append("NR")
        if quantity == 1 and not parse_field(combined_text, "ANZ"):
            missing.append("ANZ")
        if not material:
            missing.append("MAT")

        if missing:
            warnings.append("  GUID {}: missing {}".format(curve_id[:8], ", ".join(missing)))

        # Stamp the three keys as UserText on the curve object
        obj_id = curve_obj.Id
        rs.SetUserText(obj_id, "Nr",   name)
        rs.SetUserText(obj_id, "Mat", material if material else "")
        rs.SetUserText(obj_id, "Anz",   str(quantity))
        
        stamped += 1

    sc.doc.Views.Redraw()

    print("Done.")
    print("Curves stamped: {}".format(stamped))
    print("Curves skipped: {}".format(skipped))
    if warnings:
        print("Warnings ({} curves with incomplete labels):".format(len(warnings)))
        for w in warnings:
            print(w)
    else:
        print("All curves had complete NR / ANZ / MAT labels.")

if __name__ == "__main__":
    main()#! python 3
