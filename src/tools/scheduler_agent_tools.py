"""SchedulerAgent 工具集"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ..storage.database import get_db
from ..storage.models import Event


# ============ 工具函数 ============

def parse_datetime(dt_str: str) -> datetime:
    """解析时间字符串，支持多种格式"""
    # 支持的时间格式
    formats = [
        "%Y-%m-%d %H:%M",           # 2025-10-22 09:00
        "%Y-%m-%dT%H:%M:%S",        # 2025-10-22T09:00:00 (ISO格式)
        "%Y-%m-%dT%H:%M",           # 2025-10-22T09:00
        "%Y-%m-%d",                 # 2025-10-22
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    # 所有格式都失败
    raise ValueError(
        f"无法解析时间格式：{dt_str}，"
        f"支持的格式：YYYY-MM-DD HH:MM, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD"
    )


def add_event(
    title: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    tags: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """添加事件（自动检测时间冲突）"""
    try:
        start_dt = parse_datetime(start_time)
        end_dt = parse_datetime(end_time)
        
        if start_dt >= end_dt:
            return {"status": "error", "message": "开始时间必须早于结束时间"}
        
        # 自动检测冲突
        conflicts = _check_conflicts(start_time, end_time)
        
        # 如果有冲突且未强制添加，返回冲突信息
        if conflicts["has_conflict"] and not force:
            conflict_info = "\n".join([
                f"  - {c['title']} ({c['start_time']} ~ {c['end_time']})"
                for c in conflicts["conflicts"]
            ])
            return {
                "status": "error",
                "message": f"时间冲突！与以下事件重叠：\n{conflict_info}\n如需强制添加，请设置 force=True",
                "conflicts": conflicts["conflicts"]
            }
        
        with get_db() as db:
            event = Event(
                title=title,
                description=description,
                start_time=start_dt,
                end_time=end_dt,
                location=location,
                tags=tags,
                status="active"
            )
            db.add(event)
            db.flush()
            
            result = {
                "status": "success",
                "message": f"成功添加事件：{title}",
                "event": event.to_dict()
            }
            
            # 如果是强制添加且有冲突，添加警告信息
            if force and conflicts["has_conflict"]:
                result["warning"] = f"已强制添加，但与 {len(conflicts['conflicts'])} 个事件存在时间冲突"
                result["conflicts"] = conflicts["conflicts"]
            
            return result
    except Exception as e:
        return {"status": "error", "message": f"添加事件失败：{str(e)}"}


def update_event(
    event_id: int,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    tags: Optional[str] = None,
    status: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """更新事件（自动检测时间冲突）"""
    try:
        with get_db() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return {"status": "error", "message": f"未找到ID为 {event_id} 的事件"}
            
            # 更新字段
            if title:
                event.title = title
            if description is not None:
                event.description = description
            if location is not None:
                event.location = location
            if tags is not None:
                event.tags = tags
            if status:
                event.status = status
            
            # 更新时间并自动检测冲突
            if start_time or end_time:
                new_start = parse_datetime(start_time) if start_time else event.start_time
                new_end = parse_datetime(end_time) if end_time else event.end_time
                
                if new_start >= new_end:
                    return {"status": "error", "message": "开始时间必须早于结束时间"}
                
                # 自动检测冲突（排除当前事件）
                conflicts = _check_conflicts(
                    new_start.strftime("%Y-%m-%d %H:%M"),
                    new_end.strftime("%Y-%m-%d %H:%M"),
                    exclude_event_id=event_id
                )
                
                # 如果有冲突且未强制更新，返回冲突信息
                if conflicts["has_conflict"] and not force:
                    conflict_info = "\n".join([
                        f"  - {c['title']} ({c['start_time']} ~ {c['end_time']})"
                        for c in conflicts["conflicts"]
                    ])
                    return {
                        "status": "error",
                        "message": f"时间冲突！与以下事件重叠：\n{conflict_info}\n如需强制更新，请设置 force=True",
                        "conflicts": conflicts["conflicts"]
                    }
                
                event.start_time = new_start
                event.end_time = new_end
            
            event.updated_at = datetime.now()
            
            result = {
                "status": "success",
                "message": f"成功更新事件：{event.title}",
                "event": event.to_dict()
            }
            
            # 如果是强制更新且有冲突，添加警告信息
            if force and (start_time or end_time):
                conflicts = _check_conflicts(
                    event.start_time.strftime("%Y-%m-%d %H:%M"),
                    event.end_time.strftime("%Y-%m-%d %H:%M"),
                    exclude_event_id=event_id
                )
                if conflicts["has_conflict"]:
                    result["warning"] = f"已强制更新，但与 {len(conflicts['conflicts'])} 个事件存在时间冲突"
                    result["conflicts"] = conflicts["conflicts"]
            
            return result
    except Exception as e:
        return {"status": "error", "message": f"更新事件失败：{str(e)}"}


def remove_event(event_id: int) -> Dict[str, Any]:
    """删除事件"""
    try:
        with get_db() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return {"status": "error", "message": f"未找到ID为 {event_id} 的事件"}
            
            title = event.title
            db.delete(event)
            
            return {
                "status": "success",
                "message": f"成功删除事件：{title}"
            }
    except Exception as e:
        return {"status": "error", "message": f"删除事件失败：{str(e)}"}


def get_event(event_id: int) -> Dict[str, Any]:
    """查询单个事件"""
    try:
        with get_db() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return {"status": "error", "message": f"未找到ID为 {event_id} 的事件"}
            
            return {
                "status": "success",
                "event": event.to_dict()
            }
    except Exception as e:
        return {"status": "error", "message": f"查询事件失败：{str(e)}"}


def list_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: str = "active"
) -> Dict[str, Any]:
    """列出事件"""
    try:
        with get_db() as db:
            query = db.query(Event)
            
            # 状态筛选
            if status:
                query = query.filter(Event.status == status)
            
            # 时间范围筛选
            if start_date:
                start_dt = parse_datetime(start_date)
                query = query.filter(Event.start_time >= start_dt)
            
            if end_date:
                end_dt = parse_datetime(end_date) + timedelta(days=1)
                query = query.filter(Event.start_time < end_dt)
            
            events = query.order_by(Event.start_time).all()
            
            return {
                "status": "success",
                "count": len(events),
                "events": [event.to_dict() for event in events]
            }
    except Exception as e:
        return {"status": "error", "message": f"查询事件列表失败：{str(e)}"}


def get_free_slots(date: str, min_duration: int = 30) -> Dict[str, Any]:
    """查询空闲时间段"""
    try:
        date_dt = parse_datetime(date)
        day_start = date_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        with get_db() as db:
            # 查询当天的所有事件
            events = db.query(Event).filter(
                Event.status == "active",
                Event.start_time < day_end,
                Event.end_time > day_start
            ).order_by(Event.start_time).all()
            
            # 计算空闲时间段
            free_slots = []
            current_time = day_start.replace(hour=8, minute=0)  # 从早上8点开始
            end_of_day = day_start.replace(hour=22, minute=0)  # 到晚上10点
            
            for event in events:
                event_start = max(event.start_time, day_start)
                event_end = min(event.end_time, day_end)
                
                # 如果当前时间到事件开始有空闲
                if current_time < event_start:
                    duration = int((event_start - current_time).total_seconds() / 60)
                    if duration >= min_duration:
                        free_slots.append({
                            "start": current_time.strftime("%Y-%m-%d %H:%M"),
                            "end": event_start.strftime("%Y-%m-%d %H:%M"),
                            "duration_minutes": duration
                        })
                
                current_time = max(current_time, event_end)
            
            # 最后一个时间段
            if current_time < end_of_day:
                duration = int((end_of_day - current_time).total_seconds() / 60)
                if duration >= min_duration:
                    free_slots.append({
                        "start": current_time.strftime("%Y-%m-%d %H:%M"),
                        "end": end_of_day.strftime("%Y-%m-%d %H:%M"),
                        "duration_minutes": duration
                    })
            
            return {
                "status": "success",
                "date": date,
                "free_slots": free_slots,
                "count": len(free_slots)
            }
    except Exception as e:
        return {"status": "error", "message": f"查询空闲时间失败：{str(e)}"}


def _check_conflicts(start_time_str: str, end_time_str: str, exclude_event_id: Optional[int] = None) -> Dict[str, Any]:
    """内部函数：检测时间冲突"""
    try:
        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)
        
        with get_db() as db:
            query = db.query(Event).filter(
                Event.status == "active",
                Event.start_time < end_time,
                Event.end_time > start_time
            )
            
            # 排除指定事件
            if exclude_event_id:
                query = query.filter(Event.id != exclude_event_id)
            
            conflicts = query.all()
            
            return {
                "has_conflict": len(conflicts) > 0,
                "conflicts": [
                    {
                        "id": event.id,
                        "title": event.title,
                        "start_time": event.start_time.strftime("%Y-%m-%d %H:%M"),
                        "end_time": event.end_time.strftime("%Y-%m-%d %H:%M")
                    }
                    for event in conflicts
                ]
            }
    except Exception as e:
        return {"has_conflict": False, "conflicts": [], "error": str(e)}
