# Unified Dashboard — Architecture Plan

> **Status (2026-07):** Split into four GitHub repos for independent permissions/releases:
> `dashboard-front`, `dashboard-back`, `dashboard-boxout-back`, `dashboard-simple-parts-back`.
> See workspace [`../README.md`](../README.md) and [`README.md`](README.md).
> [`AGENT_CODING_PROMPT.md`](AGENT_CODING_PROMPT.md) is historical bootstrap guidance — do not re-run.

## What you have

| Repo | Stack | What it does |
|------|-------|--------------|
| `boxout-back` | Flask · Python 3.14 · Anthropic · Rhino.Compute | Validates CSV box dimensions, runs Grasshopper `.gh` definitions row-by-row, returns geometry JSON |
| `boxout-front` | Vue 3 · Vite · Three.js · rhino3dm · D3 · ExcelJS | Chat/CSV input → 3D box viewer, parallel-coords plot, nesting panel |
| `simple-parts-back` | Flask · Python 3.14 · Anthropic · ezdxf · Rhino.Compute | DXF ingestion, part-metadata extraction/correction, nesting, CNC export |
| `simple-parts-front` | Vue 3 · Vite · Three.js · rhino3dm · dxf-vuer | DXF upload/chat → 3D mesh viewer, metadata panel, nesting result modal |

Both pairs share the same philosophy: a left-sidebar chat that drives a right-side 3D viewer, background async jobs polled from the frontend, Anthropic LLM for natural-language input, and Rhino.Compute for geometry.

---

## What's already shared (free wins)

Before writing a line of new code, these things are already almost identical and can be unified immediately.

**Design tokens** — `styles.css` in both frontends defines the same `:root` CSS variables (`--color-accent`, `--color-border`, `--color-surface`, etc.) with identical values. They just need to be merged into one file.

**`ChatMessage` typedef** — both repos use `{ id, role, kind, content, meta }`. Identical.

**`ChatPanelComponent.vue`** — structurally the same: message list, scroll-to-bottom watcher, file drag-and-drop, send-on-Enter. The only differences are accepted file extensions (`.csv/.xlsx/.jpg` vs `.dxf/.3dm`) and a few extra message kinds in simple-parts (`sheet-size-select`, `material-select`, etc.) that are passed through as slots or render-props.

**Sidebar shell** — both `Sidebar.vue` / `SidebarComponent.vue` are thin wrappers that render `<h1>AppName</h1>` + `<ChatPanelComponent>`. Purely a title difference.

**Mobile toggle pattern** — identical hidden-radio CSS trick in both `styles.css`. One shared implementation works for both.

**Flask app factory pattern** — `create_app()` + Blueprint + `config.py`. simple-parts is already blueprint-based (`routes.py`); boxout can be lifted to the same pattern with minimal effort.

**`llm.py`** — both backends call Anthropic with a system prompt + user message + structured JSON output. The class shapes differ but the plumbing is the same.

---

## Proposed structure

```
dashboard/                        ← new monorepo root
├── package.json                  ← npm workspaces
├── packages/
│   └── shared/                   ← extracted shared frontend library
│       ├── package.json          (name: "@dashboard/shared")
│       ├── components/
│       │   ├── AppShell.vue      ← top nav + <router-view> slot
│       │   ├── ChatPanel.vue     ← merged ChatPanelComponent
│       │   ├── Sidebar.vue       ← generic sidebar (title prop + ChatPanel slot)
│       │   └── MobileToggle.vue  ← shared radio-tab component
│       ├── composables/
│       │   └── useJobPoller.js   ← generic GET-poll loop (used by both viewers)
│       └── styles/
│           └── tokens.css        ← single merged :root token set
├── apps/
│   ├── dashboard/                ← shell app (Vue Router, nav, landing page)
│   │   ├── package.json
│   │   └── src/
│   │       ├── main.js
│   │       ├── App.vue           ← <AppShell> + top nav
│   │       ├── router.js         ← /boxout and /simple-parts lazy routes
│   │       └── views/
│   │           └── HomeView.vue  ← landing page linking to both tools
│   ├── boxout/                   ← boxout-front, refactored to use @dashboard/shared
│   │   └── src/ (unchanged except imports)
│   └── simple-parts/             ← simple-parts-front, same
│       └── src/ (unchanged except imports)
└── backends/
    ├── shared/
    │   └── llm_base.py           ← extracted base LLM class both backends inherit
    ├── boxout/                   ← boxout-back (moved)
    └── simple-parts/             ← simple-parts-back (moved)
```

