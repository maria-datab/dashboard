# Simple Parts — Frontend

> Branching model and feature recovery: see [../docs/FEATURE_BRANCHES.md](../docs/FEATURE_BRANCHES.md) and [../README.md#branching-and-simplification](../README.md#branching-and-simplification).

Vue 3 + Vite single-page app for uploading client CAD (`.dxf` or `.3dm`), previewing geometry in 2D or 3D, running Hops nesting via Rhino.Compute, and editing part metadata through NL chat.

The DXF is parsed **entirely in the browser** (`dxf-vuer`). The backend is called for Hops solve and chat intents.

## Running locally

**Requirements:** Node.js 20.19+ or 22.12+

```bash
npm install
npm run dev
```

The dev server runs on Vite’s default port (5173) and proxies `/api` to `http://localhost:5001`. Start the backend (`simple-parts-back`) before processing files.

| Script | Purpose |
|--------|---------|
| `npm run dev` | Development server with hot reload |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the production build locally |

## Architecture

```
index.html → main.js → App.vue
                           ├── SharedSidebar → ChatPanelComponent (domain slots)
                           └── main (viewer)
                                 ├── ThreeMeshViewer (Hops meshes3d preview)
                                 ├── DXFViewerComponent (2D or local 3D)
                                 └── NestingResultModal
```

**State and logic** live in composables under `src/features/`:

| File | Role |
|------|------|
| `useApp.js` | Single entry point: shared state, file upload routing, Hops solve, viewer computed props, nesting modal |
| `shared/createAppState.js` | Reactive refs (`dxfText`, `messages`, `viewerBusy`, `summonedPreview`, …) |
| `shared/curveHelpers.js` | Messaging, curve/boundary helpers, metadata lookups |
| `chat/useChat.js` | `POST /api/chat` intents (`show_part`, `modify`, `bulk_modify`) |

`App.vue` is thin: it calls `useApp()` and wires props/events to components.

## Upload flow

1. User attaches a `.dxf` or `.3dm` in the chat panel.
2. **2D DXF** — parsed locally; chat shows a **Nest** prompt immediately.
3. **3D DXF / ACIS solid** — `useApp.js` calls `POST /api/hops/solve` for mesh preview. The viewer shows **"Computing 3D visualization…"** (not chat). When done, chat shows **"3D DXF processed for visualization"** and the **Nest** button.
4. **`.3dm`** — same Hops preview path as 3D DXF (`geometryMode=1`); viewer shows **"Computing 3D visualization…"**. Chat shows **".3dm processed for visualization"** when done, with `InputText`/`InputTextPt` overlay from GH.
5. User clicks **Nest** → Hops solve → nesting result modal + download (`jobId`).
6. **Input / Output** toggle shows original upload vs flat merged DXF after solve.

## File reference

### Root

| File | Role |
|------|------|
| `package.json` | Project metadata, npm scripts, dependencies (`vue`, `dxf-vuer`, `three`, `vite`). |
| `vite.config.js` | Vue plugin, `@` → `src/` alias, dev-server proxy `/api` → port 5001. |
| `index.html` | HTML shell; mounts the Vue app on `#app`. |

### `src/`

| File | Role |
|------|------|
| `main.js` | Application entry: creates the Vue app, imports global styles, mounts `App.vue`. |
| `App.vue` | Layout: shared `Sidebar` + local `ChatPanelComponent` + viewer + nesting modal. Delegates logic to `useApp()`. |
| `features/useApp.js` | Upload flow, Hops API, viewer data (`viewerDxfText`, `viewerBoundaries`, …), nesting. |
| `features/shared/createAppState.js` | Central reactive state factory. |
| `features/chat/useChat.js` | NL chat message handling. |
| `dxfDetection.js` | `is3dDxf()`, ACIS solid detection. |
| `dxfMetadata.js` | 3D entity listing, `build3dInterpretBoundaries()`. |
| `rhino3dmPreview.js` | Hops `meshes3d` normalization and `InputText` overlay helpers. |

### `src/components/`

| File | Role |
|------|------|
| `ChatPanelComponent.vue` | App-specific chat bubbles (sheet/material/nesting) + Nest CTA; wraps shared `ChatPanel`. |
| `DXFViewerComponent.vue` | 2D (`Dxf2DViewer`) or local 3D (`PlanView3DViewer`) preview. |
| `ThreeMeshViewer.vue` | Three.js orthographic viewer for Hops `meshes3d` JSON. |
| `NestingResultModalComponent.vue` | Modal with flat DXF preview and download link after nesting. |

### `src/styles/`

| File | Role |
|------|------|
| `styles.css` | Global CSS variables, layout (`.app`, `.sidebar`, `.main`), mobile Agent/DXF toggle. |

## Key concepts

### DXF metadata

Each closed boundary can carry three XData keys:

| Key | Meaning |
|-----|---------|
| **Nr** | Part serial / name |
| **Mat** | Material |
| **Anz** | Quantity |

Overrides from chat are stored per entity **handle** in `metadataOverrides`.

### 2D vs 3D detection

`is3dDxf()` returns true when model space has `SOLID`, `3DFACE`, or a closed `POLYLINE` with `isPolyfaceMesh`. True 3D uploads trigger the visualization solve before nesting.

### Busy states

| State | Where shown | When |
|-------|-------------|------|
| `viewerBusy` | Viewer overlay | 3D visualization / `.3dm` mesh load |
| `busy` | Chat typing indicator | Nesting solve, chat intent fetch |

### API usage

| Call | When |
|------|------|
| `POST /api/hops/solve` | 3D visualization on upload; nesting on **Nest** click |
| `POST /api/chat` | User sends a free-text message |
| `GET /api/jobs/<jobId>/download` | Download nesting ZIP (per-sheet DXFs + merged PDF) from nesting modal |

## Dependencies

| Package | Use |
|---------|-----|
| `vue` | UI framework (Composition API, `<script setup>`) |
| `dxf-vuer` | Parse DXF in browser; 2D viewer; Three.js helpers for 3D |
| `three` | `ThreeMeshViewer` and local 3D shading |
| `vite` | Dev server and bundler |
