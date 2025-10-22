"""SummaryAgent 演示脚本 - 自动运行测试用例"""
import os
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.summary import SummaryAgentRunner



def main():
    """演示函数"""
    # 初始化数据库
    print("📦 初始化数据库...")
    init_db()
    print("✅ 数据库初始化完成\n")

    # 创建 Agent
    print("📊 创建 SummaryAgent...")
    agent = SummaryAgentRunner()
    print("✅ Agent 创建完成\n")

    # 计算日期范围
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # 测试用例
    test_cases = [
        "总结一下最近的日程安排",
        f"分析一下 {week_ago} 到 {today} 的时间使用情况",
        "我最常做什么活动？",
        f"查看 {yesterday} 到 {today} 的所有事件详情",
    ]

    print("="*60)
    print("开始演示 SummaryAgent")
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
