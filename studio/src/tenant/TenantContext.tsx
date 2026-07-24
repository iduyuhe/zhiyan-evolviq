import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import {
  setTenantKey,
  getTenantKey,
  registerTenant as apiRegister,
  rotateTenantKey as apiRotate,
  deleteTenant as apiDelete,
  getTenantMe,
  type TenantInfo,
} from '../api/client';

/** 本浏览器中已注册并保存的租户（含明文 key，仅存本地）。 */
export interface StoredTenant {
  tenant_id: string;
  name: string;
  api_key: string;
}

interface TenantContextValue {
  tenants: StoredTenant[];
  activeTenant: StoredTenant | null;
  loading: boolean;
  registerTenant: (name: string) => Promise<StoredTenant>;
  setActive: (tenantId: string | null) => void;
  rotateKey: (tenantId: string) => Promise<void>;
  deleteTenant: (tenantId: string) => Promise<void>;
  me: TenantInfo | null;
  refreshMe: () => Promise<void>;
}

const LS_TENANTS = 'zhiyan_tenants';
const LS_ACTIVE = 'zhiyan_active_tenant';

function loadTenants(): StoredTenant[] {
  try {
    const raw = localStorage.getItem(LS_TENANTS);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<StoredTenant[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [me, setMe] = useState<TenantInfo | null>(null);
  const [loading, setLoading] = useState(false);

  // 初次挂载：从 localStorage 恢复租户列表与激活态，并把 key 注入全局请求层
  useEffect(() => {
    const ts = loadTenants();
    setTenants(ts);
    const aid = localStorage.getItem(LS_ACTIVE);
    const active = ts.find((t) => t.tenant_id === aid) || null;
    setActiveId(active ? active.tenant_id : null);
    setTenantKey(active ? active.api_key : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setActive = useCallback(
    (tenantId: string | null) => {
      setActiveId(tenantId);
      if (tenantId === null) {
        localStorage.removeItem(LS_ACTIVE);
        setTenantKey(null);
        setMe(null);
        return;
      }
      const t = tenants.find((x) => x.tenant_id === tenantId);
      if (t) {
        localStorage.setItem(LS_ACTIVE, tenantId);
        setTenantKey(t.api_key);
      }
    },
    [tenants],
  );

  const registerTenant = useCallback(
    async (name: string): Promise<StoredTenant> => {
      setLoading(true);
      try {
        const { tenant_id, api_key } = await apiRegister(name);
        const t: StoredTenant = { tenant_id, name, api_key };
        const next = [...tenants, t];
        setTenants(next);
        localStorage.setItem(LS_TENANTS, JSON.stringify(next));
        setActiveId(tenant_id);
        localStorage.setItem(LS_ACTIVE, tenant_id);
        setTenantKey(api_key);
        return t;
      } finally {
        setLoading(false);
      }
    },
    [tenants],
  );

  const rotateKey = useCallback(
    async (tenantId: string) => {
      const t = tenants.find((x) => x.tenant_id === tenantId);
      if (!t) throw new Error('租户不存在');
      const wasActive = activeId === tenantId;
      // 用该租户当前 key 调用轮换接口
      setTenantKey(t.api_key);
      const { api_key } = await apiRotate();
      const next = tenants.map((x) => (x.tenant_id === tenantId ? { ...x, api_key } : x));
      setTenants(next);
      localStorage.setItem(LS_TENANTS, JSON.stringify(next));
      // 恢复正确的激活 key
      if (wasActive) {
        setTenantKey(api_key);
      } else {
        const a = next.find((x) => x.tenant_id === activeId);
        setTenantKey(a ? a.api_key : null);
      }
    },
    [tenants, activeId],
  );

  const deleteTenant = useCallback(
    async (tenantId: string) => {
      const t = tenants.find((x) => x.tenant_id === tenantId);
      if (!t) return;
      setTenantKey(t.api_key);
      await apiDelete();
      const next = tenants.filter((x) => x.tenant_id !== tenantId);
      setTenants(next);
      localStorage.setItem(LS_TENANTS, JSON.stringify(next));
      if (activeId === tenantId) {
        setActiveId(null);
        localStorage.removeItem(LS_ACTIVE);
        setTenantKey(null);
        setMe(null);
      } else {
        const a = next.find((x) => x.tenant_id === activeId);
        setTenantKey(a ? a.api_key : null);
      }
    },
    [tenants, activeId],
  );

  const refreshMe = useCallback(async () => {
    if (!activeId) {
      setMe(null);
      return;
    }
    try {
      setMe(await getTenantMe());
    } catch {
      setMe(null);
    }
  }, [activeId]);

  useEffect(() => {
    refreshMe();
  }, [refreshMe]);

  const activeTenant = tenants.find((t) => t.tenant_id === activeId) || null;

  return (
    <TenantContext.Provider
      value={{ tenants, activeTenant, loading, registerTenant, setActive, rotateKey, deleteTenant, me, refreshMe }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext);
  if (!ctx) throw new Error('useTenant 必须在 TenantProvider 内使用');
  return ctx;
}

// 供其它模块在特殊场景下直接取当前 key
export function currentTenantKey(): string | null {
  return getTenantKey();
}
