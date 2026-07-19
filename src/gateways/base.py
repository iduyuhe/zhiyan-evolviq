"""协议网关基础接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GatewayConfig:
    name: str
    enabled: bool = True
    poll_interval_seconds: int = 30


@dataclass
class DataPoint:
    """单条工业数据点"""
    tag: str
    value: float | str | bool
    timestamp: float
    quality: str = "good"  # good / bad / uncertain


class BaseGateway(ABC):
    """协议网关基类——所有工业协议适配器继承此类"""

    def __init__(self, config: GatewayConfig):
        self.config = config
        self._running = False

    @abstractmethod
    async def connect(self) -> bool:
        """连接到设备/模拟器"""
        ...

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        ...

    @abstractmethod
    async def read(self, address: str, count: int = 1) -> list[DataPoint]:
        """读取数据"""
        ...

    @abstractmethod
    async def write(self, address: str, value: float | str | bool) -> bool:
        """写入数据（控制指令）"""
        ...

    async def health_check(self) -> dict:
        """网关健康检查"""
        return {
            "name": self.config.name,
            "running": self._running,
            "poll_interval": self.config.poll_interval_seconds,
        }
