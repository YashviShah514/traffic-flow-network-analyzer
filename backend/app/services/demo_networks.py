"""Three demonstration networks. External inflow is NET traffic entering a junction
(negative = leaving). Each was built from a known ground-truth flow assignment
so conservation holds exactly; tests re-verify them with the solver."""

DEMO_NETWORKS = [
    {
        "name": "Network 1 - Basic Traffic Network",
        "description": "3 junctions, 3 roads. One sensor on road A->C makes the system uniquely solvable (x1=60, x2=30).",
        "junctions": [
            {"key": "A", "name": "A", "x": 80, "y": 140, "external_inflow": "100"},
            {"key": "B", "name": "B", "x": 380, "y": 40, "external_inflow": "-30"},
            {"key": "C", "name": "C", "x": 380, "y": 260, "external_inflow": "-70"},
        ],
        "roads": [
            {"key": "r1", "label": "A to B", "source": "A", "target": "B", "known_flow": None},
            {"key": "r2", "label": "B to C", "source": "B", "target": "C", "known_flow": None},
            {"key": "r3", "label": "A to C (sensor)", "source": "A", "target": "C", "known_flow": "40"},
        ],
    },
    {
        "name": "Network 2 - Intermediate Traffic Network",
        "description": "3 junctions, 4 roads, one free variable: x1=30+t, x2=70-t, x3=t (feasible for 0<=t<=70).",
        "junctions": [
            {"key": "A", "name": "A", "x": 80, "y": 150, "external_inflow": "90"},
            {"key": "B", "name": "B", "x": 380, "y": 40, "external_inflow": "-30"},
            {"key": "C", "name": "C", "x": 380, "y": 270, "external_inflow": "-60"},
        ],
        "roads": [
            {"key": "r1", "label": "A to B", "source": "A", "target": "B", "known_flow": None},
            {"key": "r2", "label": "A to C", "source": "A", "target": "C", "known_flow": None},
            {"key": "r3", "label": "B to C", "source": "B", "target": "C", "known_flow": None},
            {"key": "r4", "label": "C to A (sensor)", "source": "C", "target": "A", "known_flow": "10"},
        ],
    },
    {
        "name": "Network 3 - Advanced Traffic Network",
        "description": "5 junctions, 7 roads, rank 4, two free variables, strongly connected.",
        "junctions": [
            {"key": "J1", "name": "J1", "x": 60, "y": 160, "external_inflow": "70"},
            {"key": "J2", "name": "J2", "x": 280, "y": 40, "external_inflow": "0"},
            {"key": "J3", "name": "J3", "x": 280, "y": 280, "external_inflow": "-10"},
            {"key": "J4", "name": "J4", "x": 520, "y": 40, "external_inflow": "-5"},
            {"key": "J5", "name": "J5", "x": 520, "y": 280, "external_inflow": "-55"},
        ],
        "roads": [
            {"key": "r1", "label": "J1 to J2", "source": "J1", "target": "J2", "known_flow": None},
            {"key": "r2", "label": "J1 to J3", "source": "J1", "target": "J3", "known_flow": None},
            {"key": "r3", "label": "J2 to J3", "source": "J2", "target": "J3", "known_flow": None},
            {"key": "r4", "label": "J2 to J4", "source": "J2", "target": "J4", "known_flow": None},
            {"key": "r5", "label": "J3 to J5", "source": "J3", "target": "J5", "known_flow": None},
            {"key": "r6", "label": "J4 to J5", "source": "J4", "target": "J5", "known_flow": None},
            {"key": "r7", "label": "J5 to J1 (sensor)", "source": "J5", "target": "J1", "known_flow": "20"},
        ],
    },
]
