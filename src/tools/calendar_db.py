from __future__ import annotations

"""面向日历的数据库工具函数。

提供事件的新增、更新、删除、查询等基础操作；
包含时间解析与序列化、冲突检测接入。
"""

import json
from typing import Any, Dict, List, Optional

import pendulum
from pendulum import DateTime
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from src.graph.schema import EventSummary, FreeSlot
from src.storage.database import get_session, init_db
from src.storage.models import Event
from src.tools.conflict_detector import detect_conflicts

# 初始建表，确保在首次使用前表结构存在
init_db()

def _trace(state_like: Optional[dict], message: str) -> None:
    try:
        if isinstance(state_like, dict):
            state_like.setdefault("trace", []).append(message)
    except Exception:
        pass


class EventCreate(BaseModel):
    """创建事件的入参模型。时间使用 ISO 字符串，内部统一解析为 tz-aware。"""

    title: str
    description: Optional[str] = None
    start_time: str
    end_time: str
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: str = "confirmed"
    source: str = "user"

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_dt(cls, value: str) -> str:
        # 校验可被 pendulum 解析
        _ = pendulum.parse(value)
        return value


class EventUpdate(BaseModel):
    """更新事件的入参模型。字段全可选，用于部分更新。"""

    event_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class EventQuery(BaseModel):
    """事件列表查询条件。支持时间范围、标签与状态。"""

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


def parse_datetime(value: str) -> DateTime:
    """解析为 tz-aware 的 pendulum DateTime，默认补齐为 UTC。"""

    dt = pendulum.parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pendulum.timezone("UTC"))
    return dt


def serialize_event(event: Event) -> Dict[str, Any]:
    """将 ORM 实体序列化为可返回的字典，并统一时间格式为 ISO8601。"""

    start = pendulum.instance(event.start_time)
    end = pendulum.instance(event.end_time)
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start_time": start.to_iso8601_string(),
        "end_time": end.to_iso8601_string(),
        "location": event.location,
        "tags": event.tags or [],
        "status": event.status,
        "source": event.source,
        "created_at": pendulum.instance(event.created_at).to_iso8601_string(),
        "updated_at": pendulum.instance(event.updated_at).to_iso8601_string(),
    }


def add_event(payload: EventCreate, allow_overlap: bool = False, state: Optional[dict] = None) -> Dict[str, Any]:
    """创建事件，默认为不允许时间冲突。

    若检测到冲突且 `allow_overlap=False`，返回 `status=conflict` 与冲突详情。
    """

    start_dt = parse_datetime(payload.start_time)
    end_dt = parse_datetime(payload.end_time)
    if end_dt <= start_dt:
        raise ValueError("End time must be after start time.")

    with get_session() as session:
        # 获取所有现有事件用于冲突检测
        existing = session.scalars(select(Event)).all()
        conflicts = detect_conflicts(start_dt, end_dt, existing)
        if conflicts and not allow_overlap:
            _trace(state, f"DB -> add_event conflict count={len(conflicts)}")
            return {
                "status": "conflict",
                "conflicts": [serialize_event(e) for e in conflicts],
            }
        # 无冲突或允许重叠，则创建事件
        event = Event(
            title=payload.title,
            description=payload.description,
            start_time=start_dt,
            end_time=end_dt,
            location=payload.location,
            tags=payload.tags,
            status=payload.status,
            source=payload.source,
        )
        session.add(event)
        session.flush()
        session.refresh(event)
        _trace(state, f"DB -> add_event success id={event.id}")
        return {
            "status": "success",
            "event": serialize_event(event),
            "conflicts": [serialize_event(e) for e in conflicts],
        }


