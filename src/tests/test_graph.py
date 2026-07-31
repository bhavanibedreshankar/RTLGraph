from __future__ import annotations

from graph.builder import instance_id, module_id, register_id


def test_node_types_present(graph):
    node_types = {d.get("node_type") for _, d in graph.nodes(data=True)}
    expected = {
        "Module", "Instance", "Signal", "Register", "Port", "Parameter",
        "Expression", "Assignment", "AlwaysBlock", "ClockDomain", "ResetDomain",
    }
    assert expected.issubset(node_types)


def test_edge_types_present(graph):
    edge_types = {d.get("rel") for _, _, d in graph.edges(data=True)}
    expected = {
        "INSTANCE_OF", "CONTAINS", "DRIVES", "READS", "WRITES",
        "CONNECTED_TO", "CLOCKED_BY", "RESET_BY", "DEPENDS_ON",
    }
    assert expected.issubset(edge_types)


def test_instance_of_edge(graph):
    inst = instance_id("tpe_top", "u_cmd_proc")
    assert graph.has_node(inst)
    targets = [dst for _, dst, d in graph.out_edges(inst, data=True) if d.get("rel") == "INSTANCE_OF"]
    assert module_id("tpe_cmd_proc") in targets


def test_module_contains_its_instance(graph):
    mid = module_id("tpe_top")
    dsts = [dst for _, dst, d in graph.out_edges(mid, data=True) if d.get("rel") == "CONTAINS"]
    assert instance_id("tpe_top", "u_cmd_proc") in dsts


def test_register_clocked_by_edge(graph):
    reg = register_id("tpe_cmd_proc", "ctrl_enable_q")
    assert graph.has_node(reg)
    rels = {d.get("rel") for _, _, d in graph.out_edges(reg, data=True)}
    assert "CLOCKED_BY" in rels
    assert "RESET_BY" in rels


def test_signal_level_depends_on_edges_are_signal_to_signal(graph):
    # DEPENDS_ON also appears as Assignment -> Expression (the expression it
    # evaluates); the signal-level derived edges are the ones tagged with
    # via_assignment, and those must always connect two data nodes.
    found = False
    for u, v, d in graph.edges(data=True):
        if d.get("rel") != "DEPENDS_ON" or "via_assignment" not in d:
            continue
        found = True
        assert graph.nodes[u]["node_type"] in ("Signal", "Register", "Port")
        assert graph.nodes[v]["node_type"] in ("Signal", "Register", "Port")
    assert found


def test_graph_is_nontrivial(graph):
    assert graph.number_of_nodes() > 1000
    assert graph.number_of_edges() > 5000
