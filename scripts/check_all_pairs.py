#!/usr/bin/env python3
"""
全通貨ペアのアービトラージ機会をチェック
"""

import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
from src.database.connection import db
from src.database.models import CurrencyPair, Exchange, PriceTick, ArbitrageOpportunity
from src.analyzers.arbitrage_detector import ArbitrageDetector
from sqlalchemy import func, and_


async def check_all_pairs():
    """全通貨ペアのアービトラージ機会をチェック"""
    detector = ArbitrageDetector()
    jst = pytz.timezone('Asia/Tokyo')
    
    with db.get_session() as session:
        # アクティブな通貨ペアを取得
        pairs = session.query(CurrencyPair).filter_by(is_active=True).all()
        
        print("🔍 全通貨ペアのアービトラージ機会チェック")
        print("=" * 80)
        print(f"チェック時刻: {datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        all_opportunities = []
        
        for pair in pairs:
            # 最新価格を取得
            prices = await detector.get_latest_prices(pair.symbol)
            
            if len(prices) < 2:
                continue
            
            # アービトラージ機会を検出
            opportunities = detector.detect_opportunities(prices, pair.symbol)
            
            if opportunities:
                all_opportunities.extend(opportunities)
                
                # 最も利益率の高い機会を表示
                best = opportunities[0]
                profit_color = ""
                if best['estimated_profit_pct'] >= Decimal("0.5"):
                    profit_color = "🔥"  # 高利益
                elif best['estimated_profit_pct'] >= Decimal("0.1"):
                    profit_color = "💰"  # 中利益
                else:
                    profit_color = "📊"  # 低利益
                
                print(f"\n{profit_color} {pair.symbol}")
                print(f"   最高利益率: {best['estimated_profit_pct']:.3f}%")
                print(f"   買い: {best['buy_exchange']} (¥{best['buy_price']:,.0f})")
                print(f"   売り: {best['sell_exchange']} (¥{best['sell_price']:,.0f})")
                print(f"   最大取引量: {best['max_volume']:.4f} {pair.base_currency}")
                print(f"   予想利益: ¥{(best['max_volume'] * best['buy_price'] * best['estimated_profit_pct'] / 100):,.0f}")
        
        # サマリー
        print("\n" + "=" * 80)
        print("📈 サマリー")
        print("=" * 80)
        
        if all_opportunities:
            # 通貨ペア別の最高利益率
            pair_best = {}
            for opp in all_opportunities:
                pair = opp['pair_symbol']
                if pair not in pair_best or opp['estimated_profit_pct'] > pair_best[pair]['estimated_profit_pct']:
                    pair_best[pair] = opp
            
            # 利益率順にソート
            sorted_pairs = sorted(pair_best.items(), key=lambda x: x[1]['estimated_profit_pct'], reverse=True)
            
            print(f"✅ 機会のある通貨ペア: {len(pair_best)}種類")
            print("\n📊 利益率ランキング:")
            
            for i, (pair, opp) in enumerate(sorted_pairs[:10], 1):
                profit_pct = opp['estimated_profit_pct']
                if profit_pct >= Decimal("0.5"):
                    icon = "🥇"
                elif profit_pct >= Decimal("0.1"):
                    icon = "🥈"
                else:
                    icon = "🥉"
                
                print(f"{icon} {i}. {pair:10} {profit_pct:6.3f}% ({opp['buy_exchange']:10} → {opp['sell_exchange']:10})")
            
            # 通知閾値（0.05%）を超える機会
            notification_worthy = [opp for opp in all_opportunities if opp['estimated_profit_pct'] >= Decimal("0.05")]
            print(f"\n🔔 通知対象（0.05%以上）: {len(notification_worthy)}件")
            
            # 高利益機会（0.1%以上）
            high_profit = [opp for opp in all_opportunities if opp['estimated_profit_pct'] >= Decimal("0.1")]
            if high_profit:
                print(f"🔥 高利益機会（0.1%以上）: {len(high_profit)}件")
                for opp in high_profit[:5]:
                    print(f"   - {opp['pair_symbol']}: {opp['estimated_profit_pct']:.3f}%")
        else:
            print("❌ 現在アービトラージ機会はありません")
        
        # 過去1時間の実績
        one_hour_ago = datetime.now(jst) - timedelta(hours=1)
        recent_opps = session.query(ArbitrageOpportunity).filter(
            ArbitrageOpportunity.timestamp > one_hour_ago
        ).all()
        
        if recent_opps:
            print(f"\n📊 過去1時間の検出実績: {len(recent_opps)}件")
            # 通貨ペア別カウント
            pair_counts = {}
            for opp in recent_opps:
                pair_id = opp.pair_id
                pair = session.query(CurrencyPair).get(pair_id)
                if pair:
                    pair_counts[pair.symbol] = pair_counts.get(pair.symbol, 0) + 1
            
            for pair, count in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {pair}: {count}件")


if __name__ == "__main__":
    asyncio.run(check_all_pairs())