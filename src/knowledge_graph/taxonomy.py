"""知识图谱 taxonomy 常量（刀1 迭代1）。

对应白皮书 v3 的「一脊·一体·四体系」：
- 脊的四级（行业 / 产业节点 / 企业 / 岗位 / 对象）-> SPINE_LEVELS / ENTITY_TYPES
- 关系类型（竞争 / 价值链 / 供应 / 职责）-> RELATION_TYPES

⚠️ 这些是框架常量，范围基线（docs/TECHNICAL_DELIVERY_SCOPE.md）冻结：
   不得在本阶段新增实体/关系类型泛滥；对象级（人机料法环）留待后续迭代。
"""

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
