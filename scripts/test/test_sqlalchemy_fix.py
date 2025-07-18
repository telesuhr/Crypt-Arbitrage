#!/usr/bin/env python3
"""
SQLAlchemy 2.0互換性テスト
修正が正しく動作するか確認
"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db
from sqlalchemy import __version__ as sqlalchemy_version

def main():
    print("🔍 SQLAlchemy互換性テスト")
    print("=" * 50)
    print(f"SQLAlchemy version: {sqlalchemy_version}")
    
    # 1. 基本的な接続テスト
    print("\n1. 基本接続テスト...")
    if db.test_connection():
        print("✅ 接続成功！")
    else:
        print("❌ 接続失敗")
        return
    
    # 2. execute_queryテスト
    print("\n2. execute_queryテスト...")
    try:
        result = db.execute_query("SELECT current_timestamp AS now, version() AS version")
        for row in result:
            print(f"✅ 現在時刻: {row['now']}")
            print(f"✅ PostgreSQL: {row['version'].split(',')[0]}")
    except Exception as e:
        print(f"❌ エラー: {e}")
    
    # 3. パラメータ付きクエリテスト
    print("\n3. パラメータ付きクエリテスト...")
    try:
        result = db.execute_query(
            "SELECT :num1 + :num2 AS sum",
            {"num1": 10, "num2": 20}
        )
        for row in result:
            print(f"✅ 10 + 20 = {row['sum']}")
    except Exception as e:
        print(f"❌ エラー: {e}")
    
    print("\n✅ すべてのテストが完了しました！")
    print("\n別PCで実行する場合:")
    print("1. pip install -r requirements.txt")
    print("2. .envファイルを設定")
    print("3. python scripts/test_sqlalchemy_fix.py")

if __name__ == "__main__":
    main()