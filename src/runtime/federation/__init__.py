"""v24.0 跨企业联邦学习

匿名聚合多租户的经验知识，实现跨企业智能体联邦的雏形：
- 跨租户 KG 事实模式聚合（去标识化，只留结构模式）
- 跨租户策略信号聚合（匿名统计）
- 不泄露任何租户的具体业务数据
"""

from src.runtime.federation.federated_kg import FederatedKG
from src.runtime.federation.federated_strategy import FederatedStrategy

federated_kg = FederatedKG()
federated_strategy = FederatedStrategy()