---

## Frontend: shared `@dashboard/shared` package

### 1. Design tokens — `packages/shared/styles/tokens.css`

Merge the two token sets into one. Tokens unique to simple-parts (part highlight colors, `--color-salmon`) are included but inert in boxout. Both apps import this single file instead of their local `styles.css`.

No code changes needed in components — they already reference the same variable names.

### 2. `ChatPanel.vue` — merged component

The two `ChatPanelComponent.vue` files are ~80% identical. The merge strategy:

- Accept an `acceptedExtensions` prop (array of strings) — replaces the hardcoded `IMPORT_FILE_EXTENSIONS` constant in each.
- Accept a `messageRenderers` prop or use a named slot `#message="{ msg }"` for app-specific message kinds (simple-parts has `sheet-size-select`, `material-select`, `nesting-result`; boxout has `confirm`). Each app passes its own renderer; the shared component handles the common `text / file / result / error` kinds natively.
- Keep all scroll, drag-drop, and keyboard logic in the shared component — it is identical in both.

This cuts ~300 lines of duplicated code and means any chat UX improvements (typing indicator, keyboard shortcut, accessibility) are fixed once.

### 3. `Sidebar.vue` — generic wrapper

```vue
<script setup>
defineProps({ title: String })
</script>
<template>
  <aside class="sidebar">
    <h1>{{ title }}</h1>
    <slot />      <!-- ChatPanel goes here -->
  </aside>
</template>
```

Both apps' sidebars collapse to this. The style lives in `tokens.css`.

### 4. `useJobPoller.js` — shared composable

Both viewers do the same thing: `POST` a job, then `GET /<jobId>` every N ms until `status === 'completed'` or `'failed'`. Extract this into a composable:

```js
// packages/shared/composables/useJobPoller.js
export function useJobPoller({ startFn, pollFn, onSnapshot, intervalMs = 1200 }) { … }
```

boxout's `runSolve()` and simple-parts' Rhino.Compute polling both become thin wrappers over this.

### 5. `MobileToggle.vue`

The hidden-radio CSS tab trick is copy-pasted verbatim. Extract to a component that accepts a `tabs` prop and emits `update:modelValue`.

---

## Dashboard shell app

The shell is a new minimal Vue 3 + Vite + Vue Router app. It:

1. Renders a persistent top nav bar with links to each tool.
2. Lazy-loads each tool as a route component.
3. Owns shared state that lives above both tools (e.g., a future auth layer or cross-app notifications).

### Router

```js
// apps/dashboard/src/router.js
const routes = [
  { path: '/', component: () => import('./views/HomeView.vue') },
  { path: '/boxout/:pathMatch(.*)*', component: () => import('@dashboard/boxout/src/App.vue') },
  { path: '/simple-parts/:pathMatch(.*)*', component: () => import('@dashboard/simple-parts/src/App.vue') },
]
```

Each app's `App.vue` is unchanged — it just gets mounted inside a `<router-view>` instead of directly on `#app`.

### Top nav

A narrow fixed header (32px) with the product logo, tool tabs, and a user indicator. The nav disappears on mobile (each tool manages its own mobile layout).

### Landing page

A simple two-card grid. Each card shows the tool name, a one-line description, and a "Open" link. Future: add job counts, recent files, or status badges once a shared API layer exists.

---

## Backend: what to share

### Shared `llm_base.py`

Both `llm.py` files call the Anthropic SDK in the same way: load a prompt file, call `messages.create`, parse a JSON response. Extract a `BaseLLMParser` class:

```python
# backends/shared/llm_base.py
class BaseLLMParser:
    def __init__(self, model="claude-sonnet-4-5", max_tokens=1024):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = model
        self.max_tokens = max_tokens

    def call(self, system_prompt, user_message, schema=None):
        # shared call + JSON parse logic
```

Each backend's `CSVAnalyzer`, `BoxCommandParser`, `parse_chat_intent()`, `parse_material()` inherit from this.

