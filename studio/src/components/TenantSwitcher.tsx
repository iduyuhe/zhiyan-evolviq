import { useState, useRef, useEffect } from 'react';
import { useTenant } from '../tenant/TenantContext';

export default function TenantSwitcher({ onManage }: { onManage: () => void }) {
  const { tenants, activeTenant, setActive } = useTenant();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-zhiyan-200 bg-zhiyan-50 hover:bg-zhiyan-100 transition-colors text-xs font-medium text-zhiyan-700"
        title="切换租户（数据按租户隔离）"
      >
        <span>🏢</span>
        <span className="max-w-[88px] truncate">{activeTenant ? activeTenant.name : '默认租户'}</span>
        <span className="text-[9px] opacity-60">▼</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl border border-gray-200 shadow-lg z-50 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-400">
            切换租户 · 数据按租户硬隔离
          </div>

          <button
            onClick={() => {
              setActive(null);
              setOpen(false);
            }}
            className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors flex items-center justify-between ${
              !activeTenant ? 'text-zhiyan-600 font-medium bg-zhiyan-50/40' : 'text-gray-700'
            }`}
          >
            <span>🌐 默认租户（default）</span>
            {!activeTenant && <span className="text-xs">✓</span>}
          </button>

          {tenants.map((t) => (
            <button
              key={t.tenant_id}
              onClick={() => {
                setActive(t.tenant_id);
                setOpen(false);
              }}
              className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors flex items-center justify-between ${
                activeTenant?.tenant_id === t.tenant_id ? 'text-zhiyan-600 font-medium bg-zhiyan-50/40' : 'text-gray-700'
              }`}
            >
              <span className="truncate">🏢 {t.name}</span>
              {activeTenant?.tenant_id === t.tenant_id && <span className="text-xs">✓</span>}
            </button>
          ))}

          {tenants.length === 0 && (
            <div className="px-4 py-3 text-xs text-gray-400">还没有注册的租户</div>
          )}

          <div className="border-t border-gray-100">
            <button
              onClick={() => {
                setOpen(false);
                onManage();
              }}
              className="w-full text-left px-4 py-2.5 text-sm text-zhiyan-500 hover:bg-zhiyan-50 transition-colors"
            >
              ⚙️ 租户管理
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
