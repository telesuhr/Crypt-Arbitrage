#!/usr/bin/env python3
"""
Binanceのbid/askが正しく取得されているかテスト
"""

import asyncio
import aiohttp
from decimal import Decimal
import json

async def test_binance_ticker():
    """Binance APIから直接ティッカー情報を取得してbid/askを確認"""
    
    url = "https://api.binance.com/api/v3/ticker/24hr"
    test_symbols = ["BTCUSDT", "ETHUSDT", "BTCJPY"]
    
    async with aiohttp.ClientSession() as session:
        for symbol in test_symbols:
            try:
                async with session.get(url, params={'symbol': symbol}) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        bid_price = Decimal(data.get('bidPrice', '0'))
                        ask_price = Decimal(data.get('askPrice', '0'))
                        last_price = Decimal(data.get('lastPrice', '0'))
                        
                        print(f"\n=== {symbol} ===")
                        print(f"Bid Price: {bid_price}")
                        print(f"Ask Price: {ask_price}")
                        print(f"Last Price: {last_price}")
                        print(f"Spread: {ask_price - bid_price}")
                        print(f"Spread %: {((ask_price - bid_price) / ask_price * 100):.4f}%")
                        
                        # 検証
                        if ask_price > bid_price:
                            print("✓ 正常: Ask > Bid")
                        else:
                            print("✗ 異常: Ask <= Bid")
                            
                        if bid_price <= last_price <= ask_price:
                            print("✓ 正常: Bid <= Last <= Ask")
                        else:
                            print("! 注意: Last価格がBid-Askの範囲外")
                            
                    else:
                        print(f"Error for {symbol}: HTTP {response.status}")
                        
            except Exception as e:
                print(f"Exception for {symbol}: {e}")

async def test_orderbook():
    """オーダーブックデータも確認"""
    
    url = "https://api.binance.com/api/v3/depth"
    symbol = "BTCUSDT"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params={'symbol': symbol, 'limit': 5}) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"\n=== {symbol} Order Book ===")
                    print("\nBids (買い注文):")
                    for i, (price, qty) in enumerate(data['bids'][:5]):
                        print(f"  {i+1}. Price: {price}, Qty: {qty}")
                        
                    print("\nAsks (売り注文):")
                    for i, (price, qty) in enumerate(data['asks'][:5]):
                        print(f"  {i+1}. Price: {price}, Qty: {qty}")
                        
                    # 最良買値と最良売値を確認
                    best_bid = Decimal(data['bids'][0][0])
                    best_ask = Decimal(data['asks'][0][0])
                    
                    print(f"\nBest Bid: {best_bid}")
                    print(f"Best Ask: {best_ask}")
                    print(f"Spread: {best_ask - best_bid}")
                    
                    if best_ask > best_bid:
                        print("✓ 正常: Best Ask > Best Bid")
                    else:
                        print("✗ 異常: Best Ask <= Best Bid")
                        
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    print("Binance Bid/Ask テスト")
    print("=" * 50)
    
    asyncio.run(test_binance_ticker())
    asyncio.run(test_orderbook())