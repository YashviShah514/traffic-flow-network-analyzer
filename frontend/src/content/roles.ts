export interface Role {
  id: string; name: string; short: string; responsibilities: string[]; tech: string[];
  delivered: string[]; module: string; talking: string[]; viva: string[];
}

export const ROLES: Role[] = [
  {
    id: "lead", name: "Role 1 — Project Lead & System Architect", short: "Architecture & integration",
    responsibilities: ["Understand the complete architecture", "Coordinate all modules", "Manage frontend ↔ backend integration", "Define system requirements", "Oversee testing and deployment", "Explain the overall workflow"],
    tech: ["React + Vite", "FastAPI", "PostgreSQL", "Render / Vercel"],
    delivered: ["Monorepo layout: backend/ (FastAPI) and frontend/ (React)", "REST contract in backend/app/routers/api.py consumed by frontend/src/lib/api.ts", "render.yaml + vercel.json deployment configuration", "README with installation and environment setup"],
    module: "The system is three layers: a React UI, a FastAPI service that owns all mathematics, and a relational database. The UI never computes results — it sends the drawn network to POST /api/analyze and renders what comes back.",
    talking: ["Problem: junction inflow = outflow, sensors only on some roads", "Pipeline: draw → equations → matrix → row reduction → classification → graph analysis → report", "Why the maths lives on the server: one tested, exact implementation (Fractions) shared by the UI, the PDF and the database", "Deployment: static frontend on Vercel, API + managed PostgreSQL on Render"],
    viva: ["Walk through what happens when I press 'Save' and then 'Solve'.", "Why is the solver server-side?", "How do you deploy and configure the database?"],
  },
  {
    id: "math", name: "Role 2 — Linear Algebra & Mathematical Engineer", short: "Equations, matrices, row reduction",
    responsibilities: ["Generate flow-conservation equations", "Construct coefficient / augmented matrices", "Implement Gaussian and Gauss-Jordan elimination", "Compute REF, RREF, rank", "Identify pivot and free variables", "Compute general solution and null-space basis", "Verify results"],
    tech: ["Python Fractions", "NumPy / SciPy (LP)", "SymPy (verification)"],
    delivered: ["backend/app/engine/equations.py — equation & matrix generator", "backend/app/engine/linalg.py — hand-written row reduction with recorded steps", "backend/app/engine/solution.py — classification, null space, feasibility, SymPy cross-check", "backend/tests/test_engine.py"],
    module: "Each junction yields one equation  (incoming − outgoing) = −external inflow. Known sensor flows move to the right-hand side, so unknown roads become columns of A. Row reduction in exact rational arithmetic produces REF/RREF; pivots mark determined variables, the remaining columns are free.",
    talking: ["AX = B construction from a graph", "Forward phase = Gaussian (REF); backward phase = Gauss-Jordan (RREF)", "rank(A) < rank([A|B]) ⇒ no solution; rank = n ⇒ unique; rank < n ⇒ ∞ many", "Null space = circulating traffic; rank + nullity = number of unknowns", "Mathematically valid ≠ physically feasible (flows must be ≥ 0)"],
    viva: ["Why must the rows of A sum to zero when no roads are known?", "How do you get null-space vectors from the RREF?", "Why is exact arithmetic used?"],
  },
  {
    id: "graph", name: "Role 3 — Graph Theory & DSA Engineer", short: "Graphs, adjacency lists, BFS",
    responsibilities: ["Directed graph representation", "Adjacency lists", "Breadth-first search", "Connectivity analysis", "Validate junction/road relationships", "Support graph visualisation", "Explain circulation and reachability"],
    tech: ["Python collections.deque", "React Flow", "SVG"],
    delivered: ["backend/app/graph/analysis.py — adjacency lists, BFS, weak components, strong connectivity, isolated detection", "backend/app/engine/equations.py:validate — structural validation", "frontend NetworkDiagram (circulation view)", "backend/tests/test_graph.py"],
    module: "Junctions are vertices, roads are directed edges. Out- and in-adjacency lists are built in O(V+E). BFS on out-lists gives directed reachability; BFS on the undirected view gives weak components.",
    talking: ["Adjacency list vs matrix (space O(V+E))", "BFS uses a queue; visits each vertex/edge once → O(V+E)", "Directed reachability ≠ weak connectivity (A→B←C)", "Disconnected components must balance independently", "Cycles in the graph ↔ null-space vectors"],
    viva: ["Why BFS and not DFS here?", "Give a graph that is weakly but not strongly connected.", "How do you detect isolated junctions?"],
  },
  {
    id: "frontend", name: "Role 4 — Frontend & UI/UX Engineer", short: "Dashboard, editor, solver screens",
    responsibilities: ["Dashboard design", "Interactive network editor", "Junction & road management", "Matrix visualisation", "Solution analysis screens", "Responsive, consistent styling"],
    tech: ["React 18", "TypeScript", "Tailwind CSS", "shadcn/ui-style components", "React Flow", "Recharts", "Lucide"],
    delivered: ["frontend/src/pages/Builder.tsx — React Flow editor with floating directed edges", "frontend/src/pages/Solver.tsx — equations, matrices, step-through row reduction, solution, null space", "frontend/src/pages/PresentationMode.tsx — 21 slides", "frontend/src/components/ — Matrix, NetworkDiagram, UI primitives"],
    module: "The editor keeps one 'draft network' in React context; every change is debounced and re-analysed by the backend so equations and matrices stay live. Unknown roads are auto-labelled x1, x2, …",
    talking: ["User journey: create → inspect equations → solve → null space → graph → report", "Controlled React Flow state and custom edges with arrowheads", "Accessible colours, keyboard navigation, responsive sidebar", "Error handling: backend validation messages are shown inline"],
    viva: ["How does the UI stay in sync with the maths?", "How do you draw arrowheads on directed edges?", "What happens when the backend is down?"],
  },
  {
    id: "backend", name: "Role 5 — Database, Backend & QA Engineer", short: "PostgreSQL, API, tests, reports",
    responsibilities: ["Design the database", "Relationships & constraints", "FastAPI endpoints", "Store networks and solutions", "Validation", "Test maths and APIs", "Generate reports"],
    tech: ["PostgreSQL", "SQLAlchemy 2", "FastAPI", "Pydantic", "Pytest", "ReportLab", "Vitest"],
    delivered: ["backend/app/models.py — users, networks, junctions, roads, observed_flows, solutions", "backend/app/routers/api.py — REST endpoints", "backend/app/services/report.py — PDF report", "backend/tests — engine, graph, API and persistence tests; frontend Vitest suite"],
    module: "A road is 'known' exactly when it has an observed_flows row. Deleting a network cascades to its junctions, roads, flows and solutions. Constraints: no self-loop roads, measured flow ≥ 0, unique keys per network.",
    talking: ["ER diagram and foreign keys", "Pydantic validation → HTTP 422 with readable messages", "SQLite fallback for dev / PostgreSQL in production via DATABASE_URL", "Testing strategy: exact AX=B and Av=0 checks, SymPy cross-check, API integration tests"],
    viva: ["Why store sensor values in a separate table?", "How is persistence tested?", "What does ON DELETE CASCADE do here?"],
  },
];
