import { useState, useEffect, useCallback } from 'react';
import { authHeaders } from '../api/client';

export default function FederationPanel() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [minTrust, setMinTrust] = useState(0.6);

  const fetchAll = useCallback(async () => {
    try {
      const [statusR, patternsR, highR, strategyR] = await Promise.all([
        fetch('/api/federation/status', { headers: authHeaders() }),
        fetch('/api/federation/patterns', { headers: authHeaders() }),
        fetch(`/api/federation/patterns/high?min_trust=${minTrust}`, { headers: authHeaders() }),
        fetch('/api/federation/strategy', { headers: authHeaders() }),
      ]);
      if (statusR.ok && patternsR.ok && highR.ok && strategyR.ok) {
        setData({
          status: await statusR.json(),
          patterns: await patternsR.json(),
          high: await highR.json(),
          strategy: await strategyR.json(),
        });
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [minTrust]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  if (loading) {
    return (
      <div className="page-transition text-center py-24">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-cyan-50 to-cyan-100 flex items-center justify-center">
          <span className="w-8 h-8 border-[3px] border-cyan-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <p className="text-gray-500 text-sm">加载联邦学习面板…</p>
      </div>
    );
  }

  const status = data?.status;
  const patterns = data?.patterns;
  const high = data?.high?.patterns || [];
  const strategy = data?.strategy;
  const agents = strategy?.agent_signals || {};

  return (
    <div className="page-transition space-y-4">
      {/* 顶栏 */}
      <div className="card-highlight">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center text-white shadow-sm">
              🌍
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">跨企业联邦学习</h2>
              <p className="text-xs text-gray-400">跨租户匿名知识聚合 · 去标识化模式 · 联邦策略调参</p>
            </div>
          </div>
          <button className="btn-secondary text-xs py-1.5 px-3" onClick={fetchAll}>刷新</button>
        </div>
      </div>

      {/* 概要卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-4 text-center">
          <p className="text-[10px] text-gray-500 font-medium mb-1">🏢 租户数</p>
          <p className="text-2xl font-bold text-cyan-600">{status?.tenants?.total || 0}</p>
          <p className="text-[10px] text-gray-400">{status?.tenants?.active || 0} 活跃</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-gray-500 font-medium mb-1">🧩 KG 模式数</p>
          <p className="text-2xl font-bold text-teal-600">{patterns?.summary?.total_patterns || 0}</p>
          <p className="text-[10px] text-gray-400">{patterns?.summary?.multi_tenant_patterns || 0} 跨租户</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-gray-500 font-medium mb-1">⭐ 高可信模式</p>
          <p className="text-2xl font-bold text-emerald-600">{high.length}</p>
          <p className="text-[10px] text-gray-400">联邦可信度 ≥ {minTrust}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-[10px] text-gray-500 font-medium mb-1">🤖 联邦 Agent</p>
          <p className="text-2xl font-bold text-blue-600">{Object.keys(agents).length}</p>
          <p className="text-[10px] text-gray-400">{strategy?.summary?.total_tenants || 0} 租户贡献</p>
        </div>
      </div>

      {/* KG 跨租户模式 */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">🧩 跨租户 KG 事实模式 <span className="text-[10px] text-gray-400 font-normal">（去标识化，只保留结构）</span></h3>
        {Object.keys(patterns?.patterns || {}).length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-6">暂无跨租户 KG 模式数据</p>
        ) : (
          <div className="space-y-2">
            {Object.entries(patterns.patterns || {}).map(([predicate, objTypes]: [string, any]) => (
              <div key={predicate}>
                <p className="text-xs font-semibold text-gray-700 mb-1.5">{predicate}</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {Object.entries(objTypes).map(([objType, stats]: [string, any]) => (
                    <div key={`${predicate}-${objType}`} className="p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-xs">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-gray-600">{objType}</span>
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                          stats.federal_trust >= 0.6 ? 'bg-emerald-100 text-emerald-600' :
                          stats.federal_trust >= 0.3 ? 'bg-amber-100 text-amber-600' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {stats.tenant_count} 租户
                        </span>
                      </div>
                      <div className="flex gap-2 text-gray-400">
                        <span>✓{stats.validated_count}</span>
                        <span>✗{stats.contradicted_count}</span>
                        <span>📝{stats.draft_count}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-gray-200 overflow-hidden">
                        <div className="h-full rounded-full bg-teal-500" style={{width: `${stats.federal_trust * 100}%`}} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 高可信模式 */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">⭐ 高联邦可信度模式 <span className="text-[10px] text-gray-400 font-normal">（跨租户 validated 模式）</span></h3>
          <div className="flex items-center gap-2">
            <label className="text-[10px] text-gray-400">最低可信度</label>
            <input type="range" min="0.1" max="1" step="0.1" value={minTrust} onChange={e => setMinTrust(parseFloat(e.target.value))}
              className="w-20 h-1.5" />
            <span className="text-xs font-mono text-gray-500 w-8">{minTrust}</span>
          </div>
        </div>
        {high.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-6">暂无高可信模式（需多租户提交 validation）</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {high.map((p: any, i: number) => (
              <div key={i} className="p-3 rounded-lg bg-teal-50 border border-teal-100 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-teal-600 font-medium">{p.predicate}</span>
                  <span className="text-gray-400">→</span>
                  <span className="text-gray-600">{p.object_type}</span>
                </div>
                <div className="flex items-center gap-3 text-gray-500 text-[10px]">
                  <span className="flex items-center gap-1">🏢 {p.tenant_count} 租户</span>
                  <span className="flex items-center gap-1">✓{p.validated_count}</span>
                  <span className="flex items-center gap-1">★{(p.federal_trust * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 联邦策略信号 */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">🎚️ 联邦策略信号 <span className="text-[10px] text-gray-400 font-normal">（跨租户自治率统计）</span></h3>
        {Object.keys(agents).length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-6">暂无跨租户策略信号</p>
        ) : (
          <div className="space-y-2">
            {Object.entries(agents).map(([agent, sig]: [string, any]) => (
              <div key={agent} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 border border-gray-100 text-xs">
                <span className="font-medium text-gray-700 w-28">{agent}</span>
                <div className="flex-1 flex items-center gap-4">
                  <span className="text-gray-500">🌐 {sig.tenant_count} 租户</span>
                  <span className="text-emerald-600">均值 {((sig.avg_autonomous_rate || 0) * 100).toFixed(0)}%</span>
                  <div className="flex-1 h-1.5 rounded-full bg-gray-200 overflow-hidden">
                    <div className="h-full rounded-full bg-cyan-500" style={{width: `${(sig.avg_autonomous_rate || 0) * 100}%`}} />
                  </div>
                  <span className="text-gray-400 text-[10px]">
                    [{((sig.min_autonomous_rate || 0) * 100).toFixed(0)}%–{((sig.max_autonomous_rate || 0) * 100).toFixed(0)}%]
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 方法说明 */}
      <div className="card bg-gray-50/50">
        <h4 className="text-xs font-semibold text-gray-700 mb-2">🔐 隐私保护说明</h4>
        <ul className="text-[11px] text-gray-500 space-y-1">
          <li>• KG 模式已去标识化：去除了具体实体值，只保留 (谓词, 对象类型) 结构</li>
          <li>• 联邦可信度 = validated 占比 ×0.7 + 跨租户系数 ×0.3</li>
          <li>• 策略信号仅聚合统计量（均值/分布），不暴露具体租户的业务数字</li>
          <li>• 租户样本仅显示前 3 个 ID，不暴露租户名称</li>
        </ul>
      </div>

      <div className="text-center text-[10px] text-gray-300 py-2">
        智衍 EvolvIQ · 跨企业联邦学习 · 每 15s 自动刷新
      </div>
    </div>
  );
}
