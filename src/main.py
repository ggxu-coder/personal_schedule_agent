from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.workflow import MultiAgentRunner
from src.utils.prompt_templates import get_prompt_template


def interactive_loop() -> None:
    """交互式循环，支持多智能体协作。"""
    load_dotenv()
    
    # 仅检查并使用 OpenAI 提供商
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if openai_key:
        print("🤖 使用 OpenAI API 启动多智能体日程管理系统")
        provider = "openai"
    else:
        print("❌ 未检测到 API 密钥，请在 .env 中配置 OPENAI_API_KEY")
        sys.exit(1)
    
    print("\n📋 系统功能：")
    print("  • 日程管理：添加/删除/修改日程事件")
    print("  • 智能规划：任务分解和时间安排")
    print("  • 总结分析：日程回顾和优化建议")
    print("  • 偏好学习：理解和应用用户偏好")
    print("\n💡 示例用法：")
    print("  • '明天上午9点添加团队会议'")
    print("  • '帮我规划下周的学习计划'")
    print("  • '总结一下本周的表现'")
    print("  • '我喜欢上午学习'")
    print("\n输入 'exit' 或 'quit' 退出系统\n")
    
    # 创建多智能体运行器
    runner = MultiAgentRunner(workflow_type="full", provider=provider)
    
    while True:
        try:
            user_input = input("👤 你：").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in {"exit", "quit", "退出"}:
                print("👋 感谢使用，再见！")
                break
            
            # 处理用户输入
            print("🤖 Agent：", end="", flush=True)
            result = runner.process_input(user_input)
            
            if result["status"] == "success":
                print(result["response"])
                
                # 显示意图信息（调试用）
                if result.get("intent"):
                    print(f"🔍 识别意图：{result['intent']}")
            else:
                print(f"❌ 处理失败：{result.get('message', '未知错误')}")
            
            print()  # 空行分隔
            
        except KeyboardInterrupt:
            print("\n\n👋 检测到中断信号，正在退出...")
            break
        except Exception as e:
            print(f"\n❌ 系统错误：{str(e)}")
            print("请重试或联系技术支持")


def demo_mode() -> None:
    """演示模式，展示系统功能。"""
    load_dotenv()
    
    # 检查 API 配置（仅 OpenAI）
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_key:
        print("❌ 未检测到 API 密钥，无法运行演示")
        return
    
    provider = "openai"
    
    print("🎬 多智能体日程管理系统演示模式")
    print("=" * 50)
    
    # 创建运行器
    runner = MultiAgentRunner(workflow_type="full", provider=provider)
    
    # 演示用例
    demo_cases = [
        {
            "input": "请帮我添加一个明天上午9点到10点的团队会议",
            "description": "日程管理功能演示"
        },
        {
            "input": "帮我规划下周的学习计划，每天2小时",
            "description": "智能规划功能演示"
        },
        {
            "input": "总结一下本周的表现",
            "description": "总结分析功能演示"
        },
        {
            "input": "我喜欢上午学习",
            "description": "偏好管理功能演示"
        }
    ]
    
    for i, case in enumerate(demo_cases, 1):
        print(f"\n📝 演示 {i}：{case['description']}")
        print(f"👤 用户输入：{case['input']}")
        
        result = runner.process_input(case['input'])
        
        if result["status"] == "success":
            print(f"🤖 Agent 回复：{result['response']}")
            print(f"🔍 识别意图：{result.get('intent', 'unknown')}")
        else:
            print(f"❌ 处理失败：{result.get('message', '未知错误')}")
        
        print("-" * 50)
    
    print("\n✅ 演示完成！")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo_mode()
    else:
        interactive_loop()


