"""
Bybit取引所のデータ収集クライアント
"""

import os
import time
import hmac
import hashlib
import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime
import pytz
from loguru import logger

from .base import ExchangeClient


class BybitCollector(ExchangeClient):
    """Bybit取引所のデータ収集クライアント"""
    
    def __init__(self, config: Dict):
        super().__init__('bybit', config)
        self.api_key = os.getenv('BYBIT_API_KEY', '')
        self.api_secret = os.getenv('BYBIT_API_SECRET', '')
        self.testnet = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        
        # ベースURL設定
        if self.testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        # エンドポイント
        self.endpoints = {
            'ticker': '/v5/market/tickers',
            'orderbook': '/v5/market/orderbook',
            'kline': '/v5/market/kline',
            'server_time': '/v5/market/time'
        }
        
        # シンボルマッピング（内部形式 → Bybit形式）
        self.symbol_mapping = {
            'BTC_USDT': 'BTCUSDT',
            'ETH_USDT': 'ETHUSDT',
            'XRP_USDT': 'XRPUSDT',
            'LTC_USDT': 'LTCUSDT',
            'BCH_USDT': 'BCHUSDT',
            'ETC_USDT': 'ETCUSDT',
        }
        
        # 通貨ペアタイプ（USDT建て）
        self.pair_type = 'usdt'
        
        # 為替レートサービス（後で初期化）
        self.fx_service = None
    
    def _convert_symbol(self, internal_symbol: str) -> str:
        """内部シンボルをBybit形式に変換"""
        return self.symbol_mapping.get(internal_symbol, internal_symbol)
    
    def _generate_signature(self, timestamp: str, recv_window: str, params: Optional[Dict] = None) -> str:
        """HMAC署名を生成（Bybit API v5）"""
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
    
    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリ"""
        await super().__aenter__()
        
        # 為替レートサービスを初期化
        from ..services.fx_rate_service import fx_service
        self.fx_service = fx_service
        await self.fx_service.start()
        
        logger.info(f"Bybit collector initialized (testnet: {self.testnet})")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーのイグジット"""
        if self.fx_service:
            await self.fx_service.stop()
        await super().__aexit__(exc_type, exc_val, exc_tb)
    
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """ティッカー情報を取得"""
        try:
            bybit_symbol = self._convert_symbol(symbol)
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['ticker']}",
                params={'category': 'spot', 'symbol': bybit_symbol}
            ) as response:
                data = await response.json()
                
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    ticker = data['result']['list'][0]
                    
                    # USDTからJPYに変換
                    usdt_price = Decimal(ticker.get('lastPrice', '0'))
                    bid_usdt = Decimal(ticker.get('bid1Price', '0'))
                    ask_usdt = Decimal(ticker.get('ask1Price', '0'))
                    
                    # 為替レートを適用
                    if self.fx_service:
                        jpy_rate = await self.fx_service.get_rate('USDJPY')
                        last_jpy = usdt_price * jpy_rate
                        bid_jpy = bid_usdt * jpy_rate
                        ask_jpy = ask_usdt * jpy_rate
                    else:
                        # フォールバック
                        jpy_rate = Decimal('155.0')
                        last_jpy = usdt_price * jpy_rate
                        bid_jpy = bid_usdt * jpy_rate
                        ask_jpy = ask_usdt * jpy_rate
                    
                    return {
                        'symbol': symbol,
                        'last': last_jpy,
                        'bid': bid_jpy,
                        'ask': ask_jpy,
                        'volume': Decimal(ticker.get('volume24h', '0')),
                        'timestamp': datetime.now(pytz.UTC),
                        'fx_rate': jpy_rate,  # デバッグ用
                        'original_usdt_price': usdt_price  # デバッグ用
                    }
                    
        except Exception as e:
            logger.error(f"Error fetching Bybit ticker for {symbol}: {e}")
        
        return None
    
    async def fetch_orderbook(self, symbol: str) -> Optional[Dict]:
        """オーダーブック情報を取得"""
        try:
            bybit_symbol = self._convert_symbol(symbol)
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['orderbook']}",
                params={'category': 'spot', 'symbol': bybit_symbol, 'limit': 50}
            ) as response:
                data = await response.json()
                
                if data.get('retCode') == 0 and data.get('result'):
                    result = data['result']
                    
                    # 為替レートを取得
                    if self.fx_service:
                        jpy_rate = await self.fx_service.get_rate('USDJPY')
                    else:
                        jpy_rate = Decimal('155.0')
                    
                    # USDTからJPYに変換
                    bids = []
                    for price, size in result.get('b', []):
                        price_jpy = Decimal(price) * jpy_rate
                        bids.append((price_jpy, Decimal(size)))
                    
                    asks = []
                    for price, size in result.get('a', []):
                        price_jpy = Decimal(price) * jpy_rate
                        asks.append((price_jpy, Decimal(size)))
                    
                    return {
                        'symbol': symbol,
                        'bids': bids,
                        'asks': asks,
                        'timestamp': datetime.now(pytz.UTC)
                    }
                    
        except Exception as e:
            logger.error(f"Error fetching Bybit orderbook for {symbol}: {e}")
        
        return None
    
    async def collect_all_data(self) -> List[Dict]:
        """全通貨ペアのデータを収集"""
        results = []
        
        # 対応通貨ペアをチェック
        supported_pairs = []
        for internal_symbol in self.symbol_mapping.keys():
            # 内部形式をJPY形式に変換（例: BTC_USDT → BTC/JPY）
            base = internal_symbol.split('_')[0]
            display_symbol = f"{base}/JPY"
            supported_pairs.append((internal_symbol, display_symbol))
        
        # 並列でデータ取得
        tasks = []
        for internal_symbol, display_symbol in supported_pairs:
            tasks.append(self._collect_pair_data(internal_symbol, display_symbol))
        
        collected_data = await asyncio.gather(*tasks, return_exceptions=True)
        
        for data in collected_data:
            if isinstance(data, dict) and data:
                results.append(data)
        
        return results
    
    async def _collect_pair_data(self, internal_symbol: str, display_symbol: str) -> Optional[Dict]:
        """個別通貨ペアのデータを収集"""
        try:
            # ティッカー情報を取得
            ticker = await self.fetch_ticker(internal_symbol)
            if not ticker:
                return None
            
            # オーダーブック情報を取得
            orderbook = await self.fetch_orderbook(internal_symbol)
            
            # データを整形
            return {
                'exchange': 'bybit',
                'symbol': display_symbol,  # BTC/JPY形式で表示
                'internal_symbol': internal_symbol,  # BTC_USDT（内部形式）
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'last': ticker['last'],
                'volume': ticker['volume'],
                'bid_volume': orderbook['bids'][0][1] if orderbook and orderbook['bids'] else Decimal('0'),
                'ask_volume': orderbook['asks'][0][1] if orderbook and orderbook['asks'] else Decimal('0'),
                'timestamp': ticker['timestamp'],
                'fx_rate': ticker.get('fx_rate', Decimal('155.0')),
                'is_converted': True  # USDT→JPY変換済みフラグ
            }
            
        except Exception as e:
            logger.error(f"Error collecting data for {internal_symbol}: {e}")
            return None
    
    def get_supported_pairs(self) -> List[str]:
        """対応通貨ペアのリストを返す（表示用）"""
        # BTC/JPY形式で返す（実際はUSDT建てだが、JPY変換済み）
        pairs = []
        for internal_symbol in self.symbol_mapping.keys():
            base = internal_symbol.split('_')[0]
            pairs.append(f"{base}/JPY")
        return pairs
    
    # 基底クラスの抽象メソッドを実装
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得（ExchangeClient互換）"""
        # 内部形式に変換（BTC/JPY → BTC_USDT）
        if '/' in symbol and symbol.endswith('JPY'):
            base = symbol.split('/')[0]
            internal_symbol = f"{base}_USDT"
        else:
            internal_symbol = symbol
        
        result = await self.fetch_ticker(internal_symbol)
        return result if result else {}
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得（ExchangeClient互換）"""
        # 内部形式に変換
        if '/' in symbol and symbol.endswith('JPY'):
            base = symbol.split('/')[0]
            internal_symbol = f"{base}_USDT"
        else:
            internal_symbol = symbol
        
        result = await self.fetch_orderbook(internal_symbol)
        return result if result else {}
    
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        return {}
    
    async def place_order(self, symbol: str, side: str, size: Decimal, 
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict[str, Any]:
        """注文を発注（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        return {}
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """注文をキャンセル（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        return {}
    
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """注文一覧を取得（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        return []