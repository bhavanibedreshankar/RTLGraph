"""Generic indexing / pointer-resolution utilities over a Verilator AST JSON tree.

Verilator's `--dumpi-json` (or equivalent) tree dump represents cross-references
(e.g. a VARREF pointing back at the VAR it reads, a CELL pointing at the MODULE
it instantiates) as opaque address tokens like "(ABC)". The *first* time a node
is emitted in the tree it appears as a full nested object carrying that address
in its "addr" field; every later reference to the same underlying object is just
the bare address string in a pointer-typed field (e.g. "varp", "modp").

This module builds a single addr -> node index by walking the whole tree once,
and resolves pointer fields generically using the `ptrFieldNames` list found in
design.meta.json, so nothing here is tied to a specific signal name or module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ADDR_RE = re.compile(r"^\([A-Z0-9]+\)$")


class AstIndex:
    def __init__(self, tree: dict[str, Any], ptr_field_names: set[str], files: dict[str, dict[str, Any]]):
        self.tree = tree
        self.ptr_field_names = ptr_field_names
        self.files = files
        self.by_addr: dict[str, dict[str, Any]] = {}
        self._build_index(tree)

    def _build_index(self, node: Any) -> None:
        stack: list[Any] = [node]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                addr = cur.get("addr")
                if isinstance(addr, str) and _ADDR_RE.match(addr) and addr not in self.by_addr:
                    self.by_addr[addr] = cur
                for v in cur.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                for item in cur:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

    def resolve(self, addr: Any) -> dict[str, Any] | None:
        if not isinstance(addr, str) or addr in ("UNLINKED", ""):
            return None
        return self.by_addr.get(addr)

    def resolve_field(self, node: dict[str, Any], field: str) -> dict[str, Any] | None:
        """Resolve a pointer-typed field on a node, whether it's a bare addr
        string or (as with e.g. modp on some nodes) already inlined."""
        val = node.get(field)
        if isinstance(val, str):
            return self.resolve(val)
        if isinstance(val, dict):
            return val
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val[0]
        return None

    def loc_to_source(self, loc: str | None) -> tuple[str | None, int | None, int | None]:
        """Parse a Verilator loc string like 'v,105:17,105:18' into
        (filename, line, col) using the file-letter table from design.meta.json."""
        if not loc:
            return None, None, None
        parts = loc.split(",")
        if len(parts) < 2:
            return None, None, None
        letter = parts[0]
        start = parts[1]
        line_s, _, col_s = start.partition(":")
        file_info = self.files.get(letter)
        filename = file_info["filename"] if file_info else letter
        try:
            line = int(line_s)
        except ValueError:
            line = None
        try:
            col = int(col_s)
        except ValueError:
            col = None
        return filename, line, col


def load_ast_index(tree_path: str | Path, meta_path: str | Path) -> AstIndex:
    tree_path = Path(tree_path)
    meta_path = Path(meta_path)
    with tree_path.open() as f:
        tree = json.load(f)
    ptr_field_names: set[str] = set()
    files: dict[str, dict[str, Any]] = {}
    if meta_path.exists():
        with meta_path.open() as f:
            meta = json.load(f)
        ptr_field_names = set(meta.get("ptrFieldNames", []))
        files = meta.get("files", {})
    return AstIndex(tree, ptr_field_names, files)


CONST_VALUE_RE = re.compile(r"^(-?\d+)'s?[hHdDbBoO]?([0-9a-fA-Fxz_]+)$")


def const_to_int(text: str | None) -> int | None:
    """Best-effort parse of a Verilator CONST node's `name`, e.g. "32'sh10",
    "4'h0", "1'b1", or a plain integer literal."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    m = re.match(r"^\d+'s?([hHdDbBoO])([0-9a-fA-Fxz_]+)$", text)
    if m:
        base_char, digits = m.groups()
        digits = digits.replace("_", "")
        if "x" in digits.lower() or "z" in digits.lower():
            return None
        base = {"h": 16, "d": 10, "b": 2, "o": 8}[base_char.lower()]
        try:
            return int(digits, base)
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        return None
