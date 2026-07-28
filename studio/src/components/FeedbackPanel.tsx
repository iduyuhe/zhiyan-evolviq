/**
 * 共生进化环 · 反馈入口（S2-6，#313）
 *
 * 客户与平台相互成长：每条情报/结论旁的轻量反馈位——「👍 有用 / 👎 不准 / 💡 我有想法」。
 * 不满不是流失信号，是最高价值的进化燃料。提交即落库（租户隔离）；
 * 含文本的实质反馈经脱敏审核门（平台管理员）提报为开源 GitHub Issue（from-customer）。
 *
 * 纪律：所有请求经 client.ts authHeaders()；渲染在 App 的 ErrorBoundary 内；
 * 网络错误静默处理不白屏；48h 首响应 SLA 看板仅对租户管理员/超级管理员可见。
 */
import { useCallback, useEffect, useState } from 'react';
import {
  FeedbackBoard, FeedbackItem, FeedbackType,
  escalateFeedback, getFeedbackBoard, listMyFeedback, submitFeedback,
} from '../api/client';

function extractDetail(raw: string): string {
  try {
    const j = JSON.parse(raw);
    return j.detail || raw;
  } catch {
    return raw;
  }
}

const TYPE_META: Record<FeedbackType, { icon: string; label: string; hint: string }> = {
  like: { icon: '👍', label: '有用', hint: '这条结论帮到了我' },
  dislike: { icon: '👎', label: '不准', hint: '结论有误 / 与事实不符' },
  idea: { icon: '💡', label: '我有想法', hint: '我希望 / 我建议…' },
};

const STATUS_LABEL: Record<string, string> = {
  received: '已收到',
  pending_review: '审核中',
  issued: '已提报开源',
  rejected: '已归档',
};

