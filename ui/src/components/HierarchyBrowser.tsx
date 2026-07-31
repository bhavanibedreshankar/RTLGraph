import { useEffect, useState } from 'react'
import { rtlgraph } from '../api'
import type { HierarchyInstance, HierarchyNode } from '../types'

interface Props {
  topModule: string | null
  onSelectModule: (name: string) => void
}

function InstanceRow({ entry, onSelectModule, depth }: { entry: HierarchyInstance; onSelectModule: (n: string) => void; depth: number }) {
  const [open, setOpen] = useState(depth < 1)
  const child = entry.child
  const hasChildren = !!child && child.instances.length > 0

  return (
    <div className="tree-row" style={{ paddingLeft: depth * 14 }}>
      <div className="tree-row-line">
        {hasChildren ? (
          <span className="tree-toggle" onClick={() => setOpen(!open)}>{open ? '▾' : '▸'}</span>
        ) : (
          <span className="tree-toggle tree-toggle-leaf">·</span>
        )}
        <span className="tree-instance-name">{String(entry.instance.name)}</span>
        <span
          className="tree-module-type"
          onClick={() => onSelectModule(String(entry.instance.module_type))}
        >
          {String(entry.instance.module_type)}
        </span>
      </div>
      {open && child && (
        <div>
          {child.instances.map((childEntry, idx) => (
            <InstanceRow key={idx} entry={childEntry} onSelectModule={onSelectModule} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export function HierarchyBrowser({ topModule, onSelectModule }: Props) {
  const [tree, setTree] = useState<HierarchyNode | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!topModule) return
    rtlgraph.moduleHierarchy(topModule, 6).then(setTree).catch((e) => setError(String(e)))
  }, [topModule])

  if (!topModule) return null

  return (
    <div className="panel hierarchy-browser">
      <h3>Hierarchy</h3>
      {error && <div className="error">{error}</div>}
      {tree && (
        <div className="tree-root">
          <div className="tree-row-line tree-root-line" onClick={() => onSelectModule(String(tree.module.name))}>
            <span className="tree-instance-name">{String(tree.module.name)}</span>
          </div>
          {tree.instances.map((entry, idx) => (
            <InstanceRow key={idx} entry={entry} onSelectModule={onSelectModule} depth={1} />
          ))}
        </div>
      )}
    </div>
  )
}
