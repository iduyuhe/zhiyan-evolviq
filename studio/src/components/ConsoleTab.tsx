import { useState, useEffect, useCallback } from 'react';
import {
  getBoundaries,
  patchBoundary,
  getInterventions,
  decideIntervention,
  getEffectReport,
  AuthBoundary,
  Intervention,
  EffectReport,
} from '../api/client';

type Panel = 'boundary' | 'intervention' | 'report';

const AGENT_LABELS: Record<string, string> = {
  supply_chain: '📦 供应链自治',
  pm_maintenance: '🔧 设备维护',
  yield_analysis: '📈 良率分析',
  quality_trace: '🔍 质量追溯',
  dfm_check: '📐 DFM检查',
  bom_selector: '🔬 BOM选型',
  oee_optimizer: '⚡ OEE优化',
  eco_change: '🔄 ECO变更',
  smt_changeover: '🔀 SMT换线',
  aoi_judge: '👁 AOI判定',
  ipc_standard: '📋 IPC标准',
};

export default function ConsoleTab() {
  const [panel, setPanel] = useState<Panel>('boundary');
  const [boundaries, setBoundaries] = useState<AuthBoundary[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [report, setReport] = useState<EffectReport | null>(null);
  const [loading, setLoading] = useState(true);

  const loadBoundaries = useCallback(async () => {
    try {
      setBoundaries(await getBoundaries());
    } catch { /* silent */ }
  }, []);

  const loadInterventions = useCallback(async () => {
    try {
      const d = await getInterventions();
      setInterventions(d.interventions);
      setPendingCount(d.pending);
    } catch { /* silent */ }
  }, []);

  const loadReport = useCallback(async () => {
    try {
      setReport(await getEffectReport());
    } catch { /* silent */ }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadBoundaries(), loadInterventions(), loadReport()]);
    setLoading(false);
  }, [loadBoundaries, loadInterventions, loadReport]);

  useEffect(() => {
    loadAll();
    const t = setInterval(loadAll, 6000);
    return () => clearInterval(t);
  }, [loadAll]);

  const handleBoundaryChange = async (id: string, patch: Partial<AuthBoundary>) => {
    await patchBoundary(id, patch);
    loadBoundaries();
  };

  const handleDecide = async (id: string, approved: boolean) => {
    await decideIntervention(id, approved, approved ? '控制台审批通过' : '控制台驳回');
    loadInterventions();
    loadReport();
  };

  return (
    <div className="page-transition space-y-4">
      {/* 头部 */}
      <div className="card-highlight relative overflow-hidden">
        <div className="relative flex items-center gap-3 flex-wrap">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center text-white shadow-sm">
            🎛️
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-900">企业控制台</h2>
            <p className="text-xs text-gray-400">设定 Agent 目标与边界 · 仅在异常时介入 · 验收结果</p>
          </div>
          <div className="flex items-center gap-2">
            {pendingCount > 0 && (
              <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-red-50 text-red-600 border border-red-200 animate-pulse">
                ⚠️ {pendingCount} 项待审批
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 子面板切换 */}
      <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {([
          { k: 'boundary', label: '授权边界', icon: '🔒' },
          { k: 'intervention', label: '异常介入', icon: '🤝', badge: pendingCount },
          { k: 'report', label: '效果报告', icon: '📊' },
        ] as { k: Panel; label: string; icon: string; badge?: number }[]).map(p => (
          <button
            key={p.k}
            onClick={() => setPanel(p.k)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5 ${
              panel === p.k ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {p.icon} {p.label}
            {p.badge ? <span className="ml-0.5 px-1.5 py-0.5 text-[10px] rounded-full bg-red-500 text-white">{p.badge}</span> : null}
          </button>
        ))}
      </div>

      {loading && panel === 'boundary' && boundaries.length === 0 ? (
        <div className="card text-sm text-gray-400">加载中…</div>
      ) : null}

      {panel === 'boundary' && (
        <div className="space-y-3">
          <p className="text-xs text-gray-500">
            授权边界定义 Agent 可自主执行的范围。超出边界的动作会暂停并推送到「异常介入中心」等你确认。
          </p>
          {boundaries.map(b => (
            <BoundaryCard key={b.id} boundary={b} onChange={handleBoundaryChange} />
          ))}
        </div>
      )}

      {panel === 'intervention' && (
        <InterventionPanel
          interventions={interventions}
          pending={pendingCount}
          onDecide={handleDecide}
        />
      )}

      {panel === 'report' && report && <ReportPanel report={report} />}
    </div>
  );
}

function BoundaryCard({ boundary, onChange }: { boundary: AuthBoundary; onChange: (id: string, patch: Partial<AuthBoundary>) => void }) {
  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState(boundary.max_lock_qty);
  const [price, setPrice] = useState(boundary.price_tolerance_pct);
  const [conf, setConf] = useState(Math.round(boundary.confidence_threshold * 100));

  // 供应链类边界涉及锁物料/采购，展示锁定上限与价格波动；其余 Agent 靠置信度 + 动作类型送审
  const isSupplyLike = boundary.auto_execute_actions.includes('lock_inventory')
    || boundary.require_approval_actions.some(a => ['purchase_order', 'price_change', 'new_supplier'].includes(a));

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">{AGENT_LABELS[boundary.agent] || boundary.agent}</span>
          <span className={`px-2 py-0.5 text-[10px] rounded-full ${boundary.enabled ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-400'}`}>
            {boundary.enabled ? '已启用' : '已停用'}
          </span>
        </div>
        <button onClick={() => setOpen(!open)} className="text-xs text-indigo-600 hover:underline">
          {open ? '收起' : '调整参数'}
        </button>
      </div>

      {/* 当前边界摘要：供应链类 vs 其他 Agent 差异化展示 */}
      {isSupplyLike ? (
        <div className="grid grid-cols-3 gap-2">
          <Metric label="单次锁定上限" value={`${boundary.max_lock_qty} pcs`} />
          <Metric label="价格波动容忍" value={`±${boundary.price_tolerance_pct}%`} />
          <Metric label="置信度阈值" value={`${Math.round(boundary.confidence_threshold * 100)}%`} />
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <Metric label="可自主动作" value={`${boundary.auto_execute_actions.length} 类`} />
          <Metric label="须审批动作" value={`${boundary.require_approval_actions.length} 类`} />
          <Metric label="置信度阈值" value={`${Math.round(boundary.confidence_threshold * 100)}%`} />
        </div>
      )}

      <div className="text-[11px] text-gray-400">
        可自主执行：{boundary.auto_execute_actions.join('、') || '无'} ｜ 须审批：{boundary.require_approval_actions.join('、') || '无'}
      </div>

      {open && (
        <div className="pt-2 border-t border-gray-100 space-y-3">
          {isSupplyLike && (
            <>
              <Slider label="单次锁定上限" value={qty} min={0} max={5000} step={50} unit="pcs"
                onChange={setQty} onCommit={(v) => onChange(boundary.id, { max_lock_qty: v })} />
              <Slider label="价格波动容忍度" value={price} min={0} max={30} step={1} unit="%"
                onChange={setPrice} onCommit={(v) => onChange(boundary.id, { price_tolerance_pct: v })} />
            </>
          )}
          <Slider label="置信度阈值" value={conf} min={50} max={100} step={5} unit="%"
            onChange={setConf} onCommit={(v) => onChange(boundary.id, { confidence_threshold: v / 100 })} />
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2">
      <div className="text-[10px] text-gray-400">{label}</div>
      <div className="text-sm font-semibold text-gray-800">{value}</div>
    </div>
  );
}

function Slider({ label, value, min, max, step, unit, onChange, onCommit }: {
  label: string; value: number; min: number; max: number; step: number; unit: string;
  onChange: (v: number) => void; onCommit: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-600">{label}</span>
        <span className="text-xs font-semibold text-indigo-600">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        onMouseUp={(e) => onCommit(Number((e.target as HTMLInputElement).value))}
        onTouchEnd={(e) => onCommit(Number((e.target as HTMLInputElement).value))}
        className="w-full accent-indigo-500" />
    </div>
  );
}

function InterventionPanel({ interventions, pending, onDecide }: {
  interventions: Intervention[]; pending: number; onDecide: (id: string, approved: boolean) => void;
}) {
  if (interventions.length === 0) {
    return (
      <div className="card text-center py-10">
        <div className="text-3xl mb-2">✅</div>
        <p className="text-sm text-gray-500">暂无待处理事项。所有 Agent 动作均在授权边界内自主执行。</p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className="px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200">待审批 {pending}</span>
        <span>以下动作超出授权边界，需你确认后 Agent 才能执行</span>
      </div>
      {interventions.map(iv => (
        <div key={iv.id} className={`card border-l-4 ${iv.status === 'pending' ? 'border-l-amber-400' : iv.status === 'approved' ? 'border-l-green-400' : 'border-l-red-400'}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-800">{iv.action.detail}</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded bg-gray-100 text-gray-500">{AGENT_LABELS[iv.agent] || iv.agent}</span>
              </div>
              <p className="text-xs text-amber-600 mt-1">⏸️ {iv.reason}</p>
              <p className="text-[11px] text-gray-400 mt-1">
                {iv.action.category} · {iv.action.qty} pcs · 置信度 {Math.round(iv.action.confidence * 100)}%
              </p>
            </div>
            {iv.status === 'pending' ? (
              <div className="flex flex-col gap-1.5 shrink-0">
                <button onClick={() => onDecide(iv.id, true)}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-green-500 text-white hover:bg-green-600 transition-colors">
                  ✅ 批准
                </button>
                <button onClick={() => onDecide(iv.id, false)}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors">
                  ❌ 驳回
                </button>
              </div>
            ) : (
              <span className={`text-xs font-medium ${iv.status === 'approved' ? 'text-green-600' : 'text-red-500'}`}>
                {iv.status === 'approved' ? '已批准' : '已驳回'}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ReportPanel({ report }: { report: EffectReport }) {
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="自主执行率" value={pct(report.autonomous_rate)} sub={`目标 ${pct(report.target_autonomous_rate)}`}
          good={report.meets_target} />
        <StatCard label="累计节省工时" value={`${report.time_saved_hours}h`} sub={`${report.auto_actions} 次自主执行`} good />
        <StatCard label="异常准确率" value={pct(report.intervention_accuracy)} sub={`${report.human_actions} 次介入`} good={report.intervention_accuracy >= 0.7} />
        <StatCard label="执行会话数" value={`${report.sessions}`} sub={`总动作 ${report.total_actions}`} good />
      </div>

      {/* 自主率进度条 */}
      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">自主执行率 vs 目标</span>
          <span className={`text-xs font-medium ${report.meets_target ? 'text-green-600' : 'text-amber-600'}`}>
            {report.meets_target ? '✅ 达标' : '⚠️ 未达标'}
          </span>
        </div>
        <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
          <div className="absolute left-0 top-0 h-full bg-indigo-500 rounded-full transition-all"
            style={{ width: pct(report.autonomous_rate) }} />
          {/* 目标线 */}
          <div className="absolute top-0 h-full border-l-2 border-dashed border-gray-400"
            style={{ left: pct(report.target_autonomous_rate) }} />
        </div>
        <p className="text-[11px] text-gray-400 mt-1.5">
          虚线为 70% 目标线。Agent 在授权边界内自主完成的动作占比越高，人工干预越少。
        </p>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, good }: { label: string; value: string; sub: string; good: boolean }) {
  return (
    <div className="card">
      <div className="text-[11px] text-gray-400">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${good ? 'text-gray-900' : 'text-amber-600'}`}>{value}</div>
      <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>
    </div>
  );
}
