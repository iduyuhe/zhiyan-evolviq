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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
