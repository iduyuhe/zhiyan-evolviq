import { useCallback, useEffect, useState } from 'react';
import {
  getWritebackPending,
  getWritebackStats,
  retryWriteback,
  submitWriteback,
  type WritebackRecord,
  type WritebackStats,
  type WritebackSubmitResult,
} from '../api/client';

const SYSTEM_LABELS: Record<string, string> = {
  mes: 'MES 制造执行',
  erp: 'ERP 企业资源',
};

const STATUS_STYLE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  sent: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

function fmtTime(ts: number | null): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false });
}

/** ERP/MES 决策回写审计桥面板：提交回写 + pending 队列可视化 + 重试。 */
export default function WritebackPanel() {
  const [stats, setStats] = useState<WritebackStats | null>(null);
  const [pending, setPending] = useState<WritebackRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<WritebackSubmitResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 提交表单状态
  const [system, setSystem] = useState('mes');
  const [agent, setAgent] = useState('supply_chain');
  const [decisionType, setDecisionType] = useState('supply_risk_approval');
  const [payloadText, setPayloadText] = useState('{\n  "conclusion": "",\n  "evidence": ""\n}');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([getWritebackStats(), getWritebackPending()]);
      setStats(s);
      setPending(p.pending);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const onSubmit = async () => {
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(payloadText);
    } catch {
      setError('决策 payload 不是合法 JSON');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const r = await submitWriteback({
        system,
        agent: agent.trim(),
        decision_type: decisionType.trim(),
        payload,
      });
      setLastResult(r);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const onRetry = async () => {
    setRetrying(true);
    setError(null);
    try {
      const r = await retryWriteback();
      setLastResult({
        status: r.sent > 0 ? 'sent' : 'pending',
        detail: `重试成功 ${r.sent} 条，剩余 pending ${r.pending_remaining}`,
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* 顶部说明 + 统计 */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-800">🔁 决策回写审计桥（ERP / MES）</h2>
            <p className="text-xs text-gray-500 mt-1">
              agent 决策以<span className="font-medium">审计记录</span>形式回写业务系统账本留痕——
              不篡夺 ERP/MES 权威账本；连接器不可达时自动进 pending 队列，不阻断主流程。
            </p>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="text-xs text-zhiyan-600 hover:underline disabled:opacity-50 shrink-0"
          >
            {loading ? '刷新中…' : '立即刷新'}
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-3">
          <div className="rounded bg-yellow-50 p-3 text-center">
            <div className="text-2xl font-bold text-yellow-700">{stats?.pending ?? '—'}</div>
            <div className="text-[11px] text-gray-500 mt-0.5">Pending 待回写</div>
          </div>
          <div className="rounded bg-green-50 p-3 text-center">
            <div className="text-2xl font-bold text-green-700">{stats?.sent_total ?? '—'}</div>
            <div className="text-[11px] text-gray-500 mt-0.5">已回写成功</div>
          </div>
          <div className="rounded bg-blue-50 p-3 text-center">
            <div className="text-2xl font-bold text-blue-700">
              {stats ? stats.systems.length : '—'}
            </div>
            <div className="text-[11px] text-gray-500 mt-0.5">
              支持系统 {stats ? `(${stats.systems.join(' / ').toUpperCase()})` : ''}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
          ⚠️ {error}
        </div>
      )}
      {lastResult && !error && (
        <div
          className={`rounded border text-xs px-3 py-2 ${
            lastResult.status === 'sent'
              ? 'bg-green-50 border-green-200 text-green-700'
              : lastResult.status === 'pending'
                ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
                : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {lastResult.status === 'sent' && '✅ 已回写'}
          {lastResult.status === 'pending' && '⏳ 已入 pending 队列（连接器不可达或写入失败，稍后可重试）'}
          {lastResult.status === 'rejected' && '❌ 已拒绝'}
          {lastResult.record_id ? ` · 记录 ${lastResult.record_id}` : ''}
          {lastResult.detail ? ` · ${lastResult.detail}` : ''}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 提交回写 */}
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">📤 手动提交回写</h3>
          <div className="space-y-2.5">
            <div className="grid grid-cols-2 gap-2.5">
              <label className="block">
                <span className="text-[11px] text-gray-500">目标系统</span>
                <select
                  value={system}
                  onChange={(e) => setSystem(e.target.value)}
                  className="mt-0.5 w-full border border-gray-200 rounded px-2 py-1.5 text-xs bg-white"
                >
                  {Object.entries(SYSTEM_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-[11px] text-gray-500">决策 Agent</span>
                <input
                  value={agent}
                  onChange={(e) => setAgent(e.target.value)}
                  className="mt-0.5 w-full border border-gray-200 rounded px-2 py-1.5 text-xs"
                  placeholder="如 supply_chain"
                />
              </label>
            </div>
            <label className="block">
              <span className="text-[11px] text-gray-500">决策类型</span>
              <input
                value={decisionType}
                onChange={(e) => setDecisionType(e.target.value)}
                className="mt-0.5 w-full border border-gray-200 rounded px-2 py-1.5 text-xs"
                placeholder="如 supply_risk_approval"
              />
            </label>
            <label className="block">
              <span className="text-[11px] text-gray-500">决策结论 + 依据（JSON）</span>
              <textarea
                value={payloadText}
                onChange={(e) => setPayloadText(e.target.value)}
                rows={6}
                className="mt-0.5 w-full border border-gray-200 rounded px-2 py-1.5 text-xs font-mono"
                spellCheck={false}
              />
            </label>
            <button
              onClick={onSubmit}
              disabled={submitting || !agent.trim() || !decisionType.trim()}
              className="w-full bg-zhiyan-600 hover:bg-zhiyan-700 text-white text-xs font-medium rounded px-3 py-2 disabled:opacity-50"
            >
              {submitting ? '提交中…' : '提交回写'}
            </button>
          </div>
        </div>

        {/* pending 队列 */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-800">⏳ Pending 队列（{pending.length}）</h3>
            <button
              onClick={onRetry}
              disabled={retrying || pending.length === 0}
              className="text-xs bg-yellow-500 hover:bg-yellow-600 text-white rounded px-2.5 py-1 disabled:opacity-40"
            >
              {retrying ? '重试中…' : '🔁 全部重试'}
            </button>
          </div>
          {pending.length === 0 ? (
            <div className="text-xs text-gray-400 text-center py-8">
              队列为空——所有回写已送达或尚未产生
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-auto">
              {pending.map((r) => (
                <div key={r.id} className="border border-gray-100 rounded p-2.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-gray-600">{r.id}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] ${STATUS_STYLE[r.status] || 'bg-gray-100 text-gray-600'}`}
                    >
                      {r.status}
                    </span>
                  </div>
                  <div className="mt-1 text-gray-700">
                    <span className="font-medium">{(r.system || '').toUpperCase()}</span>
                    {' · '}
                    {r.agent}
                    {' · '}
                    {r.decision_type}
                  </div>
                  <div className="mt-0.5 text-[10px] text-gray-400 flex items-center justify-between">
                    <span>创建 {fmtTime(r.created_at)}</span>
                    {r.error && (
                      <span className="text-red-500 truncate max-w-[55%]" title={r.error}>
                        {r.error}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
