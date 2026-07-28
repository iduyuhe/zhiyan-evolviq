import { useState, useEffect, useCallback } from 'react';
import { authHeaders, apiUrl } from '../api/client';

const RISK_COLORS: Record<string, string> = {
  low: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  medium: 'bg-orange-50 border-orange-200 text-orange-700',
  high: 'bg-red-50 border-red-200 text-red-700',
  critical: 'bg-red-100 border-red-400 text-red-800',
};

const LEVEL_ICONS: Record<string, string> = {
  low: '🟡', medium: '🟠', high: '🔴', critical: '🚨',
};

export default function SupplyChainFederation() {
  const [activeTab, setActiveTab] = useState<'goals' | 'risks' | 'plans' | 'status'>('goals');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [goalInput, setGoalInput] = useState('');
  const [riskInput, setRiskInput] = useState({ material: '', level: 'medium', desc: '' });
  const [planInput, setPlanInput] = useState({ goalId: '', plan: '' });

  const fetchAll = useCallback(async () => {
    try {
      const [goalsR, risksR, plansR, statusR] = await Promise.all([
        fetch(apiUrl('/federation/supply-chain/goals'), { headers: authHeaders() }),
        fetch(apiUrl('/federation/supply-chain/risks'), { headers: authHeaders() }),
        fetch(apiUrl('/federation/supply-chain/plans'), { headers: authHeaders() }),
        fetch(apiUrl('/federation/supply-chain/fed-status'), { headers: authHeaders() }),
      ]);
      if (goalsR.ok && risksR.ok && plansR.ok && statusR.ok) {
        setData({
          goals: (await goalsR.json()).goals,
          risks: await risksR.json(),
          plans: (await plansR.json()).plans,
          status: await statusR.json(),
        });
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const shareGoal = async () => {
    if (!goalInput.trim()) return;
    try {
      await fetch(apiUrl('/federation/supply-chain/goal'), {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ tenant_id: 'default', goal: goalInput, target_materials: [], urgency: 'normal' }),
      });
      setGoalInput('');
      fetchAll();
    } catch { /* ignore */ }
  };

  const reportRisk = async () => {
    if (!riskInput.material.trim()) return;
    try {
      await fetch(apiUrl('/federation/supply-chain/risk'), {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ tenant_id: 'default', material: riskInput.material, risk_level: riskInput.level, description: riskInput.desc }),
      });
      setRiskInput({ material: '', level: 'medium', desc: '' });
      fetchAll();
    } catch { /* ignore */ }
  };

  if (loading) {
    return (
      <div className="page-transition text-center py-24">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-amber-50 to-amber-100 flex items-center justify-center">
          <span className="w-8 h-8 border-[3px] border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <p className="text-gray-500 text-sm">加载产业链联邦…</p>
      </div>
    );
  }

  const status = data?.status;
  const goals = data?.goals || [];
  const risks = data?.risks;
  const plans = data?.plans || [];

  return (
    <div className="page-transition space-y-4">
      {/* Header */}
      <div className="card-highlight">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white shadow-sm">
              🔗
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">产业链智能体联邦</h2>
              <p className="text-xs text-gray-400">跨企业供应链协同 · 共享目标 · 共担风险</p>
            </div>
          </div>
          <button className="btn-secondary text-xs py-1.5 px-3" onClick={fetchAll}>刷新</button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card p-3 text-center">
          <p className="text-[10px] text-gray-500">🏢 参与者</p>
          <p className="text-xl font-bold text-amber-600">{status?.participants?.count || 0}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[10px] text-gray-500">🎯 活跃目标</p>
          <p className="text-xl font-bold text-blue-600">{status?.goals?.active || 0}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[10px] text-gray-500">⚠️ 活跃风险</p>
          <p className="text-xl font-bold text-red-600">{risks?.summary?.total_active_risks || 0}</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-[10px] text-gray-500">📋 联合计划</p>
          <p className="text-xl font-bold text-green-600">{status?.plans?.active || 0}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {(['goals', 'risks', 'plans', 'status'] as const).map(tab => (
          <button key={tab} className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
            activeTab === tab ? 'border-amber-500 text-amber-700' : 'border-transparent text-gray-400 hover:text-gray-600'
          }`} onClick={() => setActiveTab(tab)}>
            {tab === 'goals' && '🎯 共享目标'}
            {tab === 'risks' && '⚠️ 风险视图'}
            {tab === 'plans' && '📋 联合计划'}
            {tab === 'status' && '🏭 联邦状态'}
          </button>
        ))}
      </div>

      {/* Goals tab */}
      {activeTab === 'goals' && (
        <div className="space-y-3">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-800 mb-2">共享新目标</h3>
            <div className="flex gap-2">
              <input className="input flex-1 text-xs" placeholder="输入产业链目标，如：确保某客户下周订单交付" value={goalInput} onChange={e => setGoalInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && shareGoal()} />
              <button className="btn-primary text-xs py-1.5 px-4" onClick={shareGoal}>共享</button>
            </div>
          </div>
          {goals.length === 0 ? (
            <div className="card text-center py-8 text-xs text-gray-400">暂无共享目标。你可以共享一个产业链目标，吸引其他企业加入协同。</div>
          ) : (
            goals.map((g: any, i: number) => (
              <div key={g.id || i} className="card p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-700">🎯 目标</span>
                    <span className="text-xs font-medium text-gray-800">{g.goal}</span>
                  </div>
                  <span className="text-[10px] text-gray-400">{g.origin}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                  <span>{g.participant_count} 家企业参与</span>
                  {g.urgency && <span className={`px-1 py-0.5 rounded ${g.urgency === 'high' ? 'bg-red-100 text-red-600' : 'bg-gray-100'}`}>{g.urgency}</span>}
                  {g.deadline && <span>截止 {g.deadline}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Risks tab */}
      {activeTab === 'risks' && (
        <div className="space-y-3">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-800 mb-2">报告供应链风险</h3>
            <div className="grid grid-cols-3 gap-2">
              <input className="input text-xs" placeholder="物料编码/名称" value={riskInput.material} onChange={e => setRiskInput({...riskInput, material: e.target.value})} />
              <select className="input text-xs" value={riskInput.level} onChange={e => setRiskInput({...riskInput, level: e.target.value})}>
                <option value="low">低危</option>
                <option value="medium">中危</option>
                <option value="high">高危</option>
                <option value="critical">危急</option>
              </select>
              <button className="btn-primary text-xs py-1.5" onClick={reportRisk}>报告风险</button>
            </div>
            <input className="input text-xs mt-2 w-full" placeholder="风险描述（可选）" value={riskInput.desc} onChange={e => setRiskInput({...riskInput, desc: e.target.value})} />
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-800">跨企业风险视图</h3>
              <div className="flex gap-3 text-[10px] text-gray-400">
                <span>共 {risks?.summary?.total_active_risks || 0} 活跃</span>
                <span>已解决 {risks?.summary?.total_resolved || 0}</span>
              </div>
            </div>

            {/* Risk level breakdown */}
            {risks?.summary?.risk_levels && (
              <div className="grid grid-cols-4 gap-2 mb-3">
                {Object.entries(risks.summary.risk_levels).map(([level, count]: [string, any]) => (
                  <div key={level} className={`p-2 rounded-lg text-center ${RISK_COLORS[level] || 'bg-gray-50'} border`}>
                    <p className="text-lg font-bold">{count as number}</p>
                    <p className="text-[10px]">{LEVEL_ICONS[level]} {level}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Risk list */}
            {risks?.recent_risks?.length > 0 ? (
              <div className="space-y-1.5">
                {risks.recent_risks.map((r: any, i: number) => (
                  <div key={r.id || i} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 text-xs">
                    <span>{LEVEL_ICONS[r.risk_level] || '⚠️'}</span>
                    <span className={`px-1 py-0.5 rounded text-[10px] ${
                      r.risk_level === 'high' || r.risk_level === 'critical' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'
                    }`}>{r.risk_level}</span>
                    <span className="text-gray-600">{r.material}</span>
                    <span className="text-gray-400 truncate flex-1">{r.description}</span>
                    <span className="text-gray-400 text-[10px]">{r.reporter}</span>
                    <span className="text-gray-300">{r.status}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 text-center py-4">暂无跨企业风险报告</p>
            )}
          </div>
        </div>
      )}

      {/* Plans tab */}
      {activeTab === 'plans' && (
        <div className="space-y-3">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-800 mb-2">创建联合计划</h3>
            <div className="flex gap-2">
              <input className="input flex-1 text-xs" placeholder="目标 ID" value={planInput.goalId} onChange={e => setPlanInput({...planInput, goalId: e.target.value})} />
              <input className="input flex-[2] text-xs" placeholder="联合执行计划描述" value={planInput.plan} onChange={e => setPlanInput({...planInput, plan: e.target.value})} />
              <button className="btn-primary text-xs py-1.5 px-4" onClick={async () => {
                if (!planInput.goalId || !planInput.plan) return;
                await fetch(apiUrl('/federation/supply-chain/plan'), {
                  method: 'POST', headers: authHeaders({'Content-Type': 'application/json'}),
                  body: JSON.stringify({ initiator: 'default', goal_id: planInput.goalId, plan: planInput.plan }),
                });
                setPlanInput({goalId: '', plan: ''});
                fetchAll();
              }}>创建</button>
            </div>
          </div>
          {plans.length === 0 ? (
            <div className="card text-center py-8 text-xs text-gray-400">暂无联合计划</div>
          ) : (
            plans.map((p: any, i: number) => (
              <div key={p.id || i} className="card p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-800">{p.plan}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                    p.status === 'active' ? 'bg-green-100 text-green-600' : 'bg-amber-100 text-amber-600'
                  }`}>{p.status}</span>
                </div>
                <div className="flex gap-3 text-[10px] text-gray-400">
                  <span>🎯 {p.goal_id}</span>
                  <span>👥 {p.participants?.length || 0} 方</span>
                  <span>🏢 {p.initiator}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Status tab */}
      {activeTab === 'status' && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">产业链联邦全景</h3>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <p className="font-medium text-gray-700 mb-2">🏢 参与企业</p>
              <p className="text-2xl font-bold text-amber-600 mb-1">{status?.participants?.count || 0}</p>
              <div className="flex flex-wrap gap-1">
                {(status?.participants?.anonymized || []).map((p: string, i: number) => (
                  <span key={i} className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[10px]">{p}</span>
                ))}
              </div>
            </div>
            <div>
              <p className="font-medium text-gray-700 mb-2">📊 联邦活动</p>
              <div className="space-y-2">
                <div className="flex justify-between"><span>活跃目标</span><span className="font-mono">{status?.goals?.active || 0}</span></div>
                <div className="flex justify-between"><span>活跃风险</span><span className="font-mono">{status?.risks?.active || risks?.summary?.total_active_risks || 0}</span></div>
                <div className="flex justify-between"><span>联合计划(活跃/提议)</span><span className="font-mono">{status?.plans?.active || 0}/{status?.plans?.proposed || 0}</span></div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="text-center text-[10px] text-gray-300 py-2">
        智衍 EvolvIQ · 产业链智能体联邦 · 每 15s 自动刷新
      </div>
    </div>
  );
}
