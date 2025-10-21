"""SchedulerAgent - 日程管理智能体"""
import os
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv, find_dotenv
from ..graph.state import AgentState
from ..tools.scheduler_agent_tools import (
    add_event,
    update_event,
    remove_event,
    get_event,
    list_events,
    get_free_slots,
)

load_dotenv()

model_name = os.getenv("MODEL_NAME")
api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")

class SchedulerAgent:
    """日程管理 Agent"""
    
    def __init__(self):
        self.llm = self._create_llm()
        self.tools = self._build_tools()
        self.graph = self._build_graph()
    
    def _create_llm(self):
        """创建 LLM"""
        return ChatOpenAI(
        temperature=0,
        model=model_name,
        api_key=api_key,
        base_url=base_url)
    
    def _build_tools(self):
        """构建工具集"""
        tools = [
            StructuredTool.from_function(
                name="add_event",
                description="添加日程事件。自动检测时间冲突，如有冲突会返回错误。需要提供标题、开始时间、结束时间，可选描述、地点、标签。如需强制添加（忽略冲突），设置 force=True",
                func=add_event,
            ),
            StructuredTool.from_function(
                name="update_event",
                description="更新日程事件。自动检测时间冲突，如有冲突会返回错误。需要提供事件ID和要更新的字段。如需强制更新（忽略冲突），设置 force=True",
                func=update_event,
            ),
            StructuredTool.from_function(
                name="remove_event",
                description="删除日程事件。需要提供事件ID",
                func=remove_event,
            ),
            StructuredTool.from_function(
                name="get_event",
                description="查询单个日程事件的详细信息。需要提供事件ID",
                func=get_event,
            ),
            StructuredTool.from_function(
                name="list_events",
                description="列出日程事件列表。可以按日期范围和状态筛选",
                func=list_events,
            ),
            StructuredTool.from_function(
                name="get_free_slots",
                description="查询指定日期的空闲时间段。需要提供日期，可选最小时长",
                func=get_free_slots,
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
            print("🤖 [Agent 节点] 开始推理...")
            print(f"📝 当前消息数: {len(messages)}")
            
            # 获取当前时间
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 添加系统提示
            system_message = SystemMessage(content=f"""您是专门处理日程管理的助理。

当前时间: {current_time}
当前日期: {current_date}

您的职责是帮助用户管理他们的日程安排，包括添加、修改、删除和查询事件。

工作原则：

1. 主动执行，而非过度询问
   - 当用户表达了明确的时间安排意图时，直接调用相应工具执行
   - 只在信息不足或遇到冲突时才向用户确认
   - 不要在执行前反复确认用户已经明确表达的意图

2. 持久处理冲突
   - 所有添加和修改操作都会自动检测时间冲突
   - 如果检测到冲突，向用户清晰展示冲突的事件详情
   - 询问用户是否仍要继续，如果用户确认，使用 force=True 参数重新执行
   - 记住之前的操作参数，用户确认后立即执行，不要重复询问

3. 利用对话历史
   - 您可以访问完整的对话历史
   - 记住之前讨论的事件详情和用户偏好
   - 当用户说"是"、"确认"、"继续"等时，理解这是对之前操作的确认
   - 使用历史信息中的参数，避免让用户重复提供信息

4. 任务完成标准
   - 检查每个工具调用的返回结果中的 status 字段
   - status="success" 表示操作成功完成
   - status="error" 表示需要处理错误或获取用户确认
   - 只有在成功完成用户请求或用户明确放弃时才结束任务

5. 时间处理
   - 基于当前时间 {current_time} 计算相对时间表达
   - 支持多种时间格式，包括相对时间（明天、下周）和绝对时间

请记住，只有在相关工具成功执行后（status="success"），任务才算完成。
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
                        message = content.get("message", "")
                        
                        if status == "success":
                            print(f"✅ 工具执行成功: {message}")
                        elif status == "error":
                            print(f"❌ 工具执行失败: {message}")
                        elif status == "warning":
                            print(f"⚠️  工具警告: {message}")
                        else:
                            print(f"📄 工具返回: {msg.content[:100]}...")
                    except:
                        print(f"📄 工具返回: {str(msg.content)[:100]}...")
            
            return result
        
        # 定义路由函数
        def should_continue(state: AgentState) -> Literal["tools", "end"]:
            """判断是否继续调用工具
            
            判断逻辑：
            1. 如果 Agent 发起了工具调用 -> 执行工具
            2. 如果 Agent 没有工具调用 -> 任务完成，结束
            
            Agent 会根据工具返回的结果（包含 status 字段）来决定：
            - 是否需要继续调用其他工具
            - 是否任务已完成
            - 是否需要向用户反馈
            """
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
            print("🚀 [SchedulerAgent] 开始处理请求")
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
            print("🎉 [SchedulerAgent] 处理完成")
            print(f"📊 总消息数: {len(result['messages'])}")
            print(f"💬 最终响应: {final_message.content}")
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


class SchedulerAgentRunner:
    """SchedulerAgent 运行器（简化接口）"""
    
    def __init__(self):
        self.agent = SchedulerAgent()
    
    def process(self, user_input: str) -> dict:
        """处理用户输入"""
        return self.agent.process(user_input)


def create_scheduler_graph():
    """创建 SchedulerAgent 图（工厂函数）"""
    agent = SchedulerAgent()
    return agent.graph
