/**
 * 无感转型三圈解锁进度视图（S2-3，#310）
 *
 * 外圈（免费·环境感知）→ 中圈（接第 1 个内部数据源解锁）→ 内圈（私有化）。
 * F4 纪律：只呈现事实进度 + 下一步说明——不弹窗、不推销，相邻呈现。
 * 数据源：GET /environment/unlock-progress（含 quota 摘要，一次请求渲染全视图）。
 *
 * 铁律：所有请求经 client.ts authHeaders()；渲染在 App 的 ErrorBoundary 内。
 */
import { useState, useEffect } from 'react';
import { getUnlockProgress, UnlockProgressView, UnlockCircle, AgentRecommendation, authHeaders, apiUrl } from '../api/client';

interface AgentMeta {
  id: string;
  name: string;
  icon?: string;
}

const CIRCLE_STYLE: Record<string, { ring: string; badge: string; icon: string }> = {
  outer: { ring: 'border-emerald-300 bg-emerald-50', badge: 'bg-emerald-100 text-emerald-700', icon: '🌍' },
  middle: { ring: 'border-blue-300 bg-blue-50', badge: 'bg-blue-100 text-blue-700', icon: '🔗' },
  inner: { ring: 'border-purple-300 bg-purple-50', badge: 'bg-purple-100 text-purple-700', icon: '🏭' },
};

function QuotaBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  if (limit === null) {
    return (
      <div className="flex items-center gap-2 text-xs text-gray-600">
        <span className="w-20">{label}</span>
        <span className="text-emerald-600 font-medium">不限量</span>
      </div>
    );
  }
  const pct = Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  return (
    <div className="flex items-center gap-2 text-xs text-gray-600">
      <span className="w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${pct >= 100 ? 'bg-amber-500' : 'bg-blue-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-14 text-right tabular-nums">{used}/{limit}</span>
    </div>
  );
}

