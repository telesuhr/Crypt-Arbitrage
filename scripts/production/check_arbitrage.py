#!/usr/bin/env python3
"""
価格差とアービトラージ機会を確認するスクリプト
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
from sqlalchemy import func

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.database.connection import db
from src.database.models import Exchange, CurrencyPair, PriceTick, ArbitrageOpportunity

def print_header(title):
    """見出しを表示"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def get_current_prices(pair_symbol="BTC/JPY"):
    """現在の価格を取得"""
    with db.get_session() as session:
        # 通貨ペアを取得
        pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
        if not pair:
            print(f"通貨ペア {pair_symbol} が見つかりません")
            return None
        
        # 各取引所の最新価格を取得
        exchanges = session.query(Exchange).filter_by(is_active=True).all()
        jst = pytz.timezone('Asia/Tokyo')
        five_minutes_ago = datetime.now(jst) - timedelta(minutes=5)
        
        prices = []
        for exchange in exchanges:
            if exchange.code == 'binance':  # Binanceはスキップ
                continue
                
            latest_tick = session.query(PriceTick).filter_by(
                exchange_id=exchange.id,
                pair_id=pair.id
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

def calculate_arbitrage_opportunities(prices):
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
                
                if profit > 0:
                    opportunities.append({
                        'buy_exchange': buy_price['exchange'],
                        'sell_exchange': sell_price['exchange'],
                        'buy_price': buy_price['ask'],
                        'sell_price': sell_price['bid'],
                        'profit': profit,
                        'profit_pct': profit_pct
                    })
    
    return sorted(opportunities, key=lambda x: x['profit_pct'], reverse=True)

def get_historical_arbitrage(pair_symbol="BTC/JPY", hours=1):
    """過去のアービトラージ機会を取得"""
    with db.get_session() as session:
        pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
        if not pair:
            return []
        
        pair_id = pair.id  # IDを保存
        jst = pytz.timezone('Asia/Tokyo')
        start_time = datetime.now(jst) - timedelta(hours=hours)
        
        opportunities = session.query(ArbitrageOpportunity).filter(
            ArbitrageOpportunity.pair_id == pair_id,
            ArbitrageOpportunity.timestamp > start_time,
            ArbitrageOpportunity.estimated_profit_pct > 0
        ).order_by(ArbitrageOpportunity.timestamp.desc()).limit(20).all()
        
        return opportunities

def main():
    print_header("仮想通貨アービトラージ機会チェック")
    
    # 現在の価格を取得
    print("\n📊 現在の価格情報:")
    prices = get_current_prices()
    
    if not prices:
        print("価格データが取得できませんでした")
        return
    
    # 価格表示
    print(f"{'取引所':^12} {'買値(Ask)':^12} {'売値(Bid)':^12} {'スプレッド':^10} {'時刻':^10}")
    print("-" * 70)
    
    for price in prices:
        timestamp_str = price['timestamp'].strftime('%H:%M:%S')
        print(f"{price['exchange']:^12} {price['ask']:^12,.0f} {price['bid']:^12,.0f} {price['spread_pct']:^9.2f}% {timestamp_str:^10}")
    
    # 価格差の分析
    print("\n💰 価格差分析:")
    if len(prices) >= 2:
        max_ask = max(prices, key=lambda x: x['ask'])
        min_ask = min(prices, key=lambda x: x['ask'])
        max_bid = max(prices, key=lambda x: x['bid'])
        min_bid = min(prices, key=lambda x: x['bid'])
        
        ask_spread = max_ask['ask'] - min_ask['ask']
        bid_spread = max_bid['bid'] - min_bid['bid']
        
        print(f"Ask最高: {max_ask['exchange']} ¥{max_ask['ask']:,.0f}")
        print(f"Ask最低: {min_ask['exchange']} ¥{min_ask['ask']:,.0f}")
        print(f"Ask価格差: ¥{ask_spread:,.0f} ({(ask_spread/min_ask['ask']*100):.2f}%)")
        print()
        print(f"Bid最高: {max_bid['exchange']} ¥{max_bid['bid']:,.0f}")
        print(f"Bid最低: {min_bid['exchange']} ¥{min_bid['bid']:,.0f}")
        print(f"Bid価格差: ¥{bid_spread:,.0f} ({(bid_spread/min_bid['bid']*100):.2f}%)")
    
    # アービトラージ機会の計算
    print("\n🔄 理論的アービトラージ機会:")
    opportunities = calculate_arbitrage_opportunities(prices)
    
    if opportunities:
        print(f"{'買い取引所':^12} {'売り取引所':^12} {'買値':^12} {'売値':^12} {'利益':^10} {'利益率':^8}")
        print("-" * 80)
        
        for opp in opportunities[:5]:  # 上位5つのみ表示
            print(f"{opp['buy_exchange']:^12} {opp['sell_exchange']:^12} "
                  f"{opp['buy_price']:^12,.0f} {opp['sell_price']:^12,.0f} "
                  f"{opp['profit']:^10,.0f} {opp['profit_pct']:^7.2f}%")
    else:
        print("現在アービトラージ機会はありません")
    
    # 過去の実績
    print("\n📈 過去1時間のアービトラージ検出実績:")
    historical_opps = get_historical_arbitrage(hours=1)
    
    if historical_opps:
        print(f"検出数: {len(historical_opps)}件")
        
        with db.get_session() as session:
            print(f"{'時刻':^10} {'買い取引所':^12} {'売り取引所':^12} {'利益率':^8} {'状態':^10}")
            print("-" * 70)
            
            for opp in historical_opps[:10]:  # 上位10件
                buy_ex = session.query(Exchange).filter_by(id=opp.buy_exchange_id).first()
                sell_ex = session.query(Exchange).filter_by(id=opp.sell_exchange_id).first()
                
                if buy_ex and sell_ex:
                    time_str = opp.timestamp.strftime('%H:%M:%S')
                    print(f"{time_str:^10} {buy_ex.name:^12} {sell_ex.name:^12} "
                          f"{float(opp.estimated_profit_pct):^7.2f}% {opp.status:^10}")
        
        # 統計情報
        total_profit = sum(float(opp.estimated_profit_pct) for opp in historical_opps)
        avg_profit = total_profit / len(historical_opps)
        max_profit = max(float(opp.estimated_profit_pct) for opp in historical_opps)
        
        print(f"\n統計情報:")
        print(f"平均利益率: {avg_profit:.3f}%")
        print(f"最大利益率: {max_profit:.3f}%")
        print(f"合計検出数: {len(historical_opps)}件")
    else:
        print("過去1時間にアービトラージ機会は検出されませんでした")
    
    # データ取得状況
    print("\n📡 データ取得状況:")
    with db.get_session() as session:
        jst = pytz.timezone('Asia/Tokyo')
        one_hour_ago = datetime.now(jst) - timedelta(hours=1)
        
        exchanges = session.query(Exchange).filter_by(is_active=True).all()
        pair = session.query(CurrencyPair).filter_by(symbol="BTC/JPY").first()
        
        if pair:
            pair_id = pair.id  # IDを保存
            for exchange in exchanges:
                if exchange.code == 'binance':
                    continue
                    
                tick_count = session.query(PriceTick).filter(
                    PriceTick.exchange_id == exchange.id,
                    PriceTick.pair_id == pair_id,
                    PriceTick.timestamp > one_hour_ago
                ).count()
                
                latest_tick = session.query(PriceTick).filter_by(
                    exchange_id=exchange.id,
                    pair_id=pair_id
                ).order_by(PriceTick.timestamp.desc()).first()
                
                if latest_tick:
                    last_update = latest_tick.timestamp.strftime('%H:%M:%S')
                    print(f"{exchange.name:^12}: {tick_count:^5}件 (最終更新: {last_update})")
                else:
                    print(f"{exchange.name:^12}: データなし")

if __name__ == "__main__":
    main()