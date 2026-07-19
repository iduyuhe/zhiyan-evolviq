import { useEffect, useState, useCallback } from 'react';
import {
  getGateways,
  readGateway,
  type GatewayOverview,
  type GatewayHealth,
  type GatewayReadResult,
} from '../api/client';

const GW_LABELS: Record<string, string> = {
  modbus: 'Modbus',
  mqtt: 'MQTT',
  opcua: 'OPC-UA',
  ipc_cfx: 'IPC-CFX',
};

const GW_ICONS: Record<string, string> = {
  modbus: '🔌',
  mqtt: '📡',
  opcua: '🏭',
  ipc_cfx: '📨',
};

function fmtValue(v: number | string | boolean | Record<string, unknown>): string {
  if (typeof v === 'object') return JSON.stringify(v);
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return String(v);
}

function GatewayCard({ name }: { name: string }) {
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [read, setRead] = useState<GatewayReadResult | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [h, r] = await Promise.all([getGateways(), readGateway(name, '*', 8)]);
      setHealth(h.gateways[name] || null);
      setRead(r);
    } catch {
      /* 单网关失败不影响其余 */
    } finally {
      setLoading(false);
    }
  }, [name]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000); // 实时读数轮询
    return () => clearInterval(t);
  }, [refresh]);

  const ready = health?.running;
  const mode = health?.mode || '—';

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{GW_ICONS[name] || '🔧'}</span>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">{GW_LABELS[name] || name}</h3>
            <span
              className={`inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] ${
                ready ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}
            >
              {ready ? '就绪' : '未就绪'}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div
            className={`text-[10px] px-1.5 py-0.5 rounded ${
              mode === 'simulated' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'
            }`}
          >
            {mode}
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">
            {health?.nodes_monitored ? `${health.nodes_monitored} 节点` : ''}
            {health?.subscribed_topics ? `${health.subscribed_topics} 主题` : ''}
          </div>
        </div>
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-gray-500">实时读数</span>
          <button
            onClick={refresh}
            disabled={loading}
            className="text-[10px] text-zhiyan-600 hover:underline disabled:opacity-50"
          >
            {loading ? '刷新中…' : '立即刷新'}
          </button>
        </div>
        {read && read.points.length > 0 ? (
          <div className="space-y-1 max-h-52 overflow-auto">
            {read.points.map((p, i) => (
              <div
                key={`${p.tag}-${i}`}
                className="flex items-center justify-between text-xs border-b border-gray-100 py-1"
              >
                <span className="font-mono text-gray-600 truncate max-w-[60%]" title={String(p.tag)}>
                  {String(p.tag)}
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-gray-800 font-medium">{fmtValue(p.value)}</span>
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      p.quality === 'good' ? 'bg-green-500' : 'bg-red-500'
                    }`}
                    title={p.quality}
                  />
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400 py-2">暂无读数</p>
        )}
      </div>
    </div>
  );
}

export default function GatewayTab() {
  const [overview, setOverview] = useState<GatewayOverview | null>(null);

  useEffect(() => {
    getGateways()
      .then(setOverview)
      .catch(() => setOverview(null));
  }, []);

  const names = overview ? Object.keys(overview.gateways) : ['modbus', 'mqtt', 'opcua', 'ipc_cfx'];

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span>🛰️</span> 工业协议网关
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          四类工业协议实时接入 · 每 4 秒自动刷新读数
        </p>
        {overview && (
          <div className="flex gap-4 mt-3 text-xs text-gray-500">
            <span>网关总数：<b className="text-gray-800">{overview.total}</b></span>
            <span>就绪：<b className="text-green-600">{overview.ready}</b></span>
            <span>
              模式分布：
              {Object.entries(overview.modes).map(([m, c]) => (
                <span key={m} className="ml-1 px-1 py-0.5 rounded bg-gray-100">{m}:{c}</span>
              ))}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {names.map((name) => (
          <GatewayCard key={name} name={name} />
        ))}
      </div>
    </div>
  );
}
