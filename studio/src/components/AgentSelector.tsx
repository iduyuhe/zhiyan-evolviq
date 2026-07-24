import { useState, useEffect, useRef } from 'react';

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  icon: string;
  scenarios: string[];
  version: string;
}

export const SCENARIO_GROUPS: Record<string, { label: string; icon: string; agents: string[] }> = {
  supply: {
    label: '供应链指挥官',
    icon: '📦',
    agents: ['supply_chain'],
  },
  rd: {
    label: '研发加速器',
    icon: '🔬',
    agents: ['dfm_check', 'bom_selector', 'eco_change'],
  },
  production: {
    label: '产线管家',
    icon: '⚙️',
    agents: ['pm_maintenance', 'oee_optimizer', 'smt_changeover', 'aoi_judge'],
  },
  quality: {
    label: '质量侦探',
    icon: '🛡️',
    agents: ['yield_analysis', 'quality_trace', 'ipc_standard'],
  },
};

const DEFAULT_EXAMPLES: Record<string, string[]> = {
  supply_chain: [
    '每2小时检查28nm产线物料齐套，硅片/光刻胶/特种气体缺料风险>30%时自动检索替代方案',
    '检查SMIC-28nm-Logic BOM的物料供应情况，重点关注国产替代方案',
    '监控晶圆厂关键物料库存，库存低于安全水位时自动发起采购建议',
  ],
  pm_maintenance: [
    '检查SMIC光刻机和刻蚀机的设备健康状态，列出需要关注的高风险部件',
    '查看薄膜沉积设备的预防维护计划和备件更换建议',
    '分析刻蚀机最近一周的异常告警，给出维修优先级排序',
  ],
  yield_analysis: [
    '分析28nm逻辑产品的良率趋势和缺陷分布，找出主要原因',
    '对比光刻机#1和#2的良率差异，定位低良率设备',
    '查看最近5批晶圆的良率变化趋势，给出改进建议',
  ],
  quality_trace: [
    '追溯28nm产品边缘颗粒污染超标的质量问题，从客诉追溯根因',
    '分析刻蚀深度偏差的根因，追溯到具体设备和工艺参数',
    '对近期质量异常批次进行追溯分析，找出共性根因',
  ],
  dfm_check: [
    '对PCB-A-v3.2进行全板DFM检查，焊盘间距/线宽/阻焊覆盖全面审查',
    '检查电源模块的DFM可制造性，重点关注载流能力',
    '审查BGA区域的过孔密度和焊盘设计规则合规性',
  ],
  bom_selector: [
    '查找STM32F407VGT6的pin-to-pin兼容替代料，优先国产方案',
    '分析TPS63020DSJR的替代方案，比较价格和供应链稳定性',
    '推荐MCU选型，要求ARM Cortex-M4/1MB Flash/LQFP-100封装',
  ],
  oee_optimizer: [
    '分析全部SMT产线的OEE，找出瓶颈产线和六大损失分布',
    '查看SMT-L02产线OEE低于目标的原因，给出改善建议',
    '对比三条产线的OEE表现，制定改善优先级',
  ],
  eco_change: [
    '分析ECO变更：U12 MCU由STM32F407切换为GD32F407的影响范围',
    '评估阻焊层厚度从15um改为20um的工程变更影响',
    '检查物料替换变更对在制库存和工单的影响',
  ],
  smt_changeover: [
    '生成SMT-L01从PCB-A切换到PCB-C的换线计划，SMED优化',
    '分析SMT-L02换线时间过长的原因，给出SMED改善建议',
    '生成换线检查清单，包括料站/钢网/程序确认项',
  ],
  aoi_judge: [
    '分析SMT-L01产线AOI误报率，给出阈值优化建议',
    '统计AOI各类缺陷的误报分布，找出最大误报来源',
    '优化AOI检测参数，目标将误报率从75%降至25%',
  ],
  ipc_standard: [
    '查询BGA焊球空洞在IPC-A-610标准下的可接受范围',
    '判定Chip组件偏位在不同Class下的可接受标准',
    '查询焊锡桥连在IPC标准下的判定规则',
  ],
};

