#!/usr/bin/env python3
"""
アービトラージ検出のデバッグスクリプト
同一取引所でアービトラージが検出される問題を調査
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db
from src.database.models import PriceTick, Exchange, CurrencyPair
from src.analyzers.advanced_arbitrage import advanced_analyzer


def check_recent_opportunities():
    """最近検出されたアービトラージ機会を詳細に確認"""
    print("🔍 アービトラージ機会のデバッグ")
    print("=" * 80)
    
    # データベースから最新の価格データを取得
    with db.get_session() as session:
        recent_time = datetime.now(pytz.UTC) - timedelta(minutes=5)
        
        # LTC/USDTのデータを確認（1.77%の機会が検出された）
        ltc_usdt_pair = session.query(CurrencyPair).filter_by(symbol='LTC/USDT').first()
        
        if ltc_usdt_pair:
            print("\n📊 LTC/USDT 価格データ:")
            print("-" * 40)
            
            prices = session.query(
                PriceTick,
                Exchange.code,
                Exchange.name
            ).join(
                Exchange
            ).filter(
                PriceTick.pair_id == ltc_usdt_pair.id,
                PriceTick.timestamp >= recent_time
            ).order_by(
                PriceTick.timestamp.desc()
            ).limit(10).all()
            
            print(f"{'取引所':<15} {'Bid':<12} {'Ask':<12} {'スプレッド':<10} 時刻")
            print("-" * 60)
            
            for tick, code, name in prices:
                spread = (tick.ask - tick.bid) / tick.bid * 100 if tick.bid > 0 else 0
                print(f"{name:<15} {tick.bid:<12.4f} {tick.ask:<12.4f} {spread:<10.4f}% {tick.timestamp.strftime('%H:%M:%S')}")
        
        # LTC/JPYのデータも確認
        ltc_jpy_pair = session.query(CurrencyPair).filter_by(symbol='LTC/JPY').first()
        
        if ltc_jpy_pair:
            print("\n📊 LTC/JPY 価格データ:")
            print("-" * 40)
            
            prices = session.query(
                PriceTick,
                Exchange.code,
                Exchange.name
            ).join(
                Exchange
            ).filter(
                PriceTick.pair_id == ltc_jpy_pair.id,
                PriceTick.timestamp >= recent_time
            ).order_by(
                PriceTick.timestamp.desc()
            ).limit(10).all()
            
            print(f"{'取引所':<15} {'Bid':<12} {'Ask':<12} {'スプレッド':<10} 時刻")
            print("-" * 60)
            
            for tick, code, name in prices:
                spread = (tick.ask - tick.bid) / tick.bid * 100 if tick.bid > 0 else 0
                print(f"{name:<15} {tick.bid:,.0f} {tick.ask:,.0f} {spread:<10.4f}% {tick.timestamp.strftime('%H:%M:%S')}")


async def test_arbitrage_detection():
    """アービトラージ検出ロジックをテスト"""
    print("\n\n🧪 アービトラージ検出ロジックのテスト")
    print("=" * 80)
    
    # 実際の検出を実行
    opportunities = await advanced_analyzer.analyze_all_opportunities()
    
    print(f"\n検出された機会: {len(opportunities)}件")
    
    # 同一取引所の機会をフィルタ
    same_exchange_opps = [
        opp for opp in opportunities 
        if opp['buy_exchange_code'] == opp['sell_exchange_code']
    ]
    
    if same_exchange_opps:
        print(f"\n⚠️  同一取引所でのアービトラージ機会が検出されました: {len(same_exchange_opps)}件")
        for opp in same_exchange_opps[:5]:  # 最初の5件
            print(f"\n問題のある機会:")
            print(f"  タイプ: {opp['type']}")
            print(f"  ペア: {opp['pair']}")
            print(f"  取引所: {opp['buy_exchange']} (買い) → {opp['sell_exchange']} (売り)")
            print(f"  買値: {opp['buy_price']:,.2f}")
            print(f"  売値: {opp['sell_price']:,.2f}")
            print(f"  利益率: {opp['profit_percentage']:.2f}%")
    else:
        print("\n✅ 同一取引所でのアービトラージ機会は検出されませんでした")
    
    # 正常なアービトラージ機会
    normal_opps = [
        opp for opp in opportunities 
        if opp['buy_exchange_code'] != opp['sell_exchange_code']
    ]
    
    if normal_opps:
        print(f"\n✅ 正常なアービトラージ機会: {len(normal_opps)}件")
        for opp in normal_opps[:5]:  # 最初の5件
            print(f"\n機会 {normal_opps.index(opp) + 1}:")
            print(f"  タイプ: {opp['type']}")
            print(f"  ペア: {opp['pair']}")
            print(f"  買い: {opp['buy_exchange']} @ {opp['buy_price']:,.2f}")
            print(f"  売り: {opp['sell_exchange']} @ {opp['sell_price']:,.2f}")
            print(f"  利益率: {opp['profit_percentage']:.2f}%")


async def main():
    """メイン処理"""
    # データベース接続確認
    if not db.test_connection():
        print("❌ データベース接続失敗")
        return
    
    # 最近の価格データを確認
    check_recent_opportunities()
    
    # アービトラージ検出をテスト
    await test_arbitrage_detection()
    
    # クリーンアップ
    db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())