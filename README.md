# RTLGraph

> Stop retrieving RTL text. Start retrieving hardware knowledge.

**Compiler elaboration is an untapped retrieval source for AI.**

Current AI systems repeatedly reconstruct information about a hardware
design that a compiler has already computed — hierarchy, connectivity,
dependencies, symbol resolution — by re-reading RTL as text, from scratch,
every time. RTLGraph proposes preserving that computation instead of
rediscovering it: capture a compiler's elaborated understanding of a design
as a canonical semantic graph, so AI agents and humans retrieve exact
structural evidence instead of reconstructing it from source.

[Try the reference implementation →](https://rtlgraph.vercel.app)

---

## The idea, in one picture

```
+-----------------------------------------------------------------------+
|                               RTL Source                              |
+-----------------------------------+-----------------------------------+
                                    |  elaboration
                                    v
+-----------------------------------------------------------------------+
|                                Compiler                               |
|     elaborates hierarchy, symbols, parameters, types, dependencies    |
+-----------------------------------+-----------------------------------+
                                    |  captured, not discarded
                                    v
+-----------------------------------------------------------------------+
|                    Compiler Knowledge  (the asset)                    |
|  hierarchy, connectivity, dependencies, clocks, resets, symbol table  |
+-----------------------------------+-----------------------------------+
                                    |  structured as a typed graph
                                    v
+-----------------------------------------------------------------------+
|                  Canonical Graph  (just the encoding)                 |
|                preserved, compiler-agnostic, queryable                |
+-----------------------------------+-----------------------------------+
                                    |  queried by traversal, not text search
                                    v
+-----------------------------------------------------------------------+
|                            Retrieval Engine                           |
|           graph traversal -- no embeddings, no vector search          |
+-----------------------------------+-----------------------------------+
                                    |  structural evidence, not text
                                    v
+-----------------------------------------------------------------------+
|                            AI Agent / Human                           |
+-----------------------------------------------------------------------+
```

Notice what's doing the work. **Not the graph.** The graph is just how
compiler knowledge gets preserved and made queryable — a serialization
choice, not the idea. The asset is the compiler's own resolved understanding
of the design, captured instead of discarded.

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

## Compilers already solved this. AI throws it away.

A compiler spends its entire existence solving exactly the problems a
retrieval system needs solved:

- **Symbol resolution** — every reference already linked to its declaration.
- **Hierarchy** — the full instance tree, resolved, not just what's visible
  in one file.
- **Elaboration** — generate loops unrolled, conditionally-compiled code
  resolved, macros expanded.
- **Parameter binding** — every parameter bound to its actual value at every
  instantiation site, not left as an ambiguous template.
- **Type inference** — every signal's width and type resolved.
- **Dependency analysis** — what drives what, and what depends on what.
- **Connectivity** — every port-to-net connection at every instance
  boundary, explicit.

Most AI systems working on hardware source throw all of that away and start
over from raw text, on every query, for a problem the compiler already
solved correctly — because its own downstream job (simulation or synthesis)
depends on getting it right.

**RTLGraph asks: what if we didn't?**

## Research hypothesis

Traditional AI retrieval systems treat RTL as text.

We hypothesize that compiler elaboration is a significantly richer
retrieval source.

If compiler knowledge is preserved as a canonical semantic graph, AI systems
can retrieve exact structural evidence instead of approximate text.

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

With preserved compiler knowledge already available as a graph, the
retrieval layer does that work instead and returns only the relevant
structural evidence: the specific driving assignment, its enclosing always
block, the clock and reset it's governed by, its immediate fan-in — a
handful of precise facts instead of thousands of lines of surrounding code.
Context size drops sharply, and correctness stops depending on the model's
ability to mentally simulate a hardware compiler. **The retrieval engine is
the core innovation here; the LLM downstream of it becomes optional** — the
graph is useful to a human engineer through the same APIs, with no model in
the loop at all.

## Why this matters

Preserved compiler knowledge is a primitive, not an end product — once it
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

## Why this idea isn't limited to RTL

The pattern is `Compiler → Knowledge → Graph → Retriever`, and nothing about
it is specific to hardware description languages. It depends only on there
being a compiler that already resolves a domain's ambiguous, textual source
into structured, disambiguated knowledge. RTLGraph validates the pattern
against Verilator first — not because the idea is about Verilator, but
because it's open-source and unusually willing to expose its elaborated
internals.

The same pattern applies anywhere a compiler already does that work:

- **Other RTL/HDL compilers** — VCS, Xcelium, Surelog (via UHDM) — different
  elaborators, same canonical graph.
- **General-purpose compiler IRs** — LLVM IR, MLIR — already-resolved symbol
  tables, call graphs, and data-flow, thrown away by most AI code-retrieval
  systems the same way text-based RTL retrieval throws away elaboration.
- **Other hardware representations** — synthesis netlists, gate-level
  connectivity, extracted state machines.
- **Structured domains outside hardware entirely** — a SQL query planner
  already resolves the semantic structure a text-based SQL-retrieval system
  would otherwise have to reconstruct; the same is true of anything with a
  compiler or planner sitting in front of it.

The claim isn't "this works for other RTL compilers too." It's broader:
**wherever a compiler already exists for a domain, its elaborated output is
a better retrieval substrate than that domain's source text.** RTL is simply
the domain where this project tests the idea first.

## Architecture: compiler-agnostic by design

RTLGraph is **not tied to Verilator.** Verilator is the first validated
backend — not the architecture's ceiling. The retrieval engine and
everything downstream of it operate purely on the canonical graph
(`src/models/design.py`) and know nothing about Verilator, or any other
compiler, specifically. A different compiler backend means writing a new
adapter that produces the same canonical model — nothing in `src/graph`,
`src/retrieval`, or `src/api` has to change.

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
    --json-only-output design.tree.json \
    --json-only-meta-output design.meta.json \
    -Wall -Wno-fatal \
    -f rtl/filelist.f \
    --top-module tpe_top
```

`--json-only` elaborates the design (resolves includes, macros, parameters,
generate-for loops, and types) and dumps the internal AST as JSON instead of
proceeding to C++ codegen. Both output files are committed at `data/sample/`
so the deployed app is self-contained; the parser that consumes them
(`src/parser/`) never hardcodes a signal or module name — it walks whatever
elaborated structure Verilator produced, generically, including constructs
that would break a naive parser: `generate for` loops unrolled into 256
individually-scoped `pe` instances, module names with bound parameter values
folded in (`dp_ram__DB10_A4_S10`), sensitivity lists in non-obvious orders.

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
docs/         future_work.md -- scaling this to an actively-changing codebase
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

---

Everything above is proven against a small, static, single-snapshot design.
For the honest engineering constraints of running this continuously against
an actively-changing, multi-engineer codebase — incremental rebuilds,
Verilator's own lack of incremental elaboration, storage/versioning at
scale, and the gap between static structure and runtime waveform data — see
[`docs/future_work.md`](docs/future_work.md).
