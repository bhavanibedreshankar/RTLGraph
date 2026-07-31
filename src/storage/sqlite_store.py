"""SQLite persistence for the RTLGraph semantic graph.

The graph is rebuilt from Verilator's JSON in well under a second even for a
multi-thousand-node design, so this layer isn't about raw parse performance --
it exists so the graph can be inspected/queried without re-parsing, shipped as
a single portable file, and reloaded by the API process on startup without
needing the original Verilator output on disk.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import networkx as nx

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    name TEXT,
    module TEXT,
    attrs TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_module ON nodes(module);

CREATE TABLE IF NOT EXISTS edges (
    edge_key INTEGER PRIMARY KEY AUTOINCREMENT,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    rel TEXT NOT NULL,
    attrs TEXT NOT NULL,
    FOREIGN KEY(src) REFERENCES nodes(id),
    FOREIGN KEY(dst) REFERENCES nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(rel);
"""


def save_graph(graph: nx.MultiDiGraph, db_path: str | Path, meta: dict[str, str] | None = None) -> None:
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        node_rows = []
        for node_id, attrs in graph.nodes(data=True):
            attrs = dict(attrs)
            node_type = attrs.pop("node_type", "Unknown")
            name = attrs.get("name")
            module = attrs.get("module")
            node_rows.append((node_id, node_type, name, module, json.dumps(attrs)))
        conn.executemany(
            "INSERT INTO nodes (id, node_type, name, module, attrs) VALUES (?, ?, ?, ?, ?)", node_rows
        )

        edge_rows = []
        for src, dst, attrs in graph.edges(data=True):
            attrs = dict(attrs)
            rel = attrs.pop("rel", "RELATED_TO")
            edge_rows.append((src, dst, rel, json.dumps(attrs)))
        conn.executemany("INSERT INTO edges (src, dst, rel, attrs) VALUES (?, ?, ?, ?)", edge_rows)

        for key, value in (meta or {}).items():
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def load_graph(db_path: str | Path) -> nx.MultiDiGraph:
    db_path = Path(db_path)
    conn = sqlite3.connect(db_path)
    graph = nx.MultiDiGraph()
    try:
        for node_id, node_type, attrs_json in conn.execute("SELECT id, node_type, attrs FROM nodes"):
            attrs = json.loads(attrs_json)
            attrs["node_type"] = node_type
            graph.add_node(node_id, **attrs)
        for src, dst, rel, attrs_json in conn.execute("SELECT src, dst, rel, attrs FROM edges"):
            attrs = json.loads(attrs_json)
            attrs["rel"] = rel
            graph.add_edge(src, dst, **attrs)
    finally:
        conn.close()
    return graph


def load_meta(db_path: str | Path) -> dict[str, str]:
    db_path = Path(db_path)
    conn = sqlite3.connect(db_path)
    try:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())
    finally:
        conn.close()
