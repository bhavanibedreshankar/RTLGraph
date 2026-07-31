"""Parses a Verilator AST JSON tree dump (design.tree.json + design.meta.json)
into the canonical RTLGraph object model (src/models/design.py).

Nothing in this module hardcodes a signal, module, or instance name from any
particular design -- everything is driven by walking whatever MODULE/CELL/
VAR/ALWAYS/ASSIGN* nodes actually appear in the supplied tree, so it works on
any Verilator-elaborated design, not just the bundled tpe_top sample.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

from models.design import (
    AlwaysBlock,
    Assignment,
    ClockDomain,
    Design,
    Expression,
    Instance,
    Module,
    Parameter,
    PinConnection,
    Port,
    Register,
    ResetDomain,
    SensitivityItem,
    Signal,
    SourceLoc,
)
from parser.ast_index import AstIndex, load_ast_index
from parser.expr_render import collect_varrefs, render_expr

_STMT_CONTAINER_FIELDS = ("stmtsp", "itemsp", "thensp", "elsesp", "declsp", "contsp")

_id_counter = itertools.count()


def _next_id(prefix: str) -> str:
    return f"{prefix}_{next(_id_counter)}"


class _ModuleCtx:
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.expressions: list[Expression] = []
        # VAR node addr -> fully scope-qualified name. Populated as VARs are
        # visited so later VARREFs (which point back at a VAR via `varp`) can
        # resolve to the correct, disambiguated name even when a generate-for
        # loop has been unrolled into sibling GENBLOCKs that reuse the same
        # local variable name in every iteration.
        self.addr_to_qualified: dict[str, str] = {}


def _qualify(scope_prefix: str, name: str) -> str:
    return f"{scope_prefix}.{name}" if scope_prefix else name


class VerilatorParser:
    def __init__(self, index: AstIndex):
        self.index = index

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    def parse(self) -> Design:
        design = Design()
        for filename, letter in self._iter_files():
            design.source_files[letter] = filename

        modules_raw = self.index.tree.get("modulesp", [])
        for mod_node in modules_raw:
            if mod_node.get("type") != "MODULE":
                continue
            module = self._parse_module(mod_node)
            design.modules[module.name] = module

        top = self._find_top(modules_raw)
        if top:
            design.top_module = top
            if top in design.modules:
                design.modules[top].is_top = True

        self._assign_clock_reset(design)
        for module in design.modules.values():
            self._classify_registers(module)
        self._collect_domains(design)
        return design

    def _assign_clock_reset(self, design: Design) -> None:
        """Design-wide frequency pass: the signal edge-sensitized by the most
        distinct always blocks is treated as THE clock; the next most common
        distinct signal is treated as THE (primary) reset. This avoids relying
        on sensitivity-list order or any hardcoded signal name."""
        from collections import Counter

        freq: Counter[str] = Counter()
        for module in design.modules.values():
            for always in module.always_blocks:
                for signal_name in {item.signal for item in always.sensitivity if item.edge in ("POS", "NEG", "BOTH")}:
                    freq[signal_name] += 1

        ranked = [name for name, _ in freq.most_common()]
        clock_name = ranked[0] if len(ranked) >= 1 else None
        reset_name = ranked[1] if len(ranked) >= 2 else None

        for module in design.modules.values():
            for always in module.always_blocks:
                edge_items = [i for i in always.sensitivity if i.edge in ("POS", "NEG", "BOTH")]
                for item in edge_items:
                    if item.signal == clock_name:
                        always.clock, always.clock_edge = item.signal, item.edge
                    elif item.signal == reset_name:
                        always.reset, always.reset_edge = item.signal, item.edge
                if always.clock is None and edge_items:
                    # Single-signal sensitivity block whose signal never won
                    # the global vote (e.g. a locally clocked sub-block) --
                    # fall back to treating its own most-common edge item as
                    # the clock so it's still queryable.
                    always.clock, always.clock_edge = edge_items[0].signal, edge_items[0].edge
                    for item in edge_items[1:]:
                        if item.signal != always.clock and always.reset is None:
                            always.reset, always.reset_edge = item.signal, item.edge
        return

    def _iter_files(self):
        for letter, info in self.index.files.items():
            yield info.get("filename", letter), letter

    def _find_top(self, modules_raw: list[dict[str, Any]]) -> str | None:
        instantiated: set[str] = set()
        for mod_node in modules_raw:
            for cell in self._find_all(mod_node.get("stmtsp", []), "CELL"):
                modp = self.index.resolve_field(cell, "modp")
                if modp:
                    instantiated.add(modp.get("name", ""))
        candidates = [
            m.get("name")
            for m in modules_raw
            if m.get("type") == "MODULE" and m.get("name") not in instantiated and m.get("name") != "$unit"
        ]
        if not candidates:
            return None
        # Prefer the shallowest level (closest to root of the design hierarchy).
        by_level = sorted(
            (m for m in modules_raw if m.get("name") in candidates),
            key=lambda m: m.get("level", 0),
        )
        return by_level[0]["name"] if by_level else None

    # ------------------------------------------------------------------
    # module-level parsing
    # ------------------------------------------------------------------
    def _parse_module(self, mod_node: dict[str, Any]) -> Module:
        name = mod_node["name"]
        module = Module(name=name, orig_name=mod_node.get("origName", name), level=mod_node.get("level", 0))
        ctx = _ModuleCtx(name)

        stmts = mod_node.get("stmtsp", [])
        self._walk_module_stmts(stmts, module, ctx, "")

        module.expressions = ctx.expressions
        return module

    def _walk_module_stmts(self, stmts: Any, module: Module, ctx: _ModuleCtx, scope_prefix: str) -> None:
        if isinstance(stmts, dict):
            stmts = [stmts]
        if not isinstance(stmts, list):
            return
        for node in stmts:
            if not isinstance(node, dict):
                continue
            t = node.get("type")
            if t == "VAR":
                self._parse_var(node, module, ctx, scope_prefix)
            elif t == "CELL":
                self._parse_cell(node, module, ctx, scope_prefix)
            elif t == "ALWAYS":
                self._parse_always(node, module, ctx)
            elif t in ("ASSIGNW", "ASSIGN"):
                self._parse_top_assign(node, module, ctx, kind="continuous" if t == "ASSIGNW" else "blocking")
            elif t == "INITIAL":
                # Initial blocks don't represent synthesizable hardware relationships
                # we track (no clock), but may still declare/assign vars in sim-only code.
                continue
            elif t in ("GENBLOCK", "BEGIN"):
                child_prefix = scope_prefix
                if t == "GENBLOCK":
                    genblock_name = node.get("name") or ""
                    if genblock_name:
                        child_prefix = _qualify(scope_prefix, genblock_name)
                for field in _STMT_CONTAINER_FIELDS:
                    if field in node:
                        self._walk_module_stmts(node.get(field), module, ctx, child_prefix)
            # other top-level node types (TYPEDEF, package refs, etc.) are not
            # part of the hardware graph and are intentionally ignored.

    def _loc(self, node: dict[str, Any]) -> SourceLoc:
        filename, line, col = self.index.loc_to_source(node.get("loc"))
        return SourceLoc(file=filename, line=line, col=col)

    def _width_of(self, var_node: dict[str, Any]) -> int | None:
        dtype = self.index.resolve_field(var_node, "dtypep")
        if not dtype:
            return None
        rng = dtype.get("range")
        if isinstance(rng, str) and ":" in rng:
            try:
                msb_s, lsb_s = rng.split(":")
                msb, lsb = int(msb_s), int(lsb_s)
                return abs(msb - lsb) + 1
            except ValueError:
                return None
        return 1

    def _parse_var(self, node: dict[str, Any], module: Module, ctx: _ModuleCtx, scope_prefix: str) -> None:
        name = _qualify(scope_prefix, node["name"])
        addr = node.get("addr")
        if addr:
            ctx.addr_to_qualified[addr] = name
        direction = node.get("direction", "NONE")
        is_param = bool(node.get("isParam") or node.get("isGParam"))
        loc = self._loc(node)
        dtype_name = node.get("dtypeName")
        width = self._width_of(node)

        if is_param:
            value_node = node.get("valuep")
            value_text = render_expr(value_node) if value_node else None
            module.parameters.append(
                Parameter(
                    id=f"{module.name}.{name}",
                    name=name,
                    module=module.name,
                    value_text=value_text,
                    dtype=dtype_name,
                    is_gparam=bool(node.get("isGParam")),
                    loc=loc,
                )
            )
            return

        if direction in ("INPUT", "OUTPUT", "INOUT"):
            module.ports.append(
                Port(
                    id=f"{module.name}.{name}",
                    name=name,
                    module=module.name,
                    direction=direction,
                    width=width,
                    dtype=dtype_name,
                    loc=loc,
                )
            )
            return

        # Provisionally a plain wire/signal; may be reclassified as a Register
        # once always-block analysis (below) determines it's clocked.
        module.signals.append(
            Signal(
                id=f"{module.name}.{name}",
                name=name,
                module=module.name,
                kind="wire",
                width=width,
                dtype=dtype_name,
                loc=loc,
            )
        )

    def _parse_cell(self, node: dict[str, Any], module: Module, ctx: _ModuleCtx, scope_prefix: str) -> None:
        name = _qualify(scope_prefix, node["name"])
        modp = self.index.resolve_field(node, "modp")
        module_type = modp.get("name") if modp else "?"
        pins: list[PinConnection] = []
        for pin in node.get("pinsp", []):
            if not isinstance(pin, dict):
                continue
            expr = pin.get("exprp")
            reads = collect_varrefs(expr, access="RD", addr_to_qualified=ctx.addr_to_qualified) if expr else []
            pins.append(
                PinConnection(
                    port_name=pin.get("name", ""),
                    expr_text=render_expr(expr) if expr else "",
                    reads=reads,
                )
            )
        module.instances.append(
            Instance(
                id=f"{module.name}.{name}",
                name=name,
                parent_module=module.name,
                module_type=module_type,
                pins=pins,
                loc=self._loc(node),
            )
        )

    # ------------------------------------------------------------------
    # always-block / statement-level parsing
    # ------------------------------------------------------------------
    def _parse_always(self, node: dict[str, Any], module: Module, ctx: _ModuleCtx) -> None:
        always_id = _next_id(f"{module.name}.always")
        sensitivity: list[SensitivityItem] = []
        sentree = node.get("sentreep")
        senitems = self._find_all(sentree, "SENITEM") if sentree else []
        for si in senitems:
            edge = si.get("edgeType", "NONE")
            names = collect_varrefs(si.get("sensp"), access="RD", addr_to_qualified=ctx.addr_to_qualified)
            for n in names:
                sensitivity.append(SensitivityItem(edge=edge, signal=n))

        # Clock/reset are NOT assigned here: sensitivity-list order is not a
        # reliable signal (e.g. `@(negedge rst_n or posedge clk)` is legal and
        # common), so we can't just call "first edge item" the clock. Instead
        # we defer to a design-wide frequency pass (_assign_clock_reset_domains)
        # run once every module has been parsed: the signal edge-sensitized by
        # the most always blocks design-wide is almost certainly the clock,
        # the next-most-common is almost certainly the (a) reset.
        is_seq = any(item.edge in ("POS", "NEG", "BOTH") for item in sensitivity)
        always = AlwaysBlock(
            id=always_id,
            module=module.name,
            kind="sequential" if is_seq else "combinational",
            sensitivity=sensitivity,
            loc=self._loc(node),
        )

        assignments: list[Assignment] = []
        reads: set[str] = set()
        writes: set[str] = set()
        self._walk_always_stmts(node.get("stmtsp", []), module, ctx, always, [], assignments, reads, writes)

        always.reads = sorted(reads)
        always.writes = sorted(writes)
        always.assignment_ids = [a.id for a in assignments]
        module.always_blocks.append(always)
        module.assignments.extend(assignments)

    def _walk_always_stmts(
        self,
        stmts: Any,
        module: Module,
        ctx: _ModuleCtx,
        always: AlwaysBlock,
        cond_stack: list[str],
        assignments: list[Assignment],
        block_reads: set[str],
        block_writes: set[str],
    ) -> None:
        if isinstance(stmts, dict):
            stmts = [stmts]
        if not isinstance(stmts, list):
            return
        for node in stmts:
            if not isinstance(node, dict):
                continue
            t = node.get("type")
            if t == "IF":
                cond_reads = collect_varrefs(node.get("condp"), access="RD", addr_to_qualified=ctx.addr_to_qualified)
                block_reads.update(cond_reads)
                new_stack = cond_stack + cond_reads
                self._walk_always_stmts(node.get("thensp"), module, ctx, always, new_stack, assignments, block_reads, block_writes)
                self._walk_always_stmts(node.get("elsesp"), module, ctx, always, new_stack, assignments, block_reads, block_writes)
            elif t == "CASE":
                sel_reads = collect_varrefs(node.get("exprp"), access="RD", addr_to_qualified=ctx.addr_to_qualified)
                block_reads.update(sel_reads)
                for item in node.get("itemsp", []):
                    if not isinstance(item, dict):
                        continue
                    item_reads = collect_varrefs(item.get("condsp"), access="RD", addr_to_qualified=ctx.addr_to_qualified)
                    block_reads.update(item_reads)
                    new_stack = cond_stack + sel_reads + item_reads
                    self._walk_always_stmts(item.get("stmtsp"), module, ctx, always, new_stack, assignments, block_reads, block_writes)
            elif t in ("BEGIN", "GENBLOCK"):
                for field in _STMT_CONTAINER_FIELDS:
                    if field in node:
                        self._walk_always_stmts(node.get(field), module, ctx, always, cond_stack, assignments, block_reads, block_writes)
            elif t == "LOOP":
                self._walk_always_stmts(node.get("stmtsp"), module, ctx, always, cond_stack, assignments, block_reads, block_writes)
                self._walk_always_stmts(node.get("contsp"), module, ctx, always, cond_stack, assignments, block_reads, block_writes)
            elif t in ("ASSIGN", "ASSIGNDLY", "ASSIGNW"):
                assign_kind = "nonblocking" if t == "ASSIGNDLY" else ("continuous" if t == "ASSIGNW" else "blocking")
                assignment = self._make_assignment(node, module, ctx, always.id, cond_stack, kind=assign_kind)
                assignments.append(assignment)
                block_reads.update(assignment.reads)
                block_writes.update(assignment.lhs)
            else:
                # Statements with no hardware read/write meaning for our graph
                # (DISPLAY, STOP, JUMPGO, ...) are skipped, but may still nest
                # further statement lists we should not silently drop.
                for field in _STMT_CONTAINER_FIELDS:
                    if field in node:
                        self._walk_always_stmts(node.get(field), module, ctx, always, cond_stack, assignments, block_reads, block_writes)

    def _parse_top_assign(self, node: dict[str, Any], module: Module, ctx: _ModuleCtx, kind: str) -> None:
        assignment = self._make_assignment(node, module, ctx, None, [], kind=kind)
        module.assignments.append(assignment)

    def _make_assignment(
        self,
        node: dict[str, Any],
        module: Module,
        ctx: _ModuleCtx,
        always_id: str | None,
        extra_reads: list[str],
        kind: str,
    ) -> Assignment:
        lhs_names = collect_varrefs(node.get("lhsp"), access="WR", addr_to_qualified=ctx.addr_to_qualified)
        rhs_reads = collect_varrefs(node.get("rhsp"), access="RD", addr_to_qualified=ctx.addr_to_qualified)
        lhs_index_reads = collect_varrefs(node.get("lhsp"), access="RD", addr_to_qualified=ctx.addr_to_qualified)  # e.g. arr[i] <= ...
        reads = sorted(set(rhs_reads) | set(lhs_index_reads) | set(extra_reads))

        expr_id = _next_id(f"{module.name}.expr")
        expression = Expression(
            id=expr_id,
            module=module.name,
            text=render_expr(node.get("rhsp")),
            reads=rhs_reads,
            loc=self._loc(node),
        )
        ctx.expressions.append(expression)

        return Assignment(
            id=_next_id(f"{module.name}.assign"),
            module=module.name,
            kind=kind,
            lhs=lhs_names,
            reads=reads,
            expression_id=expr_id,
            always_block_id=always_id,
            loc=self._loc(node),
        )

    # ------------------------------------------------------------------
    # post-processing
    # ------------------------------------------------------------------
    def _classify_registers(self, module: Module) -> None:
        """Promote any Signal that is nonblocking-assigned inside a
        sequential always block to a Register."""
        reg_drivers: dict[str, AlwaysBlock] = {}
        assignments_by_id = {a.id: a for a in module.assignments}
        for always in module.always_blocks:
            if always.kind != "sequential":
                continue
            for assignment_id in always.assignment_ids:
                assignment = assignments_by_id.get(assignment_id)
                if not assignment or assignment.kind != "nonblocking":
                    continue
                for name in assignment.lhs:
                    reg_drivers.setdefault(name, always)

        if not reg_drivers:
            return

        remaining_signals = []
        for sig in module.signals:
            always = reg_drivers.get(sig.name)
            if always is None:
                remaining_signals.append(sig)
                continue
            module.registers.append(
                Register(
                    id=sig.id,
                    name=sig.name,
                    module=sig.module,
                    width=sig.width,
                    dtype=sig.dtype,
                    clock=always.clock,
                    clock_edge=always.clock_edge,
                    reset=always.reset,
                    reset_edge=always.reset_edge,
                    loc=sig.loc,
                )
            )
        module.signals = remaining_signals

    def _collect_domains(self, design: Design) -> None:
        for module in design.modules.values():
            for always in module.always_blocks:
                if always.clock:
                    cid = f"clk:{always.clock}"
                    design.clock_domains.setdefault(cid, ClockDomain(id=cid, name=always.clock))
                if always.reset:
                    rid = f"rst:{always.reset}:{always.reset_edge}"
                    design.reset_domains.setdefault(
                        rid, ResetDomain(id=rid, name=always.reset, edge=always.reset_edge or "NONE")
                    )

    # ------------------------------------------------------------------
    def _find_all(self, node: Any, target_type: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if cur.get("type") == target_type:
                    found.append(cur)
                for v in cur.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                for item in cur:
                    stack.append(item)
        return found


def parse_design(tree_path: str | Path, meta_path: str | Path) -> Design:
    index = load_ast_index(tree_path, meta_path)
    return VerilatorParser(index).parse()
