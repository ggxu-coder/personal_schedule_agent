from __future__ import annotations

"""OrchestratorAgent 实现。

用户意图理解与 Agent 路由的核心组件，负责：
- 意图识别：理解用户输入的真实意图
- Agent 路由：根据意图选择合适的 Agent
- 上下文管理：维护多轮对话的上下文
- 结果汇总：整合各 Agent 的输出结果
"""

import json
import os
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.graph.state import AgentState


ORCHESTRATOR_PROMPT = """你是用户意图理解助手，负责理解用户输入并路由到合适的 Agent。

你的职责：
1. 分析用户输入，识别真实意图
2. 提取关键参数（时间、任务描述等）
3. 路由到合适的 Agent 进行处理
4. 管理对话上下文和状态

支持的意图类型：
- scheduling: 日程增删改查（添加会议、删除事件、修改时间等）
- planning: 任务规划与安排（帮我规划学习计划、安排项目任务等）
- summary: 日程总结分析（总结本周表现、分析时间分配等）
- preference: 偏好管理（我喜欢上午学习、设置工作时间等）

输出格式：
请以 JSON 格式输出意图识别结果：
{
    "intent": "意图类型",
    "confidence": 0.95,
    "params": {
        "key": "value"
    },
    "reasoning": "识别理由"
}

请仔细分析用户输入，准确识别意图并提供必要的参数。"""


class IntentResult(BaseModel):
    """意图识别结果模型。"""
    
    intent: str = Field(..., description="意图类型")
    confidence: float = Field(..., description="置信度（0-1）")
    params: Dict[str, Any] = Field(default_factory=dict, description="提取的参数")
    reasoning: str = Field(..., description="识别理由")


class OrchestratorAgent:
    """Orchestrator Agent 实现。
    
    负责用户意图识别和 Agent 路由。
    """
    
    def __init__(self, provider: str = "openai"):
        """初始化 Orchestrator Agent。
        
        Args:
            provider: LLM 提供商
        """
        self.provider = provider
        
        # 统一使用 OpenAI 提供商
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
        )
    
    def classify_intent(self, user_input: str) -> IntentResult:
        """识别用户意图。
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            意图识别结果
        """
        try:
            # 构建意图识别请求
            prompt = f"""
用户输入：{user_input}

请分析用户意图，输出 JSON 格式的结果。
"""
            
            messages = [
                SystemMessage(content=ORCHESTRATOR_PROMPT),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # 解析 JSON 响应
            try:
                # 尝试从响应中提取 JSON
                content = response.content
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                elif "{" in content and "}" in content:
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    json_str = content[json_start:json_end]
                else:
                    json_str = content
                
                intent_data = json.loads(json_str)
                
                return IntentResult(
                    intent=intent_data.get("intent", "unknown"),
                    confidence=intent_data.get("confidence", 0.5),
                    params=intent_data.get("params", {}),
                    reasoning=intent_data.get("reasoning", "未提供理由")
                )
                
            except json.JSONDecodeError:
                # JSON 解析失败，使用启发式规则
                return self._fallback_intent_classification(user_input)
                
        except Exception as e:
            return IntentResult(
                intent="error",
                confidence=0.0,
                params={"error": str(e)},
                reasoning=f"意图识别失败: {str(e)}"
            )
    
    def _fallback_intent_classification(self, user_input: str) -> IntentResult:
        """备用意图分类（基于关键词规则）。
        
        Args:
            user_input: 用户输入
            
        Returns:
            意图识别结果
        """
        user_input_lower = user_input.lower()
        
        # 关键词映射
        scheduling_keywords = [
            "添加", "删除", "修改", "更新", "会议", "约会", "事件",
            "明天", "后天", "下周", "时间", "几点", "安排"
        ]
        
        planning_keywords = [
            "规划", "计划", "安排", "学习计划", "项目", "任务",
            "帮我", "制定", "设计", "分解"
        ]
        
        summary_keywords = [
            "总结", "分析", "回顾", "表现", "统计", "报告",
            "本周", "本月", "这周", "这月", "总结一下"
        ]
        
        preference_keywords = [
            "偏好", "喜欢", "习惯", "设置", "配置", "偏好",
            "我喜欢", "我习惯", "工作时间", "学习时间"
        ]
        
        # 计算关键词匹配度
        scheduling_score = sum(1 for kw in scheduling_keywords if kw in user_input_lower)
        planning_score = sum(1 for kw in planning_keywords if kw in user_input_lower)
        summary_score = sum(1 for kw in summary_keywords if kw in user_input_lower)
        preference_score = sum(1 for kw in preference_keywords if kw in user_input_lower)
        
        # 选择得分最高的意图
        scores = {
            "scheduling": scheduling_score,
            "planning": planning_score,
            "summary": summary_score,
            "preference": preference_score
        }
        
        best_intent = max(scores, key=scores.get)
        confidence = min(0.8, scores[best_intent] * 0.2)  # 规则匹配的置信度较低
        
        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            params={},
            reasoning=f"基于关键词规则识别，{best_intent} 得分: {scores[best_intent]}"
        )
    
    def extract_parameters(self, user_input: str, intent: str) -> Dict[str, Any]:
        """从用户输入中提取参数。
        
        Args:
            user_input: 用户输入
            intent: 识别的意图
            
        Returns:
            提取的参数
        """
        params = {}
        
        if intent == "scheduling":
            # 提取时间相关参数
            import re
            time_patterns = [
                r"(\d{1,2}):(\d{2})",  # 9:30
                r"(\d{1,2})点",  # 9点
                r"上午|下午|晚上|中午",
                r"明天|后天|今天|下周|下周"
            ]
            
            for pattern in time_patterns:
                matches = re.findall(pattern, user_input)
                if matches:
                    params["time_mentions"] = matches
        
        elif intent == "planning":
            # 提取任务描述和时间范围
            params["task_description"] = user_input
            params["time_range"] = "未指定"
        
        elif intent == "summary":
            # 提取时间范围
            if "本周" in user_input or "这周" in user_input:
                params["period"] = "weekly"
            elif "本月" in user_input or "这月" in user_input:
                params["period"] = "monthly"
            elif "今天" in user_input:
                params["period"] = "daily"
            else:
                params["period"] = "weekly"  # 默认周总结
        
        elif intent == "preference":
            # 提取偏好描述
            params["preference_description"] = user_input
        
        return params
    
    def route_to_agent(self, intent_result: IntentResult) -> str:
        """根据意图路由到对应的 Agent。
        
        Args:
            intent_result: 意图识别结果
            
        Returns:
            目标 Agent 名称
        """
        intent = intent_result.intent
        
        routing_map = {
            "scheduling": "scheduler",
            "planning": "planner", 
            "summary": "summary",
            "preference": "preference_manager"
        }
        
        return routing_map.get(intent, "scheduler")  # 默认路由到 scheduler
    
    def process_user_input(self, user_input: str, state: AgentState) -> Dict[str, Any]:
        """处理用户输入。
        
        Args:
            user_input: 用户输入
            state: 当前状态
            
        Returns:
            处理结果
        """
        # 识别意图
        intent_result = self.classify_intent(user_input)
        
        # 提取参数
        params = self.extract_parameters(user_input, intent_result.intent)
        intent_result.params.update(params)
        
        # 路由到 Agent
        target_agent = self.route_to_agent(intent_result)
        
        # 更新状态
        state["current_intent"] = intent_result.intent
        state["messages"].append(HumanMessage(content=user_input))
        
        return {
            "status": "success",
            "intent_result": intent_result.model_dump(),
            "target_agent": target_agent,
            "confidence": intent_result.confidence,
            "reasoning": intent_result.reasoning
        }


