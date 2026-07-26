import { useState, useEffect, useCallback } from 'react';
import { getAlerts, getMonitorStatus, triggerMonitorCheck, AlertItem, MonitorStatus } from '../api/client';

const KIND_LABEL: Record<string, string> = {
  writeback_backlog: '回写积压',
  gateway_stale: '网关断流',
  login_anomaly: '登录异常',
};

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleString('zh-CN', { hour12: false });
}

const sevStyle: Record<string, string> = {
  warning: 'bg-yellow-100 text-yellow-700',
  critical: 'bg-red-100 text-red-700',
};

export default function AlertPanel() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const refresh = useCallback(async () => {
    try {
      const [a, s] = await Promise.all([getAlerts(undefined, 50), getMonitorStatus()]);
      setAlerts(a);
      setStatus(s);
      setLastUpdated(new Date());
    } catch (e) {
      // 静默：保留上一次数据
    }
  }, []);

  const onCheck = useCallback(async () => {
    setChecking(true);
    try {
      await triggerMonitorCheck();
      await refresh();
    } finally {
      setChecking(false);
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="space-y-4">
      {/* 状态卡 */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-gray-800">🚨 监控告警中心</h4>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-400">{lastUpdated.toLocaleTimeString('zh-CN')}</span>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={onCheck} disabled={checking}>
              {checking ? '检测中…' : '立即检测'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
            <div className="text-2xl font-bold text-gray-800">{status?.alerts_total ?? 0}</div>
            <div className="text-xs text-gray-400">累计告警</div>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
            <div className="text-sm font-medium text-gray-700">回写 ≥ {status?.thresholds.wb_pending ?? 10}</div>
            <div className="text-xs text-gray-400">积压阈值(条)</div>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
            <div className="text-sm font-medium text-gray-700">断流 ≥ {status?.thresholds.twin_stale_s ?? 600}s</div>
            <div className="text-xs text-gray-400">孪生体阈值</div>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
            <div className="text-sm font-medium text-gray-700">{(status?.notifiers ?? ['log']).join(', ')}</div>
            <div className="text-xs text-gray-400">通知渠道</div>
          </div>
        </div>
      </div>

      {/* 告警列表 */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">实时告警（最近 {alerts.length} 条）</h4>
        {alerts.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-8">✅ 当前无活跃告警</div>
        ) : (
          <div className="space-y-2">
            {alerts.map((a, i) => (
              <div key={`${a.key}-${a.ts}-${i}`} className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50/50">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap ${sevStyle[a.severity] ?? 'bg-gray-100 text-gray-600'}`}>
                  {a.severity === 'critical' ? '严重' : '警告'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800">
                    {KIND_LABEL[a.kind] ?? a.kind}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">{a.message}</div>
                  <div className="text-[10px] text-gray-300 mt-1 font-mono">
                    {a.key} · {fmtTime(a.ts)} · 已通知 {a.notified} 渠道
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