def update_event(payload: EventUpdate, allow_overlap: bool = False) -> Dict[str, Any]:
    """更新事件，默认不允许时间冲突。支持部分字段更新。"""

    with get_session() as session:
        event = session.get(Event, payload.event_id)
        if event is None:
            return {"status": "not_found", "event_id": payload.event_id}

        updated_start = parse_datetime(payload.start_time) if payload.start_time else pendulum.instance(event.start_time)
        updated_end = parse_datetime(payload.end_time) if payload.end_time else pendulum.instance(event.end_time)
        if updated_end <= updated_start:
            raise ValueError("End time must be after start time.")

        existing = session.scalars(select(Event)).all()
        conflicts = detect_conflicts(updated_start, updated_end, existing, exclude_event_id=event.id)
        if conflicts and not allow_overlap:
            return {
                "status": "conflict",
                "conflicts": [serialize_event(e) for e in conflicts],
            }

        # 按需更新字段
        if payload.title is not None:
            event.title = payload.title
        if payload.description is not None:
            event.description = payload.description
        if payload.start_time is not None:
            event.start_time = updated_start
        if payload.end_time is not None:
            event.end_time = updated_end
        if payload.location is not None:
            event.location = payload.location
        if payload.tags is not None:
            event.tags = payload.tags
        if payload.status is not None:
            event.status = payload.status

        session.flush()
        session.refresh(event)
        return {
            "status": "success",
            "event": serialize_event(event),
            "conflicts": [serialize_event(e) for e in conflicts],
        }


def remove_event(event_id: str) -> Dict[str, Any]:
    """删除事件。若不存在返回 not_found。"""

    with get_session() as session:
        event = session.get(Event, event_id)
        if event is None:
            return {"status": "not_found", "event_id": event_id}
        session.delete(event)
        return {"status": "success", "event_id": event_id}


def get_event(event_id: str) -> Dict[str, Any]:
    """获取单个事件详情。"""

    with get_session() as session:
        event = session.get(Event, event_id)
        if event is None:
            return {"status": "not_found", "event_id": event_id}
        return {"status": "success", "event": serialize_event(event)}


def list_events(query: Optional[EventQuery] = None) -> Dict[str, Any]:
    """按条件查询事件列表并序列化返回。支持按标签包含过滤。"""

    query = query or EventQuery()
    with get_session() as session:
        stmt = select(Event)
        if query.start_time:
            stmt = stmt.where(Event.start_time >= parse_datetime(query.start_time))
        if query.end_time:
            stmt = stmt.where(Event.end_time <= parse_datetime(query.end_time))
        if query.status:
            stmt = stmt.where(Event.status == query.status)
        events = session.scalars(stmt).all()
        serialized = [serialize_event(e) for e in events]
        # 可选：标签包含过滤（传入的 tags 需为序列化后的字段）
        if query.tags:
            filtered = []
            tag_set = set(query.tags)
            for event in serialized:
                event_tags = set(event.get("tags", []))
                if tag_set.issubset(event_tags):
                    filtered.append(event)
            serialized = filtered
        return {"status": "success", "events": serialized}


