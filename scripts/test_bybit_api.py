#!/usr/bin/env python3
"""
Bybit API接続テスト
APIキーが正しく機能するか確認
"""

import os
import sys
from pathlib import Path
import time
import hashlib
import hmac
import requests
import json
from datetime import datetime
import pytz

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class BybitAPITester:
    def __init__(self):
        self.api_key = os.getenv('BYBIT_API_KEY', '').strip()
        self.api_secret = os.getenv('BYBIT_API_SECRET', '').strip()
        self.testnet = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        
        # ベースURL設定
        if self.testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        self.session = requests.Session()
        self.session.headers.update({
            'X-BAPI-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        })
    
    def generate_signature(self, timestamp, recv_window, params):
        """HMAC署名を生成（Bybit API v5）"""
        # Bybit v5の署名方式
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            param_str = f"{timestamp}{self.api_key}{recv_window}{query_string}"
        else:
            param_str = f"{timestamp}{self.api_key}{recv_window}"
        
        signature = hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(param_str, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def test_public_endpoint(self):
        """パブリックAPIのテスト（認証不要）"""
        print("\n1. パブリックAPIテスト（認証不要）")
        print("-" * 50)
        
        try:
            # サーバー時刻を取得
            response = self.session.get(f"{self.base_url}/v5/market/time")
            data = response.json()
            
            if data['retCode'] == 0:
                server_time = int(data['result']['timeSecond'])
                dt = datetime.fromtimestamp(server_time, tz=pytz.UTC)
                jst = dt.astimezone(pytz.timezone('Asia/Tokyo'))
                print(f"✅ サーバー接続成功")
                print(f"   サーバー時刻: {jst.strftime('%Y-%m-%d %H:%M:%S')} JST")
            else:
                print(f"❌ エラー: {data}")
            
            # BTC/USDT価格を取得
            response = self.session.get(
                f"{self.base_url}/v5/market/tickers",
                params={'category': 'spot', 'symbol': 'BTCUSDT'}
            )
            data = response.json()
            
            if data['retCode'] == 0 and data['result']['list']:
                ticker = data['result']['list'][0]
                print(f"\n✅ BTC/USDT価格取得成功")
                print(f"   現在価格: ${float(ticker['lastPrice']):,.2f}")
                print(f"   24時間変動: {float(ticker['price24hPcnt'])*100:.2f}%")
                print(f"   24時間高値: ${float(ticker['highPrice24h']):,.2f}")
                print(f"   24時間安値: ${float(ticker['lowPrice24h']):,.2f}")
                return True
            else:
                print(f"❌ 価格取得エラー: {data}")
                return False
                
        except Exception as e:
            print(f"❌ 接続エラー: {e}")
            return False
    
    def test_private_endpoint(self):
        """プライベートAPIのテスト（認証必要）"""
        print("\n2. プライベートAPIテスト（認証必要）")
        print("-" * 50)
        
        if not self.api_key or not self.api_secret:
            print("❌ APIキーが設定されていません")
            return False
        
        try:
            # タイムスタンプとrecv_window
            timestamp = str(int(time.time() * 1000))
            recv_window = '5000'
            
            # アカウント情報を取得
            endpoint = "/v5/account/wallet-balance"
            params = {
                'accountType': 'UNIFIED'  # Bybitの統合アカウント
            }
            
            # 署名を生成
            signature = self.generate_signature(timestamp, recv_window, params)
            
            # ヘッダーを更新
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-SIGN': signature,
                'X-BAPI-RECV-WINDOW': recv_window
            }
            
            response = self.session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            )
            data = response.json()
            
            if data['retCode'] == 0:
                print(f"✅ 認証成功！APIキーは有効です")
                
                # ウォレット情報を表示
                if 'list' in data['result'] and data['result']['list']:
                    wallet = data['result']['list'][0]
                    print(f"\nアカウントタイプ: {wallet.get('accountType', 'N/A')}")
                    
                    # 主要通貨の残高を表示
                    if 'coin' in wallet:
                        print("\n保有資産:")
                        for coin in wallet['coin'][:5]:  # 最初の5つまで
                            if float(coin.get('walletBalance', 0)) > 0:
                                print(f"   {coin['coin']}: {float(coin['walletBalance']):.8f}")
                
                return True
            else:
                print(f"❌ 認証エラー: {data.get('retMsg', 'Unknown error')}")
                print(f"   エラーコード: {data.get('retCode')}")
                
                # よくあるエラーの説明
                if data['retCode'] == 10003:
                    print("   → APIキーが無効です")
                elif data['retCode'] == 10004:
                    print("   → 署名が無効です（API Secretを確認してください）")
                elif data['retCode'] == 10005:
                    print("   → 権限が不足しています")
                
                return False
                
        except Exception as e:
            print(f"❌ リクエストエラー: {e}")
            return False
    
    def test_spot_symbols(self):
        """取引可能な通貨ペアを確認"""
        print("\n3. 取引可能な通貨ペア確認")
        print("-" * 50)
        
        try:
            response = self.session.get(
                f"{self.base_url}/v5/market/instruments-info",
                params={'category': 'spot'}
            )
            data = response.json()
            
            if data['retCode'] == 0:
                symbols = data['result']['list']
                
                # JPY建ての通貨ペアを探す
                jpy_pairs = [s for s in symbols if s['quoteCoin'] == 'JPY']
                usdt_pairs = [s for s in symbols if s['quoteCoin'] == 'USDT' and s['baseCoin'] in ['BTC', 'ETH', 'XRP', 'LTC']]
                
                print(f"✅ 通貨ペア情報取得成功")
                print(f"   総ペア数: {len(symbols)}")
                
                if jpy_pairs:
                    print(f"\nJPY建てペア: {len(jpy_pairs)}個")
                    for pair in jpy_pairs[:5]:
                        print(f"   - {pair['symbol']}")
                else:
                    print("\n❌ JPY建てペアは見つかりませんでした")
                
                print(f"\n主要USDT建てペア:")
                for pair in usdt_pairs:
                    print(f"   - {pair['symbol']} (最小注文: {pair['lotSizeFilter']['minOrderQty']} {pair['baseCoin']})")
                
                return True
            else:
                print(f"❌ エラー: {data}")
                return False
                
        except Exception as e:
            print(f"❌ エラー: {e}")
            return False

def main():
    print("🚀 Bybit API接続テスト")
    print("=" * 60)
    
    tester = BybitAPITester()
    
    # API設定を表示（シークレットは隠す）
    print(f"API Key: {tester.api_key[:10]}..." if tester.api_key else "API Key: 未設定")
    print(f"API Secret: {'*' * 10}" if tester.api_secret else "API Secret: 未設定")
    print(f"環境: {'テストネット' if tester.testnet else '本番環境'}")
    print(f"Base URL: {tester.base_url}")
    
    # 各テストを実行
    public_ok = tester.test_public_endpoint()
    
    if public_ok:
        private_ok = tester.test_private_endpoint()
        symbols_ok = tester.test_spot_symbols()
        
        print("\n" + "=" * 60)
        print("📊 テスト結果サマリー")
        print("=" * 60)
        print(f"パブリックAPI: {'✅ 成功' if public_ok else '❌ 失敗'}")
        print(f"プライベートAPI: {'✅ 成功' if private_ok else '❌ 失敗'}")
        print(f"通貨ペア取得: {'✅ 成功' if symbols_ok else '❌ 失敗'}")
        
        if private_ok:
            print("\n✅ BybitのAPIキーは正常に動作しています！")
            print("\n次のステップ:")
            print("1. Bybitを取引所リストに追加")
            print("2. データ収集クライアントを実装")
            print("3. アービトラージ監視に統合")
        else:
            print("\n⚠️  APIキーの設定を確認してください")
            print("1. APIキーとシークレットが正しくコピーされているか")
            print("2. APIキーに読み取り権限があるか")
            print("3. IP制限が設定されている場合、現在のIPが許可されているか")

if __name__ == "__main__":
    main()