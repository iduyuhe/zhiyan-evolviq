import { riskColor, riskIcon } from '../api/client';
import type { ExecutionResult, SupplyChainMetrics } from '../api/client';

interface ExecutionResultProps {
  result: ExecutionResult;
  onNewGoal: () => void;
}

function GaugeBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="gauge-bar">
      <div className={`gauge-fill ${color}`} style={{ width: `${value}%` }} />
    </div>
  );
}

function RoiGauge({ value, color, label }: { value: number; color: string; label: string }) {
  const dash = Math.max(0, Math.min(100, value)) * 0.97;
  return (
    <div className="text-center">
      <div className="relative w-24 h-24 mx-auto">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e5e7eb" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15.5" fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={`${dash} 97`} strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold" style={{ color }}>{value}%</span>
        </div>
      </div>
      <div className="text-xs text-gray-500 mt-1.5">{label}</div>
    </div>
  );
}

function DeltaBadge({ pp, suffix = 'pp' }: { pp: number; suffix?: string }) {
  const positive = pp >= 0;
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm font-semibold ${
      positive ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
    }`}>
      {positive ? '▲' : '▼'} {positive ? '+' : ''}{pp}{suffix}
    </span>
  );
}

function CompareRow({ label, before, after, unit = '' }: { label: string; before: number; after: number; unit?: string }) {
  const improved = after <= before;
  return (
    <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
      <span className="text-xs text-gray-500">{label}</span>
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-400 line-through">{before}{unit}</span>
        <span className="text-gray-300">→</span>
        <span className={`font-semibold ${improved ? 'text-green-600' : 'text-red-600'}`}>{after}{unit}</span>
      </div>
    </div>
  );
}

export default function ExecutionResultView({ result, onNewGoal }: ExecutionResultProps) {
  const m: SupplyChainMetrics | undefined = result.metrics;

  return (
    <div className="page-transition space-y-4">
      {/* ===== T3 · 齐套率 ROI 闭环（MVP 门面） ===== */}
      {m && (
        <div className="card-highlight relative overflow-hidden bg-gradient-to-br from-blue-50 via-white to-indigo-50/40">
          <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-blue-400/10 to-transparent rounded-full -mr-12 -mt-12" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-lg">📈</span>
              <h3 className="text-lg font-semibold text-gray-900">齐套率 ROI 闭环</h3>
              <span className="badge-blue text-xs ml-1">Agent 价值可演示</span>
            </div>
            <p className="text-xs text-gray-400 mb-4">基准（现货+在途） → Agent 确认开放PO / 催交延期PO / 锁定替代后（承诺齐套率）</p>

            <div className="flex items-center justify-center gap-6 mb-5">
              <RoiGauge value={m.kitting_rate_before} color="#ef4444" label="基准齐套率" />
              <div className="flex flex-col items-center gap-1">
                <span className="text-2xl text-gray-300">→</span>
                <DeltaBadge pp={m.improvement_pp} />
              </div>
              <RoiGauge value={m.kitting_rate_after} color="#2563eb" label="承诺齐套率" />
            </div>

            <div className="grid grid-cols-3 gap-2.5">
              <CompareRow label="缺料风险项" before={m.risk_items_before} after={m.risk_items_after} unit=" 项" />
              <CompareRow label="缺料总量" before={m.shortage_qty_before} after={m.shortage_qty_after} unit=" pcs" />
              <CompareRow label="交期准时率" before={m.delivery_accuracy_before} after={m.delivery_accuracy_after} unit="%" />
            </div>

            <div className="mt-3 text-center text-xs text-gray-500 bg-white/70 rounded-lg py-2 px-3 border border-blue-100">
              {m.roi_summary}
            </div>
          </div>
        </div>
      )}

      {/* 摘要卡片 — 品牌化 */}
      <div className="card-highlight relative overflow-hidden bg-gradient-to-br from-green-50 via-white to-emerald-50/30">
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-green-400/10 to-transparent rounded-full -mr-10 -mt-10" />

        <div className="relative flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <span className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-lg">✅</span>
              <h3 className="text-lg font-semibold text-gray-900">执行完成</h3>
              <span className="badge-green text-xs">Agent 已返回结果</span>
            </div>
            <p className="text-sm text-gray-600 mt-1 max-w-lg">{result.summary}</p>
            <div className="mt-2 text-xs text-gray-400">BOM: {result.bom}</div>
          </div>

          {/* 齐套率仪表（承诺齐套率） */}
          <div className="text-center flex-shrink-0">
            <div className="relative w-20 h-20">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                <circle
                  cx="18" cy="18" r="15.5" fill="none" stroke="#2563eb" strokeWidth="3"
                  strokeDasharray={`${result.completeness_pct * 0.97} 97`}
                  strokeLinecap="round"
                  className="transition-all duration-1000 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xl font-bold text-zhiyan-600">{result.completeness_pct}%</span>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-1">承诺齐套率</div>
          </div>
        </div>
      </div>

      {/* 齐套明细表 — 带 before/after 进度条 */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span>📊</span> 齐套检查明细
          <span className="text-xs text-gray-400 font-normal ml-auto">
            {result.check_details.filter(d => (d.risk_after ?? d.risk) === 'low').length}/{result.check_details.length} 项就绪
          </span>
        </h4>

        <div className="space-y-3">
          {result.check_details.map((item, i) => {
            const risk = item.risk_after ?? item.risk;
            const availAfter = item.available_after ?? item.available;
            const pct = item.required > 0 ? Math.min(100, Math.round((availAfter / item.required) * 100)) : 0;
            const showBefore = item.available_before !== undefined && item.available_after !== undefined
              && item.available_before !== item.available_after;
            return (
              <div key={i} className="flex items-center gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors">
                <div className="flex-shrink-0 w-8 text-center">
                  <span className={riskColor(risk)}>{riskIcon(risk)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-800 truncate">{item.name}</span>
                    <span className="text-xs text-gray-500 flex-shrink-0 ml-2">
                      需 {item.required.toLocaleString()}
                      {showBefore && (
                        <span className="text-gray-400"> · {item.available_before?.toLocaleString()}→{availAfter.toLocaleString()}</span>
                      )}
                      {!showBefore && <span> · 有 {availAfter.toLocaleString()}</span>}
                    </span>
                  </div>
                  <GaugeBar
                    value={pct}
                    color={risk === 'low' ? 'bg-green-500' : risk === 'medium' ? 'bg-yellow-500' : 'bg-red-500'}
                  />
                  <div className="flex justify-between mt-0.5">
                    <span className="text-xs text-gray-400">{item.material}</span>
                    <span className="text-xs font-medium text-gray-500">
                      {(item.shortage_after ?? item.shortage) > 0 ? (
                        <span className="text-red-600">缺 {(item.shortage_after ?? item.shortage)?.toLocaleString()}</span>
                      ) : (
                        <span className="text-green-600">充足</span>
                      )}
                    </span>
                  </div>
                  {/* 风险等级转换标记 */}
                  {item.risk_before && item.risk_after && item.risk_before !== item.risk_after && (
                    <div className="mt-1">
                      <span className="text-xs text-gray-400">
                        {riskIcon(item.risk_before)} {item.risk_before}
                        <span className="text-green-600"> → {riskIcon(item.risk_after)} {item.risk_after}</span>
                      </span>
                    </div>
                  )}
                </div>
                {item.alternative && (
                  <div className="flex-shrink-0 text-xs bg-zhiyan-50 text-zhiyan-600 rounded-lg px-2.5 py-1.5 max-w-[140px] truncate">
                    → {item.alternative}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 预警 */}
      {result.warning.length > 0 && (
        <div className="card border-red-200 bg-gradient-to-r from-red-50/80 to-white">
          <h4 className="text-sm font-semibold text-red-800 mb-3 flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center text-xs">🚨</span>
            预警信息
            <span className="badge-red ml-1">{result.warning.length}</span>
          </h4>
          <div className="space-y-2">
            {result.warning.map((w, i) => (
              <div key={i} className="flex items-start gap-2.5 text-sm bg-white/80 rounded-lg p-3 border border-red-100">
                <span className="text-red-400 mt-0.5">•</span>
                <span className="text-red-700">{w}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 执行操作 */}
      {result.actions_taken.length > 0 && (
        <div className="card">
          <h4 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span>⚡</span> 已执行操作
            <span className="text-xs text-gray-400 font-normal ml-auto">
              {result.actions_taken.filter(a => a.status === 'auto_confirmed' || a.status === 'auto_locked').length} 自动 · {result.actions_taken.filter(a => a.status === 'pending_approval').length} 待批
            </span>
          </h4>
          <div className="space-y-2">
            {result.actions_taken.map((action, i) => {
              const meta = actionMeta(action.type, action.status);
              return (
                <div key={i} className="flex items-center gap-3 text-sm bg-gradient-to-r from-gray-50 to-white rounded-lg p-3 border border-gray-100">
                  <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${meta.bg}`}>
                    {meta.icon}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-700 truncate">{meta.label}</div>
                    <div className="text-xs text-gray-400 mt-0.5 truncate">
                      {action.name || action.material} · {action.qty.toLocaleString()} pcs
                      {action.alternative && action.alternative !== 'null' && action.alternative !== '' ? ` · → ${action.alternative}` : ''}
                    </div>
                    {action.note && <div className="text-xs text-gray-400 mt-0.5">{action.note}</div>}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full flex-shrink-0 ${meta.badge}`}>
                    {meta.statusLabel}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 底部操作 */}
      <div className="flex gap-3 pt-2">
        <button className="btn-primary flex-1 py-3" onClick={onNewGoal}>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          设定新目标
        </button>
        <button className="btn-secondary py-3" onClick={() => window.print()}>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          导出报告
        </button>
      </div>
    </div>
  );
}

function actionMeta(type: string, status: string): { icon: string; label: string; bg: string; badge: string; statusLabel: string } {
  if (type === 'confirm_po') {
    return { icon: '📦', label: '确认开放PO交期', bg: 'bg-green-100', badge: 'bg-green-50 text-green-600', statusLabel: '已自动确认' };
  }
  if (type === 'expedite_po') {
    return { icon: '🚚', label: '紧急催交延期PO', bg: 'bg-yellow-100', badge: 'bg-yellow-50 text-yellow-600', statusLabel: '待确认' };
  }
  if (type === 'lock_alternative') {
    const auto = status === 'auto_locked';
    return {
      icon: auto ? '🔒' : '⏳',
      label: '锁定替代库存',
      bg: auto ? 'bg-green-100' : 'bg-yellow-100',
      badge: auto ? 'bg-green-50 text-green-600' : 'bg-yellow-50 text-yellow-600',
      statusLabel: auto ? '已自动执行' : '待确认',
    };
  }
  return { icon: '⚙️', label: type, bg: 'bg-gray-100', badge: 'bg-gray-100 text-gray-600', statusLabel: status };
}
