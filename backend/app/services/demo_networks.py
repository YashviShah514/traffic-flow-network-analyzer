"""Three demonstration networks (manual method). ``net_demand`` D is the net traffic LEAVING the
network at a junction (negative = traffic enters): incoming - outgoing = D.
Each was built from a known ground-truth flow assignment so conservation holds exactly;
tests re-verify them with the solver."""


def _j(key, x, y, demand):
    return {"key": key, "name": key, "x": x, "y": y, "net_demand": demand}


def _r(key, source, target, label, flow=None):
    return {"key": key, "label": label, "source": source, "target": target, "known_flow": flow}


DEMO_NETWORKS = [
    {
        "name": "Network 1 - Basic Traffic Network",
        "description": "3 junctions, 3 roads. One sensor on road A->C makes the system uniquely solvable (x1=60, x2=30).",
        "junctions": [_j("A", 80, 140, "-100"), _j("B", 380, 40, "30"), _j("C", 380, 260, "70")],
        "roads": [_r("E1", "A", "B", "A to B"), _r("E2", "B", "C", "B to C"), _r("E3", "A", "C", "A to C (sensor)", "40")],
    },
    {
        "name": "Network 2 - Intermediate Traffic Network",
        "description": "3 junctions, 4 roads, one free variable: x1=30+t, x2=70-t, x3=t (feasible for 0<=t<=70).",
        "junctions": [_j("A", 80, 150, "-90"), _j("B", 380, 40, "30"), _j("C", 380, 270, "60")],
        "roads": [_r("E1", "A", "B", "A to B"), _r("E2", "A", "C", "A to C"), _r("E3", "B", "C", "B to C"),
                  _r("E4", "C", "A", "C to A (sensor)", "10")],
    },
    {
        "name": "Network 3 - Advanced Traffic Network",
        "description": "5 junctions, 7 roads, rank 4, two free variables, strongly connected.",
        "junctions": [_j("J1", 60, 160, "-70"), _j("J2", 280, 40, "0"), _j("J3", 280, 280, "10"),
                      _j("J4", 520, 40, "5"), _j("J5", 520, 280, "55")],
        "roads": [_r("E1", "J1", "J2", "J1 to J2"), _r("E2", "J1", "J3", "J1 to J3"), _r("E3", "J2", "J3", "J2 to J3"),
                  _r("E4", "J2", "J4", "J2 to J4"), _r("E5", "J3", "J5", "J3 to J5"), _r("E6", "J4", "J5", "J4 to J5"),
                  _r("E7", "J5", "J1", "J5 to J1 (sensor)", "20")],
    },
]
