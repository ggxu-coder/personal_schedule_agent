from __future__ import annotations

from typing import Iterable, List, Optional

import pendulum
from pendulum import DateTime

from src.storage.models import Event


def detect_conflicts(
    candidate_start: DateTime,
    candidate_end: DateTime,
    events: Iterable[Event],
    exclude_event_id: Optional[str] = None,
) -> List[Event]:
    """检测与候选时间区间产生重叠的事件。

    参数：
    - candidate_start, candidate_end：候选事件的起止时间（pendulum.DateTime，需满足 candidate_start < candidate_end）。
    - events：待检测的事件集合，事件的 `start_time`/`end_time` 需为可转换为 pendulum 的 datetime。
    - exclude_event_id：可选，忽略具有此 ID 的事件（用于更新场景避免与自身比较）。

    返回：
    - 与候选区间有实际重叠（latest_start < earliest_end）的事件列表。
    """
    conflicts: List[Event] = []
    for event in events:
        if exclude_event_id and event.id == exclude_event_id:
            continue
        # 将模型中的时间字段转为 pendulum 实例，便于跨时区/比较操作
        start = pendulum.instance(event.start_time)
        end = pendulum.instance(event.end_time)
        # 两区间 [candidate_start, candidate_end) 与 [start, end) 的
        # 经典重叠判断：max(starts) < min(ends)
        latest_start = max(candidate_start, start)
        earliest_end = min(candidate_end, end)
        if latest_start < earliest_end:
            conflicts.append(event)
    return conflicts


