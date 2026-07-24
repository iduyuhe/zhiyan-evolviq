import { useState, useEffect } from 'react';
import { useTenant, type StoredTenant } from '../tenant/TenantContext';
import {
  getTenantGatewayConfig,
  putTenantGatewayConfig,
  type GatewayConfig,
} from '../api/client';

function maskKey(key: string): string {
  if (key.length <= 12) return key;
  return `${key.slice(0, 6)}${'•'.repeat(10)}${key.slice(-4)}`;
}

function copy(text: string) {
  navigator.clipboard?.writeText(text).catch(() => {});
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-gray-400">{label}</span>
      <span className={`text-sm text-gray-800 break-all ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}

export default function TenantManagement() {
  const {
    tenants,
    activeTenant,
    loading,
    registerTenant,
    setActive,
    rotateKey,
    deleteTenant,
    me,
    refreshMe,
  } = useTenant();

  const [name, setName] = useState('');
  const [newKey, setNewKey] = useState<{ tenant_id: string; name: string; api_key: string } | null>(null);
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [error, setError] = useState('');

  // 网关配置
  const [gw, setGw] = useState<GatewayConfig>({});
  const [gwLoading, setGwLoading] = useState(false);
  const [gwMsg, setGwMsg] = useState('');

  // 加载当前租户网关配置
  useEffect(() => {
    if (!activeTenant) {
      setGw({});
      return;
    }
    setGwLoading(true);
    getTenantGatewayConfig()
      .then((d) => setGw(d.gateway_config || {}))
      .catch(() => setGw({}))
      .finally(() => setGwLoading(false));
  }, [activeTenant]);

  const handleRegister = async () => {
    setError('');
    if (!name.trim()) {
      setError('请填写租户名称');
      return;
    }
    try {
      const t = await registerTenant(name.trim());
      setNewKey({ tenant_id: t.tenant_id, name: t.name, api_key: t.api_key });
      setName('');
      await refreshMe();
    } catch (e) {
      setError(e instanceof Error ? e.message : '注册失败');
    }
  };

  const handleRotate = async (t: StoredTenant) => {
    setError('');
    try {
      await rotateKey(t.tenant_id);
      setNewKey({ tenant_id: t.tenant_id, name: t.name, api_key: getStoredKey(t.tenant_id) });
      await refreshMe();
    } catch (e) {
      setError(e instanceof Error ? e.message : '轮换失败');
    }
  };

  // rotateKey 已更新 localStorage，这里从最新 tenants 取
  function getStoredKey(id: string): string {
    return tenants.find((x) => x.tenant_id === id)?.api_key || '';
  }

  const handleDelete = async (t: StoredTenant) => {
    if (!confirm(`确认注销租户「${t.name}」？该租户在平台上的数据将被删除，此操作不可恢复。`)) return;
    setError('');
    try {
      await deleteTenant(t.tenant_id);
      if (newKey?.tenant_id === t.tenant_id) setNewKey(null);
      await refreshMe();
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  const handleSaveGw = async () => {
    setGwMsg('');
    try {
      await putTenantGatewayConfig(gw);
      setGwMsg('✅ 网关配置已保存');
    } catch (e) {
      setGwMsg(`❌ ${e instanceof Error ? e.message : '保存失败'}`);
    }
  };

  const handleClearGw = async () => {
    setGwMsg('');
    try {
      await putTenantGatewayConfig({});
      setGw({});
      setGwMsg('✅ 已清除网关覆写（改用平台共享网关）');
    } catch (e) {
      setGwMsg(`❌ ${e instanceof Error ? e.message : '清除失败'}`);
    }
  };

  return (
    <div className="space-y-4">
      {/* 当前租户状态 */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">🏢</span>
          <h2 className="text-base font-semibold text-gray-800">当前租户</h2>
          <span className="badge badge-blue ml-1">
            {activeTenant ? activeTenant.name : '默认租户（default）'}
          </span>
        </div>
        {activeTenant ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Field label="租户 ID" value={me?.id || activeTenant.tenant_id} mono />
            <Field label="名称" value={me?.name || activeTenant.name} />
            <Field label="状态" value={me?.is_active ? '启用' : '禁用'} />
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            当前未选择租户，所有请求归属 <span className="font-mono text-gray-700">default</span> 租户（平台共享数据）。
            在右上角切换器中选择一个租户后，本页面的所有数据与操作都会按该租户隔离。
          </p>
        )}
      </div>

      {/* 注册新租户 */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">➕</span>
          <h2 className="text-base font-semibold text-gray-800">注册新租户</h2>
        </div>
        <div className="flex gap-2">
          <input
            className="input"
            placeholder="租户名称，如 acme / 华东工厂"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRegister()}
          />
          <button className="btn-primary whitespace-nowrap" onClick={handleRegister} disabled={loading}>
            {loading ? '注册中…' : '注册'}
          </button>
        </div>
        {error && <p className="text-sm text-red-500 mt-2">{error}</p>}

        {newKey && (
          <div className="mt-4 p-4 rounded-lg bg-zhiyan-50 border border-zhiyan-200">
            <p className="text-sm font-medium text-zhiyan-700 mb-1">✅ 租户「{newKey.name}」注册成功</p>
            <p className="text-xs text-gray-500 mb-2">
              请妥善保存以下 API Key（<b>仅此一次显示</b>，之后可在「我的租户」中轮换）：
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono break-all bg-white rounded px-3 py-2 border border-zhiyan-200 text-gray-800">
                {newKey.api_key}
              </code>
              <button className="btn-secondary whitespace-nowrap" onClick={() => copy(newKey.api_key)}>
                复制
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 我的租户列表 */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">🗂️</span>
          <h2 className="text-base font-semibold text-gray-800">我的租户</h2>
          <span className="badge badge-blue">{tenants.length}</span>
        </div>
        {tenants.length === 0 ? (
          <p className="text-sm text-gray-400">还没有在本机注册过租户。注册后，密钥会安全保存在浏览器本地（localStorage），用于自动携带 X-Tenant-Key。</p>
        ) : (
          <div className="space-y-2">
            {tenants.map((t) => {
              const isActive = activeTenant?.tenant_id === t.tenant_id;
              const show = revealed[t.tenant_id];
              return (
                <div
                  key={t.tenant_id}
                  className={`rounded-lg border p-3 flex flex-col gap-2 ${
                    isActive ? 'border-zhiyan-300 bg-zhiyan-50/40' : 'border-gray-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800">🏢 {t.name}</span>
                      {isActive && <span className="badge badge-green">当前</span>}
                    </div>
                    <code className="text-[10px] font-mono text-gray-400">{t.tenant_id}</code>
                  </div>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs font-mono break-all bg-gray-50 rounded px-2 py-1.5 text-gray-600">
                      {show ? t.api_key : maskKey(t.api_key)}
                    </code>
                    <button
                      className="text-xs text-gray-500 hover:text-gray-700"
                      onClick={() => setRevealed((r) => ({ ...r, [t.tenant_id]: !r[t.tenant_id] }))}
                    >
                      {show ? '隐藏' : '显示'}
                    </button>
                    <button className="text-xs text-gray-500 hover:text-gray-700" onClick={() => copy(t.api_key)}>
                      复制
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!isActive && (
                      <button className="text-xs btn-secondary px-3 py-1" onClick={() => setActive(t.tenant_id)}>
                        设为当前
                      </button>
                    )}
                    <button className="text-xs btn-secondary px-3 py-1" onClick={() => handleRotate(t)}>
                      轮换密钥
                    </button>
                    <button
                      className="text-xs px-3 py-1 rounded-lg border border-red-200 text-red-600 hover:bg-red-50"
                      onClick={() => handleDelete(t)}
                    >
                      注销
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 网关配置（仅当前租户） */}
      {activeTenant && (
        <div className="card">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">🛰️</span>
            <h2 className="text-base font-semibold text-gray-800">租户级网关配置</h2>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            为当前租户覆写工业协议网关连接参数；留空字段沿用平台共享网关。保存后立即对租户生效。
          </p>
          {gwLoading ? (
            <p className="text-sm text-gray-400">加载中…</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {([
                ['modbus_host', 'Modbus 主机'],
                ['modbus_port', 'Modbus 端口', 'number'],
                ['mqtt_broker', 'MQTT Broker'],
                ['mqtt_port', 'MQTT 端口', 'number'],
                ['opcua_endpoint', 'OPC-UA Endpoint'],
                ['ipc_cfx_broker', 'IPC-CFX Broker'],
              ] as [keyof GatewayConfig, string, string?][]).map(([k, label, type]) => (
                <div key={k} className="flex flex-col gap-1">
                  <label className="text-xs text-gray-400">{label}</label>
                  <input
                    className="input"
                    type={type === 'number' ? 'number' : 'text'}
                    placeholder="沿用平台默认"
                    value={(gw[k] as string | number | undefined) ?? ''}
                    onChange={(e) =>
                      setGw((g) => ({
                        ...g,
                        [k]: type === 'number' ? (e.target.value ? Number(e.target.value) : undefined) : e.target.value || undefined,
                      }))
                    }
                  />
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2 mt-4">
            <button className="btn-primary" onClick={handleSaveGw}>
              保存配置
            </button>
            <button className="btn-secondary" onClick={handleClearGw}>
              清除覆写
            </button>
            {gwMsg && <span className="text-sm self-center">{gwMsg}</span>}
          </div>
        </div>
      )}

      {/* 隔离说明 */}
      <div className="card bg-gradient-to-br from-zhiyan-50/40 to-white border-zhiyan-100">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">🔒</span>
          <h2 className="text-base font-semibold text-gray-800">多租户隔离说明</h2>
        </div>
        <ul className="text-sm text-gray-600 space-y-1.5 list-disc list-inside">
          <li>行级隔离：所有会话、授权边界、审计日志都带 <code className="font-mono text-xs">tenant_id</code>，按租户过滤。</li>
          <li>密钥认证：每次请求在请求头携带 <code className="font-mono text-xs">X-Tenant-Key</code>；无效密钥返回 401。</li>
          <li>切换租户即切换数据视图：本页与顶部切换器选择的租户，决定你看到的是哪一家的会话与报表。</li>
          <li>密钥仅存于本浏览器，不会上传到平台之外；注销租户会同时在平台删除其数据。</li>
        </ul>
      </div>
    </div>
  );
}
