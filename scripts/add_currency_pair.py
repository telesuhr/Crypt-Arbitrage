#!/usr/bin/env python3
"""
通貨ペアを追加するスクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db
from src.database.models import CurrencyPair
from loguru import logger


def add_currency_pair(symbol: str, base_currency: str, quote_currency: str):
    """通貨ペアを追加"""
    with db.get_session() as session:
        # 既存チェック
        existing = session.query(CurrencyPair).filter_by(symbol=symbol).first()
        
        if existing:
            if not existing.is_active:
                existing.is_active = True
                session.commit()
                print(f"✅ {symbol} を再有効化しました")
            else:
                print(f"ℹ️ {symbol} は既に有効です")
            return
        
        # 新規追加
        new_pair = CurrencyPair(
            symbol=symbol,
            base_currency=base_currency,
            quote_currency=quote_currency,
            is_active=True
        )
        
        session.add(new_pair)
        session.commit()
        
        print(f"✅ {symbol} を追加しました")


def list_available_pairs():
    """追加可能な通貨ペアを表示"""
    print("\n📊 追加可能な通貨ペア:")
    print("=" * 50)
    
    pairs_info = {
        'ETH/JPY': {
            'name': 'イーサリアム',
            'exchanges': 4,
            'volume': '高',
            'recommended': True
        },
        'XRP/JPY': {
            'name': 'リップル',
            'exchanges': 4,
            'volume': '高',
            'recommended': True
        },
        'BCH/JPY': {
            'name': 'ビットコインキャッシュ',
            'exchanges': 3,
            'volume': '中',
            'recommended': False
        },
        'LTC/JPY': {
            'name': 'ライトコイン',
            'exchanges': 3,
            'volume': '中',
            'recommended': False
        },
        'MONA/JPY': {
            'name': 'モナコイン',
            'exchanges': 2,
            'volume': '低',
            'recommended': False
        }
    }
    
    for symbol, info in pairs_info.items():
        status = "⭐ 推奨" if info['recommended'] else ""
        print(f"\n{symbol} ({info['name']}) {status}")
        print(f"  対応取引所数: {info['exchanges']}")
        print(f"  取引量: {info['volume']}")


def show_current_pairs():
    """現在の通貨ペアを表示"""
    with db.get_session() as session:
        pairs = session.query(CurrencyPair).all()
        
        print("\n📋 現在の通貨ペア:")
        print("=" * 50)
        
        for pair in pairs:
            status = "✅ 有効" if pair.is_active else "❌ 無効"
            print(f"{pair.symbol}: {status}")


def main():
    """メイン関数"""
    if len(sys.argv) < 2:
        print("使い方:")
        print("  python add_currency_pair.py list        # 追加可能な通貨ペアを表示")
        print("  python add_currency_pair.py current     # 現在の通貨ペアを表示")
        print("  python add_currency_pair.py add ETH/JPY # ETH/JPYを追加")
        print("  python add_currency_pair.py add-all     # 推奨通貨ペアをすべて追加")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        list_available_pairs()
    
    elif command == "current":
        show_current_pairs()
    
    elif command == "add" and len(sys.argv) >= 3:
        symbol = sys.argv[2].upper()
        
        # 通貨ペアの解析
        if "/" not in symbol:
            print("❌ 通貨ペアは BASE/QUOTE 形式で指定してください（例: ETH/JPY）")
            return
        
        base, quote = symbol.split("/")
        add_currency_pair(symbol, base, quote)
        
        print("\n💡 次のステップ:")
        print("1. データ収集を再起動してください")
        print("2. アービトラージ分析も再起動してください")
    
    elif command == "add-all":
        # 推奨通貨ペアをすべて追加
        recommended_pairs = [
            ("ETH/JPY", "ETH", "JPY"),
            ("XRP/JPY", "XRP", "JPY")
        ]
        
        print("⭐ 推奨通貨ペアを追加します...")
        
        for symbol, base, quote in recommended_pairs:
            add_currency_pair(symbol, base, quote)
        
        print("\n✅ 推奨通貨ペアの追加が完了しました")
        print("\n💡 次のステップ:")
        print("1. データ収集を再起動してください")
        print("2. アービトラージ分析も再起動してください")
    
    else:
        print("❌ 無効なコマンドです")
        print("python add_currency_pair.py list で使い方を確認してください")


if __name__ == "__main__":
    main()