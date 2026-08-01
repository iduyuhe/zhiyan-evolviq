# 研究案例租户登录账号（团队查阅）

> **用途**：2026-07-29 杜总破例授权——在未真正开拓客户前，先把两个研究案例（通讯 / 半导体）实例化为可登录租户，让团队能进生产系统以租户身份看到「研究案例推演数据」。
> **对应代码**：`src/runtime/seed_case_tenants.py`（seed 幂等，重复启动不重复建号）。
> **生产状态**：✅ 已实机验证 4 个账号均可登录（核心入口 `http://43.153.172.52:3006`）。

---

## 生产入口

- 核心入口：`http://43.153.172.52:3006`
- 边缘入口：`https://zhiyan.weomnitech.com.cn`（同账号通用）
- 登录方式：Studio 登录页，填「用户名 + 密码」即可（无需 X-Tenant-Key，租户上下文由 JWT 自动解析）。

## 账号表（可直接复制）

| 租户（匿名显示名） | 角色 | 用户名 | 密码 | 登录后入口 |
|---|---|---|---|---|
| 某某通讯公司（研究案例租户·未签约） | 管理员 | `telecom_admin` | `Zhiyan@telecom_admin2026` | 「研究案例库」→「我的绑定案例」= case_telecom_2026 |
| 某某通讯公司（研究案例租户·未签约） | 观察员 | `telecom_viewer` | `Zhiyan@telecom_viewer2026` | 同上，但只读、无写回权限 |
| 某某半导体公司（研究案例租户·未签约） | 管理员 | `semicon_admin` | `Zhiyan@semicon_admin2026` | 「研究案例库」→「我的绑定案例」= case_semicon_2026 |
| 某某半导体公司（研究案例租户·未签约） | 观察员 | `semicon_viewer` | `Zhiyan@semicon_viewer2026` | 同上，但只读、无写回权限 |

**密码规则**：固定为 `Zhiyan@{完整用户名}2026`（英文 `@` 紧跟 `Zhiyan` 后，无空格）。
例：`telecom_admin` → `Zhiyan@telecom_admin2026`。

---

## 易踩坑提醒

- **用户名是整串，不是 `admin`**：用 `admin` 登录会失败——那是杜特总租户 `dute_admin`。
- **`@` 是英文 at 符号**：`Zhiyan@telecom_admin2026`（Z-h-i-y-a-n-@-t-e-l-e-c-o-m-_-a-d-m-i-n-2-0-2-6）。
- **匿名显示名不含真名**：界面显示「某某通讯公司 / 某某半导体公司」，真实企业（中兴通讯 / 中芯国际）仅用于内部研究案例推演，绝不在界面或任何对外 payload 出现（对外出口 `pop("real_anchor")`）。

## 数据性质与合规红线（破例的是「流程」不是「合规」）

- `tenant_kind="research_case"`，租户标注「未签约·非真实客户」。
- 数据来源标注「公开披露信息推演」（`data_origin=public_disclosure_derivation`），`/cases/my` 出口带 `disclaimer`。
- 注入的决策信号一律 `real_time=False`，**不计入**杜特第 0 号真实客户撑起的北极星真实率。
- 这些是演示态账号，仅用于内部查看研究案例推演，**不可对外宣称已签约客户或已融合真实数据**。

## 环境变量覆盖（可选）

若需统一口令，可在 runtime 环境变量覆盖（无需改代码）：

- `ZHIYAN_CASE_PW`（所有案例账号统一密码），或
- `ZHIYAN_CASE_PW_TELECOM_ADMIN` / `ZHIYAN_CASE_PW_SEMICON_ADMIN` 等按大写用户名逐账号覆盖。

> 注：本仓库为公开仓库，以上默认密码已随种子代码入库，属「已知演示口令」。在接入任何真实客户前，应改用内部统一口令或通过 `ZHIYAN_CASE_PW_*` 覆盖。
