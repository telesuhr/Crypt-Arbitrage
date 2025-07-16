import os
import yaml
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

class DatabaseConfig:
    """データベース設定管理クラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "database.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.config = config['database']
        self._resolve_env_vars()
    
    def _resolve_env_vars(self):
        """環境変数を解決"""
        for key, value in self.config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                default = None
                if ':' in env_var:
                    env_var, default = env_var.split(':', 1)
                self.config[key] = os.getenv(env_var, default)
    
    @property
    def connection_string(self) -> str:
        """SQLAlchemy用の接続文字列を生成"""
        return (
            f"postgresql://{self.config['user']}:{self.config['password']}"
            f"@{self.config['host']}:{self.config['port']}/{self.config['name']}"
        )
    
    @property
    def psycopg2_params(self) -> dict:
        """psycopg2用の接続パラメータを生成"""
        return {
            'host': self.config['host'],
            'port': self.config['port'],
            'database': self.config['name'],
            'user': self.config['user'],
            'password': self.config['password']
        }


class DatabaseConnection:
    """データベース接続管理クラス"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._engine = None
        self._session_factory = None
        self._connection_pool = None
    
    @property
    def engine(self):
        """SQLAlchemyエンジンを取得（遅延初期化）"""
        if self._engine is None:
            self._engine = create_engine(
                self.config.connection_string,
                poolclass=QueuePool,
                pool_size=self.config.config.get('pool_size', 10),
                max_overflow=self.config.config.get('max_overflow', 20),
                pool_timeout=self.config.config.get('pool_timeout', 30),
                pool_recycle=self.config.config.get('pool_recycle', 3600),
                echo=self.config.config.get('echo', False),
                echo_pool=self.config.config.get('echo_pool', False)
            )
            logger.info("SQLAlchemy engine created")
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
    
    @property
    def connection_pool(self):
        """psycopg2コネクションプールを取得"""
        if self._connection_pool is None:
            self._connection_pool = ThreadedConnectionPool(
                minconn=2,
                maxconn=self.config.config.get('pool_size', 10),
                **self.config.psycopg2_params
            )
            logger.info("psycopg2 connection pool created")
        return self._connection_pool
    
    @contextmanager
    def get_connection(self):
        """psycopg2接続のコンテキストマネージャ"""
        conn = self.connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.connection_pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """psycopg2カーソルのコンテキストマネージャ"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None):
        """単一クエリを実行"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_many(self, query: str, params_list: list):
        """バッチクエリを実行"""
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def test_connection(self) -> bool:
        """データベース接続をテスト"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                logger.info("Database connection test successful")
                return result['?column?'] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def close(self):
        """すべての接続を閉じる"""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("Connection pool closed")
        if self._engine:
            self._engine.dispose()
            logger.info("SQLAlchemy engine disposed")


# グローバルインスタンス
db = DatabaseConnection()


# ヘルパー関数
def get_db_session():
    """セッション取得のヘルパー関数"""
    return db.get_session()


def get_db_connection():
    """接続取得のヘルパー関数"""
    return db.get_connection()


def get_db_cursor():
    """カーソル取得のヘルパー関数"""
    return db.get_cursor()