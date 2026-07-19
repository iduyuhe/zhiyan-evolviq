import { useState } from 'react';

interface GoalInputProps {
  onSubmit: (goal: string) => void;
  onQuickCheck: (goal: string) => void;
  loading: boolean;
  agentExamples: string[];
}

export default function GoalInput({ onSubmit, onQuickCheck, loading, agentExamples }: GoalInputProps) {
  const [goal, setGoal] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (goal.trim()) onSubmit(goal.trim());
  };

  return (
    <div className="page-transition">
      <div className="card-highlight relative overflow-hidden">
        {/* 装饰品牌背景 */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-gradient-to-bl from-zhiyan-500/5 to-transparent rounded-full pointer-events-none" />
        <div className="absolute -bottom-10 -left-10 w-24 h-24 bg-gradient-to-tr from-zhiyan-400/5 to-transparent rounded-full pointer-events-none" />

        <div className="relative">
          {/* 头部 */}
          <div className="flex items-center gap-3 mb-6">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-zhiyan-500 to-zhiyan-700 flex items-center justify-center text-white text-lg font-bold shadow-sm">
              智
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">设定 Agent 目标</h1>
              <p className="text-sm text-gray-500">用自然语言描述你的业务目标，Agent 将自主规划并执行</p>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="relative">
              <textarea
                className="input min-h-[120px] resize-y text-base leading-relaxed"
                placeholder="描述你的业务目标，例如：检查NPI物料齐套，发现缺料风险时自动检索替代方案..."
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                disabled={loading}
              />
              {!goal && (
                <div className="absolute bottom-3 left-4 flex items-center gap-1.5 text-xs text-gray-300 pointer-events-none select-none">
                  <span className="inline-block w-2 h-2 rounded-full bg-zhiyan-300 animate-pulse-dot" />
                  <span className="inline-block w-2 h-2 rounded-full bg-zhiyan-300 animate-pulse-dot" />
                  <span className="inline-block w-2 h-2 rounded-full bg-zhiyan-300 animate-pulse-dot" />
                </div>
              )}
            </div>

            <div className="mt-4 space-y-3">
              <div className="space-y-1.5">
                <p className="text-xs text-gray-500 font-medium">💡 点击示例加载：</p>
                <div className="space-y-1.5">
                  {agentExamples.slice(0, 3).map((ex, i) => (
                    <button
                      key={i}
                      type="button"
                      className="w-full text-left px-3 py-2 text-xs rounded-lg border border-gray-200 text-gray-600
                                 hover:border-zhiyan-300 hover:text-zhiyan-700 hover:bg-zhiyan-50
                                 transition-all duration-200 flex items-start gap-2"
                      onClick={() => setGoal(ex)}
                    >
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-zhiyan-100 text-zhiyan-600 flex items-center justify-center text-[10px] font-semibold mt-0.5">
                        {i + 1}
                      </span>
                      <span className="flex-1 line-clamp-2">{ex}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  className="btn-secondary text-xs px-3"
                  onClick={() => onQuickCheck(goal.trim())}
                  disabled={loading || !goal.trim()}
                  title="跳过规划预览，直接执行"
                >
                  ⚡ 一键检查
                </button>
                <button type="submit" className="btn-primary px-6" disabled={loading || !goal.trim()}>
                  {loading ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      分析中...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      启动 Agent
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
