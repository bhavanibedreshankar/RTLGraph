# RTLGraph

**Live demo: [rtlgraph.vercel.app](https://rtlgraph.vercel.app)**

A semantic retrieval engine for RTL designs. RTLGraph parses Verilator's
elaborated AST JSON output into a canonical object model, builds a typed
directed graph, persists it to SQLite, and exposes graph-traversal retrieval
APIs over REST — **no embeddings, no vector search, no LLM anywhere in the
retrieval path.** The engine is designed to be embedded directly into an AI
agent's toolset for debugging, design understanding, and failure analysis,
or browsed interactively through the bundled React + Cytoscape.js UI.

## Features

- **Generic Verilator AST parser** — walks any `design.tree.json` +
  `design.meta.json` pair into a canonical Pydantic object model (Module,
  Instance, Port, Signal, Register, Assignment, AlwaysBlock, Parameter,
  ClockDomain, ResetDomain). No signal or module names are hardcoded.
- **Correct clock/reset inference** — resolves clock and reset signals by a
  design-wide sensitivity-frequency vote rather than trusting sensitivity-list
  order (which Verilator does not guarantee, e.g. `negedge rst_n or posedge clk`
  is legal and common).
- **Generate-block scope resolution** — Verilator unrolls `generate for`
  loops into sibling blocks that reuse identical local names per lane; the
  parser resolves every reference through its AST pointer back to the
  declaring node and produces disambiguated scoped names
  (e.g. `g_rows[3].g_cols[2].u_pe`) instead of silently colliding them.
- **Typed semantic graph** (NetworkX `MultiDiGraph`) — 11 node types, 9
  relationship types (`INSTANCE_OF`, `CONTAINS`, `DRIVES`, `READS`, `WRITES`,
  `CONNECTED_TO`, `CLOCKED_BY`, `RESET_BY`, `DEPENDS_ON`).
- **SQLite-backed caching** — the graph is rebuilt once and reloaded from
  SQLite on subsequent starts unless the source AST changed.
- **Pure graph-traversal retrieval engine** — `find_signal`, `find_module`,
  `trace_driver`, `trace_receivers`, `fanin`, `fanout`, `dependency_path`,
  `clock_domain`, `reset_tree`, `module_hierarchy`, `find_registers`,
  `find_assignments`, `find_always_blocks`. Callable directly from Python
  with zero HTTP/LLM dependency, or via REST.
- **React + TypeScript + Cytoscape.js UI** — search, module browser,
  hierarchy browser, signal explorer, interactive fan-in/fan-out graphs and
  trees, and dependency-path visualization.
- **pytest suite (48 tests)** run against a real, non-trivial elaborated
  design (16 modules, 285 instances, ~3,400 graph nodes) — no mocks.

## Tech stack

- Python 3.11+, FastAPI, NetworkX, Pydantic, SQLite, pytest
- React 19, TypeScript, Vite, Cytoscape.js (`cytoscape-dagre` layout)

## Project structure

```
src/
  parser/     Verilator AST JSON -> canonical object model
  models/     Pydantic canonical types (Module, Instance, Signal, ...)
  graph/      canonical model -> networkx.MultiDiGraph
  storage/    SQLite persistence + build/load caching pipeline
  retrieval/  graph-traversal retrieval APIs (no embeddings/LLM)
  api/        FastAPI REST layer
  tests/      pytest suite run against a real Verilator sample
ui/           React + TypeScript + Cytoscape.js frontend
```

## Setup & run

**Backend**

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pytest -q

# runs against the bundled sample design (data/sample/) by default
.venv/bin/uvicorn api.main:app --app-dir src --port 8010

# or point at your own Verilator dump (design.tree.json + design.meta.json
# produced by Verilator's --dumpi-json / tree-json output)
export RTLGRAPH_TREE=/path/to/design.tree.json
export RTLGRAPH_META=/path/to/design.meta.json
.venv/bin/uvicorn api.main:app --app-dir src --port 8010
```

The first request builds the graph and caches it to `data/rtlgraph.db`;
subsequent starts reload from SQLite unless the source tree is newer.

**Frontend**

```bash
cd ui
npm install
npm run dev   # http://localhost:5173, proxies /api/* to http://localhost:8010
```

## How to use it

1. Start the backend (`uvicorn`, port 8010) and frontend (`npm run dev`,
   port 5173), then open **http://localhost:5173** — the API itself is a
   JSON backend, not a webpage.
2. Use the **search bar** or **module browser** in the sidebar to find a
   module, instance, signal, or register.
3. Selecting a module opens the **Module Browser** tab — ports, registers,
   signals, parameters, instances, and always blocks.
4. Selecting a signal opens the **Signal Explorer** tab — driver trace,
   receivers, clock domain, reset tree (plus every co-reset register),
   driving/reading assignments and always blocks, and fan-in/fan-out trees.
5. From the Signal Explorer, click **"Show Fan-in Graph"** / **"Show Fan-out
   Graph"** to open the **Dependency Graph** tab's interactive Cytoscape
   visualization, or select **"Path to…"** there to trace the shortest
   dependency path between two signals.
6. Use the **hierarchy tree** in the sidebar to walk the instance tree from
   the top module down through generate-block-expanded arrays.

## REST API

`/search` `/module` `/module/hierarchy` `/module/registers` `/signal`
`/signal/assignments` `/signal/always-blocks` `/signal/clock-domain`
`/signal/reset-tree` `/driver` `/receivers` `/fanin` `/fanout` `/path`

## Retrieval engine (importable directly, no HTTP required)

```python
from retrieval.engine import RetrievalEngine
from storage.pipeline import load_or_build_graph

graph = load_or_build_graph(tree_path, meta_path, db_path)
engine = RetrievalEngine(graph)

engine.trace_driver("ctrl_enable_q", module="tpe_cmd_proc")
engine.fanin("ctrl_enable_q", module="tpe_cmd_proc", max_depth=4)
engine.dependency_path("ctrl_enable_q", "s_awvalid", module="tpe_cmd_proc")
```
