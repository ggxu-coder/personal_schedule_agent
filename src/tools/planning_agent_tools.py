"""PlanningAgent 工具集"""
from typing import Dict, Any, Optional
from datetime import datetime

from ..agents.scheduler import SchedulerAgent
from ..agents.summary import SummaryAgent


# 创建子 Agent 实例（单例模式）
_scheduler_agent = None
_summary_agent = None


def get_scheduler_agent():
    """获取 SchedulerAgent 实例（单例）"""
    global _scheduler_agent
    if _scheduler_agent is None:
        _scheduler_agent = SchedulerAgent()
    return _scheduler_agent


def get_summary_agent():
    """获取 SummaryAgent 实例（单例）"""
    global _summary_agent
    if _summary_agent is None:
        _summary_agent = SummaryAgent()
    return _summary_agent


# ============ Agent 调用工具 ============

def call_scheduler_agent(request: str) -> Dict[str, Any]:
    """调用 SchedulerAgent 处理日程管理请求
    
    Args:
        request: 用户的日程管理请求（添加、修改、删除、查询等）
    
    Returns:
        SchedulerAgent 的处理结果
    """
    try:
        print(f"\n🔄 [PlanningAgent] 调用 SchedulerAgent")
        print(f"   请求: {request}")
        
        agent = get_scheduler_agent()
        result = agent.process(request)
        
        print(f"   结果: {result['status']}")
        
        return {
            "status": "success",
            "agent": "SchedulerAgent",
            "response": result.get("response", ""),
            "original_result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "agent": "SchedulerAgent",
            "message": f"调用 SchedulerAgent 失败：{str(e)}"
        }


def call_summary_agent(request: str) -> Dict[str, Any]:
    """调用 SummaryAgent 处理日程分析请求
    
    Args:
        request: 用户的分析请求（统计、总结、建议等）
    
    Returns:
        SummaryAgent 的处理结果
    """
    try:
        print(f"\n🔄 [PlanningAgent] 调用 SummaryAgent")
        print(f"   请求: {request}")
        
        agent = get_summary_agent()
        result = agent.process(request)
        
        print(f"   结果: {result['status']}")
        
        return {
            "status": "success",
            "agent": "SummaryAgent",
            "response": result.get("response", ""),
            "original_result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "agent": "SummaryAgent",
            "message": f"调用 SummaryAgent 失败：{str(e)}"
        }


# ============ 偏好管理工具 ============

# 简单的内存存储（实际项目中应该用数据库）
_user_preferences = {}


def store_preference(
    category: str,
    preference: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """存储用户偏好
    
    Args:
        category: 偏好类别（如 work_time, meeting_preference, break_time 等）
        preference: 偏好内容
        description: 偏好描述
    
    Examples:
        - category="work_time", preference="上午9点到12点效率最高"
        - category="meeting_preference", preference="尽量避免周五下午开会"
        - category="break_time", preference="每工作2小时休息15分钟"
    """
    try:
        _user_preferences[category] = {
            "preference": preference,
            "description": description,
            "updated_at": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "message": f"已保存偏好：{category}",
            "category": category,
            "preference": preference
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"保存偏好失败：{str(e)}"
        }


def get_preferences(category: Optional[str] = None) -> Dict[str, Any]:
    """获取用户偏好
    
    Args:
        category: 偏好类别，如果为 None 则返回所有偏好
    
    Returns:
        用户偏好信息
    """
    try:
        if category:
            if category in _user_preferences:
                return {
                    "status": "success",
                    "category": category,
                    "preference": _user_preferences[category]
                }
            else:
                return {
                    "status": "success",
                    "message": f"未找到类别 {category} 的偏好",
                    "category": category,
                    "preference": None
                }
        else:
            return {
                "status": "success",
                "message": f"共有 {len(_user_preferences)} 个偏好",
                "preferences": _user_preferences
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取偏好失败：{str(e)}"
        }


def clear_preferences() -> Dict[str, Any]:
    """清空所有用户偏好"""
    try:
        count = len(_user_preferences)
        _user_preferences.clear()
        return {
            "status": "success",
            "message": f"已清空 {count} 个偏好"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"清空偏好失败：{str(e)}"
        }
