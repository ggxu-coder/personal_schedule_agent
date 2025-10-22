"""配置文件"""

# API 调用配置
API_CONFIG = {
    # 重试配置
    "max_retries": 3,           # 最大重试次数
    "retry_delay": 5,           # 重试延迟（秒）
    
    # 限流配置
    "demo_delay": 3,            # 演示脚本中每个测试用例之间的延迟（秒）
    "batch_delay": 1,           # 批量操作中每个操作之间的延迟（秒）
}

# LLM 配置
LLM_CONFIG = {
    "temperature": 0,           # 温度参数
    "timeout": 60,              # 超时时间（秒）
}

# 数据库配置
DB_CONFIG = {
    "db_dir": "./data",
    "db_name": "scheduler.db",
}
