"""SummaryAgent 测试。

测试日程总结 Agent 的功能：
- 事件统计摘要生成
- 时间分布分析
- 用户偏好对比
- 优化建议生成
"""

import os
import tempfile
from unittest.mock import patch

import pendulum
import pytest

from src.agents.summary import SummaryAgentRunner, create_summary_graph
from src.graph.schema import SummaryOutput, EventSummary
from src.tools.calendar_db import add_event, EventCreate
from src.tools.preferences import store_preference


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    """为每个测试用例提供隔离的数据库。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_summary.db")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        
        # 重新加载数据库模块
        import importlib
        import src.storage.database as database
        import src.tools.calendar_db as calendar_db
        
        importlib.reload(database)
        database.init_db()
        
        importlib.reload(calendar_db)
        calendar_db.init_db()
        
        yield


@pytest.fixture
def summary_runner():
    """创建总结 Agent 运行器。"""
    return SummaryAgentRunner(provider="longcat")


def test_summary_graph_creation():
    """测试总结图创建。"""
    graph = create_summary_graph(provider="longcat")
    assert graph is not None
    assert hasattr(graph, "invoke")


def test_summary_runner_initialization():
    """测试总结运行器初始化。"""
    runner = SummaryAgentRunner(provider="longcat")
    assert runner is not None
    assert runner.state is not None
    assert runner.state["current_intent"] == "summary"


def test_summary_output_model():
    """测试 SummaryOutput 模型。"""
    output = SummaryOutput(
        period="本周",
        summary_text="本周共完成15个事件，学习时间占40%",
        recommendations=["增加运动时间", "优化学习效率"],
        stats={"total_events": 15, "learning_hours": 20}
    )
    
    assert output.period == "本周"
    assert "15个事件" in output.summary_text
    assert len(output.recommendations) == 2
    assert output.get_recommendation_count() == 2
    assert output.stats["total_events"] == 15


def test_event_summary_model():
    """测试 EventSummary 模型。"""
    summary = EventSummary(
        total_events=10,
        events_by_tag={"学习": 5, "工作": 3, "运动": 2},
        time_distribution={"morning": 4, "afternoon": 4, "evening": 2},
        avg_duration_minutes=60.5
    )
    
    assert summary.total_events == 10
    assert summary.events_by_tag["学习"] == 5
    assert summary.time_distribution["morning"] == 4
    assert summary.avg_duration_minutes == 60.5
    
    # 测试获取热门标签
    top_tags = summary.get_top_tags(limit=2)
    assert len(top_tags) == 2
    assert top_tags[0][0] == "学习"  # 最多的标签


def test_summary_with_empty_schedule(summary_runner):
    """测试空日程表的总结。"""
    start_date = pendulum.now().subtract(days=7).format("YYYY-MM-DD")
    end_date = pendulum.now().format("YYYY-MM-DD")
    
    with patch.object(summary_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "summary",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = summary_runner.generate_summary(
            period_type="weekly",
            start_date=start_date,
            end_date=end_date,
            user_id="test_user"
        )
        
        assert result["status"] == "success"


def test_summary_with_events(summary_runner):
    """测试有事件的总结。"""
    # 添加一些测试事件
    base_date = pendulum.now().subtract(days=3)
    
    # 添加不同类型的事件
    add_event(EventCreate(
        title="学习 Python",
        start_time=base_date.replace(hour=9, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=11, minute=0).to_iso8601_string(),
        tags=["学习", "编程"]
    ))
    
    add_event(EventCreate(
        title="团队会议",
        start_time=base_date.replace(hour=14, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=15, minute=0).to_iso8601_string(),
        tags=["工作", "会议"]
    ))
    
    add_event(EventCreate(
        title="运动",
        start_time=base_date.replace(hour=18, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=19, minute=0).to_iso8601_string(),
        tags=["运动", "健康"]
    ))
    
    # 添加偏好
    store_preference(
        user_id="test_user",
        preference_key="learning_time",
        preference_value="morning",
        description="喜欢上午学习"
    )
    
    start_date = base_date.format("YYYY-MM-DD")
    end_date = pendulum.now().format("YYYY-MM-DD")
    
    with patch.object(summary_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "summary",
            "planner_output": None,
            "summary_output": SummaryOutput(
                period="最近几天",
                summary_text="共完成3个事件，包括学习、工作和运动",
                recommendations=["保持学习节奏", "增加运动时间"],
                stats={"total_events": 3}
            ),
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = summary_runner.generate_summary(
            period_type="daily",
            start_date=start_date,
            end_date=end_date,
            user_id="test_user"
        )
        
        assert result["status"] == "success"


def test_summary_trend_analysis(summary_runner):
    """测试趋势分析功能。"""
    # 添加多个事件用于趋势分析
    base_date = pendulum.now().subtract(days=7)
    
    for i in range(5):
        event_date = base_date.add(days=i)
        add_event(EventCreate(
            title=f"学习任务 {i+1}",
            start_time=event_date.replace(hour=9, minute=0).to_iso8601_string(),
            end_time=event_date.replace(hour=10, minute=0).to_iso8601_string(),
            tags=["学习"]
        ))
    
    start_date = base_date.format("YYYY-MM-DD")
    end_date = pendulum.now().format("YYYY-MM-DD")
    
    trends = summary_runner.analyze_trends(start_date, end_date)
    
    assert trends["status"] == "success"
    assert trends["trends"]["total_events"] == 5
    assert trends["trends"]["most_common_tags"]["学习"] == 5


def test_summary_error_handling(summary_runner):
    """测试总结错误处理。"""
    with patch.object(summary_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.side_effect = Exception("模拟错误")
        
        result = summary_runner.generate_summary(
            period_type="weekly",
            start_date="2024-01-01",
            end_date="2024-01-07",
            user_id="test_user"
        )
        
        assert result["status"] == "error"


def test_summary_with_preferences():
    """测试偏好对总结的影响。"""
    # 存储多个偏好
    store_preference(
        user_id="test_user",
        preference_key="ideal_schedule",
        preference_value="morning_work",
        description="理想的工作时间是上午",
        weight=0.9
    )
    
    store_preference(
        user_id="test_user",
        preference_key="break_preference",
        preference_value="every_2_hours",
        description="每2小时需要休息",
        weight=0.7
    )
    
    runner = SummaryAgentRunner(provider="longcat")
    
    # 测试偏好检索
    from src.tools.preferences import retrieve_preferences
    preferences = retrieve_preferences(
        user_id="test_user",
        query="工作时间偏好"
    )
    
    assert preferences["status"] == "success"
    assert len(preferences["preferences"]) >= 1


def test_summary_period_types(summary_runner):
    """测试不同时间范围的总结。"""
    period_types = ["daily", "weekly", "monthly"]
    
    for period_type in period_types:
        with patch.object(summary_runner.graph, 'invoke') as mock_invoke:
            mock_invoke.return_value = {
                "messages": [],
                "current_intent": "summary",
                "planner_output": None,
                "summary_output": SummaryOutput(
                    period=period_type,
                    summary_text=f"{period_type}总结",
                    recommendations=[],
                    stats={}
                ),
                "user_feedback": None,
                "pending_tasks": [],
                "preferences": [],
                "user_id": "test_user"
            }
            
            result = summary_runner.generate_summary(
                period_type=period_type,
                start_date="2024-01-01",
                end_date="2024-01-07",
                user_id="test_user"
            )
            
            assert result["status"] == "success"


def test_summary_statistics_calculation():
    """测试统计计算功能。"""
    from src.tools.calendar_db import get_events_summary
    
    # 添加测试事件
    base_date = pendulum.now().subtract(days=2)
    
    add_event(EventCreate(
        title="学习1",
        start_time=base_date.replace(hour=9, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=10, minute=0).to_iso8601_string(),
        tags=["学习"]
    ))
    
    add_event(EventCreate(
        title="学习2",
        start_time=base_date.replace(hour=10, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=11, minute=0).to_iso8601_string(),
        tags=["学习"]
    ))
    
    add_event(EventCreate(
        title="工作",
        start_time=base_date.replace(hour=14, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=15, minute=0).to_iso8601_string(),
        tags=["工作"]
    ))
    
    start_date = base_date.format("YYYY-MM-DD")
    end_date = pendulum.now().format("YYYY-MM-DD")
    
    summary = get_events_summary(start_date, end_date)
    
    assert summary["status"] == "success"
    assert summary["summary"]["total_events"] == 3
    assert summary["summary"]["events_by_tag"]["学习"] == 2
    assert summary["summary"]["events_by_tag"]["工作"] == 1
    assert summary["summary"]["avg_duration_minutes"] == 60.0


def test_summary_recommendations():
    """测试优化建议生成。"""
    runner = SummaryAgentRunner(provider="longcat")
    
    # 模拟有偏好的总结
    runner.state["summary_output"] = SummaryOutput(
        period="本周",
        summary_text="本周学习时间较少，工作时间较多",
        recommendations=[
            "增加学习时间",
            "平衡工作与学习",
            "保持运动习惯"
        ],
        stats={"learning_hours": 5, "work_hours": 20}
    )
    
    output = runner.get_summary_output()
    assert output is not None
    assert len(output.recommendations) == 3
    assert "增加学习时间" in output.recommendations
