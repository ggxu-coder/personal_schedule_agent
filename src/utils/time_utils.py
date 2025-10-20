from __future__ import annotations

"""时间处理工具函数。

提供时间解析、计算和格式化功能：
- 自然语言时间解析
- 时间范围计算
- 时长计算
- 时间段生成
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import pendulum
from pendulum import DateTime, Period


def parse_natural_time(text: str, reference_date: Optional[DateTime] = None) -> Optional[DateTime]:
    """解析自然语言时间描述。
    
    Args:
        text: 时间描述文本
        reference_date: 参考日期（默认为当前时间）
        
    Returns:
        解析后的 DateTime 对象，解析失败返回 None
    """
    if reference_date is None:
        reference_date = pendulum.now()
    
    text = text.strip().lower()
    
    # 相对时间解析
    relative_patterns = {
        r"明天": lambda ref: ref.add(days=1),
        r"后天": lambda ref: ref.add(days=2),
        r"今天": lambda ref: ref,
        r"昨天": lambda ref: ref.subtract(days=1),
        r"下周": lambda ref: ref.add(weeks=1),
        r"上周": lambda ref: ref.subtract(weeks=1),
        r"下个月": lambda ref: ref.add(months=1),
        r"上个月": lambda ref: ref.subtract(months=1),
    }
    
    for pattern, func in relative_patterns.items():
        if re.search(pattern, text):
            base_date = func(reference_date)
            
            # 提取具体时间
            time_match = re.search(r"(\d{1,2}):?(\d{0,2})", text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                
                # 处理上午/下午
                if "下午" in text or "pm" in text:
                    if hour < 12:
                        hour += 12
                elif "上午" in text or "am" in text:
                    if hour == 12:
                        hour = 0
                
                return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # 如果没有具体时间，返回日期的开始
            return base_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 绝对时间解析
    try:
        return pendulum.parse(text)
    except Exception:
        return None


def calculate_duration(start: DateTime, end: DateTime) -> int:
    """计算两个时间点之间的时长（分钟）。
    
    Args:
        start: 开始时间
        end: 结束时间
        
    Returns:
        时长（分钟）
    """
    if end <= start:
        return 0
    
    period = end - start
    return int(period.total_seconds() / 60)


def get_period_range(period_type: str, reference_date: Optional[DateTime] = None) -> Tuple[DateTime, DateTime]:
    """获取指定时间范围的起止时间。
    
    Args:
        period_type: 时间类型（daily/weekly/monthly）
        reference_date: 参考日期（默认为当前时间）
        
    Returns:
        (开始时间, 结束时间) 元组
    """
    if reference_date is None:
        reference_date = pendulum.now()
    
    if period_type == "daily":
        start = reference_date.start_of("day")
        end = reference_date.end_of("day")
    
    elif period_type == "weekly":
        start = reference_date.start_of("week")
        end = reference_date.end_of("week")
    
    elif period_type == "monthly":
        start = reference_date.start_of("month")
        end = reference_date.end_of("month")
    
    else:
        # 默认返回当天
        start = reference_date.start_of("day")
        end = reference_date.end_of("day")
    
    return start, end


def format_duration(minutes: int) -> str:
    """格式化时长显示。
    
    Args:
        minutes: 时长（分钟）
        
    Returns:
        格式化的时长字符串
    """
    if minutes < 60:
        return f"{minutes}分钟"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours}小时"
    else:
        return f"{hours}小时{remaining_minutes}分钟"


def get_working_hours_range(
    start_date: DateTime, 
    end_date: DateTime,
    work_start_hour: int = 9,
    work_end_hour: int = 18
) -> List[Dict[str, str]]:
    """获取工作日的工作时间范围。
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        work_start_hour: 工作开始时间（小时）
        work_end_hour: 工作结束时间（小时）
        
    Returns:
        工作时间范围列表
    """
    working_ranges = []
    current = start_date.start_of("day")
    
    while current <= end_date:
        # 跳过周末（可选）
        if current.weekday() < 5:  # 0-4 是周一到周五
            work_start = current.replace(hour=work_start_hour, minute=0, second=0)
            work_end = current.replace(hour=work_end_hour, minute=0, second=0)
            
            working_ranges.append({
                "start": work_start.to_iso8601_string(),
                "end": work_end.to_iso8601_string(),
                "date": current.format("YYYY-MM-DD"),
                "day_of_week": current.format("dddd")
            })
        
        current = current.add(days=1)
    
    return working_ranges


def parse_time_range(text: str) -> Optional[Tuple[DateTime, DateTime]]:
    """解析时间范围描述。
    
    Args:
        text: 时间范围描述（如"明天上午9点到11点"）
        
    Returns:
        (开始时间, 结束时间) 元组，解析失败返回 None
    """
    # 查找时间点
    time_pattern = r"(\d{1,2}):?(\d{0,2})\s*[到至-]\s*(\d{1,2}):?(\d{0,2})"
    match = re.search(time_pattern, text)
    
    if not match:
        return None
    
    try:
        # 解析开始时间
        start_hour = int(match.group(1))
        start_minute = int(match.group(2)) if match.group(2) else 0
        
        # 解析结束时间
        end_hour = int(match.group(3))
        end_minute = int(match.group(4)) if match.group(4) else 0
        
        # 确定日期
        base_date = parse_natural_time(text.split(":")[0]) or pendulum.now()
        
        # 处理上午/下午
        if "下午" in text or "pm" in text:
            if start_hour < 12:
                start_hour += 12
            if end_hour < 12:
                end_hour += 12
        
        start_time = base_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end_time = base_date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        return start_time, end_time
        
    except Exception:
        return None


def is_business_hours(dt: DateTime, work_start: int = 9, work_end: int = 18) -> bool:
    """检查时间是否在工作时间内。
    
    Args:
        dt: 要检查的时间
        work_start: 工作开始时间（小时）
        work_end: 工作结束时间（小时）
        
    Returns:
        是否在工作时间内
    """
    hour = dt.hour
    return work_start <= hour < work_end


def get_next_available_time(
    preferred_time: DateTime,
    duration_minutes: int,
    work_start: int = 9,
    work_end: int = 18
) -> DateTime:
    """获取下一个可用时间。
    
    Args:
        preferred_time: 首选时间
        duration_minutes: 需要的时间长度（分钟）
        work_start: 工作开始时间
        work_end: 工作结束时间
        
    Returns:
        下一个可用时间
    """
    # 如果首选时间在工作时间内，直接返回
    if is_business_hours(preferred_time, work_start, work_end):
        return preferred_time
    
    # 否则找到下一个工作时间的开始
    if preferred_time.hour < work_start:
        return preferred_time.replace(hour=work_start, minute=0, second=0, microsecond=0)
    else:
        # 第二天的工作时间开始
        next_day = preferred_time.add(days=1)
        return next_day.replace(hour=work_start, minute=0, second=0, microsecond=0)


def time_to_natural_language(dt: DateTime) -> str:
    """将时间转换为自然语言描述。
    
    Args:
        dt: 时间对象
        
    Returns:
        自然语言描述
    """
    now = pendulum.now()
    
    # 相对时间描述
    if dt.date() == now.date():
        return f"今天 {dt.format('HH:mm')}"
    elif dt.date() == now.add(days=1).date():
        return f"明天 {dt.format('HH:mm')}"
    elif dt.date() == now.subtract(days=1).date():
        return f"昨天 {dt.format('HH:mm')}"
    else:
        return dt.format("YYYY年MM月DD日 HH:mm")


def validate_time_input(time_str: str) -> Dict[str, Any]:
    """验证时间输入格式。
    
    Args:
        time_str: 时间字符串
        
    Returns:
        验证结果
    """
    try:
        dt = pendulum.parse(time_str)
        return {
            "valid": True,
            "parsed_time": dt,
            "message": "时间格式正确"
        }
    except Exception as e:
        return {
            "valid": False,
            "parsed_time": None,
            "message": f"时间格式错误: {str(e)}"
        }
