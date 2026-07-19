import { useState, useEffect, useCallback } from 'react';

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

export default function DeviceMonitor() {
  const [sensors, setSensors] = useState<SensorData[]>(MOCK_SENSORS);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const refreshData = useCallback(() => {
    setSensors(prev => prev.map(s => {
      if (typeof s.value === 'number') {
        let newVal: number;
        if (s.tag.includes('temperature') || s.tag.includes('temp')) {
          newVal = randomWalk(s.value, 0.8);
        } else if (s.tag.includes('rate') || s.tag.includes('speed')) {
          newVal = Math.max(0, Math.min(100, randomWalk(s.value, 3)));
        } else if (s.tag.includes('level')) {
          newVal = Math.max(0, Math.min(100, randomWalk(s.value, 4)));
        } else if (s.tag.includes('count')) {
          newVal = s.value + Math.floor(Math.random() * 10);
        } else {
          newVal = randomWalk(s.value, 2);
        }
        return { ...s, value: Math.round(newVal * 10) / 10 };
      }
      return s;
    }));
    setLastUpdated(new Date());
  }, []);

  useEffect(() => {
    const interval = setInterval(refreshData, 3000);
    return () => clearInterval(interval);
  }, [refreshData]);

  const statusIcon = (status: string) => {
    switch (status) {
      case 'normal': return '🟢';
      case 'warning': return '🟡';
      case 'alarm': return '🔴';
      default: return '⚪';
    }
  };

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
              <h2 className="text-lg font-semibold text-gray-900">设备监控面板</h2>
              <p className="text-xs text-gray-400">Modbus + MQTT 协议网关实时数据</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              实时
            </span>
            <span className="text-gray-400">
              {lastUpdated.toLocaleTimeString('zh-CN')}
            </span>
            <button className="btn-secondary text-xs py-1.5 px-3" onClick={refreshData}>
              刷新
            </button>
          </div>
        </div>
      </div>

      {/* 传感器网格 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {sensors.map((sensor) => (
          <div key={sensor.tag} className={`card p-4 hover:shadow-md transition-all duration-300
            ${sensor.status === 'alarm' ? 'border-red-200 bg-red-50/30' : ''}
            ${sensor.status === 'warning' ? 'border-yellow-200 bg-yellow-50/30' : ''}
          `}>
            <div className="flex items-start justify-between mb-2">
              <span className="text-xs text-gray-400 font-mono truncate max-w-[180px]" title={sensor.tag}>
                {sensor.status === 'alarm' ? '🔴' : sensor.status === 'warning' ? '🟡' : '🟢'}
                {' '}{sensor.tag.split('/').pop()}
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                sensor.status === 'alarm' ? 'bg-red-100 text-red-600' :
                sensor.status === 'warning' ? 'bg-yellow-100 text-yellow-600' :
                'bg-green-100 text-green-600'
              }`}>
                {sensor.status === 'alarm' ? '告警' : sensor.status === 'warning' ? '预警' : '正常'}
              </span>
            </div>

            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold text-gray-800">
                {typeof sensor.value === 'number' ? sensor.value.toLocaleString() : sensor.value}
              </span>
              {sensor.unit && <span className="text-sm text-gray-400">{sensor.unit}</span>}
            </div>

            {/* 数值类传感器显示迷你进度条 */}
            {typeof sensor.value === 'number' && sensor.value <= 100 && (
              <div className="mt-2 gauge-bar">
                <div
                  className={`gauge-fill ${
                    sensor.status === 'alarm' ? 'bg-red-500' :
                    sensor.status === 'warning' ? 'bg-yellow-500' :
                    'bg-emerald-500'
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
    </div>
  );
}
