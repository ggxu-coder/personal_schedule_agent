from __future__ import annotations

"""图状态定义。

支持多智能体协作的状态管理：
- messages：LangChain BaseMessage 序列，用于在图中流转
- memory：MemorySaver，用于可选的有状态对话/检查点能力
- AgentState：扩展状态，支持多 Agent 协作
"""

from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from src.graph.schema import PlannerOutput, SummaryOutput, TaskItem
from src.storage.models import UserPreference

memory = MemorySaver()


class SchedulerState(TypedDict):
    """调度 Agent 的图状态结构。

    使用 `add_messages` 合并消息，便于在多轮工具调用之间维持上下文。
    """

    messages: Annotated[List[BaseMessage], add_messages]


class AgentState(TypedDict):
    """多智能体协作的图状态结构。
    
    支持 Orchestrator、Scheduler、Planning、Summary 四个 Agent 的状态传递。
    """
    
    messages: Annotated[List[BaseMessage], add_messages]
    current_intent: str  # planning/scheduling/summary/preference
    planner_output: Optional[PlannerOutput]
    summary_output: Optional[SummaryOutput]
    user_feedback: Optional[str]
    pending_tasks: List[TaskItem]
    preferences: List[UserPreference]
    user_id: str  # 用户标识，用于偏好管理
    trace: List[str]  # 执行踪迹


