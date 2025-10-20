from __future__ import annotations

"""数据模型定义。

包含多智能体协作所需的核心数据结构：
- TaskItem：任务项模型
- PlannerOutput：规划输出模型  
- SummaryOutput：总结输出模型
"""

import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TaskItem(BaseModel):
    """任务项模型，用于规划 Agent 的任务分解。
    
    包含任务的基本信息、时间安排、标签和优先级。
    """
    
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(..., description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    priority: int = Field(1, description="优先级（1-5，5最高）")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class PlannerOutput(BaseModel):
    """规划 Agent 的输出模型。
    
    包含分解的任务列表、冲突信息、备注和空闲时间段。
    """
    
    tasks: List[TaskItem] = Field(default_factory=list, description="任务列表")
    conflicts: List[str] = Field(default_factory=list, description="冲突描述列表")
    notes: str = Field("", description="规划备注")
    free_slots: List[Dict[str, str]] = Field(default_factory=list, description="空闲时间段")
    
    def has_conflicts(self) -> bool:
        """检查是否存在冲突。"""
        return len(self.conflicts) > 0


class SummaryOutput(BaseModel):
    """总结 Agent 的输出模型。
    
    包含时间范围、总结文本、优化建议和统计数据。
    """
    
    period: str = Field(..., description="总结时间范围")
    summary_text: str = Field(..., description="总结文本")
    recommendations: List[str] = Field(default_factory=list, description="优化建议列表")
    stats: Dict[str, Any] = Field(default_factory=dict, description="统计数据")
    
    def get_recommendation_count(self) -> int:
        """获取建议数量。"""
        return len(self.recommendations)


class FreeSlot(BaseModel):
    """空闲时间段模型。
    
    用于表示可用的时间段，供规划 Agent 使用。
    """
    
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    duration_minutes: int = Field(..., description="持续时间（分钟）")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式，便于工具调用。"""
        return {
            "start": self.start_time.to_iso8601_string(),
            "end": self.end_time.to_iso8601_string(),
            "duration": str(self.duration_minutes)
        }


class EventSummary(BaseModel):
    """事件统计摘要模型。
    
    用于总结 Agent 分析日程数据。
    """
    
    total_events: int = Field(0, description="总事件数")
    events_by_tag: Dict[str, int] = Field(default_factory=dict, description="按标签分组的事件数")
    time_distribution: Dict[str, int] = Field(default_factory=dict, description="时间分布统计")
    avg_duration_minutes: float = Field(0.0, description="平均持续时间（分钟）")
    
    def get_top_tags(self, limit: int = 5) -> List[tuple[str, int]]:
        """获取使用最多的标签。"""
        return sorted(self.events_by_tag.items(), key=lambda x: x[1], reverse=True)[:limit]
