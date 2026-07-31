# RTLGraph

> Stop retrieving RTL text. Start retrieving hardware knowledge.

**RTLGraph is an AI-ready semantic retrieval engine that transforms a
compiler's elaborated view of a hardware design into a knowledge graph for
hardware reasoning.**

[Try the reference implementation →](https://rtlgraph.vercel.app)

---

## The problem

Every RTL and verification engineer already knows this pain: a bug shows up
on a signal, and answering "what actually drives this?" means grepping
across hundreds of files, following instance names through several levels of
hierarchy, mentally unrolling generate blocks, and hoping you didn't miss a
sensitivity list written in an unusual order. It is slow, and it is easy to
get subtly wrong even for an experienced engineer.

The current generation of AI coding assistants doesn't fix this — it
inherits it. They retrieve RTL the same way they retrieve any other
codebase: full-text search, or embeddings over chunks of source. That works
reasonably well for software, where a function is a mostly self-contained
unit of meaning. It works poorly for RTL, because **RTL is not naturally
organized as text.**

A hardware design is a graph: module hierarchy, signal connectivity,
instance-to-instance wiring, combinational and sequential dependencies,
clock and reset domains, state machines. None of that structure is visible
to a text chunker or an embedding model — a `data_chain` signal declared
inside the third lane of an unrolled generate loop looks, to an embedding,
just like a string of characters near some other strings. The actual
question an engineer is asking — *what is this connected to, structurally?*
— is a graph-traversal question wearing a text-search disguise.

## The central idea

Modern RTL compilers and simulators don't work from source text either.
Before a design can be simulated or synthesized, it has to be **elaborated**:
every parameter bound, every generate block unrolled, every symbol resolved,
every module instance linked to its definition, every signal's driver and
readers identified. This elaboration step already produces exactly the
structural representation a retrieval system needs — it just normally gets
thrown away after the compiler finishes its own job.

**RTLGraph's core idea: instead of retrieving RTL source code, leverage the
compiler's elaborated design representation to construct a semantic
knowledge graph that AI agents can reason over.** The graph becomes the
retrieval layer. Source text is never chunked, embedded, or searched at
query time — the compiler has already done the hard part of turning
ambiguous, macro-laden, parameterized source into a resolved structure, and
RTLGraph's only job is to preserve that structure as a queryable graph
instead of discarding it.

```
┌──────────────────────────────────────────────────┐
│               RTL Source (SystemVerilog)           │
└───────────────────────┬────────────────────────────┘
                         │  elaborated by a compiler
                         ▼
┌──────────────────────────────────────────────────┐
│                Compiler / Elaborator                │
│   resolves hierarchy, parameters, generate blocks,   │
│   symbols, connectivity, types, source mapping       │
└───────────────────────┬────────────────────────────┘
                         │  canonical adapter (one per compiler)
                         ▼
┌──────────────────────────────────────────────────┐
│            Canonical Design Graph (RTLGraph)         │
│  Modules · Instances · Signals · Registers · Clocks · │
│  Resets · Assignments · dependency & connectivity edges│
└───────────────────────┬────────────────────────────┘
                         │  graph traversal — no embeddings
                         ▼
┌──────────────────────────────────────────────────┐
│                  Retrieval Engine                    │
│  trace_driver · fanin/fanout · dependency_path ·      │
│  clock_domain · reset_tree · module_hierarchy · ...   │
└───────────────────────┬────────────────────────────┘
                         │  structural evidence, not text
                         ▼
┌──────────────────────────────────────────────────┐
│                  AI Agent  ·  Human                  │
│  debug assistants · root-cause analysis · design      │
│  review · documentation · impact analysis · ...        │
└──────────────────────────────────────────────────┘
```

## Why elaborated data beats RTL source text as a retrieval source

Everything below is work a text-based (or embedding-based) retrieval system
has to rediscover itself, imperfectly, from source. A compiler has already
done it correctly, because its own downstream job (simulation or synthesis)
depends on getting it right:

- **Module hierarchy** — the full instance tree is resolved, including every
  level of nesting, not just what's visible in one file.
- **Parameters** — every parameter is bound to its actual elaborated value;
  a module instantiated three times with three different parameter sets is
  three distinct, individually correct elaborated structures, not one
  ambiguous template.
- **Generate blocks** — `generate for` loops are fully unrolled into their
  individual, addressable instances and signals, rather than left as a loop
  construct a retrieval system would have to interpret.
- **Symbol resolution** — every reference to a signal is already linked to
  its declaration, across file and module boundaries, with macro and
  `` `include`` expansion already applied.
- **Connectivity** — every port-to-net connection at every instance boundary
  is resolved and explicit.
- **Expressions** — the actual logic driving a signal (an assignment, an
  always-block body, a condition) is available as structured data, not as a
  string to re-parse.
- **Source mapping** — every element still carries its original
  file/line/column, so structural answers can cite back to exact source
  locations.

A text or embedding-based system has to approximate all of this from
un-elaborated source and will get it wrong on exactly the constructs real
designs actually use — parameterized instances, unrolled arrays, unusual
sensitivity-list ordering. A retrieval system built on the compiler's own
resolved output doesn't have to approximate any of it.

## Retrieval philosophy: evidence, not text

RTLGraph does not use vector search, and it does not retrieve chunks of RTL
source. It retrieves **structural evidence**, produced by graph traversal
over the canonical graph:

| Question an engineer asks | How it's answered |
|---|---|
| Who drives this signal? | traverse `DRIVES` edges into the signal node |
| Which modules/instances consume this signal? | traverse `READS` / `CONNECTED_TO` edges out of it |
| What is the dependency path between two signals? | shortest path over `DEPENDS_ON` edges |
| Which always block writes this register? | traverse `WRITES` edges into the register |
| What logic is inside this clock domain? | traverse `CLOCKED_BY` edges from the clock node |
| Show the fan-in cone | bounded breadth-first traversal over `DEPENDS_ON`, inbound |
| Show the fan-out cone | bounded breadth-first traversal over `DEPENDS_ON`, outbound |
| Locate every register affected by a reset | traverse `RESET_BY` edges from the reset-domain node |

Every one of these is a deterministic graph operation with an exact,
explainable answer — the same query returns the same result every time,
which is the property that actually matters for debugging real hardware.
There is no relevance ranking, no approximate nearest-neighbor search, and
nothing for a retrieval system to hallucinate.

## Why this reduces the burden on AI agents

Ask an LLM to "read this RTL and tell me what drives this signal" and you're
asking it to behave as an ad hoc RTL compiler — parsing hierarchy,
resolving generate blocks, tracking parameter bindings — using only pattern
matching over text, with no guarantee of correctness, and burning a large
fraction of its context window on files that turn out to be irrelevant.

With a semantic graph already built, the retrieval layer does that work
instead and returns only the relevant structural evidence: the specific
driving assignment, its enclosing always block, the clock and reset it's
governed by, its immediate fan-in — a handful of precise facts instead of
thousands of lines of surrounding code. Context size drops sharply, and
correctness stops depending on the model's ability to mentally simulate a
hardware compiler. **The retrieval engine is the core innovation here; the
LLM downstream of it becomes optional** — the graph is useful to a human
engineer through the same APIs, with no model in the loop at all.

## Why this matters

A semantic hardware graph is a primitive, not an end product — once it
exists, a broad class of AI-assisted hardware engineering tools becomes
substantially easier to build on top of it, because they all currently start
by re-solving the same "understand the design's structure" problem from
scratch:

- **AI debug assistants** that trace a failure to its structural cause
  instead of guessing from surrounding code.
- **Root-cause analysis** that walks a verified dependency chain rather than
  a plausible-sounding one.
- **Design exploration** for an engineer (or agent) getting oriented in an
  unfamiliar codebase.
- **Automatic documentation** generated from the design's actual, resolved
  structure rather than comments that drift out of sync with it.
- **Design review** that can check structural claims ("is this register
  really in the same reset domain as its neighbors?") mechanically.
- **Change-impact analysis** — given a proposed edit, enumerate everything
  structurally reachable from it before it's made.
- **Testbench and assertion generation** informed by real connectivity and
  clock/reset domains instead of naming-convention heuristics.
- **Coverage analysis** that can be reasoned about structurally, not just
  numerically.
- **Design knowledge search** across a codebase too large for any one
  engineer to hold in their head.
- **Onboarding new engineers**, who can ask the same structural questions a
  senior engineer would instead of reading the whole codebase linearly.
- **Interactive design navigation** — the reference UI in this repo is one
  example, not the point of the architecture.

## Architecture: compiler-agnostic by design

RTLGraph is **not tied to Verilator.** Verilator is the first validated
backend — chosen because it is open-source and (unusually, for a
compiler) exposes its elaborated internal AST directly — not the
architecture's ceiling.

The four-layer separation shown in the diagram above is deliberate:
`Compiler → Canonical Graph → Retrieval Engine → AI Agent`. The retrieval
engine and everything downstream of it operate purely on the canonical graph
(`src/models/design.py`) and know nothing about Verilator, or any other
compiler, specifically. A different compiler backend means writing a new
adapter that produces the same canonical model — nothing in `src/graph`,
`src/retrieval`, or `src/api` has to change.

**Future compiler support** the architecture is designed to accommodate:

- **Verilator** — implemented today (`src/parser`), validated against a real
  multi-module design (see below).
- **Surelog / UHDM** — [UHDM](https://github.com/chipsalliance/UHDM) (Universal
  Hardware Data Model) is an open, tool-agnostic elaborated-design format that
  several compilers, including some commercial ones, are converging toward as
  an interchange representation — the most realistic near-term path to
  additional backends without a bespoke adapter per proprietary AST.
- **Synopsys VCS**, **Cadence Xcelium/IES** — commercial simulators that
  don't expose a public elaborated-AST dump the way Verilator does; a UHDM
  bridge (where available) or a vendor-specific export path would be the
  adapter target, still producing the same canonical model.
- **Future proprietary compilers** — the only requirement to add a backend
  is an adapter that emits the canonical `Design` model; the retrieval layer
  and every application built on it are unaffected.

---

## The reference implementation

Everything above is the architecture. This repository is one validated
instance of it: a Verilator backend, a canonical graph builder, a
graph-traversal retrieval engine, a FastAPI layer, and a React + Cytoscape.js
UI for interactive exploration — with **no embeddings, no vector search, and
no LLM anywhere in the retrieval path.**

**Live demo: [rtlgraph.vercel.app](https://rtlgraph.vercel.app)**

### Validated against a real design

The bundled dataset is not synthetic — it's the actual elaborated output of
[**tpe-tensor-processing-engine**](https://github.com/bhavanibedreshankar/tpe-tensor-processing-engine),
an open-source educational AI accelerator (16×16 systolic-array
matrix-multiply engine, AXI4-Lite command processor, DMA, scheduler, on-chip
SRAM — 16 modules, 285 elaborated instances, intentionally seeded with
catalogued bugs for verification practice), regenerated with:

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
resolve cross-references generically (`src/parser/ast_index.py`). Both files
are committed at `data/sample/` so the deployed app is self-contained.

This dataset exercises exactly the constructs that make elaborated data
worth using in the first place: `generate for` loops unrolled into 256
individually-scoped `pe` instances, module names with bound parameter values
folded in (`dp_ram__DB10_A4_S10`), and sensitivity lists written in
non-obvious orders — all of which the parser resolves generically, with no
signal or module name ever hardcoded.

### Retrieval API

Available as direct Python calls (no HTTP, no LLM):

```python
from retrieval.engine import RetrievalEngine
from storage.pipeline import load_or_build_graph

graph = load_or_build_graph(tree_path, meta_path, db_path)
engine = RetrievalEngine(graph)

engine.trace_driver("ctrl_enable_q", module="tpe_cmd_proc")
engine.fanin("ctrl_enable_q", module="tpe_cmd_proc", max_depth=4)
engine.dependency_path("ctrl_enable_q", "s_awvalid", module="tpe_cmd_proc")
```

`find_signal` · `find_module` · `trace_driver` · `trace_receivers` · `fanin`
· `fanout` · `dependency_path` · `clock_domain` · `reset_tree` ·
`module_hierarchy` · `find_registers` · `find_assignments` ·
`find_always_blocks`

Or the same operations over REST:

`/search` `/module` `/module/hierarchy` `/module/registers` `/signal`
`/signal/assignments` `/signal/always-blocks` `/signal/clock-domain`
`/signal/reset-tree` `/driver` `/receivers` `/fanin` `/fanout` `/path`

### Canonical graph

NetworkX `MultiDiGraph`, cached to SQLite. 11 node types (Module, Instance,
Port, Signal, Register, Parameter, Expression, Assignment, AlwaysBlock,
ClockDomain, ResetDomain) and 9 relationship types (`INSTANCE_OF`,
`CONTAINS`, `DRIVES`, `READS`, `WRITES`, `CONNECTED_TO`, `CLOCKED_BY`,
`RESET_BY`, `DEPENDS_ON`). Clock and reset signals are resolved by a
design-wide sensitivity-frequency vote rather than trusted sensitivity-list
order, which Verilator does not guarantee (`negedge rst_n or posedge clk` is
legal and common).

### Tech stack

- Python 3.11+, FastAPI, NetworkX, Pydantic, SQLite, pytest
- React 19, TypeScript, Vite, Cytoscape.js (`cytoscape-dagre` layout)

### Project structure

```
src/
  parser/     Verilator AST JSON -> canonical object model (the only compiler-specific layer)
  models/     Pydantic canonical types (Module, Instance, Signal, ...)
  graph/      canonical model -> networkx.MultiDiGraph
  storage/    SQLite persistence + build/load caching pipeline
  retrieval/  graph-traversal retrieval APIs (no embeddings/LLM)
  api/        FastAPI REST layer
  tests/      pytest suite run against a real Verilator sample
ui/           React + TypeScript + Cytoscape.js frontend
```

### Setup & run

**Backend**

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pytest -q

# runs against the bundled sample design (data/sample/) by default
.venv/bin/uvicorn api.main:app --app-dir src --port 8010

# or point at your own Verilator dump (design.tree.json + design.meta.json,
# produced by the `verilator --json-only ...` command above)
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

Open the app: search or browse to a module, select a signal to see its
driver trace / receivers / clock & reset domains / fan-in and fan-out trees,
and use the dependency-graph tab for an interactive Cytoscape visualization
or a shortest-path query between two signals.

### Implementation status & open problems

Everything above is proven against a small, static, single-snapshot design.
The honest next question, thinking like the design/verification engineer who
would have to run this day to day: RTL in an active project changes many
times a day across many engineers — does this require fully re-elaborating
and rebuilding the graph on every change, and is that practical?

Right now: yes, and that's a real limitation, not a solved problem.

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

None of this is a reason not to use the tool as-is for what it's good at
today — point-in-time design understanding and debugging on a snapshot —
but it's the honest list of what "run this continuously against an
actively-changing codebase" would actually require solving.
