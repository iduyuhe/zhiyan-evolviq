// API基地址：开发模式通过Vite代理(/api→local), 生产模式指向远程服务器
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

// ============ 多租户：当前租户 Key（由 TenantContext 注入） ============
// 所有受租户隔离的接口都会自动在请求头带上 X-Tenant-Key；
// 为 null 时后端回退到 default 租户（向后兼容）。
let _tenantKey: string | null = null;
export function setTenantKey(key: string | null): void {
  _tenantKey = key;
}
export function getTenantKey(): string | null {
  return _tenantKey;
}
function authHeaders(extra?: Record<string, string>, key?: string | null): Record<string, string> {
  // key 为 undefined → 使用全局激活租户 _tenantKey；为 null → 显式匿名（default）；为字符串 → 临时指定某个租户 Key
  const effectiveKey = key === undefined ? _tenantKey : key;
  return {
    'Content-Type': 'application/json',
    ...(effectiveKey ? { 'X-Tenant-Key': effectiveKey } : {}),
    ...(extra ?? {}),
  };
}

export interface Session {
  session_id: string;
  status: string;
  plan?: string;
  result?: ExecutionResult;
  feedback?: string;
  tenant_id?: string;
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
    headers: authHeaders(),
    body: JSON.stringify({ goal }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveSession(sessionId: string, approved: boolean, feedback?: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/approve`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ approved, feedback }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function interveneSession(sessionId: string, action: string, newGoal?: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/intervene`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ action, new_goal: newGoal }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function quickCheck(goal: string): Promise<{ result: ExecutionResult }> {
  const res = await fetch(`${API_BASE}/sessions/quick-check`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ goal }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ 隔离演示专用：允许临时指定租户 Key 调用 ============
// 用于「跨租户隔离演示」——用主体/对照两个租户各自的 Key 调用，验证相互不可见。

export interface SessionSummary {
  session_id: string;
  tenant_id: string;
  goal: string;
  status: string;
  completeness: number | null;
}

export interface SessionList {
  tenant_id: string;
  sessions: SessionSummary[];
  total: number;
}

export async function listSessions(key?: string | null): Promise<SessionList> {
  const res = await fetch(`${API_BASE}/sessions`, { headers: authHeaders(undefined, key) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function quickCheckWithKey(
  goal: string,
  key?: string | null,
): Promise<{ tenant_id: string; session_id: string; status: string; result: ExecutionResult }> {
  const res = await fetch(`${API_BASE}/sessions/quick-check`, {
    method: 'POST',
    headers: authHeaders(undefined, key),
    body: JSON.stringify({ goal }),
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
  tenant_id?: string;
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
  const res = await fetch(`${API_BASE}/auth/boundaries`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  const d = await res.json();
  return d.boundaries || [];
}

export async function patchBoundary(id: string, patch: Partial<AuthBoundary>): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/boundaries/${id}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getInterventions(status?: string): Promise<{ interventions: Intervention[]; pending: number }> {
  const url = status ? `${API_BASE}/interventions?status=${status}` : `${API_BASE}/interventions`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  const d = await res.json();
  return { interventions: d.interventions || [], pending: d.pending || 0 };
}

export async function decideIntervention(id: string, approved: boolean, note: string): Promise<void> {
  const res = await fetch(`${API_BASE}/interventions/${id}/decide`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ approved, note }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getEffectReport(): Promise<EffectReport> {
  const res = await fetch(`${API_BASE}/reports/effect`, { headers: authHeaders() });
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
  const res = await fetch(`${API_BASE}/kg/stats`, { headers: authHeaders() });
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
  const res = await fetch(`${API_BASE}/kg/query?${qs.toString()}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function rebuildKg(): Promise<{ mode: string; stats: KgStats }> {
  const res = await fetch(`${API_BASE}/kg/rebuild`, { method: 'POST', headers: authHeaders() });
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
  const res = await fetch(`${API_BASE}/strategy`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getStrategySuggestions(): Promise<{
  target_autonomous_rate: number;
  suggestions: StrategySuggestion[];
}> {
  const res = await fetch(`${API_BASE}/strategy/suggestions`, { headers: authHeaders() });
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
    headers: authHeaders(),
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getStrategyHistory(): Promise<{ history: StrategyHistoryEntry[]; total: number }> {
  const res = await fetch(`${API_BASE}/strategy/history`, { headers: authHeaders() });
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
  const res = await fetch(`${API_BASE}/gateways`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function readGateway(name: string, address = '*', count = 8): Promise<GatewayReadResult> {
  const res = await fetch(`${API_BASE}/gateways/${name}/read`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ address, count }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ 多租户管理 API ============

export interface TenantInfo {
  id: string;
  name: string;
  is_active: boolean;
  created_at?: string;
  gateway_config?: GatewayConfig | null;
}

export interface GatewayConfig {
  modbus_host?: string;
  modbus_port?: number;
  mqtt_broker?: string;
  mqtt_port?: number;
  opcua_endpoint?: string;
  ipc_cfx_broker?: string;
}

export interface RegisterResult {
  tenant_id: string;
  name: string;
  api_key: string;
  note?: string;
}

export interface RotateResult {
  tenant_id: string;
  api_key: string;
  note?: string;
}

/** 自助注册新租户。明文 api_key 仅此一次返回。 */
export async function registerTenant(name: string): Promise<RegisterResult> {
  const res = await fetch(`${API_BASE}/tenants/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 查询当前租户信息（需 X-Tenant-Key）。 */
export async function getTenantMe(): Promise<TenantInfo> {
  const res = await fetch(`${API_BASE}/tenants/me`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 轮换当前租户密钥（需 X-Tenant-Key）。 */
export async function rotateTenantKey(): Promise<RotateResult> {
  const res = await fetch(`${API_BASE}/tenants/rotate`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 注销当前租户（默认租户不可删，需 X-Tenant-Key）。 */
export async function deleteTenant(): Promise<void> {
  const res = await fetch(`${API_BASE}/tenants/me`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
}

/** 读取当前租户网关配置（需 X-Tenant-Key）。 */
export async function getTenantGatewayConfig(): Promise<{ tenant_id: string; gateway_config: GatewayConfig | null }> {
  const res = await fetch(`${API_BASE}/tenants/gateway-config`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 设置当前租户网关配置覆写（需 X-Tenant-Key）。 */
export async function putTenantGatewayConfig(cfg: GatewayConfig): Promise<{ tenant_id: string; gateway_config: GatewayConfig | null }> {
  const res = await fetch(`${API_BASE}/tenants/gateway-config`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(cfg),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
