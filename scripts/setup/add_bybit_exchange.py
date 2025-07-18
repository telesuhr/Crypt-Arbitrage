#!/usr/bin/env python3
"""
Bybit取引所をデータベースに追加
"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db
from src.database.models import Exchange
from datetime import datetime
import pytz


def add_bybit_exchange():
    """Bybit取引所をデータベースに追加"""
    with db.get_session() as session:
        # 既存のBybitをチェック
        existing = session.query(Exchange).filter_by(code='bybit').first()
        
        if existing:
            print(f"✅ Bybit already exists in database (ID: {existing.id})")
            if not existing.is_active:
                existing.is_active = True
                session.commit()
                print("   Activated Bybit exchange")
            return existing
        
        # 新規追加
        bybit = Exchange(
            code='bybit',
            name='Bybit',
            is_active=True,
            created_at=datetime.now(pytz.UTC),
            updated_at=datetime.now(pytz.UTC)
        )
        
        session.add(bybit)
        session.commit()
        
        print(f"✅ Added Bybit exchange to database (ID: {bybit.id})")
        return bybit


def add_bybit_currency_pairs():
    """BybitのUSDT建て通貨ペアを追加（JPY表示用）"""
    from src.database.models import CurrencyPair
    
    pairs_to_add = [
        ('BTC/JPY', 'BTC', 'JPY'),  # 実際はBTCUSDT→JPY変換
        ('ETH/JPY', 'ETH', 'JPY'),  # 実際はETHUSDT→JPY変換
        ('XRP/JPY', 'XRP', 'JPY'),  # 実際はXRPUSDT→JPY変換
        ('LTC/JPY', 'LTC', 'JPY'),  # 実際はLTCUSDT→JPY変換
        ('BCH/JPY', 'BCH', 'JPY'),  # 実際はBCHUSDT→JPY変換
        ('ETC/JPY', 'ETC', 'JPY'),  # 実際はETCUSDT→JPY変換
    ]
    
    with db.get_session() as session:
        added_count = 0
        
        for symbol, base, quote in pairs_to_add:
            # 既存チェック
            existing = session.query(CurrencyPair).filter_by(symbol=symbol).first()
            
            if not existing:
                pair = CurrencyPair(
                    symbol=symbol,
                    base_currency=base,
                    quote_currency=quote,
                    is_active=True,
                    created_at=datetime.now(pytz.UTC),
                    updated_at=datetime.now(pytz.UTC)
                )
                session.add(pair)
                added_count += 1
                print(f"   Added {symbol}")
            else:
                if not existing.is_active:
                    existing.is_active = True
                    print(f"   Activated {symbol}")
        
        session.commit()
        print(f"\n✅ Added/activated {added_count} currency pairs")


def main():
    """メイン処理"""
    print("🚀 Adding Bybit exchange to database")
    print("=" * 50)
    
    # Bybit取引所を追加
    add_bybit_exchange()
    
    # 通貨ペアを追加
    print("\n📊 Adding Bybit currency pairs...")
    add_bybit_currency_pairs()
    
    # 確認
    from src.database.models import CurrencyPair
    
    with db.get_session() as session:
        # 取引所数
        exchange_count = session.query(Exchange).filter_by(is_active=True).count()
        print(f"\n📈 Active exchanges: {exchange_count}")
        
        # 通貨ペア数
        pair_count = session.query(CurrencyPair).filter_by(is_active=True).count()
        print(f"📊 Active currency pairs: {pair_count}")
    
    print("\n✅ Bybit setup completed!")
    print("\n📌 Next steps:")
    print("1. Restart data collection: python src/main.py collect")
    print("2. Monitor with: python scripts/monitor_all_pairs.py")


if __name__ == "__main__":
    main()