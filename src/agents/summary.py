from __future__ import annotations

"""SummaryAgent 实现。

日程总结分析 Agent，负责：
- 聚合日程数据：统计指定时间范围内的事件信息
- 生成总结报告：分析时间分布、活动类型、效率等
- 提供优化建议：基于用户偏好和历史数据提出改进建议
- 趋势分析：识别日程模式和变化趋势
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

from src.graph.schema import SummaryOutput
from src.graph.state import AgentState
from src.tools.calendar_db import get_events_summary, list_events
from src.tools.preferences import retrieve_preferences


SUMMARY_PROMPT = """你是日程总结分析师，专门负责分析用户的日程数据并提供洞察。

你的职责：
1. 分析指定时间范围内的日程数据
2. 统计事件数量、时间分布、活动类型等
3. 检索用户偏好，对比实际安排与偏好
4. 生成总结报告和优化建议
5. 识别日程模式和趋势

工作流程：
1. 接收总结请求（时间范围、类型等）
2. 查询指定时间范围内的事件
3. 获取事件统计摘要
4. 检索相关用户偏好
5. 分析数据并生成总结报告
6. 提供具体的优化建议

请使用工具获取准确数据，生成有价值的总结和 actionable 的建议。"""


class SummaryArgs(BaseModel):
    """总结请求参数模型。"""
    
    period_type: str = Field(..., description="总结类型：daily/weekly/monthly")
    start_date: str = Field(..., description="开始日期（ISO 8601）")
    end_date: str = Field(None, description="结束日期（ISO 8601），可选")
    user_id: str = Field(..., description="用户ID")


class EventsSummaryArgs(BaseModel):
    """事件摘要查询参数。"""
    
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")


class EventsListArgs(BaseModel):
    """事件列表查询参数。"""
    
    start_date: str = Field(None, description="开始日期")
    end_date: str = Field(None, description="结束日期")
    tags: List[str] = Field(None, description="标签筛选")
    status: str = Field(None, description="状态筛选")


class PreferencesArgs(BaseModel):
    """偏好查询参数。"""
    
    user_id: str = Field(..., description="用户ID")
    query: str = Field(..., description="查询文本")


def build_summary_tools() -> List[StructuredTool]:
    """构建总结 Agent 的工具集。"""
    
    def _get_events_summary(args: EventsSummaryArgs) -> Dict[str, Any]:
        """获取事件统计摘要。"""
        return get_events_summary(
            start_date=args.start_date,
            end_date=args.end_date
        )
    
    def _get_events_list(args: EventsListArgs) -> Dict[str, Any]:
        """获取事件列表。"""
        from src.tools.calendar_db import EventQuery
        query = EventQuery(
            start_time=args.start_date,
            end_time=args.end_date,
            tags=args.tags,
            status=args.status
        )
        return list_events(query=query)
    
    def _get_preferences(args: PreferencesArgs) -> Dict[str, Any]:
        """检索用户偏好。"""
        return retrieve_preferences(
            user_id=args.user_id,
            query=args.query,
            top_k=10
        )
    
    def _generate_summary(args: SummaryArgs) -> Dict[str, Any]:
        """生成总结（占位函数，实际由 LLM 处理）。"""
        return {
            "status": "info",
            "message": "此工具由 LLM 调用，实际总结逻辑在 prompt 中处理"
        }
    
    return [
        StructuredTool.from_function(
            name="get_events_summary",
            description="获取指定时间范围内的事件统计摘要",
            func=_get_events_summary,
            args_schema=EventsSummaryArgs,
        ),
        StructuredTool.from_function(
            name="get_events_list",
            description="获取指定条件的事件列表",
            func=_get_events_list,
            args_schema=EventsListArgs,
        ),
        StructuredTool.from_function(
            name="get_preferences",
            description="检索用户偏好，用于对比分析",
            func=_get_preferences,
            args_schema=PreferencesArgs,
        ),
        StructuredTool.from_function(
            name="generate_summary",
            description="生成总结报告（由 LLM 调用，实际处理在 prompt 中）",
            func=_generate_summary,
            args_schema=SummaryArgs,
        ),
    ]


def _should_continue_summary(state: AgentState) -> Literal["call_tool", "finish"]:
    """判断是否继续工具调用。"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        state.setdefault("trace", []).append("SUMMARY -> tool_call")
        return "call_tool"
    return "finish"


