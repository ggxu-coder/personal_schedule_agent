"""PlanningAgent 测试。

测试任务规划 Agent 的功能：
- 任务分解和时间规划
- 空闲时间查询
- 用户偏好检索
- 规划结果生成
"""

import os
import tempfile
from unittest.mock import patch

import pendulum
import pytest

from src.agents.planning import PlanningAgentRunner, create_planning_graph
from src.graph.schema import TaskItem, PlannerOutput
from src.tools.calendar_db import add_event, EventCreate
from src.tools.preferences import store_preference


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    """为每个测试用例提供隔离的数据库。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_planning.db")
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
def planning_runner():
    """创建规划 Agent 运行器。"""
    return PlanningAgentRunner(provider="longcat")


def test_planning_graph_creation():
    """测试规划图创建。"""
    graph = create_planning_graph(provider="longcat")
    assert graph is not None
    assert hasattr(graph, "invoke")


def test_planning_runner_initialization():
    """测试规划运行器初始化。"""
    runner = PlanningAgentRunner(provider="longcat")
    assert runner is not None
    assert runner.state is not None
    assert runner.state["current_intent"] == "planning"


def test_task_item_model():
    """测试 TaskItem 模型。"""
    task = TaskItem(
        title="学习 Python",
        description="完成 Python 基础教程",
        tags=["学习", "编程"]
    )
    
    assert task.title == "学习 Python"
    assert task.description == "完成 Python 基础教程"
    assert task.tags == ["学习", "编程"]
    assert task.priority == 1  # 默认优先级
    assert task.task_id is not None


def test_planner_output_model():
    """测试 PlannerOutput 模型。"""
    tasks = [
        TaskItem(title="任务1", description="描述1"),
        TaskItem(title="任务2", description="描述2")
    ]
    
    output = PlannerOutput(
        tasks=tasks,
        conflicts=["时间冲突1"],
        notes="规划备注",
        free_slots=[{"start": "09:00", "end": "10:00"}]
    )
    
    assert len(output.tasks) == 2
    assert output.has_conflicts() is True
    assert output.notes == "规划备注"
    assert len(output.free_slots) == 1


def test_planning_with_empty_schedule(planning_runner):
    """测试空日程表的规划。"""
    # 添加一些偏好
    store_preference(
        user_id="test_user",
        preference_key="learning_time",
        preference_value="morning",
        description="喜欢上午学习"
    )
    
    # 模拟规划请求
    start_date = pendulum.now().add(days=1).format("YYYY-MM-DD")
    end_date = pendulum.now().add(days=7).format("YYYY-MM-DD")
    
    with patch.object(planning_runner.graph, 'invoke') as mock_invoke:
        # 模拟 LLM 回复
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "planning",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = planning_runner.plan_tasks(
            task_description="学习 Python 基础",
            start_date=start_date,
            end_date=end_date,
            user_id="test_user"
        )
        
        assert result["status"] == "success"


def test_planning_with_existing_events(planning_runner):
    """测试有现有事件的规划。"""
    # 添加一些现有事件
    tomorrow = pendulum.now().add(days=1)
    add_event(EventCreate(
        title="现有会议",
        start_time=tomorrow.replace(hour=10, minute=0).to_iso8601_string(),
        end_time=tomorrow.replace(hour=11, minute=0).to_iso8601_string(),
        tags=["会议"]
    ))
    
    # 添加偏好
    store_preference(
        user_id="test_user",
        preference_key="work_time",
        preference_value="morning",
        description="喜欢上午工作"
    )
    
    start_date = tomorrow.format("YYYY-MM-DD")
    end_date = tomorrow.add(days=1).format("YYYY-MM-DD")
    
    with patch.object(planning_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "planning",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = planning_runner.plan_tasks(
            task_description="完成项目报告",
            start_date=start_date,
            end_date=end_date,
            user_id="test_user"
        )
        
        assert result["status"] == "success"


def test_planning_feedback_handling(planning_runner):
    """测试规划反馈处理。"""
    # 添加初始规划
    planning_runner.state["planner_output"] = PlannerOutput(
        tasks=[TaskItem(title="初始任务")],
        conflicts=[],
        notes="初始规划",
        free_slots=[]
    )
    
    # 添加用户反馈
    planning_runner.update_feedback("需要调整时间安排")
    
    assert planning_runner.state["user_feedback"] == "需要调整时间安排"
    assert len(planning_runner.state["messages"]) > 1


def test_planning_error_handling(planning_runner):
    """测试规划错误处理。"""
    with patch.object(planning_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.side_effect = Exception("模拟错误")
        
        result = planning_runner.plan_tasks(
            task_description="测试任务",
            start_date="2024-01-01",
            end_date="2024-01-02",
            user_id="test_user"
        )
        
        # 应该捕获异常并返回错误状态
        assert result["status"] == "error"


def test_planning_with_preferences():
    """测试偏好对规划的影响。"""
    # 存储多个偏好
    store_preference(
        user_id="test_user",
        preference_key="morning_work",
        preference_value="true",
        description="喜欢上午工作",
        weight=0.9
    )
    
    store_preference(
        user_id="test_user",
        preference_key="break_time",
        preference_value="15min",
        description="需要15分钟休息时间",
        weight=0.7
    )
    
    runner = PlanningAgentRunner(provider="longcat")
    
    # 测试偏好检索
    from src.tools.preferences import retrieve_preferences
    preferences = retrieve_preferences(
        user_id="test_user",
        query="工作时间偏好"
    )
    
    assert preferences["status"] == "success"
    assert len(preferences["preferences"]) >= 1


def test_planning_conflict_detection():
    """测试规划中的冲突检测。"""
    tomorrow = pendulum.now().add(days=1)
    
    # 添加重叠事件
    add_event(EventCreate(
        title="会议A",
        start_time=tomorrow.replace(hour=9, minute=0).to_iso8601_string(),
        end_time=tomorrow.replace(hour=10, minute=0).to_iso8601_string()
    ))
    
    add_event(EventCreate(
        title="会议B",
        start_time=tomorrow.replace(hour=9, minute=30).to_iso8601_string(),
        end_time=tomorrow.replace(hour=10, minute=30).to_iso8601_string()
    ))
    
    # 查询空闲时间
    from src.tools.calendar_db import get_free_slots
    free_slots = get_free_slots(
        start_date=tomorrow.format("YYYY-MM-DD"),
        end_date=tomorrow.format("YYYY-MM-DD")
    )
    
    assert free_slots["status"] == "success"
    # 应该有空闲时间段（除了重叠的时间）
    assert "free_slots" in free_slots


def test_planning_task_decomposition():
    """测试任务分解功能。"""
    runner = PlanningAgentRunner(provider="longcat")
    
    # 测试复杂任务分解
    complex_task = "完成一个完整的 Web 应用项目，包括前端、后端、数据库设计和部署"
    
    with patch.object(runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "planning",
            "planner_output": PlannerOutput(
                tasks=[
                    TaskItem(title="前端开发", description="React 组件开发"),
                    TaskItem(title="后端开发", description="API 接口开发"),
                    TaskItem(title="数据库设计", description="数据模型设计"),
                    TaskItem(title="部署配置", description="生产环境部署")
                ],
                conflicts=[],
                notes="项目分解完成",
                free_slots=[]
            ),
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = runner.plan_tasks(
            task_description=complex_task,
            start_date="2024-01-01",
            end_date="2024-01-07",
            user_id="test_user"
        )
        
        assert result["status"] == "success"
        planning_output = runner.get_planning_output()
        if planning_output:
            assert len(planning_output.tasks) == 4
