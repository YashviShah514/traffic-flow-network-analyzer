export type Level = "Beginner" | "Intermediate" | "Advanced";
export interface QA { level: Level; q: string; a: string }
export interface Category { name: string; items: QA[] }

export const VIVA: Category[] = [
  { name: "Linear Algebra", items: [
    { level: "Beginner", q: "What is a system of linear equations?", a: "A set of equations in which every unknown appears only to the first power. In our app each junction gives one: e.g. for Network 1, x1 = 60 and x1 − x2 = 30." },
    { level: "Beginner", q: "Why does traffic lead to linear equations?", a: "Conservation: at every junction (incoming + external inflow) = outgoing. Sums of flows are linear in the road flows." },
    { level: "Intermediate", q: "Classify the three possible outcomes of AX = B.", a: "No solution (rank A < rank [A|B]), unique (rank = number of unknowns), infinitely many (consistent and rank < unknowns). Network 1 is unique, Networks 2 and 3 are infinite." },
    { level: "Advanced", q: "Why is the sum of all junction equations 0 = (sum of external flows) when every road is unknown?", a: "Each unknown road appears once with +1 (at its target) and once with −1 (at its source), so the columns of A sum to zero. Hence the system can be consistent only if total external inflow is 0 — and rank(A) ≤ junctions − 1." },
  ]},
  { name: "Matrix Operations", items: [
    { level: "Beginner", q: "What are A, X and B?", a: "A = coefficient matrix (one row per junction, one column per unknown road, entries +1 / −1 / 0); X = vector of unknown flows; B = constants after moving known sensor flows and external flows to the right-hand side." },
    { level: "Intermediate", q: "What is the augmented matrix?", a: "[A | B] — A with B appended as an extra column. Row operations on it keep the solution set unchanged." },
    { level: "Intermediate", q: "Which entries can be ±1 only?", a: "The entries of A: a road leaves one junction (−1) and enters another (+1). Self-loops are rejected because they would cancel to 0." },
  ]},
  { name: "Gaussian Elimination", items: [
    { level: "Beginner", q: "What does Gaussian elimination do?", a: "Uses row swaps and row additions to create zeros below each pivot, producing Row Echelon Form (REF). Our solver shows each swap and R_i ← R_i − k·R_j step." },
    { level: "Intermediate", q: "What are the three elementary row operations?", a: "Swap two rows; multiply a row by a nonzero scalar; add a multiple of one row to another. All are reversible, so the solutions are preserved." },
    { level: "Advanced", q: "Do you need partial pivoting?", a: "Not here: we use exact rational (Fraction) arithmetic, so there is no rounding error to control. We just pick the first nonzero entry." },
  ]},
  { name: "RREF", items: [
    { level: "Beginner", q: "How does RREF differ from REF?", a: "In RREF every pivot is 1 and is the only nonzero entry in its column. Gauss-Jordan elimination continues from REF by scaling and clearing entries above pivots." },
    { level: "Intermediate", q: "Is RREF unique?", a: "Yes — every matrix has exactly one RREF. That is why we can compare our result with SymPy's rref() entry by entry." },
  ]},
  { name: "Matrix Rank", items: [
    { level: "Beginner", q: "Define rank.", a: "The number of pivots in the (R)REF = the number of linearly independent rows/columns. Network 3 has rank 4." },
    { level: "Intermediate", q: "State the rank–nullity theorem and verify it for Network 3.", a: "rank + nullity = number of unknowns. Network 3: 4 + 2 = 6." },
    { level: "Advanced", q: "Why is the rank of a connected network's incidence structure at most V − 1?", a: "Rows of the junction equations sum to zero (see above), so one row is always dependent per connected component: rank ≤ V − (#components)." },
  ]},
  { name: "Free Variables", items: [
    { level: "Beginner", q: "What is a free variable?", a: "An unknown whose column has no pivot. It can take any value; pivot variables are then determined. Network 2 has one free variable (x3)." },
    { level: "Intermediate", q: "Give the general solution of Network 2.", a: "x1 = 30 + t, x2 = 70 − t, x3 = t. Physically feasible only for 0 ≤ t ≤ 70, since flows can't be negative." },
  ]},
  { name: "Null Space", items: [
    { level: "Beginner", q: "What is the null space?", a: "All vectors v with Av = 0. For Network 2: multiples of (1, −1, 1)." },
    { level: "Intermediate", q: "What does a null-space vector mean for traffic?", a: "A circulation: add t cars on roads with +1 and remove t on roads with −1, and every junction still balances." },
    { level: "Advanced", q: "How are the basis vectors obtained from the RREF?", a: "For each free variable f set it to 1, other free variables to 0, and solve pivot variable p_i = −(RREF entry in column f). The solver tests A·v = 0 in exact arithmetic and compares the subspace with SymPy's nullspace()." },
    { level: "Advanced", q: "Why do general solutions have the form particular + null-space combination?", a: "If Ax_p = b and Av = 0 then A(x_p + v) = b; conversely any two solutions differ by a null-space vector." },
  ]},
  { name: "Graph Theory", items: [
    { level: "Beginner", q: "How is the network modelled as a graph?", a: "Junctions = vertices, one-way roads = directed edges." },
    { level: "Intermediate", q: "Weak vs strong connectivity?", a: "Weak: connected when directions are ignored. Strong: every vertex reachable from every other following directions. The graph A→B←C is weakly but not strongly connected." },
    { level: "Advanced", q: "How do cycles relate to the null space?", a: "With all roads unknown, the null space of A is the cycle space of the graph (dimension E − V + components). Sensors remove roads from the unknown set, shrinking it." },
  ]},
  { name: "BFS", items: [
    { level: "Beginner", q: "How does BFS work?", a: "Start at a vertex, use a queue, visit all neighbours level by level." },
    { level: "Intermediate", q: "Complexity?", a: "O(V + E) with adjacency lists (each vertex enqueued once, each edge examined once)." },
    { level: "Intermediate", q: "How do you find weak components with BFS?", a: "Run BFS on the undirected adjacency view from each unvisited vertex; each run is one component." },
  ]},
  { name: "Database Management", items: [
    { level: "Beginner", q: "List the tables.", a: "users, networks, junctions, roads, observed_flows, solutions." },
    { level: "Intermediate", q: "Which constraints exist?", a: "PKs, FKs with ON DELETE CASCADE, UNIQUE(network_id, key) for junctions and roads, CHECK(source ≠ target), CHECK(flow ≥ 0)." },
    { level: "Advanced", q: "Why is a measured flow a separate row?", a: "Normalisation: 'known' is optional data for a road; absence of a row means the road is an unknown variable, and measured_at can record when the sensor reported." },
  ]},
  { name: "Backend", items: [
    { level: "Beginner", q: "What is FastAPI?", a: "A Python web framework that builds REST APIs from type-annotated functions and auto-generates /docs." },
    { level: "Intermediate", q: "How is input validated?", a: "Pydantic models validate shapes and numbers; engine-level checks (dangling endpoints, self loops, negative flows) raise errors that become HTTP 422 responses." },
    { level: "Advanced", q: "Why Fractions rather than floats?", a: "Row reduction with floats produces round-off (0.1+0.2≠0.3), which can falsely create or hide pivots. Fractions make rank and AX=B checks exact." },
  ]},
  { name: "Frontend", items: [
    { level: "Beginner", q: "What does React Flow provide?", a: "A node/edge canvas with zoom, pan, drag and connect handlers; we render junctions as nodes and roads as custom directed edges." },
    { level: "Intermediate", q: "How does the UI update equations live?", a: "A debounced effect posts the current draft to /api/analyze; the response feeds every page." },
  ]},
  { name: "Project Architecture", items: [
    { level: "Beginner", q: "Name the layers.", a: "React UI → FastAPI (engine, graph, services) → SQLAlchemy → PostgreSQL." },
    { level: "Advanced", q: "How do you know the results are right?", a: "Three independent checks: exact AX = B and Av = 0, back-substitution agreeing with Gauss-Jordan, and SymPy's rref/rank/nullspace comparison. Demo networks are built from known ground-truth flows." },
  ]},
];
