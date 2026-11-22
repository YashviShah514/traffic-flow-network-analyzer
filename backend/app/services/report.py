"""PDF report generator (ReportLab). Every number comes from the analysis result."""
import io
import math

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0b1f3a")
BLUE = colors.HexColor("#1d4ed8")


def _diagram(schema, result, w=480, h=260) -> Drawing:
    d = Drawing(w, h)
    js = schema.junctions
    if not js:
        return d
    xs, ys = [j.x for j in js], [j.y for j in js]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sx = (w - 80) / (maxx - minx or 1)
    sy = (h - 60) / (maxy - miny or 1)
    s = min(sx, sy)
    pos = {j.key: (40 + (j.x - minx) * s, h - 30 - (j.y - miny) * s) for j in js}
    var = {v["road_key"]: v["name"] for v in result["variables"]}
    for r in schema.roads:
        (x1, y1), (x2, y2) = pos[r.source], pos[r.target]
        ang = math.atan2(y2 - y1, x2 - x1)
        # opposite roads between the same pair are drawn side by side
        off = 5 if any(o.source == r.target and o.target == r.source for o in schema.roads) else 0
        ox, oy = -math.sin(ang) * off, math.cos(ang) * off
        ax, ay = x1 + 16 * math.cos(ang) + ox, y1 + 16 * math.sin(ang) + oy
        bx, by = x2 - 16 * math.cos(ang) + ox, y2 - 16 * math.sin(ang) + oy
        d.add(Line(ax, ay, bx, by, strokeColor=BLUE, strokeWidth=1.5))
        d.add(Polygon([bx, by, bx - 8 * math.cos(ang - .4), by - 8 * math.sin(ang - .4),
                       bx - 8 * math.cos(ang + .4), by - 8 * math.sin(ang + .4)], fillColor=BLUE, strokeColor=BLUE))
        lab = var.get(r.key) or f"{r.known_flow} (known)"
        d.add(String((ax + bx) / 2 + 3 + ox, (ay + by) / 2 + 4 + oy, lab, fontSize=8, fillColor=NAVY))
    for j in js:
        x, y = pos[j.key]
        d.add(Circle(x, y, 16, fillColor=NAVY, strokeColor=NAVY))
        d.add(String(x, y - 3, j.name[:4], fontSize=8, fillColor=colors.white, textAnchor="middle"))
        ext = j.external_inflow
        if str(ext) not in ("0", "0.0"):
            d.add(String(x, y + 21, f"ext {ext}", fontSize=7, fillColor=colors.HexColor("#0e7490"), textAnchor="middle"))
    return d


def _mtable(rows, header=None, font=8):
    data = ([header] if header else []) + rows
    t = Table(data, hAlign="LEFT")
    st = [("FONTSIZE", (0, 0), (-1, -1), font), ("GRID", (0, 0), (-1, -1), .25, colors.lightgrey),
          ("ALIGN", (0, 0), (-1, -1), "CENTER")]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(st))
    return t


