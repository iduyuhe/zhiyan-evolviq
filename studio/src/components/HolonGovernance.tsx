import { useState, useEffect, useCallback } from 'react';

interface AgentGovernance {
  agent: string;
  autonomy_level: string;
  boundary: { confidence_threshold: number; auto_execute_actions: number; require_approval_actions: number; max_daily_autonomous: number; enabled: boolean };
  experience: { approvals: number; rejections: number; recent_rejections: number };
  consequence: { total: number; validated: number; contradicted: number };
}

interface PanelData {
  summary: { total_agents: number; thin: number; medium: number; thick: number };
  agents: AgentGovernance[];
  strategy_signals: Record<string, any>;
  strategy_suggestions: any;
}

const LEVEL_COLORS: Record<string, { bg: string; badge: string; label: string }> = {
  thin: { bg: 'bg-red-50 border-red-200', badge: 'bg-red-100 text-red-600', label: '薄' },
  medium: { bg: 'bg-amber-50 border-amber-200', badge: 'bg-amber-100 text-amber-600', label: '中' },
  thick: { bg: 'bg-emerald-50 border-emerald-200', badge: 'bg-emerald-100 text-emerald-600', label: '厚' },
};

const LEVEL_ICONS: Record<string, string> = { thin: '🔴', medium: '🟡', thick: '🟢' };

