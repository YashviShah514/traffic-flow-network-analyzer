export interface DocSection { title: string; body: string[] }

export const DOCS: DocSection[] = [
  { title: "Abstract", body: [
    "The Traffic Flow Network Analyzer estimates unknown vehicle flows on the roads of a directed network using Linear Algebra and Graph Theory. Each junction contributes a flow-conservation equation; sensor measurements fix some road flows and the remainder become unknowns. The resulting linear system AX = B is solved by hand-written Gaussian and Gauss-Jordan elimination in exact rational arithmetic. The application classifies the system, exposes free variables and the null space (circulating traffic), checks physical feasibility (nonnegative flows), analyses connectivity with BFS, stores everything in a relational database and produces PDF reports.",
  ]},
  { title: "Introduction", body: [
    "Traffic engineers cannot place sensors on every road. Conservation of vehicles at junctions nevertheless couples all flows together, so measured values constrain the unmeasured ones. The same mathematics applies to water, electricity, pipeline and computer-network flows.",
  ]},
  { title: "Problem definition", body: [
    "Given junctions with external net inflow e_j, directed roads, and measured flows on a subset of roads, determine all flow assignments x on the remaining roads such that at every junction: incoming + e_j = outgoing.",
  ]},
  { title: "Objectives", body: [
    "Model a directed traffic network interactively.", "Generate the conservation equations and the matrices A, B and [A|B] automatically.",
    "Perform row reduction step by step and verify it independently.", "Classify the system; compute the general solution and null-space basis.",
    "Separate mathematically valid from physically feasible solutions.", "Analyse connectivity (adjacency lists, BFS).", "Persist networks and solutions; export reports.",
  ]},
  { title: "Scope", body: [
    "Steady-state (static) flows on one-way roads. Parallel roads are allowed; self-loops are rejected. Flow values are decimals with up to six places or exact fractions. Authentication, time-varying flows and optimisation of traffic are out of scope.",
  ]},
  { title: "Functional requirements", body: [
    "FR1 Create, edit, delete junctions and directed roads.", "FR2 Enter external inflow per junction and measured flow per road.", "FR3 Show per-junction equation derivations.",
    "FR4 Display A, X, B, [A|B].", "FR5 Show every row operation with intermediate matrices, REF and RREF.", "FR6 Classify solutions; show general solution, free variables, null space.",
    "FR7 Let the user choose parameter values and check nonnegativity.", "FR8 Show adjacency lists, BFS, reachability, weak connectivity, isolated junctions.",
    "FR9 Save/load networks and solutions in the database.", "FR10 Generate a PDF report.",
  ]},
  { title: "Non-functional requirements", body: [
    "Correctness: all arithmetic exact (Python Fractions); every solution re-checked as AX = B and Av = 0.", "Usability: responsive layout, readable matrices, inline error messages.",
    "Maintainability: separate engine, graph, persistence, API and UI modules, each with tests.", "Portability: SQLite for local development, PostgreSQL in production through DATABASE_URL.",
  ]},
  { title: "System architecture", body: [
    "Browser (React + React Flow) ⇄ REST/JSON ⇄ FastAPI ⇄ SQLAlchemy ⇄ PostgreSQL. The API contains three stateless engines (equations/linear algebra, graph, report) and a persistence service. The UI keeps a draft network and requests POST /api/analyze for live results; saving calls POST/PUT /api/networks.",
  ]},
  { title: "Technology stack", body: [
    "Frontend: React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui-style components (hand-written, same cva + cn conventions), Lucide icons, React Flow (@xyflow/react), Recharts.",
    "Backend: Python, FastAPI, Pydantic, SQLAlchemy 2, NumPy, SciPy (feasibility LP), SymPy (verification), ReportLab (PDF).", "Database: PostgreSQL (SQLite for development/tests). Testing: Pytest, Vitest. Deployment: Vercel (frontend), Render (backend + managed PostgreSQL).",
  ]},
  { title: "Mathematical methodology", body: [
    "Equation per junction j:  Σ(in) − Σ(out) = −e_j. Known roads are moved to the right: for unknown roads u, Σ_{u in} x_u − Σ_{u out} x_u = −e_j − Σ(known in) + Σ(known out).",
    "Matrix form AX = B where A ∈ {−1,0,1}^{V×U}. Row reduce [A|B]. Let r = rank(A). If a row reads 0 = c with c ≠ 0 the system has no solution. Otherwise there are n − r free variables; x = x_p + Σ t_k v_k where v_k span the null space.",
    "Feasibility: all x_i ≥ 0 required. The set {x : Ax = B, x ≥ 0} is a polyhedron; a linear program (HiGHS via SciPy) decides emptiness and gives the minimum and maximum of each flow.",
  ]},
  { title: "Algorithm explanations", body: [
    "Gaussian elimination: for each column pick the first row at or below the current row with a nonzero entry, swap it up, and subtract multiples to zero the entries beneath. Result: REF.",
    "Gauss-Jordan: from the last pivot upward scale the pivot row to 1 and clear the entries above. Result: RREF.",
    "Null space: for each free column f, v_f = 1, other free entries 0, pivot entries −RREF[row, f].",
    "BFS: queue-based traversal of adjacency lists in O(V+E). Directed reachability uses out-lists; weak connectivity uses the undirected view; strong connectivity checks that BFS on the out- and in-lists both reach every junction.",
  ]},
  { title: "Database schema", body: [
    "users(id, username, created_at) — networks(id, user_id→users, name, description, is_demo, created_at, updated_at) — junctions(id, network_id→networks, key, name, x, y, external_inflow) — roads(id, network_id, key, label, source_id→junctions, target_id→junctions, position) — observed_flows(id, road_id→roads UNIQUE, value ≥ 0, measured_at) — solutions(id, network_id, created_at, classification, rank, n_equations, n_unknowns, free_variables JSON, parameters JSON, result JSON).",
    "Constraints: UNIQUE(network_id, key) on junctions and roads, CHECK(source_id <> target_id), CHECK(value >= 0), cascading deletes from networks downward.",
  ]},
  { title: "Implementation details", body: [
    "backend/app/engine/linalg.py implements the elimination; solution.py classifies and verifies; equations.py builds the system; pipeline.py assembles the JSON returned to the UI. backend/app/graph/analysis.py contains BFS and connectivity. backend/app/routers/api.py exposes the REST endpoints. frontend/src/lib/store.tsx holds the draft network and debounced analysis.",
    "Authentication is not implemented; all data belongs to a default user.",
  ]},
  { title: "Results", body: [
    "Network 1 (3 junctions, 3 roads): unique solution x1 = 60, x2 = 30, rank 2.",
    "Network 2 (3 junctions, 4 roads): x1 = 30 + t, x2 = 70 − t, x3 = t; null-space basis (1, −1, 1); feasible for 0 ≤ t ≤ 70.",
    "Network 3 (5 junctions, 7 roads): rank 4, two free variables (x3, x6), general solution x1 = 5 + t1 + t2, x2 = 85 − t1 − t2, x4 = 5 + t2, x5 = 75 − t2; strongly connected.",
  ]},
  { title: "Test cases", body: [
    "Engine: unique, infinite, inconsistent, underdetermined, overdetermined, negative-flow infeasibility, fractional inputs, all-roads-known, validation errors, swap steps, null-space vectors (Av = 0), SymPy agreement.",
    "Graph: BFS order and levels, directed vs weak connectivity, disconnected networks, isolated junctions, strong connectivity.",
    "API/DB: CRUD, persistence across sessions, analysis of drafts and saved networks, stored solutions, 422 validation, dashboard statistics, PDF generation.",
    "Frontend (Vitest): helper functions and component rendering.",
  ]},
  { title: "Limitations", body: [
    "Static flows only; no travel times or capacities. Nonnegativity ranges come from floating-point LP. No authentication. Very large networks would need sparse matrices and paginated step output.",
  ]},
  { title: "Future enhancements", body: [
    "Road capacities and cost minimisation (min-cost flow), time-series sensor data, least-squares estimation with noisy sensors, user accounts, importing OpenStreetMap networks.",
  ]},
  { title: "Conclusion", body: [
    "The project shows how Linear Algebra (systems, rank, null space), Graph Theory (adjacency lists, BFS) and database engineering combine into a verified, interactive tool for estimating unknown network flows.",
  ]},
  { title: "References", body: [
    "G. Strang, Introduction to Linear Algebra, Wellesley-Cambridge Press.", "D. Lay, Linear Algebra and Its Applications, Pearson.",
    "T. Cormen et al., Introduction to Algorithms (BFS), MIT Press.", "FastAPI, SQLAlchemy, SymPy, SciPy, React Flow official documentation.",
  ]},
];
