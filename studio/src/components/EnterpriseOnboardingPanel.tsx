import { useState, useEffect, useCallback } from 'react';
import {
  getEnterpriseProfile,
  saveEnterpriseProfile,
  listEnterpriseCredentials,
  storeEnterpriseCredential,
  deleteEnterpriseCredential,
  getOnboardingRecommendations,
  EnterpriseProfile,
  CredentialRef,
  OnboardingRecommendation,
} from '../api/client';

const INDUSTRIES = ['半导体', '3C', '新能源汽车', '通讯', '光伏', '工程机械', '其他'];
const ERP_OPTIONS = ['无', '用友', '金蝶', 'SAP', 'Oracle', '自研'];
const MES_OPTIONS = ['无', '自有', '第三方'];
const GATEWAY_OPTIONS = ['OPC-UA', 'Modbus', 'AMQP', 'MQTT'];
const SOCIAL_OPTIONS = ['企业微信', '钉钉', '邮件'];
const INTENT_OPTIONS = ['暂不', '评估后', '现在就开'];
const CRED_KINDS = ['erp_writeback', 'gateway_opcua', 'social_wecom', 'social_dingtalk', 'email_imap'];
const ORG_SCALES = ['<50', '50-200', '200-1000', '1000+'];

const CIRCLE_LABEL: Record<string, string> = { outer: '外圈·免费', middle: '中圈·付费线', inner: '内圈·私有化' };
const CIRCLE_STYLE: Record<string, string> = {
  outer: 'bg-green-100 text-green-700',
  middle: 'bg-blue-100 text-blue-700',
  inner: 'bg-purple-100 text-purple-700',
};

function emptyProfile(): EnterpriseProfile {
  return {
    industry: '通讯',
    region: '',
    legal_entities: [],
    org_scale: '',
    revenue_band: '',
    systems: { erp: '无', mes: '无', gateway: [], social: [], knowledge_base: false },
    intent: { free_tier_ok: true, internal_connect: '暂不', concerns: '' },
    narrative: '',
  };
}

