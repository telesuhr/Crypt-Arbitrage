#!/usr/bin/env python3
"""
リアルタイムアービトラージ監視スクリプト
"""

import sys
from pathlib import Path
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
from sqlalchemy import func
import os

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.database.connection import db
from src.database.models import Exchange, CurrencyPair, PriceTick, ArbitrageOpportunity

class ArbitrageMonitor:
    def __init__(self, pair_symbol="BTC/JPY", refresh_interval=5, min_profit_threshold=0.01):
        self.pair_symbol = pair_symbol
        self.refresh_interval = refresh_interval
        self.min_profit_threshold = min_profit_threshold
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # 統計情報
        self.stats = {
            'total_checks': 0,
            'opportunities_found': 0,
            'max_profit': 0,
            'start_time': datetime.now(self.jst)
        }
        
        # 通貨ペアIDを取得（オブジェクトではなくIDのみ保存）
        with db.get_session() as session:
            pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
            if not pair:
                raise ValueError(f"通貨ペア {pair_symbol} が見つかりません")
            self.pair_id = pair.id
    
    def clear_screen(self):
        """画面をクリア"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def get_current_prices(self):
        """現在の価格を取得"""
        with db.get_session() as session:
            exchanges = session.query(Exchange).filter_by(is_active=True).all()
            five_minutes_ago = datetime.now(self.jst) - timedelta(minutes=5)
            
            prices = []
            for exchange in exchanges:
                if exchange.code == 'binance':  # Binanceはスキップ
                    continue
                    
                latest_tick = session.query(PriceTick).filter_by(
                    exchange_id=exchange.id,
                    pair_id=self.pair_id
                ).order_by(PriceTick.timestamp.desc()).first()
                
                if latest_tick and latest_tick.timestamp > five_minutes_ago:
                    spread = float(latest_tick.ask - latest_tick.bid)
                    spread_pct = (spread / float(latest_tick.bid)) * 100
                    
                    prices.append({
                        'exchange': exchange.name,
                        'code': exchange.code,
                        'bid': float(latest_tick.bid),
                        'ask': float(latest_tick.ask),
                        'spread': spread,
                        'spread_pct': spread_pct,
                        'timestamp': latest_tick.timestamp
                    })
            
            return prices
    
    def calculate_arbitrage_opportunities(self, prices):
        """アービトラージ機会を計算"""
        if len(prices) < 2:
            return []
        
        opportunities = []
        
        for i, buy_price in enumerate(prices):
            for j, sell_price in enumerate(prices):
                if i != j:  # 同じ取引所は除外
                    # 買い（ask）と売り（bid）の差を計算
                    profit = sell_price['bid'] - buy_price['ask']
                    profit_pct = (profit / buy_price['ask']) * 100
                    
                    if profit_pct >= self.min_profit_threshold:
                        opportunities.append({
                            'buy_exchange': buy_price['exchange'],
                            'sell_exchange': sell_price['exchange'],
                            'buy_price': buy_price['ask'],
                            'sell_price': sell_price['bid'],
                            'profit': profit,
                            'profit_pct': profit_pct
                        })
        
        return sorted(opportunities, key=lambda x: x['profit_pct'], reverse=True)
    
    def get_recent_opportunities(self, minutes=15):
        """最近のアービトラージ機会を取得"""
        with db.get_session() as session:
            start_time = datetime.now(self.jst) - timedelta(minutes=minutes)
            
            opportunities = session.query(ArbitrageOpportunity).filter(
                ArbitrageOpportunity.pair_id == self.pair_id,
                ArbitrageOpportunity.timestamp > start_time,
                ArbitrageOpportunity.estimated_profit_pct > 0
            ).order_by(ArbitrageOpportunity.timestamp.desc()).limit(10).all()
            
            return opportunities
    
    def display_dashboard(self, prices, opportunities, recent_opportunities):
        """ダッシュボード表示"""
        now = datetime.now(self.jst)
        
        print("=" * 80)
        print(f"🔄 仮想通貨アービトラージ監視 - {self.pair_symbol}")
        print(f"時刻: {now.strftime('%Y-%m-%d %H:%M:%S')} JST")
        print("=" * 80)
        
        # 現在の価格
        print("\n📊 現在の価格:")
        if prices:
            print(f"{'取引所':^12} {'買値(Ask)':^12} {'売値(Bid)':^12} {'スプレッド':^10} {'更新時刻':^10}")
            print("-" * 70)
            
            for price in prices:
                timestamp_str = price['timestamp'].strftime('%H:%M:%S')
                print(f"{price['exchange']:^12} {price['ask']:^12,.0f} {price['bid']:^12,.0f} {price['spread_pct']:^9.2f}% {timestamp_str:^10}")
        else:
            print("価格データがありません")
        
        # アービトラージ機会
        print("\n🚀 リアルタイムアービトラージ機会:")
        if opportunities:
            print(f"{'買い取引所':^12} {'売り取引所':^12} {'買値':^12} {'売値':^12} {'利益':^10} {'利益率':^8}")
            print("-" * 80)
            
            for opp in opportunities:
                print(f"{opp['buy_exchange']:^12} {opp['sell_exchange']:^12} "
                      f"{opp['buy_price']:^12,.0f} {opp['sell_price']:^12,.0f} "
                      f"{opp['profit']:^10,.0f} {opp['profit_pct']:^7.2f}%")
        else:
            print("現在アービトラージ機会はありません")
        
        # 最近の検出機会
        print("\n📈 最近15分間の検出機会:")
        if recent_opportunities:
            print(f"{'時刻':^10} {'買い取引所':^12} {'売り取引所':^12} {'利益率':^8}")
            print("-" * 50)
            
            with db.get_session() as session:
                for opp in recent_opportunities:
                    buy_ex = session.query(Exchange).filter_by(id=opp.buy_exchange_id).first()
                    sell_ex = session.query(Exchange).filter_by(id=opp.sell_exchange_id).first()
                    
                    if buy_ex and sell_ex:
                        time_str = opp.timestamp.strftime('%H:%M:%S')
                        print(f"{time_str:^10} {buy_ex.name:^12} {sell_ex.name:^12} "
                              f"{float(opp.estimated_profit_pct):^7.2f}%")
        else:
            print("最近15分間にアービトラージ機会は検出されませんでした")
        
        # 統計情報
        print("\n📊 統計情報:")
        runtime = datetime.now(self.jst) - self.stats['start_time']
        runtime_str = str(runtime).split('.')[0]  # 秒以下を切り捨て
        
        print(f"実行時間: {runtime_str}")
        print(f"チェック回数: {self.stats['total_checks']}")
        print(f"機会発見数: {self.stats['opportunities_found']}")
        print(f"最大利益率: {self.stats['max_profit']:.3f}%")
        
        # 制御情報
        print("\n" + "=" * 80)
        print(f"更新間隔: {self.refresh_interval}秒 | 最小利益率: {self.min_profit_threshold}% | Ctrl+C で終了")
        print("=" * 80)
    
    def run(self):
        """監視実行"""
        print("アービトラージ監視を開始します...")
        print("Ctrl+C で終了")
        
        try:
            while True:
                self.clear_screen()
                
                # 価格取得
                prices = self.get_current_prices()
                
                # アービトラージ機会計算
                opportunities = self.calculate_arbitrage_opportunities(prices)
                
                # 最近の機会取得
                recent_opportunities = self.get_recent_opportunities()
                
                # 統計更新
                self.stats['total_checks'] += 1
                if opportunities:
                    self.stats['opportunities_found'] += 1
                    max_profit = max(opp['profit_pct'] for opp in opportunities)
                    if max_profit > self.stats['max_profit']:
                        self.stats['max_profit'] = max_profit
                
                # ダッシュボード表示
                self.display_dashboard(prices, opportunities, recent_opportunities)
                
                # アラート
                if opportunities:
                    best_opp = opportunities[0]
                    if best_opp['profit_pct'] >= 0.1:  # 0.1%以上で強調
                        print(f"\n🚨 高利益率機会発見! {best_opp['buy_exchange']} → {best_opp['sell_exchange']}: {best_opp['profit_pct']:.2f}%")
                
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            print("\n\n監視を終了します...")
        except Exception as e:
            print(f"\nエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='仮想通貨アービトラージ監視')
    parser.add_argument('--pair', default='BTC/JPY', help='通貨ペア (default: BTC/JPY)')
    parser.add_argument('--interval', type=int, default=5, help='更新間隔(秒) (default: 5)')
    parser.add_argument('--threshold', type=float, default=0.01, help='最小利益率(%%) (default: 0.01)')
    
    args = parser.parse_args()
    
    monitor = ArbitrageMonitor(
        pair_symbol=args.pair,
        refresh_interval=args.interval,
        min_profit_threshold=args.threshold
    )
    
    monitor.run()

if __name__ == "__main__":
    main()