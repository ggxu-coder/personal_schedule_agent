"""重试辅助函数"""
import time
from functools import wraps


def retry_on_rate_limit(max_retries=3, delay=5):
    """装饰器：在遇到 429 错误时自动重试
    
    Args:
        max_retries: 最大重试次数
        delay: 每次重试的延迟（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    
                    # 检查是否是 429 错误
                    if "429" in error_msg or "rate limit" in error_msg.lower():
                        if attempt < max_retries - 1:
                            wait_time = delay * (attempt + 1)  # 递增延迟
                            print(f"\n⚠️  遇到 API 限流，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                    
                    # 其他错误直接抛出
                    raise
            
            # 所有重试都失败
            raise Exception(f"重试 {max_retries} 次后仍然失败")
        
        return wrapper
    return decorator


def add_delay_between_calls(delay=2):
    """装饰器：在函数调用之间添加延迟
    
    Args:
        delay: 延迟时间（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            time.sleep(delay)
            return result
        
        return wrapper
    return decorator
