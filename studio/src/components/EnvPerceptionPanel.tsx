/**
 * 环境感知第⑥路 · 租户订阅规则面板（S2 v30.5 β）
 *
 * 「抓取共享、语义隔离」消费层的可视化配置：
 *  A. 环境源状态（三类源 live/simulated + 连通性测试 + 立即拉取）
 *  B. 订阅规则编辑（源开关 / credibility 准入档 / 关键词 include+exclude / 轮询频率）
 *     - 先测试后保存闸门：后端 409 → 提示可强制保存；402 → 免费额度文案（信任爬梯③）
 *  C. 我的环境信号流（平台池 × 本租户规则过滤后的可见流）
 *
 * 铁律：所有请求经 client.ts authHeaders()；渲染在 App 的 ErrorBoundary 内。
 */
import { useState, useEffect, useCallback } from 'react';
import {
  getEnvironmentOverview,
  testEnvSource,
  listEnvSubscriptions,
  saveEnvSubscription,
  deleteEnvSubscription,
  getEnvFeed,
  getEnvSourceRecommendations,
  pullEnvSources,
  trackBehavior,
  EnvSourceStatus,
  EnvSubscription,
  EnvSignal,
  EnvSourceRecommendation,
  postEnvRecommendationFeedback,
  getEnvFeedbackStatus,
  getEnvGrowthProfile,
  getEnvEvolution,
  postEnvFeedback,
  ConnectivityTestResult,
  type FeedbackStatusItem,
  type GrowthProfile,
  type EvolutionNotification,
  type FeedbackKind,
} from '../api/client';

const CRED_LEVELS = [
  { value: 'general', label: '一般（全收）' },
  { value: 'authoritative', label: '权威及以上' },
  { value: 'official', label: '仅官方' },
] as const;

const POLL_OPTIONS = [
  { value: 900, label: '15 分钟' },
  { value: 3600, label: '1 小时' },
  { value: 14400, label: '4 小时' },
  { value: 86400, label: '每天' },
] as const;

