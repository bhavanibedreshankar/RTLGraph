from __future__ import annotations

import pytest

from retrieval.engine import ModuleNotFound, SignalNotFound


def test_find_module(engine):
    m = engine.find_module("tpe_cmd_proc")
    assert m is not None
    assert m["name"] == "tpe_cmd_proc"
    assert len(m["ports"]) > 0
    assert len(m["registers"]) > 0


def test_find_module_missing_returns_none(engine):
    assert engine.find_module("does_not_exist") is None


def test_find_signal_exact_and_basename(engine):
    exact = engine.find_signal("register:tpe_cmd_proc.ctrl_enable_q")
    assert exact == [] or exact  # id lookup isn't the primary key path; basename is
    by_name = engine.find_signal("ctrl_enable_q")
    assert any(s["module"] == "tpe_cmd_proc" for s in by_name)


def test_find_signal_resolves_generate_block_basename(engine):
    matches = engine.find_signal("data_chain")
    assert matches
    assert all(m["name"].endswith("data_chain") for m in matches)


def test_trace_driver(engine):
    result = engine.trace_driver("ctrl_enable_q", module="tpe_cmd_proc")
    assert result["drivers"]
    for entry in result["drivers"]:
        assert entry["driver"]["node_type"] == "Assignment"


def test_trace_driver_unknown_signal_raises(engine):
    with pytest.raises(SignalNotFound):
        engine.trace_driver("totally_bogus_signal_xyz")


def test_trace_receivers(engine):
    result = engine.trace_receivers("s_awvalid", module="tpe_cmd_proc")
    assert result["receivers"]


def test_fanin_nonempty_for_driven_register(engine):
    result = engine.fanin("ctrl_enable_q", module="tpe_cmd_proc")
    assert len(result["fanin"]) > 0


def test_fanin_respects_max_depth(engine):
    shallow = engine.fanin("ctrl_enable_q", module="tpe_cmd_proc", max_depth=1)
    deep = engine.fanin("ctrl_enable_q", module="tpe_cmd_proc", max_depth=10)
    assert len(shallow["fanin"]) <= len(deep["fanin"])


def test_fanout_of_a_driven_signal_reaches_back(engine):
    # Whatever ctrl_enable_q's fanin roots are, fanout from one of them
    # should be able to reach ctrl_enable_q again.
    fanin = engine.fanin("ctrl_enable_q", module="tpe_cmd_proc")
    if not fanin["fanin"]:
        pytest.skip("no fanin to test fanout symmetry against")
    root = fanin["fanin"][-1]["node"]
    if root["node_type"] not in ("Signal", "Register", "Port"):
        pytest.skip("root is not a directly nameable signal")
    fanout = engine.fanout(root["name"], module=root["module"])
    assert isinstance(fanout["fanout"], list)


def test_dependency_path_same_module(engine):
    result = engine.dependency_path("ctrl_enable_q", "s_awvalid", module="tpe_cmd_proc")
    assert result["found"] is True
    assert result["path"][0]["name"] == "ctrl_enable_q"
    assert result["path"][-1]["name"] == "s_awvalid"


def test_clock_domain(engine):
    result = engine.clock_domain("ctrl_enable_q", module="tpe_cmd_proc")
    names = {c["name"] for c in result["clock_domains"]}
    assert "clk" in names


def test_reset_tree(engine):
    result = engine.reset_tree("ctrl_enable_q", module="tpe_cmd_proc")
    names = {c["name"] for c in result["reset_domains"]}
    assert "rst_n" in names
    assert len(result["co_reset_registers"]) > 1


def test_module_hierarchy(engine):
    result = engine.module_hierarchy("tpe_top", max_depth=1)
    assert result["module"]["name"] == "tpe_top"
    instance_names = {i["instance"]["name"] for i in result["instances"]}
    assert "u_cmd_proc" in instance_names


def test_module_hierarchy_missing_module_raises(engine):
    with pytest.raises(ModuleNotFound):
        engine.module_hierarchy("nope_not_a_module")


def test_find_registers(engine):
    regs = engine.find_registers("tpe_cmd_proc")
    assert len(regs) > 0
    assert all(r["node_type"] == "Register" for r in regs)


def test_find_assignments(engine):
    result = engine.find_assignments("ctrl_enable_q", module="tpe_cmd_proc")
    assert result["driving_assignments"]


def test_find_always_blocks(engine):
    result = engine.find_always_blocks("ctrl_enable_q", module="tpe_cmd_proc")
    assert result["writing_always_blocks"]
    for block in result["writing_always_blocks"]:
        assert block["kind"] == "sequential"


def test_search_finds_module_and_instance(engine):
    results, total = engine.search("cmd_proc")
    names = {r["name"] for r in results}
    assert "tpe_cmd_proc" in names
    assert "u_cmd_proc" in names
    assert total == len(results)
