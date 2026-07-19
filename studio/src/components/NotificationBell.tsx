import { useState, useEffect, useRef } from 'react';

interface EventItem {
  id: string;
  type: string;
  title: string;
  message: string;
  level: string;
  timestamp: string;
  read: boolean;
}

export default function NotificationBell() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const fetchEvents = async () => {
    try {
      const res = await fetch('/api/events?limit=10');
      const data = await res.json();
      setEvents(data.events || []);
      setUnread(data.unread || 0);
    } catch {
      // silent
    }
  };

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 5000);
    return () => clearInterval(interval);
  }, []);

  // 点击外部关闭
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const markAllRead = async () => {
    await fetch('/api/events/read-all', { method: 'POST' });
    setUnread(0);
    setEvents(prev => prev.map(e => ({ ...e, read: true })));
  };

  const levelIcon = (level: string) => {
    switch (level) {
      case 'critical': return '🔴';
      case 'warning': return '🟡';
      case 'success': return '✅';
      default: return 'ℹ️';
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        className="relative p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl border border-gray-200 shadow-lg z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-800">通知</span>
            {unread > 0 && (
              <button className="text-xs text-zhiyan-500 hover:text-zhiyan-600" onClick={markAllRead}>
                全部已读
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {events.length === 0 && (
              <div className="text-center py-8 text-gray-400 text-sm">暂无通知</div>
            )}
            {events.map((evt) => (
              <div key={evt.id} className={`px-4 py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors ${!evt.read ? 'bg-zhiyan-50/30' : ''}`}>
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5">{levelIcon(evt.level)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800 truncate">{evt.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">{evt.message}</div>
                    <div className="text-[10px] text-gray-400 mt-1 font-mono">
                      {new Date(evt.timestamp).toLocaleTimeString('zh-CN')}
                    </div>
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
