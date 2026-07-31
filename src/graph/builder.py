"""Builds a directed semantic graph (networkx.MultiDiGraph) from the canonical
RTLGraph Design model produced by the parser layer.

Node id scheme (stable, human-readable, used as the graph's node key):
    module:<module>
    instance:<parent_module>.<instance>
    port:<module>.<name>
    signal:<module>.<name>
    register:<module>.<name>
    parameter:<module>.<name>
    always:<always_block_id>
    assignment:<assignment_id>
    expression:<expression_id>
    clockdomain:<clock_name>
    resetdomain:<reset_name>:<edge>

Every node carries a `node_type` attribute (one of Module/Instance/Signal/
Register/Port/Parameter/Expression/Assignment/AlwaysBlock/ClockDomain/
ResetDomain) plus the flattened fields of its source Pydantic model, so the
retrieval layer never needs to reach back into the parser's objects.

Edge types (the `rel` attribute on each edge):
    INSTANCE_OF, CONTAINS, DRIVES, READS, WRITES, CONNECTED_TO,
    CLOCKED_BY, RESET_BY, DEPENDS_ON

FANIN/FANOUT are intentionally *not* materialized as edges: they are the
transitive closure of DEPENDS_ON and are computed on demand by the retrieval
engine's traversal (materializing them would mean an edge per reachable pair,
which is both redundant with DEPENDS_ON and quadratic in graph size).
"""

from __future__ import annotations

import networkx as nx

from models.design import Design, Module


def module_id(name: str) -> str:
    return f"module:{name}"


def instance_id(parent_module: str, name: str) -> str:
    return f"instance:{parent_module}.{name}"


def port_id(module: str, name: str) -> str:
    return f"port:{module}.{name}"


def signal_id(module: str, name: str) -> str:
    return f"signal:{module}.{name}"


def register_id(module: str, name: str) -> str:
    return f"register:{module}.{name}"


def parameter_id(module: str, name: str) -> str:
    return f"parameter:{module}.{name}"


def always_id(always_block_id: str) -> str:
    return f"always:{always_block_id}"


def assignment_node_id(assignment_id: str) -> str:
    return f"assignment:{assignment_id}"


def expression_node_id(expression_id: str) -> str:
    return f"expression:{expression_id}"


def clockdomain_id(name: str) -> str:
    return f"clockdomain:{name}"


def resetdomain_id(name: str, edge: str) -> str:
    return f"resetdomain:{name}:{edge}"