export default function AgentSelector({ onSelect }: { onSelect: (agent: AgentInfo) => void }) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [current, setCurrent] = useState<string>('supply_chain');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/api/agents')
      .then(r => r.json())
      .then(d => {
        setAgents(d.agents || []);
        if (d.agents?.length > 0) onSelect(d.agents[0]);
      })
      .catch(() => {});
  }, []);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const currentAgent = agents.find(a => a.id === current) || agents[0];
  const currentGroup = Object.entries(SCENARIO_GROUPS).find(([_, g]) => g.agents.includes(current))?.[0] || 'supply';

  const handleSelect = (agent: AgentInfo) => {
    setCurrent(agent.id);
    onSelect(agent);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      {/* 当前选中的Agent按钮 */}
      <button
        className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-zhiyan-50 to-blue-50 border border-zhiyan-200 rounded-lg hover:border-zhiyan-300 transition-colors shadow-sm"
        onClick={() => setOpen(!open)}
      >
        <span className="text-base">{currentAgent?.icon || '🤖'}</span>
        <div className="flex flex-col items-start">
          <span className="text-xs font-semibold text-zhiyan-700 leading-tight">{currentAgent?.name || '选择Agent'}</span>
          <span className="text-[10px] text-zhiyan-500 leading-tight">v{currentAgent?.version?.split('.')[0] || '0'} · {SCENARIO_GROUPS[currentGroup]?.label?.slice(0, 4) || ''}</span>
        </div>
        <svg className={`w-3 h-3 text-zhiyan-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* 下拉面板 */}
      {open && (
        <div className="absolute top-full mt-2 right-0 w-[480px] bg-white rounded-xl shadow-2xl border border-gray-200 p-3 z-50 animate-fade-in">
          <div className="flex items-center justify-between mb-3 px-1">
            <h3 className="text-sm font-semibold text-gray-900">选择 Agent</h3>
            <span className="text-[10px] text-gray-400">11 个 Agent · 4 大场景</span>
          </div>

          <div className="space-y-3 max-h-[480px] overflow-y-auto">
            {Object.entries(SCENARIO_GROUPS).map(([groupKey, group]) => (
              <div key={groupKey} className="bg-gray-50 rounded-lg p-2.5">
                <div className="flex items-center gap-1.5 mb-2 px-1">
                  <span className="text-sm">{group.icon}</span>
                  <span className="text-xs font-semibold text-gray-700">{group.label}</span>
                  <span className="text-[10px] text-gray-400">({group.agents.length})</span>
                </div>
                <div className="grid grid-cols-1 gap-1.5">
                  {group.agents.map(agentId => {
                    const agent = agents.find(a => a.id === agentId);
                    if (!agent) return null;
                    const isCurrent = current === agentId;
                    return (
                      <button
                        key={agentId}
                        onClick={() => handleSelect(agent)}
                        className={`flex items-center gap-2.5 p-2 rounded-md text-left transition-colors ${
                          isCurrent
                            ? 'bg-zhiyan-100 border border-zhiyan-300'
                            : 'hover:bg-white border border-transparent'
                        }`}
                      >
                        <span className="text-lg flex-shrink-0">{agent.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className={`text-sm font-medium ${isCurrent ? 'text-zhiyan-700' : 'text-gray-900'}`}>
                              {agent.name}
                            </p>
                            <span className="text-[10px] text-gray-400">v{agent.version?.split('.')[0]}</span>
                          </div>
                          <p className="text-[11px] text-gray-500 truncate">{agent.description}</p>
                        </div>
                        {isCurrent && (
                          <svg className="w-4 h-4 text-zhiyan-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 pt-2.5 border-t border-gray-100 px-1">
            <p className="text-[10px] text-gray-400 text-center">
              切换 Agent 即可加载对应的目标示例场景
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export { DEFAULT_EXAMPLES };
