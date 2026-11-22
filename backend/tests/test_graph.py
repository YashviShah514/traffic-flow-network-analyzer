from app.graph.analysis import analyse_graph, bfs, build_adjacency

N = ["A", "B", "C", "D"]
names = {n: n for n in N}


def test_bfs_order_and_levels():
    out, _, _ = build_adjacency(N, [("A", "B"), ("A", "C"), ("B", "D")])
    r = bfs(out, "A")
    assert r["order"] == ["A", "B", "C", "D"] and r["level"]["D"] == 2


def test_directed_vs_weak():
    g = analyse_graph(["A", "B", "C"], {k: k for k in "ABC"}, [("A", "B"), ("C", "B")], "A")
    assert g["weakly_connected"] is True
    assert g["bfs_directed"]["unreachable"] == ["C"]
    assert g["bfs_undirected"]["unreachable"] == []
    assert g["strongly_connected"] is False


def test_disconnected_and_isolated():
    g = analyse_graph(N, names, [("A", "B")], "A")
    assert g["weakly_connected"] is False
    assert sorted(map(sorted, g["weak_components"])) == [["A", "B"], ["C"], ["D"]]
    assert g["isolated_junctions"] == ["C", "D"]


def test_cycle_strongly_connected():
    g = analyse_graph(["A", "B", "C"], {k: k for k in "ABC"}, [("A", "B"), ("B", "C"), ("C", "A")], "B")
    assert g["strongly_connected"] and g["bfs_directed"]["order"] == ["B", "C", "A"]
