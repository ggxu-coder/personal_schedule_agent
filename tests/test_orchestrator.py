"""OrchestratorAgent 测试。

测试用户意图理解与 Agent 路由功能：
- 意图识别准确性
- 参数提取
- Agent 路由逻辑
- 错误处理
"""

import json
from unittest.mock import patch

import pytest

from src.agents.orchestrator import (
    OrchestratorAgent,
    IntentResult,
    classify_intent,
    route_by_intent,
    check_user_confirmation,
)


def test_intent_result_model():
    """测试 IntentResult 模型。"""
    result = IntentResult(
        intent="scheduling",
        confidence=0.95,
        params={"time": "明天上午9点", "title": "会议"},
        reasoning="用户明确提到添加会议和时间"
    )
    
    assert result.intent == "scheduling"
    assert result.confidence == 0.95
    assert result.params["time"] == "明天上午9点"
    assert "会议" in result.reasoning


def test_orchestrator_agent_initialization():
    """测试 OrchestratorAgent 初始化。"""
    agent = OrchestratorAgent(provider="longcat")
    assert agent.provider == "longcat"
    assert agent.llm is not None


def test_intent_classification_scheduling():
    """测试日程管理意图识别。"""
    test_cases = [
        "请帮我添加一个明天上午9点的会议",
        "删除下周三的约会",
        "修改明天下午2点的会议时间",
        "查看明天的日程安排",
        "明天上午10点有个团队会议"
    ]
    
    agent = OrchestratorAgent(provider="longcat")
    
    for user_input in test_cases:
        with patch.object(agent.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value.content = json.dumps({
                "intent": "scheduling",
                "confidence": 0.9,
                "params": {"action": "add", "time": "明天上午9点"},
                "reasoning": "用户要求管理日程"
            })
            
            result = agent.classify_intent(user_input)
            assert result.intent == "scheduling"
            assert result.confidence > 0.5


def test_intent_classification_planning():
    """测试任务规划意图识别。"""
    test_cases = [
        "帮我规划下周的学习计划",
        "制定一个项目时间表",
        "安排一下这个月的任务",
        "帮我分解这个项目",
        "规划一下学习路线"
    ]
    
    agent = OrchestratorAgent(provider="longcat")
    
    for user_input in test_cases:
        with patch.object(agent.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value.content = json.dumps({
                "intent": "planning",
                "confidence": 0.9,
                "params": {"task": "学习计划", "period": "下周"},
                "reasoning": "用户要求规划任务"
            })
            
            result = agent.classify_intent(user_input)
            assert result.intent == "planning"
            assert result.confidence > 0.5


def test_intent_classification_summary():
    """测试总结分析意图识别。"""
    test_cases = [
        "总结一下本周的表现",
        "分析这个月的时间分配",
        "回顾一下最近的工作",
        "统计一下学习时间",
        "总结本周的日程"
    ]
    
    agent = OrchestratorAgent(provider="longcat")
    
    for user_input in test_cases:
        with patch.object(agent.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value.content = json.dumps({
                "intent": "summary",
                "confidence": 0.9,
                "params": {"period": "本周", "type": "表现"},
                "reasoning": "用户要求总结分析"
            })
            
            result = agent.classify_intent(user_input)
            assert result.intent == "summary"
            assert result.confidence > 0.5


def test_intent_classification_preference():
    """测试偏好管理意图识别。"""
    test_cases = [
        "我喜欢上午学习",
        "设置工作时间为9点到18点",
        "我习惯下午开会",
        "记录一下我的偏好",
        "我喜欢晚上运动"
    ]
    
    agent = OrchestratorAgent(provider="longcat")
    
    for user_input in test_cases:
        with patch.object(agent.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value.content = json.dumps({
                "intent": "preference",
                "confidence": 0.9,
                "params": {"preference": "上午学习"},
                "reasoning": "用户表达个人偏好"
            })
            
            result = agent.classify_intent(user_input)
            assert result.intent == "preference"
            assert result.confidence > 0.5


def test_fallback_intent_classification():
    """测试备用意图分类（基于关键词规则）。"""
    agent = OrchestratorAgent(provider="longcat")
    
    # 测试日程管理关键词
    result = agent._fallback_intent_classification("明天添加会议")
    assert result.intent == "scheduling"
    
    # 测试规划关键词
    result = agent._fallback_intent_classification("帮我规划学习计划")
    assert result.intent == "planning"
    
    # 测试总结关键词
    result = agent._fallback_intent_classification("总结本周表现")
    assert result.intent == "summary"
    
    # 测试偏好关键词
    result = agent._fallback_intent_classification("我喜欢上午学习")
    assert result.intent == "preference"


def test_parameter_extraction():
    """测试参数提取功能。"""
    agent = OrchestratorAgent(provider="longcat")
    
    # 测试时间参数提取
    params = agent.extract_parameters("明天上午9点添加会议", "scheduling")
    assert "time_mentions" in params
    
    # 测试任务描述提取
    params = agent.extract_parameters("帮我规划学习计划", "planning")
    assert params["task_description"] == "帮我规划学习计划"
    
    # 测试时间范围提取
    params = agent.extract_parameters("总结本周的表现", "summary")
    assert params["period"] == "weekly"
    
    # 测试偏好描述提取
    params = agent.extract_parameters("我喜欢上午学习", "preference")
    assert params["preference_description"] == "我喜欢上午学习"


def test_agent_routing():
    """测试 Agent 路由逻辑。"""
    agent = OrchestratorAgent(provider="longcat")
    
    # 测试各种意图的路由
    test_cases = [
        ("scheduling", "scheduler"),
        ("planning", "planner"),
        ("summary", "summary"),
        ("preference", "preference_manager"),
        ("unknown", "scheduler")  # 默认路由
    ]
    
    for intent, expected_agent in test_cases:
        result = IntentResult(
            intent=intent,
            confidence=0.9,
            params={},
            reasoning="测试"
        )
        
        routed_agent = agent.route_to_agent(result)
        assert routed_agent == expected_agent


def test_route_by_intent_function():
    """测试路由函数。"""
    from src.graph.state import AgentState
    
    test_cases = [
        ("scheduling", "scheduler"),
        ("planning", "planner"),
        ("summary", "summary"),
        ("preference", "preference_manager"),
        ("unknown", "scheduler")
    ]
    
    for intent, expected_route in test_cases:
        state = {"current_intent": intent}
        route = route_by_intent(state)
        assert route == expected_route


def test_user_confirmation_check():
    """测试用户确认检查。"""
    from src.graph.state import AgentState
    from langchain_core.messages import HumanMessage
    
    # 测试确认
    state = {"messages": [HumanMessage(content="确认")]}
    result = check_user_confirmation(state)
    assert result == "confirmed"
    
    # 测试修改
    state = {"messages": [HumanMessage(content="需要修改")]}
    result = check_user_confirmation(state)
    assert result == "revise"
    
    # 测试结束
    state = {"messages": [HumanMessage(content="好的")]}
    result = check_user_confirmation(state)
    assert result == "end"


def test_process_user_input():
    """测试用户输入处理。"""
    agent = OrchestratorAgent(provider="longcat")
    
    with patch.object(agent, 'classify_intent') as mock_classify:
        mock_classify.return_value = IntentResult(
            intent="scheduling",
            confidence=0.9,
            params={"time": "明天上午9点"},
            reasoning="用户要求添加会议"
        )
        
        state = {
            "messages": [],
            "current_intent": "",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "test_user"
        }
        
        result = agent.process_user_input("明天上午9点添加会议", state)
        
        assert result["status"] == "success"
        assert result["intent_result"]["intent"] == "scheduling"
        assert result["target_agent"] == "scheduler"
        assert state["current_intent"] == "scheduling"


def test_error_handling():
    """测试错误处理。"""
    agent = OrchestratorAgent(provider="longcat")
    
    # 测试 LLM 调用失败
    with patch.object(agent.llm, 'invoke') as mock_invoke:
        mock_invoke.side_effect = Exception("API 错误")
        
        result = agent.classify_intent("测试输入")
        assert result.intent == "error"
        assert result.confidence == 0.0
        assert "API 错误" in result.params["error"]


def test_json_parsing_error():
    """测试 JSON 解析错误处理。"""
    agent = OrchestratorAgent(provider="longcat")
    
    with patch.object(agent.llm, 'invoke') as mock_invoke:
        mock_invoke.return_value.content = "这不是有效的 JSON"
        
        result = agent.classify_intent("测试输入")
        # 应该使用备用分类方法
        assert result.intent in ["scheduling", "planning", "summary", "preference"]


def test_confidence_threshold():
    """测试置信度阈值。"""
    agent = OrchestratorAgent(provider="longcat")
    
    # 测试高置信度
    result = IntentResult(
        intent="scheduling",
        confidence=0.95,
        params={},
        reasoning="高置信度"
    )
    
    assert result.confidence > 0.8
    
    # 测试低置信度
    result = IntentResult(
        intent="unknown",
        confidence=0.3,
        params={},
        reasoning="低置信度"
    )
    
    assert result.confidence < 0.5


def test_intent_ambiguity():
    """测试意图歧义处理。"""
    agent = OrchestratorAgent(provider="longcat")
    
    # 测试模糊输入
    ambiguous_inputs = [
        "明天",
        "帮我",
        "好的",
        "谢谢"
    ]
    
    for user_input in ambiguous_inputs:
        with patch.object(agent.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value.content = json.dumps({
                "intent": "unknown",
                "confidence": 0.3,
                "params": {},
                "reasoning": "输入不够明确"
            })
            
            result = agent.classify_intent(user_input)
            # 应该能够处理模糊输入
            assert result.intent is not None
            assert result.confidence >= 0.0
