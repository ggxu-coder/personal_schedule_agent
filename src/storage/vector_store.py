from __future__ import annotations

"""Chroma 向量存储实现。

提供用户偏好的向量化存储与检索功能：
- 使用 ChromaDB 作为本地向量数据库
- 通过 LongCat API 获取 embeddings
- 支持偏好存储、检索和删除操作
"""

import os
import uuid
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel


class PreferenceVectorStore:
    """用户偏好向量存储管理器。
    
    使用 ChromaDB 存储用户偏好的向量表示，支持语义检索。
    """
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        """初始化向量存储。
        
        Args:
            persist_directory: ChromaDB 数据持久化目录
        """
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 初始化 embeddings（使用 LongCat API）
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("LONGCAT_API_KEY"),
            base_url=os.getenv("LONGCAT_API_BASE", "https://api.longcat.chat/openai"),
            model="text-embedding-ada-002"  # LongCat 支持的 embedding 模型
        )
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="user_preferences",
            metadata={"description": "用户偏好向量存储"}
        )
    
    def add_preference(
        self, 
        user_id: str, 
        preference_key: str,
        description: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加用户偏好。
        
        Args:
            user_id: 用户标识
            preference_key: 偏好键
            description: 偏好描述文本
            metadata: 额外元数据
            
        Returns:
            偏好 ID
        """
        preference_id = str(uuid.uuid4())
        
        # 生成向量嵌入
        embedding = self.embeddings.embed_query(description)
        
        # 构建元数据
        full_metadata = {
            "user_id": user_id,
            "preference_key": preference_key,
            "description": description,
            **(metadata or {})
        }
        
        # 添加到集合
        self.collection.add(
            ids=[preference_id],
            embeddings=[embedding],
            documents=[description],
            metadatas=[full_metadata]
        )
        
        return preference_id
    
    def search_preferences(
        self, 
        user_id: str, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """搜索用户偏好。
        
        Args:
            user_id: 用户标识
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            匹配的偏好列表，包含相似度分数
        """
        # 生成查询向量
        query_embedding = self.embeddings.embed_query(query)
        
        # 执行向量搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"user_id": user_id}  # 仅搜索该用户的偏好
        )
        
        # 格式化结果
        preferences = []
        if results["ids"] and results["ids"][0]:
            for i, preference_id in enumerate(results["ids"][0]):
                preferences.append({
                    "id": preference_id,
                    "description": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "similarity": results["distances"][0][i] if results["distances"] else 0.0
                })
        
        return preferences
    
    def get_all_preferences(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有偏好。
        
        Args:
            user_id: 用户标识
            
        Returns:
            用户偏好列表
        """
        results = self.collection.get(
            where={"user_id": user_id}
        )
        
        preferences = []
        if results["ids"]:
            for i, preference_id in enumerate(results["ids"]):
                preferences.append({
                    "id": preference_id,
                    "description": results["documents"][i],
                    "metadata": results["metadatas"][i]
                })
        
        return preferences
    
    def delete_preference(self, preference_id: str) -> bool:
        """删除偏好。
        
        Args:
            preference_id: 偏好 ID
            
        Returns:
            是否删除成功
        """
        try:
            self.collection.delete(ids=[preference_id])
            return True
        except Exception:
            return False
    
    def update_preference(
        self, 
        preference_id: str, 
        description: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新偏好。
        
        Args:
            preference_id: 偏好 ID
            description: 新的描述文本
            metadata: 新的元数据
            
        Returns:
            是否更新成功
        """
        try:
            # 生成新的向量嵌入
            embedding = self.embeddings.embed_query(description)
            
            # 更新文档和嵌入
            self.collection.update(
                ids=[preference_id],
                embeddings=[embedding],
                documents=[description],
                metadatas=[metadata or {}]
            )
            return True
        except Exception:
            return False


# 全局向量存储实例
_vector_store: Optional[PreferenceVectorStore] = None


def get_vector_store() -> PreferenceVectorStore:
    """获取全局向量存储实例。
    
    Returns:
        向量存储实例
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = PreferenceVectorStore()
    return _vector_store


def reset_vector_store():
    """重置向量存储实例（主要用于测试）。"""
    global _vector_store
    _vector_store = None
