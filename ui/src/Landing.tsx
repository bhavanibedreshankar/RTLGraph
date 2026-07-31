import './Landing.css'

const RTLGRAPH_REPO = 'https://github.com/bhavanibedreshankar/RTLGraph'
const TPE_REPO = 'https://github.com/bhavanibedreshankar/tpe-tensor-processing-engine'

interface Demo {
  tag: string
  title: string
  description: string
  href: string
}

const DEMOS: Demo[] = [
  {
    tag: 'Hierarchy',
    title: 'Browse the top-level design',
    description: 'Open the top module and see every port, register, instance, and always block it contains — the whole chip, one screen.',
    href: '/app?tab=module&module=tpe_top',
  },
  {
    tag: 'Driver trace',
    title: 'What drives this control register?',
    description: 'ctrl_enable_q in the command processor — see the exact assignment, always block, clock, and reset that control it.',
    href: '/app?tab=signal&signal=ctrl_enable_q&module=tpe_cmd_proc',
  },
  {
    tag: 'Fan-in',
    title: 'Walk a signal’s fan-in cone',
    description: 'Every signal, transitively, that this register’s value depends on — as an interactive graph, not a wall of code.',
    href: '/app?tab=graph&mode=fanin&signal=ctrl_enable_q&module=tpe_cmd_proc',
  },
  {
    tag: 'Fan-out',
    title: 'Walk a signal’s fan-out cone',
    description: 'Everything downstream that reads an AXI handshake signal, several hops deep, visualized live.',
    href: '/app?tab=graph&mode=fanout&signal=s_awvalid&module=tpe_cmd_proc',
  },
  {
    tag: 'Path finder',
    title: 'Find the path between two signals',
    description: 'Ask RTLGraph for the shortest logical path from one register to a totally unrelated-looking input — and get the actual chain.',
    href: '/app?tab=graph&mode=path&signal=ctrl_enable_q&module=tpe_cmd_proc&destination=s_awvalid',
  },
  {
    tag: 'Generate blocks',
    title: 'Explore an unrolled array',
    description: 'The matrix engine’s systolic array unrolls into 256 near-identical PE instances — RTLGraph keeps every lane individually addressable.',
    href: '/app?tab=signal&signal=data_chain',
  },
]

