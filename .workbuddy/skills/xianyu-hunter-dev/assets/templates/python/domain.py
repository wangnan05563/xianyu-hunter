"""领域模型模板

复制后替换以下占位符：
- {Entity}：实体类名（如 Task、Item、Order）
- {entity}：变量名（如 task、item）

设计要点：
- 领域模型使用 dataclass，不可变（frozen=True）保证语义安全
- 业务规则封装在领域模型方法中，避免贫血模型
- 不依赖任何基础设施（无 ORM、无 HTTP、无 DB）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class {Entity}Status(str, Enum):
    """{Entity} 状态枚举
    
    继承 str, Enum 使其值即为字符串，便于 JSON 序列化
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


@dataclass(frozen=True)
class {Entity}:
    """{Entity} 领域模型（不可变）
    
    为什么用 frozen=True：
    - 防止运行时意外修改字段导致状态不一致
    - 可哈希，可作为 dict key 或集合元素
    - 强制通过 with_* 方法"修改"（实际返回新实例）
    """
    
    id: str
    name: str
    status: {Entity}Status = {Entity}Status.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """是否为活跃状态"""
        return self.status == {Entity}Status.ACTIVE
    
    def can_be_deleted(self) -> bool:
        """是否可删除（业务规则：只有非活跃状态可删除）"""
        return self.status != {Entity}Status.ACTIVE
    
    def with_status(self, new_status: {Entity}Status) -> {Entity}:
        """返回新状态的实例（不可变对象的"修改"模式）
        
        为什么不直接修改字段：
        - frozen=True 禁止字段赋值
        - 返回新实例保持原对象不变，避免副作用
        """
        return {Entity}(
            id=self.id,
            name=self.name,
            status=new_status,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )
    
    def with_metadata(self, key: str, value: Any) -> {Entity}:
        """返回新增元数据的实例"""
        new_metadata = {**self.metadata, key: value}
        return {Entity}(
            id=self.id,
            name=self.name,
            status=self.status,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=new_metadata,
        )


@dataclass
class {Entity}Factory:
    """{Entity} 工厂
    
    为什么用工厂类：
    - 封装复杂创建逻辑（如 ID 生成、默认值填充）
    - 便于测试（可注入 mock ID 生成器）
    - 集中校验业务规则
    """
    
    @staticmethod
    def create(name: str, **kwargs) -> {Entity}:
        """创建新 {Entity}"""
        if not name or not name.strip():
            raise ValueError("name 不能为空")
        
        import uuid
        return {Entity}(
            id=uuid.uuid4().hex,
            name=name.strip(),
            status={Entity}Status.ACTIVE,
            metadata=kwargs,
        )
    
    @staticmethod
    def from_dict(data: dict) -> {Entity}:
        """从字典重建 {Entity}（用于持久化层反序列化）"""
        return {Entity}(
            id=data["id"],
            name=data["name"],
            status={Entity}Status(data.get("status", "active")),
            created_at=data.get("created_at", datetime.now(timezone.utc)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc)),
            metadata=data.get("metadata", {}),
        )


# ==================== 领域事件 ====================

@dataclass(frozen=True)
class {Entity}Created:
    """{Entity} 创建事件"""
    entity_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class {Entity}StatusChanged:
    """{Entity} 状态变更事件"""
    entity_id: str
    old_status: {Entity}Status
    new_status: {Entity}Status
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
