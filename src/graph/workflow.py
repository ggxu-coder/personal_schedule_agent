from __future__ import annotations

"""完整的 LangGraph 工作流实现。

构建多智能体协作的完整工作流：
- OrchestratorAgent：意图识别与路由
- SchedulerAgent：日程管理
- PlanningAgent：任务规划
- SummaryAgent：总结分析
- 反馈循环与状态管理
"""

from typing import Any, Dict, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.orchestrator import (
    check_user_confirmation,
    create_orchestrator_node,
    route_by_intent,
)
from src.agents.planning import create_planning_graph
from src.agents.scheduler import create_scheduler_graph
from src.agents.summary import create_summary_graph
from src.graph.state import AgentState
from src.utils.prompt_templates import get_prompt_template


def create_orchestrator_workflow(provider: str = "openai") -> CompiledStateGraph:
    """创建完整的多智能体协作工作流。
    
    Args:
        provider: LLM 提供商（longcat/openai）
        
    Returns:
        编译后的工作流图
    """
    # 创建各个 Agent 的图
    scheduler_graph = create_scheduler_graph(provider=provider)
    planner_graph = create_planning_graph(provider=provider)
    summary_graph = create_summary_graph(provider=provider)
    
    # 创建 Orchestrator 节点
    orchestrator_node = create_orchestrator_node(provider=provider)
    
    # 构建主工作流
    builder = StateGraph(AgentState)
    
    # 添加节点
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("scheduler", scheduler_graph)
    builder.add_node("planner", planner_graph)
    builder.add_node("summary", summary_graph)
    
    # 路由逻辑：从 Orchestrator 到各个 Agent
    builder.add_conditional_edges(
        "orchestrator",
        route_by_intent,
        {
            "scheduler": "scheduler",
            "planner": "planner",
            "summary": "summary",
            "preference_manager": "scheduler",  # 偏好管理暂时路由到 scheduler
        },
    )
    
    # 反馈循环：从 Planner 处理用户确认
    builder.add_conditional_edges(
        "planner",
        check_user_confirmation,
        {
            "confirmed": "scheduler",  # 确认后执行日程添加
            "revise": "planner",       # 需要修改，重新规划
            "end": END,               # 结束流程
        },
    )
    
    # 其他 Agent 完成后回到 Orchestrator 或结束
    builder.add_edge("scheduler", END)
    builder.add_edge("summary", END)
    
    # 设置入口点
    builder.set_entry_point("orchestrator")
    
    # 编译图
    graph = builder.compile()
    graph = graph.with_config(run_name="MultiAgentWorkflow")
    
    return graph


def create_simple_workflow(provider: str = "openai") -> CompiledStateGraph:
    """创建简化的工作流（仅包含 Scheduler）。
    
    Args:
        provider: LLM 提供商
        
    Returns:
        编译后的简化工作流
    """
    scheduler_graph = create_scheduler_graph(provider=provider)
    
    builder = StateGraph(AgentState)
    builder.add_node("scheduler", scheduler_graph)
    builder.set_entry_point("scheduler")
    
    graph = builder.compile()
    graph = graph.with_config(run_name="SimpleSchedulerWorkflow")
    
    return graph


def create_planning_workflow(provider: str = "openai") -> CompiledStateGraph:
    """创建规划工作流（Planning + Scheduler）。
    
    Args:
        provider: LLM 提供商
        
    Returns:
        编译后的规划工作流
    """
    planner_graph = create_planning_graph(provider=provider)
    scheduler_graph = create_scheduler_graph(provider=provider)
    
    builder = StateGraph(AgentState)
    builder.add_node("planner", planner_graph)
    builder.add_node("scheduler", scheduler_graph)
    
    # 规划完成后，根据用户确认决定下一步
    builder.add_conditional_edges(
        "planner",
        check_user_confirmation,
        {
            "confirmed": "scheduler",
            "revise": "planner",
            "end": END,
        },
    )
    
    builder.add_edge("scheduler", END)
    builder.set_entry_point("planner")
    
    graph = builder.compile()
    graph = graph.with_config(run_name="PlanningWorkflow")
    
    return graph


class MultiAgentRunner:
    """多智能体工作流运行器。
    
    提供统一的接口来运行不同的工作流。
    """
    
    def __init__(self, workflow_type: str = "full", provider: str = "openai"):
        """初始化工作流运行器。
        
        Args:
            workflow_type: 工作流类型（full/simple/planning）
            provider: LLM 提供商
        """
        self.provider = provider
        self.workflow_type = workflow_type
        
        # 根据类型创建对应的工作流
        if workflow_type == "full":
            self.graph = create_orchestrator_workflow(provider=provider)
        elif workflow_type == "simple":
            self.graph = create_simple_workflow(provider=provider)
        elif workflow_type == "planning":
            self.graph = create_planning_workflow(provider=provider)
        else:
            raise ValueError(f"不支持的工作流类型: {workflow_type}")
        
        # 初始化状态
        self.state: AgentState = {
            "messages": [SystemMessage(content=get_prompt_template("system"))],
            "current_intent": "",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "default_user",
            "trace": []
        }
    
    def process_input(self, user_input: str, user_id: str = "default_user") -> Dict[str, Any]:
        """处理用户输入。
        
        Args:
            user_input: 用户输入文本
            user_id: 用户ID
            
        Returns:
            处理结果
        """
        # 更新用户ID
        self.state["user_id"] = user_id
        
        # 添加用户消息
        self.state["messages"].append(HumanMessage(content=user_input))
        self.state["trace"].append(f"INPUT -> {user_input}")
        
        try:
            # 运行工作流
            self.state = self.graph.invoke(self.state)
            self.state["trace"].append("GRAPH -> completed")
            
            # 提取 AI 回复
            ai_messages = [
                msg for msg in self.state["messages"] 
                if isinstance(msg, AIMessage)
            ]
            
            if ai_messages:
                return {
                    "status": "success",
                    "response": ai_messages[-1].content,
                    "intent": self.state.get("current_intent", ""),
                    "workflow_type": self.workflow_type,
                    "trace": self.state.get("trace", [])
                }
            else:
                return {
                    "status": "error",
                    "message": "未生成回复",
                    "intent": self.state.get("current_intent", ""),
                    "trace": self.state.get("trace", [])
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"处理失败: {str(e)}",
                "intent": self.state.get("current_intent", ""),
                "trace": self.state.get("trace", [])
            }
    
    def get_state(self) -> AgentState:
        """获取当前状态。"""
        return self.state
    
    def reset_state(self):
        """重置状态。"""
        self.state = {
            "messages": [SystemMessage(content=get_prompt_template("system"))],
            "current_intent": "",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "default_user",
            "trace": []
        }


def demo_run() -> None:
    """演示工作流运行。"""
    print("=== 多智能体日程管理系统演示 ===\n")
    
    # 创建完整工作流运行器
    runner = MultiAgentRunner(workflow_type="full", provider="longcat")
    
    # 测试用例
    test_inputs = [
        "请帮我添加一个明天上午9点到10点的团队会议",
        "帮我规划下周的学习计划，每天2小时",
        "总结一下本周的表现",
        "我喜欢上午学习"
    ]
    
    for i, user_input in enumerate(test_inputs, 1):
        print(f"测试 {i}: {user_input}")
        result = runner.process_input(user_input)
        
        print(f"意图: {result.get('intent', 'unknown')}")
        print(f"回复: {result.get('response', result.get('message', '无回复'))}")
        print("-" * 50)
    
    print("演示完成！")