def build_pdf(schema, result) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Traffic Flow Report - {schema.name}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=NAVY)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=BLUE, spaceBefore=10)
    body, mono = ss["BodyText"], ParagraphStyle("mono", parent=ss["Code"], fontSize=8)
    P = lambda t, s=body: Paragraph(t, s)
    a = result["analysis"]
    mat = result["matrix"]
    vars_ = mat["variables"]
    el = [P("Traffic Flow Network Analyzer - Report", h1), P(f"<b>Network:</b> {schema.name}"),
          P(schema.description or ""), Spacer(1, 6), P("1. Network diagram", h2), _diagram(schema, result)]

    el += [P("2. Junctions", h2), _mtable([[j.name, j.key, j.external_inflow] for j in schema.junctions],
                                          ["Junction", "Key", "External net inflow"])]
    var = {v["road_key"]: v["name"] for v in result["variables"]}
    jn = {j.key: j.name for j in schema.junctions}
    el += [P("3. Roads", h2), _mtable([[r.label or r.key, f"{jn[r.source]} -> {jn[r.target]}",
                                        var.get(r.key, "known"), r.known_flow or "unknown"] for r in schema.roads],
                                      ["Road", "Direction", "Variable", "Measured flow"])]
    el += [P("4. Flow-conservation equations", h2),
           P("Rule: incoming + external inflow = outgoing, i.e. (incoming - outgoing) = -(external inflow).")]
    for e in result["equations"]:
        el.append(P(f"<b>{e['junction_name']}</b>: {e['text']}", mono))
    el += [P("5. Matrices", h2), P("Coefficient matrix A (columns: " + ", ".join(vars_) + "):"),
           _mtable(mat["A"] or [[""]]), Spacer(1, 4), P("Augmented matrix [A | B]:"), _mtable(mat["augmented"] or [[""]])]
    red = result["reduction"]
    el += [P("6. Row echelon forms", h2), P("REF (Gaussian elimination):"), _mtable(red["ref"] or [[""]]),
           Spacer(1, 4), P("RREF (Gauss-Jordan):"), _mtable(red["rref"] or [[""]])]
    el += [P("7. Row operations", h2)]
    for s in red["steps"]:
        if s["kind"] != "pivot":
            el.append(P(f"Step {s['index']} [{s['phase']}]: <b>{s['notation'].replace('<', '&lt;').replace('>', '&gt;')}</b> - {s['description']}", body))
    el += [P("8. Rank and classification", h2),
           P(f"Rank = {a['rank']}; unknowns = {a['n_unknowns']}; equations = {a['n_equations']}; nullity = {a['nullity']}. "
             f"Classification: <b>{a['classification']}</b>."),
           P("Pivot variables: " + (", ".join(a["pivot_columns"]) or "none") + ". Free variables: " +
             (", ".join(a["free_variables"]) or "none") + ".")]
    if a["consistent"]:
        el.append(P("9. General solution", h2))
        for g in a["general_solution"]:
            el.append(P(g["text"], mono))
        el.append(P("10. Null space basis (AX = 0)", h2))
        if a["null_basis"]:
            for b in a["null_basis"]:
                el.append(P(f"{b['parameter']} * ({', '.join(b['vector'])})  over ({', '.join(vars_)})", mono))
        else:
            el.append(P("Null space is {0}: no circulating traffic is possible."))
        sample, feas = result["sample_solution"], result["feasible_example"]
        el.append(P("11. Example numerical solution", h2))
        shown = [("Chosen parameters", sample)]
        if feas and feas["parameters"] != sample["parameters"]:
            shown.append(("A physically feasible example", feas))
        for title, ex in shown:
            if not ex:
                continue
            ok = "physically feasible" if ex["physically_feasible"] else "NOT physically feasible (negative flow: " + ", ".join(ex["negative_variables"]) + ")"
            el.append(P(f"<b>{title}</b> - parameters: " + (", ".join(f"{k} = {v}" for k, v in ex["parameters"].items()) or "none")
                        + f" - mathematically valid, {ok}."))
            el.append(_mtable([[r["label"] or r["road_key"], f"{r['from']} -> {r['to']}", r["value"],
                                "measured" if r["known"] else "computed"] for r in ex["roads"]],
                              ["Road", "Direction", "Flow", "Source"]))
            el.append(Spacer(1, 4))
    fe = result["feasibility"]
    el += [P("12. Physical feasibility", h2),
           P({True: "A nonnegative assignment exists. Flow ranges over all feasible solutions (LP, floating-point):",
              False: "No nonnegative assignment exists: the solution set is mathematically valid but not physically feasible.",
              None: "Feasibility could not be determined."}[fe.get("exists")])]
    if fe.get("ranges"):
        el.append(_mtable([[k, v["min"], "unbounded" if v["max"] is None else v["max"]] for k, v in fe["ranges"].items()],
                          ["Variable", "Min", "Max"]))
    v = result["verification"]
    el += [P("13. Verification", h2), P(f"Exact checks AX = B, Av = 0, back-substitution, rank-nullity and SymPy cross-check: "
                                        f"<b>{'ALL PASSED' if v['all_passed'] else 'FAILED'}</b>.")]
    g = result["graph"]
    el += [P("14. Graph connectivity", h2),
           P(f"Weakly connected: {g['weakly_connected']}. Strongly connected: {g.get('strongly_connected')}. "
             f"Isolated junctions: {', '.join(g['isolated_junctions']) or 'none'}.")]
    el += [P("15. Conclusion", h2), P(result["conclusion"])]
    doc.build(el)
    return buf.getvalue()
