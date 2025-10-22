"""PlanningAgent 交互式入口文件（主控）"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.planning import PlanningAgentRunner


def main():
    """主函数"""
    # 初始化数据库
    print("📦 初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成\n")

    # 创建 Agent
    print("🧠 创建 PlanningAgent（主控）...")
    agent = PlanningAgentRunner()
    print("✅ Agent 创建完成\n")

    print("="*60)
    print("欢迎使用智能日程管理系统 - PlanningAgent（主控）")
    print("="*60)
    print("\nPlanningAgent 可以：")
    print("  📅 管理日程：添加、修改、删除、查询日程")
    print("  📊 分析总结：统计数据、生成报告、提供建议")
    print("  🎯 智能规划：基于偏好制定日程计划")
    print("  💾 偏好管理：记住你的习惯和喜好")
    print("\n示例命令：")
    print("  - 添加明天上午9点的团队会议")
    print("  - 总结一下本周的日程安排")
    print("  - 帮我规划下周的学习计划，每天2小时")
    print("  - 我喜欢上午工作，下午开会")
    print("  - 查看我的偏好设置")
    print("  - 输入 'quit' 或 'exit' 退出\n")

    # 保持对话历史
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
            conversation_state = agent.agent.graph.invoke({
                "messages": conversation_state["messages"] + [HumanMessage(content=user_input)]
            })
            
            # 显示结果
            final_message = conversation_state["messages"][-1]
            print(f"\n🧠 Agent: {final_message.content}")
                
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")


if __name__ == "__main__":
    main()