export default function EnterpriseOnboardingPanel() {
  const [profile, setProfile] = useState<EnterpriseProfile>(emptyProfile());
  const [exists, setExists] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const [refs, setRefs] = useState<CredentialRef[]>([]);
  const [credKind, setCredKind] = useState('erp_writeback');
  const [credJson, setCredJson] = useState('');
  const [credMsg, setCredMsg] = useState('');
  const [credSaving, setCredSaving] = useState(false);

  const [rec, setRec] = useState<OnboardingRecommendation | null>(null);
  const [recSummary, setRecSummary] = useState('');
  const [recLoading, setRecLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const p = await getEnterpriseProfile();
      if (p.exists && p.profile) {
        setExists(true);
        setProfile({ ...emptyProfile(), ...p.profile, systems: { ...emptyProfile().systems, ...(p.profile.systems || {}) }, intent: { ...emptyProfile().intent, ...(p.profile.intent || {}) } });
      }
    } catch { /* 静默 */ }
    try {
      const c = await listEnterpriseCredentials();
      setRefs(c.refs);
    } catch { /* 静默 */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const toggleList = (list: string[], v: string): string[] =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  const onSave = async () => {
    setSaving(true);
    setMsg('');
    try {
      await saveEnterpriseProfile(profile);
      setExists(true);
      setMsg('✅ 企业现状画像已保存');
    } catch (e) {
      setMsg('保存失败：' + (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const onStoreCred = async () => {
    setCredSaving(true);
    setCredMsg('');
    try {
      let secret: Record<string, string>;
      try {
        secret = JSON.parse(credJson || '{}');
      } catch {
        setCredMsg('凭证须为合法 JSON，如 {"api_key":"..."}');
        setCredSaving(false);
        return;
      }
      await storeEnterpriseCredential(credKind, secret);
      setCredJson('');
      setCredMsg('✅ 凭证已加密入 vault（仅存引用，明文不落库不回显）');
      const c = await listEnterpriseCredentials();
      setRefs(c.refs);
    } catch (e) {
      setCredMsg('入 vault 失败：' + (e as Error).message);
    } finally {
      setCredSaving(false);
    }
  };

  const onDeleteCred = async (vaultId: string) => {
    try {
      await deleteEnterpriseCredential(vaultId);
      setRefs((p) => p.filter((r) => r.vault_id !== vaultId));
    } catch { /* 静默 */ }
  };

  const onRecommend = async () => {
    setRecLoading(true);
    setRec(null);
    setRecSummary('');
    try {
      const r = await getOnboardingRecommendations();
      setRecSummary(r.summary);
      if (r.recommendation) setRec(r.recommendation);
    } catch (e) {
      setRecSummary('推荐生成失败：' + (e as Error).message);
    } finally {
      setRecLoading(false);
    }
  };

  return (
    <section className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-1">企业入驻 · 现状描述与接口实例化</h3>
      <p className="text-xs text-gray-500 mb-3">
        声明式描述企业现状（行业 / 系统清单 / 接入意愿），系统按同行业研究案例自动推荐该开通的集成接口；
        凭证加密入 vault 后即可实例化为客户专属活体实例。
      </p>

      {/* 1. 画像表单（D1 混合形态：结构化 + 自由叙述） */}
      <div className="space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <label className="text-xs text-gray-600">
            行业（必填）
            <select
              className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              value={profile.industry}
              onChange={(e) => setProfile({ ...profile, industry: e.target.value })}
            >
              {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-600">
            区域（省/市）
            <input
              className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              value={profile.region}
              onChange={(e) => setProfile({ ...profile, region: e.target.value })}
            />
          </label>
          <label className="text-xs text-gray-600">
            组织规模
            <select
              className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              value={profile.org_scale}
              onChange={(e) => setProfile({ ...profile, org_scale: e.target.value })}
            >
              <option value="">未选择</option>
              {ORG_SCALES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-600">
            内部系统接入意愿
            <select
              className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              value={profile.intent.internal_connect}
              onChange={(e) => setProfile({ ...profile, intent: { ...profile.intent, internal_connect: e.target.value } })}
            >
              {INTENT_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <label className="text-xs text-gray-600">
            ERP
            <select
              className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              value={profile.systems.erp || '无'}
              onChange={(e) => setProfile({ ...profile, systems: { ...profile.systems, erp: e.target.value } })}
            >
              {ERP_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-600">
            MES
            <select
              className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              value={profile.systems.mes || '无'}
              onChange={(e) => setProfile({ ...profile, systems: { ...profile.systems, mes: e.target.value } })}
            >
              {MES_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap gap-4">
          <div className="text-xs text-gray-600">
            工业网关协议：
            {GATEWAY_OPTIONS.map((g) => (
              <label key={g} className="inline-flex items-center gap-1 ml-2">
                <input
                  type="checkbox"
                  checked={profile.systems.gateway.includes(g)}
                  onChange={() => setProfile({ ...profile, systems: { ...profile.systems, gateway: toggleList(profile.systems.gateway, g) } })}
                />
                {g}
              </label>
            ))}
          </div>
          <div className="text-xs text-gray-600">
            社交通道：
            {SOCIAL_OPTIONS.map((s) => (
              <label key={s} className="inline-flex items-center gap-1 ml-2">
                <input
                  type="checkbox"
                  checked={profile.systems.social.includes(s)}
                  onChange={() => setProfile({ ...profile, systems: { ...profile.systems, social: toggleList(profile.systems.social, s) } })}
                />
                {s}
              </label>
            ))}
          </div>
        </div>

        <label className="block text-xs text-gray-600">
          自由叙述（战略意图 / 痛点 / 组织文化，系统自动抽取补全画像）
          <textarea
            className="mt-1 w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
            rows={2}
            maxLength={2000}
            value={profile.narrative}
            onChange={(e) => setProfile({ ...profile, narrative: e.target.value })}
          />
        </label>

        <div className="flex items-center gap-3">
          <button className="btn-primary text-sm" onClick={onSave} disabled={saving}>
            {saving ? '保存中…' : exists ? '更新画像' : '保存画像'}
          </button>
          {msg && <span className={`text-xs ${msg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>{msg}</span>}
        </div>
      </div>

      {/* 2. 凭证 vault（D2 铁律：加密存储，仅显示引用） */}
      <div className="border-t border-gray-100 mt-4 pt-3 space-y-2">
        <p className="text-xs text-gray-500">
          凭证 Vault（加密存储 · 租户隔离 · 绝不明文落库 / 绝不回显）
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <select
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
            value={credKind}
            onChange={(e) => setCredKind(e.target.value)}
          >
            {CRED_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm flex-1 min-w-[220px]"
            placeholder='凭证 JSON，如 {"api_key":"...","endpoint":"..."}'
            value={credJson}
            onChange={(e) => setCredJson(e.target.value)}
          />
          <button className="btn-secondary text-sm" onClick={onStoreCred} disabled={credSaving}>
            {credSaving ? '加密入库…' : '加密入 Vault'}
          </button>
        </div>
        {credMsg && <p className={`text-xs ${credMsg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>{credMsg}</p>}
        {refs.length > 0 && (
          <div className="space-y-1">
            {refs.map((r) => (
              <div key={r.vault_id} className="flex items-center justify-between text-xs text-gray-600 border-b border-gray-50 pb-1">
                <span>
                  <span className="font-medium">{r.kind}</span>
                  <span className="text-gray-400 ml-2">{r.vault_id.slice(0, 8)}…</span>
                </span>
                <button className="text-red-500 hover:underline" onClick={() => onDeleteCred(r.vault_id)}>删除</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. 接口推荐三态清单（D3：案例库驱动） */}
      <div className="border-t border-gray-100 mt-4 pt-3 space-y-2">
        <div className="flex items-center gap-3">
          <button className="btn-primary text-sm" onClick={onRecommend} disabled={recLoading}>
            {recLoading ? '生成中…' : '生成接口推荐'}
          </button>
          <span className="text-xs text-gray-400">按同行业研究案例推荐该开通的集成接口（三圈渐进解锁）</span>
        </div>
        {recSummary && <p className="text-xs text-gray-600">{recSummary}</p>}
        {rec && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {([
              ['建议开通', rec.ready],
              ['待补凭证', rec.pending_credentials],
              ['暂不需要', rec.not_needed],
            ] as const).map(([title, items]) => (
              <div key={title} className="border border-gray-100 rounded-lg p-2">
                <p className="text-xs font-semibold text-gray-700 mb-1">{title}（{items.length}）</p>
                {items.length === 0 && <p className="text-[11px] text-gray-400">无</p>}
                {items.map((it) => (
                  <div key={it.interface} className="flex items-center justify-between text-[11px] py-0.5">
                    <span className="text-gray-600">{it.interface}</span>
                    <span className={`px-1.5 py-0.5 rounded-full ${CIRCLE_STYLE[it.circle] || 'bg-gray-100 text-gray-500'}`}>
                      {CIRCLE_LABEL[it.circle] || it.circle}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
        {rec && <p className="text-[11px] text-gray-400">解锁路径：{rec.unlock_path}</p>}
      </div>
    </section>
  );
}
