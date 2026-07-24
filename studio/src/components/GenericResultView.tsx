import { useState } from 'react';
import type { ReactElement } from 'react';

interface ResultViewProps {
  result: any;
  onNewGoal: () => void;
}

const AGENT_META: Record<string, { title: string; icon: string }> = {
  dfm_check: { title: 'DFM检查报告', icon: '📐' },
  bom_selector: { title: 'BOM选型分析', icon: '🔬' },
  oee_optimizer: { title: 'OEE优化分析', icon: '⚡' },
  eco_change: { title: 'ECO变更影响分析', icon: '🔄' },
  smt_changeover: { title: 'SMT换线优化', icon: '🔀' },
  aoi_judge: { title: 'AOI判定分析', icon: '👁' },
  ipc_standard: { title: 'IPC标准判定', icon: '📋' },
  aps_scheduler: { title: '计划排程分析', icon: '🧠' },
  energy_carbon: { title: '能源碳ESG分析', icon: '🌿' },
  cost_analysis: { title: '制造成本分析', icon: '💰' },
  demand_order: { title: '需求订单分析', icon: '📊' },
  wms_logistics: { title: '仓储物流分析', icon: '🚚' },
  compliance_q: { title: '质量合规分析', icon: '🛡️' },
  executive_cockpit: { title: '经营驾驶舱', icon: '🏢' },
  rd_npi: { title: '研发新产导入', icon: '🔬' },
  procurement_manage: { title: '采购供应商', icon: '📑' },
};