export default function FeedbackPanel() {
  const [fbType, setFbType] = useState<FeedbackType>('idea');
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [myList, setMyList] = useState<FeedbackItem[]>([]);
  const [board, setBoard] = useState<FeedbackBoard | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    try {
      const mine = await listMyFeedback();
      setMyList(mine.feedbacks);
    } catch (e) {
      // 静默：ErrorBoundary 兜底渲染错误，网络错误不白屏
    }
    try {
      const b = await getFeedbackBoard();
      setBoard(b);
    } catch (e) {
      // 403（非管理员）→ 不显示看板；其它静默
      setBoard(null);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSubmit = async () => {
    setError('');
    setSuccess('');
    if (!text.trim() && fbType === 'like') {
      // 👍 允许无文本；👎/💡 建议带文本但非强制
    }
    setSubmitting(true);
    try {
      const r = await submitFeedback(fbType, text.trim() || undefined);
      setSuccess(`已收到你的反馈（${TYPE_META[fbType].label}）· 你的每条反馈都会推动平台进化`);
      setText('');
      setMyList((prev) => [r.feedback, ...prev]);
    } catch (e) {
      setError(extractDetail(e instanceof Error ? e.message : String(e)));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEscalate = async (fb: FeedbackItem) => {
    setError('');
    setSuccess('');
    try {
      const r = await escalateFeedback(fb.id);
      if (r.success) {
        setSuccess(`已提报为开源 Issue #${r.github_issue_number}（from-customer）· 你的反馈正在推动平台进化`);
      } else {
        setError('提报未成功（GitHub 暂不可用），反馈已脱敏待运营补提报');
      }
      load();
    } catch (e) {
      setError(extractDetail(e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-zhiyan-600 text-lg">🤝</span>
          <h2 className="text-base font-semibold text-gray-900">共生进化环 · 反馈入口</h2>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          不满不是流失信号，是最高价值的进化燃料。你的每条反馈都会推动平台进化——并经脱敏后（剥离租户名与隐私）进入开源社区。
        </p>

        {/* 类型选择 */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          {(Object.keys(TYPE_META) as FeedbackType[]).map((t) => {
            const m = TYPE_META[t];
            const active = fbType === t;
            return (
              <button
                key={t}
                onClick={() => setFbType(t)}
                className={`flex flex-col items-center gap-1 py-3 rounded-lg border transition-all ${
                  active
                    ? 'border-zhiyan-300 bg-zhiyan-50 text-zhiyan-700 shadow-sm'
                    : 'border-gray-200 bg-white text-gray-500 hover:border-zhiyan-200'
                }`}
              >
                <span className="text-2xl leading-none">{m.icon}</span>
                <span className="text-xs font-medium">{m.label}</span>
              </button>
            );
          })}
        </div>

        {/* 文本 */}
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder={`${TYPE_META[fbType].hint}${fbType === 'like' ? '（可留空）' : ''}`}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 resize-none focus:outline-none focus:border-zhiyan-300"
        />

        {error && (
          <div className="mt-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</div>
        )}
        {success && (
          <div className="mt-2 text-xs text-green-700 bg-green-50 border border-green-100 rounded-lg px-3 py-2">{success}</div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="mt-3 w-full btn-primary disabled:opacity-50"
        >
          {submitting ? '提交中…' : '提交反馈'}
        </button>
      </div>

      {/* 48h SLA 看板（仅管理员可见） */}
      {board && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-800 mb-2">📊 48 小时首响应看板</h3>
          <div className="grid grid-cols-4 gap-2 text-center">
            <div className="bg-gray-50 rounded-lg py-2">
              <div className="text-lg font-semibold text-gray-800">{board.total}</div>
              <div className="text-[10px] text-gray-400">累计反馈</div>
            </div>
            <div className="bg-amber-50 rounded-lg py-2">
              <div className="text-lg font-semibold text-amber-600">{board.pending}</div>
              <div className="text-[10px] text-gray-400">待响应</div>
            </div>
            <div className="bg-red-50 rounded-lg py-2">
              <div className="text-lg font-semibold text-red-600">{board.overdue}</div>
              <div className="text-[10px] text-gray-400">已逾期</div>
            </div>
            <div className="bg-green-50 rounded-lg py-2">
              <div className="text-lg font-semibold text-green-600">
                {board.sla_rate == null ? '—' : `${Math.round(board.sla_rate * 100)}%`}
              </div>
              <div className="text-[10px] text-gray-400">SLA 达成</div>
            </div>
          </div>
          <p className="text-[10px] text-gray-400 mt-2">
            红线：任何反馈 48 小时内必有首次回音（哪怕只是「已收到、已立项」）。
          </p>
        </div>
      )}

      {/* 我的反馈 */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">我的反馈</h3>
        {myList.length === 0 ? (
          <p className="text-xs text-gray-400">还没有提交过反馈。在上方选择 👍 / 👎 / 💡 即可提交。</p>
        ) : (
          <ul className="space-y-2">
            {myList.map((fb) => (
              <li key={fb.id} className="border border-gray-100 rounded-lg p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{TYPE_META[fb.feedback_type]?.icon || '•'}</span>
                    <span className="text-xs font-medium text-gray-700">
                      {TYPE_META[fb.feedback_type]?.label || fb.feedback_type}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                      {STATUS_LABEL[fb.status] || fb.status}
                    </span>
                  </div>
                  {fb.status === 'received' && (fb.feedback_type !== 'like' || fb.text) && (
                    <button
                      onClick={() => handleEscalate(fb)}
                      title="脱敏后提报为开源 Issue"
                      className="text-[11px] px-2 py-1 rounded-md text-zhiyan-700 hover:bg-zhiyan-50 border border-zhiyan-200 transition"
                    >
                      提报开源
                    </button>
                  )}
                </div>
                {fb.text && <p className="text-xs text-gray-600 mt-1 whitespace-pre-wrap break-words">{fb.text}</p>}
                {fb.github_issue_url && (
                  <a
                    href={fb.github_issue_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-block mt-1 text-[11px] text-blue-600 hover:underline"
                  >
                    🔗 已提交开源社区 Issue #{fb.github_issue_number}
                  </a>
                )}
                {fb.status === 'issued' && !fb.github_issue_url && (
                  <p className="text-[11px] text-amber-600 mt-1">已脱敏，待运营补提报开源</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
