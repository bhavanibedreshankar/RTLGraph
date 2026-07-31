# RTLGraph

**Live demo: [rtlgraph.vercel.app](https://rtlgraph.vercel.app)**

A semantic retrieval engine for RTL designs. RTLGraph parses Verilator's
elaborated AST JSON output into a canonical object model, builds a typed
directed graph, persists it to SQLite, and exposes graph-traversal retrieval
APIs over REST — **no embeddings, no vector search, no LLM anywhere in the
retrieval path.** The engine is designed to be embedded directly into an AI
agent's toolset for debugging, design understanding, and failure analysis,
or browsed interactively through the bundled React + Cytoscape.js UI.

## Where the sample data comes from

The bundled demo graph is not hand-written or scraped from source text — it's
the **actual elaborated output of a real RTL design**, compiled with
[Verilator](https://www.veripool.org/verilator/):
[**bhavanibedreshankar/tpe-tensor-processing-engine**](https://github.com/bhavanibedreshankar/tpe-tensor-processing-engine),
an open-source educational AI accelerator (16×16 systolic-array matrix-multiply
engine, AXI4-Lite command processor, DMA, scheduler, on-chip SRAM — 16 modules,
285 elaborated instances) that's intentionally seeded with catalogued bugs for
verification practice.

It was regenerated with:

```bash
verilator \
    --json-only \
    --json-only-output /Users/bhavanibs/Documents/Claude/tpe_database/design.tree.json \
    --json-only-meta-output /Users/bhavanibs/Documents/Claude/tpe_database/design.meta.json \
    -Wall -Wno-fatal \
    -f rtl/filelist.f \
    --top-module tpe_top > /Users/bhavanibs/Documents/Claude/tpe_database/verilator.log 2>&1
```

`--json-only` makes Verilator elaborate the design (resolve includes, macros,
parameters, generate-for loops, and types) and dump its internal AST as JSON
instead of proceeding to C++ codegen; `--json-only-meta-output` dumps the
companion source-file table and pointer-field schema the parser uses to
resolve cross-references generically (see `src/parser/ast_index.py`). The two
files are committed at `data/sample/` so the deployed app is self-contained.

### Why compile the design instead of parsing the source text?

A regex/text-based RTL parser has to reimplement a meaningful chunk of a
Verilog/SystemVerilog compiler to be reliable — macro expansion,
`` `include`` resolution, parameter binding, generate-block elaboration,
width/type inference — and will quietly get it wrong on real designs (this
project's own sample hits every one of those: `generate for` loops that unroll
`mac_array` into 256 individually-scoped `pe` instances, module names that
embed bound parameter values like `dp_ram__DB10_A4_S10`, sensitivity lists in
non-obvious orders). Verilator has already solved all of that correctly to do
its own job (simulation), so RTLGraph parses its *answer* instead of
re-deriving it — which is also why the parser in this repo never hardcodes a
signal or module name: it's walking whatever elaborated structure Verilator
actually produced, generically.

**This generalizes beyond Verilator in principle, but not for free.** VCS and
Xcelium are commercial simulators and don't expose an equivalent public
elaborated-AST-as-JSON dump the way Verilator's `--json-only` does. The
realistic path to a multi-compiler version of this tool is a common
intermediate representation — most plausibly
[UHDM](https://github.com/chipsalliance/UHDM) (Universal Hardware Data Model,
via [Surelog](https://github.com/chipsalliance/Surelog)), which several tools
including some commercial ones are converging on as an interchange format —
rather than writing a bespoke adapter per proprietary AST schema. The graph
builder and retrieval engine (`src/graph`, `src/retrieval`) are already
decoupled from the Verilator-specific parser (`src/parser`) for exactly this
reason: swapping in a UHDM-based parser would only mean producing the same
canonical `Design` object model (`src/models/design.py`), not touching
anything downstream.

## Why this matters for RTL debugging

The concrete failure mode this tool targets: an engineer (or an AI agent) is
staring at a bug report — "`ctrl_enable_q` has the wrong value" — in a design
with hundreds of files. The traditional move is `grep` and manual traversal
through however many files that signal touches, hoping not to miss a
generate-block instance or an unusual sensitivity list. That's slow and
error-prone even for humans, and worse for an LLM reading code out of context,
which will confidently hallucinate a connection that isn't there.

With the graph already built, the same investigation is a handful of
deterministic lookups against this repo's own verified sample:

```python
engine.trace_driver("ctrl_enable_q", module="tpe_cmd_proc")
# -> the exact Assignment + AlwaysBlock that drives it, with source loc

engine.clock_domain("ctrl_enable_q", module="tpe_cmd_proc")
engine.reset_tree("ctrl_enable_q", module="tpe_cmd_proc")
# -> clk / rst_n, plus every other register reset alongside it

engine.fanin("ctrl_enable_q", module="tpe_cmd_proc", max_depth=4)
# -> the full transitive cone of everything this register's value depends on

engine.dependency_path("ctrl_enable_q", "s_awvalid", module="tpe_cmd_proc")
# -> the shortest structural chain connecting two signals that don't
#    obviously look related
```

Every one of those is an exact, explainable graph traversal over the
compiler's own resolved view of the design — not a guess.

## How an AI agent uses this

RTLGraph is deliberately built as a **tool**, not an app an LLM has to
scrape: the retrieval engine (`src/retrieval/engine.py`) has zero HTTP or LLM
dependency, so it drops straight into an agent's tool-call loop (or behind
the REST API for a remote agent). A typical agent workflow:

1. A test fails; the agent gets a signal name and instance path from the
   failure log.
2. It calls `find_signal` / `trace_driver` to identify exactly what wrote the
   value, and `clock_domain` / `reset_tree` to rule out a clock/reset-domain
   mismatch.
3. It walks `fanin` a few levels to build a small, *verified* subgraph of
   everything that could have influenced the bad value — instead of dumping
   the whole file into an LLM context window and asking it to "figure out the
   wiring."
4. It uses `dependency_path` to check a specific hypothesis ("is X even
   reachable from Y?") before proposing a fix, and every node it reasons about
   carries the real source `loc` (file:line:col) to cite back to the human.

The point isn't that the LLM stops being useful — it's that the LLM stops
being asked to *be* the RTL compiler. It reasons over ground-truth structure
instead of re-deriving it from text, which is exactly the class of mistake
grep-and-guess debugging (by humans or agents) tends to make on real designs.

## Scaling to real RTL development

Everything above is proven against a small, static, single-snapshot design.
The honest next question, thinking like the design/verification engineer who
would actually have to run this day to day: **RTL in an active project
changes many times a day across many engineers — does this tool have to
fully re-elaborate and rebuild the graph on every change, and is that
practical?**

Right now: yes, and that's a real limitation, not a solved problem. Here's
the concrete breakdown of why, and the directions worth pursuing to fix it.

| # | Problem | Why it bites in practice | Direction to fix |
|---|---------|---------------------------|-------------------|
| 1 | **No incremental rebuild.** `storage/sqlite_store.py` deletes and rewrites the *entire* SQLite DB on every build; there's no notion of "only module X changed." | A one-line change to a leaf module currently costs the same as a from-scratch build of the whole design. At team scale (dozens of commits/day), that's wasted CPU on every single change if run eagerly. | Content-hash each module's elaborated subtree; on rebuild, diff against the previous graph's per-module hashes and only re-insert nodes/edges for modules whose hash changed, splicing the rest through unchanged. Needs stable node IDs across rebuilds (already true here — IDs are `module.name`-keyed, not addr-keyed) and a hierarchy-aware invalidation pass (a changed leaf module's parents' instance/pin edges may also need re-linking). |
| 2 | **Verilator itself doesn't do incremental elaboration.** Even with a smarter graph-diff on my side, Verilator re-elaborates the *whole* design from `-f filelist.f` every time `--json-only` runs — there's no "just re-elaborate this module" mode. | Sets a hard floor on latency regardless of how clever the graph-side incrementality gets. For a large SoC (vs. this 16-module sample), elaboration alone can be minutes. | Don't run it inline on every save. Trigger on a debounced file-watch (batch rapid edits) for local/interactive use, and on CI only for changed filelist paths (skip when a commit doesn't touch RTL). Accept some staleness for anything faster than that — same trade every incremental build system makes. |
| 3 | **JSON dump size scales with design size, and it's loaded fully into memory.** This sample's dump is ~5.5MB for 16 modules / ~3,400 graph nodes, parsed in ~0.1s. A real SoC with hundreds of modules could produce a multi-GB dump, and `ast_index.py` currently `json.load`s the whole thing plus builds a full `addr -> node` index in RAM. | Multi-GB `json.load` + Python object overhead (typically 3-5x the file size in memory) risks becoming a memory/latency wall well before the design gets exotically large. | Stream-parse (e.g. `ijson`) instead of loading the whole tree at once; or have Verilator scope the dump to a subsystem (`--top-module` per IP block) and stitch subsystem graphs together at the boundary rather than elaborating the entire chip in one JSON blob. |
| 4 | **Elaborated module identity is parameter-sensitive.** Verilator bakes bound parameter values into elaborated module names (`dp_ram__DB10_A4_S10`); a param change looks like "new/deleted module," not "modified module," to a naive diff. Generate-block unrolling has the same effect at the instance level if a loop bound changes (256 `pe` instances becoming 288 shifts every scoped name after it). | Naive content-hashing (problem #1) will misfire here — a single parameter tweak can look like most of the subtree "changed" even when the logic didn't. | Diff on (orig module name, parameter bindings) as a structured key rather than the mangled elaborated name, so the diff engine can recognize "same module, different parameters" instead of treating it as unrelated. |
| 5 | **Multiple build configurations multiply everything.** Real projects elaborate the same RTL under several configs (ASIC vs. FPGA target, different memory sizes, pre-DFT vs. post-DFT, per-subsystem verification top-levels). Each is a structurally different elaborated graph. | Naively, that's N full graphs (N × the storage/rebuild cost of #1-3) for N configs, growing linearly with configuration count, not design count. | Store one graph per (design, config) key with the module-level dedup from #1 shared across configs where the *underlying* RTL is identical — most configs differ in only a handful of parameters/defines, so the majority of module subgraphs should be reusable. |
| 6 | **No versioning / history.** One graph = one point-in-time snapshot; rebuilding overwrites it. There's no "what changed between yesterday's build and today's," which is one of the most valuable debugging questions in an actively-changing codebase. | Can't answer "did this driver change last week" without keeping N full snapshots, which multiplies disk cost linearly with history depth. | Content-addressed, git-like storage for node/edge records (dedup unchanged nodes across versions instead of duplicating the whole graph per snapshot) rather than one SQLite file per build. |
| 7 | **SQLite has a single-writer model.** Fine for one engineer's local instance; not fine as a shared team service where CI is rebuilding while others are querying. | Concurrent-write contention, and no natural multi-tenant story. | For a shared/hosted deployment, move to a server-backed store (Postgres, or a real graph DB) behind the same retrieval-engine interface — `src/retrieval/engine.py` only depends on a `networkx.MultiDiGraph`, so the storage layer is already swappable without touching retrieval logic. |
| 8 | **Black-boxed / IP-protected submodules break full visibility.** Real SoCs pull in vendor IP that may be given as an encrypted or source-unavailable model — Verilator can't elaborate what it can't see inside. | The parser currently assumes full RTL visibility; an opaque IP block would either fail to elaborate or (worse) silently produce an incomplete picture without saying so. | Explicit "black box" node type for unelaboratable instances (ports/pins visible from the parent's connectivity, internals absent) so the retrieval engine degrades gracefully and *says* "opaque here" instead of silently stopping. |
| 9 | **This is a static structural graph only — no runtime correlation.** RTLGraph knows what's *wired* to what; it has no idea what value anything actually took during a failing simulation, no waveform/coverage data. | The most common real debugging question is "why did this signal have the wrong *value* at time T," which needs dynamic (VCD/FSDB) data the static graph doesn't carry. | The most valuable extension, arguably more than incrementality: tag graph nodes with their simulation signal path so an agent can pivot from "this failed at time T in the waveform" to "here's the static fanin cone that could have caused it" in one hop — combining structural graph (this tool) with dynamic waveform data (a separate concern) rather than trying to make one tool do both. |

None of this is a reason not to use the tool as-is for what it's good at today
— point-in-time design understanding and debugging on a snapshot — but it's
the honest list of what "run this continuously against an actively-changing
codebase" would actually require solving.

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

# or point at your own Verilator dump (design.tree.json + design.meta.json,
# produced by `verilator --json-only --json-only-output ... --json-only-meta-output ...`
# -- see "Where the sample data comes from" below for the full command)
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
