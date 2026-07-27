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
    llm_reasoning_model: str = "deepseek-reasoner"
    llm_fast_model: str = "deepseek-chat"

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

    # 环境感知第⑥路（v30.0 α）：三类官方源。留空=simulated 演示态；配置真实 URL 后自动升级 live。
    env_policy_url: str = ""      # 政策法规官方发布页（如部委公开发布 RSS/JSON）
    env_market_url: str = ""      # 原材料行情官方指数接口
    env_benchmark_url: str = ""   # 行业智能化对标官方名录（试点示范/灯塔工厂等）
    env_pull_interval: int = 3600  # 环境源后台轮询间隔（秒），0=不轮询仅手动

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "zhiyan_",  # P0修复：与 .env 中 ZHIYAN_WECOM_TOKEN 等实际变量名匹配
    }


settings = Settings()
