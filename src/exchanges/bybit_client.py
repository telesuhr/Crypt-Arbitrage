"""
Bybit取引所クライアント
"""

import os
import time
import hmac
import hashlib
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime
import pytz
from loguru import logger

from ..config import ExchangeConfig
from .base import BaseExchangeClient


class BybitClient(BaseExchangeClient):
    """Bybit取引所のAPIクライアント"""
    
    def __init__(self, config: ExchangeConfig):
        super().__init__(config)
        self.api_key = os.getenv('BYBIT_API_KEY', '')
        self.api_secret = os.getenv('BYBIT_API_SECRET', '')
        self.testnet = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        
        # テストネット対応
        if self.testnet:
            self.base_url = self.base_url.replace('api.bybit.com', 'api-testnet.bybit.com')
            
        # デフォルトヘッダー
        self.default_headers = {
            'Content-Type': 'application/json'
        }
        
        # シンボルマッピング（標準形式 → Bybit形式）
        self.symbol_mapping = {
            'BTC/USDT': 'BTCUSDT',
            'ETH/USDT': 'ETHUSDT',
            'XRP/USDT': 'XRPUSDT',
            'LTC/USDT': 'LTCUSDT',
            'BCH/USDT': 'BCHUSDT',
            'ETC/USDT': 'ETCUSDT',
        }
        
        # 逆マッピング
        self.reverse_symbol_mapping = {v: k for k, v in self.symbol_mapping.items()}
    
    def _convert_symbol(self, symbol: str) -> str:
        """シンボルをBybit形式に変換"""
        return self.symbol_mapping.get(symbol, symbol)
    
    def _convert_symbol_reverse(self, symbol: str) -> str:
        """Bybit形式から標準形式に変換"""
        return self.reverse_symbol_mapping.get(symbol, symbol)
    
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
    
    def _get_auth_headers(self, params: Optional[Dict] = None) -> Dict[str, str]:
        """認証ヘッダーを生成"""
        timestamp = str(int(time.time() * 1000))
        recv_window = '5000'
        
        headers = self.default_headers.copy()
        headers.update({
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-RECV-WINDOW': recv_window,
            'X-BAPI-SIGN': self._generate_signature(timestamp, recv_window, params)
        })
        
        return headers
    
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
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
                    
                    # 標準形式に変換
                    return {
                        'symbol': symbol,
                        'bid': Decimal(ticker.get('bid1Price', '0')),
                        'ask': Decimal(ticker.get('ask1Price', '0')),
                        'last': Decimal(ticker.get('lastPrice', '0')),
                        'volume': Decimal(ticker.get('volume24h', '0')),
                        'timestamp': datetime.now(pytz.UTC)
                    }
                else:
                    logger.error(f"Bybit ticker error: {data}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Bybit ticker for {symbol}: {e}")
            return None
    
    async def get_orderbook(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        """オーダーブック情報を取得"""
        try:
            bybit_symbol = self._convert_symbol(symbol)
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['orderbook']}",
                params={'category': 'spot', 'symbol': bybit_symbol, 'limit': limit}
            ) as response:
                data = await response.json()
                
                if data.get('retCode') == 0 and data.get('result'):
                    result = data['result']
                    
                    # 標準形式に変換
                    return {
                        'symbol': symbol,
                        'bids': [(Decimal(price), Decimal(size)) for price, size in result.get('b', [])],
                        'asks': [(Decimal(price), Decimal(size)) for price, size in result.get('a', [])],
                        'timestamp': datetime.now(pytz.UTC)
                    }
                else:
                    logger.error(f"Bybit orderbook error: {data}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Bybit orderbook for {symbol}: {e}")
            return None
    
    async def get_balance(self) -> Optional[Dict[str, Decimal]]:
        """残高情報を取得"""
        try:
            params = {'accountType': 'UNIFIED'}
            headers = self._get_auth_headers(params)
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['balance']}",
                params=params,
                headers=headers
            ) as response:
                data = await response.json()
                
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    balances = {}
                    wallet = data['result']['list'][0]
                    
                    if 'coin' in wallet:
                        for coin_data in wallet['coin']:
                            coin = coin_data['coin']
                            available = Decimal(coin_data.get('walletBalance', '0'))
                            if available > 0:
                                balances[coin] = available
                    
                    return balances
                else:
                    logger.error(f"Bybit balance error: {data}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Bybit balance: {e}")
            return None
    
    async def get_all_tickers(self) -> List[Dict]:
        """全ての対応ペアのティッカー情報を取得"""
        tickers = []
        
        # 並列で取得
        tasks = []
        for symbol in self.symbol_mapping.keys():
            tasks.append(self.get_ticker(symbol))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict) and result:
                tickers.append(result)
        
        return tickers
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         amount: Decimal, price: Optional[Decimal] = None) -> Optional[str]:
        """注文を発行（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        logger.warning("Bybit order placement not implemented for monitoring-only mode")
        return None
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """注文をキャンセル（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        logger.warning("Bybit order cancellation not implemented for monitoring-only mode")
        return False
    
    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        """注文状態を取得（実装予定）"""
        # アービトラージ監視のみの場合は実装不要
        logger.warning("Bybit order status not implemented for monitoring-only mode")
        return None