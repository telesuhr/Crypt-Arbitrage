#!/usr/bin/env python3
"""
読み取り専用のアービトラージモニター
データ収集は行わず、既存データベースの監視のみ実行
"""

import sys
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from decimal import Decimal
from src.database.connection import db
from src.database.models import CurrencyPair, Exchange, PriceTick
from src.analyzers.arbitrage_detector import ArbitrageDetector
from sqlalchemy import func, and_, desc


class ReadOnlyMonitor:
    """読み取り専用モニター（API呼び出しなし）"""
    
    def __init__(self, refresh_interval=5, min_profit_threshold=0.05):
        self.refresh_interval = refresh_interval
        self.min_profit_threshold = Decimal(str(min_profit_threshold))
        self.jst = pytz.timezone('Asia/Tokyo')
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
    
    def get_latest_prices_from_db(self, pair_symbol, minutes_ago=5):
        """データベースから最新価格を取得"""
        with db.get_session() as session:
            # 通貨ペアを取得
            pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
            if not pair:
                return []
            
            # 過去N分間の最新価格を取得
            cutoff_time = datetime.now(self.jst) - timedelta(minutes=minutes_ago)
            
            # 各取引所の最新価格を取得
            subquery = session.query(
                PriceTick.exchange_id,
                func.max(PriceTick.timestamp).label('max_timestamp')
            ).filter(
                and_(
                    PriceTick.pair_id == pair.id,
                    PriceTick.timestamp > cutoff_time
                )
            ).group_by(PriceTick.exchange_id).subquery()
            
            # 最新価格データを取得
            prices = session.query(
                PriceTick,
                Exchange.code.label('exchange_code'),
                Exchange.name.label('exchange_name')
            ).join(
                subquery,
                and_(
                    PriceTick.exchange_id == subquery.c.exchange_id,
                    PriceTick.timestamp == subquery.c.max_timestamp
                )
            ).join(
                Exchange,
                PriceTick.exchange_id == Exchange.id
            ).filter(
                PriceTick.pair_id == pair.id
            ).all()
            
            # ArbitrageDetectorが期待する形式に変換
            price_data = []
            for tick, exchange_code, exchange_name in prices:
                price_data.append({
                    'exchange': exchange_code,
                    'exchange_name': exchange_name,
                    'bid': tick.bid_price,
                    'ask': tick.ask_price,
                    'bid_volume': tick.bid_volume,
                    'ask_volume': tick.ask_volume,
                    'timestamp': tick.timestamp
                })
            
            return price_data
    
    def monitor_once(self):
        """1回の監視実行（DBからのみデータ取得）"""
        opportunities_by_pair = {}
        detector = ArbitrageDetector()
        
        with db.get_session() as session:
            pairs = session.query(CurrencyPair).filter_by(is_active=True).all()
            
            for pair in pairs:
                try:
                    # DBから最新価格を取得
                    prices = self.get_latest_prices_from_db(pair.symbol)
                    
                    if len(prices) >= 2:
                        # アービトラージ機会を検出
                        opportunities = detector.detect_opportunities(prices, pair.symbol)
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
        print("📖 読み取り専用モニター（DB監視モード）")
        print("=" * 80)
        print(f"時刻: {datetime.now(self.jst).strftime('%Y-%m-%d %H:%M:%S')} JST")
        print(f"最小利益閾値: {self.min_profit_threshold}%")
        print(f"更新間隔: {self.refresh_interval}秒")
        print("モード: データベース読み取りのみ（API呼び出しなし）")
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
        else:
            print("\n❌ 現在、利益閾値を超えるアービトラージ機会はありません")
        
        # データ鮮度の確認
        print("\n📊 データ鮮度チェック:")
        with db.get_session() as session:
            for exchange in session.query(Exchange).filter_by(is_active=True).all():
                # 最新データの時刻を確認
                latest = session.query(func.max(PriceTick.timestamp)).filter_by(
                    exchange_id=exchange.id
                ).scalar()
                
                if latest:
                    age = datetime.now(self.jst) - latest.replace(tzinfo=self.jst)
                    if age.total_seconds() < 60:
                        status = "🟢"  # 1分以内
                    elif age.total_seconds() < 300:
                        status = "🟡"  # 5分以内
                    else:
                        status = "🔴"  # 5分以上古い
                    
                    print(f"  {status} {exchange.name}: {int(age.total_seconds())}秒前")
                else:
                    print(f"  ❌ {exchange.name}: データなし")
        
        print("\n[Ctrl+C で終了]")
        
        # 現在の機会を保存
        self.last_opportunities = opportunities
    
    def run(self):
        """継続的な監視を実行"""
        print("🚀 読み取り専用モニターを開始します...")
        print("データベースから価格情報を読み取ります（API呼び出しなし）")
        time.sleep(2)
        
        try:
            while True:
                start_time = time.time()
                
                # 監視実行
                opportunities = self.monitor_once()
                
                # 表示更新
                self.display_status(opportunities)
                
                # 次の更新まで待機
                elapsed = time.time() - start_time
                wait_time = max(0, self.refresh_interval - elapsed)
                if wait_time > 0:
                    time.sleep(wait_time)
                    
        except KeyboardInterrupt:
            print("\n\n⛔ 監視を終了しました")


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='読み取り専用アービトラージモニター')
    parser.add_argument('--interval', type=int, default=5, 
                       help='更新間隔（秒）')
    parser.add_argument('--threshold', type=float, default=0.05,
                       help='最小利益閾値（%）')
    parser.add_argument('--data-age', type=int, default=5,
                       help='データの有効期限（分）')
    
    args = parser.parse_args()
    
    monitor = ReadOnlyMonitor(
        refresh_interval=args.interval,
        min_profit_threshold=args.threshold
    )
    
    monitor.run()


if __name__ == "__main__":
    main()