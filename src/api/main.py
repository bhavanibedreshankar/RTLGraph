"""RTLGraph REST API.

Thin FastAPI wrapper around the retrieval engine (src/retrieval/engine.py).
This layer does no graph traversal itself -- it validates input, calls the
retrieval engine, and serializes the result. The retrieval engine has zero
dependency on FastAPI, so it can be embedded directly into an AI agent's
toolset without going through HTTP at all.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from retrieval.engine import ModuleNotFound, RetrievalEngine, SignalNotFound
from storage.pipeline import load_or_build_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLE_DIR = REPO_ROOT / "data" / "sample"
DEFAULT_TREE = os.environ.get("RTLGRAPH_TREE", str(_SAMPLE_DIR / "design.tree.json"))
DEFAULT_META = os.environ.get("RTLGRAPH_META", str(_SAMPLE_DIR / "design.meta.json"))

# Vercel's function filesystem is read-only except /tmp; VERCEL=1 is set
# automatically in that runtime. Locally, cache next to the repo as before.
_DEFAULT_DB_PATH = "/tmp/rtlgraph.db" if os.environ.get("VERCEL") else str(REPO_ROOT / "data" / "rtlgraph.db")
DEFAULT_DB = os.environ.get("RTLGRAPH_DB", _DEFAULT_DB_PATH)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    get_engine()
    yield


app = FastAPI(
    title="RTLGraph",
    description="Semantic retrieval engine for RTL designs elaborated by Verilator.",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine: RetrievalEngine | None = None
# Guards first-build of the engine/SQLite cache. Vercel's Python runtime can
# dispatch concurrent requests to a single cold instance's process (and this
# app is mounted as a sub-app under api/index.py, whose ASGI lifespan isn't
# guaranteed to run before the first request reaches it) -- without this
# lock, two concurrent requests could both see `_engine is None` and race to
# write /tmp/rtlgraph.db at the same time, corrupting it and 500ing.
_engine_lock = threading.Lock()


def get_engine() -> RetrievalEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                graph = load_or_build_graph(DEFAULT_TREE, DEFAULT_META, DEFAULT_DB)
                _engine = RetrievalEngine(graph)
    return _engine


def _wrap_not_found(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except (SignalNotFound, ModuleNotFound) as e:
        raise HTTPException(status_code=404, detail=str(e))


# ----------------------------------------------------------------------
# Health / stats
# ----------------------------------------------------------------------
@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "RTLGraph API",
        "note": "This is the JSON backend, not the UI. Open the React app (default http://localhost:5173) instead.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    engine = get_engine()
    g = engine.graph
    return {"status": "ok", "nodes": g.number_of_nodes(), "edges": g.number_of_edges()}


@app.get("/stats")
def stats() -> dict[str, Any]:
    engine = get_engine()
    g = engine.graph
    from collections import Counter

    node_types = Counter(d.get("node_type") for _, d in g.nodes(data=True))
    edge_types = Counter(d.get("rel") for _, _, d in g.edges(data=True))
    return {"node_counts": dict(node_types), "edge_counts": dict(edge_types)}


# ----------------------------------------------------------------------
# /search
# ----------------------------------------------------------------------
@app.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = 25) -> dict[str, Any]:
    engine = get_engine()
    results, total = engine.search(q, limit=limit)
    return {"query": q, "results": results, "total": total}


# ----------------------------------------------------------------------
# /module
# ----------------------------------------------------------------------
@app.get("/module")
def get_module(name: str) -> dict[str, Any]:
    engine = get_engine()
    result = engine.find_module(name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No module named '{name}'")
    return result


@app.get("/module/hierarchy")
def module_hierarchy(name: str, max_depth: int | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.module_hierarchy, name, max_depth=max_depth)


@app.get("/module/registers")
def module_registers(name: str) -> dict[str, Any]:
    engine = get_engine()
    regs = _wrap_not_found(engine.find_registers, name)
    return {"module": name, "registers": regs}


@app.get("/module/list")
def list_modules() -> dict[str, Any]:
    engine = get_engine()
    modules = [
        {"id": node_id, **d}
        for node_id, d in engine.graph.nodes(data=True)
        if d.get("node_type") == "Module"
    ]
    modules.sort(key=lambda m: m.get("name", ""))
    return {"modules": modules}


# ----------------------------------------------------------------------
# /signal
# ----------------------------------------------------------------------
@app.get("/signal")
def get_signal(name: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    matches = engine.find_signal(name, module=module)
    if not matches:
        raise HTTPException(status_code=404, detail=f"No signal/register/port found matching '{name}'")
    return {"matches": matches}


@app.get("/signal/assignments")
def signal_assignments(name: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.find_assignments, name, module=module)


@app.get("/signal/always-blocks")
def signal_always_blocks(name: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.find_always_blocks, name, module=module)


@app.get("/signal/clock-domain")
def signal_clock_domain(name: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.clock_domain, name, module=module)


@app.get("/signal/reset-tree")
def signal_reset_tree(name: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.reset_tree, name, module=module)


# ----------------------------------------------------------------------
# /driver, /receivers
# ----------------------------------------------------------------------
@app.get("/driver")
def driver(signal: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.trace_driver, signal, module=module)


@app.get("/receivers")
def receivers(signal: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.trace_receivers, signal, module=module)


# ----------------------------------------------------------------------
# /fanin, /fanout
# ----------------------------------------------------------------------
@app.get("/fanin")
def fanin(signal: str, module: str | None = None, max_depth: int | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.fanin, signal, module=module, max_depth=max_depth)


@app.get("/fanout")
def fanout(signal: str, module: str | None = None, max_depth: int | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.fanout, signal, module=module, max_depth=max_depth)


# ----------------------------------------------------------------------
# /path
# ----------------------------------------------------------------------
@app.get("/path")
def path(source: str, destination: str, module: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    return _wrap_not_found(engine.dependency_path, source, destination, module=module)
