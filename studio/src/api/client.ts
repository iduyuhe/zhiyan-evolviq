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

// ============ 企业认证（v28）：JWT 存取 + 自动注入 ============
const TOKEN_KEY = 'zhiyan_jwt';
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string | null): void {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: string;
  tenant_id: string;
  auth_source: string;
}

export function authHeaders(extra?: Record<string, string>, key?: string | null): Record<string, string> {
  // key 为 undefined → 使用全局激活租户 _tenantKey；为 null → 显式匿名（default）；为字符串 → 临时指定某个租户 Key
  const effectiveKey = key === undefined ? _tenantKey : key;
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(effectiveKey ? { 'X-Tenant-Key': effectiveKey } : {}),
    ...(extra ?? {}),
  };
}

// ============ 登录 / 当前用户 / 登出 ============
export async function login(username: string, password: string): Promise<{ access_token: string; user: AuthUser }> {
  const res = await fetch(`${API_BASE}/authn/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => '');
    throw new Error(msg || `登录失败 (${res.status})`);
  }
  const data = await res.json();
  // 🔴 关键：登录成功后必须持久化 token，否则 authHeaders() 永远读不到，
  // 所有受 JWT 保护的接口都会 401（此前"点击没反应"的真正根因）。
  setToken(data.access_token);
  return data;
}

export async function fetchMe(): Promise<AuthUser> {
  const token = getToken();
  if (!token) throw new Error('no token');
  const res = await fetch(`${API_BASE}/authn/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`未授权 (${res.status})`);
  return res.json();
}

