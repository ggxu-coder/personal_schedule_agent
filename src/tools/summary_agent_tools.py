"""SummaryAgent 工具集"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from collections import defaultdict

from ..storage.database import get_db
from ..storage.models import Event


# ============ 工具函数 ============

def parse_datetime(dt_str: str) -> datetime:
    """解析时间字符串，支持多种格式"""
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(
        f"无法解析时间格式：{dt_str}，"
        f"支持的格式：YYYY-MM-DD HH:MM, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD"
    )


def get_events_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: str = "active"
) -> Dict[str, Any]:
    """获取事件统计摘要
    
    统计指定时间范围内的事件数量、总时长、类型分布等
    """
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
            
            events = query.all()
            
            if not events:
                return {
                    "status": "success",
                    "message": "指定时间范围内没有事件",
                    "total_count": 0,
                    "total_hours": 0,
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    }
                }
            
            # 统计数据
            total_count = len(events)
            total_minutes = sum(
                (event.end_time - event.start_time).total_seconds() / 60
                for event in events
            )
            total_hours = round(total_minutes / 60, 2)
            
            # 按日期分组统计
            events_by_date = defaultdict(int)
            for event in events:
                date_key = event.start_time.strftime("%Y-%m-%d")
                events_by_date[date_key] += 1
            
            # 按标题分组统计（事件类型）
            events_by_type = defaultdict(int)
            for event in events:
                events_by_type[event.title] += 1
            
            # 时间段分布（上午、下午、晚上）
            time_distribution = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
            for event in events:
                hour = event.start_time.hour
                if 6 <= hour < 12:
                    time_distribution["morning"] += 1
                elif 12 <= hour < 18:
                    time_distribution["afternoon"] += 1
                elif 18 <= hour < 22:
                    time_distribution["evening"] += 1
                else:
                    time_distribution["night"] += 1
            
            return {
                "status": "success",
                "date_range": {
                    "start": start_date or events[0].start_time.strftime("%Y-%m-%d"),
                    "end": end_date or events[-1].start_time.strftime("%Y-%m-%d")
                },
                "total_count": total_count,
                "total_hours": total_hours,
                "average_duration_minutes": round(total_minutes / total_count, 1),
                "events_by_date": dict(events_by_date),
                "events_by_type": dict(sorted(events_by_type.items(), key=lambda x: x[1], reverse=True)),
                "time_distribution": time_distribution,
                "busiest_day": max(events_by_date.items(), key=lambda x: x[1]) if events_by_date else None,
                "most_common_event": max(events_by_type.items(), key=lambda x: x[1]) if events_by_type else None
            }
    except Exception as e:
        return {"status": "error", "message": f"获取事件摘要失败：{str(e)}"}


def get_events_detail(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: str = "active"
) -> Dict[str, Any]:
    """获取事件详细列表
    
    返回指定时间范围内的所有事件详情
    """
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
        return {"status": "error", "message": f"获取事件详情失败：{str(e)}"}


def analyze_time_usage(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """分析时间使用情况
    
    分析工作、学习、娱乐等不同类型活动的时间占比
    """
    try:
        with get_db() as db:
            query = db.query(Event).filter(Event.status == "active")
            
            # 时间范围筛选
            if start_date:
                start_dt = parse_datetime(start_date)
                query = query.filter(Event.start_time >= start_dt)
            
            if end_date:
                end_dt = parse_datetime(end_date) + timedelta(days=1)
                query = query.filter(Event.start_time < end_dt)
            
            events = query.all()
            
            if not events:
                return {
                    "status": "success",
                    "message": "指定时间范围内没有事件",
                    "total_hours": 0
                }
            
            # 计算每个事件的时长
            event_durations = {}
            total_minutes = 0
            
            for event in events:
                duration = (event.end_time - event.start_time).total_seconds() / 60
                event_durations[event.title] = event_durations.get(event.title, 0) + duration
                total_minutes += duration
            
            total_hours = round(total_minutes / 60, 2)
            
            # 计算占比
            time_breakdown = {}
            for title, minutes in event_durations.items():
                hours = round(minutes / 60, 2)
                percentage = round((minutes / total_minutes) * 100, 1)
                time_breakdown[title] = {
                    "hours": hours,
                    "percentage": percentage
                }
            
            # 按时长排序
            sorted_breakdown = dict(sorted(time_breakdown.items(), key=lambda x: x[1]["hours"], reverse=True))
            
            return {
                "status": "success",
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "total_hours": total_hours,
                "time_breakdown": sorted_breakdown,
                "top_3_activities": list(sorted_breakdown.items())[:3]
            }
    except Exception as e:
        return {"status": "error", "message": f"分析时间使用失败：{str(e)}"}
