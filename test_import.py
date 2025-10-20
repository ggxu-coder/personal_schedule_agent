#!/usr/bin/env python3
"""测试导入是否正常"""

try:
    from src.agents.scheduler import SchedulerAgentRunner, SYSTEM_PROMPT
    print("✅ 导入成功！")
    print(f"SYSTEM_PROMPT: {SYSTEM_PROMPT[:50]}...")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
except Exception as e:
    print(f"❌ 其他错误: {e}")
