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

// Each section fetches independently: a failure or slow response in one
// (e.g. driver trace) must not blank the sections that already loaded fine.
type Loadable<T> = { status: 'loading' } | { status: 'error' } | { status: 'ok'; data: T }

function useLoadable<T>(fetcher: () => Promise<T>, deps: unknown[]): Loadable<T> {
  const [state, setState] = useState<Loadable<T>>({ status: 'loading' })
  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetcher()
      .then((data) => { if (!cancelled) setState({ status: 'ok', data }) })
      .catch(() => { if (!cancelled) setState({ status: 'error' }) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

function SectionStatus({ state }: { state: Loadable<unknown> }) {
  if (state.status === 'loading') return <div className="hint">loading…</div>
  if (state.status === 'error') return <div className="error">failed to load</div>
  return null
}

function Loc({ node }: { node: GraphNode }) {
  if (!node.loc) return null
  return <span className="loc">{String(node.loc)}</span>
}

export function SignalExplorer({ signalName, moduleName, onShowFanin, onShowFanout, onSelectSignal }: Props) {
  const signalState = useLoadable(() => rtlgraph.getSignal(signalName, moduleName), [signalName, moduleName])
  const driverState = useLoadable(() => rtlgraph.driver(signalName, moduleName), [signalName, moduleName])
  const receiversState = useLoadable(() => rtlgraph.receivers(signalName, moduleName), [signalName, moduleName])
  const clockDomainState = useLoadable(() => rtlgraph.signalClockDomain(signalName, moduleName), [signalName, moduleName])
  const resetTreeState = useLoadable(() => rtlgraph.signalResetTree(signalName, moduleName), [signalName, moduleName])
  const assignmentsState = useLoadable(() => rtlgraph.signalAssignments(signalName, moduleName), [signalName, moduleName])
  const alwaysBlocksState = useLoadable(() => rtlgraph.signalAlwaysBlocks(signalName, moduleName), [signalName, moduleName])

  const signal = signalState.status === 'ok' ? signalState.data.matches[0] ?? null : null
  const driver: DriverResponse | null = driverState.status === 'ok' ? driverState.data : null
  const receivers: ReceiverResponse | null = receiversState.status === 'ok' ? receiversState.data : null
  const clockDomain: ClockDomainResponse | null = clockDomainState.status === 'ok' ? clockDomainState.data : null
  const resetTree: ResetTreeResponse | null = resetTreeState.status === 'ok' ? resetTreeState.data : null
  const assignments: AssignmentsResponse | null = assignmentsState.status === 'ok' ? assignmentsState.data : null
  const alwaysBlocks: AlwaysBlocksResponse | null = alwaysBlocksState.status === 'ok' ? alwaysBlocksState.data : null

  return (
    <div className="signal-explorer">
      <h2>
        <span className="mono">{signalName}</span>
        {signal ? <span className={`badge badge-${signal.node_type}`}>{signal.node_type}</span> : null}
        {signal?.module ? <span className="tag">{String(signal.module)}</span> : null}
      </h2>
      {signal?.width ? <div className="hint">width: {String(signal.width)} bit(s)</div> : null}
      {signalState.status === 'error' && <div className="error">failed to load signal details</div>}

      <div className="button-row">
        <button onClick={onShowFanin}>Show Fan-in Graph</button>
        <button onClick={onShowFanout}>Show Fan-out Graph</button>
      </div>

      <div className="grid-2">
        <section>
          <h4>Driver Trace</h4>
          <SectionStatus state={driverState} />
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
          <SectionStatus state={receiversState} />
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
          <SectionStatus state={clockDomainState} />
          {clockDomain && clockDomain.clock_domains.length === 0 && <div className="hint">not clocked</div>}
          <ul className="compact-list">
            {clockDomain?.clock_domains.map((c) => (
              <li key={c.id}><span className="mono">{String(c.name)}</span></li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Reset Tree</h4>
          <SectionStatus state={resetTreeState} />
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
          <SectionStatus state={assignmentsState} />
          {assignments && (
            <div className="hint">driving: {assignments.driving_assignments.length} · reading: {assignments.reading_assignments.length}</div>
          )}
          <ul className="compact-list">
            {assignments?.driving_assignments.map((a) => (
              <li key={a.id}><span className="tag">{String(a.kind)}</span><Loc node={a} /></li>
            ))}
          </ul>
        </section>

        <section>
          <h4>Always Blocks</h4>
          <SectionStatus state={alwaysBlocksState} />
          {alwaysBlocks && (
            <div className="hint">writing: {alwaysBlocks.writing_always_blocks.length} · reading: {alwaysBlocks.reading_always_blocks.length}</div>
          )}
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
