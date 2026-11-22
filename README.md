# Traffic Flow Network Analyzer

Estimates unknown traffic flows on a directed road network using **Linear Algebra** (flow-conservation equations, Gaussian / Gauss-Jordan elimination, rank, free variables, null space) and **Graph Theory** (adjacency lists, BFS, connectivity), with a FastAPI + database backend and a React front end.

At every junction: `incoming + external inflow = outgoing`. Sensors fix some road flows; the rest become unknowns `x1, x2, …`, giving `AX = B`.

> **Sign convention.** "External inflow" is the *net* traffic entering a junction from outside the model (+ enters, − leaves). The equation row is `incoming − outgoing = −external inflow`, with known road flows moved to the right-hand side.

## Repository layout

```
backend/
  app/engine/linalg.py       hand-written exact row reduction (Fractions), step recording
  app/engine/equations.py    network -> equations, A, B, [A|B]
  app/engine/solution.py     classification, general solution, null space, LP feasibility, SymPy cross-check
  app/engine/pipeline.py     assembles the JSON served to the UI
  app/graph/analysis.py      adjacency lists, BFS, weak/strong connectivity, isolated junctions
  app/models.py              users, networks, junctions, roads, observed_flows, solutions
  app/routers/api.py         REST API (/api/...)
  app/services/              demo networks, repository, PDF report
  tests/                     pytest suite
frontend/                    React + Vite + TypeScript + Tailwind + React Flow + Recharts
render.yaml                  Render blueprint (API + PostgreSQL)
frontend/vercel.json         Vercel SPA config
```

## Run locally

Requirements: Python 3.11+, Node 18+.

```bash
# 1) backend  (http://127.0.0.1:8000, docs at /docs)
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload

# 2) frontend (http://localhost:5173) - Vite proxies /api to port 8000
cd frontend
npm install
npm run dev
```

On first start the tables are created and the three demonstration networks are inserted (and solved with the real solver).

### Configuration

| Variable | Where | Meaning |
|---|---|---|
| `DATABASE_URL` | backend | PostgreSQL URL, e.g. `postgresql://user:pw@host:5432/traffic`. **If unset, a local SQLite file `traffic.db` is used.** |
| `CORS_ORIGINS` | backend | Comma-separated allowed origins (your Vercel URL in production). |
| `VITE_API_URL` | frontend | Backend base URL in production. Empty in dev. |

Copy `backend/.env.example` and `frontend/.env.example` to `.env` files to use them.

## Tests

```bash
cd backend  && python -m pytest          # engine, graph, API, persistence, PDF
cd frontend && npm test                  # Vitest
cd frontend && npm run build             # type-check + production build
```

The backend tests assert, with exact arithmetic: `AX = B`, `A·v = 0` for each null-space basis vector, rank + nullity = unknowns, agreement of back-substitution with Gauss-Jordan, and agreement of RREF/rank/null space with SymPy. They cover unique, infinite, inconsistent, under-/over-determined systems, negative-flow infeasibility, disconnected networks, isolated junctions, BFS, CRUD and persistence.

A note on test output: on some Anaconda installs SymPy prints a harmless `gmpy2` DLL warning at start-up; it falls back to pure Python.

## Demonstration networks (verified by tests)

| Network | Size | Result |
|---|---|---|
| 1 Basic | 3 junctions, 3 roads | unique: x1 = 60, x2 = 30 |
| 2 Intermediate | 3 junctions, 4 roads | x1 = 30 + t, x2 = 70 − t, x3 = t; null space (1, −1, 1); feasible for 0 ≤ t ≤ 70 |
| 3 Advanced | 5 junctions, 7 roads | rank 4, free x3, x6; strongly connected |

## Application pages

Dashboard · Create Network (React Flow editor) · Network Library · Mathematical Solver (equations with derivations, A/X/B and [A|B], step-by-step row operations, solution analysis, null space) · Graph Analysis · Solution Reports (PDF) · Team Contributions (editable names) · Project Documentation + Viva Preparation · Presentation Mode (21 slides; arrow keys / space, `F` full screen, `N` notes) · Settings.

## Deployment (Render, one click)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YashviShah514/traffic-flow-network-analyzer)

`render.yaml` is a Blueprint that creates three things: a managed **PostgreSQL** database (`traffic-db`), the **FastAPI** backend (`tfna-yashvi-api`, `DATABASE_URL` is injected automatically) and the **React** frontend as a static site (`tfna-yashvi-web`) that forwards `/api/*` to the backend, so no CORS or `VITE_API_URL` setup is needed.

1. Sign in at render.com, open the link above (or *New -> Blueprint* and pick this repository) and click **Apply**.
2. Wait for the three resources to finish building (first backend build takes a few minutes: SciPy/SymPy).
3. Open the URL of **tfna-yashvi-web**. The three demo networks are created automatically on the first backend start.

Notes: the backend rewrite target in `render.yaml` assumes the API's URL is `https://tfna-yashvi-api.onrender.com`; if Render adds a suffix because the name is taken, edit that line to your real backend URL. Free web services sleep after inactivity (the first request takes ~1 minute) and Render's free PostgreSQL expires after 30 days - upgrade the plan for anything long-lived.

Alternative: frontend on Vercel (`frontend/vercel.json`, set `VITE_API_URL` to the backend URL and `CORS_ORIGINS` on the backend).

## Verification status

| Check | Result |
|---|---|
| Backend tests (`pytest`) | 32 pass on SQLite **and** on PostgreSQL 19 (`TEST_DATABASE_URL`) |
| Frontend tests (`vitest`) + `tsc` + `vite build` | 10 pass, type-check and build clean |
| PostgreSQL constraints | CHECK(flow >= 0), CHECK(source <> target) and UNIQUE(network, key) verified to reject bad rows |
| Browser walkthrough (Edge, Playwright) | dashboard, library, editor (add junction, drag-to-connect, drag node, edit, save), all five solver tabs, graph page, PDF download, team/docs/viva/settings, all 21 slides, reload persistence - zero console errors; phone width has no horizontal scroll |
| PDF report | generated and rendered; contents checked page by page |

Bugs found and fixed during this verification: the null space was hidden when `AX = B` was inconsistent (it depends only on `A`); the PDF crashed for roads without a label; saving an edited demo network overwrote the demo (demos are now read-only, "Save" stores a copy); new junctions could spawn under UI overlays.

To run the tests against PostgreSQL: `TEST_DATABASE_URL=postgresql://user:pw@host:5432/dbname python -m pytest` (the tables of that database are dropped and recreated).

## Known limitations (honest status)

- Deployment is configured (`render.yaml`) but must be applied from your own Render account; it was not deployed from the development machine.
- There is no authentication: all networks belong to a single default `demo` user (the `users` table is in place).
- The shadcn/ui-style components are hand-written following shadcn conventions (cva + `cn`), not generated by the shadcn CLI.
- Feasible-range numbers come from a floating-point linear program; all algebra is exact.
- Team member names are stored in the browser (`localStorage`), not in the database.
- Steady-state flows only (no capacities, travel times or time series).
- Frontend unit tests are light (helpers, components, slide navigation); the interactive flows were verified with the browser walkthrough above, which is not part of the repository's test suite.
