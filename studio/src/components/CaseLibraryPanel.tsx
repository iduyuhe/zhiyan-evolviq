/**
 * 研究案例库（#426 独立页）
 *
 * 两大区块：
 * ① 我的绑定案例（仅 research_case 租户，如 telecom / semicon 登录后可见"自家数据"）：
 *    消费 /cases/my —— 公开披露事实(disclosure_facts) + 推演结论(derived_insights)，
 *    让"破例直接实例化"的租户进来就能看本行业推演数据。
 * ② 研究案例库（公开匿名）：消费 /cases/library —— 4 个行业标杆案例卡片 + 详情抽屉。
 *
 * 🔴 匿名铁律：本页绝不出现 real_anchor 真名；仅展示 subject_anon / 公开披露推演。
 * 🔴 鉴权守卫：挂载即 fetch 的 effect 必须 gate 在 token 存在（否则 401 悬空态）。
 */
import { useCallback, useEffect, useState } from 'react';
import { apiUrl, authHeaders, getToken } from '../api/client';

interface CaseItem {
  case_id: string;
  subject_anon: string;
  industry: string;
  status?: string;
  updated_at?: string;
}
interface DisclosureFact {
  metric: string;
  value: string;
  yoy?: string;
  share?: string;
}
interface DerivedInsight {
  dimension: string;
  claim: string;
  rationale: string;
  key_figures?: string[];
}
interface MyCase {
  bound: boolean;
  subject_anon?: string;
  industry?: string;
  disclaimer?: string;
  disclosure_facts?: { source: string; fiscal_year: number; facts: DisclosureFact[] };
  derived_insights?: DerivedInsight[];
}
interface CaseDetail {
  case_id: string;
  subject_anon: string;
  industry: string;
  recommended_interfaces?: string[];
  teaching_notes_anon?: string;
  pilot_scenario?: { scenario: string; label: string; agents?: string[]; note?: string } | null;
  status?: string;
  updated_at?: string;
}

const DIM_LABEL: Record<string, string> = {
  strategy: '战略', supply_chain: '供应链', compliance: '合规',
  cost: '成本', equipment: '设备', energy: '能耗',
};

