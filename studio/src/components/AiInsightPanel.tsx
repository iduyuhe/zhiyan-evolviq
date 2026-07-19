interface AiInsightPanelProps {
  insight?: string | null;
  source?: 'llm' | 'none';
}

/** 内联加粗渲染：把 **xxx** 转成 <strong> */
function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) {
      return <strong key={i} className="font-semibold text-zhiyan-700">{p.slice(2, -2)}</strong>;
    }
    return <span key={i}>{p}</span>;
  });
}

function renderInsight(text: string) {
  const lines = text.split('\n').filter(l => l.trim());
  return lines.map((line, i) => {
    const t = line.trim();
    // 列表项（- 或 * 开头）
    if (t.startsWith('- ') || t.startsWith('* ')) {
      return (
        <p key={i} className="text-sm text-gray-700 ml-1 my-1 flex items-start gap-2 leading-relaxed">
          <span className="text-zhiyan-400 mt-1 flex-shrink-0">▸</span>
          <span>{renderInline(t.replace(/^[-*]\s/, ''))}</span>
        </p>
      );
    }
    // 小标题（**xxx** 独占一行）
    if (/^\*\*[^*]+\*\*[:：]?$/.test(t)) {
      return (
        <h5 key={i} className="text-sm font-semibold text-zhiyan-700 mt-3 mb-1 first:mt-0">
          {t.replace(/\*\*/g, '').replace(/[:：]$/, '')}
        </h5>
      );
    }
    if (t.startsWith('### ')) {
      return <h5 key={i} className="text-sm font-semibold text-zhiyan-700 mt-3 mb-1">{t.replace('### ', '')}</h5>;
    }
    return <p key={i} className="text-sm text-gray-700 my-1 leading-relaxed">{renderInline(t)}</p>;
  });
}

export default function AiInsightPanel({ insight, source }: AiInsightPanelProps) {
  // 无 LLM 辅助（未配置 Key 或调用失败）时不渲染，页面仅展示纯确定性结果
  if (!insight || source !== 'llm') return null;

  return (
    <div className="page-transition card relative overflow-hidden border-zhiyan-100">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-zhiyan-400 via-zhiyan-500 to-zhiyan-600" />
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-zhiyan-500 to-zhiyan-700 flex items-center justify-center text-white text-sm shadow-md flex-shrink-0">
          🤖
        </div>
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-900">AI 决策辅助</h3>
          <span className="px-2 py-0.5 text-[10px] rounded-full bg-zhiyan-50 text-zhiyan-600 font-medium">
            L2 推理 · 基于确定性结果
          </span>
        </div>
      </div>
      <div className="bg-gradient-to-b from-zhiyan-50/40 to-white rounded-lg border border-zhiyan-100/60 px-4 py-3">
        {renderInsight(insight)}
      </div>
      <p className="text-[10px] text-gray-400 mt-2 flex items-center gap-1">
        <span>⚠️</span>
        <span>AI 辅助意见仅供参考，最终以确定性执行结果与人工审批为准</span>
      </p>
    </div>
  );
}
