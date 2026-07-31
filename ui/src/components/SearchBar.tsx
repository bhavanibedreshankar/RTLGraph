import { useState } from 'react'
import { rtlgraph } from '../api'
import type { GraphNode } from '../types'

interface Props {
  onSelect: (node: GraphNode) => void
}

export function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GraphNode[]>([])
  const [loading, setLoading] = useState(false)

  async function runSearch(q: string) {
    setQuery(q)
    if (q.trim().length < 2) {
      setResults([])
      return
    }
    setLoading(true)
    try {
      const res = await rtlgraph.search(q.trim())
      setResults(res.results)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel search-bar">
      <input
        type="text"
        placeholder="Search modules, instances, signals, registers, ports..."
        value={query}
        onChange={(e) => runSearch(e.target.value)}
      />
      {loading && <div className="hint">searching…</div>}
      {results.length > 0 && (
        <ul className="result-list">
          {results.map((r) => (
            <li key={r.id} onClick={() => { onSelect(r); setResults([]); setQuery('') }}>
              <span className={`badge badge-${r.node_type}`}>{r.node_type}</span>
              <span className="result-name">{String(r.name)}</span>
              {r.module ? <span className="result-module">{String(r.module)}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
