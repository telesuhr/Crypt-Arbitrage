#!/usr/bin/env python3
"""
全通貨ペアのリアルタイムアービトラージ監視
"""

import sys
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime
import pytz

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from decimal import Decimal
from src.database.connection import db
from src.database.models import CurrencyPair
from src.analyzers.arbitrage_detector import ArbitrageDetector


class MultiPairMonitor:
    """複数通貨ペアのアービトラージ監視"""
    
    def __init__(self, refresh_interval=5, min_profit_threshold=0.05):
        self.refresh_interval = refresh_interval
        self.min_profit_threshold = Decimal(str(min_profit_threshold))
        self.jst = pytz.timezone('Asia/Tokyo')
        self.detector = ArbitrageDetector()
        self.last_opportunities = {}
        
    def clear_screen(self):
        """画面クリア"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def format_profit_indicator(self, profit_pct):
        """利益率に応じたインジケーター"""
        if profit_pct >= Decimal("0.5"):
            return "🔥🔥🔥"
        elif profit_pct >= Decimal("0.3"):
            return "🔥🔥"
        elif profit_pct >= Decimal("0.1"):
            return "🔥"
        elif profit_pct >= self.min_profit_threshold:
            return "💰"
        else:
            return "📊"
    
    async def monitor_once(self):
        """1回の監視実行"""
        opportunities_by_pair = {}
        
        with db.get_session() as session:
            pairs = session.query(CurrencyPair).filter_by(is_active=True).all()
            
            for pair in pairs:
                try:
                    # 最新価格を取得
                    prices = await self.detector.get_latest_prices(pair.symbol)
                    
                    if len(prices) >= 2:
                        # アービトラージ機会を検出
                        opportunities = self.detector.detect_opportunities(prices, pair.symbol)
                        if opportunities:
                            # 閾値以上の機会のみ保持
                            filtered = [
                                opp for opp in opportunities 
                                if opp['estimated_profit_pct'] >= self.min_profit_threshold
                            ]
                            if filtered:
                                opportunities_by_pair[pair.symbol] = filtered[0]  # 最高利益のみ
                
                except Exception as e:
                    # エラーは無視して継続
                    pass
        
        return opportunities_by_pair
    
    def display_status(self, opportunities):
        """監視状況を表示"""
        self.clear_screen()
        
        # ヘッダー
        print("🔍 全通貨ペア リアルタイムアービトラージ監視")
        print("=" * 80)
        print(f"時刻: {datetime.now(self.jst).strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"最小利益閾値: {self.min_profit_threshold}%")
        print(f"更新間隔: {self.refresh_interval}秒")
        print("=" * 80)
        
        if opportunities:
            # 利益率順にソート
            sorted_opps = sorted(opportunities.items(), 
                               key=lambda x: x[1]['estimated_profit_pct'], 
                               reverse=True)
            
            print(f"\n🎯 アービトラージ機会: {len(opportunities)}件")
            print("-" * 80)
            
            # ヘッダー行
            print(f"{'通貨ペア':^10} {'利益率':^8} {'買い取引所':^12} {'売り取引所':^12} {'価格差':^12} {'状態':^6}")
            print("-" * 80)
            
            for pair_symbol, opp in sorted_opps:
                profit_pct = opp['estimated_profit_pct']
                price_diff = opp['sell_price'] - opp['buy_price']
                indicator = self.format_profit_indicator(profit_pct)
                
                # 新規機会かチェック
                is_new = pair_symbol not in self.last_opportunities
                status = "🆕" if is_new else ""
                
                print(f"{pair_symbol:^10} {profit_pct:>6.3f}% "
                      f"{opp['buy_exchange']:^12} {opp['sell_exchange']:^12} "
                      f"¥{price_diff:>10,.0f} {indicator} {status}")
            
            # 最高利益の詳細
            best_pair, best_opp = sorted_opps[0]
            print("\n📈 最高利益機会の詳細:")
            print(f"   通貨ペア: {best_pair}")
            print(f"   利益率: {best_opp['estimated_profit_pct']:.3f}%")
            print(f"   買い: {best_opp['buy_exchange']} @ ¥{best_opp['buy_price']:,.0f}")
            print(f"   売り: {best_opp['sell_exchange']} @ ¥{best_opp['sell_price']:,.0f}")
            print(f"   最大取引量: {best_opp['max_volume']:.4f}")
            
            # 高利益カウント
            high_profit = sum(1 for _, opp in opportunities.items() 
                            if opp['estimated_profit_pct'] >= Decimal("0.1"))
            if high_profit > 0:
                print(f"\n🔥 高利益機会（0.1%以上）: {high_profit}件")
        else:
            print("\n❌ 現在、利益閾値を超えるアービトラージ機会はありません")
        
        # 監視中の通貨ペア
        with db.get_session() as session:
            active_pairs = session.query(CurrencyPair).filter_by(is_active=True).count()
            print(f"\n📊 監視中: {active_pairs}通貨ペア")
        
        print("\n[Ctrl+C で終了]")
        
        # 現在の機会を保存
        self.last_opportunities = opportunities
    
    async def run(self):
        """継続的な監視を実行"""
        print("🚀 全通貨ペア監視を開始します...")
        print("Discord通知が有効です。機会が見つかり次第、iPhoneに通知されます。")
        time.sleep(2)
        
        try:
            while True:
                start_time = time.time()
                
                # 監視実行
                opportunities = await self.monitor_once()
                
                # 表示更新
                self.display_status(opportunities)
                
                # 次の更新まで待機
                elapsed = time.time() - start_time
                wait_time = max(0, self.refresh_interval - elapsed)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
        except KeyboardInterrupt:
            print("\n\n⛔ 監視を終了しました")


async def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='全通貨ペアのアービトラージ監視')
    parser.add_argument('--interval', type=int, default=5, 
                       help='更新間隔（秒）')
    parser.add_argument('--threshold', type=float, default=0.05,
                       help='最小利益閾値（%）')
    
    args = parser.parse_args()
    
    monitor = MultiPairMonitor(
        refresh_interval=args.interval,
        min_profit_threshold=args.threshold
    )
    
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())