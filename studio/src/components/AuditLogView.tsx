import { useState, useEffect } from 'react';

interface AuditEntry {
  timestamp: string;
  session_id: string;
  event_type: string;
  actor: string;
  detail: string;
}

interface AuditStats {
  total_logs: number;
  by_event_type: Record<string, number>;
}

export default function AuditLogView() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/audit/logs');
      const data = await res.json();
      setLogs(data.logs || []);
      setStats(data.stats || null);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  const eventLabel = (type: string) => {
    const map: Record<string, string> = {
      goal_set: '🎯 目标设定',
      plan_created: '📋 规划生成',
      approved: '✅ 人确认',
      executed: '⚡ 执行完成',
      rejected: '↩️ 人驳回',
      intervened: '🛑 人介入',
    };
    return map[type] || type;
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.event_type === filter);

  return (
    <div className="page-transition space-y-4">
      {/* 头部 */}
      <div className="card-highlight relative overflow-hidden">
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center text-white shadow-sm">
            📜
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">审计日志</h2>
                <p className="text-xs text-gray-400">所有 Agent 操作全程可追溯</p>
              </div>
              <div className="flex items-center gap-3">
                {stats && (
                  <span className="text-xs text-gray-400">共 {stats.total_logs} 条</span>
                )}
                <button className="btn-secondary text-xs py-1.5 px-3" onClick={fetchLogs} disabled={loading}>
                  {loading ? '...' : '刷新'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 分类统计 */}
        {stats && stats.total_logs > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
                filter === 'all'
                  ? 'bg-zhiyan-50 border-zhiyan-300 text-zhiyan-600'
                  : 'border-gray-200 text-gray-500 hover:border-gray-300'
              }`}
              onClick={() => setFilter('all')}
            >
              全部 ({stats.total_logs})
            </button>
            {Object.entries(stats.by_event_type).map(([type, count]) => (
              <button
                key={type}
                className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
                  filter === type
                    ? 'bg-zhiyan-50 border-zhiyan-300 text-zhiyan-600'
                    : 'border-gray-200 text-gray-500 hover:border-gray-300'
                }`}
                onClick={() => setFilter(type)}
              >
                {eventLabel(type)} ({count})
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 日志列表 */}
      {filteredLogs.length === 0 && !loading && (
        <div className="card text-center py-12 text-gray-400">
          <div className="text-3xl mb-3">📭</div>
          <p className="text-sm">暂无审计日志</p>
          <p className="text-xs mt-1">创建 Agent 会话后日志将自动记录</p>
        </div>
      )}

      {loading && logs.length === 0 && (
        <div className="card text-center py-12">
          <span className="w-6 h-6 border-2 border-zhiyan-500 border-t-transparent rounded-full animate-spin inline-block" />
        </div>
      )}

      {filteredLogs.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="divide-y divide-gray-100">
            {filteredLogs.map((log, i) => (
              <div key={i} className="flex items-start gap-4 p-4 hover:bg-gray-50 transition-colors">
                <div className="flex-shrink-0 w-8 text-center text-lg">
                  {log.actor === 'human' ? '👤' : '🤖'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-medium text-gray-800">
                      {eventLabel(log.event_type)}
                    </span>
                    <span className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                      {log.actor === 'human' ? '人' : 'Agent'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 truncate">{log.detail}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-gray-400 font-mono">{log.session_id.slice(0, 12)}...</span>
                    <span className="text-[10px] text-gray-300">|</span>
                    <span className="text-[10px] text-gray-400">
                      {new Date(log.timestamp).toLocaleTimeString('zh-CN')}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
