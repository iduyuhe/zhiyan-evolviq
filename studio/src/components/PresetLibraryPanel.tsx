/**
 * 设备预设库（#426 独立页）
 *
 * 消费 /presets/library：设备库（按行业分组）+ ERP 库 + MES 库 + 权限模板概览。
 * 行业可展开 → /presets/library/{industry}：单行业设备模板明细（OPC-UA 标签 / 关键部件 / 能耗 / MTBF）。
 *
 * 🔴 鉴权守卫：挂载即 fetch 的 effect 必须 gate 在 token 存在（否则 401 悬空态）。
 */
import { useCallback, useEffect, useState } from 'react';
import { apiUrl, authHeaders, getToken } from '../api/client';

interface Equipment {
  equipment_id: string;
  name: string;
  type_cn: string;
  vendor: string;
  model: string;
  opcua_tag_count: number;
  key_part_count?: number;
  power_kw_avg?: number;
  mtbf_hours?: number;
}
interface IndustryGroup {
  industry: string;
  industry_cn: string;
  equipment_type_count: number;
  profile_count: number;
  equipments: Equipment[];
}
interface PresetItem {
  key: string;
  name: string;
  vendor: string;
  version: string;
  interfaces: string[];
  data_domain_count: number;
  agent_count: number;
}
interface LibraryData {
  equipment: {
    industry_count: number;
    type_count: number;
    profile_count: number;
    industries: IndustryGroup[];
  };
  erp: { count: number; items: PresetItem[] };
  mes: { count: number; items: PresetItem[] };
  permission: { role_count: number; industries: string[] };
  coverage: string;
}
interface EquipmentDetail extends Equipment {
  opcua_tags: { tag: string; default: string | number; unit: string; desc: string }[];
  key_parts: string[];
  power_kw_peak?: number;
  coolant_flow_lpm?: number;
}

