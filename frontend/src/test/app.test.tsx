import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Matrix } from "@/components/Matrix";
import { NetworkDiagram } from "@/components/NetworkDiagram";
import { DOCS } from "@/content/docs";
import { VIVA } from "@/content/viva";
import {
  addJunction, addRoad, chooseSolution, emptyNetwork, removeJunction, removeRoad, replay, reverseRoad, roadFlows, applyTraffic, clearTraffic, isPort, roadIds, setEndpoints, setTwoWay,
  splitRoadAt, toNumber, updateRoad, variableNames,
} from "@/lib/graph";
import PresentationMode, { SLIDE_COUNT, SLIDE_TITLES } from "@/pages/PresentationMode";
import type { Analysis, NetworkDraft } from "@/lib/types";

function triangle(): NetworkDraft {
  let n = emptyNetwork();
  for (const at of [{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 100, y: 150 }]) n = addJunction(n, at).net;
  n = addRoad(n, "V1", "V2").net;
  n = addRoad(n, "V2", "V3").net;
  n = addRoad(n, "V3", "V1").net;
  return n;
}

describe("graph editing", () => {
  it("creates junctions and roads that reference real junction ids", () => {
    const n = triangle();
    expect(n.junctions.map((j) => j.key)).toEqual(["V1", "V2", "V3"]);
    expect(n.roads.map((r) => [r.source, r.target])).toEqual([["V1", "V2"], ["V2", "V3"], ["V3", "V1"]]);
  });
  it("blocks self-loops, unknown endpoints and duplicate roads unless parallel roads are allowed", () => {
    const n = triangle();
    expect(addRoad(n, "V1", "V1").error).toMatch(/same junction/);
    expect(addRoad(n, "V1", "V9").error).toMatch(/existing/);
    expect(addRoad(n, "V1", "V2").error).toMatch(/already exists/);
    expect(addRoad(n, "V1", "V2", true).net.roads).toHaveLength(4);
    expect(addRoad(n, "V2", "V1").error).toBeUndefined();
  });
  it("deleting a junction removes every connected road and its measured flow", () => {
    const n = updateRoad(triangle(), "E1", { known_flow: "7" });
    const out = removeJunction(n, "V2");
    expect(out.junctions).toHaveLength(2);
    expect(out.roads.map((r) => r.key)).toEqual(["E3"]);
    expect(removeRoad(out, "E3").roads).toEqual([]);
  });
  it("reverses direction and toggles two-way", () => {
    const n = reverseRoad(triangle(), "E1");
    expect([n.roads[0].source, n.roads[0].target]).toEqual(["V2", "V1"]);
    const two = setTwoWay(n, "E1", true);
    expect(two.roads).toHaveLength(4);
    expect(setTwoWay(two, "E1", false).roads).toHaveLength(3);
  });
  it("changes a road's start or end junction under the same rules as drawing one", () => {
    const n = addJunction(triangle(), { x: 300, y: 300 }).net;
    const moved = setEndpoints(n, "E1", "V1", "V4");
    expect(moved.error).toBeUndefined();
    expect(moved.net.roads[0]).toMatchObject({ key: "E1", source: "V1", target: "V4" });
    expect(moved.net.roads.map((r) => r.key)).toEqual(["E1", "E2", "E3"]); // order (and variable names) unchanged
    expect(setEndpoints(n, "E1", "V2", "V2").error).toMatch(/same junction/);
    expect(setEndpoints(n, "E1", "V2", "V3").error).toMatch(/already exists/);
    expect(setEndpoints(n, "E1", "V2", "V3", true).error).toBeUndefined();
  });
  it("numbers only the unknown roads", () => {
    const n = updateRoad(triangle(), "E2", { known_flow: "4" });
    expect(variableNames(n)).toEqual({ E1: "x1", E3: "x2" });
  });
  it("splits a two-way map road at a point, keeping geometry joined", () => {
    let n: NetworkDraft = { ...emptyNetwork(), method: "map" };
    n = addJunction(n, { x: 0, y: 0, lat: 23.0, lng: 72.5 }).net;
    n = addJunction(n, { x: 100, y: 0, lat: 23.0, lng: 72.502 }).net;
    n = addRoad(n, "V1", "V2").net;
    n = setTwoWay(n, "E1", true);
    n = updateRoad(n, "E1", { known_flow: "30" });
    const out = splitRoadAt(n, "E1", [23.0, 72.501]);
    expect(out.error).toBeUndefined();
    expect(out.net.junctions).toHaveLength(3);
    expect(out.net.roads).toHaveLength(4);
    expect(out.net.roads.filter((r) => r.known_flow === "30")).toHaveLength(1);
    for (const r of out.net.roads) {
      const at = (k: string) => { const j = out.net.junctions.find((x) => x.key === k)!; return [j.lat, j.lng]; };
      expect(r.geometry![0]).toEqual(at(r.source));
      expect(r.geometry![r.geometry!.length - 1]).toEqual(at(r.target));
    }
  });
});

