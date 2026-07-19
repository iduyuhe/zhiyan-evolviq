import { useState, useCallback } from 'react';
import GoalInput from './components/GoalInput';
import PlanPreview from './components/PlanPreview';
import ExecutionResultView from './components/ExecutionResult';
import PMResultView from './components/PMResultView';
import YieldResultView from './components/YieldResultView';
import TraceResultView from './components/TraceResultView';
import GenericResultView from './components/GenericResultView';
import DeviceMonitor from './components/DeviceMonitor';
import SessionHistory from './components/SessionHistory';
import AuditLogView from './components/AuditLogView';
import ConsoleTab from './components/ConsoleTab';
import KnowledgeGraphTab from './components/KnowledgeGraphTab';
import StrategyTuningTab from './components/StrategyTuningTab';
import GatewayTab from './components/GatewayTab';
import AiInsightPanel from './components/AiInsightPanel';
import NotificationBell from './components/NotificationBell';
import AgentSelector from './components/AgentSelector';
import type { AgentInfo } from './components/AgentSelector';
import { DEFAULT_EXAMPLES } from './components/AgentSelector';
import { createSession, approveSession } from './api/client';
import type { Session, ExecutionResult } from './api/client';

const API_BASE = '/api';

type Stage = 'input' | 'planning' | 'approving' | 'executing' | 'result' | 'error';
type Tab = 'studio' | 'monitor' | 'history' | 'audit' | 'console' | 'knowledge' | 'strategy' | 'gateway';

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
  const [currentAgent, setCurrentAgent] = useState<string>('supply_chain');
  const [examples, setExamples] = useState<string[]>(DEFAULT_EXAMPLES.supply_chain);

  const handleAgentChange = (agent: AgentInfo) => {
    setCurrentAgent(agent.id);
    setExamples(DEFAULT_EXAMPLES[agent.id] || DEFAULT_EXAMPLES.supply_chain);
    handleNewGoal();
  };

  const handleQuickCheck = useCallback(async (goal: string) => {
    setStage('executing');
    setExecuting(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/sessions/quick-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data.result);
      setStage('result');
    } catch (e) {
      setError(e instanceof Error ? e.message : '快速检查失败');
      setStage('error');
    } finally {
      setExecuting(false);
    }
  }, []);

  const handleSubmitGoal = useCallback(async (goal: string) => {
    setStage('planning');
    setError('');
    try {
      const s = await createSession(goal);
      setSession(s);
      setStage('approving');
    } catch (e) {
      setError(e instanceof Error ? e.message : '请求失败');
      setStage('error');
    }
  }, []);

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
      setError(e instanceof Error ? e.message : '执行失败');
      setStage('error');
    } finally {
      setExecuting(false);
    }
  }, [session]);

  const handleNewGoal = () => {
    setSession(null);
    setResult(null);
    setError('');
    setStage('input');
  };

  const totalSteps = stage === 'result' || stage === 'error' ? 4 : 3;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* 顶栏 */}
      <header className="border-b border-gray-200 bg-white/80 backdrop-blur-md sticky top-0 z-20 shadow-sm">
        <div className="max-w-3xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
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
          <div className="flex items-center gap-2 flex-1 justify-center">
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5 gap-0.5">
              {[
                { key: 'studio' as Tab, label: 'Studio', icon: '🤖' },
                { key: 'console' as Tab, label: '控制台', icon: '🎛️' },
                { key: 'monitor' as Tab, label: '监控', icon: '📡' },
                { key: 'history' as Tab, label: '历史', icon: '📋' },
                { key: 'audit' as Tab, label: '审计', icon: '📜' },
                { key: 'knowledge' as Tab, label: '知识图谱', icon: '🕸️' },
                { key: 'strategy' as Tab, label: '策略调参', icon: '🎚️' },
                { key: 'gateway' as Tab, label: '网关', icon: '🛰️' },
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
            <AgentSelector onSelect={handleAgentChange} />
          </div>

          {/* 右：通知 */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <NotificationBell />
          </div>
        </div>

        {/* Studio进度条 */}
        {tab === 'studio' && stage !== 'input' && (
          <div className="max-w-3xl mx-auto px-4 pb-2">
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
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-4">
        {tab === 'monitor' && <DeviceMonitor />}
        {tab === 'history' && <SessionHistory onSelect={(id) => { setTab('studio'); }} />}
        {tab === 'audit' && <AuditLogView />}
        {tab === 'console' && <ConsoleTab />}
        {tab === 'knowledge' && <KnowledgeGraphTab />}
        {tab === 'strategy' && <StrategyTuningTab />}
        {tab === 'gateway' && <GatewayTab />}

        {tab === 'studio' && stage === 'input' && <GoalInput onSubmit={handleSubmitGoal} onQuickCheck={handleQuickCheck} loading={false} agentExamples={examples} />}

        {tab === 'studio' && stage === 'planning' && (
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

        {tab === 'studio' && stage === 'approving' && session?.plan && (
          <PlanPreview plan={session.plan} onApprove={handleApprove} loading={executing} />
        )}

        {tab === 'studio' && stage === 'executing' && (
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

        {tab === 'studio' && stage === 'result' && result && (
          <div className="space-y-4">
            {/* AI 决策辅助（统一展示于各结果视图之上；无 LLM 时自动隐藏） */}
            <AiInsightPanel insight={result.ai_insight} source={result.ai_insight_source} />
            {currentAgent === 'pm_maintenance' ? (
              <PMResultView result={result as any} onNewGoal={handleNewGoal} />
            ) : currentAgent === 'yield_analysis' ? (
              <YieldResultView result={result as any} onNewGoal={handleNewGoal} />
            ) : currentAgent === 'quality_trace' ? (
              <TraceResultView result={result as any} onNewGoal={handleNewGoal} />
            ) : ['dfm_check','bom_selector','oee_optimizer','eco_change','smt_changeover','aoi_judge','ipc_standard'].includes(currentAgent) ? (
              <GenericResultView result={result as any} onNewGoal={handleNewGoal} />
            ) : (
              <ExecutionResultView result={result as any} onNewGoal={handleNewGoal} />
            )}
          </div>
        )}

        {tab === 'studio' && stage === 'error' && (
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
      </main>

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
