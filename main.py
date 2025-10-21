"""主入口文件"""
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.scheduler import SchedulerAgentRunner


def main():
    """主函数"""
    # 初始化数据库
    print("📦 初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成\n")

    # 创建 Agent
    print("🤖 创建 SchedulerAgent...")
    agent = SchedulerAgentRunner()
    print("✅ Agent 创建完成\n")

    print("="*60)
    print("欢迎使用 SchedulerAgent - 智能日程管理助手")
    print("="*60)
    print("\n可以尝试的命令：")
    print("  - 添加明天上午9点到10点的团队会议")
    print("  - 查询明天的所有日程")
    print("  - 查询明天的空闲时间")
    print("  - 删除事件1")
    print("  - 输入 'quit' 或 'exit' 退出\n")

    # 保持对话历史
    # add_messages 会自动合并新消息到历史中
    from langchain_core.messages import HumanMessage
    conversation_state = {"messages": []}

    # 交互循环
    while True:
        try:
            user_input = input("\n👤 你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("\n👋 再见！")
                break
            
            # 将新消息添加到状态中
            # add_messages 注解会自动合并消息列表
            conversation_state = agent.agent.graph.invoke({
                "messages": conversation_state["messages"] + [HumanMessage(content=user_input)]
            })
            
            # 显示结果
            final_message = conversation_state["messages"][-1]
            print(f"\n🤖 Agent: {final_message.content}")
                
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")


if __name__ == "__main__":
    main()
