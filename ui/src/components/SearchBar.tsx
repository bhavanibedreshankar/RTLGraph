import { useEffect, useRef, useState } from 'react'
import { rtlgraph } from '../api'
import type { GraphNode } from '../types'

interface Props {
  onSelect: (node: GraphNode) => void
}

const DEBOUNCE_MS = 200

export function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GraphNode[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const requestId = useRef(0)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      setTotal(0)
      setLoading(false)
      return
    }
    setLoading(true)
    const id = ++requestId.current
    const timer = setTimeout(() => {
      rtlgraph.search(q)
        .then((res) => {
          // Ignore stale responses from a query that's since been superseded.
          if (id !== requestId.current) return
          setResults(res.results)
          setTotal(res.total)
        })
        .catch(() => {
          if (id !== requestId.current) return
          setResults([])
          setTotal(0)
        })
        .finally(() => {
          if (id !== requestId.current) return
          setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query])

  return (
    <div className="panel search-bar">
      <input
        type="text"
        placeholder="Search modules, instances, signals, registers, ports..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading && <div className="hint">searching…</div>}
      {!loading && results.length > 0 && (
        <ul className="result-list">
          {results.map((r) => (
            <li key={r.id} onClick={() => { onSelect(r); setResults([]); setTotal(0); setQuery('') }}>
              <span className={`badge badge-${r.node_type}`}>{r.node_type}</span>
              <span className="result-name">{String(r.name)}</span>
              {r.module ? <span className="result-module">{String(r.module)}</span> : null}
            </li>
          ))}
          {total > results.length && (
            <li className="result-more hint">+{total - results.length} more — refine your search to see them</li>
          )}
        </ul>
      )}
    </div>
  )
}
