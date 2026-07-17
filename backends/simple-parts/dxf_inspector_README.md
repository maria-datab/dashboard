## DXF inspector

Single inspect path via `POST /api/inspect` and CLI [`dxf_manual_inspector.py`](dxf_manual_inspector.py).

After upload, the chat prompts **Interpret DXF?** → user picks **inside** or **outside** text placement → inspect runs. Part boundaries and counts come from the API response (`boundaries` from [`boundary_detection.py`](boundary_detection.py)). **Output** view stays disabled until inspect succeeds.

Shared geometry: [`boundary_detection.py`](boundary_detection.py), [`block_detection.py`](block_detection.py).

---

### Layer scheme (fixed)

Part geometry must use these layer names only:

| Layer | Role |
|-------|------|
| `Outside` | External part boundaries |
| `Inside` | Internal cuts |
| `Bohr` | Drill holes |

Any entity on another layer is listed in `schemeOutliers` (detection + reporting only; no viewer UI yet).

Boundary join collects curves on admitted layers (`Outside`, `Inside`, `Bohr`) **plus** `LINE` entities on any other layer (except defpoints/bemassung) so open `Outside` chains can close via foreign segments. Those closing LINEs are flagged in `layerOutliers` / export `FOREIGN_LINE` warnings; non-admitted entities also appear in `schemeOutliers`.

---

### CLI

```bash
pipenv run python dxf_manual_inspector.py path/to/file.dxf
pipenv run python dxf_manual_inspector.py path/to/file.dxf --text-position outside
```

---

### Pipeline

1. `find_boundaries()` — Rhino-style join on admitted layers only.
2. Exterior candidates — boundaries with a member on `Outside`; nested split by geometry.
3. Inner propagation — nested `Outside`, plus `Inside` and `Bohr` boundaries inside an exterior inherit that part's metadata.
4. All TEXT/MTEXT from any layer → `split_shared_layer_texts` (`Stk.` / `Stück` / `Zx` / `Z x` → amount; rest → serial).
5. Spatial assignment by `textPosition`:
   - **`inside`:** text insertion point inside boundary; amount prefers inside, then x-aligned with serial, then nearest center.
   - **`outside`:** text closest to any segment of the part boundary polygon (serials must lie outside all exteriors).
6. `find_scheme_outliers()` — entities not on admitted layers.
7. Block INSERT positions via `find_block_inserts()`.

Material is read from any TEXT/MTEXT matching `Material=` or `Material:` in the file. If none is found, `mat` is left empty and the chat asks the user.

---

### API

`POST /api/inspect` — multipart form:

| Field | Values | Default |
|-------|--------|---------|
| `file` | DXF upload | required |
| `textPosition` | `inside` \| `outside` | `inside` |

Legacy: `serialPosition` accepted; `above` maps to `outside`.

**Response:**

```json
{
  "metadataOverrides": { "handle": { "nr", "mat", "anz" } },
  "fileMaterial": "FunderMAX",
  "blockInserts": [...],
  "boundaries": [...],
  "schemeOutliers": [{ "handle", "layer", "entityType" }]
}
```

Per-boundary `layerOutliers` / `FOREIGN_LINE` warnings (cross-layer LINE members) are unchanged and still feed export CSVs.
