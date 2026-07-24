import { useState } from 'react';
import type { AgentInfo } from './AgentSelector';
import { SCENARIO_GROUPS } from './AgentSelector';

interface AgentSidebarProps {
  agents: AgentInfo[];
  current: string;
  onSelect: (agent: AgentInfo) => void;
  /** 选中项后由父层关闭抽屉（窄屏用） */
  onItemClick?: () => void;
}

export default function AgentSidebar({ agents, current, onSelect, onItemClick }: AgentSidebarProps) {
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const toggleGroup = (key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="p-3">
      <div className="flex items-center justify-between px-1 mb-3">
        <h3 className="text-sm font-semibold text-gray-900">选择 Agent</h3>
        <span className="text-[10px] text-gray-400">{agents.length} · 4 场景</span>
      </div>

      <div className="space-y-3">
        {Object.entries(SCENARIO_GROUPS).map(([groupKey, group]) => (
          <div key={groupKey}>
            <button
              type="button"
              onClick={() => toggleGroup(groupKey)}
              className="w-full flex items-center gap-1.5 px-1 mb-1.5 text-left cursor-pointer hover:bg-gray-50 rounded transition-colors"
            >
              <span className="text-[10px] text-gray-400 w-3 flex-shrink-0">{collapsedGroups.has(groupKey) ? '▸' : '▾'}</span>
              <span className="text-sm">{group.icon}</span>
              <span className="text-xs font-semibold text-gray-500">{group.label}</span>
              <span className="text-[10px] text-gray-400">({group.agents.length})</span>
            </button>
            {!collapsedGroups.has(groupKey) && (
            <div className="space-y-1">
              {group.agents.map((agentId) => {
                const agent = agents.find((a) => a.id === agentId);
                if (!agent) return null;
                const isCurrent = current === agentId;
                return (
                  <button
                    key={agentId}
                    onClick={() => {
                      onSelect(agent);
                      onItemClick?.();
                    }}
                    className={`w-full flex items-center gap-2.5 p-2 rounded-lg text-left border transition-colors ${
                      isCurrent
                        ? 'bg-zhiyan-50 border-zhiyan-300'
                        : 'border-transparent hover:bg-gray-50'
                    }`}
                  >
                    <span className="text-lg flex-shrink-0 leading-none">{agent.icon}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1">
                        <p className={`text-sm font-medium truncate ${isCurrent ? 'text-zhiyan-700' : 'text-gray-900'}`}>
                          {agent.name}
                        </p>
                        <span className="text-[10px] text-gray-400 flex-shrink-0">v{agent.version?.split('.')[0]}</span>
                      </div>
                      <p className="text-[11px] text-gray-500 truncate">{agent.description}</p>
                    </div>
                    {isCurrent && (
                      <span className="w-2 h-2 rounded-full bg-zhiyan-500 flex-shrink-0" />
                    )}
                  </button>
                );
              })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
