# 企业微信自建应用 H5 接入操作清单（移动端三阶第②阶）

> 目标：工人/员工在**企业微信内置浏览器**直接打开智衍 H5 → **免登**（agentConfig）→ 服务端**应用消息推送**缺料预警（工作通知）。
> 代码骨架已就绪（`src/runtime/wecom/` + `/wecom/*` 端点，未配置时优雅降级不影响平台）。本清单是**后台配置操作**，配完填凭证即生效。

## 〇、前置条件

- ✅ 企业微信**企业已认证**（未认证的企业主体无法创建自建应用并调用 API）。
- ✅ 域名已 **ICP 备案**（`zhiyan.weomnitech.com.cn` 在国内服务器，大概率已备案；未备案请先补）。
- ✅ 代码已部署（`/wecom/status` 可访问——先登录平台后访问 `https://zhiyan.weomnitech.com.cn/api/wecom/status`，应返回 `configured: false`）。

## 一、操作步骤（6 步，企微后台为主）

### 步骤 1：创建自建应用，拿 AgentId + Secret
1. 登录企业微信管理后台 `https://work.weixin.qq.com/wework_admin/frame`。
2. **应用管理 → 应用 → 自建 → 创建应用**。
3. 填写应用名（如「智衍 EvolvIQ」）、Logo、可见范围（建议先选 IT/管理层测试，再扩全员）。
4. 创建后进入应用详情：**AgentId** 直接显示；**Secret** 点「查看」获取（🔴 只复制到服务器 .env，绝不外发/截图展示）。

### 步骤 2：配置可信域名（JS-SDK 免登必需）
1. 应用详情 → **企业可信IP / 网页授权及JS-SDK** → 配置可信域名。
2. 填 `zhiyan.weomnitech.com.cn`。
3. 按提示**下载校验文件**（txt），放到边缘服务器静态目录根路径（`/var/www/zhiyan/current/` 下，即 nginx 根目录），确保 `https://zhiyan.weomnitech.com.cn/<校验文件名>` 可访问。
4. 后台点「确认」，校验通过即绑定。
> ⚠️ 可信域名必须在企业微信后台**可访问到的公网域名**下完成文件校验。

### 步骤 3：配置网页授权（免登换取身份）
1. 应用详情 → **企业微信授权登录**（网页授权及JS-SDK）→ 设置**可信域名**（同上域名）。
2. 记录网页授权回调域（一般即主域名）。

### 步骤 4：拿 CorpID
- **我的企业 → 企业信息 → 企业ID（CorpID）**。

### 步骤 5：服务器 .env 填凭证并重启
在核心服务器 `/root/zhiyan/.env` 追加（🔴 凭证只进服务器，绝进 git/代码/日志）：

```ini
ZHIYAN_WECOM_CORPID=wwxxxxxxxxxxxxx
ZHIYAN_WECOM_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
ZHIYAN_WECOM_AGENTID=1000002
```

> 注意：config.py `env_prefix="zhiyan_"` → 环境变量名是大写 `ZHIYAN_WECOM_*`。
> 重启 runtime：`cd /root/zhiyan && docker compose -f docker-compose.prod.yml up -d runtime`。

### 步骤 6：验证
1. `GET https://zhiyan.weomnitech.com.cn/api/wecom/status`（登录后带 token）→ `configured: true`。
2. `POST /api/wecom/jsapi-signature` `{"url":"https://zhiyan.weomnitech.com.cn/"}` → 返回 corpid/agentId/signature（200）。
3. `POST /api/wecom/push` `{"userids":["<你的企微账号>"],"content":"缺料预警测试","title":"测试"}` → `ok:true`，企微内收到应用消息卡片。
4. 企微内置浏览器打开 H5 → 免登生效（登录页自动跳转或显示免登按钮）。

## 二、接入后能力（代码已备，配完即用）

| 能力 | 端点/机制 | 场景 |
|---|---|---|
| 免登 | `/wecom/jsapi-signature` + 前端 agentConfig | 员工企微内打开即登录，不输密码 |
| 缺料推送 | `/wecom/push`（应用消息 textcard 卡片） | 供应链 Agent 检出缺料 → 推给责任人 |
| 状态查询 | `/wecom/status` | 运维确认配置态 |

## 三、🔴 安全与合规红线

1. **凭证不落代码**：Secret/AgentId 只进服务器 `.env`；任何响应/日志不含 secret（`status()` 已做明文脱敏）。
2. **推送内容限制**：缺料预警等**生产运营信息**可推；**客户真名/商业机密**不进推送内容（匿名铁律延伸）。
3. **权限收敛**：`/wecom/push` 受 JWT 门禁；上线前建议加业务角色校验（如仅 supply_chain/厂长可触发），需要时告诉我加。
4. **回调安全**：若后续接企微事件回调（免登 code 换取、消息回调），需配 Token/AESKey 并在后端验签——本骨架未含回调验签，属第二阶段。

## 四、缺料推送接入点（待配凭证后接线）

推送触发点在 `supply_chain` Agent 缺料检测逻辑（`analyze_goal` 内 detect 缺料分支）。配好凭证后，我可以在检测到缺料风险 > 阈值时调用 `wecom_service.send_app_message(责任人, 缺料内容)`——这属于代码接线，凭证到位即可动工。