function CredBadge({ c }: { c?: string }) {
  const map: Record<string, string> = {
    official: 'bg-green-100 text-green-700',
    authoritative: 'bg-blue-100 text-blue-700',
    general: 'bg-gray-100 text-gray-600',
  };
  const label: Record<string, string> = {
    official: '官方', authoritative: '权威', general: '一般',
  };
  const k = c || 'general';
  return (
    <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${map[k] || map.general}`}>
      {label[k] || k}
    </span>
  );
}

/** 单个源的规则编辑卡片 */
function SubscriptionCard({
  sub,
  source,
  onSaved,
  quotaFull,
}: {
  sub: EnvSubscription;
  source?: EnvSourceStatus;
  onSaved: () => void;
  quotaFull: boolean;
}) {
  const [enabled, setEnabled] = useState(sub.enabled);
  const [credMin, setCredMin] = useState(sub.credibility_min);
  const [kwInc, setKwInc] = useState(sub.keywords_include.join(', '));
  const [kwExc, setKwExc] = useState(sub.keywords_exclude.join(', '));
  const [poll, setPoll] = useState(sub.poll_interval_sec);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectivityTestResult | null>(null);
  const [msg, setMsg] = useState('');
  const [needForce, setNeedForce] = useState(false);

  useEffect(() => {
    setEnabled(sub.enabled);
    setCredMin(sub.credibility_min);
    setKwInc(sub.keywords_include.join(', '));
    setKwExc(sub.keywords_exclude.join(', '));
    setPoll(sub.poll_interval_sec);
  }, [sub]);

  const parseKw = (s: string) =>
    s.split(/[,，;；]/).map((x) => x.trim()).filter(Boolean);

  const onTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await testEnvSource(sub.source_name));
    } catch (e) {
      setTestResult({ ok: false, detail: (e as Error).message });
    } finally {
      setTesting(false);
    }
  };

  const onSave = async (force = false) => {
    setSaving(true);
    setMsg('');
    setNeedForce(false);
    try {
      const r = await saveEnvSubscription(sub.source_name, {
        enabled,
        credibility_min: credMin,
        keywords_include: parseKw(kwInc),
        keywords_exclude: parseKw(kwExc),
        poll_interval_sec: poll,
        force,
      });
      if (r.test) setTestResult(r.test);
      setMsg('✅ 规则已保存' + (force ? '（强制）' : ''));
      onSaved();
    } catch (e) {
      const err = e as Error & { status?: number };
      if (err.status === 402) {
        setMsg('💡 ' + extractDetail(err.message));
      } else if (err.status === 409) {
        setMsg('⚠️ 源连通性测试未通过，未保存。可点「强制保存」（信号可能延迟）。');
        setNeedForce(true);
      } else {
        setMsg('保存失败：' + extractDetail(err.message));
      }
    } finally {
      setSaving(false);
    }
  };

  const onReset = async () => {
    setSaving(true);
    setMsg('');
    try {
      await deleteEnvSubscription(sub.source_name);
      setMsg('已恢复行业默认模板');
      onSaved();
    } catch (e) {
      setMsg('操作失败：' + extractDetail((e as Error).message));
    } finally {
      setSaving(false);
    }
  };

  const disableToggleOn = !enabled && quotaFull; // 想开启但额度已满

  return (
    <div className="border border-gray-100 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-800">{source?.label || sub.source_name}</span>
          <CredBadge c={source?.credibility} />
          {source && (
            <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${source.mode === 'live' ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'}`}>
              {source.mode === 'live' ? '实时' : '模拟'}
            </span>
          )}
          {sub.is_default && (
            <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-gray-50 text-gray-400">默认模板</span>
          )}
        </div>
        <label className="inline-flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            disabled={disableToggleOn}
            onChange={(e) => setEnabled(e.target.checked)}
            className="accent-zhiyan-600"
          />
          <span className="text-gray-600">{enabled ? '订阅中' : '已关闭'}</span>
        </label>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <label className="text-xs text-gray-500">
          可信度准入
          <select
            className="mt-0.5 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-gray-700"
            value={credMin}
            onChange={(e) => setCredMin(e.target.value)}
          >
            {CRED_LEVELS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-gray-500">
          轮询频率
          <select
            className="mt-0.5 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-gray-700"
            value={poll}
            onChange={(e) => setPoll(Number(e.target.value))}
          >
            {POLL_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
            {!POLL_OPTIONS.some((p) => p.value === poll) && (
              <option value={poll}>{Math.round(poll / 60)} 分钟</option>
            )}
          </select>
        </label>
        <label className="text-xs text-gray-500">
          关注关键词（逗号分隔，留空=全收）
          <input
            className="mt-0.5 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
            placeholder="如：铜, 锂电, 数字化"
            value={kwInc}
            onChange={(e) => setKwInc(e.target.value)}
          />
        </label>
        <label className="text-xs text-gray-500">
          排除关键词
          <input
            className="mt-0.5 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
            placeholder="如：房地产"
            value={kwExc}
            onChange={(e) => setKwExc(e.target.value)}
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button className="btn-secondary text-xs" onClick={onTest} disabled={testing}>
          {testing ? '测试中…' : '测试源'}
        </button>
        <button className="btn-primary text-xs" onClick={() => onSave(false)} disabled={saving}>
          {saving ? '保存中…' : '测试通过再保存'}
        </button>
        {needForce && (
          <button className="text-xs px-2 py-1 rounded-lg bg-amber-100 text-amber-700 hover:bg-amber-200" onClick={() => onSave(true)} disabled={saving}>
            强制保存
          </button>
        )}
        {!sub.is_default && (
          <button className="text-xs text-gray-400 hover:text-gray-600 hover:underline" onClick={onReset} disabled={saving}>
            恢复默认
          </button>
        )}
        {testResult && (
          <span className={`text-xs px-2 py-0.5 rounded-full ${testResult.ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {testResult.ok ? '源可达' : '源异常'}
          </span>
        )}
      </div>
      {testResult?.detail && <p className="text-[11px] text-gray-400">{testResult.detail}</p>}
      {msg && (
        <p className={`text-xs ${msg.startsWith('✅') ? 'text-green-600' : msg.startsWith('💡') ? 'text-zhiyan-600' : 'text-red-600'}`}>
          {msg}
        </p>
      )}
    </div>
  );
}

/** 从 FastAPI 错误 JSON 中提取 detail 文案 */
function extractDetail(text: string): string {
  try {
    const j = JSON.parse(text);
    if (typeof j.detail === 'string') return j.detail;
    if (j.detail?.message) return j.detail.message;
    return text;
  } catch {
    return text;
  }
}

export default function EnvPerceptionPanel() {
  const [sources, setSources] = useState<EnvSourceStatus[]>([]);
  const [subs, setSubs] = useState<EnvSubscription[]>([]);
  const [enabledCount, setEnabledCount] = useState(0);
  const [freeMax, setFreeMax] = useState(3);
  const [feed, setFeed] = useState<EnvSignal[]>([]);
  const [feedStat, setFeedStat] = useState<{ pool: number; visible: number; suppressed_count?: number } | null>(null);
  const [piCount, setPiCount] = useState(0);
  const [recommendations, setRecommendations] = useState<EnvSourceRecommendation[]>([]);
  const [feedbackCount, setFeedbackCount] = useState(0);
  // S3-6 共生进化环状态
  const [symFeedbacks, setSymFeedbacks] = useState<FeedbackStatusItem[]>([]);
  const [growth, setGrowth] = useState<GrowthProfile | null>(null);
  const [evolutions, setEvolutions] = useState<EvolutionNotification[]>([]);
  const [fbKind, setFbKind] = useState<FeedbackKind>('idea');
  const [fbText, setFbText] = useState('');
  const [fbMsg, setFbMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [pullMsg, setPullMsg] = useState('');

  const refreshSymbiosis = useCallback(async () => {
    try {
      const [st, gp, ev] = await Promise.all([
        getEnvFeedbackStatus(),
        getEnvGrowthProfile(),
        getEnvEvolution(),
      ]);
      setSymFeedbacks(st.items || []);
      setGrowth(gp || null);
      setEvolutions(ev.notifications || []);
    } catch {
      /* 静默 */
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, sv, fd, rec] = await Promise.all([
        getEnvironmentOverview(),
        listEnvSubscriptions(),
        getEnvFeed(20),
        getEnvSourceRecommendations(),
      ]);
      setSources(ov.sources || []);
      setSubs(sv.subscriptions || []);
      setEnabledCount(sv.enabled_count);
      setFreeMax(sv.free_max_sources);
      setFeed(fd.signals || []);
      setFeedStat({ pool: fd.pool_size, visible: fd.visible });
      setPiCount(fd.platform_insight_count || 0);
      setRecommendations(rec.recommendations || []);
      setFeedbackCount(rec.feedback_count || 0);
    } catch {
      /* 静默：ErrorBoundary 兜底渲染错误，网络错误不白屏 */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    refreshSymbiosis();
    // S3-1 行为埋点（#315）：打开信号面板 = 一次「查看信号流」（fire-and-forget）
    trackBehavior('signal_view', 'panel', 'env_perception');
  }, [refresh, refreshSymbiosis]);

  const onPull = async () => {
    setPulling(true);
    setPullMsg('');
    trackBehavior('signal_pull', 'panel', 'env_perception');
    try {
      await pullEnvSources(10);
      setPullMsg('✅ 已拉取全部源');
      await refresh();
    } catch (e) {
      setPullMsg('拉取失败：' + extractDetail((e as Error).message));
    } finally {
      setPulling(false);
    }
  };

  const srcByName = new Map(sources.map((s) => [s.name, s]));
  const quotaFull = enabledCount >= freeMax;

  // S3-3：draft 推荐 → 人审后订阅（绝不一键全开；F4 透明纪律）
  const onSubscribeRec = async (rec: EnvSourceRecommendation) => {
    if (rec.subscribed) return;
    if (quotaFull) {
      setPullMsg('💡 免费版信息源额度已满，接入第 1 个内部数据源即可解锁更多。');
      return;
    }
    try {
      await saveEnvSubscription(rec.source_name, {
        enabled: true,
        credibility_min: 'general',
        keywords_include: [],
        keywords_exclude: [],
        poll_interval_sec: 3600,
      });
      trackBehavior('source_subscribe', 'source', rec.source_name);
      // S3-4：订阅即「采纳」→ 回流推荐模型（该类目后续推荐度上调）
      try { await postEnvRecommendationFeedback(rec.source_name, 'adopt'); } catch { /* 静默 */ }
      await refresh();
    } catch (e) {
      const err = e as Error & { status?: number };
      setPullMsg(
        err.status === 402
          ? '💡 ' + extractDetail(err.message)
          : '订阅失败：' + extractDetail(err.message),
      );
    }
  };

  // S3-4：驳回推荐 → 回流模型（推荐度下调，可撤销）；绝不静默消失（F4 透明）
  const onRejectRec = async (rec: EnvSourceRecommendation) => {
    try {
      await postEnvRecommendationFeedback(rec.source_name, 'reject');
      await refresh();
    } catch (e) {
      setPullMsg('驳回失败：' + extractDetail((e as Error).message));
    }
  };

  // S3-4：撤销驳回 → 记一次「采纳」覆盖最新动作（最新动作胜出）
  const onUndoReject = async (rec: EnvSourceRecommendation) => {
    try {
      await postEnvRecommendationFeedback(rec.source_name, 'adopt');
      await refresh();
    } catch (e) {
      setPullMsg('撤销失败：' + extractDetail((e as Error).message));
    }
  };

  return (
    <div className="space-y-5">
      {/* A. 环境感知总览 + 免费额度 */}
      <section className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900">环境感知 · 外部信息源订阅</h3>
          <div className="flex items-center gap-2">
            <button className="btn-secondary text-xs" onClick={onPull} disabled={pulling}>
              {pulling ? '拉取中…' : '立即拉取'}
            </button>
            <button className="btn-secondary text-xs" onClick={refresh} disabled={loading}>
              {loading ? '刷新中…' : '刷新'}
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          政策法规 / 原材料行情 / 行业对标三类公开信息源，按你的规则筛选后进入专属信号流并驱动智能体解读。
        </p>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-1 rounded-full ${quotaFull ? 'bg-amber-100 text-amber-700' : 'bg-zhiyan-50 text-zhiyan-700'}`}>
            信息源额度：{enabledCount} / {freeMax}（免费版）
          </span>
          {quotaFull && (
            <span className="text-[11px] text-gray-400">
              接入第 1 个内部数据源即可解锁更多信息源
            </span>
          )}
        </div>
        {pullMsg && (
          <p className={`text-xs mt-2 ${pullMsg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>{pullMsg}</p>
        )}
      </section>

      {/* B. 订阅规则（每源一卡） */}
      <section className="space-y-3">
        {subs.length === 0 && (
          <div className="card p-4 text-sm text-gray-400">{loading ? '加载中…' : '暂无可用环境源'}</div>
        )}
        {subs.map((sub) => (
          <SubscriptionCard
            key={sub.source_name}
            sub={sub}
            source={srcByName.get(sub.source_name)}
            onSaved={refresh}
            quotaFull={quotaFull}
          />
        ))}
      </section>

      {/* C. 我的环境信号流（语义隔离结果预览 + G5 轨道二平台建议） */}
      <section className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900">我的环境信号流</h3>
          {feedStat && (
            <span className="text-[11px] text-gray-400">
              平台池 {feedStat.pool} 条 → 你可见 {feedStat.visible} 条
              {piCount > 0 ? ` · 平台建议 ${piCount} 条` : ''}
              {feedStat.suppressed_count ? ` · 已降噪 ${feedStat.suppressed_count} 条低相关` : ''}
            </span>
          )}
        </div>
        {/* F4 透明图例：真实情报 vs 平台建议两轨绝不混淆 */}
        <div className="flex flex-wrap items-center gap-2 mb-3 text-[11px]">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 text-green-700">
            🟢 官方情报（真实外部信息）
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zhiyan-50 text-zhiyan-700">
            💡 平台建议（来自智衍平台的建议，仅供参考）
          </span>
        </div>
        {feed.length === 0 ? (
          <p className="text-sm text-gray-400">暂无信号——点「立即拉取」抓取最新外部信息。</p>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {[...feed]
              .sort((a, b) => (b.relevance?.score ?? 0) - (a.relevance?.score ?? 0))
              .map((s, i) => {
              if (s.kind === 'platform_insight') {
                const based = (s.payload?.based_on as Array<{ title?: string }> | undefined) || [];
                return (
                  <div
                    key={s.id || i}
                    className="rounded-lg border border-zhiyan-100 border-l-4 border-l-zhiyan-500 bg-zhiyan-50/40 p-2.5"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-zhiyan-100 text-zhiyan-700 font-medium">
                        💡 来自智衍平台的建议
                      </span>
                    </div>
                    <p className="text-sm font-medium text-gray-800">
                      {String(s.payload?.title || '平台建议')}
                    </p>
                    <p className="text-[12px] text-gray-600 mt-0.5 leading-relaxed">
                      {String(s.payload?.content || '')}
                    </p>
                    {based.length > 0 && (
                      <p className="text-[11px] text-zhiyan-600/80 mt-1">
                        依据：{based.map((b) => b.title).filter(Boolean).slice(0, 1).join('')}
                      </p>
                    )}
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {s.ts ? new Date(s.ts * 1000).toLocaleString() : ''}
                    </p>
                  </div>
                );
              }
              return (
                <div key={s.id || i} className="flex items-start gap-2 text-sm border-b border-gray-50 pb-1.5">
                  <CredBadge c={s.credibility} />
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-700 truncate">
                      {String(s.payload?.title || s.payload?.summary || s.payload?.name || JSON.stringify(s.payload || {}).slice(0, 80))}
                    </p>
                    <p className="text-[11px] text-gray-400">
                      {s.source}
                      {s.ts ? ` · ${new Date(s.ts * 1000).toLocaleString()}` : ''}
                    </p>
                    {s.relevance && (
                      <div className="mt-1 flex flex-wrap items-center gap-1">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${s.relevance.suppressed ? 'bg-gray-100 text-gray-400' : 'bg-zhiyan-50 text-zhiyan-700'}`}>
                          相关性 {Math.round((s.relevance.score ?? 0) * 100)}%
                        </span>
                        {(s.relevance.target_agents || []).map((a) => (
                          <span key={a} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                            → {a}
                          </span>
                        ))}
                      </div>
                    )}
                    {s.relevance?.reason && (
                      <p className="text-[10px] text-gray-400 mt-0.5 leading-snug">{s.relevance.reason}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* D. S3-3 源推荐：按你的行业 / 物料(BOM) / 行为画像 推荐值得订阅的信息源（draft，人审后订阅） */}
      <section className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900">为你推荐的信息源</h3>
          <span className="text-[11px] text-gray-400">
            {feedbackCount > 0 ? `已学习你的 ${feedbackCount} 次采纳/驳回` : '按你的画像相关性排序'}
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          基于你的行业属性、已上传 BOM 的物料构成、以及常用智能体的解读偏好，推荐最值得订阅的外部信息源。推荐依据全程透明——确认后点「订阅」即生效。
        </p>
        {recommendations.length === 0 ? (
          <p className="text-sm text-gray-400">暂无可用环境源</p>
        ) : (
          <div className="space-y-2.5">
            {recommendations.map((rec) => (
              <div
                key={rec.source_name}
                className="rounded-lg border border-gray-100 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-800">{rec.label}</span>
                      <CredBadge c={rec.credibility} />
                      <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-zhiyan-50 text-zhiyan-700">
                        推荐度 {Math.round((rec.score ?? 0) * 100)}%
                      </span>
                      {rec.subscribed ? (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-green-50 text-green-700">
                          已订阅
                        </span>
                      ) : rec.is_default ? (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-gray-50 text-gray-400">
                          默认模板（未显式订阅）
                        </span>
                      ) : null}
                      {rec.rejected && (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-red-50 text-red-600">
                          已驳回
                        </span>
                      )}
                    </div>
                    <ul className="mt-1.5 space-y-0.5">
                      {rec.reasons.map((r, i) => (
                        <li key={i} className="text-[11px] text-gray-500 leading-snug">
                          · {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    {rec.rejected ? (
                      <button
                        className="btn-secondary text-xs whitespace-nowrap"
                        onClick={() => onUndoReject(rec)}
                      >
                        撤销驳回
                      </button>
                    ) : !rec.subscribed ? (
                      <>
                        <button
                          className="btn-primary text-xs whitespace-nowrap"
                          onClick={() => onSubscribeRec(rec)}
                          disabled={quotaFull}
                        >
                          订阅
                        </button>
                        <button
                          className="btn-ghost text-xs whitespace-nowrap text-gray-400 hover:text-red-500"
                          onClick={() => onRejectRec(rec)}
                        >
                          不感兴趣
                        </button>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* S3-6 共生进化环（#320，§3.6）：反馈入口 + 成长档案 + 因你而进化 */}
      <section className="space-y-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900">共生进化环</h3>
          <span className="text-[11px] text-gray-400">你的反馈会推动平台进化</span>
        </div>

        {/* 反馈入口 */}
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            {(['idea', 'inaccurate', 'praise', 'other'] as FeedbackKind[]).map((k) => (
              <button
                key={k}
                className={`text-xs px-2.5 py-1 rounded-full border ${
                  fbKind === k
                    ? 'bg-zhiyan-50 border-zhiyan-300 text-zhiyan-700'
                    : 'border-gray-200 text-gray-500'
                }`}
                onClick={() => setFbKind(k)}
              >
                {k === 'idea' ? '💡 我有想法' : k === 'inaccurate' ? '👎 不准确' : k === 'praise' ? '👍 有用' : '📝 其他'}
              </button>
            ))}
          </div>
          <textarea
            className="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 resize-none"
            rows={2}
            placeholder="说点什么——这里默认匿名、已脱敏，会转为公开路线图 Issue 推动进化"
            value={fbText}
            onChange={(e) => setFbText(e.target.value)}
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gray-400">默认匿名 · 自动脱敏 · 48h 内必有首次回音</span>
            <button
              className="btn-primary text-xs"
              disabled={!fbText.trim()}
              onClick={async () => {
                try {
                  await postEnvFeedback({ kind: fbKind, text: fbText.trim(), anonymous: true });
                  setFbText('');
                  setFbMsg('✅ 已收到！已脱敏并转为公开路线图 Issue，您可在下方追踪进度。');
                  await refreshSymbiosis();
                } catch (e) {
                  setFbMsg('提交失败：' + ((e as Error).message || ''));
                }
              }}
            >
              提交反馈
            </button>
          </div>
          {fbMsg && <div className="text-[11px] text-gray-500">{fbMsg}</div>}
        </div>

        {/* 成长档案 */}
        {growth && (
          <div className="rounded-xl bg-gradient-to-br from-zhiyan-50 to-white border border-zhiyan-100 px-4 py-3">
            <div className="text-[11px] text-zhiyan-600 font-medium mb-2">成长档案 · 你和平台一起变强</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              <div>
                <div className="text-lg font-semibold text-gray-800">{growth.days_active}</div>
                <div className="text-[10px] text-gray-400">使用天数</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-gray-800">
                  {growth.unlocked_agents}/{growth.total_agents}
                </div>
                <div className="text-[10px] text-gray-400">已解锁圈层</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-gray-800">{growth.feedback_contributed}</div>
                <div className="text-[10px] text-gray-400">贡献的进化</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-gray-800">{growth.ideas_adopted}</div>
                <div className="text-[10px] text-gray-400">被采纳想法</div>
              </div>
            </div>
          </div>
        )}

        {/* 因你而进化回告 */}
        {evolutions.length > 0 && (
          <div className="space-y-1.5">
            {evolutions.map((ev) => (
              <div
                key={ev.tracking_id}
                className="rounded-lg bg-green-50 border border-green-100 px-3 py-2 text-[11px] text-green-800"
              >
                🌱 {ev.message}
                {ev.issue_url && (
                  <a href={ev.issue_url} target="_blank" rel="noreferrer" className="underline ml-1">
                    查看 Issue
                  </a>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 我的反馈进度 + 48h SLA */}
        {symFeedbacks.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[11px] text-gray-400">我的反馈进度</div>
            {symFeedbacks.map((f) => (
              <div key={f.tracking_id} className="rounded-lg border border-gray-200 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium text-gray-700">
                    {f.kind === 'idea' ? '💡 想法' : f.kind === 'inaccurate' ? '👎 不准' : f.kind === 'praise' ? '👍 有用' : '📝 其他'}
                    {' · '}
                    {f.status === 'released' ? '已上线' : f.status === 'in_progress' ? '处理中' : '已收到'}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      f.sla_remaining_hours !== null && f.sla_remaining_hours < 0
                        ? 'bg-red-50 text-red-600'
                        : 'bg-blue-50 text-blue-600'
                    }`}
                  >
                    {f.sla_remaining_hours !== null
                      ? f.sla_remaining_hours >= 0
                        ? `48h SLA 剩 ${f.sla_remaining_hours}h`
                        : 'SLA 已超时'
                      : 'SLA—'}
                  </span>
                </div>
                {f.issue_url && (
                  <a href={f.issue_url} target="_blank" rel="noreferrer" className="text-[10px] text-zhiyan-600 underline">
                    GitHub Issue #{f.issue_number}
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
