"""SummaryAgent - 总结分析智能体"""
import os
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ..graph.state import AgentState
from ..tools.summary_agent_tools import (
    get_events_summary,
    get_events_detail,
    analyze_time_usage,
)
from dotenv import load_dotenv
load_dotenv()

class SummaryAgent:
    """总结分析 Agent"""
    
    def __init__(self):
        self.llm = self._create_llm()
        self.tools = self._build_tools()
        self.graph = self._build_graph()
    
    def _create_llm(self):
        """创建 LLM"""
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
            temperature=0
        )
    
    def _build_tools(self):
        """构建工具集"""
        tools = [
            StructuredTool.from_function(
                name="get_events_summary",
                description="获取事件统计摘要。返回指定时间范围内的事件数量、总时长、类型分布、时间段分布等统计信息。适合快速了解整体情况",
                func=get_events_summary,
            ),
            StructuredTool.from_function(
                name="get_events_detail",
                description="获取事件详细列表。返回指定时间范围内所有事件的完整信息。适合需要查看具体事件详情时使用",
                func=get_events_detail,
            ),
            StructuredTool.from_function(
                name="analyze_time_usage",
                description="分析时间使用情况。计算不同类型活动的时间占比，找出最耗时的活动。适合分析时间分配是否合理",
                func=analyze_time_usage,
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
            print("📊 [SummaryAgent 节点] 开始分析...")
            print(f"📝 当前消息数: {len(messages)}")
            
            # 获取当前时间
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 添加系统提示
            system_message = SystemMessage(content=f"""您是专门处理日程总结和分析的助理。

当前时间: {current_time}
当前日期: {current_date}

您的职责是帮助用户分析和总结他们的日程安排，提供有价值的洞察和建议。

工作原则：

1. 选择合适的分析工具
   - 快速概览：使用 get_events_summary 获取统计摘要
   - 详细查看：使用 get_events_detail 获取完整事件列表
   - 时间分析：使用 analyze_time_usage 分析时间分配
   - 可以组合使用多个工具获得更全面的分析

2. 提供有洞察力的分析
   - 不要只是罗列数据，要解读数据背后的含义
   - 识别模式和趋势（如最忙碌的时段、最常见的活动）
   - 对比不同时间段的差异
   - 发现潜在的问题（如时间分配不均、过度安排等）

3. 给出可行的建议
   - 基于分析结果提供具体的优化建议
   - 建议应该是可操作的，而不是泛泛而谈
   - 考虑用户的实际情况和需求
   - 建议要积极正面，鼓励用户改进

4. 清晰的报告结构
   - 总体概况：事件数量、总时长等关键指标
   - 详细分析：时间分布、活动类型、忙碌程度等
   - 发现与洞察：识别的模式和问题
   - 优化建议：具体的改进方向

5. 时间处理
   - 基于当前时间 {current_time} 计算相对时间
   - 支持"本周"、"上周"、"本月"等相对时间表达
   - 默认分析最近一周的数据（如果用户没有指定时间范围）

请记住，您的目标是帮助用户更好地理解和优化他们的时间使用。
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
                        
                        if status == "success":
                            # 打印关键统计信息
                            if "total_count" in content:
                                print(f"✅ 统计完成: 共 {content['total_count']} 个事件")
                            elif "count" in content:
                                print(f"✅ 查询完成: 找到 {content['count']} 个事件")
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
            print("🚀 [SummaryAgent] 开始处理请求")
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
            print("🎉 [SummaryAgent] 处理完成")
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


class SummaryAgentRunner:
    """SummaryAgent 运行器（简化接口）"""
    
    def __init__(self):
        self.agent = SummaryAgent()
    
    def process(self, user_input: str) -> dict:
        """处理用户输入"""
        return self.agent.process(user_input)


def create_summary_graph():
    """创建 SummaryAgent 图（工厂函数）"""
    agent = SummaryAgent()
    return agent.graph
