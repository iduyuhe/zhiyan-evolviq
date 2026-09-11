import { useState, useEffect, useCallback } from 'react';
import { authHeaders, apiUrl } from '../api/client';
import { useTenant } from '../tenant/TenantContext';

interface SensorData {
  tag: string;
  value: number | string;
  unit?: string;
  status: 'normal' | 'warning' | 'alarm';
}

const MOCK_SENSORS: SensorData[] = [
  // 洁净室环境
  { tag: 'fab/cleanroom/temperature', value: 22.5, unit: '°C', status: 'normal' },
  { tag: 'fab/cleanroom/humidity', value: 42, unit: '%', status: 'normal' },
  { tag: 'fab/cleanroom/particles_0.1um', value: 125, unit: 'pcf', status: 'normal' },
  { tag: 'fab/cleanroom/particles_0.5um', value: 8, unit: 'pcf', status: 'normal' },
  // 光刻区
  { tag: 'fab/litho/scanner_1_status', value: '运行中', status: 'normal' },
  { tag: 'fab/litho/scanner_1_throughput', value: 95, unit: 'wph', status: 'normal' },
  { tag: 'fab/litho/overlay_error', value: 1.2, unit: 'nm', status: 'normal' },
  // 刻蚀区
  { tag: 'fab/etch/etcher_1_status', value: '运行中', status: 'normal' },
  { tag: 'fab/etch/etcher_1_chamber_pressure', value: 15.0, unit: 'mTorr', status: 'normal' },
  { tag: 'fab/etch/etcher_1_gas_flow', value: 85, unit: 'sccm', status: 'normal' },
  // 物料缓存
  { tag: 'fab/stocker/si_wafer_level', value: 62, unit: '%', status: 'normal' },
  { tag: 'fab/stocker/photoresist_level', value: 38, unit: '%', status: 'warning' },
  { tag: 'fab/stocker/special_gas_nf3', value: 55, unit: '%', status: 'normal' },
  // 质量
  { tag: 'fab/quality/defect_density', value: 0.08, unit: '/cm²', status: 'normal' },
  { tag: 'fab/quality/yield_rate', value: 92.5, unit: '%', status: 'normal' },
];

function randomWalk(value: number, range: number): number {
  return Math.round((value + (Math.random() - 0.5) * range) * 10) / 10;
}
function rnd(min: number, max: number): number {
  return Math.round((min + Math.random() * (max - min)) * 10) / 10;
}
function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

// ===== 租户设备孪生（按行业匹配预设模板，租户隔离）=====
interface EquipSeed {
  equipment_id: string;
  name: string;
  type_cn: string;
  vendor: string;
  model: string;
  opcua_tag_count: number;
  mtbf_hours: number;
}
interface EquipSensor {
  label: string;
  value: number;
  unit: string;
  range: number;
  max: number;
}
interface LiveEquip extends EquipSeed {
  health: number;
  uptime: number;
  status: 'running' | 'warning' | 'alarm';
  sensors: EquipSensor[];
  last_pm: string;
  next_pm: string;
}

function seedSensors(): EquipSensor[] {
  return [
    { label: '振动', unit: 'mm/s', value: rnd(1.2, 3.4), range: 0.5, max: 12 },
    { label: '温度', unit: '°C', value: rnd(38, 62), range: 2.2, max: 120 },
    { label: '电流', unit: 'A', value: rnd(40, 130), range: 7, max: 400 },
    { label: '转速', unit: 'rpm', value: rnd(800, 1500), range: 55, max: 5000 },
  ];
}
function toLive(e: EquipSeed): LiveEquip {
  return {
    ...e,
    health: rnd(82, 97),
    uptime: Math.floor(rnd(2000, 9000)),
    status: 'running',
    sensors: seedSensors(),
    last_pm: `2026-0${Math.ceil(rnd(1, 6))}-${pad2(Math.floor(rnd(1, 28)))}`,
    next_pm: `2026-0${Math.ceil(rnd(7, 9))}-${pad2(Math.floor(rnd(1, 28)))}`,
  };
}
function walk(v: number, range: number, max: number): number {
  const nv = v + (Math.random() - 0.5) * range * 2;
  return Math.round(Math.max(0, Math.min(max, nv)) * 10) / 10;
}

