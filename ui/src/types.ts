export type NodeType =
  | 'Module'
  | 'Instance'
  | 'Signal'
  | 'Register'
  | 'Port'
  | 'Parameter'
  | 'Expression'
  | 'Assignment'
  | 'AlwaysBlock'
  | 'ClockDomain'
  | 'ResetDomain'

export interface GraphNode {
  id: string
  node_type: NodeType
  name?: string
  module?: string
  [key: string]: unknown
}

export interface ModuleDetail extends GraphNode {
  ports: GraphNode[]
  signals: GraphNode[]
  registers: GraphNode[]
  parameters: GraphNode[]
  instances: GraphNode[]
  always_blocks: GraphNode[]
}

export interface SearchResponse {
  query: string
  results: GraphNode[]
}

export interface SignalResponse {
  matches: GraphNode[]
}

export interface DriverEntry {
  driver: GraphNode
  always_block?: GraphNode | null
  via_pin?: string | null
}

export interface DriverResponse {
  signal: GraphNode
  drivers: DriverEntry[]
}

export interface ReceiverEntry {
  reader: GraphNode
  always_block?: GraphNode | null
  via_pin?: string | null
  kind?: string
}

export interface ReceiverResponse {
  signal: GraphNode
  receivers: ReceiverEntry[]
}

export interface ConeEntry {
  node: GraphNode
  distance: number
}

export interface ConeResponse {
  signal: GraphNode
  fanin?: ConeEntry[]
  fanout?: ConeEntry[]
}

export interface PathResponse {
  source: GraphNode
  destination: GraphNode
  found: boolean
  path: GraphNode[]
  length: number | null
  note?: string
}

export interface HierarchyInstance {
  instance: GraphNode
  child?: HierarchyNode & { truncated?: string }
}

export interface HierarchyNode {
  module: GraphNode
  instances: HierarchyInstance[]
}

export interface RegistersResponse {
  module: string
  registers: GraphNode[]
}

export interface AssignmentsResponse {
  signal: GraphNode
  driving_assignments: GraphNode[]
  reading_assignments: GraphNode[]
}

export interface AlwaysBlocksResponse {
  signal: GraphNode
  writing_always_blocks: GraphNode[]
  reading_always_blocks: GraphNode[]
}

export interface ClockDomainResponse {
  signal: GraphNode
  clock_domains: GraphNode[]
}

export interface ResetTreeResponse {
  signal: GraphNode
  reset_domains: GraphNode[]
  co_reset_registers: GraphNode[]
}

export interface ModuleListResponse {
  modules: GraphNode[]
}
