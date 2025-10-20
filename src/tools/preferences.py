from __future__ import annotations

"""用户偏好管理工具。

提供偏好存储、检索和管理的工具函数：
- 与向量存储集成，支持语义检索
- 与数据库存储同步，确保数据一致性
- 为 PlanningAgent 和 SummaryAgent 提供偏好查询接口
"""

import os
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from src.storage.database import get_session
from src.storage.models import UserPreference
from src.storage.vector_store import get_vector_store


def store_preference(
    user_id: str,
    preference_key: str,
    preference_value: str,
    description: str,
    weight: float = 1.0
) -> Dict[str, Any]:
    """存储用户偏好。
    
    同时存储到数据库和向量数据库，确保数据一致性。
    
    Args:
        user_id: 用户标识
        preference_key: 偏好键（如 "working_hours", "meeting_buffer"）
        preference_value: 偏好值（JSON 字符串）
        description: 偏好描述（用于向量检索）
        weight: 偏好权重
        
    Returns:
        操作结果字典
    """
    try:
        with get_session() as session:
            # 检查是否已存在相同的偏好
            existing = session.scalars(
                select(UserPreference).where(
                    UserPreference.user_id == user_id,
                    UserPreference.preference_key == preference_key
                )
            ).first()
            
            if existing:
                # 更新现有偏好
                existing.preference_value = preference_value
                existing.description = description
                existing.weight = weight
                
                # 更新向量存储
                vector_store = get_vector_store()
                vector_store.update_preference(
                    preference_id=existing.id,
                    description=description,
                    metadata={
                        "user_id": user_id,
                        "preference_key": preference_key,
                        "weight": weight
                    }
                )
                
                session.flush()
                return {
                    "status": "success",
                    "action": "updated",
                    "preference_id": existing.id,
                    "message": f"偏好 '{preference_key}' 已更新"
                }
            else:
                # 创建新偏好
                preference = UserPreference(
                    user_id=user_id,
                    preference_key=preference_key,
                    description=description,
                    preference_value=preference_value,
                    weight=weight
                )
                session.add(preference)
                session.flush()
                
                # 添加到向量存储
                vector_store = get_vector_store()
                vector_id = vector_store.add_preference(
                    user_id=user_id,
                    preference_key=preference_key,
                    description=description,
                    metadata={
                        "user_id": user_id,
                        "preference_key": preference_key,
                        "weight": weight
                    }
                )
                
                return {
                    "status": "success",
                    "action": "created",
                    "preference_id": preference.id,
                    "vector_id": vector_id,
                    "message": f"偏好 '{preference_key}' 已创建"
                }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"存储偏好失败: {str(e)}"
        }


def retrieve_preferences(
    user_id: str,
    query: Optional[str] = None,
    preference_key: Optional[str] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """检索用户偏好。
    
    支持两种检索方式：
    1. 语义检索：通过 query 文本进行向量搜索
    2. 精确检索：通过 preference_key 精确匹配
    
    Args:
        user_id: 用户标识
        query: 查询文本（用于语义检索）
        preference_key: 偏好键（用于精确检索）
        top_k: 返回结果数量
        
    Returns:
        偏好列表和元信息
    """
    try:
        preferences = []
        
        if query:
            # 语义检索
            vector_store = get_vector_store()
            vector_results = vector_store.search_preferences(
                user_id=user_id,
                query=query,
                top_k=top_k
            )
            
            # 从数据库获取完整信息
            with get_session() as session:
                for result in vector_results:
                    db_preference = session.get(UserPreference, result["id"])
                    if db_preference:
                        preferences.append({
                            "id": db_preference.id,
                            "preference_key": db_preference.preference_key,
                            "description": db_preference.description,
                            "preference_value": db_preference.preference_value,
                            "weight": db_preference.weight,
                            "similarity": result["similarity"],
                            "created_at": db_preference.created_at.isoformat(),
                            "updated_at": db_preference.updated_at.isoformat()
                        })
        else:
            # 精确检索或获取所有偏好
            with get_session() as session:
                stmt = select(UserPreference).where(UserPreference.user_id == user_id)
                if preference_key:
                    stmt = stmt.where(UserPreference.preference_key == preference_key)
                
                db_preferences = session.scalars(stmt).all()
                
                for pref in db_preferences:
                    preferences.append({
                        "id": pref.id,
                        "preference_key": pref.preference_key,
                        "description": pref.description,
                        "preference_value": pref.preference_value,
                        "weight": pref.weight,
                        "created_at": pref.created_at.isoformat(),
                        "updated_at": pref.updated_at.isoformat()
                    })
        
        return {
            "status": "success",
            "preferences": preferences,
            "count": len(preferences),
            "query": query or preference_key or "all"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"检索偏好失败: {str(e)}",
            "preferences": []
        }


def update_preference_weight(preference_id: str, new_weight: float) -> Dict[str, Any]:
    """更新偏好权重。
    
    Args:
        preference_id: 偏好 ID
        new_weight: 新权重
        
    Returns:
        操作结果
    """
    try:
        with get_session() as session:
            preference = session.get(UserPreference, preference_id)
            if not preference:
                return {
                    "status": "error",
                    "message": "偏好不存在"
                }
            
            old_weight = preference.weight
            preference.weight = new_weight
            session.flush()
            
            # 更新向量存储中的元数据
            vector_store = get_vector_store()
            vector_store.update_preference(
                preference_id=preference_id,
                description=preference.description,
                metadata={
                    "user_id": preference.user_id,
                    "preference_key": preference.preference_key,
                    "weight": new_weight
                }
            )
            
            return {
                "status": "success",
                "message": f"偏好权重已从 {old_weight} 更新为 {new_weight}",
                "preference_id": preference_id
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"更新权重失败: {str(e)}"
        }


def delete_preference(preference_id: str) -> Dict[str, Any]:
    """删除偏好。
    
    Args:
        preference_id: 偏好 ID
        
    Returns:
        操作结果
    """
    try:
        with get_session() as session:
            preference = session.get(UserPreference, preference_id)
            if not preference:
                return {
                    "status": "error",
                    "message": "偏好不存在"
                }
            
            preference_key = preference.preference_key
            session.delete(preference)
            
            # 从向量存储删除
            vector_store = get_vector_store()
            vector_store.delete_preference(preference_id)
            
            return {
                "status": "success",
                "message": f"偏好 '{preference_key}' 已删除",
                "preference_id": preference_id
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"删除偏好失败: {str(e)}"
        }


def get_preference_summary(user_id: str) -> Dict[str, Any]:
    """获取用户偏好摘要。
    
    Args:
        user_id: 用户标识
        
    Returns:
        偏好统计信息
    """
    try:
        with get_session() as session:
            preferences = session.scalars(
                select(UserPreference).where(UserPreference.user_id == user_id)
            ).all()
            
            # 统计信息
            total_count = len(preferences)
            avg_weight = sum(p.weight for p in preferences) / total_count if total_count > 0 else 0
            
            # 按权重分组
            weight_groups = {}
            for pref in preferences:
                weight_range = f"{int(pref.weight)}-{int(pref.weight)+1}"
                weight_groups[weight_range] = weight_groups.get(weight_range, 0) + 1
            
            # 最常见的偏好键
            key_counts = {}
            for pref in preferences:
                key_counts[pref.preference_key] = key_counts.get(pref.preference_key, 0) + 1
            
            return {
                "status": "success",
                "summary": {
                    "total_preferences": total_count,
                    "average_weight": round(avg_weight, 2),
                    "weight_distribution": weight_groups,
                    "top_preference_keys": sorted(key_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取偏好摘要失败: {str(e)}"
        }
