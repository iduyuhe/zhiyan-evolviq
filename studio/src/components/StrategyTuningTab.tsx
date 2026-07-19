import { useEffect, useState, useCallback } from 'react';
import {
  getStrategyPanel,
  getStrategyHistory,
  tuneStrategy,
  type StrategyKnob,
  type EffectSignal,
  type StrategySuggestion,
  type StrategyHistoryEntry,
} from '../api/client';

const TARGET_AUTONOMOUS_RATE = 0.7;

const inputCls =
  'border border-gray-200 rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-zhiyan-400';

const tabBtn = (active: boolean) =>
  `px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
    active ? 'bg-zhiyan-500 text-white shadow-sm' : 'bg-gray-100 text-gray-500 hover:text-gray-700'
  }`;

const PARAM_LABELS: Record<string, string> = {
  confidence_threshold: '置信阈值',
  max_daily_autonomous: '每日自主上限',
  price_tolerance_pct: '价格容忍度(%)',
  max_lock_qty: '最大锁定量',
};

function pct(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

function directionBadge(direction: string) {
  if (direction === 'widen') {
    return <span className="px-1.5 py-0.5 rounded text-[10px] bg-green-100 text-green-700">放权</span>;
  }
  return <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-100 text-amber-700">收紧</span>;
}

function KnobCard({
  knob,
  signal,
}: {
  knob: StrategyKnob;
  signal?: EffectSignal;
}) {
  const ar = signal?.autonomous_rate ?? 0;
  const rateColor = ar >= TARGET_AUTONOMOUS_RATE ? 'text-green-600' : 'text-amber-600';
  const small = !signal || (signal.sample_size ?? 0) < 3;
  return (
    <div className="card p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-800">{knob.name}</span>
        <span className="text-[10px] text-gray-400 font-mono">{knob.agent}</span>
      </div>

      <div className="flex items-end gap-1">
        <span className="text-2xl font-bold text-zhiyan-600">{knob.confidence_threshold.toFixed(2)}</span>
        <span className="text-[10px] text-gray-400 mb-1">置信阈值</span>
      </div>

      <div className="flex items-center gap-3 text-[11px] text-gray-500">
        <span>自主上限 <b className="text-gray-700">{knob.max_daily_autonomous}</b></span>
        <span>价容 <b className="text-gray-700">{knob.price_tolerance_pct}%</b></span>
      </div>

      {/* 自主率进度 */}
      <div>
        <div className="flex items-center justify-between text-[11px] text-gray-400">
          <span>自主率</span>
          <span className={rateColor}>{pct(ar)}</span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full mt-1 overflow-hidden">
          <div
            className={`h-full rounded-full ${ar >= TARGET_AUTONOMOUS_RATE ? 'bg-green-500' : 'bg-amber-500'}`}
            style={{ width: `${Math.min(100, ar * 100)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] text-gray-400">
        <span>
          人工批准率{' '}
          {signal?.intervention_approval_rate == null
            ? '—'
            : pct(signal.intervention_approval_rate)}
        </span>
        <span>{small ? '样本不足' : `样本 ${signal?.sample_size}`}</span>
      </div>
    </div>
  );
}

export default function StrategyTuningTab() {
  const [knobs, setKnobs] = useState<StrategyKnob[]>([]);
  const [signals, setSignals] = useState<Record<string, EffectSignal>>({});
  const [suggestions, setSuggestions] = useState<StrategySuggestion[]>([]);
  const [history, setHistory] = useState<StrategyHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  // 手动调参表单
  const [selAgent, setSelAgent] = useState('');
  const [selParam, setSelParam] = useState('confidence_threshold');
  const [selValue, setSelValue] = useState<number>(0.7);
  const [reason, setReason] = useState('');
  const [tuning, setTuning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setMsg('');
    try {
      const [panel, hist] = await Promise.all([getStrategyPanel(), getStrategyHistory()]);
      setKnobs(panel.current);
      setSignals(panel.effect_signals);
      setSuggestions(panel.suggestions);
      setHistory(hist.history);
      if (panel.current.length && !selAgent) setSelAgent(panel.current[0].agent);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }, [selAgent]);

  useEffect(() => {
    load();
  }, [load]);

  const doTune = async (agent: string, param: string, value: number, why: string) => {
    setTuning(true);
    setMsg('');
    try {
      const r = await tuneStrategy({ agent, param, value, reason: why });
      setMsg(`已调参：${agent} · ${PARAM_LABELS[param] ?? param} ${r.old} → ${r.new}`);
      await load();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setTuning(false);
    }
  };

  const applyManual = () => {
    if (!selAgent) return;
    doTune(selAgent, selParam, selValue, reason || '控制台手动调参');
    setReason('');
  };

  const adoptSuggestion = (s: StrategySuggestion) => {
    doTune(s.agent, s.param, s.suggested, `采纳建议：${s.rationale}`);
  };

  return (
    <div className="space-y-4">
      {/* 标题 + 刷新 */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <span>🎚️</span> 策略调参 · 按效果放权
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              11 个 Agent 实时授权旋钮 · 目标自主率
              <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-zhiyan-50 text-zhiyan-600">
                {pct(TARGET_AUTONOMOUS_RATE)}
              </span>
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-zhiyan-500 text-white hover:bg-zhiyan-600 disabled:opacity-50"
          >
            刷新
          </button>
        </div>
        {msg && <p className="text-xs text-gray-500 mt-2">{msg}</p>}
      </div>

      {/* 策略旋钮总览 */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-700 mb-3">策略旋钮与效果信号</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {knobs.map((k) => (
            <KnobCard key={k.agent} knob={k} signal={signals[k.agent]} />
          ))}
        </div>
      </div>

      {/* 调参建议 */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-700 mb-3">
          效果驱动调参建议 {suggestions.length > 0 && `(${suggestions.length})`}
        </h3>
        {suggestions.length === 0 ? (
          <p className="text-xs text-gray-400 py-2">当前各 Agent 运行稳健，无需调参。</p>
        ) : (
          <div className="space-y-2">
            {suggestions.map((s) => (
              <div key={s.id} className="border border-gray-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-800">
                    {s.agent} · {PARAM_LABELS[s.param] ?? s.param}
                  </span>
                  <div className="flex items-center gap-2">
                    {directionBadge(s.direction)}
                    <span className="text-[11px] text-gray-400">
                      {s.current} → <b className={s.direction === 'widen' ? 'text-green-600' : 'text-amber-600'}>{s.suggested}</b>
                    </span>
                  </div>
                </div>
                <p className="text-[11px] text-gray-500 leading-relaxed">{s.rationale}</p>
                <p className="text-[11px] text-zhiyan-600 mt-1">预期：{s.expected_effect}</p>
                <button
                  onClick={() => adoptSuggestion(s)}
                  disabled={tuning}
                  className="mt-2 px-2.5 py-1 text-[11px] font-medium rounded-md bg-zhiyan-500 text-white hover:bg-zhiyan-600 disabled:opacity-50"
                >
                  采纳建议
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 手动调参 */}
      <div className="card space-y-3">
        <h3 className="text-sm font-medium text-gray-700">手动调参</h3>
        <div className="flex gap-2 flex-wrap items-end">
          <label className="flex flex-col text-[10px] text-gray-400 gap-1">
             Agent
            <select
              value={selAgent}
              onChange={(e) => setSelAgent(e.target.value)}
              className={inputCls}
            >
              {knobs.map((k) => (
                <option key={k.agent} value={k.agent}>
                  {k.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-[10px] text-gray-400 gap-1">
            参数
            <select
              value={selParam}
              onChange={(e) => setSelParam(e.target.value)}
              className={inputCls}
            >
              {Object.keys(PARAM_LABELS).map((p) => (
                <option key={p} value={p}>
                  {PARAM_LABELS[p]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-[10px] text-gray-400 gap-1">
            目标值
            <input
              type="number"
              step="0.01"
              value={selValue}
              onChange={(e) => setSelValue(parseFloat(e.target.value) || 0)}
              className={`${inputCls} w-24`}
            />
          </label>
          <input
            placeholder="调参理由（可选）"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className={`${inputCls} flex-1 min-w-[140px]`}
          />
          <button
            onClick={applyManual}
            disabled={tuning || !selAgent}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-zhiyan-500 text-white hover:bg-zhiyan-600 disabled:opacity-50"
          >
            应用
          </button>
        </div>
        <p className="text-[10px] text-gray-400">
          说明：置信阈值自动夹紧于 [0.50, 0.95]；调参直接写入运行时授权边界（非死代码），并记入下方审计轨迹。
        </p>
      </div>

      {/* 调参审计轨迹 */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-700 mb-3">调参审计轨迹 ({history.length})</h3>
        {history.length === 0 ? (
          <p className="text-xs text-gray-400 py-2">暂无调参记录。</p>
        ) : (
          <div className="space-y-1 max-h-72 overflow-auto">
            {history.map((h, i) => (
              <div key={i} className="text-xs border-b border-gray-100 py-1.5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                    h.basis === 'suggestion' ? 'bg-zhiyan-50 text-zhiyan-600' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {h.basis === 'suggestion' ? '采纳建议' : '手动'}
                  </span>
                  <span className="font-mono text-gray-700">{h.agent}</span>
                  <span className="text-gray-500">{PARAM_LABELS[h.param] ?? h.param}</span>
                  <span className="text-gray-400">
                    {String(h.old)} → <b className="text-zhiyan-600">{String(h.new)}</b>
                  </span>
                </div>
                <span className="text-[10px] text-gray-400">{h.ts.slice(0, 19).replace('T', ' ')}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
