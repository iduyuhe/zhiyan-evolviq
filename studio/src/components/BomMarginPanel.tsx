/**
 * BOM 上传 × 行情毛利影响面板（S2-5，#311）
 *
 * 信任爬梯③价值跳变样板：上传 1 份 BOM（不接系统、不进内网）→
 * 平台立即用第⑥路行情信号测算「原材料涨价对物料成本/毛利的影响」，
 * 同时解锁中圈 4 个交叉 agent + 免除免费额度。
 *
 * 纪律：先测试后保存（预览闸门）；F4 不推销——解锁提示为事实呈现。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BomItem, BomRecord, MarginImpactView,
  deleteBom, getBomMarginImpact, listBoms, previewBom, uploadBom,
} from '../api/client';

function extractDetail(raw: string): string {
  try {
    const j = JSON.parse(raw);
    return j.detail || raw;
  } catch {
    return raw;
  }
}

const SAMPLE_CSV = `material,qty,unit_price
电解铜,2.5,68.0
铝锭,1.2,19.5
CAP-001,120,0.05
PCB基板,1,42.0`;

function DeltaBadge({ pct }: { pct: number }) {
  const up = pct > 0;
  const cls = up ? 'bg-red-50 text-red-600' : pct < 0 ? 'bg-green-50 text-green-600' : 'bg-gray-50 text-gray-500';
  return (
    <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-medium ${cls}`}>
      {pct > 0 ? '+' : ''}{pct}%
    </span>
  );
}

function ImpactView({ impact }: { impact: MarginImpactView }) {
  const up = impact.cost_delta_total > 0;
  return (
    <div className="border border-zhiyan-100 bg-zhiyan-50/40 rounded-lg p-3 space-y-2">
      <div className="text-sm font-medium text-gray-800">
        📈 {impact.product_name} · 行情影响测算
      </div>
      <div className="text-sm text-gray-700">{impact.summary}</div>
      {impact.impacts.length > 0 && (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-400 text-left">
              <th className="py-1 font-normal">物料</th>
              <th className="py-1 font-normal">命中行情</th>
              <th className="py-1 font-normal">成本占比</th>
              <th className="py-1 font-normal">价格变动</th>
              <th className="py-1 font-normal text-right">成本影响(元)</th>
            </tr>
          </thead>
          <tbody>
            {impact.impacts.map((it, i) => (
              <tr key={i} className="border-t border-gray-100 text-gray-700">
                <td className="py-1">{it.material}</td>
                <td className="py-1 text-gray-500">{it.signal_title}</td>
                <td className="py-1">{it.cost_share_pct}%</td>
                <td className="py-1"><DeltaBadge pct={it.price_change_pct ?? 0} /></td>
                <td className={`py-1 text-right font-medium ${(it.cost_delta ?? 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {(it.cost_delta ?? 0) > 0 ? '+' : ''}{it.cost_delta}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {impact.impacts.length > 0 && (
        <div className={`text-sm font-semibold ${up ? 'text-red-600' : 'text-green-600'}`}>
          合计物料成本变动：{impact.cost_delta_total > 0 ? '+' : ''}{impact.cost_delta_total} 元
          （{impact.cost_delta_pct > 0 ? '+' : ''}{impact.cost_delta_pct}%）
        </div>
      )}
      {impact.watchlist.length > 0 && (
        <div className="text-xs text-amber-600">
          ⚠️ 关注清单（行情提及但暂无量化数字）：
          {impact.watchlist.map((w) => w.material).join('、')}
        </div>
      )}
      <div className="text-[11px] text-gray-400">
        基于 {impact.signals_scanned} 条环境行情信号 · 仅使用信号中出现的官方数字，不做外推
      </div>
    </div>
  );
}

export default function BomMarginPanel() {
  const [boms, setBoms] = useState<BomRecord[]>([]);
  const [content, setContent] = useState('');
  const [filename, setFilename] = useState('');
  const [productName, setProductName] = useState('');
  const [preview, setPreview] = useState<{ item_count: number; total_material_cost: number; items: BomItem[]; truncated: boolean } | null>(null);
  const [impact, setImpact] = useState<MarginImpactView | null>(null);
  const [unlocked, setUnlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await listBoms();
      setBoms(r.boms);
    } catch { /* 未登录/降级时静默 */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const onFile = (f: File | null) => {
    if (!f) return;
    setFilename(f.name);
    const reader = new FileReader();
    reader.onload = () => {
      setContent(String(reader.result || ''));
      setPreview(null);
      setMsg('');
    };
    reader.readAsText(f);
  };

  const onPreview = async () => {
    setBusy(true); setMsg(''); setPreview(null);
    try {
      const p = await previewBom(filename || 'bom.csv', content);
      setPreview(p);
      setMsg(`✅ 解析通过：${p.item_count} 行，物料成本合计 ¥${p.total_material_cost}`);
    } catch (e) {
      setMsg('❌ ' + extractDetail((e as Error).message));
    } finally { setBusy(false); }
  };

  const onUpload = async () => {
    setBusy(true); setMsg('');
    try {
      const r = await uploadBom(filename || 'bom.csv', content, productName);
      setImpact(r.margin_impact);
      setUnlocked(r.current_circle !== 'outer');
      setMsg('✅ BOM 已上传');
      setContent(''); setFilename(''); setProductName(''); setPreview(null);
      if (fileRef.current) fileRef.current.value = '';
      refresh();
    } catch (e) {
      setMsg('❌ ' + extractDetail((e as Error).message));
    } finally { setBusy(false); }
  };

  const onRecalc = async (id: string) => {
    setBusy(true); setMsg('');
    try {
      setImpact(await getBomMarginImpact(id));
    } catch (e) {
      setMsg('测算失败：' + extractDetail((e as Error).message));
    } finally { setBusy(false); }
  };

  const onDelete = async (id: string) => {
    setBusy(true);
    try {
      await deleteBom(id);
      if (impact?.bom_id === id) setImpact(null);
      refresh();
    } catch (e) {
      setMsg('删除失败：' + extractDetail((e as Error).message));
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-800">📄 BOM × 行情 · 毛利影响测算</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            上传 1 份物料清单（CSV/JSON，不接系统、不进内网）→ 行情信号自动测算成本影响，
            同时解锁中圈 4 个交叉分析 agent 并免除免费额度
          </p>
        </div>
        {unlocked && (
          <span className="text-[11px] px-2 py-1 rounded-full bg-zhiyan-50 text-zhiyan-700 font-medium">
            🔓 中圈已解锁
          </span>
        )}
      </div>

      {/* 上传区 */}
      <div className="border border-dashed border-gray-200 rounded-lg p-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.json,.txt"
            className="text-xs text-gray-500"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
          <button
            className="text-xs text-zhiyan-600 hover:underline"
            onClick={() => { setContent(SAMPLE_CSV); setFilename('演示BOM.csv'); setPreview(null); setMsg(''); }}
          >
            填入演示样例
          </button>
          <input
            className="border border-gray-200 rounded-lg px-2 py-1 text-xs text-gray-700 w-40"
            placeholder="产品名（可选）"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
          />
        </div>
        <textarea
          className="w-full border border-gray-200 rounded-lg p-2 text-xs font-mono text-gray-700 h-24"
          placeholder={'也可直接粘贴 CSV 文本，表头示例：\nmaterial,qty,unit_price（或 物料,数量,单价）'}
          value={content}
          onChange={(e) => { setContent(e.target.value); setPreview(null); }}
        />
        <div className="flex items-center gap-2">
          <button
            disabled={busy || !content.trim()}
            onClick={onPreview}
            className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            {busy ? '…' : '① 解析预览'}
          </button>
          <button
            disabled={busy || !preview}
            onClick={onUpload}
            className="px-3 py-1.5 text-xs rounded-lg bg-zhiyan-600 text-white hover:bg-zhiyan-700 disabled:opacity-40"
            title={preview ? '' : '先通过解析预览（先测试后保存）'}
          >
            ② 上传并测算
          </button>
          {msg && <span className="text-xs text-gray-600">{msg}</span>}
        </div>
        {preview && (
          <div className="text-xs text-gray-500">
            预览：{preview.items.slice(0, 6).map((it) => `${it.material}×${it.qty}`).join('，')}
            {preview.truncated || preview.items.length > 6 ? ' …' : ''}
          </div>
        )}
      </div>

      {/* 测算结果 */}
      {impact && <ImpactView impact={impact} />}

      {/* 已上传清单 */}
      {boms.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs text-gray-400">已上传 BOM（{boms.length}）</div>
          {boms.map((b) => (
            <div key={b.id} className="flex items-center justify-between border border-gray-100 rounded-lg px-3 py-1.5 text-xs">
              <span className="text-gray-700">
                {b.product_name || b.filename}
                <span className="text-gray-400 ml-2">{b.item_count} 行 · ¥{b.total_material_cost}</span>
              </span>
              <span className="flex gap-2">
                <button className="text-zhiyan-600 hover:underline" disabled={busy} onClick={() => onRecalc(b.id)}>重新测算</button>
                <button className="text-gray-400 hover:text-red-500" disabled={busy} onClick={() => onDelete(b.id)}>删除</button>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