def create_summary_graph(provider: str = "openai") -> CompiledStateGraph:
    """创建总结 Agent 的 LangGraph。
    
    Args:
        provider: LLM 提供商（longcat/openai）
        
    Returns:
        编译后的图
    """
    tools = build_summary_tools()
    tool_node = ToolNode(tools)
    
    # 统一使用 OpenAI 提供商
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
    )
    
    llm_with_tools = llm.bind_tools(tools)
    
    def run_summary(state: AgentState) -> Dict[str, Any]:
        """运行总结 LLM。"""
        response = llm_with_tools.invoke(state["messages"])
        state.setdefault("trace", []).append("SUMMARY -> llm_invoke")
        return {"messages": [response]}
    
    # 构建图
    builder = StateGraph(AgentState)
    builder.add_node("summary_llm", run_summary)
    builder.add_node("tool_executor", tool_node)
    
    builder.add_conditional_edges(
        "summary_llm",
        _should_continue_summary,
        {
            "call_tool": "tool_executor",
            "finish": END,
        },
    )
    builder.add_edge("tool_executor", "summary_llm")
    builder.set_entry_point("summary_llm")
    
    graph = builder.compile()
    graph = graph.with_config(run_name="SummaryAgent")
    return graph


class SummaryAgentRunner:
    """总结 Agent 运行器。
    
    提供简化的接口用于生成日程总结。
    """
    
    def __init__(self, provider: str = "openai") -> None:
        """初始化总结 Agent。
        
        Args:
            provider: LLM 提供商
        """
        self.graph = create_summary_graph(provider=provider)
        self.state: AgentState = {
            "messages": [SystemMessage(content=SUMMARY_PROMPT)],
            "current_intent": "summary",
            "planner_output": None,
            "summary_output": None,
            "user_feedback": None,
            "pending_tasks": [],
            "preferences": [],
            "user_id": "default_user"
        }
    
    def generate_summary(
        self,
        period_type: str,
        start_date: str,
        end_date: str = None,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """生成日程总结。
        
        Args:
            period_type: 总结类型（daily/weekly/monthly）
            start_date: 开始日期
            end_date: 结束日期（可选）
            user_id: 用户ID
            
        Returns:
            总结结果
        """
        # 更新状态
        self.state["user_id"] = user_id
        
        # 构建总结请求
        summary_request = f"""
请帮我生成以下时间范围的日程总结：

总结类型：{period_type}
开始日期：{start_date}
结束日期：{end_date or '未指定'}
用户ID：{user_id}

请按以下步骤进行：
1. 获取 {start_date} 到 {end_date or '今天'} 的事件统计摘要
2. 获取详细的事件列表
3. 检索用户 {user_id} 的相关偏好
4. 分析时间分布、活动类型、效率等
5. 对比实际安排与用户偏好
6. 生成总结报告和优化建议

请使用工具获取准确数据，然后生成有价值的总结和 actionable 的建议。
"""
        
        self.state["messages"].append(HumanMessage(content=summary_request))
        
        # 运行总结
        self.state = self.graph.invoke(self.state)
        
        # 提取结果
        ai_messages = [
            msg for msg in self.state["messages"] 
            if isinstance(msg, AIMessage)
        ]
        
        if ai_messages:
            return {
                "status": "success",
                "summary_result": ai_messages[-1].content,
                "messages": [msg.content for msg in ai_messages]
            }
        else:
            return {
                "status": "error",
                "message": "总结失败，未生成结果"
            }
    
    def get_summary_output(self) -> SummaryOutput:
        """获取总结输出对象。"""
        return self.state.get("summary_output")
    
    def analyze_trends(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """分析日程趋势。
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            趋势分析结果
        """
        # 获取事件数据
        events_result = list_events()
        if events_result["status"] != "success":
            return {
                "status": "error",
                "message": "获取事件数据失败"
            }
        
        events = events_result["events"]
        
        # 简单的趋势分析
        trends = {
            "total_events": len(events),
            "avg_daily_events": len(events) / max(1, (end_date - start_date).days),
            "most_common_tags": {},
            "time_distribution": {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
        }
        
        # 分析标签分布
        for event in events:
            for tag in event.get("tags", []):
                trends["most_common_tags"][tag] = trends["most_common_tags"].get(tag, 0) + 1
        
        # 分析时间分布
        for event in events:
            start_time = event["start_time"]
            hour = int(start_time.split("T")[1].split(":")[0])
            if 6 <= hour < 12:
                trends["time_distribution"]["morning"] += 1
            elif 12 <= hour < 18:
                trends["time_distribution"]["afternoon"] += 1
            elif 18 <= hour < 22:
                trends["time_distribution"]["evening"] += 1
            else:
                trends["time_distribution"]["night"] += 1
        
        return {
            "status": "success",
            "trends": trends
        }


def parse_summary_result(result_text: str, period: str) -> SummaryOutput:
    """解析总结结果文本为 SummaryOutput 对象。
    
    Args:
        result_text: LLM 输出的总结结果文本
        period: 时间范围
        
    Returns:
        解析后的总结输出对象
    """
    # 这里可以实现更复杂的解析逻辑
    # 目前返回一个基本的 SummaryOutput
    return SummaryOutput(
        period=period,
        summary_text=result_text,
        recommendations=[],
        stats={}
    )
