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
  pullEnvSources,
  trackBehavior,
  EnvSourceStatus,
  EnvSubscription,
  EnvSignal,
  ConnectivityTestResult,
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
  const [feedStat, setFeedStat] = useState<{ pool: number; visible: number } | null>(null);
  const [piCount, setPiCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [pullMsg, setPullMsg] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, sv, fd] = await Promise.all([
        getEnvironmentOverview(),
        listEnvSubscriptions(),
        getEnvFeed(20),
      ]);
      setSources(ov.sources || []);
      setSubs(sv.subscriptions || []);
      setEnabledCount(sv.enabled_count);
      setFreeMax(sv.free_max_sources);
      setFeed(fd.signals || []);
      setFeedStat({ pool: fd.pool_size, visible: fd.visible });
      setPiCount(fd.platform_insight_count || 0);
    } catch {
      /* 静默：ErrorBoundary 兜底渲染错误，网络错误不白屏 */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    // S3-1 行为埋点（#315）：打开信号面板 = 一次「查看信号流」（fire-and-forget）
    trackBehavior('signal_view', 'panel', 'env_perception');
  }, [refresh]);

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
            {[...feed].reverse().map((s, i) => {
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
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
