#!/usr/bin/env python3
"""
実際のコレクターを使用してbid/askが正しく取得されているか確認
"""

import asyncio
import sys
import os
from pathlib import Path
import yaml

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.collectors.binance import BinanceCollector

async def test_collector_bid_ask():
    """コレクター経由でbid/askを確認"""
    
    # 簡単な設定を作成
    config = {
        'exchanges': {
            'binance': {
                'enabled': True
            }
        }
    }
    
    async with BinanceCollector(config) as collector:
        # いくつかのシンボルをテスト
        test_symbols = ['BTC/JPY', 'BTC/USDT', 'ETH/USDT']
        
        for symbol in test_symbols:
            print(f"\n=== Testing {symbol} ===")
            
            # ティッカー情報を取得
            ticker = await collector.fetch_ticker(symbol)
            
            if ticker:
                bid = ticker['bid']
                ask = ticker['ask']
                last = ticker['last']
                
                print(f"Bid: {bid}")
                print(f"Ask: {ask}")
                print(f"Last: {last}")
                print(f"Spread: {ask - bid}")
                print(f"Spread %: {((ask - bid) / ask * 100):.4f}%")
                
                # 検証
                if ask > bid:
                    print("✓ 正常: Ask > Bid")
                else:
                    print("✗ 異常: Ask <= Bid")
                    
                # 元の値もチェック（USDT建ての場合）
                if 'original_bid' in ticker:
                    print(f"\nOriginal (USDT):")
                    print(f"  Bid: {ticker['original_bid']}")
                    print(f"  Ask: {ticker['original_ask']}")
                    print(f"  FX Rate: {ticker['fx_rate']}")
                    
                    if ticker['original_ask'] > ticker['original_bid']:
                        print("  ✓ 正常: Original Ask > Original Bid")
                    else:
                        print("  ✗ 異常: Original Ask <= Original Bid")
            else:
                print("No ticker data available")
                
        # 全データ収集も試す
        print("\n=== Testing collect_all_data ===")
        all_data = await collector.collect_all_data()
        
        print(f"\n収集されたデータ数: {len(all_data)}")
        
        # 最初の5つのデータを確認
        for i, data in enumerate(all_data[:5]):
            print(f"\n{i+1}. {data['symbol']} ({data['exchange']})")
            print(f"   Bid: {data['bid']}")
            print(f"   Ask: {data['ask']}")
            print(f"   Spread: {data['ask'] - data['bid']}")
            
            if data['ask'] > data['bid']:
                print("   ✓ 正常")
            else:
                print("   ✗ 異常")

if __name__ == "__main__":
    print("コレクター Bid/Ask テスト")
    print("=" * 50)
    
    asyncio.run(test_collector_bid_ask())