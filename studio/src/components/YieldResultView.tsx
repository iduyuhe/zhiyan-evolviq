/** 良率分析Agent结果展示 */

interface YieldResult {
  summary: string;
  product: string;
  current_yield: number;
  target_yield: number;
  gap: number;
  defects: { type: string; ratio: number; trend: string }[];
  by_equipment: { equipment: string; yield: number; status: string }[];
  findings: string[];
  recommendations: string[];
}

export default function YieldResultView({ result, onNewGoal }: { result: YieldResult; onNewGoal: () => void }) {
  return (
    <div className="page-transition space-y-4">
      {/* 摘要 */}
      <div className="card-highlight bg-gradient-to-br from-emerald-50 via-white to-teal-50/30">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">📈</span>
          <div>
            <h3 className="font-semibold text-gray-900">良率分析完成</h3>
            <p className="text-sm text-gray-500">{result.summary}</p>
          </div>
        </div>
      </div>

      {/* 良率仪表盘 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-gray-800">当前良率</h4>
          <span className="text-xs text-gray-400">{result.product}</span>
        </div>
        <div className="flex items-end gap-4">
          <div className="text-4xl font-bold text-gray-900">{result.current_yield}%</div>
          <div className="pb-1">
            <span className="text-sm text-gray-500">目标 {result.target_yield}%</span>
            <div className="flex items-center gap-1 mt-1">
              <span className={`text-sm font-medium ${result.gap > 0 ? 'text-red-500' : 'text-green-500'}`}>
                {result.gap > 0 ? `差 ${result.gap}%` : '达标'}
              </span>
            </div>
          </div>
        </div>
        {/* 进度条 */}
        <div className="mt-3 gauge-bar">
          <div
            className={`gauge-fill ${result.current_yield >= result.target_yield ? 'bg-green-500' : 'bg-zhiyan-500'}`}
            style={{ width: `${Math.min(100, (result.current_yield / result.target_yield) * 100)}%` }}
          />
        </div>
      </div>

      {/* 缺陷分布 */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">缺陷分布 Top 3</h4>
        <div className="space-y-3">
          {result.defects?.map((d, i) => (
            <div key={i}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-700">{d.type}</span>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-800">{d.ratio}%</span>
                  <span className={`text-xs ${
                    d.trend === '上升中' ? 'text-red-500' :
                    d.trend === '下降中' ? 'text-green-500' : 'text-gray-400'
                  }`}>
                    {d.trend === '上升中' ? '↑' : d.trend === '下降中' ? '↓' : '→'}
                  </span>
                </div>
              </div>
              <div className="gauge-bar">
                <div className={`gauge-fill ${
                  d.trend === '上升中' ? 'bg-red-500' :
                  d.trend === '下降中' ? 'bg-green-500' : 'bg-yellow-500'
                }`} style={{ width: `${d.ratio}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 设备对比 */}
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">设备良率对比</h4>
        <div className="space-y-2">
          {result.by_equipment?.map((eq, i) => (
            <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50">
              <span className={`w-2 h-2 rounded-full ${eq.status === 'attention' ? 'bg-yellow-500' : 'bg-green-500'}`} />
              <span className="text-sm text-gray-700 flex-1">{eq.equipment}</span>
              <span className={`text-sm font-medium ${eq.yield < 90 ? 'text-yellow-600' : 'text-green-600'}`}>
                {eq.yield}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 发现与建议 */}
      {result.findings?.length > 0 && (
        <div className="card">
          <h4 className="text-sm font-semibold text-gray-800 mb-2">🔍 分析发现</h4>
          <ul className="space-y-1">
            {result.findings.map((f, i) => (
              <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                <span>•</span><span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.recommendations?.length > 0 && (
        <div className="card border-zhiyan-200 bg-zhiyan-50/30">
          <h4 className="text-sm font-semibold text-zhiyan-800 mb-2">💡 改进建议</h4>
          <ul className="space-y-1">
            {result.recommendations.map((r, i) => (
              <li key={i} className="text-sm text-zhiyan-700 flex items-start gap-2">
                <span>→</span><span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="btn-secondary w-full" onClick={onNewGoal}>← 新分析任务</button>
    </div>
  );
}
