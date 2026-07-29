import { useState, useEffect, useCallback } from 'react';
import {
  getConnectivity,
  testGateway,
  testRegisteredDataSource,
  testDataSource,
  listDataSources,
  addDataSource,
  getConnectors,
  testConnector,
  pullEmail,
  ConnectivityOverview,
  ConnectivityTestResult,
  SocialConnector,
  DataSourceEntry,
} from '../api/client';
import EnterpriseOnboardingPanel from './EnterpriseOnboardingPanel';

const GATEWAY_PROTOCOLS = ['opcua', 'mqtt', 'modbus', 'ipc_cfx'] as const;
const DS_KINDS = ['mes', 'erp', 'plm', 'wms', 'timeseries'] as const;

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span
        className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`}
      />
      <span className="text-gray-700">{label}</span>
    </span>
  );
}

function TestBadge({ r }: { r: ConnectivityTestResult | null }) {
  if (!r) return <span className="text-xs text-gray-400">未测试</span>;
  const ok = r.ok;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
      {ok ? '已连接' : '异常'}
      {r.latency_ms != null && ` · ${Math.round(r.latency_ms)}ms`}
    </span>
  );
}

export default function ConnectivityPanel() {
  const [overview, setOverview] = useState<ConnectivityOverview | null>(null);
  const [loading, setLoading] = useState(false);

  const [gwProtocol, setGwProtocol] = useState<string>('opcua');
  const [gwEndpoint, setGwEndpoint] = useState('');
  const [gwResult, setGwResult] = useState<ConnectivityTestResult | null>(null);
  const [gwTesting, setGwTesting] = useState(false);

  const [dsList, setDsList] = useState<DataSourceEntry[]>([]);
  const [dsKind, setDsKind] = useState<string>('mes');
  const [dsUrl, setDsUrl] = useState('');
  const [dsKey, setDsKey] = useState('');
  const [dsResult, setDsResult] = useState<ConnectivityTestResult | null>(null);
  const [dsTesting, setDsTesting] = useState(false);
  const [dsSaving, setDsSaving] = useState(false);
  const [dsMsg, setDsMsg] = useState('');

  const [connectors, setConnectors] = useState<SocialConnector[]>([]);
  const [connResults, setConnResults] = useState<Record<string, ConnectivityTestResult>>({});
  const [connTesting, setConnTesting] = useState<string | null>(null);
  const [emailPulling, setEmailPulling] = useState(false);
  const [emailMsg, setEmailMsg] = useState('');

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      const ov = await getConnectivity();
      setOverview(ov);
      if (Array.isArray(ov.data_sources)) setDsList(ov.data_sources as DataSourceEntry[]);
      if (Array.isArray(ov.connectors)) setConnectors(ov.connectors as SocialConnector[]);
    } catch {
      /* 静默 */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();
    listDataSources()
      .then(setDsList)
      .catch(() => {});
    getConnectors()
      .then((d) => setConnectors(d.connectors))
      .catch(() => {});
  }, [refreshAll]);

  // ---- 网关连通性测试 ----
  const onTestGateway = async () => {
    setGwTesting(true);
    setGwResult(null);
    try {
      const r = await testGateway(gwProtocol, gwEndpoint || undefined);
      setGwResult(r);
    } catch (e) {
      setGwResult({ ok: false, detail: (e as Error).message });
    } finally {
      setGwTesting(false);
    }
  };

  // ---- 数据源：先测试后保存（§4.4 铁律）----
  const onTestDs = async () => {
    setDsTesting(true);
    setDsResult(null);
    setDsMsg('');
    const config = { base_url: dsUrl, api_key: dsKey };
    try {
      // 优先用待保存配置测试（/connectivity/datasource 不落地）
      const r = dsUrl ? await testDataSource(dsKind, config) : await testRegisteredDataSource(dsKind);
      setDsResult(r);
    } catch (e) {
      setDsResult({ ok: false, detail: (e as Error).message });
    } finally {
      setDsTesting(false);
    }
  };

  const onSaveDs = async () => {
    setDsMsg('');
    // 保存前强制先测试（路线图 §4.4：未通过连通性验证不得保存）
    setDsTesting(true);
    const config = { base_url: dsUrl, api_key: dsKey };
    try {
      const r = dsUrl ? await testDataSource(dsKind, config) : await testRegisteredDataSource(dsKind);
      setDsResult(r);
      if (!r.ok) {
        setDsMsg('⚠️ 连通性验证未通过，已阻止保存：' + (r.detail || ''));
        return;
      }
      setDsSaving(true);
      await addDataSource(dsKind, config);
      setDsMsg('✅ 连通性验证通过，数据源已保存');
      await refreshAll();
    } catch (e) {
      setDsMsg('保存失败：' + (e as Error).message);
    } finally {
      setDsTesting(false);
      setDsSaving(false);
    }
  };

  // ---- 社交连接器 ----
  const onTestConn = async (name: string) => {
    setConnTesting(name);
    try {
      const r = await testConnector(name);
      setConnResults((p) => ({ ...p, [name]: r }));
    } catch (e) {
      setConnResults((p) => ({ ...p, [name]: { ok: false, detail: (e as Error).message } }));
    } finally {
      setConnTesting(null);
    }
  };

  const onPullEmail = async () => {
    setEmailPulling(true);
    setEmailMsg('');
    try {
      const r = await pullEmail();
      setEmailMsg(`已拉取 ${r.pulled} 封，发布 ${r.published} 条（敏感待审 ${r.sensitive}）`);
    } catch (e) {
      setEmailMsg('拉取失败：' + (e as Error).message);
    } finally {
      setEmailPulling(false);
    }
  };

  const dsAvailable = (kind: string): boolean | null => {
    const e = dsList.find((d) => d.kind === kind);
    return e ? e.available : null;
  };

  return (
    <div className="space-y-5">
      {/* A. 系统连通性概览 */}
      <section className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900">系统连通性概览</h3>
          <button className="btn-secondary text-xs" onClick={refreshAll} disabled={loading}>
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>
        {overview ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatusDot ok={!!overview.db?.available} label={`数据库 (${overview.db?.mode || '?'})`} />
            <StatusDot ok={!!overview.knowledge_graph?.available} label={`知识图谱 (${overview.knowledge_graph?.mode || '?'})`} />
            <StatusDot
              ok={!!overview.gateways?.ready}
              label={`网关 ${overview.gateways?.ready || 0}/${overview.gateways?.total || 0} 就绪`}
            />
          </div>
        ) : (
          <p className="text-sm text-gray-400">加载中…</p>
        )}
      </section>

      {/* B. 工业协议网关连通性 */}
      <section className="card p-4">
        <h3 className="font-semibold text-gray-900 mb-3">工业协议网关 · 连通性验证</h3>
        <div className="flex flex-wrap items-end gap-2">
          <select
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={gwProtocol}
            onChange={(e) => setGwProtocol(e.target.value)}
          >
            {GATEWAY_PROTOCOLS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[200px]"
            placeholder="自定义端点（留空用默认配置），如 opc.tcp://host:4840"
            value={gwEndpoint}
            onChange={(e) => setGwEndpoint(e.target.value)}
          />
          <button className="btn-primary text-sm" onClick={onTestGateway} disabled={gwTesting}>
            {gwTesting ? '测试中…' : '测试连接'}
          </button>
          <TestBadge r={gwResult} />
        </div>
        {gwResult?.detail && (
          <p className="text-xs text-gray-500 mt-2">{gwResult.detail}</p>
        )}
      </section>

      {/* C. 数据源接入（保存前必须测试）*/}
      <section className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900">数据源接入 · 连通性验证（§4.4 铁律）</h3>
        </div>

        {/* 已注册数据源列表 */}
        <div className="space-y-1.5 mb-4">
          {DS_KINDS.map((k) => {
            const av = dsAvailable(k);
            return (
              <div key={k} className="flex items-center justify-between text-sm border-b border-gray-100 pb-1.5">
                <span className="font-medium text-gray-700 uppercase">{k}</span>
                <span className="flex items-center gap-2">
                  {av == null ? (
                    <span className="text-xs text-gray-400">未注册</span>
                  ) : av ? (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">已连接</span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">回退 seed</span>
                  )}
                  <button
                    className="text-xs text-zhiyan-600 hover:underline"
                    onClick={() => {
                      setDsKind(k);
                      setDsUrl('');
                      setDsResult(null);
                      onTestDs();
                    }}
                  >
                    测试
                  </button>
                </span>
              </div>
            );
          })}
        </div>

        {/* 新增数据源表单（带保存前测试闸门）*/}
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <p className="text-xs text-gray-500">新增 / 覆写数据源（保存前将自动验证连通性，未通过则阻止保存）</p>
          <div className="flex flex-wrap items-end gap-2">
            <select
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
              value={dsKind}
              onChange={(e) => setDsKind(e.target.value)}
            >
              {DS_KINDS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <input
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[180px]"
              placeholder="base_url，如 https://mes.internal/api"
              value={dsUrl}
              onChange={(e) => setDsUrl(e.target.value)}
            />
            <input
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-40"
              placeholder="api_key（可选）"
              value={dsKey}
              onChange={(e) => setDsKey(e.target.value)}
            />
            <button className="btn-secondary text-sm" onClick={onTestDs} disabled={dsTesting}>
              {dsTesting ? '测试中…' : '先测试'}
            </button>
            <button className="btn-primary text-sm" onClick={onSaveDs} disabled={dsSaving || dsTesting}>
              {dsSaving ? '保存中…' : '测试通过再保存'}
            </button>
            <TestBadge r={dsResult} />
          </div>
          {dsResult?.detail && <p className="text-xs text-gray-500">{dsResult.detail}</p>}
          {dsMsg && <p className={`text-xs ${dsMsg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>{dsMsg}</p>}
        </div>
      </section>

      {/* D. 社交通道接入（隐性捕获生产态）*/}
      <section className="card p-4">
        <h3 className="font-semibold text-gray-900 mb-1">社交通道接入 · 隐性捕获</h3>
        <p className="text-xs text-gray-500 mb-3">
          把企业微信 / 钉钉 / 邮件的真实外部信号经 token 鉴权后喂入隐性捕获管线。下方回调 URL 配置到对应平台后台。
        </p>
        <div className="space-y-3">
          {connectors.length === 0 && <p className="text-sm text-gray-400">加载中…</p>}
          {connectors.map((c) => (
            <div key={c.name} className="border border-gray-100 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-800 uppercase">{c.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${c.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {c.enabled ? '已配置' : '未配置'}
                  </span>
                </div>
                <button
                  className="text-xs text-zhiyan-600 hover:underline"
                  onClick={() => onTestConn(c.name)}
                  disabled={connTesting === c.name}
                >
                  {connTesting === c.name ? '测试中…' : '测试'}
                </button>
              </div>
              <TestBadge r={connResults[c.name] || null} />
              {!c.enabled && (
                <p className="text-xs text-gray-500 mt-1">
                  在后端环境变量配置对应密钥即可启用（如 ZHIYAN_WECOM_TOKEN / ZHIYAN_DINGTALK_SECRET / ZHIYAN_EMAIL_IMAP_*）。
                </p>
              )}
              {c.name === 'wecom' && c.enabled && (
                <p className="text-[11px] text-gray-400 mt-1 break-all">
                  回调 URL：/api/connectors/wecom/callback（企微后台「接收消息」配置，Token 需与 ZHIYAN_WECOM_TOKEN 一致）
                </p>
              )}
              {c.name === 'dingtalk' && c.enabled && (
                <p className="text-[11px] text-gray-400 mt-1 break-all">
                  回调 URL：/api/connectors/dingtalk/callback（钉钉机器人「加签」secret 需与 ZHIYAN_DINGTALK_SECRET 一致）
                </p>
              )}
              {c.name === 'email' && c.enabled && (
                <div className="mt-1 flex items-center gap-2">
                  <button className="text-xs btn-secondary" onClick={onPullEmail} disabled={emailPulling}>
                    {emailPulling ? '拉取中…' : '立即拉取'}
                  </button>
                  {emailMsg && <span className="text-[11px] text-gray-500">{emailMsg}</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* E. 企业入驻 · 现状描述与接口实例化（Phase 2 两阶段实例化框架） */}
      <EnterpriseOnboardingPanel />
    </div>
  );
}
