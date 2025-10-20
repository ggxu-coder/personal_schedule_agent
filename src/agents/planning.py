from __future__ import annotations

"""PlanningAgent 实现。

智能任务规划 Agent，负责：
- 任务分解：将复杂任务分解为可执行的子任务
- 时间规划：结合空闲时间和用户偏好安排任务
- 冲突检测：识别时间冲突并提供解决方案
- 计划优化：根据用户反馈调整计划
"""

import json
import os
from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.graph.schema import PlannerOutput, TaskItem
from src.graph.state import AgentState
from src.tools.calendar_db import get_free_slots
from src.tools.preferences import retrieve_preferences


PLANNER_PROMPT = """你是智能规划助手，专门负责任务分解和时间安排。

你的职责：
1. 将用户的任务需求分解为具体的可执行子任务
2. 查询用户的空闲时间段
3. 检索用户偏好，优化任务安排
4. 生成结构化的时间计划
5. 识别潜在的时间冲突并提供解决方案

工作流程：
1. 接收任务描述和时间范围
2. 查询空闲时间段
3. 检索相关用户偏好
4. 分解任务并安排时间
5. 输出 PlannerOutput 格式的结果

请始终使用提供的工具来获取准确信息，并生成合理的任务安排。"""


class PlanningArgs(BaseModel):
    """规划请求参数模型。"""
    
    task_description: str = Field(..., description="任务描述")
    start_date: str = Field(..., description="开始日期（ISO 8601）")
    end_date: str = Field(..., description="结束日期（ISO 8601）")
    consider_preferences: bool = Field(True, description="是否考虑用户偏好")
    min_task_duration: int = Field(30, description="最小任务时长（分钟）")


class FreeSlotsArgs(BaseModel):
    """空闲时间查询参数。"""
    
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    min_duration_minutes: int = Field(30, description="最小时长")


class PreferencesArgs(BaseModel):
    """偏好查询参数。"""
    
    user_id: str = Field(..., description="用户ID")
    query: str = Field(..., description="查询文本")


def build_planning_tools() -> List[StructuredTool]:
    """构建规划 Agent 的工具集。"""
    
    def _get_free_slots(args: FreeSlotsArgs) -> Dict[str, Any]:
        """查询空闲时间段。"""
        return get_free_slots(
            start_date=args.start_date,
            end_date=args.end_date,
            min_duration_minutes=args.min_duration_minutes
        )
    
    def _get_preferences(args: PreferencesArgs) -> Dict[str, Any]:
        """检索用户偏好。"""
        return retrieve_preferences(
            user_id=args.user_id,
            query=args.query,
            top_k=5
        )
    
    def _generate_plan(args: PlanningArgs) -> Dict[str, Any]:
        """生成任务规划（占位函数，实际由 LLM 处理）。"""
        return {
            "status": "info",
            "message": "此工具由 LLM 调用，实际规划逻辑在 prompt 中处理"
        }
    
    return [
        StructuredTool.from_function(
            name="get_free_slots",
            description="查询指定时间范围内的空闲时间段，用于任务安排",
            func=_get_free_slots,
            args_schema=FreeSlotsArgs,
        ),
        StructuredTool.from_function(
            name="get_preferences",
            description="检索用户偏好，用于优化任务安排",
            func=_get_preferences,
            args_schema=PreferencesArgs,
        ),
        StructuredTool.from_function(
            name="generate_plan",
            description="生成任务规划（由 LLM 调用，实际处理在 prompt 中）",
            func=_generate_plan,
            args_schema=PlanningArgs,
        ),
    ]


