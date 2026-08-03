/**
 * 研究案例库（#426 独立页）—— 加强版（2026-08-02）
 *
 * 两大区块：
 * ① 我的绑定案例（仅 research_case 租户，如 telecom / semicon 登录后可见"自家数据"）：
 *    消费 /cases/my —— 公开披露事实(disclosure_facts) + 推演结论(derived_insights)，
 *    让"破例直接实例化"的租户进来就能看本行业推演数据。
 * ② 研究案例库（公开匿名）：消费 /cases/library —— 4 个行业标杆案例卡片 + 详情抽屉。
 *
 * 加强版要点：
 *  - 详情抽屉放行 disclosure_facts + derived_insights（无真名，对外匿名合规）
 *  - 列表卡片加 fact/insight 计数角标 + status 徽标 + 行业色条
 *  - 推演按 value_judgment 排序 + dimension 着色 + assertion_type 标签
 *
 * 🔴 匿名铁律：本页绝不出现 real_anchor 真名；仅展示 subject_anon / 公开披露推演。
 * 🔴 鉴权守卫：挂载即 fetch 的 effect 必须 gate 在 token 存在（否则 401 悬空态）。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiUrl, authHeaders, getToken } from '../api/client';

interface CaseItem {
  case_id: string;
  subject_anon: string;
  industry: string;
  status?: string;
  updated_at?: string;
  fact_count?: number;
  insight_count?: number;
  scope?: string;            // global = 全球化锚（2026-08-03）
  value_chain_node?: string; // 价值链节点（制造/设备…）
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
  assertion_type?: 'descriptive' | 'predictive' | string;  // 描述性/前瞻性
  value_judgment?: 'high' | 'medium' | 'low' | string;  // 价值权重
}
interface MyCaseCase {
  case_id?: string;
  subject_anon?: string;
  industry?: string;
  recommended_interfaces?: string[];
  teaching_notes_anon?: string;
  pilot_scenario?: { scenario: string; label: string; agents?: string[]; note?: string } | null;
  disclosure_facts?: { source: string; fiscal_year: number; facts: DisclosureFact[] };
  derived_insights?: DerivedInsight[];
}
interface MyCase {
  bound: boolean;
  tenant_id?: string;
  tenant_kind?: string;
  data_origin?: string;
  disclaimer?: string;
  // 🔴 后端 /cases/my 将案例数据嵌套在 case 字段下（见 src/runtime/api/library.py get_my_case）
  case?: MyCaseCase;
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
  // 加强版：详情端点也放行事实+结论
  disclosure_facts?: { source: string; fiscal_year: number; facts: DisclosureFact[] };
  derived_insights?: DerivedInsight[];
}

const DIM_LABEL: Record<string, string> = {
  strategy: '战略', supply_chain: '供应链', compliance: '合规',
  cost: '成本', equipment: '设备', energy: '能耗',
};

// 维度配色（与 Tailwind 色板一致，单色调蓝主色，差异靠 bg-300/text-700 区分）
const DIM_COLOR: Record<string, { bg: string; text: string; ring: string }> = {
  strategy:    { bg: 'bg-blue-100',   text: 'text-blue-800',   ring: 'ring-blue-200' },
  supply_chain:{ bg: 'bg-sky-100',    text: 'text-sky-800',    ring: 'ring-sky-200' },
  compliance:  { bg: 'bg-indigo-100', text: 'text-indigo-800', ring: 'ring-indigo-200' },
  cost:        { bg: 'bg-zhiyan-100', text: 'text-zhiyan-800', ring: 'ring-zhiyan-200' },
  equipment:   { bg: 'bg-blue-50',    text: 'text-blue-700',   ring: 'ring-blue-100' },
  energy:      { bg: 'bg-cyan-100',   text: 'text-cyan-800',   ring: 'ring-cyan-200' },
};

// 价值权重排序：high 在前
const JUDGMENT_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

// 行业色条映射（侧栏色）—— 取主色蓝的 4 档变体做行业区分
function industryBarClass(industry: string): string {
  const head = industry.replace(/\s/g, '').slice(0, 2);
  if (head.includes('半导体')) return 'bg-zhiyan-500';
  if (head.includes('通讯') || head.includes('通信')) return 'bg-blue-400';
  if (head.includes('消费电子') || head.includes('3C')) return 'bg-sky-500';
  if (head.includes('新能源') || head.includes('动力')) return 'bg-cyan-500';
  return 'bg-gray-400';
}

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  active:    { label: '活跃', cls: 'bg-green-100 text-green-700' },
  completed: { label: '完结', cls: 'bg-gray-100 text-gray-600' },
  draft:     { label: '草稿', cls: 'bg-amber-100 text-amber-700' },
};

function sortInsights(arr: DerivedInsight[]): DerivedInsight[] {
  return [...arr].sort((a, b) => {
    const ra = JUDGMENT_RANK[a.value_judgment ?? ''] ?? 9;
    const rb = JUDGMENT_RANK[b.value_judgment ?? ''] ?? 9;
    if (ra !== rb) return ra - rb;
    // 同权重：预测性(predictive) 排在描述性(descriptive)前
    if ((a.assertion_type === 'predictive') !== (b.assertion_type === 'predictive')) {
      return a.assertion_type === 'predictive' ? -1 : 1;
    }
    return 0;
  });
}

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

  // 加强版：详情抽屉里的推演按权重排序，避免重复计算
  const sortedInsights = useMemo<DerivedInsight[]>(
    () => (detail?.derived_insights ? sortInsights(detail.derived_insights) : []),
    [detail?.derived_insights]
  );

  // 加强版：详情块右上角的 status 徽标
  const detailStatus = useMemo(
    () => (detail?.status ? STATUS_LABEL[detail.status] || null : null),
    [detail?.status]
  );

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
              我的绑定案例 · {myCase.case?.subject_anon}
            </h3>
            <span className="text-[11px] px-2 py-1 rounded-full bg-amber-50 text-amber-700 font-medium">
              研究案例租户 · 未签约
            </span>
          </div>
          <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            ⚠️ {myCase.disclaimer || '本视图数据来源于公开披露信息推演，非企业内部真实数据，本租户亦非签约客户。'}
          </div>

          {myCase.case?.disclosure_facts && (
            <div>
              <div className="text-xs text-gray-400 mb-1">
                公开披露事实（{myCase.case.disclosure_facts.source}）
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
                    {myCase.case.disclosure_facts.facts.map((f, i) => (
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

          {myCase.case?.derived_insights && myCase.case.derived_insights.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-gray-500 font-medium">
                💡 推演结论（{myCase.case.derived_insights.length}）· 按价值权重排序
              </div>
              {sortInsights(myCase.case.derived_insights).map((ins, i) => {
                const dimCls = DIM_COLOR[ins.dimension] || DIM_COLOR.equipment;
                const isPredict = ins.assertion_type === 'predictive';
                const isHigh = ins.value_judgment === 'high';
                return (
                  <div key={i} className={`relative border ${dimCls.ring} bg-white rounded-lg p-3 ${isHigh ? 'shadow-sm' : ''}`}>
                    {isHigh && <span className={`absolute left-0 top-0 bottom-0 w-1 ${dimCls.bg.replace('-100', '-500')}`} aria-hidden />}
                    <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${dimCls.bg} ${dimCls.text}`}>
                        {DIM_LABEL[ins.dimension] || ins.dimension}
                      </span>
                      {isPredict && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium">
                          🔮 前瞻预判
                        </span>
                      )}
                      {isHigh && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-50 text-red-700 font-medium">
                          ⚡ 高价值
                        </span>
                      )}
                      {ins.value_judgment === 'medium' && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                          中价值
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-900 font-medium leading-relaxed">{ins.claim}</div>
                    <div className="text-xs text-gray-500 mt-1 leading-relaxed">{ins.rationale}</div>
                    {ins.key_figures && ins.key_figures.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {ins.key_figures.map((k, j) => (
                          <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 font-medium">{k}</span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* ② 研究案例库（公开匿名） */}
      <section className="space-y-2">
        <h3 className="font-semibold text-gray-800">研究案例库（公开匿名 · {cases.length} 个）</h3>
        {busy && <div className="text-xs text-gray-400">加载中…</div>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {cases.map((c) => {
            const status = STATUS_LABEL[c.status || ''] || null;
            const fc = c.fact_count ?? 0;
            const ic = c.insight_count ?? 0;
            return (
              <button
                key={c.case_id}
                onClick={() => openDetail(c.case_id)}
                className="relative text-left bg-white rounded-xl shadow-sm border border-gray-100 p-4 pl-5 hover:border-zhiyan-300 hover:shadow-md transition-all space-y-1.5 overflow-hidden"
              >
                {/* 行业色条 */}
                <span className={`absolute left-0 top-0 bottom-0 w-1 ${industryBarClass(c.industry)}`} aria-hidden />
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900">{c.subject_anon}</span>
                  <div className="flex items-center gap-1">
                    {status && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${status.cls}`}>{status.label}</span>
                    )}
                    {c.case_id === activeCaseId && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zhiyan-100 text-zhiyan-700">默认案例</span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-gray-500">{c.industry}</div>
                {/* 加强版：事实/结论计数角标 */}
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                  {c.scope === 'global' && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                      🌍 全球{c.value_chain_node ? ` · ${c.value_chain_node.split('（')[0]}` : ''}
                    </span>
                  )}
                  {fc > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100">
                      📊 事实 {fc}
                    </span>
                  )}
                  {ic > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zhiyan-50 text-zhiyan-700 border border-zhiyan-100">
                      💡 结论 {ic}
                    </span>
                  )}
                  {(fc === 0 && ic === 0) && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-50 text-gray-500 border border-gray-100">
                      暂无数据
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-gray-400">更新于 {c.updated_at || '—'} · 点击查看详情</div>
              </button>
            );
          })}
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
              <div className="space-y-4">
                {/* 头部：标题 + 行业色条 */}
                <div className={`relative pl-3 border-l-4 ${industryBarClass(detail.industry)} rounded`}>
                  <div className="font-medium text-gray-900">{detail.subject_anon}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{detail.industry}</div>
                  {detailStatus && (
                    <div className="mt-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${detailStatus.cls}`}>{detailStatus.label}</span>
                    </div>
                  )}
                </div>

                {detail.pilot_scenario && (
                  <div className="text-xs text-zhiyan-700 bg-zhiyan-50 border border-zhiyan-100 rounded-lg px-3 py-2">
                    🧪 试点场景 {detail.pilot_scenario.scenario}：{detail.pilot_scenario.label}
                    {detail.pilot_scenario.note ? ` · ${detail.pilot_scenario.note}` : ''}
                  </div>
                )}

                {/* 加强版：公开披露事实表 */}
                {detail.disclosure_facts?.facts && detail.disclosure_facts.facts.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 mb-1 font-medium">
                      📊 公开披露事实（{detail.disclosure_facts.facts.length}）
                      <span className="text-gray-400 font-normal ml-1">· {detail.disclosure_facts.source}</span>
                    </div>
                    <div className="overflow-x-auto border border-gray-100 rounded-lg">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-gray-500 text-left bg-gray-50">
                            <th className="py-1.5 px-2 font-normal">指标</th>
                            <th className="py-1.5 px-2 font-normal">数值</th>
                            <th className="py-1.5 px-2 font-normal">同比 / 说明</th>
                            <th className="py-1.5 px-2 font-normal text-right">占比</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.disclosure_facts.facts.map((f, i) => (
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

                {/* 加强版：推演结论（按权重排序 + 维度着色 + 预测标签） */}
                {sortedInsights && sortedInsights.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 mb-1.5 font-medium">
                      💡 推演结论（{sortedInsights.length}）· 按价值权重排序
                    </div>
                    <div className="space-y-2">
                      {sortedInsights.map((ins, i) => {
                        const dimCls = DIM_COLOR[ins.dimension] || DIM_COLOR.equipment;
                        const isPredict = ins.assertion_type === 'predictive';
                        const isHigh = ins.value_judgment === 'high';
                        return (
                          <div key={i} className={`relative border ${dimCls.ring} bg-white rounded-lg p-3 ${isHigh ? 'shadow-sm' : ''}`}>
                            {/* 高价值左侧色条 */}
                            {isHigh && <span className={`absolute left-0 top-0 bottom-0 w-1 ${dimCls.bg.replace('-100', '-500')}`} aria-hidden />}
                            <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${dimCls.bg} ${dimCls.text}`}>
                                {DIM_LABEL[ins.dimension] || ins.dimension}
                              </span>
                              {isPredict && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 font-medium">
                                  🔮 前瞻预判
                                </span>
                              )}
                              {isHigh && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-50 text-red-700 font-medium">
                                  ⚡ 高价值
                                </span>
                              )}
                              {ins.value_judgment === 'medium' && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                                  中价值
                                </span>
                              )}
                            </div>
                            <div className="text-sm text-gray-900 font-medium leading-relaxed">{ins.claim}</div>
                            <div className="text-xs text-gray-500 mt-1 leading-relaxed">{ins.rationale}</div>
                            {ins.key_figures && ins.key_figures.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1.5">
                                {ins.key_figures.map((k, j) => (
                                  <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 font-medium">{k}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 推荐接口（保留原功能） */}
                {detail.recommended_interfaces && detail.recommended_interfaces.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 mb-1 font-medium">🔌 推荐接口（{detail.recommended_interfaces.length}）</div>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.recommended_interfaces.map((it) => (
                        <span key={it} className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">{it}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 教学笔记（保留原功能） */}
                {detail.teaching_notes_anon && (
                  <div>
                    <div className="text-xs text-gray-500 mb-1 font-medium">📝 教学笔记</div>
                    <div className="text-sm text-gray-700 leading-relaxed bg-blue-50/40 border border-blue-100 rounded-lg p-3">
                      {detail.teaching_notes_anon}
                    </div>
                  </div>
                )}

                <div className="text-[11px] text-gray-400 pt-1 border-t border-gray-100">
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
