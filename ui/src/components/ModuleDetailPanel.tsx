import { useEffect, useState } from 'react'
import { rtlgraph } from '../api'
import type { GraphNode, ModuleDetail } from '../types'

interface Props {
  moduleName: string
  onSelectSignal: (name: string, module: string) => void
}

function Loc({ node }: { node: GraphNode }) {
  if (!node.loc) return null
  return <span className="loc">{String(node.loc)}</span>
}

function NameList({ items, module, onSelectSignal, showDir }: { items: GraphNode[]; module: string; onSelectSignal: (n: string, m: string) => void; showDir?: boolean }) {
  if (items.length === 0) return <div className="hint">none</div>
  return (
    <ul className="compact-list">
      {items.map((it) => (
        <li key={it.id} onClick={() => onSelectSignal(String(it.name), module)}>
          <span className="mono">{String(it.name)}</span>
          {showDir && it.direction ? <span className="tag">{String(it.direction)}</span> : null}
          {it.width ? <span className="tag">[{String(it.width)}]</span> : null}
        </li>
      ))}
    </ul>
  )
}

export function ModuleDetailPanel({ moduleName, onSelectSignal }: Props) {
  const [detail, setDetail] = useState<ModuleDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDetail(null)
    rtlgraph.getModule(moduleName).then(setDetail).catch((e) => setError(String(e)))
  }, [moduleName])

  if (error) return <div className="error">{error}</div>
  if (!detail) return <div className="hint">loading…</div>

  return (
    <div className="module-detail">
      <h2>{detail.name} {detail.is_top ? <span className="top-badge">TOP</span> : null}</h2>
      <div className="grid-2">
        <section>
          <h4>Ports ({detail.ports.length})</h4>
          <NameList items={detail.ports} module={moduleName} onSelectSignal={onSelectSignal} showDir />
        </section>
        <section>
          <h4>Registers ({detail.registers.length})</h4>
          <NameList items={detail.registers} module={moduleName} onSelectSignal={onSelectSignal} />
        </section>
        <section>
          <h4>Signals ({detail.signals.length})</h4>
          <NameList items={detail.signals} module={moduleName} onSelectSignal={onSelectSignal} />
        </section>
        <section>
          <h4>Parameters ({detail.parameters.length})</h4>
          <ul className="compact-list">
            {detail.parameters.map((p) => (
              <li key={p.id}><span className="mono">{String(p.name)}</span><span className="tag">{String(p.value_text ?? '')}</span></li>
            ))}
          </ul>
        </section>
        <section>
          <h4>Instances ({detail.instances.length})</h4>
          <ul className="compact-list">
            {detail.instances.map((i) => (
              <li key={i.id}><span className="mono">{String(i.name)}</span><span className="tag">{String(i.module_type)}</span></li>
            ))}
          </ul>
        </section>
        <section>
          <h4>Always Blocks ({detail.always_blocks.length})</h4>
          <ul className="compact-list">
            {detail.always_blocks.map((a) => {
              const writes = a.writes as string[] | undefined
              const target = writes?.[0]
              return (
                <li
                  key={a.id}
                  onClick={target ? () => onSelectSignal(target, moduleName) : undefined}
                  className={target ? undefined : 'not-clickable'}
                >
                  <span className="tag">{String(a.kind)}</span>
                  {a.clock ? <span className="mono">@{String(a.clock)}</span> : null}
                  <span className="mono">{writes && writes.length > 0 ? `writes: ${writes.join(', ')}` : ''}</span>
                  <Loc node={a} />
                </li>
              )
            })}
          </ul>
        </section>
      </div>
    </div>
  )
}
