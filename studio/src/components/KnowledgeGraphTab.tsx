import { useEffect, useMemo, useState } from 'react';
import {
  getKgStats,
  queryKg,
  rebuildKg,
  type KgStats,
  type KgNode,
  type KgNeighbor,
} from '../api/client';

const NODE_LABELS = [
  'Material', 'Equipment', 'Product', 'DefectCase', 'Line', 'Part',
  'PO', 'Component', 'Standard', 'ECOCase', 'YieldRecord',
];

const tabBtn = (active: boolean) =>
  `px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
    active ? 'bg-zhiyan-500 text-white shadow-sm' : 'bg-gray-100 text-gray-500 hover:text-gray-700'
  }`;

const inputCls =
  'border border-gray-200 rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-zhiyan-400';

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <div className="text-2xl font-bold text-zhiyan-600">{value}</div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  );
}

// ---------- 轻量力导向布局（无第三方依赖） ----------
interface GNode { id: string; center?: boolean; }
interface GEdge { source: string; target: string; label: string; }

function computeForceLayout(
  rawNodes: GNode[],
  edges: GEdge[],
  width: number,
  height: number,
): Record<string, { x: number; y: number }> {
  const pos: Record<string, { x: number; y: number }> = {};
  const n = rawNodes.length || 1;
  const radius = Math.min(width, height) / 3;
  rawNodes.forEach((nd, i) => {
    const angle = (2 * Math.PI * i) / n;
    pos[nd.id] = {
      x: width / 2 + radius * Math.cos(angle),
      y: height / 2 + radius * Math.sin(angle),
    };
  });
  const k = 0.04; // 弹簧刚度
  const repulse = 9000; // 斥力常数
  const center = { x: width / 2, y: height / 2 };
  for (let it = 0; it < 300; it++) {
    const disp: Record<string, { x: number; y: number }> = {};
    for (const nd of rawNodes) disp[nd.id] = { x: 0, y: 0 };
    // 节点间斥力
    for (let i = 0; i < rawNodes.length; i++) {
      for (let j = i + 1; j < rawNodes.length; j++) {
        const a = pos[rawNodes[i].id], b = pos[rawNodes[j].id];
        let dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const force = repulse / (dist * dist);
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        disp[rawNodes[i].id].x += fx; disp[rawNodes[i].id].y += fy;
        disp[rawNodes[j].id].x -= fx; disp[rawNodes[j].id].y -= fy;
      }
    }
    // 边弹簧
    for (const e of edges) {
      const a = pos[e.source], b = pos[e.target];
      let dx = a.x - b.x, dy = a.y - b.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const force = k * (dist - 120);
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      disp[e.source].x -= fx; disp[e.source].y -= fy;
      disp[e.target].x += fx; disp[e.target].y += fy;
    }
    // 向心 + 限步
    for (const nd of rawNodes) {
      const p = pos[nd.id];
      disp[nd.id].x += (center.x - p.x) * 0.02;
      disp[nd.id].y += (center.y - p.y) * 0.02;
      const d = disp[nd.id];
      const step = Math.sqrt(d.x * d.x + d.y * d.y);
      if (step > 20) { d.x = (d.x / step) * 20; d.y = (d.y / step) * 20; }
      pos[nd.id] = { x: p.x + d.x, y: p.y + d.y };
    }
  }
  return pos;
}

function shortId(id: string): string {
  const idx = id.indexOf(':');
  return idx >= 0 ? id.slice(idx + 1) : id;
}