export function logout(): void {
  setToken(null);
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

// ============ ERP/MES 回写审计桥 ============

export interface WritebackSubmitRequest {
  system: string;          // mes / erp
  agent: string;
  decision_type: string;
  payload: Record<string, unknown>;
  tenant_id?: string;
  decision_id?: string | null;
}

export interface WritebackSubmitResult {
  status: 'sent' | 'pending' | 'rejected';
  record_id?: string;
  detail?: string;
}

export interface WritebackRecord {
  id: string;
  system: string;
  tenant_id: string;
  agent: string;
  decision_type: string;
  decision_id: string;
  status: string;          // pending | sent | failed
  created_at: number;      // unix 秒
  sent_at: number | null;
  error: string | null;
}

export interface WritebackStats {
  pending: number;
  sent_total: number;
  systems: string[];
}

export interface WritebackRetryResult {
  sent: number;
  pending_remaining: number;
}

/** 提交一条决策回写（agent 决策 → 业务系统审计记录）。 */
export async function submitWriteback(req: WritebackSubmitRequest): Promise<WritebackSubmitResult> {
  const res = await fetch(`${API_BASE}/writeback`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 查看回写 pending 队列。 */
export async function getWritebackPending(): Promise<{ pending: WritebackRecord[] }> {
  const res = await fetch(`${API_BASE}/writeback/pending`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 触发 pending 队列重试。 */
export async function retryWriteback(): Promise<WritebackRetryResult> {
  const res = await fetch(`${API_BASE}/writeback/retry`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 回写桥状态统计。 */
export async function getWritebackStats(): Promise<WritebackStats> {
  const res = await fetch(`${API_BASE}/writeback/stats`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------- 监控告警（v29.1） ----------------

export interface AlertItem {
  key: string;
  kind: string;
  severity: string;       // warning | critical
  message: string;
  detail: Record<string, any>;
  ts: number;
  notified: number;
}

export interface MonitorStatus {
  alerts_total: number;
  thresholds: {
    wb_pending: number;
    twin_stale_s: number;
    login_fails: number;
    login_window_s: number;
  };
  login_watch: Record<string, number>;
  cooldown_s: number;
  notifiers: string[];
}

export async function getAlerts(kind?: string, n = 50): Promise<AlertItem[]> {
  const q = new URLSearchParams();
  if (kind) q.set('kind', kind);
  q.set('n', String(n));
  const res = await fetch(`${API_BASE}/monitoring/alerts?${q.toString()}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMonitorStatus(): Promise<MonitorStatus> {
  const res = await fetch(`${API_BASE}/monitoring/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function triggerMonitorCheck(): Promise<{ fired: AlertItem[] }> {
  const res = await fetch(`${API_BASE}/monitoring/check`, { method: 'POST', headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------- 隐性信号捕获（v21.5） ----------------

export type TacitChannel = 'human' | 'social' | 'meeting' | 'collab';

export interface TacitCaptureItem {
  tenant_id: string;
  kind: string;
  decision: string;
  channel: string;
  source: string;
  context: string;
  extracted: Record<string, any>;
  entities: any[];
  created_at: string;
}

export async function submitTacitSignal(
  channel: TacitChannel,
  source: string,
  payload: Record<string, any>,
  entities: string[] = [],
  confidence = 1.0,
): Promise<{ status: string; event_id: string; channel: string }> {
  const res = await fetch(`${API_BASE}/tacit-capture/${channel}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ source, payload, entities, confidence }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTacitCaptures(channel?: string, limit = 50): Promise<{
  tenant_id: string;
  tacit_captures: TacitCaptureItem[];
  pending_kg_facts: any[];
}> {
  const q = new URLSearchParams();
  if (channel) q.set('channel', channel);
  q.set('limit', String(limit));
  const res = await fetch(`${API_BASE}/experience/tacit?${q.toString()}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------- 蓝弧闭环（v22） ----------------

export interface BlueArcStatus {
  total_consequences: number;
  validated: number;
  contradicted: number;
  pending_outcomes: number;
  match_rate: number;
}

export async function declareBlueArcAction(
  agent: string,
  predicted: Record<string, any>,
  linked_fact_id?: string,
): Promise<{ action_id: string; status: string; agent: string }> {
  const res = await fetch(`${API_BASE}/blue-arc/act`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ agent, predicted, linked_fact_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function reportBlueArcActual(
  action_id: string,
  actual: Record<string, any>,
  source = 'api',
): Promise<{ action_id: string; match: boolean; validated: boolean; match_detail: any }> {
  const res = await fetch(`${API_BASE}/blue-arc/observe`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ action_id, actual, source }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getBlueArcStatus(): Promise<BlueArcStatus> {
  const res = await fetch(`${API_BASE}/blue-arc/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------- 社交通道接入（v29.9） ----------------

export interface SocialConnector {
  name: string;
  kind: string;
  enabled: boolean;
  error: string | null;
}

export interface ConnectivityTestResult {
  ok: boolean;
  mode?: string;
  latency_ms?: number;
  detail?: string;
  protocol?: string;
  kind?: string;
}

export async function getConnectors(): Promise<{ connectors: SocialConnector[] }> {
  const res = await fetch(`${API_BASE}/connectors`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function testConnector(name: string): Promise<ConnectivityTestResult> {
  const res = await fetch(`${API_BASE}/connectors/${name}/test`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function pullEmail(): Promise<{ pulled: number; published: number; sensitive: number }> {
  const res = await fetch(`${API_BASE}/connectors/email/pull`, {
    method: 'POST', headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------- 配置 UI 连通性验证（路线图 §4.4） ----------------

export interface ConnectivityOverview {
  timestamp: number;
  db: { available: boolean; mode?: string; url?: string | null };
  knowledge_graph: { available?: boolean; mode?: string };
  gateways: { total: number; ready: number; initialized: boolean; modes?: Record<string, number>; gateways?: Record<string, any> };
  data_sources: { kind: string; name: string; available: boolean }[] | { error: string };
  connectors: SocialConnector[] | { error: string };
}

export async function getConnectivity(): Promise<ConnectivityOverview> {
  const res = await fetch(`${API_BASE}/connectivity`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function testGateway(
  protocol: string, endpoint?: string, port?: number,
): Promise<ConnectivityTestResult> {
  const res = await fetch(`${API_BASE}/connectivity/gateway`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ protocol, endpoint, port }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function testDataSource(
  kind: string, config: Record<string, any> = {},
): Promise<ConnectivityTestResult> {
  const res = await fetch(`${API_BASE}/connectivity/datasource`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ kind, config }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function testRegisteredDataSource(kind: string): Promise<ConnectivityTestResult> {
  const res = await fetch(`${API_BASE}/data-sources/${kind}/test`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface DataSourceEntry {
  kind: string;
  name: string;
  tenant: string;
  available: boolean;
}

export async function listDataSources(): Promise<DataSourceEntry[]> {
  const res = await fetch(`${API_BASE}/data-sources`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addDataSource(
  kind: string, config: Record<string, any>, persist = true,
): Promise<{ status: string; kind: string; tenant: string }> {
  const res = await fetch(`${API_BASE}/data-sources?persist=${persist}`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ kind, config, persist }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}


// ============ 环境感知第⑥路（S2 v30.5 β 租户订阅规则） ============

export interface EnvSourceStatus {
  name: string;
  kind: string;
  label: string;
  credibility: string;
  enabled: boolean;
  mode: string;          // live | simulated
  last_mode?: string | null;
  last_pull_ts?: number | null;
  error?: string | null;
}

export interface EnvSubscription {
  id: string | null;
  tenant_id: string;
  source_name: string;
  enabled: boolean;
  credibility_min: string;
  keywords_include: string[];
  keywords_exclude: string[];
  poll_interval_sec: number;
  is_default?: boolean;
}

export interface EnvSubscriptionsView {
  tenant_id: string;
  subscriptions: EnvSubscription[];
  enabled_count: number;
  free_max_sources: number;
}

export interface EnvSignal {
  id?: string;
  source?: string;
  credibility?: string;
  payload?: Record<string, any>;
  entities?: string[];
  ts?: number;
}

export async function getEnvironmentOverview(): Promise<{
  sources: EnvSourceStatus[];
  signal_count: number;
  review: Record<string, number>;
}> {
  const res = await fetch(`${API_BASE}/environment`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function testEnvSource(name: string): Promise<ConnectivityTestResult & { name?: string }> {
  const res = await fetch(`${API_BASE}/environment/sources/${name}/test`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listEnvSubscriptions(): Promise<EnvSubscriptionsView> {
  const res = await fetch(`${API_BASE}/environment/subscriptions`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 保存订阅规则。后端「先测试后保存」闸门：测试失败返回 409（可 force），超免费额度返回 402。 */
export async function saveEnvSubscription(
  sourceName: string,
  body: {
    enabled: boolean;
    credibility_min: string;
    keywords_include: string[];
    keywords_exclude: string[];
    poll_interval_sec: number;
    force?: boolean;
  },
): Promise<{ status: string; subscription: EnvSubscription; test: ConnectivityTestResult | null }> {
  const res = await fetch(`${API_BASE}/environment/subscriptions/${sourceName}`, {
    method: 'PUT', headers: authHeaders(), body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(text) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function deleteEnvSubscription(
  sourceName: string,
): Promise<{ status: string; source_name: string; fallback: string }> {
  const res = await fetch(`${API_BASE}/environment/subscriptions/${sourceName}`, {
    method: 'DELETE', headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface EnvQuotaMetric {
  used: number;
  limit: number | null;      // null = 不限量（信任爬梯③已达 / default 租户）
  remaining?: number | null;
  period: string;
}

export interface EnvQuotaView {
  tenant_id: string;
  unlimited: boolean;
  upgrade_hint: string | null;
  metrics: {
    daily_signals: EnvQuotaMetric;
    monthly_insights: EnvQuotaMetric;
    env_sources: EnvQuotaMetric;
  };
}

/** 免费额度视图（源数/日信号/月解读）——#310 解锁进度视图消费 */
export async function getEnvQuota(): Promise<EnvQuotaView> {
  const res = await fetch(`${API_BASE}/environment/quota`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getEnvFeed(n = 30): Promise<{
  tenant_id: string; signals: EnvSignal[]; pool_size: number; visible: number;
  quota?: { unlimited?: boolean; used?: number; limit?: number; remaining?: number;
    truncated?: number; exhausted?: boolean; upgrade_hint?: string | null };
}> {
  const res = await fetch(`${API_BASE}/environment/feed?n=${n}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function pullEnvSources(limit = 10): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/environment/pull?limit=${limit}`, {
    method: 'POST', headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ 无感转型三圈解锁进度（S2-3，#310） ============

export interface UnlockCircle {
  key: 'outer' | 'middle' | 'inner';
  label: string;
  requirement: string;
  agents: string[];
  agent_count: number;
  unlocked: boolean;
}

export interface UnlockProgressView {
  tenant_id: string;
  current_circle: 'outer' | 'middle' | 'inner';
  circles: UnlockCircle[];
  unlocked_agents: number;
  total_agents: number;
  next_step: string;
  quota: EnvQuotaView;
}

/** 三圈解锁进度（事实进度 + 下一步说明；F4 纪律：不推销不弹窗，相邻呈现） */
export async function getUnlockProgress(): Promise<UnlockProgressView> {
  const res = await fetch(`${API_BASE}/environment/unlock-progress`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ BOM 上传 × 行情毛利影响（S2-5，#311 信任爬梯③价值跳变） ============

export interface BomItem {
  material: string;
  qty: number;
  unit_price: number;
  cost: number;
}

export interface BomRecord {
  id: string;
  tenant_id: string;
  filename: string;
  product_name: string;
  item_count: number;
  total_material_cost: number;
  created_at: string | null;
  items?: BomItem[];
}

export interface MarginImpactItem {
  material: string;
  matched_entity: string;
  signal_title: string;
  item_cost: number;
  cost_share_pct: number;
  price_change_pct?: number;
  cost_delta?: number;
}

export interface MarginImpactView {
  bom_id: string;
  product_name: string;
  item_count: number;
  total_material_cost: number;
  impacts: MarginImpactItem[];
  watchlist: MarginImpactItem[];
  cost_delta_total: number;
  cost_delta_pct: number;
  signals_scanned: number;
  summary: string;
}

/** 先测试后保存闸门：只解析不落盘，422 时抛错（detail 含行号原因） */
export async function previewBom(filename: string, content: string): Promise<{
  status: string; filename: string; item_count: number;
  total_material_cost: number; items: BomItem[]; truncated: boolean;
}> {
  const res = await fetch(`${API_BASE}/bom/preview`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ filename, content }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 上传即达信任爬梯③：响应内嵌首次毛利影响测算 + 上传后圈层 */
export async function uploadBom(filename: string, content: string, productName = ''): Promise<{
  status: string; bom: BomRecord; margin_impact: MarginImpactView | null;
  current_circle: 'outer' | 'middle' | 'inner';
}> {
  const res = await fetch(`${API_BASE}/bom/upload`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ filename, content, product_name: productName }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listBoms(): Promise<{ tenant_id: string; boms: BomRecord[] }> {
  const res = await fetch(`${API_BASE}/bom`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteBom(bomId: string): Promise<{ status: string; bom_id: string }> {
  const res = await fetch(`${API_BASE}/bom/${bomId}`, {
    method: 'DELETE', headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getBomMarginImpact(bomId: string): Promise<MarginImpactView> {
  const res = await fetch(`${API_BASE}/bom/${bomId}/margin-impact`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ 共生进化环 · 反馈入口（S2-6 #313） ============
export type FeedbackType = 'like' | 'dislike' | 'idea';

export interface FeedbackItem {
  id: string;
  tenant_id: string;
  user_id: string | null;
  feedback_type: FeedbackType;
  target_kind: string | null;
  target_id: string | null;
  text: string | null;
  status: 'received' | 'pending_review' | 'issued' | 'rejected';
  created_at: string | null;
  first_response_due_at: string | null;
  responded_at: string | null;
  github_issue_url: string | null;
  github_issue_number: number | null;
}

export interface FeedbackBoard {
  scope: string;
  total: number;
  counts: Record<string, number>;
  pending: number;
  overdue: number;
  closed: number;
  sla_met: number;
  sla_rate: number | null;
  recent: FeedbackItem[];
}

/** 提交反馈（👍/👎/💡 + 可选文本与目标引用） */
export async function submitFeedback(
  feedbackType: FeedbackType,
  text?: string,
  targetKind?: string,
  targetId?: string,
): Promise<{ status: string; feedback: FeedbackItem }> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ feedback_type: feedbackType, text: text || null, target_kind: targetKind || null, target_id: targetId || null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 我的反馈列表（本租户） */
export async function listMyFeedback(status?: string): Promise<{ total: number; feedbacks: FeedbackItem[] }> {
  const url = status ? `${API_BASE}/feedback?status=${encodeURIComponent(status)}` : `${API_BASE}/feedback`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 48h 首响应 SLA 看板（租户管理员/超级管理员） */
export async function getFeedbackBoard(): Promise<FeedbackBoard> {
  const res = await fetch(`${API_BASE}/feedback/board`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** 脱敏审核门：提报为 GitHub Issue（from-customer） */
export async function escalateFeedback(fbId: string): Promise<{
  success: boolean; status: string; github_issue_url: string | null;
  github_issue_number: number | null; desensitized_text: string | null;
}> {
  const res = await fetch(`${API_BASE}/feedback/${fbId}/escalate`, {
    method: 'POST', headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

