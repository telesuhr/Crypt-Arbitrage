#!/usr/bin/env python3
"""
PostgreSQL接続テストスクリプト
TailScale経由での接続も含めて確認
"""

import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db
from src.database.models import Exchange, CurrencyPair, PriceTick
from sqlalchemy import text
from datetime import datetime
import pytz


def test_connection():
    """PostgreSQL接続をテスト"""
    print("🔍 PostgreSQL接続テスト")
    print("=" * 50)
    
    # 接続テスト
    if db.test_connection():
        print("✅ データベース接続成功")
    else:
        print("❌ データベース接続失敗")
        return False
    
    # 詳細情報取得
    with db.get_session() as session:
        # PostgreSQLバージョン
        version = session.execute(text("SELECT version()")).scalar()
        print(f"\n📊 PostgreSQL情報:")
        print(f"バージョン: {version.split(',')[0]}")
        
        # 現在の接続情報
        current_db = session.execute(text("SELECT current_database()")).scalar()
        current_user = session.execute(text("SELECT current_user")).scalar()
        print(f"データベース: {current_db}")
        print(f"ユーザー: {current_user}")
        
        # テーブル一覧
        tables = session.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)).fetchall()
        
        print(f"\n📋 テーブル一覧:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # データ件数確認
        print(f"\n📈 データ件数:")
        
        # 取引所
        exchange_count = session.query(Exchange).count()
        print(f"  取引所: {exchange_count}件")
        
        # 通貨ペア
        pair_count = session.query(CurrencyPair).count()
        active_pairs = session.query(CurrencyPair).filter_by(is_active=True).count()
        print(f"  通貨ペア: {pair_count}件（アクティブ: {active_pairs}件）")
        
        # 価格データ
        price_count = session.query(PriceTick).count()
        print(f"  価格データ: {price_count:,}件")
        
        # 最新データ確認
        latest_price = session.query(PriceTick).order_by(PriceTick.timestamp.desc()).first()
        if latest_price:
            jst = pytz.timezone('Asia/Tokyo')
            latest_time = latest_price.timestamp.replace(tzinfo=pytz.UTC).astimezone(jst)
            age = datetime.now(jst) - latest_time
            print(f"\n⏰ 最新データ: {int(age.total_seconds())}秒前")
    
    return True


def test_tailscale_connection():
    """TailScale経由での接続情報を表示"""
    print(f"\n🌐 TailScale接続設定例:")
    print("=" * 50)
    
    # 現在の設定から情報を抽出
    from urllib.parse import urlparse
    parsed = urlparse(db.config.database_url)
    
    print("1. データ収集端末（メイン）:")
    print(f"   DATABASE_URL=postgresql://{parsed.username}:****@localhost:{parsed.port}/{parsed.path[1:]}")
    
    print("\n2. 監視端末（TailScale経由）:")
    print(f"   DATABASE_URL=postgresql://{parsed.username}:****@[tailscale-hostname]:{parsed.port}/{parsed.path[1:]}")
    print("   ※ [tailscale-hostname] は実際のTailScaleホスト名に置き換えてください")
    
    print("\n3. 読み取り専用ユーザーの作成（推奨）:")
    print("   ```sql")
    print("   CREATE USER readonly_monitor WITH PASSWORD 'secure_password';")
    print("   GRANT CONNECT ON DATABASE crypto_arbitrage TO readonly_monitor;")
    print("   GRANT USAGE ON SCHEMA public TO readonly_monitor;")
    print("   GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_monitor;")
    print("   ```")


def main():
    """メイン処理"""
    print("🚀 PostgreSQL接続テスト（SQLite不使用版）")
    print()
    
    try:
        if test_connection():
            test_tailscale_connection()
            
            print("\n✅ すべてのテスト完了！")
            print("\n📌 次のステップ:")
            print("1. TailScaleでホスト名を確認: tailscale status")
            print("2. 監視端末の.envファイルを更新")
            print("3. 監視端末で実行: python scripts/readonly_monitor.py")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()