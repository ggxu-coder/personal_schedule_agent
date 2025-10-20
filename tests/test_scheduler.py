# tests/test_scheduler.py
# 说明：本文件包含对日程数据库与冲突检测的集成测试，用以验证
# - 创建事件与冲突检测逻辑（不允许重叠时返回 conflict）
# - 更新事件起止时间的正确性与校验
# - 列表查询与基本筛选行为
import importlib
import os
import tempfile

import pendulum
import pytest

from src.tools.calendar_db import EventCreate, EventUpdate, add_event, list_events, update_event


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    """为每个测试用例提供隔离的 SQLite 数据库。

    使用 tempfile 生成临时路径，并通过 monkeypatch 设置 `DATABASE_URL`，
    随后对 `src.storage.database` 与 `src.tools.calendar_db` 进行重新加载，
    确保每个测试在全新数据库上运行，避免状态污染。
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_scheduler.db")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

        import src.storage.database as database

        importlib.reload(database)
        database.init_db()

        import src.tools.calendar_db as calendar_db

        importlib.reload(calendar_db)
        calendar_db.init_db()
        yield


def test_add_event_and_conflict_detection():
    """验证新增事件成功与冲突检测生效。

    步骤：
    1) 创建一个 9:00-10:00 的事件，期望返回 success。
    2) 再创建一个 9:30-11:00 的事件，期望返回 conflict，且冲突数为 1。
    """
    start = pendulum.now().add(days=1).replace(hour=9, minute=0, second=0)
    end = start.add(hours=1)

    result = add_event(
        EventCreate(
            title="团队会议",
            description="讨论项目进展",
            start_time=start.to_iso8601_string(),
            end_time=end.to_iso8601_string(),
            tags=["team"],
        )
    )
    assert result["status"] == "success"
    assert result["event"]["title"] == "团队会议"

    conflict = add_event(
        EventCreate(
            title="冲突会议",
            start_time=start.add(minutes=30).to_iso8601_string(),
            end_time=end.add(hours=1).to_iso8601_string(),
        )
    )
    assert conflict["status"] == "conflict"
    assert len(conflict["conflicts"]) == 1


def test_update_event_time():
    """验证更新事件的起止时间成功，并返回新的时间戳。"""
    start = pendulum.now().add(days=2).replace(hour=14, minute=0, second=0)
    end = start.add(hours=2)

    created = add_event(
        EventCreate(
            title="代码评审",
            start_time=start.to_iso8601_string(),
            end_time=end.to_iso8601_string(),
        )
    )
    event_id = created["event"]["id"]

    new_start = start.add(hours=3)
    new_end = end.add(hours=3)

    updated = update_event(
        EventUpdate(
            event_id=event_id,
            start_time=new_start.to_iso8601_string(),
            end_time=new_end.to_iso8601_string(),
        )
    )
    assert updated["status"] == "success"
    assert updated["event"]["start_time"].startswith(new_start.to_iso8601_string()[:19])


def test_list_events():
    """验证事件列表查询返回成功且数量匹配。"""
    base = pendulum.now().add(days=3).replace(hour=8, minute=0, second=0)
    add_event(
        EventCreate(
            title="晨会",
            start_time=base.to_iso8601_string(),
            end_time=base.add(hours=1).to_iso8601_string(),
            tags=["daily"],
        )
    )
    add_event(
        EventCreate(
            title="午餐",
            start_time=base.add(hours=4).to_iso8601_string(),
            end_time=base.add(hours=5).to_iso8601_string(),
            tags=["personal"],
        )
    )

    results = list_events()
    assert results["status"] == "success"
    assert len(results["events"]) == 2