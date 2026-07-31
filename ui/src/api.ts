import type {
  AlwaysBlocksResponse,
  AssignmentsResponse,
  ClockDomainResponse,
  ConeResponse,
  DriverResponse,
  HierarchyNode,
  ModuleDetail,
  ModuleListResponse,
  PathResponse,
  ReceiverResponse,
  RegistersResponse,
  ResetTreeResponse,
  SearchResponse,
  SignalResponse,
} from './types'

const BASE = '/api'

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  }
  const url = `${BASE}${path}${qs.toString() ? `?${qs.toString()}` : ''}`
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const rtlgraph = {
  health: () => get<{ status: string; nodes: number; edges: number }>('/health'),
  stats: () => get<{ node_counts: Record<string, number>; edge_counts: Record<string, number> }>('/stats'),
  search: (q: string) => get<SearchResponse>('/search', { q }),
  listModules: () => get<ModuleListResponse>('/module/list'),
  getModule: (name: string) => get<ModuleDetail>('/module', { name }),
  moduleHierarchy: (name: string, max_depth?: number) => get<HierarchyNode>('/module/hierarchy', { name, max_depth }),
  moduleRegisters: (name: string) => get<RegistersResponse>('/module/registers', { name }),
  getSignal: (name: string, module?: string) => get<SignalResponse>('/signal', { name, module }),
  signalAssignments: (name: string, module?: string) => get<AssignmentsResponse>('/signal/assignments', { name, module }),
  signalAlwaysBlocks: (name: string, module?: string) => get<AlwaysBlocksResponse>('/signal/always-blocks', { name, module }),
  signalClockDomain: (name: string, module?: string) => get<ClockDomainResponse>('/signal/clock-domain', { name, module }),
  signalResetTree: (name: string, module?: string) => get<ResetTreeResponse>('/signal/reset-tree', { name, module }),
  driver: (signal: string, module?: string) => get<DriverResponse>('/driver', { signal, module }),
  receivers: (signal: string, module?: string) => get<ReceiverResponse>('/receivers', { signal, module }),
  fanin: (signal: string, module?: string, max_depth?: number) => get<ConeResponse>('/fanin', { signal, module, max_depth }),
  fanout: (signal: string, module?: string, max_depth?: number) => get<ConeResponse>('/fanout', { signal, module, max_depth }),
  path: (source: string, destination: string, module?: string) => get<PathResponse>('/path', { source, destination, module }),
}
