import { useEffect, useState } from 'react'
import { rtlgraph } from '../api'
import type { GraphNode } from '../types'

interface Props {
  selected: string | null
  onSelect: (name: string) => void
}

export function ModuleBrowser({ selected, onSelect }: Props) {
  const [modules, setModules] = useState<GraphNode[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    rtlgraph.listModules().then((r) => setModules(r.modules)).catch((e) => setError(String(e)))
  }, [])

  return (
    <div className="panel module-browser">
      <h3>Modules</h3>
      {error && <div className="error">{error}</div>}
      <ul className="module-list">
        {modules.map((m) => (
          <li
            key={m.id}
            className={selected === m.name ? 'active' : ''}
            onClick={() => onSelect(String(m.name))}
          >
            {m.is_top ? <span className="top-badge">TOP</span> : null}
            {String(m.name)}
          </li>
        ))}
      </ul>
    </div>
  )
}
