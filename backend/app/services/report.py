"""PDF report generator (ReportLab). Every number comes from the analysis result."""
import io
import math
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, PolyLine, Polygon, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0b1f3a")
BLUE = colors.HexColor("#1d4ed8")
MAX_TABLE_COLUMNS = 16     # wider matrices are printed row by row in sparse form
MAX_PRINTED_STEPS = 250


def _ascii(text: str) -> str:
    """The built-in PDF fonts have no arrow / comparison glyphs."""
    for a, b in (("↔", "<->"), ("→", "->"), ("≥", ">="), ("·", "*"), ("…", "..."), ("−", "-")):
        text = text.replace(a, b)
    return text.encode("cp1252", "replace").decode("cp1252")


def _diagram(schema, result, w=495, h=300) -> Drawing:
    d = Drawing(w, h)
    js = schema.junctions
    if not js:
        return d
    xs, ys = [j.x for j in js], [j.y for j in js]
    use_geo = all(j.lat is not None and j.lng is not None for j in js)
    if use_geo:  # real road shapes
        lat0 = sum(j.lat for j in js) / len(js)
        project = lambda lat, lng: (lng * math.cos(math.radians(lat0)), lat)
        pts = {j.key: project(j.lat, j.lng) for j in js}
        lines = {r.key: [project(*p) for p in r.geometry] if r.geometry else [pts[r.source], pts[r.target]]
                 for r in schema.roads}
    else:
        pts = {j.key: (j.x, -j.y) for j in js}
        lines = {r.key: [pts[r.source], pts[r.target]] for r in schema.roads}
    everything = list(pts.values()) + [p for line in lines.values() for p in line]
    minx, maxx = min(p[0] for p in everything), max(p[0] for p in everything)
    miny, maxy = min(p[1] for p in everything), max(p[1] for p in everything)
    s = min((w - 60) / (maxx - minx or 1), (h - 50) / (maxy - miny or 1))
    place = lambda p: (30 + (p[0] - minx) * s, 25 + (p[1] - miny) * s)

    var = {v["road_key"]: v["name"] for v in result["variables"]}
    small = len(js) > 14
    radius = 6 if small else 14
    for r in schema.roads:
        line = [place(p) for p in lines[r.key]]
        opposite = any(o.source == r.target and o.target == r.source for o in schema.roads)
        if opposite:  # draw the two directions side by side
            (ax, ay), (bx, by) = line[0], line[-1]
            ang = math.atan2(by - ay, bx - ax)
            off = 2 if small else 5
            line = [(x - math.sin(ang) * off, y + math.cos(ang) * off) for x, y in line]
        d.add(PolyLine([c for p in line for c in p], strokeColor=BLUE, strokeWidth=0.8 if small else 1.4))
        # arrow head in the middle of the road
        i = max(0, len(line) // 2 - 1)
        (ax, ay), (bx, by) = line[i], line[i + 1]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        ang = math.atan2(by - ay, bx - ax)
        size = 4 if small else 8
        d.add(Polygon([mx + size / 2 * math.cos(ang), my + size / 2 * math.sin(ang),
                       mx - size * math.cos(ang - .5), my - size * math.sin(ang - .5),
                       mx - size * math.cos(ang + .5), my - size * math.sin(ang + .5)], fillColor=BLUE, strokeColor=BLUE))
        if len(schema.roads) <= 40:
            lab = var.get(r.key) or f"{r.known_flow} (known)"
            d.add(String(mx + 3, my + 4, _ascii(lab), fontSize=6 if small else 8, fillColor=NAVY))
    for j in js:
        x, y = place(pts[j.key])
        d.add(Circle(x, y, radius, fillColor=NAVY, strokeColor=NAVY))
        d.add(String(x, y - (1.8 if small else 3), _ascii(j.name[:4]), fontSize=4.5 if small else 8,
                     fillColor=colors.white, textAnchor="middle"))
        if str(j.net_demand) not in ("0", "0.0"):
            d.add(String(x, y - radius - 9, f"D = {j.net_demand}", fontSize=7, fillColor=colors.HexColor("#0e7490"),
                         textAnchor="middle"))
    return d


def build_pdf(schema, result, validation) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"FlowMatrix Report - {schema.name}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=NAVY)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=BLUE, spaceBefore=10)
    body = ss["BodyText"]
    mono = ParagraphStyle("mono", parent=ss["BodyText"], fontName="Courier", fontSize=8, leading=10)
    cell = ParagraphStyle("cell", parent=ss["BodyText"], fontSize=7.5, leading=9)

    def P(text, style=body):
        return Paragraph(text, style)

    def T(text, style=body):
        return Paragraph(escape(_ascii(str(text))), style)

    def table(rows, header=None, widths=None, font=8):
        data = ([header] if header else []) + [[T(c, cell) for c in row] for row in rows]
        t = Table(data, hAlign="LEFT", colWidths=widths, repeatRows=1 if header else 0)
        st = [("FONTSIZE", (0, 0), (-1, -1), font), ("GRID", (0, 0), (-1, -1), .25, colors.lightgrey),
              ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if header:
            st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        t.setStyle(TableStyle(st))
        return t

    mat = result["matrix"]
    vars_ = mat["variables"]

    def matrix(rows, augmented):
        if not rows or not rows[0]:
            return [P("(no unknown roads)")]
        if len(rows[0]) <= MAX_TABLE_COLUMNS:
            t = Table(rows, hAlign="LEFT")
            style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), .25, colors.lightgrey),
                     ("ALIGN", (0, 0), (-1, -1), "CENTER")]
            if augmented:
                style.append(("LINEBEFORE", (-1, 0), (-1, -1), 1.2, BLUE))
            t.setStyle(TableStyle(style))
            return [t]
        out = [T(f"{len(rows)} x {len(rows[0])} matrix, printed row by row (non-zero entries only).")]
        for i, row in enumerate(rows, 1):
            coeffs = row[:len(vars_)]
            terms = ", ".join(f"{vars_[k]}: {v}" for k, v in enumerate(coeffs) if v != "0") or "all zero"
            tail = f"  |  {row[-1]}" if augmented else ""
            out.append(T(f"R{i}: {terms}{tail}", mono))
        return out

    a = result["analysis"]
    jn = {j.key: j.name for j in schema.junctions}
    var = {v["road_key"]: v["name"] for v in result["variables"]}
    method = "Automatic, from OpenStreetMap data" if schema.method == "map" else "Manual"
    el = [P("FlowMatrix - Traffic Flow Analysis Report", h1), T(f"Network: {schema.name}"),
          T(f"Creation method: {method}"), T(schema.description or "")]
    meta = schema.map_meta or {}
    if schema.method == "map" and meta:
        first = meta.get("start") or meta.get("pickup") or {}
        second = meta.get("end") or meta.get("destination") or {}
        el.append(T(f"Location 1: {first.get('label', '')}   Location 2: {second.get('label', '')}. "
                    "Road data (c) OpenStreetMap contributors."))
    if meta.get("sample_values"):
        el.append(T("NOTE: the traffic values in this network are SAMPLE values for demonstration, not real counts."))
    el += [Spacer(1, 6), P("1. Network diagram", h2), _diagram(schema, result)]

    el += [P("2. Validation", h2)]
    el += [T(f"{validation['counts']['junctions']} junctions, {validation['counts']['roads']} roads, "
             f"{validation['counts']['components']} connected part(s).")]
    el += [T("- " + w["message"]) for w in validation["warnings"]] or [T("No warnings.")]

    el += [P("3. Junctions", h2), table([[j.name, j.node_type, j.net_demand] for j in schema.junctions],
                                        ["Junction", "Type", "Net external demand D"])]
    el += [P("4. Roads", h2), table([[r.key, r.label or "Unnamed road", f"{jn[r.source]} → {jn[r.target]}",
                                      var.get(r.key, "-"), r.known_flow if r.known_flow is not None else "unknown",
                                      f"{r.length_m:.0f} m" if r.length_m else "-"] for r in schema.roads],
                                    ["ID", "Road", "Direction", "Variable", "Measured flow", "Length"],
                                    widths=[12 * mm, 52 * mm, 30 * mm, 18 * mm, 28 * mm, 18 * mm])]
    el += [P("5. Traffic conservation equations", h2),
           T("Convention: incoming flow - outgoing flow = D (D = net vehicles leaving the network at the junction).")]
    el += [T(f"{e['junction_name']}:  {e['text']}", mono) for e in result["equations"]]
    el += [P("6. Coefficient matrix A", h2), T("Columns: " + ", ".join(vars_))] + matrix(mat["A"], False)
    el += [P("7. Augmented matrix [A | B]", h2)] + matrix(mat["augmented"], True)
    red = result["reduction"]
    ops = [s for s in red["steps"] if s["kind"] != "pivot"]
    el += [P("8. Row operations", h2)]
    el += [T(f"Step {s['index']} ({'Gaussian' if s['phase'] == 'forward' else 'Gauss-Jordan'}):  {s['notation']}", mono)
           for s in ops[:MAX_PRINTED_STEPS]]
    if len(ops) > MAX_PRINTED_STEPS:
        el.append(T(f"... {len(ops) - MAX_PRINTED_STEPS} further operations omitted; the application shows all of them."))
    if not ops:
        el.append(T("No row operations were needed."))
    el += [P("9. REF (Gaussian elimination)", h2)] + matrix(red["ref"], True)
    el += [P("10. RREF (Gauss-Jordan elimination)", h2)] + matrix(red["rref"], True)
    el += [P("11. Rank and classification", h2),
           T(f"Rank = independent equations = {a['rank']}; unknowns = {a['n_unknowns']}; equations = {a['n_equations']}; "
             f"nullity = {a['nullity']}. Classification: {a['classification']}."),
           T("Pivot variables: " + (", ".join(a["pivot_variables"]) or "none")),
           T("Free variables: " + (", ".join(a["free_variables"]) or "none"))]
    if a["consistent"]:
        el.append(P("12. General solution", h2))
        el += [T(g["text"], mono) for g in a["general_solution"]]
    el.append(P("13. Null space basis (AX = 0)", h2))
    if a["null_basis"]:
        for b in a["null_basis"]:
            nz = ", ".join(f"{vars_[i]}: {c}" for i, c in enumerate(b["vector"]) if c != "0")
            el.append(T(f"{b['parameter']} (free {b['free_variable']}): {nz}; all other roads 0.", mono))
    else:
        el.append(T("The null space is {0}: no circulating traffic is possible."))
    sample, feas = result["sample_solution"], result["feasible_example"]
    if sample:
        el.append(P("14. Example solution and final traffic flows", h2))
        shown = [("Chosen parameter values", sample)]
        if feas and feas["parameters"] != sample["parameters"]:
            shown.append(("A physically feasible example", feas))
        for title, ex in shown:
            ok = ("physically feasible" if ex["physically_feasible"]
                  else "NOT physically feasible - negative flow on " + ", ".join(ex["negative_variables"]))
            params = ", ".join(f"{k} = {v}" for k, v in ex["parameters"].items()) or "none"
            el.append(T(f"{title} (parameters: {params}): mathematically valid, {ok}."))
            el.append(table([[r["label"] or "Unnamed road", f"{r['from']} → {r['to']}", r["value"],
                              "measured" if r["known"] else "computed"] for r in ex["roads"]],
                            ["Road", "Direction", "Flow", "Source"], widths=[75 * mm, 40 * mm, 25 * mm, 25 * mm]))
            el.append(Spacer(1, 4))
    fe = result["feasibility"]
    el += [P("15. Physical feasibility", h2),
           T({True: "A nonnegative flow assignment exists.",
              False: "No nonnegative assignment exists: the data is mathematically inconsistent with one-way traffic.",
              None: "Feasibility could not be determined."}[fe.get("exists")])]
    if fe.get("ranges"):
        el.append(table([[k, v["min"], "unbounded" if v["max"] is None else v["max"]] for k, v in fe["ranges"].items()],
                        ["Variable", "Minimum", "Maximum"]))
    v = result["verification"]
    el += [P("16. Verification", h2),
           T("Exact checks AX = B, Av = 0, rank-nullity, back substitution and a SymPy cross-check: "
             + ("ALL PASSED." if v["all_passed"] else "FAILED."))]
    g = result["graph"]
    el += [P("17. Graph connectivity", h2),
           T(f"Weakly connected: {'yes' if g['weakly_connected'] else 'no'}. Strongly connected: "
             f"{'yes' if g['strongly_connected'] else 'no'}. Isolated junctions: "
             f"{', '.join(g['isolated_junctions']) or 'none'}.")]
    el += [P("18. Conclusion", h2), T(result["conclusion"])]
    doc.build(el)
    return buf.getvalue()
