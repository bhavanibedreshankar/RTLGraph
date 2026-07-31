import { useState } from 'react'
import { rtlgraph } from '../api'
import type { GraphNode } from '../types'

interface Props {
  prompt: string
  onSelect: (name: string, module?: string) => void
}

const SELECTABLE_TYPES = new Set(['Signal', 'Register', 'Port'])

export function SignalPicker({ prompt, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GraphNode[]>([])
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!query.trim()) return
    setError(null)
    try {
      const res = await rtlgraph.search(query.trim())
      const matches = res.results.filter((r) => SELECTABLE_TYPES.has(r.node_type))
      if (matches.length === 0) {
        setError(`No signal/register/port matching "${query}"`)
        setResults([])
        return
      }
      setResults(matches)
    } catch (e) {
      setError(String((e as Error).message ?? e))
    }
  }

  return (
    <div className="signal-picker">
      <p className="hint">{prompt}</p>
      <div className="button-row">
        <input
          type="text"
          placeholder="signal, register, or port name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && run()}
        />
        <button onClick={run}>Find</button>
      </div>
      {error && <div className="error">{error}</div>}
      {results.length > 0 && (
        <ul className="result-list">
          {results.map((r) => (
            <li key={r.id} onClick={() => onSelect(String(r.name), r.module ? String(r.module) : undefined)}>
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