export default function DeviceMonitor() {
  const { activeTenant } = useTenant();
  const [sensors, setSensors] = useState<SensorData[]>(MOCK_SENSORS);
  // null=未加载 / []=本租户无匹配设备(走 mock) / 有数据=渲染设备卡片
  const [equips, setEquips] = useState<LiveEquip[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const loadEquip = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(apiUrl('/enterprise/recommendations'), { headers: authHeaders() });
      if (r.ok) {
        const data = await r.json();
        const list: EquipSeed[] = data?.equipment_presets?.equipments || [];
        setEquips(list.length > 0 ? list.map(toLive) : []);
        // 把本租户设备孪生上线进 UNS 事件流（孪生大屏实时可见），best-effort
        if (list.length > 0) {
          fetch(apiUrl('/enterprise/equipment/seed-uns'), {
            method: 'POST',
            headers: authHeaders(),
          }).catch(() => {});
        }
      } else {
        setEquips([]);
      }
    } catch {
      setEquips([]);
    } finally {
      setLoading(false);
      setLastUpdated(new Date());
    }
  }, []);

  // 租户切换 / 挂载时重拉本租户设备
  useEffect(() => {
    loadEquip();
  }, [loadEquip, activeTenant?.tenant_id]);

  // mock 传感器实时游走（无匹配设备时）
  const refreshMock = useCallback(() => {
    setSensors((prev) =>
      prev.map((s) => {
        if (typeof s.value === 'number') {
          let newVal: number;
          if (s.tag.includes('temperature') || s.tag.includes('temp')) newVal = randomWalk(s.value, 0.8);
          else if (s.tag.includes('rate') || s.tag.includes('speed')) newVal = Math.max(0, Math.min(100, randomWalk(s.value, 3)));
          else if (s.tag.includes('level')) newVal = Math.max(0, Math.min(100, randomWalk(s.value, 4)));
          else if (s.tag.includes('count')) newVal = s.value + Math.floor(Math.random() * 10);
          else newVal = randomWalk(s.value, 2);
          return { ...s, value: Math.round(newVal * 10) / 10 };
        }
        return s;
      })
    );
    setLastUpdated(new Date());
  }, []);
  useEffect(() => {
    if (!equips || equips.length === 0) {
      const i = setInterval(refreshMock, 3000);
      return () => clearInterval(i);
    }
  }, [equips, refreshMock]);

  // 设备健康分 + 传感器实时游走
  const tickEquip = useCallback(() => {
    setEquips((prev) =>
      prev
        ? prev.map((e) => ({
            ...e,
            health: walk(e.health, 1.2, 100),
            sensors: e.sensors.map((s) => ({ ...s, value: walk(s.value, s.range, s.max) })),
          }))
        : prev
    );
    setLastUpdated(new Date());
  }, []);
  useEffect(() => {
    if (equips && equips.length > 0) {
      const i = setInterval(tickEquip, 3000);
      return () => clearInterval(i);
    }
  }, [equips, tickEquip]);

  const statusBadge = (st: string) => {
    if (st === 'alarm') return <span className="badge-red ml-auto">告警</span>;
    if (st === 'warning') return <span className="badge-yellow ml-auto">预警</span>;
    return <span className="badge-green ml-auto">运行中</span>;
  };

  const hasEquip = equips !== null && equips.length > 0;

  return (
    <div className="page-transition space-y-4">
      {/* 顶栏 */}
      <div className="card-highlight relative overflow-hidden">
        <div className="absolute -top-16 -right-16 w-32 h-32 bg-gradient-to-bl from-zhiyan-500/5 to-transparent rounded-full" />
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center text-white shadow-sm">
              📡
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {hasEquip ? '设备孪生监控' : '设备监控面板'}
              </h2>
              <p className="text-xs text-gray-400">
                {hasEquip
                  ? `${equips!.length} 台已匹配设备 · OPC-UA 标签实时孪生`
                  : 'Modbus + MQTT 协议网关实时数据'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              实时
            </span>
            <span className="text-gray-400">{lastUpdated.toLocaleTimeString('zh-CN')}</span>
            <button
              className="btn-secondary text-xs py-1.5 px-3"
              onClick={() => (hasEquip ? tickEquip() : refreshMock())}
            >
              刷新
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="text-center py-16 text-gray-400 text-sm">加载本租户设备孪生…</div>
      )}

      {/* 设备孪生卡片网格（按租户行业匹配） */}
      {hasEquip && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {equips!.map((e) => (
            <div
              key={e.equipment_id}
              className="card p-4 hover:shadow-md transition-all duration-300 border-emerald-100"
            >
              {/* 头部 */}
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-800 truncate">{e.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-600 shrink-0">
                      {e.type_cn}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-400 mt-0.5 truncate">
                    {e.vendor} · {e.model}
                  </p>
                </div>
                {statusBadge(e.status)}
              </div>

              {/* 健康分 */}
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-2xl font-bold text-gray-800">{e.health.toFixed(1)}</span>
                <span className="text-sm text-gray-400">健康分</span>
                <span className="text-[10px] text-gray-300 ml-1">MTBF {e.mtbf_hours}h</span>
              </div>
              <div className="mt-1 gauge-bar">
                <div
                  className={`gauge-fill ${
                    e.health >= 90 ? 'bg-emerald-500' : e.health >= 75 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, e.health))}%` }}
                />
              </div>

              {/* 指标行 */}
              <div className="grid grid-cols-2 gap-2 mt-3 text-[11px]">
                <div className="flex justify-between text-gray-500">
                  <span>运行</span>
                  <span className="font-mono text-gray-700">{e.uptime}h</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>OPC-UA</span>
                  <span className="font-mono text-gray-700">{e.opcua_tag_count} 标签</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>上次PM</span>
                  <span className="font-mono text-gray-700">{e.last_pm}</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>下次PM</span>
                  <span className="font-mono text-gray-700">{e.next_pm}</span>
                </div>
              </div>

              {/* 实时传感器芯片 */}
              <div className="flex flex-wrap gap-1.5 mt-3">
                {e.sensors.map((s) => (
                  <span
                    key={s.label}
                    className="px-2 py-1 rounded-lg bg-gray-50 border border-gray-100 text-[10px] font-mono text-gray-600"
                    title={`${s.label} 实时`}
                  >
                    {s.label} {s.value}
                    <span className="text-gray-400">{s.unit}</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* mock 传感器网格（无匹配设备时回退，兼容半导体演示租户） */}
      {!loading && !hasEquip && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {sensors.map((sensor) => (
              <div
                key={sensor.tag}
                className={`card p-4 hover:shadow-md transition-all duration-300 ${
                  sensor.status === 'alarm' ? 'border-red-200 bg-red-50/30' : ''
                } ${sensor.status === 'warning' ? 'border-yellow-200 bg-yellow-50/30' : ''}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs text-gray-400 font-mono truncate max-w-[180px]" title={sensor.tag}>
                    {sensor.status === 'alarm' ? '🔴' : sensor.status === 'warning' ? '🟡' : '🟢'}
                    {' '}
                    {sensor.tag.split('/').pop()}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      sensor.status === 'alarm'
                        ? 'bg-red-100 text-red-600'
                        : sensor.status === 'warning'
                        ? 'bg-yellow-100 text-yellow-600'
                        : 'bg-green-100 text-green-600'
                    }`}
                  >
                    {sensor.status === 'alarm' ? '告警' : sensor.status === 'warning' ? '预警' : '正常'}
                  </span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-gray-800">
                    {typeof sensor.value === 'number' ? sensor.value.toLocaleString() : sensor.value}
                  </span>
                  {sensor.unit && <span className="text-sm text-gray-400">{sensor.unit}</span>}
                </div>
                {typeof sensor.value === 'number' && sensor.value <= 100 && (
                  <div className="mt-2 gauge-bar">
                    <div
                      className={`gauge-fill ${
                        sensor.status === 'alarm'
                          ? 'bg-red-500'
                          : sensor.status === 'warning'
                          ? 'bg-yellow-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.max(0, Math.min(100, sensor.value))}%` }}
                    />
                  </div>
                )}
                <div className="mt-1.5 text-[10px] text-gray-300 font-mono">{sensor.tag}</div>
              </div>
            ))}
          </div>

          {/* 连接状态 */}
          <div className="card">
            <h4 className="text-sm font-semibold text-gray-800 mb-3">🔌 网关连接状态</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <div className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700">Modbus TCP</div>
                  <div className="text-xs text-gray-400">localhost:5020 · 12个寄存器</div>
                </div>
                <span className="badge-green ml-auto">已连接</span>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <div className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700">MQTT Broker</div>
                  <div className="text-xs text-gray-400">localhost:1883 · 7个主题</div>
                </div>
                <span className="badge-green ml-auto">已连接</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