function GraphView({ centerId, neighbors }: { centerId: string; neighbors: KgNeighbor[] }) {
  const W = 640, H = 380;
  const graph = useMemo(() => {
    const nodes: GNode[] = [{ id: centerId, center: true }];
    const edges: GEdge[] = [];
    for (const nb of neighbors) {
      nodes.push({ id: nb.id });
      edges.push({ source: centerId, target: nb.id, label: nb.edge_type });
    }
    const pos = computeForceLayout(nodes, edges, W, H);
    return { nodes, edges, pos };
  }, [centerId, neighbors]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto bg-gray-50 rounded-lg">
      {/* 边 */}
      {graph.edges.map((e, i) => {
        const a = graph.pos[e.source], b = graph.pos[e.target];
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        return (
          <g key={`e${i}`}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#cbd5e1" strokeWidth={1.5} />
            <text x={mx} y={my - 4} fontSize={10} fill="#64748b" textAnchor="middle">{e.label}</text>
          </g>
        );
      })}
      {/* 节点 */}
      {graph.nodes.map((nd) => {
        const p = graph.pos[nd.id];
        const isCenter = nd.center;
        return (
          <g key={nd.id}>
            <circle
              cx={p.x} cy={p.y} r={isCenter ? 22 : 16}
              fill={isCenter ? '#2563eb' : '#e0e7ff'}
              stroke={isCenter ? '#1d4ed8' : '#a5b4fc'}
              strokeWidth={1.5}
            />
            <text
              x={p.x} y={p.y + (isCenter ? 4 : 3)} fontSize={isCenter ? 11 : 9}
              fill={isCenter ? '#ffffff' : '#3730a3'} textAnchor="middle"
              style={{ pointerEvents: 'none' }}
            >
              {shortId(nd.id).slice(0, 10)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function KnowledgeGraphTab() {
  const [stats, setStats] = useState<KgStats | null>(null);
  const [mode, setMode] = useState<'list' | 'neighbors'>('list');
  const [label, setLabel] = useState('Material');
  const [category, setCategory] = useState('');
  const [nodeId, setNodeId] = useState('CASE:CASE-2026-001');
  const [edge, setEdge] = useState('');
  const [nodes, setNodes] = useState<KgNode[]>([]);
  const [neighbors, setNeighbors] = useState<KgNeighbor[]>([]);
  const [showGraph, setShowGraph] = useState(false);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  const loadStats = async () => {
    try {
      setStats(await getKgStats());
    } catch (e) {
      setMsg(String(e));
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const doQuery = async () => {
    setLoading(true);
    setMsg('');
    try {
      if (mode === 'list') {
        const r = await queryKg({ label, category: category || undefined });
        setNodes(r.nodes || []);
        setNeighbors([]);
        setShowGraph(false);
      } else {
        const r = await queryKg({ node_id: nodeId, edge: edge || undefined });
        setNeighbors(r.neighbors || []);
        setNodes([]);
        setShowGraph(true);
      }
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  };

  const doRebuild = async () => {
    setLoading(true);
    try {
      const r = await rebuildKg();
      setStats(r.stats);
      setMsg(`已重建：${r.stats.total_nodes} 节点 / ${r.stats.total_edges} 边`);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  };

  const examples = [
    { name: '质量案例→设备（跨Agent）', node_id: 'CASE:CASE-2026-001', edge: '怀疑设备' },
    { name: '设备→部件', node_id: 'EQP:scanner_1', edge: '有部件' },
    { name: '产线联邦(OEE/SMT/AOI)', node_id: 'LINE:SMT-L01', edge: '' },
  ];

  return (
    <div className="space-y-4">
      {/* 标题 + 重建 */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <span>🕸️</span> 跨 Agent 知识图谱
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              11 个 Agent 的工业语义网 · 存储模式：
              <span
                className={`ml-1 px-1.5 py-0.5 rounded text-[10px] ${
                  stats?.mode === 'neo4j' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                }`}
              >
                {stats?.mode || '—'}
              </span>
            </p>
          </div>
          <button
            onClick={doRebuild}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-zhiyan-500 text-white hover:bg-zhiyan-600 disabled:opacity-50"
          >
            重建图谱
          </button>
        </div>

        {stats && (
          <div className="grid grid-cols-3 gap-3 mt-4">
            <StatCard label="节点总数" value={stats.total_nodes} />
            <StatCard label="关系总数" value={stats.total_edges} />
            <StatCard label="实体类型" value={Object.keys(stats.nodes_by_label).length} />
          </div>
        )}
        {msg && <p className="text-xs text-gray-500 mt-2">{msg}</p>}
      </div>

      {/* 查询区 */}
      <div className="card space-y-3">
        <div className="flex gap-2">
          <button onClick={() => setMode('list')} className={tabBtn(mode === 'list')}>
            按类型列节点
          </button>
          <button onClick={() => setMode('neighbors')} className={tabBtn(mode === 'neighbors')}>
            查节点邻居
          </button>
        </div>

        {mode === 'list' ? (
          <div className="flex gap-2 flex-wrap items-center">
            <select value={label} onChange={(e) => setLabel(e.target.value)} className={inputCls}>
              {NODE_LABELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
            <input
              placeholder="category 过滤（可选）"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={`${inputCls} flex-1`}
            />
            <button
              onClick={doQuery}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-zhiyan-500 text-white hover:bg-zhiyan-600 disabled:opacity-50"
            >
              查询
            </button>
          </div>
        ) : (
          <div className="flex gap-2 flex-wrap items-center">
            <input
              placeholder="节点 id，如 CASE:CASE-2026-001"
              value={nodeId}
              onChange={(e) => setNodeId(e.target.value)}
              className={`${inputCls} flex-1`}
            />
            <input
              placeholder="关系（可选），如有部件"
              value={edge}
              onChange={(e) => setEdge(e.target.value)}
              className={`${inputCls} w-44`}
            />
            <button
              onClick={doQuery}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-zhiyan-500 text-white hover:bg-zhiyan-600 disabled:opacity-50"
            >
              查询
            </button>
          </div>
        )}

        {/* 跨 Agent 桥接示例 */}
        <div className="flex gap-2 flex-wrap">
          {examples.map((ex) => (
            <button
              key={ex.name}
              onClick={() => {
                setMode('neighbors');
                setNodeId(ex.node_id);
                setEdge(ex.edge);
                setShowGraph(true);
                setTimeout(doQuery, 0);
              }}
              className="px-2 py-1 text-[11px] rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
            >
              {ex.name}
            </button>
          ))}
        </div>
      </div>

      {/* 节点结果 */}
      {nodes.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-medium text-gray-700 mb-2">节点（{nodes.length}）</h3>
          <div className="space-y-1 max-h-80 overflow-auto">
            {nodes.map((n) => (
              <div key={n.id} className="text-xs border-b border-gray-100 py-1.5">
                <span className="font-mono text-zhiyan-600">{n.id}</span>
                <span className="text-gray-400 ml-2">{n.labels.join(',')}</span>
                <div className="text-gray-500 mt-0.5">
                  {Object.entries(n.props)
                    .slice(0, 4)
                    .map(([k, v]) => `${k}=${String(v)}`)
                    .join(' · ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 邻居结果 + 力导向图 */}
      {neighbors.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-700">邻居（{neighbors.length}）</h3>
            <button
              onClick={() => setShowGraph((v) => !v)}
              className="px-2 py-1 text-[11px] rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
            >
              {showGraph ? '隐藏力导向图' : '显示力导向图'}
            </button>
          </div>
          <div className="space-y-1 max-h-60 overflow-auto mb-3">
            {neighbors.map((n) => (
              <div key={n.id} className="text-xs border-b border-gray-100 py-1.5">
                <span className="inline-block px-1.5 py-0.5 rounded bg-zhiyan-50 text-zhiyan-600 text-[10px] mr-2">
                  {n.edge_type}
                </span>
                <span className="font-mono text-gray-800">{n.id}</span>
                <span className="text-gray-400 ml-2">{n.labels.join(',')}</span>
              </div>
            ))}
          </div>
          {showGraph && <GraphView centerId={nodeId} neighbors={neighbors} />}
        </div>
      )}
    </div>
  );
}
