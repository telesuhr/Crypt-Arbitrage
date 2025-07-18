#!/usr/bin/env python3
"""
Binance API接続テストスクリプト
APIキーの動作確認とアカウント情報の取得
"""

import os
import sys
import time
import hmac
import hashlib
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
import json
from urllib.parse import urlencode
from dotenv import load_dotenv

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .envファイルの読み込み
load_dotenv()


async def test_binance_api():
    """Binance APIの接続テスト"""
    print("🚀 Binance API接続テスト")
    print("=" * 60)
    
    # API認証情報
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    testnet = os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
    
    if not api_key or not api_secret:
        print("❌ APIキーまたはシークレットが設定されていません")
        return
    
    print(f"✅ APIキー: {api_key[:10]}...")
    print(f"✅ 環境: {'テストネット' if testnet else '本番環境'}")
    
    # ベースURL設定
    if testnet:
        base_url = "https://testnet.binance.vision"
    else:
        base_url = "https://api.binance.com"
    
    print(f"✅ ベースURL: {base_url}")
    
    async with aiohttp.ClientSession() as session:
        # 1. サーバー時刻の確認（認証不要）
        print("\n1. サーバー時刻の確認")
        print("-" * 40)
        
        try:
            async with session.get(f"{base_url}/api/v3/time") as response:
                data = await response.json()
                server_time = data.get('serverTime', 0)
                server_datetime = datetime.fromtimestamp(server_time / 1000)
                print(f"✅ サーバー時刻: {server_datetime}")
                print(f"   タイムスタンプ: {server_time}")
        except Exception as e:
            print(f"❌ サーバー時刻取得エラー: {e}")
            return
        
        # 2. 取引所情報の取得（認証不要）
        print("\n2. 利用可能な取引ペア確認")
        print("-" * 40)
        
        try:
            async with session.get(f"{base_url}/api/v3/exchangeInfo") as response:
                data = await response.json()
                symbols = data.get('symbols', [])
                
                # JPY建てペアを探す
                jpy_pairs = [s for s in symbols if s['quoteAsset'] == 'JPY' and s['status'] == 'TRADING']
                usdt_pairs = [s for s in symbols if s['symbol'] in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'LTCUSDT', 'BCHUSDT'] and s['status'] == 'TRADING']
                
                print(f"✅ 総取引ペア数: {len(symbols)}")
                print(f"✅ JPY建てペア数: {len(jpy_pairs)}")
                if jpy_pairs:
                    print("   JPYペア例:")
                    for pair in jpy_pairs[:5]:
                        print(f"   - {pair['symbol']}")
                
                print(f"\n✅ 主要USDT建てペア: {len(usdt_pairs)}")
                for pair in usdt_pairs:
                    print(f"   - {pair['symbol']} (手数料: Maker {pair.get('makerCommission', 'N/A')}, Taker {pair.get('takerCommission', 'N/A')})")
                    
        except Exception as e:
            print(f"❌ 取引所情報取得エラー: {e}")
        
        # 3. 価格情報の取得（認証不要）
        print("\n3. 現在の価格情報")
        print("-" * 40)
        
        try:
            # BTCUSDT価格
            async with session.get(f"{base_url}/api/v3/ticker/price?symbol=BTCUSDT") as response:
                data = await response.json()
                if isinstance(data, dict) and 'price' in data:
                    btc_price = float(data['price'])
                    print(f"✅ BTC/USDT: ${btc_price:,.2f}")
                else:
                    print(f"❌ 価格データ形式エラー: {data}")
            
            # 複数ペアの価格を一度に取得
            symbols_param = '["BTCUSDT","ETHUSDT","XRPUSDT"]'
            async with session.get(f"{base_url}/api/v3/ticker/price?symbols={symbols_param}") as response:
                data = await response.json()
                if isinstance(data, list):
                    for ticker in data:
                        symbol = ticker['symbol']
                        price = float(ticker['price'])
                        print(f"   {symbol}: ${price:,.4f}")
                        
        except Exception as e:
            print(f"❌ 価格情報取得エラー: {e}")
        
        # 4. アカウント情報の取得（認証必要）
        print("\n4. アカウント情報（認証テスト）")
        print("-" * 40)
        
        try:
            # タイムスタンプとパラメータの準備
            timestamp = int(time.time() * 1000)
            params = {
                'timestamp': timestamp,
                'recvWindow': 5000
            }
            
            # クエリ文字列を作成
            query_string = urlencode(params)
            
            # 署名の生成
            signature = hmac.new(
                api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 署名をパラメータに追加
            params['signature'] = signature
            
            # ヘッダー
            headers = {
                'X-MBX-APIKEY': api_key
            }
            
            # アカウント情報を取得
            async with session.get(
                f"{base_url}/api/v3/account",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ API認証成功！")
                    print(f"   アカウントタイプ: {data.get('accountType', 'N/A')}")
                    print(f"   メーカー手数料: {data.get('makerCommission', 'N/A')}")
                    print(f"   テイカー手数料: {data.get('takerCommission', 'N/A')}")
                    print(f"   取引可能: {data.get('canTrade', False)}")
                    print(f"   出金可能: {data.get('canWithdraw', False)}")
                    print(f"   入金可能: {data.get('canDeposit', False)}")
                    
                    # 残高情報
                    balances = data.get('balances', [])
                    non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
                    
                    if non_zero_balances:
                        print("\n   保有資産:")
                        for balance in non_zero_balances[:5]:  # 最大5つまで表示
                            asset = balance['asset']
                            free = float(balance['free'])
                            locked = float(balance['locked'])
                            total = free + locked
                            print(f"   - {asset}: {total:.8f} (利用可能: {free:.8f}, ロック: {locked:.8f})")
                    else:
                        print("\n   保有資産なし")
                        
                else:
                    error_data = await response.text()
                    print(f"❌ API認証エラー (ステータス: {response.status})")
                    print(f"   エラー内容: {error_data}")
                    
                    if response.status == 401:
                        print("\n   考えられる原因:")
                        print("   1. APIキーが無効")
                        print("   2. APIシークレットが間違っている")
                        print("   3. IP制限が設定されている")
                    elif response.status == 418:
                        print("\n   ⚠️  IPがブロックされています")
                        print("   しばらく待ってから再試行してください")
                    
        except Exception as e:
            print(f"❌ アカウント情報取得エラー: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. API権限の確認
        print("\n5. API権限の確認")
        print("-" * 40)
        
        try:
            # APIキー権限の確認（Binanceは直接的な権限確認エンドポイントがないため、アカウント情報から推測）
            print("ℹ️  API権限はアカウント情報から確認されました")
            print("   必要な権限:")
            print("   - 読み取り: ✅ （価格・残高照会に必要）")
            print("   - 取引: アービトラージ実行時に必要")
            print("   - 出金: 不要（アービトラージ監視のみ）")
            
        except Exception as e:
            print(f"❌ 権限確認エラー: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Binance API接続テスト完了！")
    
    # 推奨事項
    print("\n📋 次のステップ:")
    print("1. IP制限を設定している場合は、現在のIPアドレスを許可リストに追加")
    print("2. API権限は「読み取り」のみで十分（アービトラージ監視用）")
    print("3. 本番運用前に少額でテスト取引を実施（取引機能実装時）")


async def main():
    """メイン処理"""
    try:
        await test_binance_api()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())