def _should_continue_planning(state: AgentState) -> Literal["call_tool", "finish"]:
    """判断是否继续工具调用。"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        state.setdefault("trace", []).append("PLANNER -> tool_call")
        return "call_tool"
    return "finish"


def create_planning_graph(provider: str = "openai") -> CompiledStateGraph:
    """创建规划 Agent 的 LangGraph。
    
    Args:
        provider: LLM 提供商（longcat/openai）
        
    Returns:
        编译后的图
    """
    tools = build_planning_tools()
    tool_node = ToolNode(tools)
    
    # 统一使用 OpenAI 提供商
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.1,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
    )
    
    llm_with_tools = llm.bind_tools(tools)
    
    def run_planner(state: AgentState) -> Dict[str, Any]:
        """运行规划 LLM。"""
        response = llm_with_tools.invoke(state["messages"])
        state.setdefault("trace", []).append("PLANNER -> llm_invoke")
        return {"messages": [response]}
    
    # 构建图
    builder = StateGraph(AgentState)
    builder.add_node("planner_llm", run_planner)
    builder.add_node("tool_executor", tool_node)
    
    builder.add_conditional_edges(
        "planner_llm",
        _should_continue_planning,
        {
            "call_tool": "tool_executor",
            "finish": END,
        },
    )
    builder.add_edge("tool_executor", "planner_llm")
    builder.set_entry_point("planner_llm")
    
    graph = builder.compile()
    graph = graph.with_config(run_name="PlanningAgent")
    return graph


class PlanningAgentRunner:
    """规划 Agent 运行器。
    
    提供简化的接口用于规划任务。
    """
    
    def __init__(self, provider: str = "openai") -> None:
        """初始化规划 Agent。
        
        Args:
            provider: LLM 提供商
        """
        self.graph = create_planning_graph(provider=provider)
        self.state: AgentState = {
            "messages": [SystemMessage(content=PLANNER_PROMPT)],
            "current_intent": "planning",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "default_user"
        }
    
    def plan_tasks(
        self,
        task_description: str,
        start_date: str,
        end_date: str,
        user_id: str = "default_user",
        consider_preferences: bool = True
    ) -> Dict[str, Any]:
        """规划任务。
        
        Args:
            task_description: 任务描述
            start_date: 开始日期
            end_date: 结束日期
            user_id: 用户ID
            consider_preferences: 是否考虑偏好
            
        Returns:
            规划结果
        """
        # 更新状态
        self.state["user_id"] = user_id
        
        # 构建规划请求
        planning_request = f"""
请帮我规划以下任务：

任务描述：{task_description}
时间范围：{start_date} 到 {end_date}
用户ID：{user_id}
考虑偏好：{consider_preferences}

请按以下步骤进行：
1. 查询 {start_date} 到 {end_date} 的空闲时间段
2. 检索用户 {user_id} 的相关偏好
3. 将任务分解为具体的子任务
4. 根据空闲时间和偏好安排任务时间
5. 输出结构化的规划结果

请使用工具获取准确信息，然后生成详细的规划方案。
"""
        
        self.state["messages"].append(HumanMessage(content=planning_request))
        
        # 运行规划
        self.state = self.graph.invoke(self.state)
        
        # 提取结果
        ai_messages = [
            msg for msg in self.state["messages"] 
            if isinstance(msg, AIMessage)
        ]
        
        if ai_messages:
            return {
                "status": "success",
                "planning_result": ai_messages[-1].content,
                "messages": [msg.content for msg in ai_messages]
            }
        else:
            return {
                "status": "error",
                "message": "规划失败，未生成结果"
            }
    
    def get_planning_output(self) -> PlannerOutput:
        """获取规划输出对象。"""
        return self.state.get("planner_output")
    
    def update_feedback(self, feedback: str):
        """更新用户反馈。"""
        self.state["user_feedback"] = feedback
        self.state["messages"].append(HumanMessage(content=f"用户反馈：{feedback}"))


def parse_planning_result(result_text: str) -> PlannerOutput:
    """解析规划结果文本为 PlannerOutput 对象。
    
    这是一个辅助函数，用于从 LLM 输出中提取结构化信息。
    
    Args:
        result_text: LLM 输出的规划结果文本
        
    Returns:
        解析后的规划输出对象
    """
    # 这里可以实现更复杂的解析逻辑
    # 目前返回一个基本的 PlannerOutput
    return PlannerOutput(
        tasks=[],
        conflicts=[],
        notes=result_text,
        free_slots=[]
    )
