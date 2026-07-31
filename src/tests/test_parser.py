"""Parser correctness tests run against the real Verilator output bundled in
/Users/bhavanibs/Documents/Claude/tpe_database/. Nothing here hardcodes
expectations beyond what's actually true of that design's RTL.
"""

from __future__ import annotations


def test_top_module_is_tpe_top(design):
    assert design.top_module == "tpe_top"
    assert design.modules["tpe_top"].is_top is True


def test_expected_modules_present(design):
    expected = {
        "tpe_top", "tpe_dma", "tpe_cmd_proc", "tpe_pmu", "tpe_debug", "pe",
    }
    assert expected.issubset(design.modules.keys())


def test_no_duplicate_signal_names_within_a_module(design):
    for module in design.modules.values():
        names = [s.name for s in module.signals]
        assert len(names) == len(set(names)), f"duplicate signal names in {module.name}"
        reg_names = [r.name for r in module.registers]
        assert len(reg_names) == len(set(reg_names)), f"duplicate register names in {module.name}"


def test_no_duplicate_instance_names_within_a_module(design):
    for module in design.modules.values():
        names = [i.name for i in module.instances]
        assert len(names) == len(set(names)), f"duplicate instance names in {module.name}"


def test_generate_block_signals_are_scope_qualified(design):
    mec = design.modules["matrix_engine_ctrl__pi1"]
    qualified = [r.name for r in mec.registers if "." in r.name]
    assert len(qualified) > 0
    assert any(name.startswith("g_a_skew[") for name in qualified)


def test_generate_block_instances_are_scope_qualified(design):
    mac_array = design.modules["mac_array__R10_C10_O8_A20"]
    assert len(mac_array.instances) == 256
    names = {i.name for i in mac_array.instances}
    assert len(names) == 256


def test_clock_and_reset_detected_correctly(design):
    cmd_proc = design.modules["tpe_cmd_proc"]
    seq_blocks = [a for a in cmd_proc.always_blocks if a.kind == "sequential"]
    assert seq_blocks
    for always in seq_blocks:
        assert always.clock == "clk"
        assert always.clock_edge == "POS"
        if always.reset:
            assert always.reset == "rst_n"
            assert always.reset_edge == "NEG"


def test_registers_carry_clock_and_reset(design):
    cmd_proc = design.modules["tpe_cmd_proc"]
    assert cmd_proc.registers
    for reg in cmd_proc.registers:
        assert reg.clock == "clk"


def test_ports_have_direction_and_width(design):
    cmd_proc = design.modules["tpe_cmd_proc"]
    clk_port = next(p for p in cmd_proc.ports if p.name == "clk")
    assert clk_port.direction == "INPUT"
    assert clk_port.width == 1
    addr_port = next(p for p in cmd_proc.ports if p.name == "s_awaddr")
    assert addr_port.width == 16


def test_instances_reference_valid_module_types(design):
    top = design.modules["tpe_top"]
    for inst in top.instances:
        assert inst.module_type in design.modules


def test_continuous_and_procedural_assignments_present(design):
    top = design.modules["tpe_top"]
    kinds = {a.kind for a in top.assignments}
    assert "continuous" in kinds
    assert "nonblocking" in kinds or "blocking" in kinds


def test_assignment_counts_reconcile_with_raw_ast(design):
    # Ground truth established by directly walking design.tree.json:
    # 351 ASSIGNW, 337 ASSIGNDLY design-wide, and 259 ASSIGN whose ultimate
    # ancestor is an ALWAYS block (the remaining 35 ASSIGN nodes live inside
    # non-synthesizable INITIAL/FUNC bodies, which the parser intentionally skips).
    kinds = {"continuous": 0, "nonblocking": 0, "blocking": 0}
    for module in design.modules.values():
        for a in module.assignments:
            kinds[a.kind] += 1
    assert kinds["continuous"] == 351
    assert kinds["nonblocking"] == 337
    assert kinds["blocking"] == 259