### Shared `config_base.py`

The `_env_bool / _env_int / _env_str / _env_float` helpers are identical in both `config.py` files. Move to a shared module both import.

### API routing strategy (two options)

**Option A — Keep separate backends, proxy from dashboard dev server**

Simplest. The dashboard Vite config proxies:
- `/api/boxout/*` → `http://127.0.0.1:5000`
- `/api/simple-parts/*` → `http://127.0.0.1:5001`

No backend restructuring needed beyond the shared modules above. Each backend continues to own its own Flask process. For production, nginx sits in front and does the same routing.

**Option B — Single Flask gateway**

Create a thin `backends/gateway/app.py` that registers both apps' blueprints under prefixes:

```python
from boxout.app import create_app as boxout_app
from simple_parts.app import create_app as simple_parts_app

gateway = Flask(__name__)
gateway.register_blueprint(boxout_app(), url_prefix='/api/boxout')
gateway.register_blueprint(simple_parts_app(), url_prefix='/api/simple-parts')
```

This is cleaner for deployment (one process, one port) but requires that both backends share a Pipenv/venv environment. Given that their dependencies overlap almost entirely (Flask, anthropic, python-dotenv, plus ezdxf for simple-parts), this is viable.

**Recommendation: start with Option A** (no operational change), migrate to Option B once the monorepo is settled.

---

## What NOT to merge

Some things look similar but shouldn't be collapsed:

- **3D viewers** — `3DViewer.vue` (boxout) and `ThreeMeshViewer.vue` (simple-parts) both use Three.js but render completely different data (rhino3dm File3dm geometry vs. BufferGeometry meshes + DXF annotations). A shared base class for camera/controls setup makes sense; the rendering logic stays separate.

- **Solve polling logic** — the `useJobPoller` composable above handles the generic loop; the snapshot processing (`processSolveSnapshot`, mesh decoding) stays in each app since the response shapes are different.

- **Nesting UI** — `NestingCurvePreviewComponent` (boxout) and `NestingResultModalComponent` (simple-parts) are totally different (SVG curve preview vs. a full-screen modal with DXF viewer). Keep separate.

- **Backend business logic** — DXF parsing (ezdxf), GH definition management, compute job tickets — keep in their respective backends. The shared layer is only infrastructure (config helpers, LLM base class).

---

## Component inventory: what goes where

| Component | Current | Action |
|-----------|---------|--------|
| `ChatPanelComponent.vue` | both apps | → `@dashboard/shared/ChatPanel.vue` (merged) |
| `Sidebar.vue` / `SidebarComponent.vue` | both apps | → `@dashboard/shared/Sidebar.vue` (generic) |
| `MobileToggle` (inline CSS) | both apps | → `@dashboard/shared/MobileToggle.vue` |
| `tokens.css` / `styles.css` | both apps | → `@dashboard/shared/styles/tokens.css` |
| `ChatMessage` typedef | both apps | → `@dashboard/shared/types.js` |
| `useJobPoller.js` | extracted from both | → `@dashboard/shared/composables/` |
| `3DViewer.vue` | boxout only | stays in `apps/boxout/`, Three.js camera setup may share helpers |
| `ThreeMeshViewer.vue` | simple-parts only | stays in `apps/simple-parts/` |
| `CsvPreviewComponent.vue` | boxout only | stays in `apps/boxout/` |
| `ParallelCoordinatesComponent.vue` | boxout only | stays in `apps/boxout/` |
| `NestingCurvePreviewComponent.vue` | boxout only | stays in `apps/boxout/` |
| `DXFViewerComponent.vue` | simple-parts only | stays in `apps/simple-parts/` |
| `PartMetadataPanel.vue` | simple-parts only | stays in `apps/simple-parts/` |
| `NestingResultModalComponent.vue` | simple-parts only | stays in `apps/simple-parts/` |
| `llm_base.py` | extracted from both | → `backends/shared/llm_base.py` |
| `config_helpers.py` | extracted from both | → `backends/shared/config_helpers.py` |

---

## Dependencies: final picture

