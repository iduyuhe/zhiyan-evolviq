"""全局配置管理"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "智衍 EvolvIQ"
    app_version: str = "0.1.0"
    debug: bool = True

    # PostgreSQL
    db_url: str = "postgresql+asyncpg://zhiyan:zhiyan_dev@localhost:5432/zhiyan"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "zhiyan_dev"

    # LLM —— 主用 DeepSeek（OpenAI 兼容）
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    # 2026-07-24 DeepSeek 正式弃用 deepseek-reasoner / deepseek-chat → V4 系列。
    # deepseek-v4-flash 同时支持思考/非思考模式：推理模型须开启 thinking（见 llm_client.chat）。
    llm_reasoning_model: str = "deepseek-v4-flash"
    llm_fast_model: str = "deepseek-v4-flash"

    # LLM —— 备用 混元 Hunyuan（OpenAI 兼容，腾讯 MaaS tokenhub 通道）
    hunyuan_api_key: str = ""
    hunyuan_base_url: str = "https://tokenhub.tencentmaas.com/v1"
    hunyuan_model: str = "hy3"

    # MCP
    mcp_server_port: int = 8100

    # Gateway
    modbus_host: str = "localhost"
    modbus_port: int = 5020
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    ipc_cfx_broker: str = "amqp://localhost:5672"

    # Auth
    auth_enabled: bool = False  # MVP阶段暂不开启
    jwt_secret: str = "zhiyan-mvp-secret"

    # 社交通道接入（隐性捕获 → 经验库 + 知识图谱，v29.9）
    # 企业微信（自建应用回调）：Token 用于 URL/消息签名校验；EncodingAESKey + CorpId 用于消息体 AES 解密
    wecom_token: str = ""
    wecom_aes_key: str = ""
    wecom_corp_id: str = ""
    # 钉钉（群机器人/连接平台回调）：机器人「加签」secret 用于 HmacSHA256 校验
    dingtalk_secret: str = ""
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    # 邮件渠道（IMAP 轮询拉取）
    email_imap_host: str = ""
    email_imap_user: str = ""
    email_imap_password: str = ""
    email_imap_mailbox: str = "INBOX"
    email_poll_interval: int = 300

    # 环境感知第⑥路（v30.0 α）：三类官方源 + 客户声音情报源。留空=simulated 演示态；配置真实 URL 后自动升级 live。
    env_policy_url: str = ""      # 政策法规官方发布页（如部委公开发布 RSS/JSON）
    env_market_url: str = ""      # 原材料行情官方指数接口
    env_benchmark_url: str = ""   # 行业智能化对标官方名录（试点示范/灯塔工厂等）
    env_customer_voice_url: str = ""  # 客户声音情报（招投标/行业报告/舆情聚合 JSON；authoritative 级→人工审核队列）
    env_pull_interval: int = 3600  # 环境源后台轮询间隔（秒），0=不轮询仅手动

    # 企业微信自建应用 H5（移动端三阶第②阶，2026-08-02）：免登 agentConfig + 应用消息推送
    # 留空=未配置（优雅降级，/wecom/status 返回未配置，不阻塞平台）；凭证进服务器 .env 绝不进代码
    wecom_corpid: str = ""        # 企业微信 CorpID（我的企业→企业信息）
    wecom_secret: str = ""        # 自建应用 Secret（应用管理→自建应用→Secret）
    wecom_agentid: str = ""       # 自建应用 AgentId
    wecom_token: str = ""         # 可信域名校验 Token（企微后台配置回调用，可留空）

    # Agent 心跳自触发（2026-08-02 OpenClaw HEARTBEAT 借鉴，杜总拍板默认关）
    # 主动巡检：风险发生 → 系统主动识别 → 复用 AlertMonitor 发布告警（不等用户提问）
    # 默认关闭（避免演示环境噪音）；ZHIYAN_HEARTBEAT_ENABLED=1 开启
    heartbeat_enabled: bool = False
    heartbeat_interval_supply_chain: int = 1800    # 缺料巡检（秒，30min）
    heartbeat_interval_bid_intel: int = 14400      # 商机扫描（秒，4h）
    heartbeat_interval_energy_carbon: int = 3600   # 能耗/碳强度巡检（秒，1h）
    heartbeat_interval_executive_cockpit: int = 43200  # 资金/应收巡检（秒，12h）

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "zhiyan_",  # P0修复：与 .env 中 ZHIYAN_WECOM_TOKEN 等实际变量名匹配
    }


settings = Settings()
