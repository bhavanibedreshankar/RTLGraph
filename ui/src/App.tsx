import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { rtlgraph } from './api'
import { FaninFanoutTree } from './components/FaninFanoutTree'
import { GraphView } from './components/GraphView'
import { HierarchyBrowser } from './components/HierarchyBrowser'
import { ModuleBrowser } from './components/ModuleBrowser'
import { ModuleDetailPanel } from './components/ModuleDetailPanel'
import { SearchBar } from './components/SearchBar'
import { SignalExplorer } from './components/SignalExplorer'
import { SignalPicker } from './components/SignalPicker'
import type { GraphNode } from './types'

type Tab = 'module' | 'signal' | 'graph'
type GraphMode = 'fanin' | 'fanout' | 'path'

export default function App() {
  const [topModule, setTopModule] = useState<string | null>(null)
  const [selectedModule, setSelectedModule] = useState<string | null>(null)
  const [selectedSignal, setSelectedSignal] = useState<{ name: string; module?: string } | null>(null)
  const [tab, setTab] = useState<Tab>('module')
  const [graphMode, setGraphMode] = useState<GraphMode>('fanin')
  const [pathDestination, setPathDestination] = useState('')
  const [stats, setStats] = useState<{ nodes: number; edges: number } | null>(null)
  const [connectionError, setConnectionError] = useState(false)

  useEffect(() => {
    rtlgraph.health()
      .then((h) => setStats({ nodes: h.nodes, edges: h.edges }))
      .catch(() => setConnectionError(true))
    rtlgraph.listModules()
      .then((r) => {
        const top = r.modules.find((m) => m.is_top)
        if (top) {
          setTopModule(String(top.name))
          setSelectedModule(String(top.name))
        }
      })
      .catch(() => setConnectionError(true))
  }, [])

  const handleSelectSignal = useCallback((name: string, module?: string) => {
    setSelectedSignal({ name, module })
    setTab('signal')
  }, [])

  const handleSearchSelect = useCallback((node: GraphNode) => {
    if (node.node_type === 'Module') {
      setSelectedModule(String(node.name))
      setTab('module')
    } else if (node.node_type === 'Instance') {
      setSelectedModule(String(node.module_type))
      setTab('module')
    } else {
      handleSelectSignal(String(node.name), node.module ? String(node.module) : undefined)
    }
  }, [handleSelectSignal])

  if (connectionError) {
    return (
      <div className="app-error">
        <h1>RTLGraph</h1>
        <p>Could not reach the API at <code>/api</code>. Is the backend running (<code>uvicorn api.main:app</code>)?</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>RTLGraph</h1>
        <span className="hint">semantic RTL retrieval engine{stats ? ` · ${stats.nodes} nodes · ${stats.edges} edges` : ''}</span>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <SearchBar onSelect={handleSearchSelect} />
          <ModuleBrowser
            selected={selectedModule}
            onSelect={(name) => { setSelectedModule(name); setTab('module') }}
          />
          <HierarchyBrowser
            topModule={topModule}
            onSelectModule={(name) => { setSelectedModule(name); setTab('module') }}
          />
        </aside>
        <main className="main">
          <nav className="tabs">
            <button className={tab === 'module' ? 'active' : ''} onClick={() => setTab('module')}>Module Browser</button>
            <button className={tab === 'signal' ? 'active' : ''} onClick={() => setTab('signal')}>Signal Explorer</button>
            <button className={tab === 'graph' ? 'active' : ''} onClick={() => setTab('graph')}>Dependency Graph</button>
          </nav>

          {tab === 'module' && (
            selectedModule
              ? <ModuleDetailPanel moduleName={selectedModule} onSelectSignal={handleSelectSignal} />
              : <div className="hint">Search or pick a module from the sidebar to get started.</div>
          )}

          {tab === 'signal' && (
            selectedSignal ? (
              <>
                <SignalExplorer
                  signalName={selectedSignal.name}
                  moduleName={selectedSignal.module}
                  onShowFanin={() => { setGraphMode('fanin'); setTab('graph') }}
                  onShowFanout={() => { setGraphMode('fanout'); setTab('graph') }}
                  onSelectSignal={handleSelectSignal}
                />
                <div className="grid-2">
                  <section>
                    <h4>Fan-in Tree</h4>
                    <FaninFanoutTree signalName={selectedSignal.name} moduleName={selectedSignal.module} direction="fanin" onSelectSignal={handleSelectSignal} />
                  </section>
                  <section>
                    <h4>Fan-out Tree</h4>
                    <FaninFanoutTree signalName={selectedSignal.name} moduleName={selectedSignal.module} direction="fanout" onSelectSignal={handleSelectSignal} />
                  </section>
                </div>
              </>
            ) : (
              <SignalPicker
                prompt="No signal selected yet. Search for one, or click a port/signal/register inside Module Browser."
                onSelect={handleSelectSignal}
              />
            )
          )}

          {tab === 'graph' && (
            selectedSignal ? (
              <div className="graph-tab">
                <div className="button-row">
                  <label><input type="radio" checked={graphMode === 'fanin'} onChange={() => setGraphMode('fanin')} /> Fan-in</label>
                  <label><input type="radio" checked={graphMode === 'fanout'} onChange={() => setGraphMode('fanout')} /> Fan-out</label>
                  <label><input type="radio" checked={graphMode === 'path'} onChange={() => setGraphMode('path')} /> Path to…</label>
                  {graphMode === 'path' && (
                    <input
                      type="text"
                      placeholder="destination signal name"
                      value={pathDestination}
                      onChange={(e) => setPathDestination(e.target.value)}
                    />
                  )}
                </div>
                <h3>
                  <span className="mono">{selectedSignal.name}</span>
                  {graphMode !== 'path' ? ` — ${graphMode}` : ` → ${pathDestination || '…'}`}
                </h3>
                <GraphView
                  signalName={selectedSignal.name}
                  moduleName={selectedSignal.module}
                  mode={graphMode}
                  destination={graphMode === 'path' ? pathDestination : undefined}
                  onSelectSignal={handleSelectSignal}
                />
              </div>
            ) : (
              <SignalPicker
                prompt="No signal selected yet. Search for one to visualize its dependency graph."
                onSelect={handleSelectSignal}
              />
            )
          )}
        </main>
      </div>
    </div>
  )
}
