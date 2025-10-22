"""PlanningAgent - 任务规划智能体（主控）"""
import os
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ..graph.state import AgentState
from ..tools.planning_agent_tools import (
    call_scheduler_agent,
    call_summary_agent,
    store_preference,
    get_preferences,
    clear_preferences,
)


class PlanningAgent:
    """任务规划 Agent（主控）"""
    
    def __init__(self):
        self.llm = self._create_llm()
        self.tools = self._build_tools()
        self.graph = self._build_graph()
    
    def _create_llm(self):
        """创建 LLM"""
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
            temperature=0
        )
    
    def _build_tools(self):
        """构建工具集"""
        tools = [
            StructuredTool.from_function(
                name="call_scheduler_agent",
                description="调用日程管理助手（SchedulerAgent）处理日程相关操作。适用于：添加、修改、删除、查询日程事件，查询空闲时间等。将用户的日程管理请求传递给该助手",
                func=call_scheduler_agent,
            ),
            StructuredTool.from_function(
                name="call_summary_agent",
                description="调用日程分析助手（SummaryAgent）处理分析和总结请求。适用于：统计事件数据、分析时间使用、生成总结报告、提供优化建议等。将用户的分析请求传递给该助手",
                func=call_summary_agent,
            ),
            StructuredTool.from_function(
                name="store_preference",
                description="存储用户的偏好设置。记录用户的习惯、喜好、工作时间偏好等信息，用于后续的智能规划。例如：工作时间偏好、会议时间偏好、休息习惯等",
                func=store_preference,
            ),
            StructuredTool.from_function(
                name="get_preferences",
                description="获取用户的偏好设置。查询之前存储的用户偏好信息，用于制定符合用户习惯的日程安排",
                func=get_preferences,
            ),
            StructuredTool.from_function(
                name="clear_preferences",
                description="清空所有用户偏好设置。慎用，只在用户明确要求重置偏好时使用",
                func=clear_preferences,
            ),
        ]
        return tools
    
    def _build_graph(self):
        """构建 LangGraph 图"""
        # 创建图
        workflow = StateGraph(AgentState)
        
        # 绑定工具到 LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # 定义节点
        def agent_node(state: AgentState):
            """Agent 推理节点"""
            messages = state["messages"]
            
            print("\n" + "="*60)
            print("🧠 [PlanningAgent 节点] 开始规划...")
            print(f"📝 当前消息数: {len(messages)}")
            
            # 获取当前时间
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 添加系统提示
            system_message = SystemMessage(content=f"""您是智能日程管理系统的主控助理（PlanningAgent）。

当前时间: {current_time}
当前日期: {current_date}

您的职责是理解用户意图，协调其他专业助手，提供智能的日程规划和管理服务。

系统架构：

1. SchedulerAgent（日程管理助手）
   - 负责日程的增删改查操作
   - 自动检测时间冲突
   - 查询空闲时间段
   - 处理所有与日程操作相关的请求

2. SummaryAgent（日程分析助手）
   - 负责统计和分析日程数据
   - 生成总结报告
   - 提供优化建议
   - 处理所有与分析总结相关的请求

3. 您的工具（偏好管理）
   - 存储和获取用户偏好
   - 用于个性化的日程规划

工作原则：

1. 智能意图识别
   - 准确理解用户的真实需求
   - 识别请求类型：日程操作、分析总结、规划建议、偏好设置
   - 对于复杂请求，分解为多个子任务

2. 合理任务委派
   - 日程操作类请求 → 委派给 SchedulerAgent
   - 分析总结类请求 → 委派给 SummaryAgent
   - 偏好相关请求 → 使用偏好管理工具
   - 复杂规划请求 → 组合使用多个助手

3. 智能规划能力
   - 在制定日程计划时，先查询用户偏好
   - 考虑时间冲突和空闲时间
   - 提供合理的时间安排建议
   - 基于历史数据优化规划

4. 协调与整合
   - 协调多个助手的工作
   - 整合不同助手的返回结果
   - 向用户提供统一、连贯的回复
   - 确保任务完整执行

5. 用户体验优化
   - 主动提供建议，而非被动响应
   - 记住用户偏好，提供个性化服务
   - 对话要自然流畅，避免机械感
   - 在适当时候主动询问用户需求

任务委派示例：

- "添加明天的会议" → call_scheduler_agent
- "总结本周日程" → call_summary_agent
- "帮我规划下周的学习计划" → 先 get_preferences，再 call_scheduler_agent
- "我喜欢上午工作" → store_preference
- "查看我的偏好" → get_preferences

请记住：
- 您是协调者，不直接操作数据库
- 充分利用专业助手的能力
- 提供有价值的规划建议
- 确保用户请求得到完整处理
""")
            
            # 调用 LLM
            print("💭 正在调用 LLM...")
            response = llm_with_tools.invoke([system_message] + list(messages))
            
            # 打印 Agent 的决策
            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"🔧 Agent 决定调用 {len(response.tool_calls)} 个工具:")
                for tool_call in response.tool_calls:
                    print(f"   - {tool_call['name']}: {tool_call['args']}")
            else:
                print("✅ Agent 决定结束任务")
                print(f"💬 最终回复: {response.content[:100]}...")
            
            return {"messages": [response]}
        
        # 定义工具节点（包装以添加日志）
        original_tool_node = ToolNode(self.tools)
        
        def tool_node(state: AgentState):
            """工具执行节点（带日志）"""
            print("\n" + "-"*60)
            print("🔧 [工具节点] 开始执行工具...")
            
            # 获取要执行的工具
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls"):
                for tool_call in last_message.tool_calls:
                    print(f"⚙️  执行工具: {tool_call['name']}")
            
            # 执行工具
            result = original_tool_node.invoke(state)
            
            # 打印工具返回结果
            tool_messages = result["messages"]
            for msg in tool_messages:
                if hasattr(msg, "content"):
                    import json
                    try:
                        content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                        status = content.get("status", "unknown")
                        agent = content.get("agent", "")
                        
                        if status == "success":
                            if agent:
                                print(f"✅ {agent} 执行成功")
                            else:
                                print(f"✅ 工具执行成功")
                        elif status == "error":
                            message = content.get("message", "")
                            print(f"❌ 工具执行失败: {message}")
                        else:
                            print(f"📄 工具返回: {str(msg.content)[:100]}...")
                    except:
                        print(f"📄 工具返回: {str(msg.content)[:100]}...")
            
            return result
        
        # 定义路由函数
        def should_continue(state: AgentState) -> Literal["tools", "end"]:
            """判断是否继续调用工具"""
            messages = state["messages"]
            last_message = messages[-1]
            
            print("\n" + "~"*60)
            print("🔀 [路由判断]")
            
            # 如果有工具调用，继续
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                print("➡️  路由到: tools (执行工具)")
                return "tools"
            
            # 否则结束（Agent 认为任务已完成）
            print("➡️  路由到: end (任务完成)")
            return "end"
        
        # 添加节点
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        
        # 设置入口
        workflow.set_entry_point("agent")
        
        # 添加边
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        # 工具执行后返回 agent
        workflow.add_edge("tools", "agent")
        
        # 编译图
        return workflow.compile()
    
    def process(self, user_input: str) -> dict:
        """处理用户输入"""
        try:
            print("\n" + "="*60)
            print("🚀 [PlanningAgent] 开始处理请求")
            print(f"👤 用户输入: {user_input}")
            print("="*60)
            
            # 创建初始状态
            initial_state = {
                "messages": [HumanMessage(content=user_input)]
            }
            
            # 执行图
            result = self.graph.invoke(initial_state)
            
            # 提取最终响应
            final_message = result["messages"][-1]
            
            print("\n" + "="*60)
            print("🎉 [PlanningAgent] 处理完成")
            print(f"📊 总消息数: {len(result['messages'])}")
            print(f"💬 最终响应: {final_message.content[:200]}...")
            print("="*60 + "\n")
            
            return {
                "status": "success",
                "response": final_message.content,
                "messages": result["messages"]
            }
        except Exception as e:
            print(f"\n❌ [错误] {str(e)}\n")
            return {
                "status": "error",
                "response": f"处理请求时出错：{str(e)}"
            }


class PlanningAgentRunner:
    """PlanningAgent 运行器（简化接口）"""
    
    def __init__(self):
        self.agent = PlanningAgent()
    
    def process(self, user_input: str) -> dict:
        """处理用户输入"""
        return self.agent.process(user_input)


def create_planning_graph():
    """创建 PlanningAgent 图（工厂函数）"""
    agent = PlanningAgent()
    return agent.graph
