import { useState, useEffect } from 'react';

interface SessionSummary {
  session_id: string;
  goal: string;
  status: string;
  completeness: number | null;
}

export default function SessionHistory({ onSelect }: { onSelect: (id: string) => void }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 5000);
    return () => clearInterval(interval);
  }, []);

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      completed: 'badge-green',
      rejected: 'badge-red',
      executing: 'badge-yellow',
      awaiting_approval: 'badge-blue',
      planning: '',
    };
    return map[status] || 'badge-blue';
  };

  const statusLabel = (status: string) => {
    const map: Record<string, string> = {
      completed: '已完成',
      rejected: '已驳回',
      executing: '执行中',
      awaiting_approval: '待确认',
      planning: '规划中',
    };
    return map[status] || status;
  };

  return (
    <div className="page-transition space-y-4">
      {/* 头部 */}
      <div className="card-highlight relative overflow-hidden">
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center text-white shadow-sm">
            📋
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">会话历史</h2>
                <p className="text-xs text-gray-400">所有 Agent 执行记录</p>
              </div>
              <button className="btn-secondary text-xs py-1.5 px-3" onClick={fetchSessions} disabled={loading}>
                {loading ? '刷新中...' : '刷新'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 列表 */}
      {sessions.length === 0 && !loading && (
        <div className="card text-center py-12 text-gray-400">
          <div className="text-3xl mb-3">📭</div>
          <p className="text-sm">暂无执行记录</p>
          <p className="text-xs mt-1">前往 Agent Studio 创建第一个任务</p>
        </div>
      )}

      {loading && sessions.length === 0 && (
        <div className="card text-center py-12">
          <span className="w-6 h-6 border-2 border-zhiyan-500 border-t-transparent rounded-full animate-spin inline-block" />
          <p className="text-sm text-gray-400 mt-3">加载中...</p>
        </div>
      )}

      {sessions.length > 0 && (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className="card flex items-center gap-4 p-4 hover:border-zhiyan-200 cursor-pointer transition-all group"
              onClick={() => onSelect(s.session_id)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`badge ${statusBadge(s.status)}`}>{statusLabel(s.status)}</span>
                  {s.completeness !== null && (
                    <span className="text-xs text-gray-400">齐套率 {s.completeness}%</span>
                  )}
                </div>
                <p className="text-sm text-gray-700 truncate">{s.goal}</p>
                <p className="text-xs text-gray-400 font-mono mt-1">{s.session_id.slice(0, 16)}...</p>
              </div>
              <div className="flex-shrink-0 text-gray-300 group-hover:text-zhiyan-500 transition-colors">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