def get_free_slots(
    start_date: str, 
    end_date: str, 
    min_duration_minutes: int = 30,
    working_hours_start: int = 9,
    working_hours_end: int = 18
) -> Dict[str, Any]:
    """查询指定时间范围内的空闲时间段。
    
    用于 PlanningAgent 获取可用的时间段进行任务安排。
    
    Args:
        start_date: 开始日期（ISO 8601 格式）
        end_date: 结束日期（ISO 8601 格式）
        min_duration_minutes: 最小空闲时长（分钟）
        working_hours_start: 工作时间开始（小时）
        working_hours_end: 工作时间结束（小时）
        
    Returns:
        空闲时间段列表
    """
    try:
        start_dt = parse_datetime(start_date)
        end_dt = parse_datetime(end_date)
        
        if end_dt <= start_dt:
            return {
                "status": "error",
                "message": "结束时间必须晚于开始时间",
                "free_slots": []
            }
        
        with get_session() as session:
            # 查询指定时间范围内的所有事件
            events = session.scalars(
                select(Event).where(
                    Event.start_time >= start_dt,
                    Event.end_time <= end_dt,
                    Event.status == "confirmed"
                ).order_by(Event.start_time)
            ).all()
            
            # 转换为 FreeSlot 对象
            free_slots = []
            current_time = start_dt
            
            for event in events:
                event_start = pendulum.instance(event.start_time)
                event_end = pendulum.instance(event.end_time)
                
                # 检查是否有空闲时间
                if current_time < event_start:
                    duration_minutes = (event_start - current_time).total_seconds() / 60
                    if duration_minutes >= min_duration_minutes:
                        # 限制在工作时间内
                        slot_start = max(current_time, current_time.replace(hour=working_hours_start, minute=0, second=0))
                        slot_end = min(event_start, current_time.replace(hour=working_hours_end, minute=0, second=0))
                        
                        if slot_start < slot_end:
                            actual_duration = (slot_end - slot_start).total_seconds() / 60
                            if actual_duration >= min_duration_minutes:
                                free_slots.append(FreeSlot(
                                    start_time=slot_start,
                                    end_time=slot_end,
                                    duration_minutes=int(actual_duration)
                                ))
                
                current_time = max(current_time, event_end)
            
            # 检查最后一段空闲时间
            if current_time < end_dt:
                duration_minutes = (end_dt - current_time).total_seconds() / 60
                if duration_minutes >= min_duration_minutes:
                    slot_start = max(current_time, current_time.replace(hour=working_hours_start, minute=0, second=0))
                    slot_end = min(end_dt, current_time.replace(hour=working_hours_end, minute=0, second=0))
                    
                    if slot_start < slot_end:
                        actual_duration = (slot_end - slot_start).total_seconds() / 60
                        if actual_duration >= min_duration_minutes:
                            free_slots.append(FreeSlot(
                                start_time=slot_start,
                                end_time=slot_end,
                                duration_minutes=int(actual_duration)
                            ))
            
            return {
                "status": "success",
                "free_slots": [slot.to_dict() for slot in free_slots],
                "total_slots": len(free_slots),
                "total_duration_minutes": sum(slot.duration_minutes for slot in free_slots),
                "query_range": {
                    "start": start_dt.to_iso8601_string(),
                    "end": end_dt.to_iso8601_string()
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"查询空闲时间失败: {str(e)}",
            "free_slots": []
        }


def get_events_summary(start_date: str, end_date: str) -> Dict[str, Any]:
    """获取指定时间范围内的事件统计摘要。
    
    用于 SummaryAgent 分析日程数据。
    
    Args:
        start_date: 开始日期（ISO 8601 格式）
        end_date: 结束日期（ISO 8601 格式）
        
    Returns:
        事件统计摘要
    """
    try:
        start_dt = parse_datetime(start_date)
        end_dt = parse_datetime(end_date)
        
        with get_session() as session:
            # 查询指定时间范围内的所有事件
            events = session.scalars(
                select(Event).where(
                    Event.start_time >= start_dt,
                    Event.end_time <= end_dt,
                    Event.status == "confirmed"
                )
            ).all()
            
            # 统计信息
            total_events = len(events)
            events_by_tag = {}
            time_distribution = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
            total_duration_minutes = 0
            
            for event in events:
                # 按标签统计
                for tag in (event.tags or []):
                    events_by_tag[tag] = events_by_tag.get(tag, 0) + 1
                
                # 按时间段统计
                start_hour = pendulum.instance(event.start_time).hour
                if 6 <= start_hour < 12:
                    time_distribution["morning"] += 1
                elif 12 <= start_hour < 18:
                    time_distribution["afternoon"] += 1
                elif 18 <= start_hour < 22:
                    time_distribution["evening"] += 1
                else:
                    time_distribution["night"] += 1
                
                # 计算总时长
                duration = (pendulum.instance(event.end_time) - pendulum.instance(event.start_time)).total_seconds() / 60
                total_duration_minutes += duration
            
            avg_duration_minutes = total_duration_minutes / total_events if total_events > 0 else 0
            
            # 创建统计摘要
            summary = EventSummary(
                total_events=total_events,
                events_by_tag=events_by_tag,
                time_distribution=time_distribution,
                avg_duration_minutes=round(avg_duration_minutes, 2)
            )
            
            return {
                "status": "success",
                "summary": summary.model_dump(),
                "query_range": {
                    "start": start_dt.to_iso8601_string(),
                    "end": end_dt.to_iso8601_string()
                },
                "period_days": (end_dt - start_dt).days + 1
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取事件摘要失败: {str(e)}",
            "summary": {}
        }

