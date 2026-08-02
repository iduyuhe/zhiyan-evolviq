import { useEffect, useState } from 'react';
import { authHeaders, apiUrl } from '../api/client';

interface NorthStarReport {
  decision_realization_rate_real: number | null;
  decision_realization_count_real: number;
  decision_realization_rate_demo: number;
  decision_realization_count_demo: number;
  real_time_active: boolean;
  demo_data_active: boolean;
  target_mvp: number;
  target_steady: number;
  note?: string;
}

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `${Math.round(v * 1000) / 10}%`;
}

/**
 * F3 · 北极星「真实率 / 演示率」双率区分条
 *
 * 应用型可信度：真实客户信号驱动的决策实时化率与演示种子数据的实时化率
 * 必须在 UI 上一眼可分，绝不合并成一个「看起来很好」的总数。
 *
 * 韧性：接口异常 / 未登录 一律静默隐藏，绝不影响主流程渲染（白屏铁律）。
 */
export default function NorthStarStrip() {
  const [data, setData] = useState<NorthStarReport | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(apiUrl('/reports/north-star'), { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (alive && d && typeof d === 'object') setData(d as NorthStarReport);
      })
      .catch(() => {
        /* 静默降级 */
      });
    return () => {
      alive = false;
    };
  }, []);

  if (!data) return null;

  const realRate = data.decision_realization_rate_real;
  const mvpTarget = data.target_mvp ?? 0.4;
  const realReached = realRate !== null && realRate >= mvpTarget;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
      {/* 真实客户信号率——唯一计入北极星的口径 */}
      <div
        className={`rounded-lg border px-3 py-2.5 ${
          data.real_time_active
            ? 'border-green-200 bg-green-50'
            : 'border-gray-200 bg-gray-50'
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-gray-600 flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${data.real_time_active ? 'bg-green-500' : 'bg-gray-300'}`} />
            决策实时化率 · 真实客户信号
          </span>
          <span className={`text-lg font-bold leading-none ${data.real_time_active ? 'text-green-700' : 'text-gray-400'}`}>
            {pct(realRate)}
          </span>
        </div>
        <p className="mt-1 text-[10px] leading-4 text-gray-500">
          {data.real_time_active
            ? `基于 ${data.decision_realization_count_real} 条真实客户信号 · MVP 目标 ${pct(mvpTarget)}${realReached ? ' ✅ 已达标' : ' ⏳ 未达标'}`
            : '尚无真实客户信号接入，北极星尚未起跳'}
        </p>
      </div>

      {/* 演示数据率——不计入北极星，仅供能力演示 */}
      <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-gray-500 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-gray-400" />
            演示数据实时化率（不计入北极星）
          </span>
          <span className="text-lg font-bold leading-none text-gray-500">
            {pct(data.decision_realization_rate_demo)}
          </span>
        </div>
        <p className="mt-1 text-[10px] leading-4 text-gray-400">
          基于 {data.decision_realization_count_demo} 条演示种子数据 · 仅用于能力演示，不代表真实生产成效
        </p>
      </div>
    </div>
  );
}
