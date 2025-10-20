from __future__ import annotations

import json
from typing import Any, Dict, List, Literal
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.graph.state import SchedulerState
from src.tools.calendar_db import (
    EventCreate,
    EventQuery,
    EventUpdate,
    add_event,
    get_event,
    list_events,
    remove_event,
    update_event,
)


SYSTEM_PROMPT = (
    "你是一个基于工具的日程管理智能体。"
    "你只能通过提供的工具查询或修改日程。"
    "在回应用户前，务必确认所有操作结果，"
    "并在最终答复中以中文总结执行情况。"
)


class AddEventArgs(BaseModel):
    title: str = Field(..., description="日程标题")
    description: str | None = Field(None, description="日程描述")
    start_time: str = Field(..., description="ISO 8601 格式的开始时间")
    end_time: str = Field(..., description="ISO 8601 格式的结束时间")
    location: str | None = Field(None, description="地点")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    status: str = Field("confirmed", description="事件状态")
    source: str = Field("agent", description="事件来源说明")


class UpdateEventArgs(BaseModel):
    event_id: str = Field(..., description="事件 ID")
    title: str | None = Field(None, description="新的标题")
    description: str | None = Field(None, description="新的描述")
    start_time: str | None = Field(None, description="新的开始时间（ISO 8601）")
    end_time: str | None = Field(None, description="新的结束时间（ISO 8601）")
    location: str | None = Field(None, description="新的地点")
    tags: List[str] | None = Field(None, description="新的标签列表")
    status: str | None = Field(None, description="新的状态")
    allow_overlap: bool = Field(
        False, description="是否允许与既有事件冲突后仍然更新"
    )


class RemoveEventArgs(BaseModel):
    event_id: str = Field(..., description="需要删除的事件 ID")


class GetEventArgs(BaseModel):
    event_id: str = Field(..., description="需要查询的事件 ID")


class ListEventsArgs(BaseModel):
    start_time: str | None = Field(None, description="开始时间下限（ISO 8601）")
    end_time: str | None = Field(None, description="结束时间上限（ISO 8601）")
    tags: List[str] | None = Field(None, description="筛选标签（全部匹配）")
    status: str | None = Field(None, description="根据状态筛选事件")


def build_scheduler_tools() -> List[StructuredTool]:
    def _add_event(args: AddEventArgs) -> Dict[str, Any]:
        payload = EventCreate(**args.model_dump())
        return add_event(payload)

    def _update_event(args: UpdateEventArgs) -> Dict[str, Any]:
        payload = EventUpdate(
            event_id=args.event_id,
            title=args.title,
            description=args.description,
            start_time=args.start_time,
            end_time=args.end_time,
            location=args.location,
            tags=args.tags,
            status=args.status,
        )
        return update_event(payload, allow_overlap=args.allow_overlap)

    def _remove_event(args: RemoveEventArgs) -> Dict[str, Any]:
        return remove_event(args.event_id)

    def _get_event(args: GetEventArgs) -> Dict[str, Any]:
        return get_event(args.event_id)

    def _list_events(args: ListEventsArgs) -> Dict[str, Any]:
        query = EventQuery(
            start_time=args.start_time,
            end_time=args.end_time,
            tags=args.tags,
            status=args.status,
        )
        return list_events(query=query)

    return [
        StructuredTool.from_function(
            name="add_event",
            description="添加新的日程事件，如会议或任务安排。",
            func=_add_event,
            args_schema=AddEventArgs,
        ),
        StructuredTool.from_function(
            name="update_event",
            description="更新现有日程事件的内容或时间。",
            func=_update_event,
            args_schema=UpdateEventArgs,
        ),
        StructuredTool.from_function(
            name="remove_event",
            description="根据事件 ID 删除日程记录。",
            func=_remove_event,
            args_schema=RemoveEventArgs,
        ),
        StructuredTool.from_function(
            name="get_event",
            description="根据事件 ID 查询详细信息。",
            func=_get_event,
            args_schema=GetEventArgs,
        ),
        StructuredTool.from_function(
            name="list_events",
            description="列出满足条件的日程事件集合。",
            func=_list_events,
            args_schema=ListEventsArgs,
        ),
    ]


def _should_continue(state: SchedulerState) -> Literal["call_tool", "finish"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        # 记录 LLM 发起的工具调用
        tool_names = ",".join([tc["name"] for tc in last_message.tool_calls]) if isinstance(last_message.tool_calls, list) else "has_tool_calls"
        state.setdefault("trace", []).append(f"SCHEDULER -> tool_call {tool_names}")
        return "call_tool"
    return "finish"


def create_scheduler_graph(model: str = "gpt-4o-mini", provider: str = "openai") -> CompiledStateGraph:
    tools = build_scheduler_tools()
    tool_node = ToolNode(tools)
    
    # 统一使用 OpenAI 提供商
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL"),
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
    )
    
    llm_with_tools = llm.bind_tools(tools)

    def run_llm(state: SchedulerState) -> Dict[str, Any]:
        response = llm_with_tools.invoke(state["messages"])
        state.setdefault("trace", []).append("SCHEDULER -> llm_invoke")
        return {"messages": [response]}

    builder = StateGraph(SchedulerState)
    builder.add_node("scheduler_llm", run_llm)
    builder.add_node("tool_executor", tool_node)

    builder.add_conditional_edges(
        "scheduler_llm",
        _should_continue,
        {
            "call_tool": "tool_executor",
            "finish": END,
        },
    )
    builder.add_edge("tool_executor", "scheduler_llm")
    builder.set_entry_point("scheduler_llm")

    graph = builder.compile()
    graph = graph.with_config(run_name="SchedulerAgent")
    return graph


class SchedulerAgentRunner:
    """Helper for interactive use in Milestone 1."""

    def __init__(self, model: str = "gpt-4o-mini", provider: str = "openai") -> None:
        self.graph = create_scheduler_graph(model=model, provider=provider)
        self.state: SchedulerState = {
            "messages": [SystemMessage(content=SYSTEM_PROMPT)]
        }

    def send(self, user_text: str) -> str:
        self.state["messages"].append(HumanMessage(content=user_text))
        self.state = self.graph.invoke(self.state)
        ai_messages = [
            msg for msg in self.state["messages"] if isinstance(msg, AIMessage)
        ]
        return ai_messages[-1].content if ai_messages else ""