function CircleCard({
  circle,
  isCurrent,
  agentMeta,
}: {
  circle: UnlockCircle;
  isCurrent: boolean;
  agentMeta: Record<string, AgentMeta>;
}) {
  const [expanded, setExpanded] = useState(isCurrent);
  const st = CIRCLE_STYLE[circle.key] || CIRCLE_STYLE.outer;
  return (
    <div
      className={`rounded-xl border-2 p-4 transition ${
        circle.unlocked ? st.ring : 'border-gray-200 bg-gray-50 opacity-80'
      } ${isCurrent ? 'ring-2 ring-offset-1 ring-blue-400' : ''}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{st.icon}</span>
          <span className="font-semibold text-sm text-gray-800">{circle.label}</span>
          <span className={`text-[11px] px-2 py-0.5 rounded-full ${circle.unlocked ? st.badge : 'bg-gray-200 text-gray-500'}`}>
            {circle.unlocked ? (isCurrent ? '当前圈层' : '已解锁') : '🔒 未解锁'}
          </span>
        </div>
        <button
          className="text-xs text-blue-600 hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? '收起' : `${circle.agent_count} 个 agent`}
        </button>
      </div>
      <div className="mt-1.5 text-xs text-gray-500">{circle.requirement}</div>
      {expanded && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {circle.agents.map((id) => {
            const m = agentMeta[id];
            return (
              <span
                key={id}
                className={`text-[11px] px-2 py-1 rounded-lg border ${
                  circle.unlocked
                    ? 'bg-white border-gray-200 text-gray-700'
                    : 'bg-gray-100 border-gray-200 text-gray-400'
                }`}
                title={id}
              >
                {m?.icon ? `${m.icon} ` : ''}{m?.name || id}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function UnlockProgressPanel() {
  const [view, setView] = useState<UnlockProgressView | null>(null);
  const [agentMeta, setAgentMeta] = useState<Record<string, AgentMeta>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getUnlockProgress()
      .then((v) => alive && setView(v))
      .catch((e) => alive && setError(e?.message || String(e)));
    fetch(apiUrl('/agents'), { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive || !d?.agents) return;
        const map: Record<string, AgentMeta> = {};
        for (const a of d.agents) map[a.id] = { id: a.id, name: a.name, icon: a.icon };
        setAgentMeta(map);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  if (error) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 text-sm text-gray-500">
        解锁进度暂不可用：{error.slice(0, 120)}
      </div>
    );
  }
  if (!view) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 text-sm text-gray-400">
        解锁进度加载中…
      </div>
    );
  }

  const q = view.quota;
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-bold text-gray-800">🧭 无感转型 · 解锁进度</h3>
          <span className="text-xs text-gray-400">
            已解锁 {view.unlocked_agents}/{view.total_agents} 个 agent
          </span>
        </div>
        <div className="h-2 w-40 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-emerald-400 to-blue-500 rounded-full"
            style={{ width: `${Math.round((view.unlocked_agents / Math.max(view.total_agents, 1)) * 100)}%` }}
          />
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {view.circles.map((c) => (
          <CircleCard
            key={c.key}
            circle={c}
            isCurrent={c.key === view.current_circle}
            agentMeta={agentMeta}
          />
        ))}
      </div>

      {/* 下一步：事实说明，相邻呈现（F4 纪律：不弹窗不推销） */}
      <div className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-3 text-xs text-blue-800 leading-relaxed">
        <span className="font-semibold">下一步：</span>{view.next_step}
      </div>

      {/* S3-5 行为导航④：为你推荐的下一步（融入三圈视图，相邻呈现；F4 价值句式 + 透明标注） */}
      {view.recommended_next && view.recommended_next.length > 0 && (
        <div className="rounded-xl bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-100 px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm">💡</span>
            <h4 className="font-semibold text-gray-800 text-sm">为你推荐的下一步</h4>
            <span className="text-[11px] text-gray-400">基于你最近的使用习惯</span>
          </div>
          <div className="space-y-2">
            {view.recommended_next.map((rec: AgentRecommendation) => {
              const st = CIRCLE_STYLE[rec.circle] || CIRCLE_STYLE.middle;
              return (
                <div
                  key={rec.agent}
                  className="rounded-lg bg-white/80 border border-indigo-100 px-3 py-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[13px] text-gray-800 leading-snug font-medium">
                      {rec.value_sentence}
                    </p>
                    <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full ${st.badge}`}>
                      {st.icon} {rec.label}
                    </span>
                  </div>
                  <details className="mt-1">
                    <summary className="text-[11px] text-indigo-500 cursor-pointer select-none">
                      为什么推荐（透明）
                    </summary>
                    <ul className="mt-1 space-y-0.5">
                      {rec.reasons.map((r, i) => (
                        <li key={i} className="text-[11px] text-gray-500 leading-snug">· {r}</li>
                      ))}
                    </ul>
                  </details>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-[11px] text-gray-400">
            完成上方「下一步」即可解锁这些智能体——全程无感，不打断你的日常使用。
          </p>
        </div>
      )}

      {q && !q.unlimited && (
        <div className="space-y-1.5 pt-1 border-t border-gray-100">
          <div className="text-xs font-medium text-gray-500 pt-2">免费额度</div>
          <QuotaBar label="订阅源" used={q.metrics.env_sources?.used ?? 0} limit={q.metrics.env_sources?.limit ?? null} />
          <QuotaBar label="今日信号" used={q.metrics.daily_signals?.used ?? 0} limit={q.metrics.daily_signals?.limit ?? null} />
          <QuotaBar label="本月解读" used={q.metrics.monthly_insights?.used ?? 0} limit={q.metrics.monthly_insights?.limit ?? null} />
        </div>
      )}
      {q && q.unlimited && (
        <div className="text-xs text-emerald-600 pt-2 border-t border-gray-100">
          ✓ 当前租户不受免费额度限制
        </div>
      )}
    </div>
  );
}
