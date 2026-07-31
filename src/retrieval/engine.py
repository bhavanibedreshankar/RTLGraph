"""RTLGraph retrieval engine.

Pure graph-traversal retrieval over the semantic graph built by
src/graph/builder.py. No embeddings, no vector search, no LLM calls -- every
API here is implemented with plain NetworkX/BFS/DFS over typed nodes and
edges, so it can run standalone and be composed into an AI agent's toolset
without depending on any language model.

All public methods return plain JSON-serializable dicts/lists so the FastAPI
layer (src/api) can pass results straight through.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import networkx as nx

_DATA_NODE_TYPES = ("Signal", "Register", "Port")


def _node(graph: nx.MultiDiGraph, node_id: str) -> dict[str, Any]:
    attrs = dict(graph.nodes[node_id])
    attrs["id"] = node_id
    return attrs


class SignalNotFound(Exception):
    pass


class ModuleNotFound(Exception):
    pass


class RetrievalEngine:
    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        self._name_index: dict[str, list[str]] = {}
        self._basename_index: dict[str, list[str]] = {}
        self._module_index: dict[str, str] = {}
        self._build_indices()

    def _build_indices(self) -> None:
        for node_id, attrs in self.graph.nodes(data=True):
            node_type = attrs.get("node_type")
            if node_type == "Module":
                self._module_index[attrs.get("name", "")] = node_id
            if node_type in _DATA_NODE_TYPES or node_type in ("Instance", "Parameter"):
                name = attrs.get("name")
                if not name:
                    continue
                self._name_index.setdefault(name, []).append(node_id)
                basename = name.rsplit(".", 1)[-1]
                if basename != name:
                    self._basename_index.setdefault(basename, []).append(node_id)

    # ------------------------------------------------------------------
    # find_signal / find_module
    # ------------------------------------------------------------------
    def find_signal(self, name: str, module: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Find Signal/Register/Port nodes by exact name, exact scope-qualified
        name, or (fallback) case-insensitive substring match on name/basename."""
        candidates: list[str] = []
        candidates.extend(self._name_index.get(name, []))
        candidates.extend(self._basename_index.get(name, []))

        if not candidates:
            needle = name.lower()
            for node_id, attrs in self.graph.nodes(data=True):
                if attrs.get("node_type") not in _DATA_NODE_TYPES:
                    continue
                if needle in (attrs.get("name") or "").lower():
                    candidates.append(node_id)

        if module:
            candidates = [c for c in candidates if self.graph.nodes[c].get("module") == module]

        seen: set[str] = set()
        results = []
        for node_id in candidates:
            if node_id in seen:
                continue
            seen.add(node_id)
            results.append(_node(self.graph, node_id))
            if len(results) >= limit:
                break
        return results

    def find_module(self, name: str) -> dict[str, Any] | None:
        node_id = self._module_index.get(name)
        if not node_id:
            return None
        result = _node(self.graph, node_id)
        result["ports"] = self._children_by_type(node_id, "Port")
        result["signals"] = self._children_by_type(node_id, "Signal")
        result["registers"] = self._children_by_type(node_id, "Register")
        result["parameters"] = self._children_by_type(node_id, "Parameter")
        result["instances"] = self._children_by_type(node_id, "Instance")
        result["always_blocks"] = self._children_by_type(node_id, "AlwaysBlock")
        return result

    def _children_by_type(self, module_node_id: str, node_type: str) -> list[dict[str, Any]]:
        out = []
        for _, dst, data in self.graph.out_edges(module_node_id, data=True):
            if data.get("rel") == "CONTAINS" and self.graph.nodes[dst].get("node_type") == node_type:
                out.append(_node(self.graph, dst))
        return out

    def search(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        """Free-text search across module/instance/signal/register/port names
        for the REST /search endpoint. Still pure string/graph matching --
        no embeddings."""
        needle = query.lower()
        results: list[dict[str, Any]] = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("node_type") not in (*_DATA_NODE_TYPES, "Module", "Instance"):
                continue
            name = attrs.get("name") or ""
            if needle in name.lower():
                score = 0 if name.lower() == needle else (1 if name.lower().endswith(needle) else 2)
                results.append((score, _node(self.graph, node_id)))
        results.sort(key=lambda pair: (pair[0], len(pair[1].get("name", ""))))
        return [r for _, r in results[:limit]]

    # ------------------------------------------------------------------
    # driver / receiver tracing
    # ------------------------------------------------------------------
    def _resolve_one(self, signal: str, module: str | None = None) -> str:
        matches = self.find_signal(signal, module=module, limit=5)
        if not matches:
            raise SignalNotFound(f"No signal/register/port found matching '{signal}'")
        return matches[0]["id"]

    def trace_driver(self, signal: str, module: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        drivers = []
        for src, _, data in self.graph.in_edges(node_id, data=True):
            if data.get("rel") != "DRIVES":
                continue
            driver_node = _node(self.graph, src)
            entry: dict[str, Any] = {"driver": driver_node}
            if driver_node.get("node_type") == "Assignment":
                always_id = self._owning_always(src)
                entry["always_block"] = _node(self.graph, always_id) if always_id else None
            entry["via_pin"] = data.get("via_pin")
            drivers.append(entry)
        return {"signal": _node(self.graph, node_id), "drivers": drivers}

    def trace_receivers(self, signal: str, module: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        receivers = []
        for src, _, data in self.graph.in_edges(node_id, data=True):
            if data.get("rel") != "READS":
                continue
            reader_node = _node(self.graph, src)
            entry: dict[str, Any] = {"reader": reader_node}
            if reader_node.get("node_type") == "Assignment":
                always_id = self._owning_always(src)
                entry["always_block"] = _node(self.graph, always_id) if always_id else None
            receivers.append(entry)
        for _, dst, data in self.graph.out_edges(node_id, data=True):
            if data.get("rel") == "DRIVES" and self.graph.nodes[dst].get("node_type") == "Port":
                receivers.append({"reader": _node(self.graph, dst), "via_pin": data.get("via_pin"), "kind": "instance_port"})
        return {"signal": _node(self.graph, node_id), "receivers": receivers}

    def _owning_always(self, assignment_node_id: str) -> str | None:
        for src, _, data in self.graph.in_edges(assignment_node_id, data=True):
            if data.get("rel") == "CONTAINS" and self.graph.nodes[src].get("node_type") == "AlwaysBlock":
                return src
        return None

    # ------------------------------------------------------------------
    # fanin / fanout / dependency_path
    # ------------------------------------------------------------------
    def fanin(self, signal: str, module: str | None = None, max_depth: int | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        levels = self._bfs_depends_on(node_id, forward=True, max_depth=max_depth)
        return {
            "signal": _node(self.graph, node_id),
            "fanin": [{"node": _node(self.graph, n), "distance": d} for n, d in levels.items() if n != node_id],
        }

    def fanout(self, signal: str, module: str | None = None, max_depth: int | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        levels = self._bfs_depends_on(node_id, forward=False, max_depth=max_depth)
        return {
            "signal": _node(self.graph, node_id),
            "fanout": [{"node": _node(self.graph, n), "distance": d} for n, d in levels.items() if n != node_id],
        }

    def _bfs_depends_on(self, start: str, forward: bool, max_depth: int | None) -> dict[str, int]:
        """forward=True walks DEPENDS_ON out-edges (driven -> source, i.e.
        fanin); forward=False walks in-edges (fanout: who depends on me)."""
        visited: dict[str, int] = {start: 0}
        queue: deque[str] = deque([start])
        while queue:
            cur = queue.popleft()
            dist = visited[cur]
            if max_depth is not None and dist >= max_depth:
                continue
            edges = self.graph.out_edges(cur, data=True) if forward else self.graph.in_edges(cur, data=True)
            for edge in edges:
                other = edge[1] if forward else edge[0]
                data = edge[2]
                if data.get("rel") != "DEPENDS_ON":
                    continue
                if other not in visited:
                    visited[other] = dist + 1
                    queue.append(other)
        return visited

    def dependency_path(self, source: str, destination: str, module: str | None = None) -> dict[str, Any]:
        src_id = self._resolve_one(source, module)
        dst_id = self._resolve_one(destination, module)

        depends_view = nx.MultiDiGraph()
        depends_view.add_nodes_from(self.graph.nodes(data=True))
        depends_view.add_edges_from(
            (u, v, d) for u, v, d in self.graph.edges(data=True) if d.get("rel") == "DEPENDS_ON"
        )
        try:
            path = nx.shortest_path(depends_view, src_id, dst_id)
            return {
                "source": _node(self.graph, src_id),
                "destination": _node(self.graph, dst_id),
                "found": True,
                "path": [_node(self.graph, n) for n in path],
                "length": len(path) - 1,
            }
        except nx.NetworkXNoPath:
            pass

        # Fall back to the full graph (crosses instance boundaries via
        # DRIVES/CONNECTED_TO) so cross-hierarchy paths are still findable.
        try:
            path = nx.shortest_path(self.graph.to_undirected(as_view=True), src_id, dst_id)
            return {
                "source": _node(self.graph, src_id),
                "destination": _node(self.graph, dst_id),
                "found": True,
                "path": [_node(self.graph, n) for n in path],
                "length": len(path) - 1,
                "note": "No direct combinational/sequential DEPENDS_ON path; showing shortest structural path instead.",
            }
        except nx.NetworkXNoPath:
            return {
                "source": _node(self.graph, src_id),
                "destination": _node(self.graph, dst_id),
                "found": False,
                "path": [],
                "length": None,
            }

    # ------------------------------------------------------------------
    # clock / reset domains
    # ------------------------------------------------------------------
    def clock_domain(self, signal: str, module: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        attrs = self.graph.nodes[node_id]

        clock_nodes = set()
        for _, dst, data in self.graph.out_edges(node_id, data=True):
            if data.get("rel") == "CLOCKED_BY":
                clock_nodes.add(dst)

        if not clock_nodes:
            for always_id in self._writing_always_blocks(node_id, attrs.get("name")):
                for _, dst, data in self.graph.out_edges(always_id, data=True):
                    if data.get("rel") == "CLOCKED_BY":
                        clock_nodes.add(dst)

        return {
            "signal": _node(self.graph, node_id),
            "clock_domains": [_node(self.graph, c) for c in clock_nodes],
        }

    def reset_tree(self, signal: str, module: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        attrs = self.graph.nodes[node_id]

        reset_nodes = set()
        for _, dst, data in self.graph.out_edges(node_id, data=True):
            if data.get("rel") == "RESET_BY":
                reset_nodes.add(dst)
        for always_id in self._writing_always_blocks(node_id, attrs.get("name")):
            for _, dst, data in self.graph.out_edges(always_id, data=True):
                if data.get("rel") == "RESET_BY":
                    reset_nodes.add(dst)

        siblings = []
        for reset_id in reset_nodes:
            for src, _, data in self.graph.in_edges(reset_id, data=True):
                if data.get("rel") == "RESET_BY" and self.graph.nodes[src].get("node_type") == "Register":
                    siblings.append(_node(self.graph, src))

        return {
            "signal": _node(self.graph, node_id),
            "reset_domains": [_node(self.graph, r) for r in reset_nodes],
            "co_reset_registers": siblings,
        }

    def _writing_always_blocks(self, node_id: str, name: str | None) -> list[str]:
        out = []
        for src, _, data in self.graph.in_edges(node_id, data=True):
            if data.get("rel") == "WRITES" and self.graph.nodes[src].get("node_type") == "AlwaysBlock":
                out.append(src)
        return out

    # ------------------------------------------------------------------
    # hierarchy / registers / assignments / always blocks
    # ------------------------------------------------------------------
    def module_hierarchy(self, module: str, max_depth: int | None = None) -> dict[str, Any]:
        module_node_id = self._module_index.get(module)
        if not module_node_id:
            raise ModuleNotFound(f"No module named '{module}'")
        return self._hierarchy_node(module_node_id, depth=0, max_depth=max_depth, seen=set())

    def _hierarchy_node(self, module_node_id: str, depth: int, max_depth: int | None, seen: set[str]) -> dict[str, Any]:
        module_attrs = _node(self.graph, module_node_id)
        node = {"module": module_attrs, "instances": []}
        if max_depth is not None and depth >= max_depth:
            return node
        for _, dst, data in self.graph.out_edges(module_node_id, data=True):
            if data.get("rel") != "CONTAINS" or self.graph.nodes[dst].get("node_type") != "Instance":
                continue
            inst_attrs = _node(self.graph, dst)
            child_module_id = None
            for _, child_dst, child_data in self.graph.out_edges(dst, data=True):
                if child_data.get("rel") == "INSTANCE_OF":
                    child_module_id = child_dst
                    break
            entry: dict[str, Any] = {"instance": inst_attrs}
            if child_module_id and child_module_id not in seen:
                entry["child"] = self._hierarchy_node(child_module_id, depth + 1, max_depth, seen | {child_module_id})
            elif child_module_id:
                entry["child"] = {"module": _node(self.graph, child_module_id), "instances": [], "truncated": "cycle"}
            node["instances"].append(entry)
        return node

    def find_registers(self, module: str) -> list[dict[str, Any]]:
        module_node_id = self._module_index.get(module)
        if not module_node_id:
            raise ModuleNotFound(f"No module named '{module}'")
        return self._children_by_type(module_node_id, "Register")

    def find_assignments(self, signal: str, module: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        name = self.graph.nodes[node_id].get("name")
        driving, reading = [], []
        for node_id_, attrs in self.graph.nodes(data=True):
            if attrs.get("node_type") != "Assignment":
                continue
            if name in (attrs.get("lhs") or []):
                driving.append(_node(self.graph, node_id_))
            if name in (attrs.get("reads") or []):
                reading.append(_node(self.graph, node_id_))
        return {"signal": _node(self.graph, node_id), "driving_assignments": driving, "reading_assignments": reading}

    def find_always_blocks(self, signal: str, module: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_one(signal, module)
        name = self.graph.nodes[node_id].get("name")
        writing, reading = [], []
        for node_id_, attrs in self.graph.nodes(data=True):
            if attrs.get("node_type") != "AlwaysBlock":
                continue
            if name in (attrs.get("writes") or []):
                writing.append(_node(self.graph, node_id_))
            if name in (attrs.get("reads") or []):
                reading.append(_node(self.graph, node_id_))
        return {"signal": _node(self.graph, node_id), "writing_always_blocks": writing, "reading_always_blocks": reading}