def create_orchestrator_node(provider: str = "openai"):
    """创建 Orchestrator 节点函数。
    
    Args:
        provider: LLM 提供商
        
    Returns:
        节点函数
    """
    orchestrator = OrchestratorAgent(provider=provider)
    
    def orchestrator_node(state: AgentState) -> Dict[str, Any]:
        """Orchestrator 节点函数。"""
        last_message = state["messages"][-1]
        if isinstance(last_message, HumanMessage):
            user_input = last_message.content
            
            # 处理用户输入
            result = orchestrator.process_user_input(user_input, state)
            
            # 添加系统消息说明意图识别结果
            system_msg = f"""
意图识别结果：
- 意图类型：{result['intent_result']['intent']}
- 置信度：{result['confidence']:.2f}
- 目标 Agent：{result['target_agent']}
- 识别理由：{result['reasoning']}
- 提取参数：{json.dumps(result['intent_result']['params'], ensure_ascii=False)}
"""
            
            state["messages"].append(SystemMessage(content=system_msg))
            # 记录踪迹
            trace_line = (
                f"ORCHESTRATOR -> intent={result['intent_result']['intent']} "
                f"target={result['target_agent']} conf={result['confidence']:.2f}"
            )
            state.setdefault("trace", []).append(trace_line)
            
            return {
                "messages": [SystemMessage(content=system_msg)],
                "current_intent": result["intent_result"]["intent"]
            }
        
        return {"messages": []}
    
    return orchestrator_node


def route_by_intent(state: AgentState) -> str:
    """根据意图进行路由。
    
    Args:
        state: 当前状态
        
    Returns:
        目标节点名称
    """
    intent = state.get("current_intent", "scheduling")
    
    routing_map = {
        "scheduling": "scheduler",
        "planning": "planner",
        "summary": "summary",
        "preference": "preference_manager"
    }
    
    return routing_map.get(intent, "scheduler")


def check_user_confirmation(state: AgentState) -> str:
    """检查用户确认状态。
    
    Args:
        state: 当前状态
        
    Returns:
        下一步动作
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage):
        content = last_message.content.lower()
        
        if any(word in content for word in ["确认", "同意", "好的", "可以", "yes", "ok"]):
            return "confirmed"
        elif any(word in content for word in ["修改", "调整", "重新", "revise", "change"]):
            return "revise"
        else:
            return "end"
    
    return "end"
