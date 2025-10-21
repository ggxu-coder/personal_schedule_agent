"""数据库连接管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os

from .models import Base

# 数据库路径
DB_DIR = "./data"
DB_PATH = os.path.join(DB_DIR, "scheduler.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建引擎
engine = create_engine(DATABASE_URL, echo=False)

# 创建会话工厂
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """初始化数据库"""
    os.makedirs(DB_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Session:
    """获取数据库会话（上下文管理器）"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