class GraphBuilder:
    def __init__(self, design: Design):
        self.design = design
        self.graph = nx.MultiDiGraph()
        # module -> {signal name -> node_id} across ports/signals/registers,
        # used to resolve DRIVES/READS/CONNECTED_TO targets by name.
        self._module_signal_index: dict[str, dict[str, str]] = {}

    def build(self) -> nx.MultiDiGraph:
        for module in self.design.modules.values():
            self._add_module_node(module)
        for name, cd in self.design.clock_domains.items():
            self.graph.add_node(clockdomain_id(cd.name), node_type="ClockDomain", **cd.model_dump())
        for name, rd in self.design.reset_domains.items():
            self.graph.add_node(resetdomain_id(rd.name, rd.edge), node_type="ResetDomain", **rd.model_dump())

        for module in self.design.modules.values():
            self._index_module_signals(module)

        for module in self.design.modules.values():
            self._add_ports_signals_registers_params(module)
        for module in self.design.modules.values():
            self._add_instances(module)
        for module in self.design.modules.values():
            self._add_always_and_assignments(module)

        return self.graph

    # ------------------------------------------------------------------
    def _add_module_node(self, module: Module) -> None:
        self.graph.add_node(
            module_id(module.name),
            node_type="Module",
            name=module.name,
            orig_name=module.orig_name,
            level=module.level,
            is_top=module.is_top,
        )

    def _index_module_signals(self, module: Module) -> None:
        idx: dict[str, str] = {}
        for p in module.ports:
            idx[p.name] = port_id(module.name, p.name)
        for s in module.signals:
            idx[s.name] = signal_id(module.name, s.name)
        for r in module.registers:
            idx[r.name] = register_id(module.name, r.name)
        for prm in module.parameters:
            idx.setdefault(prm.name, parameter_id(module.name, prm.name))
        self._module_signal_index[module.name] = idx

    def _resolve(self, module: str, name: str) -> str | None:
        return self._module_signal_index.get(module, {}).get(name)

    # ------------------------------------------------------------------
    def _add_ports_signals_registers_params(self, module: Module) -> None:
        mid = module_id(module.name)
        for p in module.ports:
            nid = port_id(module.name, p.name)
            self.graph.add_node(nid, node_type="Port", **p.model_dump(exclude={"loc"}), loc=str(p.loc) if p.loc else None)
            self.graph.add_edge(mid, nid, rel="CONTAINS")
        for s in module.signals:
            nid = signal_id(module.name, s.name)
            self.graph.add_node(nid, node_type="Signal", **s.model_dump(exclude={"loc"}), loc=str(s.loc) if s.loc else None)
            self.graph.add_edge(mid, nid, rel="CONTAINS")
        for r in module.registers:
            nid = register_id(module.name, r.name)
            self.graph.add_node(nid, node_type="Register", **r.model_dump(exclude={"loc"}), loc=str(r.loc) if r.loc else None)
            self.graph.add_edge(mid, nid, rel="CONTAINS")
            if r.clock:
                cid = clockdomain_id(r.clock)
                if self.graph.has_node(cid):
                    self.graph.add_edge(nid, cid, rel="CLOCKED_BY")
            if r.reset:
                rid = resetdomain_id(r.reset, r.reset_edge or "NONE")
                if self.graph.has_node(rid):
                    self.graph.add_edge(nid, rid, rel="RESET_BY")
        for prm in module.parameters:
            nid = parameter_id(module.name, prm.name)
            self.graph.add_node(nid, node_type="Parameter", **prm.model_dump(exclude={"loc"}), loc=str(prm.loc) if prm.loc else None)
            self.graph.add_edge(mid, nid, rel="CONTAINS")

    def _add_instances(self, module: Module) -> None:
        mid = module_id(module.name)
        for inst in module.instances:
            nid = instance_id(module.name, inst.name)
            self.graph.add_node(
                nid,
                node_type="Instance",
                id=inst.id,
                name=inst.name,
                parent_module=inst.parent_module,
                module_type=inst.module_type,
                loc=str(inst.loc) if inst.loc else None,
            )
            self.graph.add_edge(mid, nid, rel="CONTAINS")
            child_mid = module_id(inst.module_type)
            if self.graph.has_node(child_mid):
                self.graph.add_edge(nid, child_mid, rel="INSTANCE_OF")

            child_ports = {p.name: p for p in self.design.modules[inst.module_type].ports} if inst.module_type in self.design.modules else {}
            for pin in inst.pins:
                child_port = child_ports.get(pin.port_name)
                child_port_nid = port_id(inst.module_type, pin.port_name) if child_port else None
                for parent_signal_name in pin.reads:
                    parent_nid = self._resolve(module.name, parent_signal_name)
                    if not parent_nid:
                        continue
                    if child_port_nid and self.graph.has_node(child_port_nid):
                        self.graph.add_edge(parent_nid, child_port_nid, rel="CONNECTED_TO", via_pin=pin.port_name)
                        if child_port and child_port.direction == "INPUT":
                            self.graph.add_edge(parent_nid, child_port_nid, rel="DRIVES", via_pin=pin.port_name)
                        elif child_port and child_port.direction in ("OUTPUT", "INOUT"):
                            self.graph.add_edge(child_port_nid, parent_nid, rel="DRIVES", via_pin=pin.port_name)
                    else:
                        # Unresolvable child port (e.g. black-boxed/unparsed
                        # submodule) -- still record the connection at the
                        # instance boundary so the topology stays queryable.
                        self.graph.add_edge(parent_nid, nid, rel="CONNECTED_TO", via_pin=pin.port_name)

    def _add_always_and_assignments(self, module: Module) -> None:
        mid = module_id(module.name)
        expr_by_id = {e.id: e for e in module.expressions}

        for always in module.always_blocks:
            aid = always_id(always.id)
            self.graph.add_node(
                aid,
                node_type="AlwaysBlock",
                id=always.id,
                module=always.module,
                kind=always.kind,
                clock=always.clock,
                clock_edge=always.clock_edge,
                reset=always.reset,
                reset_edge=always.reset_edge,
                reads=list(always.reads),
                writes=list(always.writes),
                loc=str(always.loc) if always.loc else None,
            )
            self.graph.add_edge(mid, aid, rel="CONTAINS")

            if always.clock:
                cid = clockdomain_id(always.clock)
                if self.graph.has_node(cid):
                    self.graph.add_edge(aid, cid, rel="CLOCKED_BY")
            if always.reset:
                rid = resetdomain_id(always.reset, always.reset_edge or "NONE")
                if self.graph.has_node(rid):
                    self.graph.add_edge(aid, rid, rel="RESET_BY")

            for write_name in always.writes:
                target = self._resolve(module.name, write_name)
                if target:
                    self.graph.add_edge(aid, target, rel="WRITES")

        for assignment in module.assignments:
            asn_id = assignment_node_id(assignment.id)
            self.graph.add_node(
                asn_id,
                node_type="Assignment",
                id=assignment.id,
                module=assignment.module,
                kind=assignment.kind,
                lhs=list(assignment.lhs),
                reads=list(assignment.reads),
                loc=str(assignment.loc) if assignment.loc else None,
            )
            if assignment.always_block_id:
                self.graph.add_edge(always_id(assignment.always_block_id), asn_id, rel="CONTAINS")
            else:
                self.graph.add_edge(mid, asn_id, rel="CONTAINS")

            if assignment.expression_id and assignment.expression_id in expr_by_id:
                expr = expr_by_id[assignment.expression_id]
                exp_nid = expression_node_id(expr.id)
                self.graph.add_node(
                    exp_nid,
                    node_type="Expression",
                    id=expr.id,
                    module=expr.module,
                    text=expr.text,
                    reads=list(expr.reads),
                    loc=str(expr.loc) if expr.loc else None,
                )
                self.graph.add_edge(asn_id, exp_nid, rel="DEPENDS_ON")
                for read_name in expr.reads:
                    read_nid = self._resolve(module.name, read_name)
                    if read_nid:
                        self.graph.add_edge(exp_nid, read_nid, rel="READS")

            lhs_nids = []
            for lhs_name in assignment.lhs:
                lhs_nid = self._resolve(module.name, lhs_name)
                if lhs_nid:
                    lhs_nids.append(lhs_nid)
                    self.graph.add_edge(asn_id, lhs_nid, rel="DRIVES")

            read_nids = []
            for read_name in assignment.reads:
                read_nid = self._resolve(module.name, read_name)
                if read_nid:
                    read_nids.append(read_nid)
                    self.graph.add_edge(asn_id, read_nid, rel="READS")

            # Signal-level derived dependency edges: lets the retrieval layer
            # do fanin/fanout/dependency_path traversal directly over
            # Signal/Register/Port nodes without hopping through Assignment
            # nodes for the common case.
            for lhs_nid in lhs_nids:
                for read_nid in read_nids:
                    if lhs_nid != read_nid:
                        self.graph.add_edge(lhs_nid, read_nid, rel="DEPENDS_ON", via_assignment=assignment.id)


def build_graph(design: Design) -> nx.MultiDiGraph:
    return GraphBuilder(design).build()
