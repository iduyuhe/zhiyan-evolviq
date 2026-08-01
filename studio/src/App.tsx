import { useState, useCallback, useEffect } from 'react';
import GoalInput from './components/GoalInput';
import PlanPreview from './components/PlanPreview';
import ExecutionResultView from './components/ExecutionResult';
import PMResultView from './components/PMResultView';
import YieldResultView from './components/YieldResultView';
import TraceResultView from './components/TraceResultView';
import GenericResultView from './components/GenericResultView';
import DeviceMonitor from './components/DeviceMonitor';
import AlertPanel from './components/AlertPanel';
import TacitCapturePanel from './components/TacitCapturePanel';
import BlueArcPanel from './components/BlueArcPanel';
import SessionHistory from './components/SessionHistory';
import AuditLogView from './components/AuditLogView';
import ConsoleTab from './components/ConsoleTab';
import KnowledgeGraphTab from './components/KnowledgeGraphTab';
import StrategyTuningTab from './components/StrategyTuningTab';
import GatewayTab from './components/GatewayTab';
import TwinDashboard from './components/TwinDashboard';
import HolonGovernance from './components/HolonGovernance';
import FederationPanel from './components/FederationPanel';
import SupplyChainFederation from './components/SupplyChainFederation';
import AiInsightPanel from './components/AiInsightPanel';
import NotificationBell from './components/NotificationBell';
import type { AgentInfo } from './components/AgentSelector';
import { DEFAULT_EXAMPLES } from './components/AgentSelector';
import AgentSidebar from './components/AgentSidebar';
import TenantSwitcher from './components/TenantSwitcher';
import TenantManagement from './components/TenantManagement';
import WritebackPanel from './components/WritebackPanel';
import ConnectivityPanel from './components/ConnectivityPanel';
import EnvPerceptionPanel from './components/EnvPerceptionPanel';
import UnlockProgressPanel from './components/UnlockProgressPanel';
import BomMarginPanel from './components/BomMarginPanel';
import FeedbackPanel from './components/FeedbackPanel';
import { createSession, approveSession, quickCheck, authHeaders, apiUrl } from './api/client';
import type { Session, ExecutionResult } from './api/client';
import Login from './components/Login';
import { getToken, fetchMe, logout, requireLocalToken, AuthExpiredError, type AuthUser } from './api/client';

type Stage = 'input' | 'planning' | 'approving' | 'executing' | 'result' | 'error';
type Tab = 'studio' | 'monitor' | 'history' | 'audit' | 'console' | 'knowledge' | 'strategy' | 'gateway' | 'twin' | 'governance' | 'federation' | 'supplychain' | 'writeback' | 'tacit' | 'bluearc' | 'tenant' | 'connect' | 'symbiosis';

