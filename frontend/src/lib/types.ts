export interface Junction { key: string; name: string; x: number; y: number; external_inflow: string }
export interface Road { key: string; label: string; source: string; target: string; known_flow: string | null }
export interface NetworkDraft {
  id?: number; name: string; description: string; is_demo?: boolean;
  junctions: Junction[]; roads: Road[];
}
export interface NetworkSummary {
  id: number; name: string; description: string; is_demo: boolean; junctions: number; roads: number;
  updated_at: string; classification: string | null; rank: number | null;
}
export interface Variable { name: string; road_key: string; source: string; target: string; label: string }
export interface EquationInfo {
  junction_key: string; junction_name: string; text: string; rhs: string; external_inflow: string;
  known_in_sum: string; known_out_sum: string; derivation: string[]; coefficients: Record<string, string>;
  incoming: RoadDesc[]; outgoing: RoadDesc[];
}
export interface RoadDesc { road_key: string; label: string; from: string; to: string; variable: string | null; known_flow: string | null }
export interface Step {
  index: number; phase: "forward" | "backward"; kind: "pivot" | "swap" | "scale" | "add";
  description: string; notation: string; matrix: string[][]; pivot: [number, number] | null;
}
export interface GeneralTerm { parameter: string; coefficient: string }
export interface SolutionInfo {
  variables_values?: never;
  parameters: Record<string, string>; values: Record<string, string>;
  roads: { road_key: string; label: string; from: string; to: string; value: string; known: boolean; negative: boolean }[];
  mathematically_valid: boolean; physically_feasible: boolean; negative_variables: string[];
}
export interface Analysis {
  variables: Variable[];
  equations: EquationInfo[];
  matrix: { A: string[][]; B: string[]; augmented: string[][]; variables: string[] };
  reduction: { ref: string[][]; rref: string[][]; steps: Step[]; pivot_columns: number[] };
  analysis: {
    classification: "unique" | "infinite" | "none"; consistent: boolean; rank: number; n_unknowns: number;
    n_equations: number; nullity: number; pivot_columns: string[]; free_variables: string[];
    inconsistent_rows: number[]; particular: string[] | null;
    null_basis: { parameter: string; free_variable: string; vector: string[] }[];
    general_solution: { variable: string; constant: string; terms: GeneralTerm[]; is_free: boolean; text: string }[];
  };
  sample_solution: SolutionInfo | null;
  feasible_example: SolutionInfo | null;
  feasibility: { exists: boolean | null; ranges: Record<string, { min: number | null; max: number | null }>; method: string };
  circulations: { parameter: string; free_variable: string; roads: { variable: string; road_key: string; coefficient: string }[] }[];
  verification: { all_passed: boolean; sympy: Record<string, boolean>; [k: string]: unknown };
  graph: GraphResult;
  conclusion: string;
}
export interface GraphResult {
  adjacency_out: Record<string, string[]>; adjacency_in: Record<string, string[]>;
  degrees: Record<string, { in: number; out: number }>;
  weak_components: string[][]; weakly_connected: boolean; isolated_junctions: string[];
  sources_only: string[]; sinks_only: string[]; start: string | null; strongly_connected?: boolean; note?: string;
  bfs_directed?: { order: string[]; levels: Record<string, number>; unreachable: string[] };
  bfs_undirected?: { order: string[]; levels: Record<string, number>; unreachable: string[] };
}
export interface Dashboard {
  total_networks: number; total_junctions: number; total_roads: number; solved_networks: number;
  networks_with_free_variables: number;
  per_network: { name: string; junctions: number; roads: number }[];
  classification_counts: Record<string, number>;
  recent_activity: { type: string; title: string; detail?: string; at: string; id: number }[];
}