export default function CaseLibraryPanel() {
  const [myCase, setMyCase] = useState<MyCase | null>(null);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [busy, setBusy] = useState(true);
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    if (!getToken()) return; // 🔴 鉴权守卫
    setBusy(true);
    setMsg('');
    try {
      const [libR, myR] = await Promise.all([
        fetch(apiUrl('/cases/library'), { headers: authHeaders() }),
        fetch(apiUrl('/cases/my'), { headers: authHeaders() }),
      ]);
      if (!libR.ok) throw new Error(`案例库加载失败 (${libR.status})`);
      const lib = await libR.json();
      setCases(lib.cases || []);
      setActiveCaseId(lib.active_case_id || null);
      if (myR.ok) {
        const my = await myR.json();
        if (my && my.bound) setMyCase(my);
      }
    } catch (e) {
      setMsg('❌ ' + (e instanceof Error ? e.message : '加载失败'));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openDetail = useCallback(async (caseId: string) => {
    setActiveCaseId(caseId);
    setLoadingDetail(true);
    setDetail(null);
    try {
      const r = await fetch(apiUrl(`/cases/library/${caseId}`), { headers: authHeaders() });
      if (!r.ok) throw new Error(`详情加载失败 (${r.status})`);
      const d = await r.json();
      setDetail(d.case || null);
    } catch (e) {
      setMsg('❌ ' + (e instanceof Error ? e.message : '详情加载失败'));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span>📚</span> 研究案例库
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          基于公开披露信息推演 · 对外匿名 · 非真实客户数据 · 用于演示「研究案例范式」与获客教学
        </p>
      </div>

      {msg && <div className="text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">{msg}</div>}

      {/* ① 我的绑定案例（research_case 租户可见） */}
      {myCase?.bound && (
        <section className="bg-white rounded-xl shadow-sm border border-zhiyan-100 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-800">
              我的绑定案例 · {myCase.subject_anon}
            </h3>
            <span className="text-[11px] px-2 py-1 rounded-full bg-amber-50 text-amber-700 font-medium">
              研究案例租户 · 未签约
            </span>
          </div>
          <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            ⚠️ {myCase.disclaimer || '本视图数据来源于公开披露信息推演，非企业内部真实数据，本租户亦非签约客户。'}
          </div>

          {myCase.disclosure_facts && (
            <div>
              <div className="text-xs text-gray-400 mb-1">
                公开披露事实（{myCase.disclosure_facts.source}）
              </div>
              <div className="overflow-x-auto border border-gray-100 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 text-left bg-gray-50">
                      <th className="py-1.5 px-2 font-normal">指标</th>
                      <th className="py-1.5 px-2 font-normal">数值</th>
                      <th className="py-1.5 px-2 font-normal">同比 / 说明</th>
                      <th className="py-1.5 px-2 font-normal text-right">占比</th>
                    </tr>
                  </thead>
                  <tbody>
                    {myCase.disclosure_facts.facts.map((f, i) => (
                      <tr key={i} className="border-t border-gray-100 text-gray-700">
                        <td className="py-1.5 px-2 whitespace-nowrap">{f.metric}</td>
                        <td className="py-1.5 px-2 font-medium text-gray-900">{f.value}</td>
                        <td className="py-1.5 px-2 text-gray-500">{f.yoy || '—'}</td>
                        <td className="py-1.5 px-2 text-right text-gray-500">{f.share || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {myCase.derived_insights && myCase.derived_insights.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-gray-400">推演结论（{myCase.derived_insights.length}）</div>
              {myCase.derived_insights.map((ins, i) => (
                <div key={i} className="border border-zhiyan-100 bg-zhiyan-50/40 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zhiyan-100 text-zhiyan-700 font-medium">
                      {DIM_LABEL[ins.dimension] || ins.dimension}
                    </span>
                  </div>
                  <div className="text-sm text-gray-800">{ins.claim}</div>
                  <div className="text-xs text-gray-500 mt-1">{ins.rationale}</div>
                  {ins.key_figures && ins.key_figures.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {ins.key_figures.map((k, j) => (
                        <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{k}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ② 研究案例库（公开匿名） */}
      <section className="space-y-2">
        <h3 className="font-semibold text-gray-800">研究案例库（公开匿名 · {cases.length} 个）</h3>
        {busy && <div className="text-xs text-gray-400">加载中…</div>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {cases.map((c) => (
            <button
              key={c.case_id}
              onClick={() => openDetail(c.case_id)}
              className="text-left bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:border-zhiyan-300 hover:shadow-md transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{c.subject_anon}</span>
                {c.case_id === activeCaseId && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zhiyan-100 text-zhiyan-700">默认案例</span>
                )}
              </div>
              <div className="text-xs text-gray-500">{c.industry}</div>
              <div className="text-[11px] text-gray-400">更新于 {c.updated_at || '—'} · 点击查看推荐接口与教学笔记</div>
            </button>
          ))}
        </div>
      </section>

      {/* 详情抽屉 */}
      {activeCaseId && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/30" onClick={() => setActiveCaseId(null)} />
          <div className="w-full max-w-md bg-white h-full overflow-y-auto shadow-xl p-5 space-y-4">
            <div className="flex items-center justify-between sticky top-0 bg-white pb-2">
              <span className="text-sm font-semibold text-gray-900">案例详情</span>
              <button onClick={() => setActiveCaseId(null)} className="text-gray-400 text-xl leading-none px-2">×</button>
            </div>
            {loadingDetail && <div className="text-xs text-gray-400">加载中…</div>}
            {detail && (
              <div className="space-y-3">
                <div>
                  <div className="font-medium text-gray-900">{detail.subject_anon}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{detail.industry}</div>
                </div>
                {detail.pilot_scenario && (
                  <div className="text-xs text-zhiyan-700 bg-zhiyan-50 border border-zhiyan-100 rounded-lg px-3 py-2">
                    🧪 试点场景 {detail.pilot_scenario.scenario}：{detail.pilot_scenario.label}
                    {detail.pilot_scenario.note ? ` · ${detail.pilot_scenario.note}` : ''}
                  </div>
                )}
                {detail.recommended_interfaces && detail.recommended_interfaces.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-400 mb-1">推荐接口</div>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.recommended_interfaces.map((it) => (
                        <span key={it} className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{it}</span>
                      ))}
                    </div>
                  </div>
                )}
                {detail.teaching_notes_anon && (
                  <div className="text-sm text-gray-700 leading-relaxed">{detail.teaching_notes_anon}</div>
                )}
                <div className="text-[11px] text-gray-400">
                  更新于 {detail.updated_at || '—'} · 对外匿名视图，不含真实企业名称
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
