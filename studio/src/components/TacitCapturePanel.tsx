import { useState, useEffect, useCallback } from 'react';
import {
  submitTacitSignal,
  getTacitCaptures,
  TacitCaptureItem,
  TacitChannel,
} from '../api/client';

const CHANNELS: { key: TacitChannel; label: string }[] = [
  { key: 'human', label: '人的判断' },
  { key: 'social', label: '社交/舆情' },
  { key: 'meeting', label: '会议决议' },
  { key: 'collab', label: '协作/设备' },
];

const CHANNEL_BADGE: Record<string, string> = {
  human: 'bg-purple-100 text-purple-700',
  social: 'bg-blue-100 text-blue-700',
  meeting: 'bg-amber-100 text-amber-700',
  collab: 'bg-emerald-100 text-emerald-700',
};

export default function TacitCapturePanel() {
  const [channel, setChannel] = useState<TacitChannel>('human');
  const [source, setSource] = useState('emp:operator');
  const [text, setText] = useState('');
  const [entities, setEntities] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState('');
  const [captures, setCaptures] = useState<TacitCaptureItem[]>([]);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const refresh = useCallback(async () => {
    try {
      const data = await getTacitCaptures(undefined, 50);
      setCaptures(data.tacit_captures);
      setLastUpdated(new Date());
    } catch {
      /* 静默 */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const onSubmit = async () => {
    if (!text.trim()) {
      setMsg('请填写信号内容');
      return;
    }
    setSubmitting(true);
    setMsg('');
    try {
      const ents = entities.split(',').map((s) => s.trim()).filter(Boolean);
      const res = await submitTacitSignal(
        channel,
        source.trim() || `auto:${channel}`,
        { content: text.trim() },
        ents,
        0.9,
      );
      setMsg(res.status === 'captured' ? '✅ 已捕获并锚定知识图谱（待审批）' : '已提交');
      setText('');
      setEntities('');
      await refresh();
    } catch (e: any) {
      setMsg(`❌ ${e?.message || '提交失败'}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card">
        <h4 className="text-sm font-semibold text-gray-800 mb-3">🧠 隐性信号捕获（ERP 从未覆盖的盲区）</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400">信号通道</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {CHANNELS.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setChannel(c.key)}
                  className={`text-xs px-2.5 py-1 rounded-full border ${
                    channel === c.key ? 'border-zhiyan-500 bg-zhiyan-50 text-zhiyan-700' : 'border-gray-200 text-gray-500'
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400">来源标识（如 emp:zhang / wecom:g1）</label>
            <input
              className="input-field mt-1"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="emp:operator"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs text-gray-400">信号内容（一句话判断 / 会议纪要 / 协作结论）</label>
            <textarea
              className="input-field mt-1 h-20 resize-none"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="例：这条产线换型风险偏高，建议先小批验证"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs text-gray-400">实体（逗号分隔，如 LINE:3, SUP:A）</label>
            <input
              className="input-field mt-1"
              value={entities}
              onChange={(e) => setEntities(e.target.value)}
              placeholder="LINE:3, EMP:zhang"
            />
          </div>
        </div>
        <div className="flex items-center gap-3 mt-3">
          <button className="btn-primary text-xs py-2 px-4" onClick={onSubmit} disabled={submitting}>
            {submitting ? '捕获中…' : '捕获并锚定'}
          </button>
          {msg && <span className="text-xs text-gray-500">{msg}</span>}
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-gray-800">近期隐性捕获（{captures.length}）</h4>
          <span className="text-xs text-gray-400">{lastUpdated.toLocaleTimeString('zh-CN')}</span>
        </div>
        {captures.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-8">暂无隐性信号，试试上方捕获一条</div>
        ) : (
          <div className="space-y-2">
            {captures.map((c, i) => (
              <div key={`${c.created_at}-${i}`} className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50/50">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap ${CHANNEL_BADGE[c.channel] ?? 'bg-gray-100 text-gray-600'}`}>
                  {c.channel}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700">{c.context.slice(0, 120)}</div>
                  <div className="text-[10px] text-gray-300 mt-1 font-mono">
                    {c.source} · {new Date(c.created_at).toLocaleString('zh-CN', { hour12: false })}
                    {(c.extracted?.predicate) ? ` · 锚定:${c.extracted.predicate}` : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
