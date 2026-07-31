import { useEffect, useState } from 'react'
import { rtlgraph } from '../api'
import type {
  AlwaysBlocksResponse,
  AssignmentsResponse,
  ClockDomainResponse,
  DriverResponse,
  GraphNode,
  ReceiverResponse,
  ResetTreeResponse,
} from '../types'

interface Props {
  signalName: string
  moduleName?: string
  onShowFanin: () => void
  onShowFanout: () => void
  onSelectSignal: (name: string, module: string) => void
}

function Loc({ node }: { node: GraphNode }) {
  if (!node.loc) return null
  return <span className="loc">{String(node.loc)}</span>
}

export function SignalExplorer({ signalName, moduleName, onShowFanin, onShowFanout, onSelectSignal }: Props) {
  const [signal, setSignal] = useState<GraphNode | null>(null)
  const [driver, setDriver] = useState<DriverResponse | null>(null)
  const [receivers, setReceivers] = useState<ReceiverResponse | null>(null)
  const [clockDomain, setClockDomain] = useState<ClockDomainResponse | null>(null)
  const [resetTree, setResetTree] = useState<ResetTreeResponse | null>(null)
  const [assignments, setAssignments] = useState<AssignmentsResponse | null>(null)
  const [alwaysBlocks, setAlwaysBlocks] = useState<AlwaysBlocksResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setError(null)
    setSignal(null)
    Promise.all([
      rtlgraph.getSignal(signalName, moduleName).then((r) => setSignal(r.matches[0] ?? null)),
      rtlgraph.driver(signalName, moduleName).then(setDriver),
      rtlgraph.receivers(signalName, moduleName).then(setReceivers),
      rtlgraph.signalClockDomain(signalName, moduleName).then(setClockDomain),
      rtlgraph.signalResetTree(signalName, moduleName).then(setResetTree),
      rtlgraph.signalAssignments(signalName, moduleName).then(setAssignments),
      rtlgraph.signalAlwaysBlocks(signalName, moduleName).then(setAlwaysBlocks),
    ]).catch((e) => setError(String(e.message ?? e)))
  }, [signalName, moduleName])

  if (error) return <div className="error">{error}</div>

  return (
    <div className="signal-explorer">
      <h2>
        <span className="mono">{signalName}</span>
        {signal ? <span className={`badge badge-${signal.node_type}`}>{signal.node_type}</span> : null}
        {signal?.module ? <span className="tag">{String(signal.module)}</span> : null}
      </h2>
      {signal?.width ? <div className="hint">width: {String(signal.width)} bit(s)</div> : null}

      <div className="button-row">
        <button onClick={onShowFanin}>Show Fan-in Graph</button>
        <button onClick={onShowFanout}>Show Fan-out Graph</button>
      </div>

      <div className="grid-2">
        <section>
          <h4>Driver Trace</h4>
          {driver && driver.drivers.length === 0 && <div className="hint">no drivers found (primary input?)</div>}
          <ul className="compact-list">
            {driver?.drivers.map((d, idx) => (
              <li key={idx}>
                <span className="tag">{String(d.driver.kind ?? d.driver.node_type)}</span>
                {d.driver.node_type === 'Assignment' ? (
                  <span className="mono">lhs: {(d.driver.lhs as string[] | undefined)?.join(', ')}</span>
                ) : (
                  <span className="mono">{String(d.driver.name)}</span>
                )}
                {d.always_block ? <span className="tag">{String(d.always_block.kind)}</span> : null}
                <Loc node={d.driver} />
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Receivers (fan-out, direct)</h4>
          {receivers && receivers.receivers.length === 0 && <div className="hint">no direct readers found</div>}
          <ul className="compact-list">
            {receivers?.receivers.map((r, idx) => (
              <li key={idx}>
                <span className="tag">{String(r.reader.kind ?? r.reader.node_type)}</span>
                <span className="mono">{r.reader.node_type === 'Port' ? String(r.reader.name) : (r.reader.reads as string[] | undefined)?.join(', ')}</span>
                <Loc node={r.reader} />
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Clock Domain</h4>
          {clockDomain && clockDomain.clock_domains.length === 0 && <div className="hint">not clocked</div>}
          <ul className="compact-list">
            {clockDomain?.clock_domains.map((c) => (
              <li key={c.id}><span className="mono">{String(c.name)}</span></li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Reset Tree</h4>
          {resetTree && resetTree.reset_domains.length === 0 && <div className="hint">no reset</div>}
          <ul className="compact-list">
            {resetTree?.reset_domains.map((r) => (
              <li key={r.id}><span className="mono">{String(r.name)}</span><span className="tag">{String(r.edge)}</span></li>
            ))}
          </ul>
          {resetTree && resetTree.co_reset_registers.length > 0 && (
            <details>
              <summary>{resetTree.co_reset_registers.length} co-reset registers</summary>
              <ul className="compact-list">
                {resetTree.co_reset_registers.slice(0, 40).map((r) => (
                  <li key={r.id} onClick={() => onSelectSignal(String(r.name), String(r.module))}>
                    <span className="mono">{String(r.name)}</span><span className="tag">{String(r.module)}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>

        <section>
          <h4>Assignments</h4>
          <div className="hint">driving: {assignments?.driving_assignments.length ?? 0} · reading: {assignments?.reading_assignments.length ?? 0}</div>
          <ul className="compact-list">
            {assignments?.driving_assignments.map((a) => (
              <li key={a.id}><span className="tag">{String(a.kind)}</span><Loc node={a} /></li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Always Blocks</h4>
          <div className="hint">writing: {alwaysBlocks?.writing_always_blocks.length ?? 0} · reading: {alwaysBlocks?.reading_always_blocks.length ?? 0}</div>
          <ul className="compact-list">
            {alwaysBlocks?.writing_always_blocks.map((a) => (
              <li key={a.id}><span className="tag">{String(a.kind)}</span>{a.clock ? <span className="mono">@{String(a.clock)}</span> : null}<Loc node={a} /></li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
