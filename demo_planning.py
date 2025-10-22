"""PlanningAgent 演示脚本"""
import os
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.planning import PlanningAgentRunner


def main():
    """演示函数"""
    # 初始化数据库
    print("📦 初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成\n")

    # 创建 Agent
    print("🧠 创建 PlanningAgent...")
    agent = PlanningAgentRunner()
    print("✅ Agent 创建完成\n")

    # 计算日期
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 测试用例
    test_cases = [
        # 1. 偏好设置
        "我喜欢上午9点到12点工作，效率最高",
        
        # 2. 日程管理
        f"添加{tomorrow}上午10点到11点的项目会议",
        
        # 3. 查询偏好
        "查看我的偏好设置",
        
        # 4. 日程分析
        "总结一下最近的日程安排",
        
        # 5. 智能规划
        "帮我规划明天下午的工作，我想学习新技术2小时",
    ]

    print("="*60)
    print("开始演示 PlanningAgent")
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
            print("\n⏸️  等待 3 秒避免 API 限流...")
            time.sleep(3)
            input("按 Enter 继续下一个演示...")

    print("\n\n" + "="*60)
    print("✅ 演示完成")
    print("="*60)


if __name__ == "__main__":
    main()
