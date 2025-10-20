"""工作流集成测试。

测试完整的多智能体工作流：
- 端到端流程测试
- Agent 间协作
- 状态传递
- 错误恢复
"""

import os
import tempfile
from unittest.mock import patch

import pendulum
import pytest

from src.graph.workflow import (
    MultiAgentRunner,
    create_orchestrator_workflow,
    create_simple_workflow,
    create_planning_workflow,
)
from src.tools.calendar_db import add_event, EventCreate
from src.tools.preferences import store_preference


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    """为每个测试用例提供隔离的数据库。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_workflow.db")
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
def multi_agent_runner():
    """创建多智能体运行器。"""
    return MultiAgentRunner(workflow_type="full", provider="longcat")


def test_workflow_creation():
    """测试工作流创建。"""
    # 测试完整工作流
    full_workflow = create_orchestrator_workflow(provider="longcat")
    assert full_workflow is not None
    
    # 测试简化工作流
    simple_workflow = create_simple_workflow(provider="longcat")
    assert simple_workflow is not None
    
    # 测试规划工作流
    planning_workflow = create_planning_workflow(provider="longcat")
    assert planning_workflow is not None


def test_multi_agent_runner_initialization():
    """测试多智能体运行器初始化。"""
    runner = MultiAgentRunner(workflow_type="full", provider="longcat")
    assert runner.provider == "longcat"
    assert runner.workflow_type == "full"
    assert runner.state is not None
    assert runner.state["current_intent"] == ""


def test_scheduling_workflow(multi_agent_runner):
    """测试日程管理工作流。"""
    # 模拟完整的调度流程
    with patch.object(multi_agent_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "scheduling",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = multi_agent_runner.process_input(
            "明天上午9点添加团队会议",
            user_id="test_user"
        )
        
        assert result["status"] == "success"
        assert result["intent"] == "scheduling"


def test_planning_workflow(multi_agent_runner):
    """测试任务规划工作流。"""
    # 添加一些偏好
    store_preference(
        user_id="test_user",
        preference_key="learning_time",
        preference_value="morning",
        description="喜欢上午学习"
    )
    
    with patch.object(multi_agent_runner.graph, 'invoke') as mock_invoke:
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
        
        result = multi_agent_runner.process_input(
            "帮我规划下周的学习计划",
            user_id="test_user"
        )
        
        assert result["status"] == "success"
        assert result["intent"] == "planning"


def test_summary_workflow(multi_agent_runner):
    """测试总结分析工作流。"""
    # 添加一些测试事件
    base_date = pendulum.now().subtract(days=3)
    
    add_event(EventCreate(
        title="学习任务",
        start_time=base_date.replace(hour=9, minute=0).to_iso8601_string(),
        end_time=base_date.replace(hour=11, minute=0).to_iso8601_string(),
        tags=["学习"]
    ))
    
    with patch.object(multi_agent_runner.graph, 'invoke') as mock_invoke:
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
        
        result = multi_agent_runner.process_input(
            "总结一下本周的表现",
            user_id="test_user"
        )
        
        assert result["status"] == "success"
        assert result["intent"] == "summary"


def test_preference_workflow(multi_agent_runner):
    """测试偏好管理工作流。"""
    with patch.object(multi_agent_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "preference",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = multi_agent_runner.process_input(
            "我喜欢上午学习",
            user_id="test_user"
        )
        
        assert result["status"] == "success"
        assert result["intent"] == "preference"


def test_workflow_error_handling(multi_agent_runner):
    """测试工作流错误处理。"""
    with patch.object(multi_agent_runner.graph, 'invoke') as mock_invoke:
        mock_invoke.side_effect = Exception("工作流错误")
        
        result = multi_agent_runner.process_input(
            "测试输入",
            user_id="test_user"
        )
        
        assert result["status"] == "error"
        assert "工作流错误" in result["message"]


def test_state_management(multi_agent_runner):
    """测试状态管理。"""
    # 测试状态获取
    state = multi_agent_runner.get_state()
    assert state is not None
    assert "messages" in state
    assert "current_intent" in state
    
    # 测试状态重置
    multi_agent_runner.reset_state()
    state = multi_agent_runner.get_state()
    assert state["current_intent"] == ""
    assert state["user_id"] == "default_user"


def test_different_workflow_types():
    """测试不同工作流类型。"""
    # 测试完整工作流
    full_runner = MultiAgentRunner(workflow_type="full", provider="longcat")
    assert full_runner.workflow_type == "full"
    
    # 测试简化工作流
    simple_runner = MultiAgentRunner(workflow_type="simple", provider="longcat")
    assert simple_runner.workflow_type == "simple"
    
    # 测试规划工作流
    planning_runner = MultiAgentRunner(workflow_type="planning", provider="longcat")
    assert planning_runner.workflow_type == "planning"
    
    # 测试无效工作流类型
    with pytest.raises(ValueError):
        MultiAgentRunner(workflow_type="invalid", provider="longcat")


def test_agent_collaboration():
    """测试 Agent 间协作。"""
    runner = MultiAgentRunner(workflow_type="planning", provider="longcat")
    
    # 模拟规划到调度的协作流程
    with patch.object(runner.graph, 'invoke') as mock_invoke:
        # 第一次调用：规划
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
        
        result1 = runner.process_input(
            "帮我规划学习计划",
            user_id="test_user"
        )
        
        assert result1["status"] == "success"
        
        # 第二次调用：确认并执行
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "scheduling",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result2 = runner.process_input(
            "确认添加这些任务",
            user_id="test_user"
        )
        
        assert result2["status"] == "success"


def test_user_context_persistence():
    """测试用户上下文持久化。"""
    runner = MultiAgentRunner(workflow_type="full", provider="longcat")
    
    # 第一次交互
    with patch.object(runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "preference",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        runner.process_input("我喜欢上午学习", user_id="test_user")
        
        # 检查用户ID是否保持
        assert runner.state["user_id"] == "test_user"
        
        # 第二次交互
        runner.process_input("帮我规划学习计划", user_id="test_user")
        
        # 用户ID应该继续保持
        assert runner.state["user_id"] == "test_user"


def test_message_history():
    """测试消息历史管理。"""
    runner = MultiAgentRunner(workflow_type="full", provider="longcat")
    
    with patch.object(runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "scheduling",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        # 发送多条消息
        runner.process_input("第一条消息", user_id="test_user")
        runner.process_input("第二条消息", user_id="test_user")
        
        # 检查消息历史
        messages = runner.state["messages"]
        assert len(messages) >= 2  # 至少包含用户消息


def test_workflow_performance():
    """测试工作流性能。"""
    import time
    
    runner = MultiAgentRunner(workflow_type="simple", provider="longcat")
    
    with patch.object(runner.graph, 'invoke') as mock_invoke:
        mock_invoke.return_value = {
            "messages": [],
            "current_intent": "scheduling",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        start_time = time.time()
        
        for i in range(5):
            runner.process_input(f"测试消息 {i}", user_id="test_user")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 性能测试：5次调用应该在合理时间内完成
        assert duration < 10.0  # 10秒内完成


def test_concurrent_workflow():
    """测试并发工作流处理。"""
    import threading
    import time
    
    runner = MultiAgentRunner(workflow_type="simple", provider="longcat")
    results = []
    
    def process_input_thread(user_id, message):
        with patch.object(runner.graph, 'invoke') as mock_invoke:
            mock_invoke.return_value = {
                "messages": [],
                "current_intent": "scheduling",
                "planner_output": None,
                "summary_output": None,
                "user_feedback": None,
                "pending_tasks": [],
                "preferences": [],
                "user_id": user_id
            }
            
            result = runner.process_input(message, user_id=user_id)
            results.append(result)
    
    # 创建多个线程
    threads = []
    for i in range(3):
        thread = threading.Thread(
            target=process_input_thread,
            args=(f"user_{i}", f"消息_{i}")
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    assert len(results) == 3
    for result in results:
        assert result["status"] == "success"
