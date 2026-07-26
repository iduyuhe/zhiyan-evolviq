import { useState, useEffect, useCallback } from 'react';
import { authHeaders } from '../api/client';

interface DashboardData {
  uns: { channel_counts: Record<string, number>; recent_events: any[]; total_events: number };
  kg: { total_proposals: number; drafts: number; approved: number; needs_review: number; validated: number; corrections: number; recent_proposals: any[] };
  consequence: { stats: { total_consequences: number; validated: number; contradicted: number; pending_outcomes: number; match_rate: number }; recent: any[] };
  experience: { total_records: number; feedback: number; tacit_captures: number; outcomes: number };
  gateways: Record<string, any>;
}

function TwoColorBar({ value, total, label, colorA, colorB }: { value: number; total: number; label: string; colorA: string; colorB: string }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 truncate">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${value > 0 ? colorA : colorB}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-gray-600">{value}</span>
    </div>
  );
}

function StatCard({ icon, label, value, sub, color }: { icon: string; label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="card p-4 hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg shadow-sm ${color || 'bg-zhiyan-50'}`}>
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-400 mb-0.5">{label}</p>
          <p className="text-xl font-bold text-gray-800">{value}</p>
          {sub && <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

function EventRow({ ev, i }: { ev: any; i: number }) {
  const chColors: Record<string, string> = {
    gateway: 'border-l-blue-500 bg-blue-50/30',
    system: 'border-l-green-500 bg-green-50/30',
    human: 'border-l-purple-500 bg-purple-50/30',
    social: 'border-l-orange-500 bg-orange-50/30',
    meeting: 'border-l-pink-500 bg-pink-50/30',
    collab: 'border-l-cyan-500 bg-cyan-50/30',
  };
  const color = chColors[ev.channel] || 'border-l-gray-300';
  return (
    <div key={ev.id || i} className={`flex items-start gap-2 p-2 rounded-lg border-l-4 ${color} text-xs`}>
      <span className="font-mono text-[10px] text-gray-400 w-12 shrink-0">
        {new Date(ev.ts * 1000).toLocaleTimeString('zh-CN')}
      </span>
      <span className={`px-1 py-0.5 rounded text-[10px] font-medium ${
        ev.channel === 'gateway' ? 'bg-blue-100 text-blue-700' :
        ev.channel === 'system' ? 'bg-green-100 text-green-700' :
        ev.channel === 'human' ? 'bg-purple-100 text-purple-700' :
        ev.channel === 'social' ? 'bg-orange-100 text-orange-700' :
        ev.channel === 'meeting' ? 'bg-pink-100 text-pink-700' :
        ev.channel === 'collab' ? 'bg-cyan-100 text-cyan-700' : ''
      }`}>{ev.channel}</span>
      <span className="text-gray-600 truncate flex-1">{ev.source}</span>
      <span className="text-gray-400 truncate max-w-[120px]">{ev.type}</span>
    </div>
  );
}

const THREE_DOCTRINES = [
  { name: '连接主义', title: '连接主义', desc: '隐性信号捕获', icon: '🔗', color: 'border-l-blue-500' },
  { name: '符号主义', title: '符号主义', desc: '知识图谱锚定', icon: '🕸️', color: 'border-l-violet-500' },
  { name: '行为主义', title: '行为主义', desc: '后果校验修正', icon: '🔄', color: 'border-l-emerald-500' },
];

const CHANNEL_ICONS: Record<string, string> = {
  gateway: '🛰️', system: '⚙️', human: '👤', social: '💬', meeting: '📋', collab: '🤝',
};

export default function TwinDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchData = useCallback(async () => {
    try {
      const r = await fetch('/api/twin/dashboard', { headers: authHeaders() });
      if (r.ok) {
        setData(await r.json());
        setLastUpdated(new Date());
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="page-transition text-center py-24">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-zhiyan-50 to-zhiyan-100 flex items-center justify-center">
          <span className="w-8 h-8 border-[3px] border-zhiyan-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <p className="text-gray-500 text-sm">加载孪生大屏数据…</p>
      </div>
    );
  }

  const channelCounts = data?.uns.channel_counts || {};
  const kg = data?.kg;
  const con = data?.consequence;
  const exp = data?.experience;
  const gw = data?.gateways;

  return (
    <div className="page-transition space-y-4">
      {/* 顶栏 */}
      <div className="card-highlight">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shadow-sm">
              🌐
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">全息孪生大屏</h2>
              <p className="text-xs text-gray-400">三主义一体活循环 · 实时经营视图</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              实时
            </span>
            <span className="text-gray-400">{lastUpdated.toLocaleTimeString('zh-CN')}</span>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={fetchData}>刷新</button>
          </div>
        </div>
      </div>

      {/* 三主义活循环 === */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-800 mb-4">
          🔄 三主义活循环
          <span className="ml-2 text-[10px] text-gray-400 font-normal">
            {data?.uns.total_events || 0} 总线事件 · {exp?.total_records || 0} 经验记录 · {kg?.total_proposals || 0} KG 提议
          </span>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {THREE_DOCTRINES.map((d) => (
            <div key={d.name} className={`p-4 rounded-xl border-l-4 ${d.color} bg-gray-50/50`}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{d.icon}</span>
                <div>
                  <p className="text-sm font-semibold text-gray-800">{d.name}</p>
                  <p className="text-[10px] text-gray-400">{d.desc}</p>
                </div>
              </div>
              <div className="text-[11px] text-gray-500 space-y-1">
                {d.name === '连接主义' && (
                  <>
                    <div className="flex justify-between"><span>UNS 通道</span><span className="font-mono">{Object.keys(channelCounts).length}</span></div>
                    <div className="flex justify-between"><span>隐性捕获</span><span className="font-mono">{exp?.tacit_captures || 0}</span></div>
                  </>
                )}
                {d.name === '符号主义' && (
                  <>
                    <div className="flex justify-between"><span>KG 提议总数</span><span className="font-mono">{kg?.total_proposals || 0}</span></div>
                    <div className="flex justify-between"><span>待审批</span><span className="font-mono">{kg?.drafts || 0}</span></div>
                    <div className="flex justify-between"><span>已 validated</span><span className="font-mono">{kg?.validated || 0}</span></div>
                    <div className="flex justify-between"><span>需复审</span><span className="font-mono">{kg?.needs_review || 0}</span></div>
                    <div className="flex justify-between"><span>纠错提议</span><span className="font-mono">{kg?.corrections || 0}</span></div>
                  </>
                )}
                {d.name === '行为主义' && (
                  <>
                    <div className="flex justify-between"><span>后果校验</span><span className="font-mono">{con?.stats.total_consequences || 0}</span></div>
                    <div className="flex justify-between"><span>合规(validated)</span><span className="font-mono">{con?.stats.validated || 0}</span></div>
                    <div className="flex justify-between"><span>矛盾(contradicted)</span><span className="font-mono">{con?.stats.contradicted || 0}</span></div>
                    <div className="flex justify-between"><span>合规率</span><span className="font-mono">{((con?.stats.match_rate || 0) * 100).toFixed(1)}%</span></div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 统计卡片 === */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon="🛰️" label="接入通道" value={Object.keys(channelCounts).length} sub="五路归一" color="bg-blue-50" />
        <StatCard icon="📊" label="KG 待审批" value={kg?.drafts || 0} sub={`${kg?.corrections || 0} 纠错待审`} color="bg-violet-50" />
        <StatCard icon="🔄" label="后果校验" value={con?.stats.total_consequences || 0} sub={`${((con?.stats.match_rate || 0) * 100).toFixed(0)}% 合规率`} color="bg-emerald-50" />
        <StatCard icon="🧠" label="经验记录" value={exp?.total_records || 0} sub={`${exp?.outcomes || 0} 后果反馈`} color="bg-amber-50" />
      </div>

      {/* 网关状态 + 通道分布 === */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">🛰️ 网关连接状态</h3>
          {gw && Object.keys(gw).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(gw).map(([name, status]: [string, any]) => (
                <div key={name} className="flex items-center gap-3 p-2 rounded-lg bg-gray-50 border border-gray-100">
                  <span className={`w-2 h-2 rounded-full ${status.running ? 'bg-green-500' : 'bg-red-400'}`} />
                  <span className="text-xs font-medium text-gray-700 w-20">{name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${status.running ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                    {status.running ? '运行中' : '已停止'}
                  </span>
                  <span className="text-[10px] text-gray-400 ml-auto">
                    {status.mode ? `模式: ${status.mode}` : ''}
                    {status.connected !== undefined ? (status.connected ? '· 已连接' : '· 模拟') : ''}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400 text-center py-6">网关管理器尚未初始化</p>
          )}
        </div>

        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">📡 UNS 通道分布</h3>
          <div className="space-y-2.5">
            {Object.entries(channelCounts).map(([ch, cnt]) => (
              <div key={ch} className="flex items-center gap-2">
                <span className="text-sm">{CHANNEL_ICONS[ch] || '📨'}</span>
                <span className="text-xs text-gray-600 w-16">{ch}</span>
                <div className="flex-1 h-2.5 rounded-full bg-gray-100 overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${
                    ch === 'gateway' ? 'bg-blue-500' :
                    ch === 'system' ? 'bg-green-500' :
                    ch === 'human' ? 'bg-purple-500' :
                    ch === 'social' ? 'bg-orange-500' :
                    ch === 'meeting' ? 'bg-pink-500' :
                    ch === 'collab' ? 'bg-cyan-500' : 'bg-gray-400'
                  }`}
                    style={{ width: `${Math.min(100, (cnt / Math.max(...Object.values(channelCounts))) * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-gray-500 w-10 text-right">{cnt}</span>
              </div>
            ))}
            {Object.keys(channelCounts).length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">暂无通道事件</p>
            )}
          </div>
        </div>
      </div>

      {/* UNS 事件流 === */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">📨 UNS ��时事件流</h3>
          <span className="text-[10px] text-gray-400">最近 {data?.uns.recent_events?.length || 0} 条</span>
        </div>
        <div className="max-h-60 overflow-y-auto space-y-1">
          {(data?.uns.recent_events || []).slice().reverse().map((ev, i) => (
            <EventRow key={ev.id || i} ev={ev} i={i} />
          ))}
          {(data?.uns.recent_events || []).length === 0 && (
            <p className="text-xs text-gray-400 text-center py-6">暂无事件，启动 Agent 即可看到实时流</p>
          )}
        </div>
      </div>

      {/* KG 审批管线和最近事实 === */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">🕸️ KG 事实管线</h3>
          <div className="space-y-2">
            <TwoColorBar value={kg?.drafts || 0} total={kg?.total_proposals || 1} label="待审批" colorA="bg-amber-400" colorB="bg-gray-200" />
            <TwoColorBar value={kg?.validated || 0} total={kg?.total_proposals || 1} label="已验证" colorA="bg-green-500" colorB="bg-gray-200" />
            <TwoColorBar value={kg?.needs_review || 0} total={kg?.total_proposals || 1} label="需复审" colorA="bg-red-400" colorB="bg-gray-200" />
            <TwoColorBar value={kg?.corrections || 0} total={kg?.total_proposals || 1} label="纠错" colorA="bg-violet-400" colorB="bg-gray-200" />
          </div>
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">💡 最近 KG 提议</h3>
          <div className="max-h-36 overflow-y-auto space-y-1.5">
            {(kg?.recent_proposals || []).slice(-8).reverse().map((p: any, i: number) => (
              <div key={p.id || i} className="flex items-center gap-2 text-[11px] p-1.5 rounded bg-gray-50">
                <span className={`w-1.5 h-1.5 rounded-full ${
                  p.status === 'validated' ? 'bg-green-500' :
                  p.status === 'approved' ? 'bg-blue-500' :
                  p.status === 'draft' ? 'bg-amber-400' :
                  p.status === 'needs_review' ? 'bg-red-400' : 'bg-gray-300'
                }`} />
                <span className="text-gray-600 truncate max-w-[100px]">{p.subject}</span>
                <span className="text-gray-300">—</span>
                <span className="text-gray-600 truncate max-w-[80px]">{p.predicate}</span>
                <span className="text-gray-300">→</span>
                <span className="text-gray-600 truncate flex-1">{p.object_val}</span>
                <span className={`text-[10px] px-1 py-0.5 rounded ${
                  p.status === 'validated' ? 'bg-green-100 text-green-600' :
                  p.status === 'draft' ? 'bg-amber-100 text-amber-600' :
                  p.status === 'needs_review' ? 'bg-red-100 text-red-600' : 'bg-gray-100'
                }`}>{p.status}</span>
              </div>
            ))}
            {(kg?.recent_proposals || []).length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">暂无 KG 事实提议</p>
            )}
          </div>
        </div>
      </div>

      {/* 蓝弧闭环统计 === */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">
          🔵 蓝弧闭环 · 执行后果校验
          <span className="ml-2 text-[10px] text-gray-400 font-normal">
            pending {con?.stats.pending_outcomes || 0} 待定
          </span>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
            <p className="text-[10px] text-emerald-600 font-medium mb-1">✅ 后果验证</p>
            <p className="text-2xl font-bold text-emerald-700">{con?.stats.validated || 0}</p>
            <p className="text-[10px] text-emerald-500">预期匹配 · 符号置信度提升</p>
          </div>
          <div className="p-3 rounded-lg bg-red-50 border border-red-100">
            <p className="text-[10px] text-red-600 font-medium mb-1">❌ 后果矛盾</p>
            <p className="text-2xl font-bold text-red-700">{con?.stats.contradicted || 0}</p>
            <p className="text-[10px] text-red-500">预期不匹配 · 触发纠错或复审</p>
          </div>
          <div className="p-3 rounded-lg bg-violet-50 border border-violet-100">
            <p className="text-[10px] text-violet-600 font-medium mb-1">📊 合规率</p>
            <p className="text-2xl font-bold text-violet-700">{((con?.stats.match_rate || 0) * 100).toFixed(1)}%</p>
            <p className="text-[10px] text-violet-500">总计 {con?.stats.total_consequences || 0} 次校验</p>
          </div>
        </div>
      </div>

      {/* 底部记录 */}
      <div className="text-center text-[10px] text-gray-300 py-2">
        智衍 EvolvIQ · 全息孪生大屏 · 每 5s 自动刷新 · 最后更新 {lastUpdated.toLocaleString('zh-CN')}
      </div>
    </div>
  );
}
