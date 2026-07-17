"""Scheme-layer and foreign-line outlier detection (outlier-visualization branch)."""

from layer_scheme import ADMITTED_LAYERS


def find_scheme_outliers(doc):
    """Entities on layers other than Outside, Inside, or Bores."""
    outliers = []
    seen = set()
    for entity in doc.modelspace():
        layer = entity.dxf.layer or "0"
        if layer in ADMITTED_LAYERS:
            continue
        handle = str(entity.dxf.handle)
        if handle in seen:
            continue
        seen.add(handle)
        outliers.append({
            "handle": handle,
            "layer": layer,
            "entityType": entity.dxftype(),
        })
    return outliers


def flag_foreign_line_outliers(members, majority_layer):
    if majority_layer is None:
        return []
    return [
        {
            "handle": m["handle"],
            "layer": m["layer"],
            "entityType": "LINE",
        }
        for m in members
        if m["entity_type"] == "LINE" and m["layer"] != majority_layer
    ]


def _layer_vote_key(item):
    layer, stats = item
    return (-stats["count"], -stats["length"], layer)


def infer_closing_layer(preliminary_outliers, edges_by_handle, polyline_length_fn):
    """File-wide majority layer among per-boundary outlier candidates."""
    if not preliminary_outliers:
        return None

    layers = {}
    for outlier in preliminary_outliers:
        layer = outlier["layer"]
        entry = layers.setdefault(layer, {"count": 0, "length": 0.0})
        entry["count"] += 1
        for edge in edges_by_handle.get(outlier["handle"], []):
            entry["length"] += polyline_length_fn(edge["pts"])

    return sorted(layers.items(), key=_layer_vote_key)[0][0]


def classify_closing_lines(members, closing_layer, edges_by_handle, majority_layer_fn):
    outliers = [
        {
            "handle": m["handle"],
            "layer": m["layer"],
            "entityType": "LINE",
        }
        for m in members
        if m["entity_type"] == "LINE" and m["layer"] == closing_layer
    ]
    non_closing = [
        m for m in members
        if not (m["entity_type"] == "LINE" and m["layer"] == closing_layer)
    ]
    majority = (
        majority_layer_fn(non_closing, edges_by_handle)
        or majority_layer_fn(members, edges_by_handle)
    )
    return majority, outliers
