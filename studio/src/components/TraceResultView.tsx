/** 质量追溯Agent结果展示——晶圆质量根因追溯 */

interface TraceResult {
  summary?: string;
  id: string;
  product: string;
  issue: string;
  severity: string;
  affected_qty: number;
  trace_path: { step: number; from: string; to: string; finding: string }[];
  suspected_equipments: { name: string; match_score: number; reason: string }[];
  root_cause: string;
  fix_actions: string[];
  historical_similar: number;
}

export default function TraceResultView({ result, onNewGoal }: { result: TraceResult; onNewGoal: () => void }) {
  const sevColor = (s: string) => {
    if (s === 'critical') return 'badge-red';
    if (s === 'major') return 'badge-yellow';
    return 'badge-blue';
  };
  const sevLabel = (s: string) => ({ critical: '严重', major: '主要', minor: '轻微' }[s] || s);

  return (
    <div className="page-transition space-y-4">
      {/* 头部摘要 */}
      <div className="card-highlight bg-gradient-to-br from-orange-50 via-white to-amber-50/30 relative overflow-hidden">
        <div className="flex items-start gap-4">
          <span className="text-2xl">🔍</span>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-gray-900">质量追溯分析</h3>
              <span className={sevColor(result.severity)}>{sevLabel(result.severity)}</span>
            </div>
            <p className="text-sm text-gray-600">{result.issue}</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
              <span>📦 {result.product}</span>
              <span>🔢 {result.affected_qty}片受影响</span>
              <span>📁 {result.id}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 追溯路径（时序图） */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-4">📌 追溯路径</h4>
        <div className="relative">
          {/* 竖线 */}
          <div className="absolute left-3.5 top-2 bottom-2 w-0.5 bg-zhiyan-200" />
          <div className="space-y-4">
            {result.trace_path?.map((step) => (
              <div key={step.step} className="relative flex items-start gap-4">
                <div className="relative z-10 w-7 h-7 rounded-full bg-zhiyan-500 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                  {step.step}
                </div>
                <div className="flex-1 pb-1">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium text-gray-700">{step.from}</span>
                    <span className="text-gray-300">→</span>
                    <span className="text-zhiyan-600 font-medium">{step.to}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{step.finding}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 嫌疑设备 */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">🎯 嫌疑设备</h4>
        <div className="space-y-2">
          {result.suspected_equipments?.map((eq, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold ${
                eq.match_score > 0.8 ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-600'
              }`}>
                {(eq.match_score * 100).toFixed(0)}%
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-800">{eq.name}</div>
                <div className="text-xs text-gray-400">{eq.reason}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 根因 */}
      <div className="card border-red-200 bg-red-50/30">
        <h4 className="text-sm font-semibold text-red-800 mb-2">🔬 根因结论</h4>
        <p className="text-sm text-red-700 leading-relaxed">{result.root_cause}</p>
      </div>

      {/* 纠正措施 */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">✅ 纠正与预防措施</h4>
        <ul className="space-y-2">
          {result.fix_actions?.map((action, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>{action}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* 历史相似案例 */}
      <div className="card text-center py-4">
        <div className="text-2xl font-bold text-zhiyan-600">{result.historical_similar}</div>
        <div className="text-xs text-gray-400 mt-1">相似历史案例</div>
      </div>

      <button className="btn-secondary w-full" onClick={onNewGoal}>← 新追溯任务</button>
    </div>
  );
}
