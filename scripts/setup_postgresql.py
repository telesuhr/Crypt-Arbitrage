#!/usr/bin/env python3
"""
PostgreSQL移行セットアップスクリプト
SQLiteからPostgreSQLへの移行を支援
"""

import sys
import os
from pathlib import Path
import subprocess
import psycopg2
from psycopg2 import sql
import sqlite3
from datetime import datetime

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import Base
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


def check_postgresql_installed():
    """PostgreSQLがインストールされているか確認"""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL installed: {result.stdout.strip()}")
            return True
        return False
    except FileNotFoundError:
        return False


def create_database(host, port, user, password, dbname):
    """データベースを作成"""
    try:
        # postgres データベースに接続
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # データベースが存在するか確認
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (dbname,)
        )
        
        if cursor.fetchone():
            print(f"ℹ️  Database '{dbname}' already exists")
        else:
            # データベース作成
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(dbname)
            ))
            print(f"✅ Database '{dbname}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False


def migrate_data(sqlite_path, pg_url):
    """SQLiteからPostgreSQLへデータを移行"""
    print("\n📦 Starting data migration...")
    
    # SQLite接続
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # PostgreSQL接続
    pg_engine = create_engine(pg_url)
    
    # テーブル作成
    Base.metadata.create_all(pg_engine)
    
    # 移行するテーブル
    tables = [
        'exchanges',
        'currency_pairs',
        'price_ticks',
        'arbitrage_opportunities'
    ]
    
    for table in tables:
        try:
            # SQLiteからデータ取得
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if rows:
                # PostgreSQLに挿入
                with pg_engine.connect() as pg_conn:
                    # カラム名を取得
                    columns = [description[0] for description in sqlite_cursor.description]
                    
                    # プレースホルダーを作成
                    placeholders = ', '.join(['%s'] * len(columns))
                    insert_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
                    
                    # バッチ挿入
                    data = [tuple(row) for row in rows]
                    pg_conn.execute(insert_query, data)
                    pg_conn.commit()
                
                print(f"✅ Migrated {len(rows)} rows from {table}")
            else:
                print(f"ℹ️  No data in {table}")
                
        except Exception as e:
            print(f"❌ Error migrating {table}: {e}")
    
    sqlite_conn.close()
    print("\n✅ Migration completed!")


def generate_env_config(host, port, user, password, dbname):
    """PostgreSQL用の.env設定を生成"""
    pg_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    
    print("\n📝 Add this to your .env file:")
    print("-" * 50)
    print(f"# PostgreSQL configuration")
    print(f"DATABASE_URL={pg_url}")
    print("-" * 50)
    
    # .env.postgresqlサンプルファイルを作成
    env_sample = f"""# PostgreSQL configuration for multi-device setup
DATABASE_URL={pg_url}

# Keep other settings from your original .env
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here

# Optional: Read-only user for monitoring devices
# DATABASE_URL_READONLY=postgresql://readonly_user:password@{host}:{port}/{dbname}
"""
    
    with open('.env.postgresql', 'w') as f:
        f.write(env_sample)
    
    print(f"\n✅ Sample configuration saved to .env.postgresql")


def main():
    """メイン処理"""
    print("🚀 PostgreSQL Setup for Multi-Device Operation")
    print("=" * 50)
    
    # PostgreSQLインストール確認
    if not check_postgresql_installed():
        print("\n❌ PostgreSQL is not installed!")
        print("\nInstall PostgreSQL:")
        print("  Mac: brew install postgresql@14")
        print("  Ubuntu: sudo apt install postgresql postgresql-contrib")
        return
    
    # 接続情報を入力
    print("\n📋 PostgreSQL Connection Details:")
    host = input("Host [localhost]: ").strip() or "localhost"
    port = input("Port [5432]: ").strip() or "5432"
    user = input("Username [postgres]: ").strip() or "postgres"
    password = input("Password: ").strip()
    dbname = input("Database name [crypto_arbitrage]: ").strip() or "crypto_arbitrage"
    
    # データベース作成
    if not create_database(host, port, user, password, dbname):
        return
    
    # 既存のSQLiteデータを移行するか確認
    sqlite_path = "crypto_arbitrage.db"
    if os.path.exists(sqlite_path):
        migrate = input("\n📊 Existing SQLite database found. Migrate data? [Y/n]: ").strip().lower()
        if migrate != 'n':
            pg_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
            migrate_data(sqlite_path, pg_url)
    
    # 設定ファイル生成
    generate_env_config(host, port, user, password, dbname)
    
    print("\n✅ Setup completed!")
    print("\n📌 Next steps:")
    print("1. Update your .env file with the PostgreSQL URL")
    print("2. Configure pg_hba.conf for network access (if using multiple devices)")
    print("3. Restart data collection: python src/main.py collect")
    print("4. On monitoring device: python scripts/readonly_monitor.py")


if __name__ == "__main__":
    main()