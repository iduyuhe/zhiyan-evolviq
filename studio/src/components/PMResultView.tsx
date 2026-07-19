/** 设备维护Agent结果展示——设备健康卡片 */

interface EquipmentResult {
  summary: string;
  equipments: {
    equipment_id: string;
    name: string;
    type: string;
    health_score: number;
    status: string;
    uptime_hours: number;
    next_pm_due: string;
    risky_components: { name: string; life_remaining_pct: number; risk: string }[];
    recent_alerts: string[];
  }[];
  alerts: string[];
}

export default function PMResultView({ result, onNewGoal }: { result: EquipmentResult; onNewGoal: () => void }) {
  const healthColor = (score: number) => {
    if (score >= 85) return 'text-green-600';
    if (score >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  const healthBg = (score: number) => {
    if (score >= 85) return 'bg-green-500';
    if (score >= 70) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="page-transition space-y-4">
      {/* 摘要 */}
      <div className="card-highlight bg-gradient-to-br from-blue-50 via-white to-indigo-50/30">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">🔧</span>
          <div>
            <h3 className="font-semibold text-gray-900">设备诊断完成</h3>
            <p className="text-sm text-gray-500">{result.summary}</p>
          </div>
        </div>
      </div>

      {/* 设备健康卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {result.equipments?.map((eq) => (
          <div key={eq.equipment_id} className={`card relative overflow-hidden ${
            eq.status === 'critical' ? 'border-red-200' : eq.status === 'warning' ? 'border-yellow-200' : ''
          }`}>
            {/* 顶部状态条 */}
            <div className={`h-1 absolute top-0 left-0 right-0 ${
              eq.status === 'critical' ? 'bg-red-500' : eq.status === 'warning' ? 'bg-yellow-500' : 'bg-green-500'
            }`} />

            <div className="pt-2">
              {/* 头部 */}
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-medium text-gray-800 text-sm">{eq.name}</h4>
                  <span className="text-xs text-gray-400">{eq.type} · 已运行 {eq.uptime_hours}h</span>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${healthColor(eq.health_score)}`}>
                    {Math.round(eq.health_score)}
                  </div>
                  <div className="text-[10px] text-gray-400">健康分</div>
                </div>
              </div>

              {/* 健康条 */}
              <div className="gauge-bar mb-3">
                <div className={`gauge-fill ${healthBg(eq.health_score)}`}
                     style={{ width: `${eq.health_score}%` }} />
              </div>

              {/* 部件状态 */}
              {eq.risky_components?.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-medium text-gray-600 mb-1.5">关键部件状态</div>
                  <div className="space-y-1">
                    {eq.risky_components.map((part, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          part.risk === 'high' ? 'bg-red-500' : 'bg-yellow-500'
                        }`} />
                        <span className="text-gray-600">{part.name}</span>
                        <span className="text-gray-400 ml-auto">{part.life_remaining_pct}%寿命</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 下次维护 */}
              <div className="text-xs text-gray-400">
                下次预防维护：{eq.next_pm_due}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 预警 */}
      {result.alerts?.length > 0 && (
        <div className="card border-red-200 bg-red-50/30">
          <h4 className="text-sm font-semibold text-red-800 mb-2">🚨 维护预警</h4>
          <ul className="space-y-1">
            {result.alerts.map((a, i) => (
              <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                <span>•</span><span>{a}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="btn-secondary w-full" onClick={onNewGoal}>← 新诊断任务</button>
    </div>
  );
}
