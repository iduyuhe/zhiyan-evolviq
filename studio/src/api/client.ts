// API基地址：开发模式通过Vite代理(/api→local), 生产模式指向远程服务器
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export interface Session {
  session_id: string;
  status: string;
  plan?: string;
  result?: ExecutionResult;
  feedback?: string;
}

export interface SupplyChainMetrics {
  kitting_rate_before: number;
  kitting_rate_after: number;
  improvement_pp: number;
  risk_items_before: number;
  risk_items_after: number;
  shortage_qty_before: number;
  shortage_qty_after: number;
  delivery_accuracy_before: number;
  delivery_accuracy_after: number;
  delivery_improvement_pp: number;
  roi_summary: string;
}

export interface ExecutionResult {
  status: string;
  summary: string;
  bom: string;
  completeness_pct: number;
  // T3: 齐套率/交期 ROI 闭环（可演示 MVP 门面）
  metrics?: SupplyChainMetrics;
  agent?: string;
  check_details: CheckDetail[];
  actions_taken: Action[];
  alternatives_found: Alternative[];
  warning: string[];
  // AI 决策辅助（L2 推理层下沉到执行阶段）；无 LLM 时为 null
  ai_insight?: string | null;
  ai_insight_source?: 'llm' | 'none';
}

export interface CheckDetail {
  material: string;
  name: string;
  required: number;
  available: number;
  shortage: number;
  risk: string;
  alternative: string | null;
  // T3: before/after 双值（ROI 闭环）
  available_before?: number;
  available_after?: number;
  shortage_before?: number;
  shortage_after?: number;
  risk_before?: string;
  risk_after?: string;
}

export interface Action {
  type: string;
  material: string;
  name?: string;
  alternative: string;
  qty: number;
  status: string;
  note?: string;
}

export interface Alternative {
  material: string;
  name: string;
  alternatives: { code: string; name: string; price: number; supplier: string }[];
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
}