function LevelBadge({ level }: { level: string }) {
  const c = LEVEL_COLORS[level] || LEVEL_COLORS.medium;
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${c.badge}`}>
      {LEVEL_ICONS[level]} {c.label}
    </span>
  );
}

export default function HolonGovernance() {
  const [data, setData] = useState<PanelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const r = await fetch('/api/governance/panel');
      if (r.ok) {
        setData(await r.json());
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="page-transition text-center py-24">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-zhiyan-50 to-zhiyan-100 flex items-center justify-center">
          <span className="w-8 h-8 border-[3px] border-zhiyan-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <p className="text-gray-500 text-sm">加载治理面板…</p>
      </div>
    );
  }

  if (!data) {
    return <div className="page-transition text-center py-16 text-gray-400">无法加载治理数据</div>;
  }

  const { summary, agents } = data;

  return (
    <div className="page-transition space-y-4">
      {/* 顶栏 */}
      <div className="card-highlight">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500 to-orange-600 flex items-center justify-center text-white shadow-sm">
              🏛️
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">薄/厚 Holon 治理面板</h2>
              <p className="text-xs text-gray-400">自治度等级 · 经验统计 · 授权边界</p>
            </div>
          </div>
          <button className="btn-secondary text-xs py-1.5 px-3" onClick={fetchData}>刷新</button>
        </div>
      </div>

      {/* 概要卡片 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="card p-4 text-center">
          <p className="text-[10px] text-red-500 font-medium mb-1">🔴 薄 Holon</p>
          <p className="text-2xl font-bold text-red-600">{summary.thin}</p>
          <p className="text-[10px] text-gray-400">应收紧 / {summary.total_agents} 总</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-amber-500 font-medium mb-1">🟡 中 Holon</p>
          <p className="text-2xl font-bold text-amber-600">{summary.medium}</p>
          <p className="text-[10px] text-gray-400">维持 / {summary.total_agents} 总</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-emerald-500 font-medium mb-1">🟢 厚 Holon</p>
          <p className="text-2xl font-bold text-emerald-600">{summary.thick}</p>
          <p className="text-[10px] text-gray-400">可放权 / {summary.total_agents} 总</p>
        </div>
      </div>

      {/* Agent 列表 */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
          <span className="text-sm font-semibold text-gray-800">Agent 自治度列表</span>
          <span className="ml-2 text-[10px] text-gray-400">{agents.length} agents</span>
        </div>
        {agents.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-400">暂无 Agent 边界数据</div>
        ) : (
          <div className="divide-y divide-gray-50">
            {agents.map((a) => {
              const c = LEVEL_COLORS[a.autonomy_level] || LEVEL_COLORS.medium;
              const open = expanded === a.agent;
              return (
                <div key={a.agent} className={`${c.bg} border-l-4 ${
                  a.autonomy_level === 'thin' ? 'border-l-red-500' :
                  a.autonomy_level === 'thick' ? 'border-l-emerald-500' : 'border-l-amber-500'
                }`}>
                  <button
                    className="w-full flex items-center justify-between px-4 py-3 text-left"
                    onClick={() => setExpanded(open ? null : a.agent)}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{LEVEL_ICONS[a.autonomy_level]}</span>
                      <div>
                        <span className="text-sm font-medium text-gray-800">{a.agent}</span>
                        <LevelBadge level={a.autonomy_level} />
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-[11px] text-gray-500">
                      <span>置信阈 {a.boundary.confidence_threshold}</span>
                      <span>经验 {a.experience.approvals + a.experience.rejections}</span>
                      <span className={`transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
                    </div>
                  </button>

                  {open && (
                    <div className="px-4 pb-4 pt-0 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                      {/* 授权边界 */}
                      <div className="p-3 rounded-lg bg-white/70 border border-gray-100">
                        <p className="font-semibold text-gray-700 mb-2">🔒 授权边界</p>
                        <div className="space-y-1.5 text-gray-500">
                          <div className="flex justify-between">
                            <span>启用</span>
                            <span className={a.boundary.enabled ? 'text-green-600' : 'text-red-500'}>
                              {a.boundary.enabled ? '✅ 是' : '❌ 否'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span>置信阈值</span>
                            <span className="font-mono">{a.boundary.confidence_threshold}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>自动执行动作</span>
                            <span className="font-mono">{a.boundary.auto_execute_actions}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>需审批动作</span>
                            <span className="font-mono">{a.boundary.require_approval_actions}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>日最大自主</span>
                            <span className="font-mono">{a.boundary.max_daily_autonomous}</span>
                          </div>
                        </div>
                      </div>

                      {/* 经验统计 */}
                      <div className="p-3 rounded-lg bg-white/70 border border-gray-100">
                        <p className="font-semibold text-gray-700 mb-2">🧠 经验反馈</p>
                        <div className="space-y-1.5 text-gray-500">
                          <div className="flex justify-between">
                            <span>采纳 (approvals)</span>
                            <span className="font-mono text-emerald-600">{a.experience.approvals}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>驳回 (rejections)</span>
                            <span className="font-mono text-red-500">{a.experience.rejections}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>🚨 近 24h 驳回</span>
                            <span className="font-mono text-red-600">{a.experience.recent_rejections}</span>
                          </div>
                          <div className="flex justify-between pt-1 border-t border-gray-100">
                            <span>采纳率</span>
                            <span className="font-mono">
                              {a.experience.approvals + a.experience.rejections > 0
                                ? ((a.experience.approvals / (a.experience.approvals + a.experience.rejections)) * 100).toFixed(0) + '%'
                                : 'N/A'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* 后果校验 */}
                      <div className="p-3 rounded-lg bg-white/70 border border-gray-100">
                        <p className="font-semibold text-gray-700 mb-2">🔄 蓝弧后果</p>
                        <div className="space-y-1.5 text-gray-500">
                          <div className="flex justify-between">
                            <span>总校验数</span>
                            <span className="font-mono">{a.consequence.total}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>✅ 已验证</span>
                            <span className="font-mono text-emerald-600">{a.consequence.validated}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>❌ 矛盾</span>
                            <span className="font-mono text-red-500">{a.consequence.contradicted}</span>
                          </div>
                          <div className="flex justify-between pt-1 border-t border-gray-100">
                            <span>合规率</span>
                            <span className="font-mono">
                              {a.consequence.total > 0
                                ? ((a.consequence.validated / a.consequence.total) * 100).toFixed(0) + '%'
                                : 'N/A'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 策略调参建议 */}
      {data.strategy_suggestions?.suggestions?.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">🎚️ 策略调参建议</h3>
          <div className="space-y-2">
            {data.strategy_suggestions.suggestions.slice(0, 5).map((s: any, i: number) => (
              <div key={s.id || i} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-xs">
                <span className={`w-2 h-2 rounded-full ${s.direction === 'tighten' ? 'bg-red-400' : 'bg-emerald-400'}`} />
                <span className="font-medium text-gray-700 w-24">{s.agent}</span>
                <span className="text-gray-500">{s.param}: {s.current} → {s.suggested}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${s.direction === 'tighten' ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-600'}`}>
                  {s.direction === 'tighten' ? '收紧' : '放宽'}
                </span>
                <span className="text-gray-400 flex-1 truncate">{s.rationale}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="text-center text-[10px] text-gray-300 py-2">
        智衍 EvolvIQ · Holon 治理面板 · 每 10s 自动刷新
      </div>
    </div>
  );
}
