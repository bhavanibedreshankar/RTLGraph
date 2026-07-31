import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { useEffect, useRef, useState } from 'react'
import { rtlgraph } from '../api'
import type { ConeEntry } from '../types'

cytoscape.use(dagre)

interface Props {
  signalName: string
  moduleName?: string
  mode: 'fanin' | 'fanout' | 'path'
  destination?: string
  onSelectSignal: (name: string, module: string) => void
}

const NODE_COLORS: Record<string, string> = {
  Signal: '#5aa9e6',
  Register: '#e6a15a',
  Port: '#6bbf7a',
  Module: '#9b8ce6',
  Instance: '#e65a8f',
  Assignment: '#888888',
}

export function GraphView({ signalName, moduleName, mode, destination, onSelectSignal }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [error, setError] = useState<string | null>(null)
  const [count, setCount] = useState<{ nodes: number; edges: number } | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)

    async function load() {
      const elements: cytoscape.ElementDefinition[] = []
      const nodeIds = new Set<string>()

      function addNode(id: string, label: string, type: string, root: boolean) {
        if (nodeIds.has(id)) return
        nodeIds.add(id)
        elements.push({ data: { id, label, type }, classes: root ? 'root' : type })
      }

      try {
        if (mode === 'path') {
          if (!destination) {
            setError('pick a destination signal to trace a dependency path')
            return
          }
          const res = await rtlgraph.path(signalName, destination, moduleName)
          if (cancelled) return
          if (!res.found) {
            setError('no path found between these signals')
            return
          }
          res.path.forEach((n, idx) => addNode(n.id, String(n.name), n.node_type, idx === 0 || idx === res.path.length - 1))
          for (let i = 0; i < res.path.length - 1; i++) {
            elements.push({ data: { id: `e${i}`, source: res.path[i].id, target: res.path[i + 1].id } })
          }
        } else {
          const res = mode === 'fanin'
            ? await rtlgraph.fanin(signalName, moduleName, 5)
            : await rtlgraph.fanout(signalName, moduleName, 5)
          if (cancelled) return
          const rootId = res.signal.id
          addNode(rootId, String(res.signal.name), res.signal.node_type, true)
          const entries: ConeEntry[] = (mode === 'fanin' ? res.fanin : res.fanout) ?? []
          for (const e of entries) {
            addNode(e.node.id, String(e.node.name), e.node.node_type, false)
          }
          // We don't have explicit parent links from the cone API (BFS
          // distances only), so approximate edges by distance adjacency for
          // visualization -- an exact edge list is available via /path for
          // any specific pair.
          const byDistance = new Map<number, string[]>()
          byDistance.set(0, [rootId])
          for (const e of entries) {
            if (!byDistance.has(e.distance)) byDistance.set(e.distance, [])
            byDistance.get(e.distance)!.push(e.node.id)
          }
          const distances = [...byDistance.keys()].sort((a, b) => a - b)
          for (let i = 1; i < distances.length; i++) {
            const prevLevel = byDistance.get(distances[i - 1])!
            const curLevel = byDistance.get(distances[i])!
            curLevel.forEach((id, idx) => {
              const parent = prevLevel[idx % prevLevel.length]
              elements.push({ data: { id: `e_${parent}_${id}`, source: mode === 'fanin' ? id : parent, target: mode === 'fanin' ? parent : id } })
            })
          }
        }
      } catch (e) {
        if (!cancelled) setError(String((e as Error).message ?? e))
        return
      }

      if (cancelled || !containerRef.current) return
      setCount({ nodes: elements.filter((e) => !('source' in e.data)).length, edges: elements.filter((e) => 'source' in e.data).length })

      cyRef.current?.destroy()
      const cy = cytoscape({
        container: containerRef.current,
        elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': (ele: cytoscape.NodeSingular) => NODE_COLORS[ele.data('type')] || '#999',
              label: 'data(label)',
              'font-size': 9,
              color: '#eee',
              'text-outline-width': 1,
              'text-outline-color': '#222',
              width: 22,
              height: 22,
            },
          },
          { selector: 'node.root', style: { width: 34, height: 34, 'border-width': 3, 'border-color': '#fff' } },
          {
            selector: 'edge',
            style: {
              width: 1.5,
              'line-color': '#666',
              'target-arrow-color': '#666',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
            },
          },
        ],
        layout: { name: 'dagre', rankDir: mode === 'fanin' ? 'LR' : 'RL', nodeSep: 20, rankSep: 60 } as unknown as cytoscape.LayoutOptions,
      })
      cy.on('tap', 'node', (evt) => {
        const d = evt.target.data()
        const idParts = String(d.id).split(':')[1]?.split('.')
        const mod = idParts && idParts.length > 1 ? idParts[0] : moduleName
        onSelectSignal(d.label, mod ?? '')
      })
      cyRef.current = cy
    }

    load()
    return () => {
      cancelled = true
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [signalName, moduleName, mode, destination, onSelectSignal])

  return (
    <div className="graph-view">
      {error && <div className="error">{error}</div>}
      {count && <div className="hint">{count.nodes} nodes · {count.edges} edges</div>}
      <div ref={containerRef} className="cytoscape-canvas" />
    </div>
  )
}