export default function GenericResultView({ result, onNewGoal }: ResultViewProps) {
  const agent = result.agent || 'unknown';
  const meta = AGENT_META[agent] || { title: '分析结果', icon: '📊' };
  const [activeTab, setActiveTab] = useState(0);

  const tabs = getTabs(agent, result);

  return (
    <div className="max-w-4xl mx-auto space-y-4 animate-fade-in">
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{meta.icon}</span>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{meta.title}</h2>
              <p className="text-sm text-gray-500">{result.summary || ''}</p>
            </div>
          </div>
          <span className={`px-3 py-1 text-xs font-medium rounded-full ${
            result.status === 'completed' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
          }`}>
            {result.status === 'completed' ? '已完成' : result.status}
          </span>
        </div>

        {tabs.length > 1 && (
          <div className="flex gap-1 mb-4 border-b border-gray-200">
            {tabs.map((t, i) => (
              <button
                key={i}
                className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === i ? 'border-zhiyan-500 text-zhiyan-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setActiveTab(i)}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        <div className="space-y-3">
          {tabs[activeTab]?.content}
        </div>
      </div>

      {result.recommendations && result.recommendations.length > 0 && (
        <div className="bg-blue-50 rounded-xl p-5 border border-blue-100">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">建议</h3>
          <div className="space-y-1.5">
            {result.recommendations.map((r: string, i: number) => (
              <p key={i} className="text-sm text-blue-800">{r}</p>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-center pt-2">
        <button
          onClick={onNewGoal}
          className="px-6 py-2.5 bg-zhiyan-600 text-white text-sm font-medium rounded-lg hover:bg-zhiyan-700 transition-colors"
        >
          新建目标
        </button>
      </div>
    </div>
  );
}

function getTabs(agent: string, result: any): { label: string; content: ReactElement }[] {
  switch (agent) {
    case 'dfm_check':
      return getDFMTabs(result);
    case 'bom_selector':
      return getBOMTabs(result);
    case 'oee_optimizer':
      return getOEETabs(result);
    case 'eco_change':
      return getECOTabs(result);
    case 'smt_changeover':
      return getChangeoverTabs(result);
    case 'aoi_judge':
      return getAOITabs(result);
    case 'ipc_standard':
      return getIPCTabs(result);
    case 'aps_scheduler':
      return getAPSTabs(result);
    case 'energy_carbon':
      return getEnergyTabs(result);
    case 'cost_analysis':
      return getCostTabs(result);
    case 'demand_order':
      return getDemandTabs(result);
    case 'wms_logistics':
      return getWmsTabs(result);
    case 'compliance_q':
      return getComplianceTabs(result);
    case 'executive_cockpit':
      return getExecutiveTabs(result);
    case 'rd_npi':
      return getNpiTabs(result);
    case 'procurement_manage':
      return getProcurementTabs(result);
    default:
      return [{ label: '结果', content: <pre className="text-xs text-gray-600 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre> }];
  }
}

function StatCard({ label, value, unit, color }: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-semibold ${color || 'text-gray-900'}`}>{value}{unit && <span className="text-sm text-gray-400 ml-1">{unit}</span>}</p>
    </div>
  );
}

function Badge({ status, children }: { status: string; children: React.ReactNode }) {
  const colors: Record<string, string> = {
    fail: 'bg-red-50 text-red-700',
    warning: 'bg-amber-50 text-amber-700',
    pass: 'bg-green-50 text-green-700',
    critical: 'bg-red-100 text-red-800',
    high: 'bg-orange-50 text-orange-700',
    medium: 'bg-amber-50 text-amber-700',
    low: 'bg-green-50 text-green-700',
    excellent: 'bg-green-50 text-green-700',
    good: 'bg-blue-50 text-blue-700',
    positive: 'bg-green-50 text-green-700',
    neutral: 'bg-gray-100 text-gray-600',
    none: 'bg-gray-100 text-gray-500',
    defect: 'bg-red-100 text-red-800',
    acceptable: 'bg-green-50 text-green-700',
  };
  return <span className={`px-2 py-0.5 text-xs font-medium rounded ${colors[status] || 'bg-gray-100 text-gray-600'}`}>{children}</span>;
}

function getDFMTabs(result: any) {
  const gradeColor = result.overall_grade === 'A' ? 'text-green-600' : result.overall_grade === 'B' ? 'text-blue-600' : result.overall_grade === 'C' ? 'text-amber-600' : 'text-red-600';
  return [
    {
      label: '概览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="评级" value={result.overall_grade} color={gradeColor} />
            <StatCard label="总检查项" value={result.total_checks || 0} />
            <StatCard label="不合格" value={result.fail_count || 0} color="text-red-600" />
            <StatCard label="警告" value={result.warning_count || 0} color="text-amber-600" />
          </div>
          <p className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3">{result.verdict}</p>
        </div>
      ),
    },
    {
      label: '检查明细',
      content: (
        <div className="space-y-2">
          {(result.checks || []).map((c: any, i: number) => (
            <div key={i} className="flex items-start gap-3 p-2.5 bg-gray-50 rounded-lg">
              <div className="flex-shrink-0 mt-0.5"><Badge status={c.status}>{c.status}</Badge></div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{c.rule}</p>
                <p className="text-xs text-gray-500">{c.location}</p>
                {c.risk_detail && <p className="text-xs text-gray-600 mt-1">{c.risk_detail}</p>}
                <p className="text-xs text-gray-400 mt-0.5">实际: {c.actual} {c.unit} / 要求: {c.required} {c.unit}</p>
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getBOMTabs(result: any) {
  return [
    {
      label: '目标器件',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="当前单价" value={`$${result.target_component?.unit_price || 0}`} />
            <StatCard label="生命周期" value={result.target_component?.lifecycle || ''} />
            <StatCard label="交期" value={`${result.target_component?.lead_time || 0}天`} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.target_component?.manufacturer} {result.target_component?.part_number}</p>
          </div>
        </div>
      ),
    },
    {
      label: '替代方案',
      content: (
        <div className="space-y-2">
          {(result.alternatives || []).map((a: any, i: number) => (
            <div key={i} className={`p-3 rounded-lg border ${i === 0 ? 'border-zhiyan-300 bg-zhiyan-50' : 'border-gray-200 bg-gray-50'}`}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium text-gray-900">{a.part_number} {a.is_domestic && '🇨🇳'}</p>
                <Badge status={a.compatibility === 'pin-to-pin' ? 'pass' : 'warning'}>{a.compatibility}</Badge>
              </div>
              <p className="text-xs text-gray-500">{a.manufacturer} · ${a.unit_price} ({a.price_diff_pct > 0 ? '+' : ''}{a.price_diff_pct}%) · 交期{a.lead_time_days}天 · 库存{a.stock_qty}</p>
              <p className="text-xs text-gray-600 mt-1">{a.compatibility_notes}</p>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '成本分析',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="年用量" value={result.cost_analysis?.annual_qty || 0} unit="pcs" />
            <StatCard label="年节省" value={`$${result.cost_analysis?.annual_savings_usd || 0}`} color="text-green-600" />
            <StatCard label="节省比例" value={`${result.cost_analysis?.savings_pct || 0}%`} color="text-green-600" />
          </div>
        </div>
      ),
    },
  ];
}

function getOEETabs(result: any) {
  return [
    {
      label: 'OEE总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="平均OEE" value={`${result.avg_oee || 0}%`} color={(result.avg_oee || 0) >= 85 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="目标" value={`${result.oee_target || 85}%`} />
            <StatCard label="差距" value={`${result.gap_to_target || 0}%`} color={(result.gap_to_target || 0) < 0 ? 'text-red-600' : 'text-green-600'} />
            <StatCard label="瓶颈产线" value={result.bottleneck?.slice(-3) || ''} color="text-red-600" />
          </div>
        </div>
      ),
    },
    {
      label: '产线详情',
      content: (
        <div className="space-y-2">
          {(result.lines || []).map((l: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{l.line_name}</p>
                <Badge status={l.status}>{l.oee}%</Badge>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <span className="text-gray-600">可用率: <span className="font-medium text-gray-900">{l.availability}%</span></span>
                <span className="text-gray-600">性能率: <span className="font-medium text-gray-900">{l.performance}%</span></span>
                <span className="text-gray-600">质量率: <span className="font-medium text-gray-900">{l.quality}%</span></span>
              </div>
              <div className="mt-2 space-y-0.5">
                {(l.losses || []).filter((x: any) => x.impact_hours > 0.1 || x.impact_qty > 10).map((loss: any, j: number) => (
                  <p key={j} className="text-xs text-gray-500">{loss.name}: {loss.detail}</p>
                ))}
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getECOTabs(result: any) {
  return [
    {
      label: '变更概览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="优先级" value={result.priority || ''} color={result.priority === 'high' ? 'text-red-600' : 'text-amber-600'} />
            <StatCard label="库存暴露" value={`$${(result.inventory_exposure_usd || 0).toLocaleString()}`} color="text-red-600" />
            <StatCard label="年节省" value={`$${(result.annual_savings_usd || 0).toLocaleString()}`} color="text-green-600" />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm font-medium text-gray-900">{result.title}</p>
            <p className="text-xs text-gray-500 mt-1">发起人: {result.initiator} · 涉及部门: {(result.departments_involved || []).join('/')}</p>
          </div>
        </div>
      ),
    },
    {
      label: '受影响项',
      content: (
        <div className="space-y-2">
          {(result.affected_items || []).map((item: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-900">{item.category}: {item.part}</p>
                <p className="text-xs text-gray-500">{item.action}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{item.qty?.toLocaleString()}</p>
                {item.value_usd > 0 && <p className="text-xs text-gray-500">${item.value_usd.toLocaleString()}</p>}
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '行动项',
      content: (
        <div className="space-y-2">
          {(result.required_actions || []).map((a: any, i: number) => (
            <div key={i} className="flex items-start gap-3 p-2.5 bg-gray-50 rounded-lg">
              <span className="px-2 py-0.5 text-xs font-medium bg-zhiyan-50 text-zhiyan-700 rounded flex-shrink-0">{a.dept}</span>
              <div className="flex-1">
                <p className="text-sm text-gray-900">{a.action}</p>
                <p className="text-xs text-gray-400">截止: {a.deadline}</p>
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getChangeoverTabs(result: any) {
  const smed = result.smed_analysis || {};
  return [
    {
      label: '换线计划',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="预估时间" value={`${result.estimated_time_min || 0}min`} />
            <StatCard label="历史平均" value={`${result.avg_history_time_min || 0}min`} />
            <StatCard label="SMED优化后" value={`${result.optimized_time_min || 0}min`} color="text-green-600" />
            <StatCard label="节省" value={`${result.improvement_min || 0}min`} color="text-green-600" />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.from_product} → {result.to_product}</p>
            <p className="text-xs text-gray-500 mt-1">Feeder: 拆{result.feeder_changes?.remove} 加{result.feeder_changes?.add} 留{result.feeder_changes?.keep} · 钢网: {result.stencil_id}</p>
          </div>
        </div>
      ),
    },
    {
      label: '关键路径',
      content: (
        <div className="space-y-1.5">
          {(result.critical_path || []).map((s: any, i: number) => (
            <div key={i} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
              <span className="w-6 h-6 rounded-full bg-zhiyan-100 text-zhiyan-700 text-xs font-medium flex items-center justify-center flex-shrink-0">{s.step}</span>
              <p className="flex-1 text-sm text-gray-900">{s.action}</p>
              <span className="text-xs text-gray-500">{s.time_min}min</span>
              <Badge status={s.type === 'internal' ? 'good' : 'medium'}>{s.type}</Badge>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '检查清单',
      content: (
        <div className="space-y-1.5">
          {(result.checklist || []).map((c: string, i: number) => (
            <div key={i} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
              <span className="w-4 h-4 border-2 border-gray-300 rounded flex-shrink-0"></span>
              <p className="text-sm text-gray-700">{c}</p>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getAOITabs(result: any) {
  return [
    {
      label: '误报概览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="当前误报率" value={`${result.false_alarm_rate || 0}%`} color="text-red-600" />
            <StatCard label="优化后" value={`${result.optimized_false_alarm_rate || 0}%`} color="text-green-600" />
            <StatCard label="复判工时" value={`${result.operator_review_time_min || 0}min`} />
            <StatCard label="节省工时" value={`${result.review_time_saved_min || 0}min`} color="text-green-600" />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.line_name} · {result.product}</p>
            <p className="text-xs text-gray-500 mt-1">总检测{result.total_inspections} · 呼叫{result.total_calls} · 真缺陷{result.true_defects} · 误报{result.false_alarms}</p>
          </div>
        </div>
      ),
    },
    {
      label: '缺陷分类',
      content: (
        <div className="space-y-2">
          {(result.defect_categories || []).map((c: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium text-gray-900">{c.type}</p>
                <span className="text-sm font-medium text-red-600">{c.false_alarm_rate}%</span>
              </div>
              <p className="text-xs text-gray-500">呼叫{c.total_calls} · 真缺陷{c.true_defects} · 误报{c.false_alarms} · 位置: {c.common_location}</p>
              <p className="text-xs text-gray-600 mt-1">根因: {c.root_cause}</p>
              <p className="text-xs text-blue-600 mt-1">建议: {c.threshold_suggestion}</p>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getIPCTabs(result: any) {
  const j = result.judgment || {};
  return [
    {
      label: '判定结果',
      content: (
        <div className="space-y-3">
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm font-medium text-gray-900 mb-2">{j.defect_type || '缺陷判定'}</p>
            <p className="text-sm text-gray-700">{j.explanation || ''}</p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Class 1 (通用)</p>
              <p className="text-sm font-medium text-gray-900">{j.class_1_limit || 'N/A'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Class 2 (专用)</p>
              <p className="text-sm font-medium text-gray-900">{j.class_2_limit || 'N/A'}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Class 3 (高性能)</p>
              <p className="text-sm font-medium text-gray-900">{j.class_3_limit || 'N/A'}</p>
            </div>
          </div>
          {j.inspection_method && (
            <div className="bg-blue-50 rounded-lg p-3">
              <p className="text-xs text-blue-700">检验方法: {j.inspection_method}</p>
            </div>
          )}
        </div>
      ),
    },
    {
      label: '标准信息',
      content: (
        <div className="space-y-2">
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm font-medium text-gray-900">{result.standard_name}</p>
            <p className="text-xs text-gray-500">{result.standard_version} · {result.matched_category}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">可查询标准</p>
            {Object.entries(result.standards_available || {}).map(([k, v]) => (
              <p key={k} className="text-xs text-gray-700">{k}: {v as string}</p>
            ))}
          </div>
        </div>
      ),
    },
  ];
}

function getAPSTabs(result: any) {
  return [
    {
      label: '排程总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="产能负荷" value={`${result.avg_utilization || 0}%`} color={(result.avg_utilization || 0) >= 85 ? 'text-red-600' : 'text-green-600'} />
            <StatCard label="交期准时率" value={`${result.on_time_rate || 0}%`} color={(result.on_time_rate || 0) >= 90 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="瓶颈" value={result.bottleneck_wc?.slice(-3) || ''} color="text-red-600" />
            <StatCard label="交期风险" value={result.at_risk_count || 0} color="text-red-600" />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '工单',
      content: (
        <div className="space-y-2">
          {(result.orders || []).map((o: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-900">{o.order_id} · {o.product}</p>
                <p className="text-xs text-gray-500">交期 {o.due} · 数量 {o.qty?.toLocaleString()}</p>
              </div>
              <div className="text-right">
                <Badge status={o.slack_days < 0 ? 'critical' : o.slack_days <= 1 ? 'high' : 'low'}>
                  {o.slack_days < 0 ? '逾期' : `缓冲${o.slack_days}天`}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '产能负荷',
      content: (
        <div className="space-y-2">
          {(result.work_centers || []).map((w: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{w.name}</p>
                <Badge status={w.status}>{w.utilization}%</Badge>
              </div>
              <div className="text-xs text-gray-500">负荷 {w.load_h}h / 产能 {w.capacity_h}h</div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getEnergyTabs(result: any) {
  return [
    {
      label: '碳概览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="周能耗" value={`${((result.total_energy_kwh || 0) / 1000).toFixed(0)}MWh`} />
            <StatCard label="碳排放" value={`${result.total_carbon_t || 0}t`} color="text-red-600" />
            <StatCard label="绿电比例" value={`${result.green_ratio || 0}%`} color={(result.green_ratio || 0) >= 30 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="降碳潜力" value={`${result.total_saving_co2_t || 0}t`} color="text-green-600" />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '产线能耗',
      content: (
        <div className="space-y-2">
          {(result.lines || []).map((l: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{l.name}</p>
                <Badge status={l.status}>{l.green_ratio}%绿电</Badge>
              </div>
              <div className="text-xs text-gray-500">能耗 {l.energy_kwh?.toLocaleString()} kWh · 碳排 {l.carbon_t}t</div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '降碳机会',
      content: (
        <div className="space-y-2">
          {(result.opportunities || []).map((op: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-900">{op.measure}</p>
                <span className="text-xs text-green-700 font-medium">回收 {op.payback_yr}年</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                投资 {op.cost_wan} 万 · 节电 {op.saving_kwh?.toLocaleString() || 0} kWh{op.saving_co2_t ? ` · 降碳 ${op.saving_co2_t}t` : ''}
              </p>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getCostTabs(result: any) {
  return [
    {
      label: '成本总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="平均单位成本" value={`¥${result.avg_unit_cost || 0}`} />
            <StatCard label="平均毛利率" value={`${result.avg_margin_pct || 0}%`} color={(result.avg_margin_pct || 0) >= 25 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="超目标" value={result.over_target_count || 0} color="text-red-600" />
            <StatCard label="降本空间" value={`¥${result.total_saving_per_unit || 0}`} color="text-green-600" />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '成本拆解',
      content: (
        <div className="space-y-2">
          {(result.breakdown || []).map((b: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-900">{b.category}</p>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">¥{b.amount}</p>
                <p className="text-xs text-gray-400">{b.pct}%</p>
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '产品成本',
      content: (
        <div className="space-y-2">
          {(result.products || []).map((p: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{p.name}</p>
                <Badge status={p.variance > 0 ? 'warning' : 'pass'}>毛利{p.margin_pct}%</Badge>
              </div>
              <div className="text-xs text-gray-500">
                单位成本 ¥{p.unit_cost}（目标 ¥{p.target_cost} · {p.variance > 0 ? `超 ${p.variance}` : '达标'}）
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '降本机会',
      content: (
        <div className="space-y-2">
          {(result.saving_opportunities || []).map((s: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-900">{s.measure}</p>
              <div className="text-right">
                <p className="text-sm font-medium text-green-700">¥{s.saving_per_unit}/片</p>
                <p className="text-xs text-gray-400">置信度{Math.round((s.confidence || 0) * 100)}%</p>
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getDemandTabs(result: any) {
  return [
    {
      label: '需求总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="本季需求" value={`${result.total_forecast || 0}万片`} />
            <StatCard label="已接订单" value={`${result.total_booked || 0}万片`} />
            <StatCard label="未交付" value={`${result.total_backlog || 0}万片`} color={(result.total_backlog || 0) > 30 ? 'text-red-600' : 'text-amber-600'} />
            <StatCard label="满足率" value={`${result.avg_fill_rate || 0}%`} color={(result.avg_fill_rate || 0) >= 90 ? 'text-green-600' : 'text-red-600'} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '产品需求',
      content: (
        <div className="space-y-2">
          {(result.demand_items || []).map((d: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{d.name}</p>
                <Badge status={d.at_risk ? 'critical' : 'low'}>{d.fill_rate}%</Badge>
              </div>
              <div className="text-xs text-gray-500">
                需求 {d.forecast} · 已接 {d.booked} · 未交付 {d.backlog} 万片
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '交期风险',
      content: (
        <div className="space-y-2">
          {(result.demand_items || []).filter((d: any) => d.at_risk).map((d: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-900">{d.name}</p>
              <div className="text-right">
                <p className="text-sm font-medium text-red-600">未交付 {d.backlog} 万片</p>
                <p className="text-xs text-gray-400">满足率 {d.fill_rate}%</p>
              </div>
            </div>
          ))}
          {(result.at_risk_count || 0) === 0 && (
            <p className="text-sm text-gray-500 p-2.5 bg-gray-50 rounded-lg">✅ 全部产品满足率在红线之上</p>
          )}
        </div>
      ),
    },
  ];
}

function getWmsTabs(result: any) {
  return [
    {
      label: '库存总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="库存总额" value={`${result.total_stock_value_wan || 0}万`} />
            <StatCard label="加权周转" value={`${result.turnover || 0}次`} />
            <StatCard label="呆滞占比" value={`${result.obsolete_pct || 0}%`} color={(result.obsolete_pct || 0) > 5 ? 'text-amber-600' : 'text-green-600'} />
            <StatCard label="物流准时" value={`${result.on_time_rate || 0}%`} color={(result.on_time_rate || 0) >= 90 ? 'text-green-600' : 'text-red-600'} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '库存明细',
      content: (
        <div className="space-y-2">
          {(result.inventory || []).map((m: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{m.name} <span className="text-xs text-gray-400">· {m.abc}类</span></p>
                <Badge status={m.below_safety ? 'critical' : 'low'}>{m.below_safety ? '低于安全' : '达标'}</Badge>
              </div>
              <div className="text-xs text-gray-500">
                库存 {m.stock_value_wan} 万（安全 {m.safety_wan} 万）· 周转 {m.turnover} 次 · 呆滞 {m.obsolete_wan} 万
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '物流时效',
      content: (
        <div className="space-y-2">
          {(result.logistics || []).map((r: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-900">{r.route}</p>
              <div className="text-right">
                <Badge status={r.status === 'ok' ? 'pass' : r.status === 'delay' ? 'critical' : 'high'}>{r.lead_time}天/{r.on_time_rate}%</Badge>
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getComplianceTabs(result: any) {
  return [
    {
      label: '合规概览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="有效认证" value={result.valid_certs || 0} />
            <StatCard label="进行中" value={result.in_progress_certs || 0} color="text-amber-600" />
            <StatCard label="未关闭发现" value={result.open_findings || 0} color={(result.open_findings || 0) > 0 ? 'text-red-600' : 'text-green-600'} />
            <StatCard label="法规合规率" value={`${result.compliant_regs || 0}/${result.total_regulations || 0}`} color={(result.compliant_regs || 0) === (result.total_regulations || 0) ? 'text-green-600' : 'text-amber-600'} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '认证状态',
      content: (
        <div className="space-y-2">
          {(result.certifications || []).map((c: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{c.name} <span className="text-xs text-gray-400">· {c.body}</span></p>
                <Badge status={c.status === 'valid' ? 'pass' : 'warning'}>{c.status === 'valid' ? `有效至${c.expiry}` : `${c.progress_pct}%`}</Badge>
              </div>
              {c.status === 'valid' && <div className="text-xs text-gray-500">最近审核 {c.last_audit}</div>}
              {c.status !== 'valid' && <div className="text-xs text-gray-500">目标 {c.target_date}，进度 {c.progress_pct}%</div>}
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '审核发现',
      content: (
        <div className="space-y-2">
          {(result.audits || []).map((a: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <div className="flex-1">
                <p className="text-sm text-gray-900">{a.finding_id} · {a.title}</p>
                <p className="text-xs text-gray-500">{a.severity} · {a.owner} · 到期 {a.due}</p>
              </div>
              <Badge status={a.status === 'open' ? 'critical' : a.status === 'in_progress' ? 'high' : 'pass'}>{a.status}</Badge>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getExecutiveTabs(result: any) {
  return [
    {
      label: '经营总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="季度营收" value={`${result.revenue_quarter || 0}万`} />
            <StatCard label="毛利率" value={`${result.gross_margin_pct || 0}%`} color={(result.gross_margin_pct || 0) >= 30 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="净利率" value={`${result.net_margin_pct || 0}%`} />
            <StatCard label="现金流" value={`${result.cash_position || 0}万`} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '产出',
      content: (
        <div className="space-y-2">
          <div className="grid grid-cols-4 gap-3 mb-3">
            <StatCard label="产出完成率" value={`${result.prod_completion_pct || 0}%`} color={(result.prod_completion_pct || 0) >= 95 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="超预算部门" value={result.overspend_depts || 0} color={(result.overspend_depts || 0) > 0 ? 'text-red-600' : 'text-green-600'} />
            <StatCard label="订单未交付" value={`${result.order_backlog_value || 0}万`} color="text-amber-600" />
            <StatCard label="现金可支撑" value={`${result.days_of_cash || 0}天`} />
          </div>
          {(result.production?.by_product || []).map((p: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-900">{p.product}</p>
              <div className="text-right">
                <p className={`text-sm font-medium ${(p.actual / p.plan) >= 0.95 ? 'text-green-700' : 'text-amber-700'}`}>{p.actual}/{p.plan}万片</p>
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      label: '预算执行',
      content: (
        <div className="space-y-2">
          {(result.budgets || []).map((b: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-900">{b.dept}</p>
              <div className="text-right">
                <Badge status={b.status === 'overspend' ? 'critical' : b.status === 'underspend' ? 'pass' : 'low'}>{b.util_pct}%</Badge>
                <p className="text-xs text-gray-400 mt-0.5">{b.actual}/{b.plan}万 · {b.variance > 0 ? `超${b.variance}` : `省${Math.abs(b.variance)}`}万</p>
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getNpiTabs(result: any) {
  return [
    {
      label: '项目总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="NPI项目" value={result.total_projects || 0} />
            <StatCard label="覆盖阶段" value={`${result.stage_coverage || 0}个`} />
            <StatCard label="按时项目" value={result.on_schedule_count || 0} color="text-green-600" />
            <StatCard label="高风险" value={result.high_risk_count || 0} color={(result.high_risk_count || 0) > 0 ? 'text-red-600' : 'text-green-600'} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '项目明细',
      content: (
        <div className="space-y-2">
          {(result.projects || []).map((p: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{p.name} <span className="text-xs text-gray-400">· {p.owner}</span></p>
                <Badge status={p.on_schedule ? 'pass' : 'critical'}>{p.stage} · {p.milestone_pct}%</Badge>
              </div>
              <div className="text-xs text-gray-500">
                ID {p.id} · ETA {p.eta}{p.risk === 'high' ? ` · 🚨 ${p.risk_note}` : ''}
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}

function getProcurementTabs(result: any) {
  return [
    {
      label: '采购总览',
      content: (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="供应商" value={result.supplier_count || 0} />
            <StatCard label="平均评分" value={result.avg_score || 0} color={(result.avg_score || 0) >= 80 ? 'text-green-600' : 'text-amber-600'} />
            <StatCard label="低绩效" value={result.low_performer_count || 0} color={(result.low_performer_count || 0) > 0 ? 'text-red-600' : 'text-green-600'} />
            <StatCard label="合同总额" value={`${result.total_contract_value_wan || 0}万`} />
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm text-gray-700">{result.summary}</p>
          </div>
        </div>
      ),
    },
    {
      label: '供应商绩效',
      content: (
        <div className="space-y-2">
          {(result.suppliers || []).map((s: any, i: number) => (
            <div key={i} className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-900">{s.name} <span className="text-xs text-gray-400">· {s.category} · {s.tier}级</span></p>
                <Badge status={s.score >= 80 ? 'pass' : s.score >= 70 ? 'warning' : 'critical'}>{s.score}</Badge>
              </div>
              <div className="text-xs text-gray-500">
                交期{s.delivery} 质量{s.quality} 成本{s.cost} 合规{s.compliance} · 合同至{s.contract_end}
              </div>
            </div>
          ))}
        </div>
      ),
    },
  ];
}
