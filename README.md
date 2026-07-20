# dashboard-front

Vue monorepo: shell + DoorBoxOut + Simple Parts + `@dashboard/shared`.

**GitHub:** `maria-datab/dashboard-front`  
**Local folder** may still be named `dashboard/` (rename to `dashboard-front` when nothing has the path locked).

## Sibling workspace

Clone all four repos next to each other:

```
dashboardTest/
  dashboard/                         ← this repo (dashboard-front)
  dashboard-back/                    ← shared Python package
  dashboard-boxout-back/
  dashboard-simple-parts-back/
```

| Repo | Role |
|------|------|
| `dashboard-front` | Vue apps + shared frontend |
| `dashboard-back` | Shared Python (`shared.*`) |
| `dashboard-boxout-back` | Boxout Flask API (:5000) |
| `dashboard-simple-parts-back` | Simple Parts Flask API (:5001) |

## Run

```bat
run-dashboard.bat   REM 2 sibling Flask backends + dashboard Vite
run-boxout.bat
run-simple-parts.bat
```

```bash
npm install
npm run dev:dashboard   # http://127.0.0.1:5173
```

First-time backends (from each `*-back` folder):

```bash
pipenv install
# copy .env.example → .env
```

`dashboard-boxout-back` / `dashboard-simple-parts-back` Pipfiles expect `../dashboard-back` as an editable install.

## New app checklist

1. Add `apps/<name>/` here (Vue 3 + Vite, thin `App.vue` + `features/useApp.js`).
2. New backend as its **own GitHub repo**; depend on `dashboard-back`.
3. Register a dashboard route that mounts the tool `App.vue`.
4. Proxy `/api/<name>` in `apps/dashboard/vite.config.js`.
5. Set `VITE_<NAME>_API_BASE=/api/<name>` in the dashboard `.env`.
6. Point `run-dashboard.bat` (or a new bat) at the sibling backend folder.
