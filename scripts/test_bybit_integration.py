#!/usr/bin/env python3
"""
Bybit統合テスト
データ収集から価格表示まで全体の動作確認
"""

import sys
import asyncio
from pathlib import Path
from decimal import Decimal
import pytz
from datetime import datetime

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.collectors.bybit import BybitCollector
from src.services.fx_rate_service import fx_service
import yaml


async def test_bybit_collector():
    """Bybitコレクターのテスト"""
    print("🚀 Bybit統合テスト")
    print("=" * 60)
    
    # 設定読み込み
    with open('config/exchanges.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    bybit_config = config['exchanges']['bybit']
    
    # コレクター初期化
    collector = BybitCollector(bybit_config)
    await collector.__aenter__()
    
    print("\n1. 為替レート取得テスト")
    print("-" * 40)
    current_rate = await fx_service.get_rate('USDJPY')
    print(f"✅ USD/JPY レート: ¥{current_rate:.2f}")
    
    print("\n2. 個別通貨ペアテスト")
    print("-" * 40)
    
    # BTC/USDTのテスト
    ticker = await collector.fetch_ticker('BTC_USDT')
    if ticker:
        print(f"✅ BTC/JPY (Bybit)")
        print(f"   USDT価格: ${ticker.get('original_usdt_price', 0):,.2f}")
        print(f"   JPY価格: ¥{ticker['last']:,.0f}")
        print(f"   買値: ¥{ticker['bid']:,.0f}")
        print(f"   売値: ¥{ticker['ask']:,.0f}")
        print(f"   使用レート: ¥{ticker.get('fx_rate', 0):.2f}/USD")
    else:
        print("❌ BTC/USDTデータ取得失敗")
    
    print("\n3. 全通貨ペアデータ収集テスト")
    print("-" * 40)
    
    all_data = await collector.collect_all_data()
    print(f"✅ 収集データ数: {len(all_data)}件")
    
    for data in all_data:
        symbol = data['symbol']
        price = data['last']
        print(f"   {symbol}: ¥{price:,.0f}")
    
    print("\n4. 国内取引所との価格比較")
    print("-" * 40)
    
    # 比較のため国内取引所のデータも取得
    from src.collectors.bitflyer import BitFlyerClient
    
    bitflyer_config = config['exchanges']['bitflyer']
    if bitflyer_config.get('enabled'):
        bitflyer = BitFlyerClient(bitflyer_config)
        await bitflyer.__aenter__()
        
        # BTC/JPYで比較
        bf_ticker = await bitflyer.get_ticker('BTC/JPY')
        bybit_btc = next((d for d in all_data if d['symbol'] == 'BTC/JPY'), None)
        
        if bf_ticker and bybit_btc:
            bf_price = Decimal(str(bf_ticker.get('last_price', bf_ticker.get('last', 0))))
            bybit_price = bybit_btc['last']
            diff = bybit_price - bf_price
            diff_pct = (diff / bf_price) * 100 if bf_price > 0 else 0
            
            print(f"BTC/JPY 価格比較:")
            print(f"   bitFlyer: ¥{bf_price:,.0f}")
            print(f"   Bybit:    ¥{bybit_price:,.0f}")
            print(f"   差額:     ¥{diff:,.0f} ({diff_pct:+.2f}%)")
            
            if abs(diff_pct) > 0.1:
                print(f"   → {'Bybit' if diff > 0 else 'bitFlyer'}が高い")
        
        await bitflyer.__aexit__(None, None, None)
    
    print("\n5. アービトラージ機会の可能性")
    print("-" * 40)
    
    # 簡易的なアービトラージチェック
    if all_data:
        btc_data = next((d for d in all_data if 'BTC' in d['symbol']), None)
        if btc_data:
            # 手数料を考慮（仮定）
            bybit_fee = Decimal('0.001')  # 0.1%
            domestic_fee = Decimal('0.0015')  # 0.15%
            total_fee = bybit_fee + domestic_fee
            
            print(f"手数料合計: {total_fee * 100:.2f}%")
            print(f"必要な価格差: {total_fee * 100:.2f}%以上")
            
            # 実際の計算はアービトラージ検出器で行われる
            print("\n💡 Bybitは海外取引所のため、価格差が大きくなりやすい可能性があります")
    
    # クリーンアップ
    await collector.__aexit__(None, None, None)
    
    print("\n✅ Bybit統合テスト完了！")


async def main():
    """メイン処理"""
    try:
        await test_bybit_collector()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())