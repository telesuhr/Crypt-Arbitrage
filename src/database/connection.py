import os
import yaml
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

class DatabaseConfig:
    """データベース設定管理クラス"""
    
    def __init__(self):
        # 環境変数からDATABASE_URLを取得
        self.database_url = os.getenv('DATABASE_URL')
        
        if not self.database_url:
            # 従来の形式から構築
            host = os.getenv('DB_HOST', 'localhost')
            port = os.getenv('DB_PORT', '5432')
            name = os.getenv('DB_NAME', 'crypto_arbitrage')
            user = os.getenv('DB_USER', 'postgres')
            password = os.getenv('DB_PASSWORD', 'password')
            self.database_url = f"postgresql://{user}:{password}@{host}:{port}/{name}"
        
        logger.info(f"Database URL configured (host: {self._get_host_from_url()})")
    
    def _get_host_from_url(self) -> str:
        """URLからホスト名を抽出（ログ用）"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.database_url)
            return parsed.hostname or "unknown"
        except:
            return "unknown"
    
    @property
    def connection_string(self) -> str:
        """SQLAlchemy用の接続文字列を生成"""
        return self.database_url


class DatabaseConnection:
    """データベース接続管理クラス"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._engine = None
        self._session_factory = None
    
    @property
    def engine(self):
        """SQLAlchemyエンジンを取得（遅延初期化）"""
        if self._engine is None:
            # TailScale/リモート接続用の設定
            self._engine = create_engine(
                self.config.connection_string,
                poolclass=NullPool,  # 長時間接続対応
                connect_args={
                    "connect_timeout": 10,
                    "application_name": "crypto_arbitrage",
                    "options": "-c statement_timeout=30000"  # 30秒タイムアウト
                },
                echo=os.getenv('SQL_ECHO', 'false').lower() == 'true'
            )
            logger.info("SQLAlchemy engine created for PostgreSQL")
        return self._engine
    
    @property
    def session_factory(self):
        """セッションファクトリを取得"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory
    
    @contextmanager
    def get_session(self) -> Session:
        """SQLAlchemyセッションのコンテキストマネージャ"""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None):
        """単一クエリを実行（SQLAlchemy経由）"""
        with self.get_session() as session:
            result = session.execute(text(query), params or {})
            return result.fetchall()
    
    def execute_many(self, query: str, params_list: list):
        """バッチクエリを実行（SQLAlchemy経由）"""
        with self.get_session() as session:
            # executemanyの場合は各パラメータで実行
            for params in params_list:
                session.execute(text(query), params)
            return len(params_list)
    
    def test_connection(self) -> bool:
        """データベース接続をテスト"""
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1")).scalar()
                logger.info("Database connection test successful")
                return result == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def close(self):
        """すべての接続を閉じる"""
        if self._engine:
            self._engine.dispose()
            logger.info("SQLAlchemy engine disposed")


# グローバルインスタンス
db = DatabaseConnection()


# ヘルパー関数
def get_db_session():
    """セッション取得のヘルパー関数"""
    return db.get_session()