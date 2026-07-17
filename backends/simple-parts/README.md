# Simple Parts — Backend

> Branching model and feature recovery: see [../docs/FEATURE_BRANCHES.md](../docs/FEATURE_BRANCHES.md) and [../README.md#branching-and-simplification](../README.md#branching-and-simplification).

Flask API and Python DXF export pipeline. Reads client DXF files with embedded curve metadata (**Nr**, **Mat**, **Anz**), applies user corrections from the frontend chat, optionally normalizes material text via Claude, and writes per-quantity CNC DXFs plus CSV reports.

A separate **`dxf_manual_inspector`** module infers part metadata from label text in client DXFs. See [dxf_inspector_README.md](dxf_inspector_README.md).

## Running locally

**Requirements:** Python 3.14 (Pipenv), `ANTHROPIC_API_KEY` in `.env`

```bash
pipenv install
pipenv run serve          # Flask API on port 5001 (see PORT in .env)
pipenv run export         # CLI export via main.py (standalone, no API)
```

Create `.env` in this folder:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Architecture

```
app.py (Flask)
  ├── POST /api/chat     → llm.parse_chat_intent()
  ├── POST /api/process  → save job → llm.parse_material() (optional) → main.run()
  ├── GET  /api/jobs/<id>/files/<name>  → single output file
  └── GET  /api/jobs/<id>/download      → nesting ZIP (per-sheet DXFs + merged PDF)

main.py
  ├── read_dxf()        → ezdxf: closed boundaries + XData metadata
  └── run()             → group by material, export × quantity per folder, write CSVs

dxf_writer.py           → custom AC1015 DXF writer (no Rhino)
```

**Per-job storage:** `tmp/jobs/<uuid>/input.dxf` and `tmp/jobs/<uuid>/output/Export/<Material>/` (DXFs + CSVs per material). This folder is gitignored.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | JSON body: `message`, `chatStep`, `parts`, `knownMaterials` → intent JSON (`process_yes`, `process_no`, `modify`, `other`) |
| `POST` | `/api/process` | Multipart form: `file` (DXF), `metadataOverrides` (JSON map handle → `{nr, mat}`), optional `materialText`, optional `onlyComplete` |
| `GET` | `/api/jobs/<jobId>/files/<filename>` | Download one exported file |
| `GET` | `/api/jobs/<jobId>/download` | Download `export.zip` (all materials under `Export/`) |

**`POST /api/process` response:**

```json
{
  "jobId": "uuid",
  "dxfFiles": ["Export/3-Schicht/4286_1.dxf", "Export/3-Schicht/4286_2.dxf"],
  "csvFiles": [
    "Export/3-Schicht/exported_dxf_files.csv",
    "Export/3-Schicht/parts_overview.csv",
    "Export/3-Schicht/assignment_warnings.csv"
  ]
}
```

## File reference

### Root — application code

| File | Role |
|------|------|
| `app.py` | **Flask HTTP layer.** `POST /api/chat` classifies chat messages. `POST /api/inspect` runs DXF part detection and metadata assignment. `POST /api/process` creates a UUID job folder, saves the uploaded DXF, runs `main.run()`, returns file lists and `jobId`. |
| `dxf_manual_inspector.py` | **DXF metadata inspector.** Fixed layer scheme (`Outside` / `Inside` / `Bohr`), text-to-boundary assignment, `schemeOutliers`. See [dxf_inspector_README.md](dxf_inspector_README.md). |
| `main.py` | **Core export pipeline.** Reads closed curves from a DXF with `ezdxf`, extracts Nr/Mat/Anz from XData, merges chat overrides, groups parts by material into `Export/<Material>/`, writes one DXF per unit (`{Nr}_{1}.dxf`, `{Nr}_{2}.dxf`, …) on CNC layers `OUTSIDE_MASS_T201_Z10` and `OUTSIDE_MASS_FINAL_T202_ZM02`, and emits three semicolon-delimited CSV reports per material folder. Can also run standalone via `pipenv run export` using `INPUT_DXF` / `OUTPUT_DIR` at the top of the file. |
| `dxf_writer.py` | **Low-level DXF writer** (AC1015, ASCII). Builds HEADER, TABLES, BLOCKS, ENTITIES from primitive tuples (`LINE`, `CIRCLE`, `ARC`, `LWPOLYLINE`, `POLYLINE3D`). Used by `main.export_two_layer_dxf()` to duplicate geometry on rough + final layers. No dependency on Rhino or ezdxf for writing. |
| `llm.py` | **Anthropic Claude integration.** Loads prompt templates from `prompts/*.md`. `parse_material()` and `parse_chat_intent()` are used by the Simple Parts upload flow. |
| `config.py` | Loads `.env` via `python-dotenv`; exposes `ANTHROPIC_API_KEY`, Rhino.Compute settings, and GH I/O param names (`serialized_file`, `file_name`, layer outputs `Outside` / `Inside` / `Bohr`). |
| `compute_service.py` | **Rhino.Compute client** for 3D flatten on export. Sends base64 input DXF to `simple-parts-summon2d.gh`; reads three per-layer base64 DXF outputs and merges them via `dxf_serializer.merge_summoned_layer_dxfs()`. |
| `dxf_serializer.py` | Base64 encode/decode helpers, `merge_summoned_layer_dxfs()` (combine per-layer GH outputs), `normalize_summoned_layers_for_export()`, and `is_3d_dxf()` detection. |

### Root — configuration & dependencies

| File | Role |
|------|------|
| `Pipfile` | Pipenv manifest: `ezdxf`, `flask`, `anthropic`, `python-dotenv`. Scripts: `serve` → `app.py`, `export` → `main.py`. |
| `Pipfile.lock` | Locked dependency versions. |
| `.env` | Local secrets (`ANTHROPIC_API_KEY`). **Not committed** — see `.gitignore`. |
| `.gitignore` | Ignores `tmp/`, `.venv/`, `*.env`, and generated DXFs under `output/`. |

### `prompts/`

| File | Role |
|------|------|
| `prompts/material-parse-prompt.md` | **`MATERIAL_PARSE_PROMPT`** — used by `llm.parse_material()` to turn user text (e.g. “3 schicht”) into canonical material JSON `{ "material": "3-Schicht" }`. |
| `prompts/chat-intent-prompt.md` | **`CHAT_INTENT_PROMPT`** — used by `llm.parse_chat_intent()` to classify chat messages (process yes/no, part metadata edits). |

### `-aux/` (Rhino & legacy tooling)

Scripts in this folder are **not** invoked by the Flask API. They run inside Rhino or as standalone experiments for authoring or debugging metadata assignment.

| File | Role |
|------|------|
| `-aux/rhino-metadata-encoding.py` | **2D Rhino script.** Finds `NR:` / `ANZ:` / `MAT:` text labels, assigns them to closed curves (proximity / containment logic), stamps UserText on curves. UserText becomes XData when exported to DXF. |
| `-aux/rhino-metadata-encoding-3d.py` | **3D Rhino script.** Same label logic for closed solids (Breps); stamps UserText on each solid. |
| `-aux/clientInputTransform_ref.py` | **Rhino script (reference).** Full pipeline: label assignment, two-layer DXF export, CSV reports — all inside Rhino. Historical reference implementation. |
| `-aux/clientInputTransform_proximity.py` | **Standalone Python (legacy).** Similar to `main.py` but assigns metadata from nearby text labels in the DXF instead of reading pre-stamped XData. Useful for testing label-matching logic without Rhino. |

### `input/`

Sample client DXF files for manual testing and CLI export. Not used automatically by the API.

| File | Purpose |
|------|---------|
| `ClientInputExample-w-metadata.dxf` | Parts with complete Nr/Mat/Anz metadata |
| `ClientInputExample-w-partial-metadata.dxf` | Some fields missing |
| `ClientInputExample-no-mat.dxf` | No material on parts |
| `ClientInputExample-no-serial-nr.dxf` | Missing serial numbers |
| `ClientInputExample-multiple-mat.dxf` | Multiple materials in one file |
| `ClientInputExample-3d.dxf` | 3D geometry (viewed on frontend; export flattens to 2D outlines) |
| `old/ClientInputExample.dxf` | Older example file |

### `input/JAF/`

Sample JAF client DXFs (legacy layer names). MSD-format files should use `Outside` / `Inside` / `Bohr`.

| File | Purpose |
|------|---------|
| `Lewog Geländer Maxplatten 02.dxf` | *(add notes)* |
| `Lieferabruf ÖBB Bludenz (1).dxf` | *(add notes)* |

### `output/`

Default destination for **CLI** runs (`pipenv run export`). Contains example exported DXFs from past runs. Gitignored for `*.dxf` files. API jobs write to `tmp/jobs/<uuid>/output/` instead.

### `tmp/`

Runtime job storage created by `app.py`. Each job gets `input.dxf` and an `output/` folder. Entire directory is gitignored.

## How `main.run()` works

For each **closed boundary** in model space (circle, closed LWPOLYLINE/POLYLINE, ellipse, or flattened 3D mesh outline):

1. **Read metadata** from XData (`read_curve_metadata`): keys `Nr`, `Mat`, `Anz` as adjacent tag pairs.
2. **Merge overrides** from the frontend chat (`metadata_overrides` keyed by DXF handle). Overrides win for `nr` and `mat`; `anz` always comes from the file.
3. **Apply default material** if the user typed one and a part still has no Mat.
4. **Parse quantity** from Anz (first integer; default 1).
5. **Record warnings** for missing Nr, Anz, or Mat in `assignment_warnings.csv`.
6. **Skip** curves with no material (parts missing Mat are not exported).
7. **Group** remaining curves by normalized material (whitespace-insensitive) into `Export/<Material>/`.
8. **Export** each group: one DXF per unit, same geometry on rough + final CNC layers.
9. **Write CSVs** (one set per material folder):
   - `exported_dxf_files.csv` — one row per generated DXF
   - `parts_overview.csv` — one row per source curve in that material
   - `assignment_warnings.csv` — metadata problems for that material

`GET /api/jobs/<jobId>/download` zips the entire `Export/` tree, preserving one subfolder per material.

## DXF metadata format

Stored as **XData** on each closed curve entity. Keys and values appear as adjacent tags:

| Key | Meaning | Example |
|-----|---------|---------|
| **Nr** | Part serial / name | `4286` |
| **Mat** | Material | `3-Schicht` |
| **Anz** | Quantity | `2` |

The backend reads these in `read_curve_metadata()`; the frontend reads the same keys from `entity.extendedData.customStrings`.

## Supported geometry (export)

| Type | Exported as |
|------|-------------|
| Circle, ellipse | Native primitives |
| Closed LWPOLYLINE / POLYLINE | 2D polyline or 3D line segments |
| Closed polyface mesh | Outline flattened to 2D via `ezdxf.path` |
| Open curves, arcs alone, splines (open) | Skipped (not closed boundaries) |

Export always produces **2D CNC outlines** regardless of whether the source file is 3D.

## LLM usage

The LLM is called **only during export**, and only when the frontend sends `materialText` (user typed a material in chat):

- **Function:** `parse_material()` in `llm.py`
- **Model:** Claude Sonnet (`claude-sonnet-4-5`)
- **Input:** user's free-text answer + known materials from overrides
- **Output:** canonical material string used as `default_material` for parts still missing Mat

The DXF file itself is never sent to the LLM.

## Dependencies

| Package | Use |
|---------|-----|
| `ezdxf` | Read and parse input DXF files |
| `flask` | HTTP API |
| `anthropic` | Material normalization via Claude |
| `python-dotenv` | Load `.env` configuration |
