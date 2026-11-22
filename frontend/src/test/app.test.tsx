import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Matrix } from "@/components/Matrix";
import { NetworkDiagram } from "@/components/NetworkDiagram";
import { VIVA } from "@/content/viva";
import { DOCS } from "@/content/docs";
import { ROLES } from "@/content/roles";
import { externalBalance, nextKey, toNumber, variableNames } from "@/lib/network";
import PresentationMode, { SLIDE_COUNT } from "@/pages/PresentationMode";
import Team from "@/pages/Team";
import type { NetworkDraft } from "@/lib/types";

const net: NetworkDraft = {
  name: "t", description: "",
  junctions: [{ key: "A", name: "A", x: 0, y: 0, external_inflow: "10" }, { key: "B", name: "B", x: 100, y: 0, external_inflow: "-10" }],
  roads: [{ key: "r1", label: "", source: "A", target: "B", known_flow: null }, { key: "r2", label: "", source: "A", target: "B", known_flow: "4" },
          { key: "r3", label: "", source: "B", target: "A", known_flow: null }],
};

describe("network helpers", () => {
  it("numbers only unknown roads", () => expect(variableNames(net)).toEqual({ r1: "x1", r3: "x2" }));
  it("generates unique keys", () => expect(nextKey("J", ["J1", "J3"])).toBe("J4"));
  it("parses fractions", () => { expect(toNumber("7/2")).toBe(3.5); expect(toNumber("-4")).toBe(-4); });
  it("sums external flow", () => expect(externalBalance(net)).toBe(0));
});

describe("components", () => {
  it("renders every matrix entry", () => {
    render(<Matrix data={[["1", "0"], ["-1/2", "3"]]} />);
    ["1", "0", "-1/2", "3"].forEach((v) => expect(screen.getAllByText(v).length).toBeGreaterThan(0));
  });
  it("draws one arrow marker per road colour and labels unknowns", () => {
    const { container } = render(<NetworkDiagram net={net} />);
    expect(container.querySelectorAll("line").length).toBe(3);
    expect(container.querySelectorAll("line[marker-end]").length).toBe(3);
    expect(screen.getByText("x1")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });
  it("team page has an editable placeholder per role", () => {
    render(<Team />);
    const boxes = screen.getAllByPlaceholderText("Enter name…");
    expect(boxes).toHaveLength(5);
    fireEvent.change(boxes[0], { target: { value: "Member X" } });
    expect((boxes[0] as HTMLInputElement).value).toBe("Member X");
  });
});

describe("content", () => {
  it("has the 19 documentation sections and 5 roles", () => { expect(DOCS).toHaveLength(19); expect(ROLES).toHaveLength(5); });
  it("viva covers all 13 categories with all levels", () => {
    expect(VIVA).toHaveLength(13);
    const levels = new Set(VIVA.flatMap((c) => c.items.map((i) => i.level)));
    expect(levels).toEqual(new Set(["Beginner", "Intermediate", "Advanced"]));
  });
});

describe("presentation", () => {
  it("has 21 slides and navigates by keyboard", () => {
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    expect(SLIDE_COUNT).toBe(21);
    render(<MemoryRouter><PresentationMode /></MemoryRouter>);
    expect(screen.getByRole("region", { name: /Slide 1:/ })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByRole("region", { name: /Slide 2:/ })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "End" });
    expect(screen.getByRole("region", { name: /Slide 21:/ })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByRole("region", { name: /Slide 20:/ })).toBeInTheDocument();
  });
});
