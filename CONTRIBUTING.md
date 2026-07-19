# 贡献指南 · Contributing to 智衍 EvolvIQ

感谢你有兴趣参与 **智衍 EvolvIQ**！本项目是面向工业制造的 AI 原生智能体平台，采用 [Apache-2.0](./LICENSE) 许可证开源。无论是修 bug、写文档、加 Agent，还是提想法，我们都欢迎。

---

## 目录

- [行为准则](#行为准则)
- [快速开始](#快速开始)
- [开发环境](#开发环境)
- [提交 Issue](#提交-issue)
- [提交 Pull Request](#提交-pull-request)
- [代码规范](#代码规范)
- [如何新增一个 Agent](#如何新增一个-agent)
- [测试](#测试)
- [提交信息规范](#提交信息规范)

---

## 行为准则

参与本项目即表示你同意遵守 [行为准则](./CODE_OF_CONDUCT.md)。请保持友善、专业、包容。

---

## 快速开始

```bash
# 1. Fork 并克隆
git clone https://github.com/<你的用户名>/zhiyan-evolviq.git
cd zhiyan-evolviq

# 2. 准备环境变量（复制模板，按需填写；不填也能跑，会自动降级）
cp .env.example .env

# 3. 安装依赖（Python >= 3.13）
pip install -e .

# 4. 启动运行时
uvicorn src.runtime.main:app --reload --port 8000

# 或用 Docker 一键起全栈（含 PostgreSQL/Neo4j/网关模拟器）
docker compose up -d
```

> **韧性降级**：即使没有 PostgreSQL / Neo4j / 工业协议数据源，系统也会自动回退到 SQLite / 内存图 / simulated 模式，绝不阻塞启动。因此本地开发零外部依赖即可跑通。

---

## 开发环境

| 组件 | 版本要求 | 说明 |
|---|---|---|
| Python | >= 3.13 | 后端运行时 |
| Node.js | >= 20 | 前端 Studio（`studio/`） |
| Docker | 可选 | 一键起全栈 |

后端核心目录：

```
src/
├── common/       # 配置、LLM 客户端、Neo4j 客户端等公共基座
├── runtime/      # 路由、API、知识图谱、授权引擎、MCP 联邦
├── gateways/     # 4 类工业协议网关（Modbus/MQTT/OPC-UA/IPC-CFX）
├── agents/       # 11 个工业 Agent（每个是独立目录包）
└── meta_agent/   # 元 Agent
```

---

## 提交 Issue

提交前请先搜索 [已有 Issue](https://github.com/iduyuhe/zhiyan-evolviq/issues)，避免重复。

- **Bug 报告**：请用 [Bug 模板](./.github/ISSUE_TEMPLATE/bug_report.md)，附上复现步骤、期望行为、实际行为、环境信息。
- **功能建议**：请用 [Feature 模板](./.github/ISSUE_TEMPLATE/feature_request.md)，说明使用场景和价值。
- **安全漏洞**：**请勿公开提交 Issue**，改为私下联系维护者（见下方联系方式）。

---

## 提交 Pull Request

1. Fork 仓库，从 `main` 拉出特性分支：`git checkout -b feat/your-feature`
2. 编写代码 + 测试，确保 `pytest` 全绿
3. 遵守[提交信息规范](#提交信息规范)
4. 推送并发起 PR，填写 PR 模板
5. 等待 Review；CI 通过 + 至少 1 个 Approve 后合并

**PR 要求**：
- 单个 PR 聚焦一件事，避免大杂烩
- 新增功能须附测试
- 破坏性变更须在 PR 描述中显式标注
- 不得引入密钥、内网 IP、真实凭据

---

## 代码规范

- **Python**：遵循 PEP 8；类型标注尽量完整；公共函数写 docstring
- **命名**：模块/函数 `snake_case`，类 `PascalCase`
- **提交前**：确保没有调试 `print`、没有硬编码密钥
- **格式化**：推荐 `ruff format` / `black`

---

## 如何新增一个 Agent

每个 Agent 是 `src/agents/<name>/` 下的独立目录包，标准结构：

```
src/agents/<name>/
├── __init__.py
├── agent.py      # Agent 主类，实现 analyze(goal) 契约
├── tools.py      # 该 Agent 的工具函数
├── prompts.py    # 提示词
└── models.py     # Pydantic 数据模型
```

**统一接口契约**：所有 Agent 主类都应实现 `analyze(goal: str) -> dict`（继承 `BaseAgent`）。这样调度层、MCP 联邦、社区贡献者才能按同一规范对接。

新增后需在以下 4 处静态接线：
1. `src/runtime/api/agents_api.py` → `AGENT_REGISTRY`
2. `src/runtime/agent/router.py` → `ROUTING_RULES` + `execute_by_agent`
3. MCP 工具注册（`src/runtime/mcp/`）
4. 授权边界（`src/runtime/core/authorization.py` → 补一条 `AuthBoundary`，**必须**，否则该 Agent 无授权边界）

---

## 测试

```bash
# 跑全部单测
pytest tests/ -q

# 端到端验证脚本
python scripts/verify_kg.py          # 知识图谱
python scripts/verify_federation.py  # MCP 联邦
python scripts/verify_gateways.py    # 工业网关
```

新增功能请补充对应测试，保证 `pytest` 无回归。

---

## 提交信息规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>: <简短描述>

<可选正文>
```

常用 type：

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 文档 |
| `test` | 测试 |
| `refactor` | 重构（不改行为） |
| `chore` | 杂务（构建、依赖等） |
| `perf` | 性能优化 |

示例：`feat: add welding-quality agent with OPC-UA data source`

---

## 联系方式

- **Issue / Discussion**：优先在 GitHub 上交流
- **维护者**：杜玉河（工业5点0产业生态联盟）

再次感谢你的贡献！🎉