export default function Landing() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <span className="brand">RTLGraph</span>
        <div className="nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#demos">Try it</a>
          <a href={RTLGRAPH_REPO} target="_blank" rel="noopener noreferrer">GitHub</a>
          <a className="cta" href="/app">Open the app →</a>
        </div>
      </nav>

      <section className="hero">
        <span className="eyebrow">Verilator → semantic graph → answers</span>
        <h1>Ask your chip's wiring questions directly.</h1>
        <p className="lede">
          RTLGraph turns an elaborated hardware design into a queryable graph
          database. No simulation, no waveform viewer, no LLM guesswork —
          just the actual modules, signals, registers, and dependencies,
          indexed so you can trace what drives what in one click.
        </p>
        <div className="hero-ctas">
          <a className="btn btn-primary" href="/app">Launch the live demo</a>
          <a className="btn btn-secondary" href="#demos">See example queries ↓</a>
        </div>
        <div className="hero-stats">
          <div className="hero-stat"><div className="num">16</div><div className="label">modules</div></div>
          <div className="hero-stat"><div className="num">285</div><div className="label">instances</div></div>
          <div className="hero-stat"><div className="num">3,379</div><div className="label">graph nodes</div></div>
          <div className="hero-stat"><div className="num">13,632</div><div className="label">typed edges</div></div>
        </div>
      </section>

      <section className="section section-alt" id="how-it-works">
        <h2>You don't need to know RTL to use this</h2>
        <p className="section-sub">
          Here's the whole idea, in plain English.
        </p>
        <div className="explainer-grid">
          <div>
            <p>
              <strong>RTL (Register-Transfer Level)</strong> is the actual
              blueprint engineers write to describe a chip's logic — every
              wire, register, and conditional block that eventually becomes
              real silicon. <strong>Verilator</strong> is an open-source tool
              that reads that blueprint and compiles it into an internal
              structural representation.
            </p>
            <p>
              <strong>RTLGraph takes that compiled structure and turns it
              into a graph</strong> — modules and instances nest inside each
              other, signals and registers are nodes, and typed edges record
              exactly who drives, reads, depends on, or is clocked by what.
              Once it's a graph, questions that would normally mean grepping
              through thousands of lines of code become direct, instant graph
              lookups: <em>what drives this? what does this affect? what's
              this signal's reset domain?</em>
            </p>
            <p>
              Everything is deterministic graph traversal (Python, NetworkX)
              — <strong>there is no embedding model, no vector search, and
              no LLM anywhere in the retrieval path.</strong> The same query
              returns the same structural answer every time, which is exactly
              what you want when you're debugging real hardware.
            </p>
          </div>
          <div className="concept-diagram">
            <div className="concept-row">
              <span className="concept-node" style={{ borderColor: '#9b8ce655', color: '#9b8ce6' }}>
                <span className="concept-dot" style={{ background: '#9b8ce6' }} /> Module
              </span>
              <span className="concept-arrow">CONTAINS →</span>
              <span className="concept-node" style={{ borderColor: '#e65a8f55', color: '#e65a8f' }}>
                <span className="concept-dot" style={{ background: '#e65a8f' }} /> Instance
              </span>
            </div>
            <div className="concept-row">
              <span className="concept-node" style={{ borderColor: '#e65a8f55', color: '#e65a8f' }}>
                <span className="concept-dot" style={{ background: '#e65a8f' }} /> Instance
              </span>
              <span className="concept-arrow">INSTANCE_OF →</span>
              <span className="concept-node" style={{ borderColor: '#9b8ce655', color: '#9b8ce6' }}>
                <span className="concept-dot" style={{ background: '#9b8ce6' }} /> Module
              </span>
            </div>
            <div className="concept-row">
              <span className="concept-node" style={{ borderColor: '#e6a15a55', color: '#e6a15a' }}>
                <span className="concept-dot" style={{ background: '#e6a15a' }} /> Register
              </span>
              <span className="concept-arrow">DEPENDS_ON →</span>
              <span className="concept-node" style={{ borderColor: '#5aa9e655', color: '#5aa9e6' }}>
                <span className="concept-dot" style={{ background: '#5aa9e6' }} /> Signal
              </span>
            </div>
            <div className="concept-row">
              <span className="concept-node" style={{ borderColor: '#e6a15a55', color: '#e6a15a' }}>
                <span className="concept-dot" style={{ background: '#e6a15a' }} /> Register
              </span>
              <span className="concept-arrow">CLOCKED_BY / RESET_BY →</span>
              <span className="concept-node" style={{ borderColor: '#8a8f9c55', color: '#8a8f9c' }}>
                Clock / Reset Domain
              </span>
            </div>
            <div className="concept-row">
              <span className="concept-node" style={{ borderColor: '#6bbf7a55', color: '#6bbf7a' }}>
                <span className="concept-dot" style={{ background: '#6bbf7a' }} /> Port
              </span>
              <span className="concept-arrow">CONNECTED_TO →</span>
              <span className="concept-node" style={{ borderColor: '#5aa9e655', color: '#5aa9e6' }}>
                <span className="concept-dot" style={{ background: '#5aa9e6' }} /> Signal
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>What you can do with it</h2>
        <p className="section-sub">Every item below is a real, working retrieval API — not a mockup.</p>
        <div className="feature-grid">
          <div className="feature-card">
            <div className="icon">🔍</div>
            <h3>Search everything</h3>
            <p>Find any module, instance, signal, register, or port by name across the entire design in one query.</p>
          </div>
          <div className="feature-card">
            <div className="icon">🧭</div>
            <h3>Driver &amp; receiver tracing</h3>
            <p>Instantly see what assignment or always-block drives a signal, and every place that reads it.</p>
          </div>
          <div className="feature-card">
            <div className="icon">🌳</div>
            <h3>Fan-in / fan-out cones</h3>
            <p>Walk the full transitive dependency tree in either direction, depth-limited, rendered as an interactive graph.</p>
          </div>
          <div className="feature-card">
            <div className="icon">📍</div>
            <h3>Dependency path finder</h3>
            <p>Ask for the shortest logical path between any two signals, anywhere in the hierarchy.</p>
          </div>
          <div className="feature-card">
            <div className="icon">⏱️</div>
            <h3>Clock &amp; reset domains</h3>
            <p>Know exactly which clock and reset tree every register belongs to, plus every register that shares it.</p>
          </div>
          <div className="feature-card">
            <div className="icon">🏗️</div>
            <h3>Full instance hierarchy</h3>
            <p>Walk the elaborated instance tree, including generate-block arrays unrolled into individually addressable lanes.</p>
          </div>
        </div>
      </section>

      <section className="section section-alt" id="demos">
        <h2>Try it live</h2>
        <p className="section-sub">
          Each card opens the app pre-loaded with a real query against the
          design below — no typing required to see it work.
        </p>
        <div className="demo-grid">
          {DEMOS.map((demo) => (
            <a className="demo-card" href={demo.href} key={demo.href}>
              <span className="demo-tag">{demo.tag}</span>
              <h3>{demo.title}</h3>
              <p>{demo.description}</p>
              <span className="demo-go">Try it →</span>
            </a>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>The design behind the demo</h2>
        <div className="source-card">
          <div className="source-copy">
            <span className="bug-badge">🐛 intentionally seeded with bugs</span>
            <h3>TPE — Tensor Processing Engine</h3>
            <p>
              This live demo runs against a complete, real RTL design: an
              open-source, educational AI accelerator implementing a
              16×16 systolic-array matrix-multiply engine (256 INT8 MACs/cycle),
              with an AXI4-Lite command processor, DMA engine, scheduler,
              on-chip SRAM, and a full pyuvm/cocotb verification stack —
              intentionally seeded with catalogued bugs as a hardware-debugging
              teaching exercise. It's exactly the kind of design where being
              able to ask "what drives this?" instead of grepping through
              SystemVerilog earns its keep.
            </p>
            <a className="btn btn-secondary" href={TPE_REPO} target="_blank" rel="noopener noreferrer">
              View the source design on GitHub →
            </a>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Built with</h2>
        <div className="stack-strip">
          <span className="stack-pill">Verilator</span>
          <span className="stack-pill">Python</span>
          <span className="stack-pill">FastAPI</span>
          <span className="stack-pill">NetworkX</span>
          <span className="stack-pill">SQLite</span>
          <span className="stack-pill">Pydantic</span>
          <span className="stack-pill">React</span>
          <span className="stack-pill">TypeScript</span>
          <span className="stack-pill">Cytoscape.js</span>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="footer-links">
          <a href={RTLGRAPH_REPO} target="_blank" rel="noopener noreferrer">RTLGraph on GitHub</a>
          <a href={TPE_REPO} target="_blank" rel="noopener noreferrer">Source design (TPE) on GitHub</a>
          <a href="/app">Open the app</a>
        </div>
        RTLGraph is a retrieval engine, not an LLM — every answer above is a deterministic graph query.
      </footer>
    </div>
  )
}
