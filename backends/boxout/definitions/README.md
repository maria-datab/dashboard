# Grasshopper definitions

Put `.gh` files in this folder, then add a row for each one in **`config.py`** → `DEFINITIONS` (near the bottom of that file).

- `doorBoxOut_PerBox.gh` — per-row geometry (3D viewer) and K/F panel counts
- `doorBoxOut_MultiBox.gh` — full-set K/F panel counts
- `doorBoxOut_MultiBox_Nested.gh` — full-set nesting preview curves

| ID | File | API prefix | Status |
|----|------|------------|--------|
| `joint-wiz` | `doorBoxOut_PerBox.gh` | `/definitions/joint-wiz/` | Enabled (default) |

## Per-definition endpoints

- `GET /definitions/<id>/definition-defaults`
- `POST /definitions/<id>/solve`
- `GET /definitions/<id>/solve/<jobId>`

List all: `GET /definitions`

Legacy routes (`/solve`, `/definition-defaults`) use `DEFAULT_DEFINITION_ID` in `.env` (`joint-wiz`).

## Adding a new definition

1. Copy your `.gh` file here.
2. Open `boxout-back/config.py` and add to `DEFINITIONS`:

   ```python
   "my-stage": {
       "label": "My Stage",
       "gh_file": "MyStage.gh",
       "stage": "my_stage",
       "enabled": True,
   },
   ```

3. Restart Flask.

When updating a `.gh` in Grasshopper, replace the file here and restart the backend.
