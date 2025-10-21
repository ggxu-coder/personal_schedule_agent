"""演示脚本 - 自动运行测试用例"""
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.scheduler import SchedulerAgentRunner


def main():
    """演示函数"""
    # 初始化数据库
    print("📦 初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成\n")

    # 创建 Agent
    print("🤖 创建 SchedulerAgent...")
    agent = SchedulerAgentRunner()
    print("✅ Agent 创建完成\n")

    # 计算明天的日期
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 测试用例
    test_cases = [
        f"添加{tomorrow}上午9点到10点的团队会议",
        f"查询{tomorrow}的所有日程",
        f"添加{tomorrow}上午9点30分到10点30分的项目讨论",  # 会有冲突
        f"查询{tomorrow}的空闲时间",
    ]

    print("="*60)
    print("开始演示 SchedulerAgent")
    print("="*60)

    for i, test_input in enumerate(test_cases, 1):
        print(f"\n\n{'='*60}")
        print(f"演示 {i}/{len(test_cases)}")
        print(f"{'='*60}")
        
        result = agent.process(test_input)
        
        print(f"\n📊 最终结果:")
        print(f"   状态: {result['status']}")
        print(f"   响应: {result['response']}")
        
        if i < len(test_cases):
            input("\n⏸️  按 Enter 继续下一个演示...")

    print("\n\n" + "="*60)
    print("✅ 演示完成")
    print("="*60)


if __name__ == "__main__":
    main()
