/**
 * 用户权限管理页（权限第③层的操作界面）
 *
 * 回答杜总的问题：「企业里有不同的用户，管理员在哪个界面授权？怎么授权？」
 * 答案 = 本页：选人 → 选岗位（权限模板库）→ 权限自动成型，无需逐个勾选智能体。
 *
 * 四层权限模型里本页负责第②③层：
 *   ② RBAC 角色      viewer / operator / tenant_admin / superadmin（能做多重的事）
 *   ③ 业务岗位       device_engineer / finance_controller / ...（能看哪些智能体）
 *
 * 后端契约：
 *   GET  /authn/users?tenant_id=      列用户（非 superadmin 强制只见本租户）
 *   POST /authn/users                 建用户（可直接带 business_role）
 *   GET  /authn/business-roles?industry=  岗位模板（含各岗位可见智能体清单）
 *   POST /authn/users/{id}/capability 改岗位（只传 business_role 即自动套模板作用域）
 *   POST /authn/users/{id}/role       改 RBAC 角色（仅 superadmin）
 *
 * 🔴 鉴权守卫：挂载即 fetch 的 effect 必须 gate 在 token 存在（否则 401 悬空态）。
 */
import { useCallback, useEffect, useState } from 'react';
import { apiUrl, authHeaders, getToken, type AuthUser } from '../api/client';

interface CapabilityScope {
  allowed_agents?: string[];
  read_only_agents?: string[];
  data_scope?: Record<string, unknown>;
}
interface UserRow {
  id: string;
  username: string;
  display_name?: string;
  email?: string | null;
  role: string;
  tenant_id: string;
  is_active?: boolean;
  business_role?: string | null;
  business_role_label?: string | null;
  capability_scope?: CapabilityScope | null;
}
interface BusinessRoleItem {
  value: string;
  label: string;
  description?: string;
  scope?: CapabilityScope;
}

const RBAC_ROLES = [
  { value: 'viewer', label: '只读者 VIEWER' },
  { value: 'operator', label: '操作员 OPERATOR' },
  { value: 'tenant_admin', label: '租户管理员 TENANT_ADMIN' },
  { value: 'superadmin', label: '超级管理员 SUPERADMIN' },
];

const ROLE_BADGE: Record<string, string> = {
  superadmin: 'bg-purple-100 text-purple-700 border-purple-200',
  tenant_admin: 'bg-blue-100 text-blue-700 border-blue-200',
  operator: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  viewer: 'bg-gray-100 text-gray-600 border-gray-200',
};

