import { useState, useEffect, useCallback } from 'react';
import {
  declareBlueArcAction,
  reportBlueArcActual,
  getBlueArcStatus,
  BlueArcStatus,
} from '../api/client';

function tryJson(s: string, fallback: Record<string, any>): Record<string, any> {
  try {
    return JSON.parse(s);
  } catch {
    return fallback;
  }
}

export default function BlueArcPanel() {
  const [agent, setAgent] = useState('oee_agent');
  const [predicted, setPredicted] = useState('{"oee": 0.90}');
  const [actionId, setActionId] = useState('');
  const [actual, setActual] = useState('{"oee": 0.91}');
  const [result, setResult] = useState('');
  const [status, setStatus] = useState<BlueArcStatus | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await getBlueArcStatus());
    } catch {
      /* 静默 */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const onDeclare = async () => {
    setResult('');
    try {
      const r = await declareBlueArcAction(agent.trim(), tryJson(predicted, { oee: 0.9 }));
      setActionId(r.action_id);
      setResult(`✅ 已声明动作，action_id=${r.action_id}`);
    } catch (e: any) {
      setResult(`❌ ${e?.message || '声明失败'}`);
    }
  };

  const onObserve = async () => {
    if (!actionId) {
      setResult('请先声明动作获取 action_id');
      return;
    }
    try {
      const r = await reportBlueArcActual(actionId, tryJson(actual, { oee: 0.91 }));
      setResult(r.match ? '🔵 后果匹配 → 正强化（validated）' : '🔴 后果不符 → 负强化（contradicted）');
      await refresh();
    } catch (e: any) {
      setResult(`❌ ${e?.message || '上报失败'}`);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">🔵 蓝弧闭环（行为主义自闭环：决策→执行→反馈→再学习）</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400">执行 agent</label>
            <input className="input-field mt-1" value={agent} onChange={(e) => setAgent(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-400">声明当前 action_id（上报实际用）</label>
            <input className="input-field mt-1 font-mono text-xs" value={actionId} readOnly placeholder="声明后自动填入" />
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs text-gray-400">预期后果（JSON）</label>
            <textarea className="input-field mt-1 h-16 resize-none font-mono text-xs" value={predicted} onChange={(e) => setPredicted(e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs text-gray-400">实际后果（JSON，上报用）</label>
            <textarea className="input-field mt-1 h-16 resize-none font-mono text-xs" value={actual} onChange={(e) => setActual(e.target.value)} />
          </div>
        </div>
        <div className="flex items-center gap-3 mt-3">
          <button className="btn-secondary text-xs py-2 px-4" onClick={onDeclare}>① 声明动作</button>
          <button className="btn-primary text-xs py-2 px-4" onClick={onObserve}>② 上报实际</button>
          {result && <span className="text-xs text-gray-500">{result}</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-3">
          <div className="text-2xl font-bold text-gray-800">{status?.total_consequences ?? 0}</div>
          <div className="text-xs text-gray-400">后果总数</div>
        </div>
        <div className="card p-3">
          <div className="text-2xl font-bold text-emerald-600">{status?.validated ?? 0}</div>
          <div className="text-xs text-gray-400">正强化</div>
        </div>
        <div className="card p-3">
          <div className="text-2xl font-bold text-red-500">{status?.contradicted ?? 0}</div>
          <div className="text-xs text-gray-400">负强化</div>
        </div>
        <div className="card p-3">
          <div className="text-2xl font-bold text-gray-800">{((status?.match_rate ?? 0) * 100).toFixed(0)}%</div>
          <div className="text-xs text-gray-400">匹配率</div>
        </div>
      </div>
    </div>
  );
}
