"""综合主入口 - 可选择使用 SchedulerAgent 或 SummaryAgent"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.scheduler import SchedulerAgentRunner
from src.agents.summary import SummaryAgentRunner


def main():
    """主函数"""
    # 初始化数据库
    print("📦 初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成\n")

    print("="*60)
    print("欢迎使用智能日程管理系统")
    print("="*60)
    print("\n请选择要使用的 Agent：")
    print("  1. SchedulerAgent - 日程管理（添加、修改、删除、查询）")
    print("  2. SummaryAgent - 日程分析（统计、总结、建议）")
    print("  3. 退出\n")

    while True:
        choice = input("请输入选项 (1/2/3): ").strip()
        
        if choice == "1":
            run_scheduler_agent()
            break
        elif choice == "2":
            run_summary_agent()
            break
        elif choice == "3":
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效选项，请重新输入")


def run_scheduler_agent():
    """运行 SchedulerAgent"""
    print("\n" + "="*60)
    print("🤖 启动 SchedulerAgent - 日程管理助手")
    print("="*60)
    
    agent = SchedulerAgentRunner()
    
    print("\n可以尝试的命令：")
    print("  - 添加明天上午9点到10点的团队会议")
    print("  - 查询明天的所有日程")
    print("  - 查询明天的空闲时间")
    print("  - 删除事件1")
    print("  - 输入 'quit' 或 'exit' 退出\n")

    from langchain_core.messages import HumanMessage
    conversation_state = {"messages": []}

    while True:
        try:
            user_input = input("\n👤 你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("\n👋 再见！")
                break
            
            conversation_state = agent.agent.graph.invoke({
                "messages": conversation_state["messages"] + [HumanMessage(content=user_input)]
            })
            
            final_message = conversation_state["messages"][-1]
            print(f"\n🤖 Agent: {final_message.content}")
                
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")


def run_summary_agent():
    """运行 SummaryAgent"""
    print("\n" + "="*60)
    print("📊 启动 SummaryAgent - 日程分析助手")
    print("="*60)
    
    agent = SummaryAgentRunner()
    
    print("\n可以尝试的命令：")
    print("  - 总结一下本周的日程安排")
    print("  - 分析一下我的时间使用情况")
    print("  - 我最常做什么活动？")
    print("  - 哪天最忙？")
    print("  - 输入 'quit' 或 'exit' 退出\n")

    from langchain_core.messages import HumanMessage
    conversation_state = {"messages": []}

    while True:
        try:
            user_input = input("\n👤 你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("\n👋 再见！")
                break
            
            conversation_state = agent.agent.graph.invoke({
                "messages": conversation_state["messages"] + [HumanMessage(content=user_input)]
            })
            
            final_message = conversation_state["messages"][-1]
            print(f"\n📊 Agent: {final_message.content}")
                
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")


if __name__ == "__main__":
    main()
