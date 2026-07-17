"""Detect block INSERT positions in modelspace."""

from ezdxf.math import Vec3


def _should_skip_name(name):
    return not name or name.startswith("*")


def _insert_positions(entity):
    """Yield (row, col, x, y) for each grid cell of an INSERT entity."""
    dxf = entity.dxf
    ins = dxf.insert
    row_count = dxf.row_count or 1
    col_count = dxf.column_count or 1
    row_spacing = dxf.row_spacing or 0.0
    col_spacing = dxf.column_spacing or 0.0
    rotation = dxf.rotation or 0.0

    done = set()
    for row in range(row_count):
        for col in range(col_count):
            offset = Vec3(col * col_spacing, row * row_spacing)
            if offset in done:
                continue
            done.add(offset)
            if rotation:
                offset = offset.rotate_deg(rotation)
            yield row, col, float(ins.x + offset.x), float(ins.y + offset.y)


def find_block_inserts(doc, layer=None, name_prefix=None):
    """
    Return INSERT instance records from modelspace.

    Each array cell becomes its own record. System blocks (*Model_Space, *U, …)
    are skipped. Optional layer and name_prefix filters may be applied.
    """
    results = []
    for entity in doc.modelspace().query("INSERT"):
        name = entity.dxf.name
        if _should_skip_name(name):
            continue
        if layer is not None and (entity.dxf.layer or "0") != layer:
            continue
        if name_prefix is not None and not name.startswith(name_prefix):
            continue

        dxf = entity.dxf
        handle = str(dxf.handle)
        xscale = float(dxf.get("xscale", 1.0) or 1.0)
        yscale = float(dxf.get("yscale", 1.0) or 1.0)
        rotation = float(dxf.rotation or 0.0)
        entity_layer = dxf.layer or "0"

        for row, col, x, y in _insert_positions(entity):
            results.append({
                "id": "{}:{}:{}".format(handle, row, col),
                "handle": handle,
                "name": name,
                "layer": entity_layer,
                "x": x,
                "y": y,
                "rotation": rotation,
                "xScale": xscale,
                "yScale": yscale,
            })

    return results
