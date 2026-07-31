"""Ties parser -> graph builder -> sqlite storage together with caching."""

from __future__ import annotations

import time
from pathlib import Path

import networkx as nx

from graph.builder import build_graph
from parser.verilator_parser import parse_design
from storage.sqlite_store import load_graph, save_graph


def load_or_build_graph(
    tree_path: str | Path,
    meta_path: str | Path,
    db_path: str | Path,
    force_rebuild: bool = False,
) -> nx.MultiDiGraph:
    db_path = Path(db_path)
    tree_path = Path(tree_path)

    if not force_rebuild and db_path.exists() and db_path.stat().st_mtime >= tree_path.stat().st_mtime:
        return load_graph(db_path)

    design = parse_design(tree_path, meta_path)
    graph = build_graph(design)
    save_graph(
        graph,
        db_path,
        meta={
            "top_module": design.top_module or "",
            "source_tree": str(tree_path),
            "built_at": str(time.time()),
            "num_modules": str(len(design.modules)),
        },
    )
    return graph