| Package | Dashboard shell | boxout | simple-parts | shared lib |
|---------|----------------|--------|--------------|------------|
| `vue` | ✓ | ✓ | ✓ | ✓ |
| `vue-router` | ✓ | — | — | — |
| `vite` + `@vitejs/plugin-vue` | ✓ | ✓ | ✓ | — |
| `three` | — | ✓ | ✓ | — |
| `rhino3dm` | — | ✓ | ✓ | — |
| `d3` | — | ✓ | — | — |
| `exceljs` | — | ✓ | — | — |
| `dxf-vuer` | — | — | ✓ | — |
| `compute-rhino3d` | — | ✓ | — | — |

No new dependencies needed. The dashboard shell itself is just Vue + Vue Router.

---

## Migration plan (step by step)

### Phase 1 — Bootstrap monorepo (no code changes yet)

1. Create `dashboard/` at repo root with a `package.json` using npm workspaces pointing to `packages/*` and `apps/*`.
2. Copy (don't delete) the four existing repos into `apps/boxout/`, `apps/simple-parts/`, `backends/boxout/`, `backends/simple-parts/`.
3. Verify both apps still build and run from their new locations.

### Phase 2 — Extract shared styles and types

4. Create `packages/shared/` with its own `package.json` (`"name": "@dashboard/shared"`).
5. Merge the two `styles.css` files into `packages/shared/styles/tokens.css`. Add the simple-parts-only tokens to boxout's set (they're inert if unused).
6. Create `packages/shared/types.js` with the shared `ChatMessage` typedef (JSDoc or TypeScript interface).
7. Update both apps to import from `@dashboard/shared/styles/tokens.css` instead of their local file. **Verify visually — nothing should change.**

### Phase 3 — Extract shared components

8. Build `packages/shared/components/ChatPanel.vue` by starting from boxout's version (slightly simpler), then adding the extensibility hooks needed by simple-parts (`acceptedExtensions` prop, `#message` slot for custom kinds).
9. Replace `ChatPanelComponent.vue` in both apps with the shared version. Run both apps and confirm chat still works.
10. Build `packages/shared/components/Sidebar.vue` (title prop + default slot).
11. Collapse both apps' sidebar components to use the shared one.
12. Extract `useJobPoller.js` and wire up both apps.

### Phase 4 — Build dashboard shell

13. Create `apps/dashboard/` with Vue 3 + Vite + Vue Router.
14. Build the persistent nav and `HomeView.vue` landing page.
15. Wire both apps as lazy route chunks.
16. Configure the Vite proxy to route `/api/boxout` and `/api/simple-parts` to the respective backends.
17. Verify both tools are reachable from the dashboard and fully functional.

### Phase 5 — Backend shared modules

18. Extract `config_helpers.py` and `llm_base.py` into `backends/shared/`.
19. Update both backends to import from the shared module.
20. (Optional) Implement Option B gateway if single-process deployment is desired.

### Phase 6 — Polish

21. Unify the Three.js camera/controls setup into a shared helper (the `useCamera` / `useControls` pattern from `dxf-vuer` is already in simple-parts; boxout uses a custom `viewerScene.js`).
22. Add a `vite-plugin-vue-devtools` to both app dev configs (it's only in simple-parts today).
23. Align Vite and `@vitejs/plugin-vue` versions across all apps (boxout is on Vite 6, simple-parts is on Vite 8).

---

## Risks and decisions to make

**Vue Router inside apps** — neither app currently uses Vue Router internally. If a tool ever needs its own sub-routes (e.g., `/boxout/job/:id`), add a child router with `createWebHashHistory` to avoid conflict with the dashboard's router.

**rhino3dm WASM** — both apps load `rhino3dm.wasm` at runtime. If both tools are mounted simultaneously in the dashboard, the WASM module should be loaded once and shared (it's already a singleton via the `loadPromise` pattern in `compute.js`). Extract `loadRhino()` to the shared package.

**State isolation** — each app manages its own state independently. No cross-app state is needed now. If it is in the future (e.g., a shared job queue or user identity), add a Pinia store to the shared package.

**Build output** — decide whether to build one bundle (dashboard imports both apps as chunks, one `dist/`) or three separate bundles served from the same nginx. One bundle is simpler for development; separate bundles allow independent deploys.

**Backend deployment** — if running on a single server, Option B (gateway) is cleaner. If the two backends will ever run on different machines or scale independently, stick with Option A and route at the load-balancer level.
