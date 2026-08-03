"""知识图谱 taxonomy 常量（刀1 迭代1）。

对应白皮书 v3 的「一脊·一体·四体系」：
- 脊的四级（行业 / 产业节点 / 企业 / 岗位 / 对象）-> SPINE_LEVELS / ENTITY_TYPES
- 关系类型（竞争 / 价值链 / 供应 / 职责）-> RELATION_TYPES

⚠️ 这些是框架常量，范围基线（docs/TECHNICAL_DELIVERY_SCOPE.md）冻结：
   不得在本阶段新增实体/关系类型泛滥；对象级（人机料法环）留待后续迭代。
"""

from typing import Dict, List

# 物理存在脊（5 级，越往下越靠近物理动作）
SPINE_LEVELS = ("industry", "industry_node", "enterprise", "role", "object")

# 实体类型
ENTITY_TYPES = {
    "industry": "行业（最底座公开聚合层，知识平权）",
    "industry_node": "产业节点（价值链节点，如代工/设备/设计/存储/封测）",
    "enterprise": "企业锚（研究案例锚定的标杆企业，对外匿名）",
    "role": "岗位（角色记忆载体，如董事长/供应链专员）",
    "object": "对象（人机料法环最小物理单元，孪生最小载体）",
}

# 关系类型（开放世界观：竞争 / 供应 / 价值链 / 对标 / 职责）
RELATION_TYPES = {
    "VALUE_CHAIN": "价值链上下游（行业↔产业节点↔企业锚的归属/上下游）",
    "COMPETES_WITH": "竞争 / 对标（同产业节点内的企业锚相互对照）",
    "SUPPLIES": "供应（企业锚之间的供需关系）",
    "REPORTS_TO": "职责（岗位向岗位 / 岗位向企业汇报）",
}

# 价值链节点拓扑（刀1 迭代2）：开放获取补全的产业常识，不调外部 API。
# 语义：上游产业节点 -> 下游产业节点；同一 (industry_key, 上游类别) 内的企业锚
# 向同一 (industry_key, 下游类别) 内的企业锚发出 SUPPLIES 供应边。
# ⚠️ 范围护栏：仅在 taxonomy 这一框架常量层声明，且只覆盖已授权行业；
# 新增行业 / 节点须先经范围基线（docs/TECHNICAL_DELIVERY_SCOPE.md）拍板。
VALUE_CHAIN_TOPOLOGY: Dict[str, List[str]] = {
    # key 形如 f"{industry_key}|{node_category}"，value 为下游同格式 key 列表
    "semiconductor|设计": ["semiconductor|代工"],
    "semiconductor|设备": ["semiconductor|代工", "semiconductor|封测"],
    "semiconductor|代工": ["semiconductor|封测"],
    "semiconductor|存储": [],            # 存储与 IDM 多为垂直整合，对外不臆造下游
    "semiconductor|封测": [],
}
