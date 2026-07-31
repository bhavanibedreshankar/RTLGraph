"""Generic expression traversal over Verilator AST expression subtrees.

Nothing here knows about any particular signal name -- it just walks whatever
nested dict/list structure it is handed and (a) collects every VARREF leaf it
finds, optionally filtered by read/write access, or (b) renders the subtree
into an approximate Verilog-like text form for human/AI consumption.
"""

from __future__ import annotations

from typing import Any

_BINOP_SYMBOLS = {
    "EQ": "==", "NEQ": "!=", "LT": "<", "LTE": "<=", "LTES": "<=", "GT": ">",
    "GTS": ">", "GTE": ">=", "GTES": ">=", "ADD": "+", "SUB": "-", "MUL": "*",
    "DIV": "/", "MODDIV": "%", "AND": "&", "OR": "|", "XOR": "^",
    "LOGAND": "&&", "LOGOR": "||", "SHIFTL": "<<", "SHIFTR": ">>",
    "SHIFTRS": ">>>", "POW": "**",
}
_UNOP_SYMBOLS = {
    "NOT": "!", "LOGNOT": "!", "NEGATE": "-", "REDAND": "&", "REDOR": "|",
    "REDXOR": "^",
}


def _walk(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "VARREF":
            out.append(node)
            return
        for k, v in node.items():
            if k in ("type", "name", "addr", "loc", "dtypep"):
                continue
            _walk(v, out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, out)


def collect_varrefs(
    node: Any, access: str | None = None, addr_to_qualified: dict[str, str] | None = None
) -> list[str]:
    """Collect the (deduplicated, order-preserving) names of every VARREF
    found anywhere under `node`, optionally filtered to a given access
    ('RD' or 'WR').

    If `addr_to_qualified` is supplied, each VARREF is resolved through its
    `varp` pointer to the *declaring* VAR's fully scope-qualified name (see
    verilator_parser._qualify) instead of trusting the VARREF's own bare
    `name` field. This matters because Verilator emits unrolled generate-for
    bodies as repeated GENBLOCK copies whose local VARs all share the same
    plain name (e.g. every lane of an array has its own "data_chain") --
    without qualification those would silently collide.
    """
    found: list[dict[str, Any]] = []
    _walk(node, found)
    seen: set[str] = set()
    result: list[str] = []
    for vr in found:
        if access is not None and vr.get("access") != access:
            continue
        name = vr.get("name")
        if addr_to_qualified is not None:
            qualified = addr_to_qualified.get(vr.get("varp"))
            if qualified:
                name = qualified
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def render_expr(node: Any, depth: int = 0) -> str:
    if depth > 60:
        return "..."
    if isinstance(node, list):
        if not node:
            return ""
        if len(node) == 1:
            return render_expr(node[0], depth + 1)
        return ", ".join(render_expr(n, depth + 1) for n in node)
    if not isinstance(node, dict):
        return str(node)

    t = node.get("type")
    if t == "CONST":
        return node.get("name", "")
    if t == "VARREF":
        return node.get("name", "")
    if t == "SEL":
        base = render_expr(node.get("fromp"), depth + 1)
        lsb = render_expr(node.get("lsbp"), depth + 1)
        width = node.get("widthConst")
        if width is not None:
            return f"{base}[{lsb}+:{width}]"
        return f"{base}[{lsb}]"
    if t == "ARRAYSEL":
        base = render_expr(node.get("fromp"), depth + 1)
        idx = render_expr(node.get("bitp"), depth + 1)
        return f"{base}[{idx}]"
    if t == "COND":
        c = render_expr(node.get("condp"), depth + 1)
        a = render_expr(node.get("thenp"), depth + 1)
        b = render_expr(node.get("elsep"), depth + 1)
        return f"({c} ? {a} : {b})"
    if t == "CONCAT":
        a = render_expr(node.get("lhsp"), depth + 1)
        b = render_expr(node.get("rhsp"), depth + 1)
        return f"{{{a}, {b}}}"
    if t in _BINOP_SYMBOLS:
        a = render_expr(node.get("lhsp"), depth + 1)
        b = render_expr(node.get("rhsp"), depth + 1)
        return f"({a} {_BINOP_SYMBOLS[t]} {b})"
    if t in _UNOP_SYMBOLS:
        a = render_expr(node.get("lhsp"), depth + 1)
        return f"{_UNOP_SYMBOLS[t]}{a}"
    if t == "EXTEND":
        return render_expr(node.get("lhsp"), depth + 1)
    if t == "FUNCREF":
        args = node.get("pinsp") or node.get("argsp") or []
        return f"{node.get('name', '?')}({render_expr(args, depth + 1)})"
    if t is None:
        return ""
    # Generic fallback: render as a function-call over any nested exprs.
    parts = []
    for k, v in node.items():
        if k in ("type", "name", "addr", "loc", "dtypep") or not isinstance(v, (dict, list)):
            continue
        rendered = render_expr(v, depth + 1)
        if rendered:
            parts.append(rendered)
    inner = ", ".join(parts)
    label = node.get("name") or t
    return f"{label}({inner})" if inner else str(label)