export default function PresetLibraryPanel() {
  const [data, setData] = useState<LibraryData | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detailEquips, setDetailEquips] = useState<EquipmentDetail[]>([]);
  const [busy, setBusy] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    if (!getToken()) return; // 🔴 鉴权守卫
    setBusy(true);
    setMsg('');
    try {
      const r = await fetch(apiUrl('/presets/library'), { headers: authHeaders() });
      if (!r.ok) throw new Error(`预设库加载失败 (${r.status})`);
      setData(await r.json());
    } catch (e) {
      setMsg('❌ ' + (e instanceof Error ? e.message : '加载失败'));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleIndustry = useCallback(async (code: string) => {
    if (expanded === code) { setExpanded(null); setDetailEquips([]); return; }
    setExpanded(code);
    setLoadingDetail(true);
    setDetailEquips([]);
    try {
      const r = await fetch(apiUrl(`/presets/library/${code}`), { headers: authHeaders() });
      if (!r.ok) throw new Error(`明细加载失败 (${r.status})`);
      const d = await r.json();
      setDetailEquips(d.equipments || []);
    } catch (e) {
      setMsg('❌ ' + (e instanceof Error ? e.message : '明细加载失败'));
    } finally {
      setLoadingDetail(false);
    }
  }, [expanded]);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span>🔧</span> 设备预设库
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          预设层：典型设备 / ERP / MES 模板开箱即用 · 客户接入同型号设备即套模板，数日而非数月
        </p>
      </div>

      {msg && <div className="text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">{msg}</div>}

      {busy && <div className="text-xs text-gray-400">加载中…</div>}

      {data && (
        <>
          {/* 概览统计 */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="覆盖行业" value={data.equipment.industry_count} unit="个" />
            <Stat label="设备类 / 台" value={`${data.equipment.type_count}/${data.equipment.profile_count}`} />
            <Stat label="ERP / MES 预设" value={`${data.erp.count}/${data.mes.count}`} />
            <Stat label="权限角色" value={data.permission.role_count} unit="个" />
          </div>
          {data.coverage && (
            <div className="text-[11px] text-gray-400">📡 行业覆盖：{data.coverage}</div>
          )}

          {/* 设备库（按行业） */}
          <section className="space-y-3">
            <h3 className="font-semibold text-gray-800">设备库 · 按行业</h3>
            {data.equipment.industries.map((ind) => (
              <div key={ind.industry} className="bg-white rounded-xl shadow-sm border border-gray-100">
                <button
                  onClick={() => toggleIndustry(ind.industry)}
                  className="w-full flex items-center justify-between px-4 py-3 text-left"
                >
                  <div>
                    <div className="font-medium text-gray-900">
                      {ind.industry_cn}
                      <span className="text-[11px] text-gray-400 ml-2">{ind.profile_count} 台 · {ind.equipment_type_count} 类</span>
                    </div>
                  </div>
                  <span className="text-gray-400 text-sm">{expanded === ind.industry ? '▾' : '▸'}</span>
                </button>

                {/* 折叠：设备卡片摘要 */}
                {expanded !== ind.industry && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 px-4 pb-3">
                    {ind.equipments.map((e) => (
                      <div key={e.equipment_id} className="border border-gray-100 rounded-lg px-3 py-2 text-xs">
                        <div className="font-medium text-gray-800">{e.name}</div>
                        <div className="text-gray-400">{e.type_cn} · {e.vendor}{e.model ? ` ${e.model}` : ''}</div>
                        <div className="text-gray-500 mt-1">
                          OPC-UA {e.opcua_tag_count} 标签 · 关键部件 {e.key_part_count ?? '—'} · 均功 {e.power_kw_avg ?? '—'}kW · MTBF {e.mtbf_hours ?? '—'} h
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 展开：明细（OPC-UA 标签 / 关键部件 / 能耗） */}
                {expanded === ind.industry && (
                  <div className="px-4 pb-4 space-y-3">
                    {loadingDetail && <div className="text-xs text-gray-400">加载明细…</div>}
                    {detailEquips.map((e) => (
                      <div key={e.equipment_id} className="border border-zhiyan-100 rounded-lg p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-gray-800">{e.name}</span>
                          <span className="text-[11px] text-gray-400">{e.type_cn}</span>
                        </div>
                        <div className="text-xs text-gray-500">{e.vendor}{e.model ? ` · ${e.model}` : ''}</div>
                        <div className="flex flex-wrap gap-3 text-[11px] text-gray-500">
                          <span>均功 {e.power_kw_avg ?? '—'} kW{e.power_kw_peak ? ` / 峰 ${e.power_kw_peak} kW` : ''}</span>
                          {e.coolant_flow_lpm ? <span>冷却液 {e.coolant_flow_lpm} L/min</span> : null}
                          <span>MTBF {e.mtbf_hours ?? '—'} h</span>
                        </div>
                        {e.opcua_tags.length > 0 && (
                          <div>
                            <div className="text-[11px] text-gray-400 mb-1">OPC-UA 标签（{e.opcua_tags.length}）</div>
                            <div className="flex flex-wrap gap-1">
                              {e.opcua_tags.map((t, i) => (
                                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-zhiyan-50 text-zhiyan-700 font-mono">
                                  {t.tag}={t.default}{t.unit}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {e.key_parts.length > 0 && (
                          <div>
                            <div className="text-[11px] text-gray-400 mb-1">关键部件（{e.key_parts.length}）</div>
                            <div className="flex flex-wrap gap-1">
                              {e.key_parts.map((k, i) => (
                                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{k}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </section>

          {/* ERP / MES 预设 */}
          <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <PresetCard title="ERP 预设" count={data.erp.count} items={data.erp.items} />
            <PresetCard title="MES 预设" count={data.mes.count} items={data.mes.items} />
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-3">
      <div className="text-[11px] text-gray-400">{label}</div>
      <div className="text-lg font-semibold text-zhiyan-700 mt-0.5">
        {value}
        {unit && <span className="text-xs text-gray-400 ml-0.5">{unit}</span>}
      </div>
    </div>
  );
}

function PresetCard({ title, count, items }: { title: string; count: number; items: PresetItem[] }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold text-gray-800">{title}</h4>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">{count} 套</span>
      </div>
      <div className="space-y-1.5">
        {items.map((it) => (
          <div key={it.key} className="border border-gray-100 rounded-lg px-3 py-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-gray-800 font-medium">{it.name}</span>
              <span className="text-gray-400">{it.vendor}{it.version ? ` ${it.version}` : ''}</span>
            </div>
            <div className="text-gray-500 mt-0.5">
              接口 {it.interfaces.length} · 数据域 {it.data_domain_count} · 映射 Agent {it.agent_count}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