const STEPS = [
  { key: 'input', label: '目标设定', icon: '🎯' },
  { key: 'approving', label: '规划预览', icon: '📋' },
  { key: 'executing', label: '自主执行', icon: '⚡' },
  { key: 'result', label: '执行结果', icon: '📊' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('studio');
  const [stage, setStage] = useState<Stage>('input');
  const [session, setSession] = useState<Session | null>(null);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [error, setError] = useState<string>('');
  const [executing, setExecuting] = useState(false);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>('supply_chain');
  const [examples, setExamples] = useState<string[]>(DEFAULT_EXAMPLES.supply_chain);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // ============ 企业认证态（v28） ============
  const [me, setMe] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // 启动时校验本地 token（有则 /authn/me 探活，无/失效则进登录页）
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setAuthChecking(false);
      return;
    }
    fetchMe()
      .then((u) => setMe(u))
      .catch(() => {
        logout();
        setMe(null);
      })
      .finally(() => setAuthChecking(false));
  }, []);

  const handleLogin = (token: string, user: AuthUser) => {
    setMe(user);
  };
  const handleLogout = () => {
    logout();
    setMe(null);
  };

  // 🔴 全局守卫：已登录态(me 存在)但本地 token 静默丢失（多 Tab 清理 / 跨日过期 /
  // localStorage 被清）→ 立即回登录页，避免"能看 Agent 列表但一点击就 401"的悬空态。
  useEffect(() => {
    if (me && !getToken()) handleLogout();
  }, [me, handleLogout]);

  // 桌面侧栏折叠偏好持久化
  useEffect(() => {
    const saved = localStorage.getItem('zhiyan_sidebar_collapsed');
    if (saved === '1') setSidebarCollapsed(true);
  }, []);
  const toggleSidebar = () => {
    setSidebarCollapsed((c) => {
      const next = !c;
      localStorage.setItem('zhiyan_sidebar_collapsed', next ? '1' : '0');
      return next;
    });
  };

  const currentAgentInfo = agents.find((a) => a.id === currentAgent) || agents[0];

  const handleAgentChange = (agent: AgentInfo) => {
    setCurrentAgent(agent.id);
    setExamples(DEFAULT_EXAMPLES[agent.id] || DEFAULT_EXAMPLES.supply_chain);
    handleNewGoal();
  };

  useEffect(() => {
    // 🔴 必须在登录后（me 就绪、token 已持久化）才拉取。
    // 挂载时若未登录不拉取——否则 effect 只在挂载跑一次、token 尚未就绪 → 401 静默失败，
    // 登录后永不重拉 → agents 永远为空 → 侧边栏无可点项（"点击没反应"）。
    if (!me) return;
    fetch(apiUrl('/agents'), { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => {
        const list = (d.agents || []) as AgentInfo[];
        setAgents(list);
        if (list.length > 0) handleAgentChange(list[0]);
      })
      .catch((e) => {
        console.warn('[App] /api/agents 加载失败:', e?.message || e);
      });
  }, [me]);

  const handleQuickCheck = useCallback(async (goal: string) => {
    setStage('executing');
    setExecuting(true);
    setError('');
    try {
      const data = await quickCheck(goal);
      setResult(data.result);
      setStage('result');
    } catch (e) {
      if (e instanceof AuthExpiredError) {
        handleLogout();
        return;
      }
      setError(e instanceof Error ? e.message : '快速检查失败');
      setStage('error');
    } finally {
      setExecuting(false);
    }
  }, [handleLogout]);

  const handleSubmitGoal = useCallback(async (goal: string) => {
    setStage('planning');
    setError('');
    try {
      const s = await createSession(goal);
      setSession(s);
      setStage('approving');
    } catch (e) {
      if (e instanceof AuthExpiredError) {
        handleLogout();
        return;
      }
      setError(e instanceof Error ? e.message : '请求失败');
      setStage('error');
    }
  }, [handleLogout]);

  const handleApprove = useCallback(async (approved: boolean, feedback?: string) => {
    if (!session) return;
    setStage('executing');
    setExecuting(true);
    try {
      const s = await approveSession(session.session_id, approved, feedback);
      if (s.status === 'completed' && s.result) {
        setResult(s.result);
        setStage('result');
      } else {
        setStage('input');
      }
    } catch (e) {
      if (e instanceof AuthExpiredError) {
        handleLogout();
        return;
      }
      setError(e instanceof Error ? e.message : '执行失败');
      setStage('error');
    } finally {
      setExecuting(false);
    }
  }, [session, handleLogout]);

  const handleNewGoal = () => {
    setSession(null);
    setResult(null);
    setError('');
    setStage('input');
  };

  const totalSteps = stage === 'result' || stage === 'error' ? 4 : 3;

  // 认证门禁：校验中 → loading；未登录 → 登录页；已登录 → 主应用
  if (authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-50 to-white">
        <div className="flex flex-col items-center gap-3">
          <span className="w-9 h-9 border-[3px] border-zhiyan-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-400">正在校验登录状态…</span>
        </div>
      </div>
    );
  }
  if (!me) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* 顶栏 */}
      <header className="border-b border-gray-200 bg-white/80 backdrop-blur-md sticky top-0 z-20 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-4 h-16 flex items-center justify-between gap-2">
          {/* 左：品牌 */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-zhiyan-500 to-zhiyan-700 flex items-center justify-center text-white text-sm font-bold shadow-md">
              智
            </div>
            <div className="hidden sm:flex flex-col leading-tight">
              <span className="font-semibold text-gray-900 text-sm">智衍</span>
              <span className="text-[10px] text-gray-400">EvolvIQ · MVP</span>
            </div>
          </div>

          {/* 中：Tab + Agent选择器 */}
          <div className="flex items-center gap-2 flex-1 min-w-0 justify-center">
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5 gap-0.5 overflow-x-auto max-w-full">
              {[
                { key: 'studio' as Tab, label: 'Studio', icon: '🤖' },
                { key: 'console' as Tab, label: '控制台', icon: '🎛️' },
                { key: 'monitor' as Tab, label: '监控', icon: '📡' },
                { key: 'tacit' as Tab, label: '隐性信号', icon: '🧠' },
                { key: 'bluearc' as Tab, label: '蓝弧闭环', icon: '🔵' },
                { key: 'history' as Tab, label: '历史', icon: '📋' },
                { key: 'audit' as Tab, label: '审计', icon: '📜' },
                { key: 'knowledge' as Tab, label: '知识图谱', icon: '🕸️' },
                { key: 'strategy' as Tab, label: '策略调参', icon: '🎚️' },
                { key: 'governance' as Tab, label: '治理', icon: '🏛️' },
                { key: 'federation' as Tab, label: '联邦', icon: '🌍' },
                { key: 'supplychain' as Tab, label: '产业链', icon: '🔗' },
                { key: 'gateway' as Tab, label: '网关', icon: '🛰️' },
                { key: 'twin' as Tab, label: '孪生大屏', icon: '🌐' },
                { key: 'writeback' as Tab, label: '回写', icon: '🔁' },
                { key: 'tenant' as Tab, label: '租户', icon: '🏢' },
                { key: 'connect' as Tab, label: '连接', icon: '🔌' },
                { key: 'symbiosis' as Tab, label: '共生环', icon: '🤝' },
              ].map(t => (
                <button
                  key={t.key}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
                    tab === t.key
                      ? 'bg-white text-zhiyan-600 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                  onClick={() => setTab(t.key)}
                >
                  <span className="mr-1">{t.icon}</span>{t.label}
                </button>
              ))}
            </div>
          </div>

          {/* 右：租户切换 + 通知 + 用户 */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <TenantSwitcher onManage={() => setTab('tenant')} />
            <NotificationBell />
            {me && (
              <div className="flex items-center gap-2 pl-1.5 border-l border-gray-200 ml-0.5">
                <div className="hidden sm:flex flex-col items-end leading-tight">
                  <span className="text-xs font-medium text-gray-700">{me.display_name || me.username}</span>
                  <span className="text-[10px] text-gray-400">{me.role}</span>
                </div>
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-zhiyan-500 to-zhiyan-700 flex items-center justify-center text-white text-xs font-bold">
                  {((me.display_name || me.username) || '?').slice(0, 1).toUpperCase()}
                </div>
                <button
                  onClick={handleLogout}
                  title="退出登录"
                  className="px-2 py-1 text-xs rounded-md text-gray-500 hover:text-red-600 hover:bg-red-50 transition"
                >
                  退出
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Studio进度条 */}
        {tab === 'studio' && stage !== 'input' && (
          <div className="max-w-[1400px] mx-auto px-4 pb-2">
            <div className="hidden sm:flex items-center gap-1 text-xs text-gray-400">
              {STEPS.slice(0, totalSteps).map((step, i) => {
                const idx = STEPS.findIndex(s => s.key === stage);
                const isActive = i <= idx;
                return (
                  <div key={step.key} className="flex items-center">
                    <span className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                      isActive ? 'text-zhiyan-600 font-medium' : ''
                    }`}>
                      {step.icon}{step.label}
                    </span>
                    {i < totalSteps - 1 && <span className="text-gray-300 mx-0.5">›</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </header>

      {/* 主内容 */}
      {tab === 'studio' ? (
        <div className="max-w-7xl mx-auto flex">
          {/* 左侧 Agent 侧栏（桌面常驻，可收起） */}
          {!sidebarCollapsed && (
            <aside className="hidden lg:flex lg:flex-col w-64 shrink-0 border-r border-gray-200 bg-white sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto">
              <div className="flex items-center justify-end px-2 pt-2">
                <button
                  onClick={toggleSidebar}
                  title="收起侧栏"
                  className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:text-zhiyan-600 hover:bg-zhiyan-50 transition-colors"
                >
                  «
                </button>
              </div>
              <AgentSidebar agents={agents} current={currentAgent} onSelect={handleAgentChange} />
            </aside>
          )}

          {/* 右侧 Studio 主区 */}
          <div className="flex-1 min-w-0">
            {/* 顶部条：桌面折叠时的展开入口 / 窄屏抽屉切换入口 */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-white sticky top-16 z-10">
              {/* 桌面 + 侧栏已收起：展开入口 */}
              {sidebarCollapsed && (
                <button
                  onClick={toggleSidebar}
                  className="hidden lg:flex items-center gap-2 px-3 py-1.5 border border-zhiyan-200 rounded-lg bg-zhiyan-50 text-zhiyan-700 text-sm"
                >
                  <span className="leading-none">»</span>
                  <span className="font-medium">选择 Agent</span>
                </button>
              )}
              {/* 窄屏：当前 Agent 抽屉切换 */}
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden flex items-center gap-2 px-3 py-1.5 border border-zhiyan-200 rounded-lg bg-zhiyan-50 text-zhiyan-700 text-sm"
              >
                <span className="text-base leading-none">{currentAgentInfo?.icon}</span>
                <span className="font-medium">{currentAgentInfo?.name || '选择 Agent'}</span>
                <span className="text-zhiyan-400">▾</span>
              </button>
              <span className="text-xs text-gray-400 lg:hidden">切换 Agent</span>
            </div>

            <div className="max-w-3xl mx-auto px-4 py-8 space-y-4">
              {stage === 'input' && <GoalInput onSubmit={handleSubmitGoal} onQuickCheck={handleQuickCheck} loading={false} agentExamples={examples} />}

              {stage === 'planning' && (
                <div className="page-transition card text-center py-16">
                  <div className="w-16 h-16 mx-auto mb-5 rounded-full bg-gradient-to-br from-zhiyan-50 to-zhiyan-100 flex items-center justify-center shadow-inner">
                    <span className="w-8 h-8 border-[3px] border-zhiyan-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                  <p className="text-gray-700 font-medium">Agent 正在分析目标</p>
                  <p className="text-sm text-gray-400 mt-2">解读业务意图 · 规划执行路径 · 计算所需数据</p>
                  <div className="flex justify-center gap-1.5 mt-4">
                    {[0, 1, 2].map(i => (
                      <span key={i} className="w-2 h-2 rounded-full bg-zhiyan-400 animate-pulse-dot" />
                    ))}
                  </div>
                </div>
              )}

              {stage === 'approving' && session?.plan && (
                <PlanPreview plan={session.plan} onApprove={handleApprove} loading={executing} />
              )}

              {stage === 'executing' && (
                <div className="page-transition card text-center py-16">
                  <div className="w-16 h-16 mx-auto mb-5 rounded-full bg-gradient-to-br from-green-50 to-green-100 flex items-center justify-center shadow-inner">
                    <span className="w-8 h-8 border-[3px] border-green-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                  <p className="text-gray-700 font-medium">Agent 正在自主执行</p>
                  <p className="text-sm text-gray-400 mt-2">
                    <span className="inline-flex items-center gap-1.5">
                      <span>查询数据</span>
                      <span className="text-gray-300">→</span>
                      <span>分析缺料</span>
                      <span className="text-gray-300">→</span>
                      <span>检索替代</span>
                      <span className="text-gray-300">→</span>
                      <span>执行操作</span>
                    </span>
                  </p>
                  <div className="flex justify-center gap-1.5 mt-4">
                    {[0, 1, 2].map(i => (
                      <span key={i} className="w-2 h-2 rounded-full bg-green-400 animate-pulse-dot" />
                    ))}
                  </div>
                </div>
              )}

              {stage === 'result' && result && (
                <div className="space-y-4">
                  {/* AI 决策辅助（统一展示于各结果视图之上；无 LLM 时自动隐藏） */}
                  <AiInsightPanel insight={result.ai_insight} source={result.ai_insight_source} />
                  {currentAgent === 'pm_maintenance' ? (
                    <PMResultView result={result as any} onNewGoal={handleNewGoal} />
                  ) : currentAgent === 'yield_analysis' ? (
                    <YieldResultView result={result as any} onNewGoal={handleNewGoal} />
                  ) : currentAgent === 'quality_trace' ? (
                    <TraceResultView result={result as any} onNewGoal={handleNewGoal} />
                  ) : ['dfm_check','bom_selector','oee_optimizer','eco_change','smt_changeover','aoi_judge','ipc_standard','aps_scheduler','energy_carbon','cost_analysis','demand_order','wms_logistics','compliance_q','executive_cockpit','rd_npi','procurement_manage'].includes(currentAgent) ? (
                    <GenericResultView result={result as any} onNewGoal={handleNewGoal} />
                  ) : (
                    <ExecutionResultView result={result as any} onNewGoal={handleNewGoal} />
                  )}
                </div>
              )}

              {stage === 'error' && (
                <div className="page-transition card border-red-200 text-center py-12">
                  <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-red-50 flex items-center justify-center">
                    <span className="text-2xl">❌</span>
                  </div>
                  <p className="text-gray-800 font-medium mb-1">出错了</p>
                  <p className="text-sm text-gray-500 mb-6">{error}</p>
                  <div className="flex gap-3 justify-center">
                    <button className="btn-secondary" onClick={handleNewGoal}>重新开始</button>
                    <button className="btn-primary" onClick={() => window.location.reload()}>刷新页面</button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 窄屏抽屉：复用 AgentSidebar */}
          {sidebarOpen && (
            <div className="lg:hidden fixed inset-0 z-40 flex">
              <div className="flex-1 bg-black/30" onClick={() => setSidebarOpen(false)} />
              <div className="w-72 max-w-[80%] bg-white h-full overflow-y-auto shadow-xl">
                <div className="flex items-center justify-between px-3 py-3 border-b border-gray-100 sticky top-0 bg-white">
                  <span className="text-sm font-semibold text-gray-900">选择 Agent</span>
                  <button onClick={() => setSidebarOpen(false)} className="text-gray-400 text-xl leading-none px-2">×</button>
                </div>
                <AgentSidebar
                  agents={agents}
                  current={currentAgent}
                  onSelect={handleAgentChange}
                  onItemClick={() => setSidebarOpen(false)}
                />
              </div>
            </div>
          )}
        </div>
      ) : (
        <main className="max-w-3xl mx-auto px-4 py-8 space-y-4">
          {tab === 'monitor' && (<><DeviceMonitor /><AlertPanel /></>)}
          {tab === 'tacit' && <TacitCapturePanel />}
          {tab === 'bluearc' && <BlueArcPanel />}
          {tab === 'history' && <SessionHistory onSelect={() => { setTab('studio'); }} />}
          {tab === 'audit' && <AuditLogView />}
          {tab === 'console' && <ConsoleTab />}
          {tab === 'knowledge' && <KnowledgeGraphTab />}
          {tab === 'strategy' && <StrategyTuningTab />}
          {tab === 'governance' && <HolonGovernance />}
          {tab === 'federation' && <FederationPanel />}
          {tab === 'supplychain' && <SupplyChainFederation />}
          {tab === 'gateway' && <GatewayTab />}
          {tab === 'twin' && <TwinDashboard />}
          {tab === 'writeback' && <WritebackPanel />}
          {tab === 'tenant' && <TenantManagement />}
          {tab === 'connect' && (<><UnlockProgressPanel /><BomMarginPanel /><EnvPerceptionPanel /><ConnectivityPanel /></>)}
          {tab === 'symbiosis' && <FeedbackPanel />}
        </main>
      )}

      {/* 底部 */}
      <footer className="border-t border-gray-100 mt-16 py-6 text-center">
        <div className="max-w-3xl mx-auto px-4">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="w-5 h-5 rounded bg-gradient-to-br from-zhiyan-500 to-zhiyan-700 flex items-center justify-center text-white text-[8px] font-bold">
              智
            </div>
            <span className="text-xs font-medium text-gray-500">智衍 EvolvIQ</span>
          </div>
          <p className="text-xs text-gray-400">Agent Studio · MVP · © 2026 工业5点0产业生态联盟</p>
        </div>
      </footer>
    </div>
  );
}
