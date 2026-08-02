# 招投标/客户声音数据源接入指南（env_customer_voice_url）

> 适用：第⑥路环境感知 `customer_voice`（客户声音）源升级 live。代码已就绪（`src/runtime/env_sources/customer_voice_source.py`），**缺的只是真实数据服务商的 API URL + 凭证**。本指南说明怎么接、接什么、怎么合规。

## 一、现状：代码已就绪

- `customer_voice_source._live_url()` 读配置 `env_customer_voice_url`（服务器 `.env`）。
- **留空 = simulated 演示态**（确定性样本，可演示、不可当真）。
- **配置后自动升级 live**：`fetch()` 用 httpx GET 该 URL，`_parse_live()` 解析 JSON，失败自动回退 simulated（韧性铁律，绝不破管）。
- 信号经 `credibility=authoritative` 进**人工审核队列**（官方为锚、其余必筛），批准后才锚定。

## 二、live URL 返回格式约定（必须遵循）

`_parse_live()` 期望顶层是 JSON **数组**，或 `{"items": [...]}`，每条：

```json
[
  {
    "title": "某运营商发布新一轮集采招标：强调低时延与自主可控",
    "content": "客户集采招标文件显示，本批设备对低时延、自主可控提出明确评分要求…",
    "customer": "运营商",
    "url": "https://example.com/tender/123",
    "date": "2026-08-01"
  }
]
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✅ | 标题，≤200 字符（截断） |
| `content` 或 `summary` | ✅ | 内容，≤500 字符（截断） |
| `customer` | 可选 | 客户类型/名称，进 `CUS:` 实体（无则用 title 兜底） |
| `url` | 可选 | 溯源链接（F4 可信治理要求来源可追溯） |

> 🔴 **供应商 API 返回格式若不同**（如嵌套 `data.list`），需在 `_parse_live()` 里加适配解析——这是唯一需要改代码的地方，届时把样例 JSON 发我即可。

## 三、🔴 合规红线（必须遵守，项目铁律）

1. **不爬未经授权的站点**：直接爬取中国政府采购网等站点属于未授权抓取，违反「法律红线=不触碰法律」。**只接正规 API 服务商**。
2. **密钥绝不进代码/仓库**：API Key 只放服务器 `.env`（`env_customer_voice_url` 可含查询参数认证，或单独 `env_customer_voice_token` 由适配层加 header——需新增配置项时告诉我）。
3. **数据授权**：确认服务商授权范围覆盖你的使用场景（内部决策 vs 对外展示）。
4. **人审闸门不变**：接入 live 后信号仍是 `authoritative` → 人工审核队列，不自动进真相源。

## 四、主流服务商参考（需自行核实授权/价格/数据覆盖）

| 类型 | 代表服务商 | 特点 | 适用 |
|---|---|---|---|
| 招投标聚合 | 剑鱼标讯 / 采招网 / 千里马 / 招标雷达 | 全行业招投标公告聚合，API 按次/按量付费 | 商机扫描（bid_intel 主消费） |
| 企业情报 | 天眼查 / 企查查 | 企业工商/经营/舆情，API 成熟 | 客户画像补强（customer_voice 扩展） |
| 行业报告 | 各咨询机构公开 API / 行业资讯聚合 | 需确认授权 | 资本开支/趋势信号 |
| 舆情 | 清博 / 识微等舆情 API | 客户口碑/投诉信号 | customer_voice 舆情维度 |

> ⚠️ 价格/数据源授权/覆盖范围变化快，**签约前务必核实**。以上仅为类型参考，非推荐背书。

## 五、接入步骤（拿到凭证后）

1. 选择服务商，购买/申请 API，拿到 **URL + 认证方式（Query/Header/Body）**。
2. 若返回格式与第二节不一致，把样例 JSON 发我，加适配解析（一行级改动）。
3. 服务器 `.env` 增加（或修改）：
   ```ini
   env_customer_voice_url=https://api.example.com/tenders?token=xxx
   ```
   🔴 若 token 不宜放 URL，告诉我加 `env_customer_voice_token` 配置项（适配层加 header）。
4. 重启 runtime：`docker compose -f docker-compose.prod.yml up -d runtime`（或走部署脚本）。
5. 验证升级：
   - `GET /api/environment/sources/customer_voice/test` → `mode: "live"`（可达）
   - `POST /api/environment/sources/customer_voice/pull?limit=5` → `"mode": "live"`、`published > 0`
   - `GET /api/environment/signals` → 出现真实 `env://customer_voice/...` 信号，credibility=authoritative
6. 后台审核队列批准后，信号进入真相源，`bid_intel` 商机情报自动消费（零改动）。

## 六、回退与运维

- **回退 simulated**：删掉 `.env` 里的 `env_customer_voice_url` 并重启即回退。
- **失败自愈**：live 拉取失败（超时/4xx/解析错）自动回退 simulated 样本，不阻塞 UNS 与 Agent。
- **频率控制**：`env_pull_interval`（秒，默认 3600）控制后台轮询；对 API 计费方建议 ≥3600，避免配额超支。
