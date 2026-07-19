interface PlanPreviewProps {
  plan: string;
  onApprove: (approved: boolean, feedback?: string) => void;
  loading: boolean;
}

function renderPlan(text: string) {
  const lines = text.split('\n');
  return lines.map((line, i) => {
    if (line.startsWith('## ')) {
      return <h3 key={i} className="text-base font-semibold text-gray-900 mt-5 mb-2">{line.replace('## ', '')}</h3>;
    }
    if (line.startsWith('### ')) {
      return <h4 key={i} className="text-sm font-medium text-gray-700 mt-4 mb-1.5">{line.replace('### ', '')}</h4>;
    }
    if (line.startsWith('| ') && (line.includes('|---') || line.includes('|:---'))) {
      return null;
    }
    if (line.startsWith('| ')) {
      const cells = line.split('|').filter(c => c.trim());
      const isHeader = i > 0 && lines[i - 1]?.startsWith('| ');
      return (
        <div key={i} className={`flex gap-2 py-1 text-sm ${isHeader ? '' : ''}`}>
          {cells.map((c, j) => (
            <span key={j} className={`flex-1 ${isHeader ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
              {c.trim()}
            </span>
          ))}
        </div>
      );
    }
    if (line.startsWith('- ')) {
      return <p key={i} className="text-sm text-gray-600 ml-4 my-0.5 flex items-start gap-2">
        <span className="text-gray-300 mt-1">•</span>
        <span>{line.replace('- ', '')}</span>
      </p>;
    }
    if (line.startsWith('> ')) {
      return (
        <blockquote key={i} className="border-l-3 border-zhiyan-300 bg-gradient-to-r from-zhiyan-50 to-transparent rounded-r-lg px-4 py-3 my-3 text-sm text-gray-700 italic">
          {line.replace('> ', '')}
        </blockquote>
      );
    }
    if (line.match(/^\d[.)]\s/)) {
      const num = line.match(/^(\d)[.)]\s(.*)/);
      if (num) {
        return (
          <div key={i} className="flex items-start gap-3 ml-1 my-1.5">
            <span className="w-6 h-6 rounded-full bg-zhiyan-100 text-zhiyan-600 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
              {num[1]}
            </span>
            <span className="text-sm text-gray-700 leading-6">{num[2]}</span>
          </div>
        );
      }
      return <p key={i} className="text-sm text-gray-600 pl-4">{line}</p>;
    }
    if (line.startsWith('```')) {
      return null;
    }
    return <p key={i} className="text-sm text-gray-600 leading-relaxed">{line}</p>;
  });
}

export default function PlanPreview({ plan, onApprove, loading }: PlanPreviewProps) {
  return (
    <div className="page-transition">
      <div className="card-highlight relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-zhiyan-400 via-zhiyan-500 to-zhiyan-600" />

        {/* 头部指示器 */}
        <div className="flex items-center gap-3 mb-4">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-zhiyan-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-zhiyan-500" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-zhiyan-700">Agent 执行规划</h3>
            <p className="text-xs text-gray-400">请仔细审阅以下计划，确认后Agent将开始执行</p>
          </div>
        </div>

        {/* 规划内容 */}
        <div className="bg-gradient-to-b from-gray-50 to-white rounded-lg border border-gray-100 p-5 max-h-[420px] overflow-y-auto text-sm leading-relaxed">
          {renderPlan(plan)}
        </div>

        {/* 操作按钮 */}
        <div className="mt-5 flex gap-3">
          <button
            className="btn-primary flex-1 py-3"
            onClick={() => onApprove(true)}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                执行中...
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                确认执行
              </>
            )}
          </button>
          <button
            className="btn-secondary flex-1 py-3"
            onClick={() => onApprove(false, '需要调整规划')}
            disabled={loading}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            驳回修改
          </button>
        </div>
      </div>
    </div>
  );
}
