"""简单测试 SchedulerAgent（无交互）"""
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 加载环境变量
load_dotenv()

from src.storage.database import init_db
from src.agents.scheduler import SchedulerAgentRunner

def main():
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
        {
            "name": "添加事件",
            "input": f"添加{tomorrow}上午9点到10点的团队会议",
            "expected": "success"
        },
        {
            "name": "查询事件",
            "input": f"查询{tomorrow}的所有日程",
            "expected": "success"
        },
        {
            "name": "添加冲突事件",
            "input": f"添加{tomorrow}上午9点30分到10点30分的项目讨论",
            "expected": "error"  # 应该检测到冲突
        },
        {
            "name": "查询空闲时间",
            "input": f"查询{tomorrow}的空闲时间",
            "expected": "success"
        },
    ]

    print("="*60)
    print("开始测试 SchedulerAgent")
    print("="*60)

    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'='*60}")
        print(f"测试用例 {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'='*60}")
        
        result = agent.process(test_case["input"])
        
        print(f"\n最终结果:")
        print(f"状态: {result['status']}")
        print(f"响应: {result['response'][:200]}...")
        
        results.append({
            "test": test_case["name"],
            "status": result["status"],
            "passed": result["status"] == test_case["expected"]
        })

    print("\n\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for r in results:
        status_icon = "✅" if r["passed"] else "❌"
        print(f"{status_icon} {r['test']}: {r['status']}")
    
    passed = sum(1 for r in results if r["passed"])
    print(f"\n通过: {passed}/{len(results)}")
    print("="*60)

if __name__ == "__main__":
    main()