export async function healthCheck(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function createSession(goal: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveSession(sessionId: string, approved: boolean, feedback?: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, feedback }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function interveneSession(sessionId: string, action: string, newGoal?: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/intervene`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, new_goal: newGoal }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function riskColor(risk: string): string {
  switch (risk) {
    case 'low': return 'badge-green';
    case 'medium': return 'badge-yellow';
    case 'high':
    case 'critical': return 'badge-red';
    default: return 'badge-blue';
  }
}

// ============ 企业控制台（模块四）API ============

export interface AuthBoundary {
  id: string;
  name: string;
  agent: string;
  allowed_categories: string[];
  price_tolerance_pct: number;
  max_lock_qty: number;
  confidence_threshold: number;
  auto_execute_actions: string[];
  require_approval_actions: string[];
  max_daily_autonomous: number;
  enabled: boolean;
}

export interface Intervention {
  id: string;
  session_id: string;
  agent: string;
  action: { type: string; category: string; qty: number; confidence: number; detail: string };
  reason: string;
  boundary_id: string;
  status: string;
  created_at: string;
}

export interface EffectReport {
  sessions: number;
  total_actions: number;
  auto_actions: number;
  human_actions: number;
  autonomous_rate: number;
  time_saved_hours: number;
  intervention_accuracy: number;
  meets_target: boolean;
  target_autonomous_rate: number;
}

export async function getBoundaries(): Promise<AuthBoundary[]> {
  const res = await fetch(`${API_BASE}/auth/boundaries`);
  if (!res.ok) throw new Error(await res.text());
  const d = await res.json();
  return d.boundaries || [];
}

export async function patchBoundary(id: string, patch: Partial<AuthBoundary>): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/boundaries/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getInterventions(status?: string): Promise<{ interventions: Intervention[]; pending: number }> {
  const url = status ? `${API_BASE}/interventions?status=${status}` : `${API_BASE}/interventions`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  const d = await res.json();
  return { interventions: d.interventions || [], pending: d.pending || 0 };
}

export async function decideIntervention(id: string, approved: boolean, note: string): Promise<void> {
  const res = await fetch(`${API_BASE}/interventions/${id}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, note }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getEffectReport(): Promise<EffectReport> {
  const res = await fetch(`${API_BASE}/reports/effect`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function riskIcon(risk: string): string {
  switch (risk) {
    case 'low': return '✅';
    case 'medium': return '🟡';
    case 'high': return '🟠';
    case 'critical': return '🔴';
    default: return '⚪';
  }
}

// ============ 知识图谱（V1-1）API ============

export interface KgStats {
  mode: string;
  available: boolean;
  total_nodes: number;
  total_edges: number;
  nodes_by_label: Record<string, number>;
  edges_by_type: Record<string, number>;
}

export interface KgNode {
  id: string;
  labels: string[];
  props: Record<string, unknown>;
}

export interface KgNeighbor {
  id: string;
  labels: string[];
  props: Record<string, unknown>;
  edge_type: string;
  edge_props: Record<string, unknown>;
}

export async function getKgStats(): Promise<KgStats> {
  const res = await fetch(`${API_BASE}/kg/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function queryKg(params: {
  label?: string;
  node_id?: string;
  edge?: string;
  direction?: string;
  category?: string;
  name?: string;
}): Promise<{ label?: string; node_id?: string; nodes?: KgNode[]; neighbors?: KgNeighbor[]; hint?: string }> {
  const qs = new URLSearchParams();
  if (params.label) qs.set('label', params.label);
  if (params.node_id) qs.set('node_id', params.node_id);
  if (params.edge) qs.set('edge', params.edge);
  if (params.direction) qs.set('direction', params.direction);
  if (params.category) qs.set('category', params.category);
  if (params.name) qs.set('name', params.name);
  const res = await fetch(`${API_BASE}/kg/query?${qs.toString()}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function rebuildKg(): Promise<{ mode: string; stats: KgStats }> {
  const res = await fetch(`${API_BASE}/kg/rebuild`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ 策略调参（V1-4）API ============

export interface StrategyKnob {
  boundary_id: string;
  agent: string;
  name: string;
  confidence_threshold: number;
  price_tolerance_pct: number;
  max_lock_qty: number;
  max_daily_autonomous: number;
  auto_execute_actions: string[];
  require_approval_actions: string[];
  enabled: boolean;
}

export interface EffectSignal {
  autonomous_rate: number;
  total_actions: number;
  auto_actions: number;
  interventions_approved: number;
  interventions_rejected: number;
  interventions_pending: number;
  intervention_approval_rate: number | null;
  sample_size: number;
}

export interface StrategySuggestion {
  id: string;
  agent: string;
  boundary_id: string;
  param: string;
  current: number;
  suggested: number;
  direction: string; // widen / tighten
  rationale: string;
  expected_effect: string;
}

export interface StrategyPanel {
  current: StrategyKnob[];
  effect_signals: Record<string, EffectSignal>;
  suggestions: StrategySuggestion[];
}

export interface StrategyHistoryEntry {
  ts: string;
  agent: string;
  boundary_id: string;
  param: string;
  old: number;
  new: number;
  reason: string;
  basis: string;
}

export async function getStrategyPanel(): Promise<StrategyPanel> {
  const res = await fetch(`${API_BASE}/strategy`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getStrategySuggestions(): Promise<{
  target_autonomous_rate: number;
  suggestions: StrategySuggestion[];
}> {
  const res = await fetch(`${API_BASE}/strategy/suggestions`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function tuneStrategy(req: {
  agent: string;
  param: string;
  value: number;
  reason?: string;
}): Promise<{ status: string; agent: string; param: string; old: number; new: number }> {
  const res = await fetch(`${API_BASE}/strategy/tune`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getStrategyHistory(): Promise<{ history: StrategyHistoryEntry[]; total: number }> {
  const res = await fetch(`${API_BASE}/strategy/history`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ 工业协议网关（V1-3）API ============

export interface GatewayHealth {
  name: string;
  running: boolean;
  poll_interval: number;
  mode?: string;
  endpoint?: string;
  broker?: string;
  connected?: boolean;
  nodes_monitored?: number;
  subscribed_topics?: number;
  error?: string;
}

export interface GatewayOverview {
  total: number;
  ready: number;
  initialized: boolean;
  modes: Record<string, number>;
  gateways: Record<string, GatewayHealth>;
}

export interface GatewayReadPoint {
  tag: string;
  value: number | string | boolean | Record<string, unknown>;
  timestamp: number;
  quality: string;
}

export interface GatewayReadResult {
  gateway: string;
  address: string;
  count: number;
  points: GatewayReadPoint[];
}

export async function getGateways(): Promise<GatewayOverview> {
  const res = await fetch(`${API_BASE}/gateways`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function readGateway(name: string, address = '*', count = 8): Promise<GatewayReadResult> {
  const res = await fetch(`${API_BASE}/gateways/${name}/read`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address, count }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
