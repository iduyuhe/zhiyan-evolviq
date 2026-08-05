// 企业登录页（v28）：调用 /authn/login，成功后回调上层注入 token + 用户信息
import { useState } from 'react';
import { login, type AuthUser } from '../api/client';

interface Props {
  onLogin: (token: string, user: AuthUser) => void;
  defaultUsername?: string;
}

export default function Login({ onLogin, defaultUsername = 'admin' }: Props) {
  const [username, setUsername] = useState(defaultUsername);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = await login(username.trim(), password);
      onLogin(data.access_token, data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-50 to-white px-4">
      <div className="w-full max-w-sm">
        {/* 品牌 */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-zhiyan-500 to-zhiyan-700 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
            智
          </div>
          <h1 className="mt-4 text-xl font-semibold text-gray-900">智衍 EvolvIQ</h1>
          <p className="text-xs text-gray-400 mt-1">工业智能体互联平台 · 企业登录</p>
        </div>

        {/* 登录卡片 */}
        <form onSubmit={submit} className="card space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">用户名</label>
            <input
              type="text"
              value={username}
              autoFocus
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 outline-none focus:border-zhiyan-400 focus:ring-2 focus:ring-zhiyan-100 transition"
              placeholder="admin"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 outline-none focus:border-zhiyan-400 focus:ring-2 focus:ring-zhiyan-100 transition"
              placeholder="请输入密码"
            />
          </div>

          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/70 border-t-transparent rounded-full animate-spin" />
                登录中…
              </>
            ) : (
              '登 录'
            )}
          </button>

          <p className="text-[11px] text-gray-400 text-center leading-relaxed">
            未配置企业目录时，使用本地账号登录。<br />
            默认超级管理员：<span className="font-mono text-gray-500">admin</span>
          </p>

          <div className="mt-3 rounded-lg bg-gray-50 border border-gray-200 px-3 py-2 text-center">
            <p className="text-[11px] text-gray-500 leading-relaxed">
              公开体验账号（任何人可登录体验演示数据）：
            </p>
            <p className="text-xs text-gray-800 mt-1">
              用户名 <span className="font-mono font-semibold">demo</span>
              &nbsp;·&nbsp; 密码 <span className="font-mono font-semibold">EvolvIQ2026</span>
            </p>
          </div>
        </form>

        <p className="text-center text-[11px] text-gray-400 mt-6">
          © 2026 工业5点0产业生态联盟
        </p>
      </div>
    </div>
  );
}
