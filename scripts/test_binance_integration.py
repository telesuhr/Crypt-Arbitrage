#!/usr/bin/env python3
"""
Binance統合テスト
JPY建て、USDT建て、クロスレート全てのデータ収集テスト
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

from src.collectors.binance import BinanceCollector
from src.collectors.bybit import BybitCollector
from src.services.fx_rate_service import fx_service
import yaml


async def test_binance_collector():
    """Binanceコレクターのテスト"""
    print("🚀 Binance統合テスト（JPY建て・USDT建て・クロスレート分析）")
    print("=" * 80)
    
    # 設定読み込み
    with open('config/exchanges.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    binance_config = config['exchanges']['binance']
    
    # コレクター初期化
    collector = BinanceCollector(binance_config)
    await collector.__aenter__()
    
    print("\n1. 為替レート確認")
    print("-" * 40)
    current_rate = await fx_service.get_rate('USDJPY')
    print(f"✅ USD/JPY レート: ¥{current_rate:.2f}")
    
    print("\n2. JPY建てペアテスト（直接取引）")
    print("-" * 40)
    
    # BTC/JPYのテスト（ネイティブJPY）
    ticker = await collector.fetch_ticker('BTC/JPY')
    if ticker and ticker.get('is_native_jpy'):
        print(f"✅ BTC/JPY (Binance Native)")
        print(f"   価格: ¥{ticker['last']:,.0f}")
        print(f"   買値: ¥{ticker['bid']:,.0f}")
        print(f"   売値: ¥{ticker['ask']:,.0f}")
        print(f"   ネイティブJPY: {ticker['is_native_jpy']}")
    else:
        print("❌ BTC/JPYデータ取得失敗または非対応")
    
    print("\n3. USDT建てペアテスト（JPY変換）")
    print("-" * 40)
    
    # BTC/USDTのテスト
    ticker_usdt = await collector.fetch_ticker('BTC/USDT')
    if ticker_usdt:
        print(f"✅ BTC/USDT → JPY変換")
        print(f"   USDT価格: ${ticker_usdt.get('original_last', 0):,.2f}")
        print(f"   JPY変換価格: ¥{ticker_usdt['last']:,.0f}")
        print(f"   買値: ${ticker_usdt.get('original_bid', 0):,.2f} → ¥{ticker_usdt['bid']:,.0f}")
        print(f"   売値: ${ticker_usdt.get('original_ask', 0):,.2f} → ¥{ticker_usdt['ask']:,.0f}")
        print(f"   使用レート: ¥{ticker_usdt.get('fx_rate', 0):.2f}/USD")
    else:
        print("❌ BTC/USDTデータ取得失敗")
    
    print("\n4. 全通貨ペアデータ収集テスト")
    print("-" * 40)
    
    all_data = await collector.collect_all_data()
    print(f"✅ 収集データ数: {len(all_data)}件")
    
    # データを分類
    jpy_pairs = [d for d in all_data if d.get('quote_type') == 'JPY']
    usdt_pairs = [d for d in all_data if d.get('quote_type') == 'USDT']
    usd_pairs = [d for d in all_data if d.get('quote_type') == 'USD']
    cross_pairs = [d for d in all_data if d.get('quote_type') == 'CROSS']
    fx_pairs = [d for d in all_data if d.get('quote_type') == 'FX']
    
    print(f"\n   JPY建てペア: {len(jpy_pairs)}件")
    for data in jpy_pairs[:3]:  # 最初の3件のみ表示
        print(f"     - {data['symbol']}: ¥{data['last']:,.0f}")
    
    print(f"\n   USDT→JPY変換ペア: {len(usdt_pairs)}件")
    for data in usdt_pairs[:3]:
        print(f"     - {data['symbol']}: ¥{data['last']:,.0f} (元: ${data.get('original_last', 0):,.2f})")
    
    print(f"\n   USD建て比較データ: {len(usd_pairs)}件")
    for data in usd_pairs[:3]:
        print(f"     - {data['symbol']}: ${data['last']:,.2f}")
    
    if cross_pairs:
        print(f"\n   クロスレート: {len(cross_pairs)}件")
        for data in cross_pairs:
            print(f"     - {data['symbol']}: {data['last']:,.2f}")
    
    if fx_pairs:
        print(f"\n   為替参考レート: {len(fx_pairs)}件")
        for data in fx_pairs:
            print(f"     - {data['symbol']}: {data['last']:,.2f}")
    
    print("\n5. アービトラージ機会の分析")
    print("-" * 40)
    
    # Bybitとの比較
    bybit_config = config['exchanges']['bybit']
    if bybit_config.get('enabled'):
        bybit = BybitCollector(bybit_config)
        await bybit.__aenter__()
        
        print("\n5-1. 国内取引所 vs 海外取引所（JPY建て）")
        print("-" * 40)
        
        # bitFlyerとの比較
        from src.collectors.bitflyer import BitFlyerClient
        bitflyer_config = config['exchanges']['bitflyer']
        if bitflyer_config.get('enabled'):
            bitflyer = BitFlyerClient(bitflyer_config)
            await bitflyer.__aenter__()
            
            # BTC/JPY比較
            bf_ticker = await bitflyer.get_ticker('BTC/JPY')
            binance_btc_jpy = next((d for d in all_data if d['symbol'] == 'BTC/JPY' and d.get('is_native_jpy')), None)
            
            if bf_ticker and binance_btc_jpy:
                bf_price = Decimal(str(bf_ticker.get('last_price', bf_ticker.get('last', 0))))
                binance_price = binance_btc_jpy['last']
                diff = binance_price - bf_price
                diff_pct = (diff / bf_price) * 100 if bf_price > 0 else 0
                
                print(f"BTC/JPY 価格比較:")
                print(f"   bitFlyer:     ¥{bf_price:,.0f}")
                print(f"   Binance(JPY): ¥{binance_price:,.0f}")
                print(f"   差額:         ¥{diff:,.0f} ({diff_pct:+.2f}%)")
                
                # 手数料考慮
                binance_fee = Decimal('0.001')  # 0.1%
                bitflyer_fee = Decimal('0.0015')  # 0.15%
                total_fee = binance_fee + bitflyer_fee
                
                if abs(diff_pct) > total_fee * 100:
                    print(f"   → ⚠️ アービトラージ機会の可能性！")
            
            await bitflyer.__aexit__(None, None, None)
        
        print("\n5-2. USDT建て価格の比較（Binance vs Bybit）")
        print("-" * 40)
        
        # BTC/USDTで比較
        bybit_ticker = await bybit.fetch_ticker('BTC_USDT')
        binance_btc_usdt = next((d for d in all_data if d['internal_symbol'] == 'BTC/USDT' and d['quote_type'] == 'USD'), None)
        
        if bybit_ticker and binance_btc_usdt:
            bybit_usdt_price = bybit_ticker.get('original_usdt_price', 0)
            binance_usdt_price = binance_btc_usdt['last']
            diff_usdt = binance_usdt_price - bybit_usdt_price
            diff_pct_usdt = (diff_usdt / bybit_usdt_price) * 100 if bybit_usdt_price > 0 else 0
            
            print(f"BTC/USDT 価格比較:")
            print(f"   Bybit:   ${bybit_usdt_price:,.2f}")
            print(f"   Binance: ${binance_usdt_price:,.2f}")
            print(f"   差額:    ${diff_usdt:,.2f} ({diff_pct_usdt:+.2f}%)")
        
        await bybit.__aexit__(None, None, None)
    
    print("\n6. クロスレートアービトラージの可能性")
    print("-" * 40)
    
    # JPY建てとUSDT建ての価格差分析
    btc_jpy_native = next((d for d in all_data if d['symbol'] == 'BTC/JPY' and d.get('is_native_jpy')), None)
    btc_jpy_via_usdt = next((d for d in all_data if d['symbol'] == 'BTC/JPY' and d['quote_type'] == 'USDT'), None)
    
    if btc_jpy_native and btc_jpy_via_usdt:
        native_price = btc_jpy_native['last']
        converted_price = btc_jpy_via_usdt['last']
        cross_diff = native_price - converted_price
        cross_diff_pct = (cross_diff / converted_price) * 100 if converted_price > 0 else 0
        
        print(f"BTC価格のクロスレート分析:")
        print(f"   直接JPY建て:      ¥{native_price:,.0f}")
        print(f"   USDT経由JPY換算: ¥{converted_price:,.0f}")
        print(f"   差額:            ¥{cross_diff:,.0f} ({cross_diff_pct:+.2f}%)")
        
        if abs(cross_diff_pct) > 0.1:
            print(f"   → 💡 クロスレートアービトラージの機会！")
            print(f"      {('JPY→USDT→JPY' if cross_diff > 0 else 'USDT→JPY→USDT')}の順で利益の可能性")
    
    print("\n7. 取引所間の価格乖離サマリー")
    print("-" * 40)
    
    # 各通貨の最高値・最安値を分析
    currencies = ['BTC', 'ETH', 'XRP']
    for currency in currencies:
        currency_data = []
        
        # 全取引所から該当通貨のデータを収集
        for data in all_data:
            if currency in data['symbol'] and '/JPY' in data['symbol'] and 'USD' not in data['quote_type']:
                currency_data.append({
                    'exchange': data['exchange'],
                    'price': data['last'],
                    'symbol': data['symbol']
                })
        
        if len(currency_data) >= 2:
            prices = sorted(currency_data, key=lambda x: x['price'])
            lowest = prices[0]
            highest = prices[-1]
            
            spread = highest['price'] - lowest['price']
            spread_pct = (spread / lowest['price']) * 100 if lowest['price'] > 0 else 0
            
            print(f"\n{currency}/JPY スプレッド分析:")
            print(f"   最安値: {lowest['exchange']:10} ¥{lowest['price']:,.0f}")
            print(f"   最高値: {highest['exchange']:10} ¥{highest['price']:,.0f}")
            print(f"   価格差: ¥{spread:,.0f} ({spread_pct:.2f}%)")
            
            # 手数料を考慮した利益可能性
            estimated_fee = Decimal('0.3')  # 往復0.3%
            if spread_pct > float(estimated_fee * 100):
                profit_pct = spread_pct - float(estimated_fee * 100)
                print(f"   → ✅ 推定利益率: {profit_pct:.2f}% (手数料控除後)")
    
    # クリーンアップ
    await collector.__aexit__(None, None, None)
    
    print("\n" + "=" * 80)
    print("✅ Binance統合テスト完了！")
    print("\n💡 アービトラージ戦略の推奨:")
    print("1. JPY建て直接取引の価格差を利用")
    print("2. USDT建てのクロスレート差を利用")
    print("3. 国内vs海外の価格乖離を利用")
    print("4. 複数通貨での三角アービトラージ")


async def main():
    """メイン処理"""
    try:
        await test_binance_collector()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())