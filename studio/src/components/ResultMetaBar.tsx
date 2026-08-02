interface ResultMetaBarProps {
  /** F1：结论的数据来源——'real' 真实客户信号源 / 'demo' 演示种子数据 */
  dataSource?: 'real' | 'demo' | string | null;
  /** F4：实际处理本次目标的 Agent 显示名（后端路由结果） */
  agentLabel?: string | null;
  /** F4：侧栏所选 Agent 显示名，与实际路由不一致时给出提示 */
  selectedLabel?: string | null;
}

/**
 * 结果元信息条（应用型可信度底座）
 *
 * 统一置于所有结果视图之上，解决两个存量问题：
 * - F1：数据来源标注此前只在供应链结果视图里有，其余四类视图（PM/良率/追溯/通用）缺失；
 * - F4：引擎按目标文本路由，实际处理 Agent 可能与侧栏所选不同，用户此前无从感知。
 */
export default function ResultMetaBar({ dataSource, agentLabel, selectedLabel }: ResultMetaBarProps) {
  const isReal = dataSource === 'real';
  const mismatch = !!agentLabel && !!selectedLabel && agentLabel !== selectedLabel;

  return (
    <div className="space-y-2">
      <div
        className={`flex flex-wrap items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
          isReal
            ? 'bg-green-50 border-green-200 text-green-700'
            : 'bg-gray-50 border-gray-200 text-gray-500'
        }`}
      >
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isReal ? 'bg-green-500' : 'bg-gray-400'}`} />
        <span className="font-semibold">{isReal ? '真实客户信号' : '演示数据'}</span>
        <span className="opacity-80">
          {isReal
            ? '本结论由已接入的真实客户信号源驱动（不与演示数据混淆）'
            : '本结论由演示种子数据驱动，用于能力演示，非真实生产数据'}
        </span>
        {agentLabel && (
          <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/70 border border-black/10 font-medium">
            🧭 处理 Agent：{agentLabel}
          </span>
        )}
      </div>

      {mismatch && (
        <div className="px-3 py-2 rounded-lg border border-amber-200 bg-amber-50 text-xs leading-5 text-amber-800">
          <span className="font-medium">⚠️ 路由提示：</span>
          你在左侧选择的是「{selectedLabel}」，系统按目标文本判定实际由「{agentLabel}」处理并产出以上结论。
          如需改由「{selectedLabel}」处理，请重新发起并在目标描述中补充该场景的关键词。
        </div>
      )}
    </div>
  );
}