describe("flows and matrices", () => {
  const n = updateRoad(triangle(), "E3", { known_flow: "10" });
  const solution = { parameters: { x2: "0" }, values: { x1: "10", x2: "-3" }, roads: [], mathematically_valid: true, physically_feasible: false, negative_variables: ["x2"] };
  const analysis = {
    road_status: [{ road_key: "E1", variable: "x1", status: "determined", expression: "10" }, { road_key: "E2", variable: "x2", status: "free", expression: "t1" }, { road_key: "E3", variable: null, status: "known", expression: "10" }],
    sample_solution: solution, feasible_example: { ...solution, values: { x1: "10", x2: "4" }, physically_feasible: true },
  } as unknown as Analysis;
  it("labels known, calculated, negative and unsolved flows", () => {
    const f = roadFlows(n, analysis, solution);
    expect([f.E1.kind, f.E2.kind, f.E3.kind]).toEqual(["determined", "negative", "known"]);
    expect(f.E2.text).toBe("x2 = -3"); // never clipped to zero
    expect(roadFlows(n, null, null).E1).toMatchObject({ text: "x1", kind: "unresolved" });
  });
  it("shows a feasible example until the user chooses parameters", () => {
    expect(chooseSolution(analysis, {}).auto).toBe(true);
    expect(chooseSolution(analysis, { x2: "-3" }).solution?.values.x2).toBe("-3");
  });
  it("replays row operations", () => {
    const steps: { changed: Record<string, string[]> }[] = [{ changed: { "1": ["0", "1"] } }, { changed: { "0": ["1", "0"] } }];
    expect(replay([["1", "1"], ["2", "3"]], steps, 1)).toEqual([["1", "1"], ["0", "1"]]);
    expect(replay([["1", "1"], ["2", "3"]], steps, 2)).toEqual([["1", "0"], ["0", "1"]]);
    expect(toNumber("7/2")).toBe(3.5);
  });
});

describe("map networks", () => {
  it("gives every road a unique ID, also for networks saved before IDs existed", () => {
    expect(Object.values(roadIds(triangle()))).toEqual(["E1", "E2", "E3"]);
    const old = { ...triangle(), roads: triangle().roads.map((r, i) => ({ ...r, key: `r${i + 7}` })) };
    expect(Object.values(roadIds(old))).toEqual(["E1", "E2", "E3"]);
  });
  it("fills and clears clearly flagged sample traffic", () => {
    const base: NetworkDraft = { ...triangle(), method: "map", map_meta: {} };
    base.junctions[0] = { ...base.junctions[0], node_type: "boundary" };
    expect(isPort(base, base.junctions[0])).toBe(true);
    expect(isPort(base, base.junctions[1])).toBe(false);
    const filled = applyTraffic(base, { junctions: [{ key: "V1", net_demand: "-30" }], roads: [{ key: "E2", known_flow: "30" }],
      summary: { entry_or_exit_points: 1, measured_roads: 1, note: "sample" } });
    expect(filled.map_meta?.sample_values).toBe(true);
    expect([filled.junctions[0].net_demand, filled.roads[1].known_flow]).toEqual(["-30", "30"]);
    const cleared = clearTraffic(filled);
    expect(cleared.map_meta?.sample_values).toBe(false);
    expect(cleared.junctions.every((j) => j.net_demand === "0") && cleared.roads.every((r) => r.known_flow === null)).toBe(true);
  });
});

describe("components and content", () => {
  it("renders every matrix entry", () => {
    render(<Matrix data={[["1", "0"], ["-1/2", "3"]]} />);
    ["1", "0", "-1/2", "3"].forEach((v) => expect(screen.getAllByText(v).length).toBeGreaterThan(0));
  });
  it("draws one direction arrow per road", () => {
    const { container } = render(<NetworkDiagram net={triangle()} />);
    expect(container.querySelectorAll("polyline")).toHaveLength(3);
    expect(container.querySelectorAll("[data-arrow]")).toHaveLength(3);
    expect(screen.getByText("x1")).toBeInTheDocument();
  });
  it("has the 28 documentation sections and no team contribution content", () => {
    expect(DOCS).toHaveLength(28);
    expect(JSON.stringify([DOCS, VIVA, SLIDE_TITLES])).not.toMatch(/team contribution|team member/i);
  });
  it("presentation has 21 slides and keyboard navigation", () => {
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    expect(SLIDE_COUNT).toBe(21);
    render(<MemoryRouter><PresentationMode /></MemoryRouter>);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByRole("region", { name: /Slide 2:/ })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "End" });
    expect(screen.getByRole("region", { name: /Slide 21:/ })).toBeInTheDocument();
  });
});