export default function UserPermissionPanel({ me }: { me: AuthUser | null }) {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [roles, setRoles] = useState<BusinessRoleItem[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [industry, setIndustry] = useState<string>('');
  const [busy, setBusy] = useState(true);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    username: '',
    password: '',
    display_name: '',
    role: 'operator',
    business_role: '',
  });

  const isSuper = String(me?.role || '').toLowerCase() === 'superadmin';

  const load = useCallback(async () => {
    if (!getToken()) return; // 🔴 鉴权守卫
    setBusy(true);
    setErr('');
    try {
      const [ru, rr] = await Promise.all([
        fetch(apiUrl('/authn/users'), { headers: authHeaders() }),
        fetch(apiUrl(`/authn/business-roles${industry ? `?industry=${encodeURIComponent(industry)}` : ''}`), {
          headers: authHeaders(),
        }),
      ]);
      if (ru.status === 403) {
        setErr('权限不足：仅租户管理员及以上可管理用户权限。');
        setUsers([]);
      } else if (ru.ok) {
        const d = await ru.json();
        setUsers(d.users || []);
      } else {
        setErr(`用户列表加载失败（HTTP ${ru.status}）`);
      }
      if (rr.ok) {
        const d = await rr.json();
        setRoles(d.roles || []);
        setIndustries(d.industries || []);
      }
    } catch (e) {
      setErr(`加载失败：${(e as Error)?.message || e}`);
    } finally {
      setBusy(false);
    }
  }, [industry]);

  useEffect(() => {
    void load();
  }, [load]);

  const flash = (t: string) => {
    setMsg(t);
    window.setTimeout(() => setMsg(''), 3200);
  };

  const applyBusinessRole = async (u: UserRow, value: string) => {
    setErr('');
    try {
      const res = await fetch(apiUrl(`/authn/users/${u.id}/capability`), {
        method: 'POST',
        headers: authHeaders(),
        // 空串 = 清空限制，恢复全部智能体可见
        body: JSON.stringify({ business_role: value, industry: industry || null }),
      });
      if (!res.ok) throw new Error(await res.text());
      flash(`已更新 ${u.username} 的岗位权限：${value ? roleLabel(value) : '不限制（全部可见）'}`);
      setEditing(null);
      await load();
    } catch (e) {
      setErr(`岗位更新失败：${(e as Error)?.message || e}`);
    }
  };

  const applyRbacRole = async (u: UserRow, value: string) => {
    setErr('');
    try {
      const res = await fetch(apiUrl(`/authn/users/${u.id}/role`), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ role: value }),
      });
      if (!res.ok) throw new Error(await res.text());
      flash(`已更新 ${u.username} 的系统角色：${value}`);
      await load();
    } catch (e) {
      setErr(`角色更新失败：${(e as Error)?.message || e}`);
    }
  };

  const createUser = async () => {
    setErr('');
    if (!form.username.trim() || !form.password.trim()) {
      setErr('用户名与初始密码必填。');
      return;
    }
    try {
      const res = await fetch(apiUrl('/authn/users'), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          username: form.username.trim(),
          password: form.password,
          display_name: form.display_name.trim() || form.username.trim(),
          role: form.role,
          business_role: form.business_role || null,
          tenant_id: me?.tenant_id || 'default',
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      flash(`用户 ${form.username} 已创建`);
      setShowCreate(false);
      setForm({ username: '', password: '', display_name: '', role: 'operator', business_role: '' });
      await load();
    } catch (e) {
      setErr(`创建失败：${(e as Error)?.message || e}`);
    }
  };

  const roleLabel = (v?: string | null) => roles.find((r) => r.value === v)?.label || v || '未设置';
  const scopeOf = (v?: string | null) => roles.find((r) => r.value === v)?.scope;

  const agentSummary = (u: UserRow) => {
    const scope = u.capability_scope || scopeOf(u.business_role);
    const allowed = scope?.allowed_agents;
    if (!allowed || allowed.length === 0 || allowed.includes('*')) return { text: '全部智能体', full: true };
    return { text: `${allowed.length} 个智能体`, full: false, list: allowed };
  };

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-4 space-y-4">
      {/* 说明卡：讲清「怎么授权」 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold text-gray-900">🔐 用户权限</h2>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              授权方式 = <b className="text-zhiyan-700">选岗位，不勾功能</b>。
              管理员只需给用户指定业务岗位（设备工程师 / 供应链经理 / 财务成本控制 …），
              系统自动套用<b>权限模板库</b>的标准可见范围；同型号企业、同岗位即插即用。
            </p>
            <p className="text-[11px] text-gray-400 mt-1">
              系统角色（RBAC）决定「能做多重的事」，业务岗位决定「能看哪些智能体」，二者取交集，岗位只收窄不放大。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              title="行业模板：命中行业时岗位可见范围会按行业微调"
            >
              <option value="">通用模板（不分行业）</option>
              {industries.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
            <button
              className="text-xs px-3 py-1.5 rounded-md bg-zhiyan-600 text-white hover:bg-zhiyan-700 transition"
              onClick={() => setShowCreate((v) => !v)}
            >
              {showCreate ? '取消' : '+ 新增用户'}
            </button>
            <button
              className="text-xs px-3 py-1.5 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 transition"
              onClick={() => void load()}
            >
              刷新
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-1 md:grid-cols-5 gap-2">
            <input
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5"
              placeholder="用户名 *"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
            <input
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5"
              placeholder="初始密码 *"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            <input
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5"
              placeholder="显示名"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            />
            <select
              className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {RBAC_ROLES.filter((r) => isSuper || r.value !== 'superadmin').map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <select
                className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white flex-1"
                value={form.business_role}
                onChange={(e) => setForm({ ...form, business_role: e.target.value })}
              >
                <option value="">岗位：不限制</option>
                {roles.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button
                className="text-xs px-3 py-1.5 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition whitespace-nowrap"
                onClick={() => void createUser()}
              >
                创建
              </button>
            </div>
          </div>
        )}
      </div>

      {msg && <div className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 whitespace-pre-wrap">{err}</div>}

      {/* 用户表 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-700">
            用户清单 {busy ? '加载中…' : `（${users.length}）`}
          </span>
          <span className="text-[10px] text-gray-400">
            {isSuper ? '超级管理员视角：全平台用户' : `租户 ${me?.tenant_id || '-'} 内用户`}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="text-left px-4 py-2 font-medium">用户</th>
                <th className="text-left px-3 py-2 font-medium">系统角色</th>
                <th className="text-left px-3 py-2 font-medium">业务岗位</th>
                <th className="text-left px-3 py-2 font-medium">可见范围</th>
                <th className="text-left px-3 py-2 font-medium">租户</th>
                <th className="text-right px-4 py-2 font-medium">授权</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && !busy && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-gray-400">
                    暂无用户
                  </td>
                </tr>
              )}
              {users.map((u) => {
                const sum = agentSummary(u);
                return (
                  <tr key={u.id} className="border-t border-gray-100 hover:bg-gray-50/60">
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-gray-900">{u.display_name || u.username}</div>
                      <div className="text-[10px] text-gray-400">{u.username}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      {isSuper ? (
                        <select
                          className="text-[11px] border border-gray-200 rounded px-1.5 py-1 bg-white"
                          value={String(u.role).toLowerCase()}
                          onChange={(e) => void applyRbacRole(u, e.target.value)}
                        >
                          {RBAC_ROLES.map((r) => (
                            <option key={r.value} value={r.value}>
                              {r.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span
                          className={`inline-block px-2 py-0.5 rounded border text-[10px] font-medium ${
                            ROLE_BADGE[String(u.role).toLowerCase()] || ROLE_BADGE.viewer
                          }`}
                        >
                          {String(u.role).toUpperCase()}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {u.business_role ? (
                        <span className="inline-block px-2 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-700 text-[10px] font-medium">
                          {u.business_role_label || roleLabel(u.business_role)}
                        </span>
                      ) : (
                        <span className="text-gray-400 text-[11px]">未设置（不限制）</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={sum.full ? 'text-gray-500' : 'text-zhiyan-700 font-medium'}>{sum.text}</span>
                      {!sum.full && sum.list && (
                        <div className="text-[10px] text-gray-400 max-w-[280px] truncate" title={sum.list.join('、')}>
                          {sum.list.join('、')}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-gray-500">{u.tenant_id}</td>
                    <td className="px-4 py-2.5 text-right">
                      {editing === u.id ? (
                        <div className="flex items-center gap-1.5 justify-end">
                          <select
                            className="text-[11px] border border-gray-200 rounded px-1.5 py-1 bg-white"
                            defaultValue={u.business_role || ''}
                            onChange={(e) => void applyBusinessRole(u, e.target.value)}
                          >
                            <option value="">不限制（全部可见）</option>
                            {roles.map((r) => (
                              <option key={r.value} value={r.value}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                          <button className="text-[11px] text-gray-400 hover:text-gray-600" onClick={() => setEditing(null)}>
                            取消
                          </button>
                        </div>
                      ) : (
                        <button
                          className="text-[11px] px-2.5 py-1 rounded-md border border-zhiyan-200 text-zhiyan-700 hover:bg-zhiyan-50 transition"
                          onClick={() => setEditing(u.id)}
                        >
                          调整岗位
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 岗位模板速查 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="text-xs font-semibold text-gray-700 mb-2">
          岗位模板速查（{industry || '通用'}）—— 选中即生效的标准可见范围
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {roles.map((r) => {
            const allowed = r.scope?.allowed_agents || [];
            const unrestricted = allowed.length === 0 || allowed.includes('*');
            return (
              <div key={r.value} className="border border-gray-100 rounded-lg p-2.5 bg-gray-50/60">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-800">{r.label}</span>
                  <span className="text-[10px] text-gray-400">
                    {unrestricted ? '全部' : `${allowed.length} 个`}
                  </span>
                </div>
                <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">
                  {unrestricted ? '不受限：全部智能体可见' : allowed.join('、')}
                </p>
                {(r.scope?.read_only_agents || []).length > 0 && (
                  <p className="text-[10px] text-amber-600 mt-1">
                    只读：{(r.scope?.read_only_agents || []).join('、')}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
