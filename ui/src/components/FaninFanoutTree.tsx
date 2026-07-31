import { useEffect, useState } from 'react'
import { rtlgraph } from '../api'
import type { ConeEntry, ConeResponse } from '../types'

interface Props {
  signalName: string
  moduleName?: string
  direction: 'fanin' | 'fanout'
  onSelectSignal: (name: string, module: string) => void
}

export function FaninFanoutTree({ signalName, moduleName, direction, onSelectSignal }: Props) {
  const [data, setData] = useState<ConeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [maxDepth, setMaxDepth] = useState(4)

  useEffect(() => {
    setError(null)
    const fn = direction === 'fanin' ? rtlgraph.fanin : rtlgraph.fanout
    fn(signalName, moduleName, maxDepth).then(setData).catch((e) => setError(String(e.message ?? e)))
  }, [signalName, moduleName, direction, maxDepth])

  if (error) return <div className="error">{error}</div>
  if (!data) return <div className="hint">loading…</div>

  const entries: ConeEntry[] = (direction === 'fanin' ? data.fanin : data.fanout) ?? []
  const byLevel = new Map<number, ConeEntry[]>()
  for (const e of entries) {
    if (!byLevel.has(e.distance)) byLevel.set(e.distance, [])
    byLevel.get(e.distance)!.push(e)
  }
  const levels = [...byLevel.keys()].sort((a, b) => a - b)

  return (
    <div className="cone-tree">
      <div className="button-row">
        <label>
          Depth:{' '}
          <select value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))}>
            {[1, 2, 3, 4, 6, 10].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <span className="hint">{entries.length} node(s) reachable</span>
      </div>
      {levels.length === 0 && <div className="hint">no {direction} signals found</div>}
      {levels.map((level) => (
        <div key={level} className="cone-level">
          <div className="cone-level-label">distance {level}</div>
          <ul className="compact-list">
            {byLevel.get(level)!.map((e) => (
              <li key={e.node.id} onClick={() => onSelectSignal(String(e.node.name), String(e.node.module))} style={{ paddingLeft: Math.min(level, 6) * 10 }}>
                <span className={`badge badge-${e.node.node_type}`}>{e.node.node_type}</span>
                <span className="mono">{String(e.node.name)}</span>
                <span className="tag">{String(e.node.module)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
