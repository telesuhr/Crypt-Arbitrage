"""
Binance取引所のデータ収集クライアント
JPY建て、USDT建て、クロスレート変換を全てサポート
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
from urllib.parse import urlencode

from .base import ExchangeClient


class BinanceCollector(ExchangeClient):
    """Binance取引所のデータ収集クライアント"""
    
    def __init__(self, config: Dict):
        super().__init__('binance', config)
        self.api_key = os.getenv('BINANCE_API_KEY', '')
        self.api_secret = os.getenv('BINANCE_API_SECRET', '')
        self.testnet = os.getenv('BINANCE_TESTNET', 'false').lower() == 'true'
        
        # ベースURL設定
        if self.testnet:
            self.base_url = "https://testnet.binance.vision"
        else:
            self.base_url = "https://api.binance.com"
        
        # エンドポイント
        self.endpoints = {
            'ticker': '/api/v3/ticker/24hr',
            'orderbook': '/api/v3/depth',
            'price': '/api/v3/ticker/price',
            'exchange_info': '/api/v3/exchangeInfo',
            'server_time': '/api/v3/time',
            'account': '/api/v3/account'
        }
        
        # 対応通貨ペア（優先順位順）
        self.supported_symbols = {
            # JPY建てペア（直接取引）
            'jpy_pairs': [
                'BTCJPY', 'ETHJPY', 'XRPJPY', 'BNBJPY', 'ADAJPY',
                'DOGEJPY', 'MATICJPY', 'DOTJPY', 'LTCJPY', 'SOLJPY'
            ],
            # USDT建てペア（要変換）
            'usdt_pairs': [
                'BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'LTCUSDT', 'BCHUSDT',
                'ETCUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT', 'MATICUSDT'
            ],
            # クロスレート用
            'cross_pairs': [
                'USDTJPY',  # USDT/JPY直接レート（もし存在すれば）
            ]
        }
        
        # シンボルマッピング（内部形式 → Binance形式）
        self._symbol_mapping = {}
        self._reverse_mapping = {}
        
        # 為替レートサービス（後で初期化）
        self.fx_service = None
        
        # 利用可能な取引ペア（実行時に取得）
        self.available_symbols = set()
        self.symbol_info = {}
    
    def _generate_signature(self, params: Dict) -> str:
        """HMAC-SHA256署名を生成"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
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
        
        # 利用可能な取引ペアを取得
        await self._fetch_exchange_info()
        
        logger.info(f"Binance collector initialized (testnet: {self.testnet})")
        logger.info(f"Available symbols: JPY={len([s for s in self.available_symbols if 'JPY' in s])}, "
                   f"USDT={len([s for s in self.available_symbols if 'USDT' in s])}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーのイグジット"""
        if self.fx_service:
            await self.fx_service.stop()
        await super().__aexit__(exc_type, exc_val, exc_tb)
    
    async def _fetch_exchange_info(self):
        """取引所情報を取得して利用可能なペアを確認"""
        try:
            async with self.session.get(f"{self.base_url}{self.endpoints['exchange_info']}") as response:
                data = await response.json()
                
                for symbol_info in data.get('symbols', []):
                    if symbol_info['status'] == 'TRADING':
                        symbol = symbol_info['symbol']
                        self.available_symbols.add(symbol)
                        self.symbol_info[symbol] = symbol_info
                        
                        # 内部マッピングを作成
                        base = symbol_info['baseAsset']
                        quote = symbol_info['quoteAsset']
                        
                        # 内部形式（例: BTC/JPY, BTC/USDT）
                        internal_symbol = f"{base}/{quote}"
                        self._symbol_mapping[internal_symbol] = symbol
                        self._reverse_mapping[symbol] = internal_symbol
                
                logger.info(f"Fetched {len(self.available_symbols)} trading symbols from Binance")
                
        except Exception as e:
            logger.error(f"Error fetching exchange info: {e}")
    
    def _is_symbol_available(self, symbol: str) -> bool:
        """シンボルが利用可能かチェック"""
        return symbol in self.available_symbols
    
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """ティッカー情報を取得"""
        try:
            # 内部形式からBinance形式に変換
            if '/' in symbol:
                binance_symbol = self._symbol_mapping.get(symbol)
                if not binance_symbol:
                    # マッピングがない場合は直接変換を試みる
                    binance_symbol = symbol.replace('/', '')
            else:
                binance_symbol = symbol
            
            if not self._is_symbol_available(binance_symbol):
                return None
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['ticker']}",
                params={'symbol': binance_symbol}
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                # 価格データを抽出
                last_price = Decimal(data.get('lastPrice', '0'))
                bid_price = Decimal(data.get('bidPrice', '0'))
                ask_price = Decimal(data.get('askPrice', '0'))
                volume = Decimal(data.get('volume', '0'))
                
                # JPY建てかUSDT建てか判定
                is_jpy = binance_symbol.endswith('JPY')
                is_usdt = binance_symbol.endswith('USDT')
                
                # 価格変換処理
                if is_jpy:
                    # JPY建ての場合はそのまま使用
                    return {
                        'symbol': symbol,
                        'last': last_price,
                        'bid': bid_price,
                        'ask': ask_price,
                        'volume': volume,
                        'timestamp': datetime.now(pytz.UTC),
                        'is_native_jpy': True,
                        'original_quote': 'JPY'
                    }
                    
                elif is_usdt and self.fx_service:
                    # USDT建ての場合は為替レート変換
                    usd_jpy_rate = await self.fx_service.get_rate('USDJPY')
                    
                    return {
                        'symbol': symbol,
                        'last': last_price * usd_jpy_rate,
                        'bid': bid_price * usd_jpy_rate,
                        'ask': ask_price * usd_jpy_rate,
                        'volume': volume,
                        'timestamp': datetime.now(pytz.UTC),
                        'is_native_jpy': False,
                        'original_quote': 'USDT',
                        'fx_rate': usd_jpy_rate,
                        'original_last': last_price,
                        'original_bid': bid_price,
                        'original_ask': ask_price
                    }
                    
                else:
                    # その他の通貨ペア（BTC/ETHなど）
                    return {
                        'symbol': symbol,
                        'last': last_price,
                        'bid': bid_price,
                        'ask': ask_price,
                        'volume': volume,
                        'timestamp': datetime.now(pytz.UTC),
                        'is_native_jpy': False,
                        'original_quote': binance_symbol[-3:] if len(binance_symbol) > 3 else 'UNKNOWN'
                    }
                    
        except Exception as e:
            logger.error(f"Error fetching Binance ticker for {symbol}: {e}")
        
        return None
    
    async def fetch_orderbook(self, symbol: str) -> Optional[Dict]:
        """オーダーブック情報を取得"""
        try:
            # 内部形式からBinance形式に変換
            if '/' in symbol:
                binance_symbol = self._symbol_mapping.get(symbol, symbol.replace('/', ''))
            else:
                binance_symbol = symbol
            
            if not self._is_symbol_available(binance_symbol):
                return None
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['orderbook']}",
                params={'symbol': binance_symbol, 'limit': 50}
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                # JPY建てかUSDT建てか判定
                is_jpy = binance_symbol.endswith('JPY')
                is_usdt = binance_symbol.endswith('USDT')
                
                # 価格変換用レート
                conversion_rate = Decimal('1.0')
                if is_usdt and self.fx_service:
                    conversion_rate = await self.fx_service.get_rate('USDJPY')
                
                # Bidsを変換
                bids = []
                for price_str, size_str in data.get('bids', []):
                    price = Decimal(price_str) * conversion_rate
                    size = Decimal(size_str)
                    bids.append((price, size))
                
                # Asksを変換
                asks = []
                for price_str, size_str in data.get('asks', []):
                    price = Decimal(price_str) * conversion_rate
                    size = Decimal(size_str)
                    asks.append((price, size))
                
                return {
                    'symbol': symbol,
                    'bids': bids,
                    'asks': asks,
                    'timestamp': datetime.now(pytz.UTC),
                    'is_converted': not is_jpy,
                    'conversion_rate': conversion_rate if not is_jpy else None
                }
                
        except Exception as e:
            logger.error(f"Error fetching Binance orderbook for {symbol}: {e}")
        
        return None
    
    async def collect_all_data(self) -> List[Dict]:
        """全通貨ペアのデータを収集（JPY建て・USDT建て両方）"""
        results = []
        
        # 収集するペアのリスト作成
        pairs_to_collect = []
        
        # 1. JPY建てペア（優先）
        for symbol in self.supported_symbols['jpy_pairs']:
            if self._is_symbol_available(symbol):
                base = symbol[:-3]  # JPYを除去
                internal_symbol = f"{base}/JPY"
                display_symbol = f"{base}/JPY"
                pairs_to_collect.append((internal_symbol, display_symbol, 'JPY'))
        
        # 2. USDT建てペア
        for symbol in self.supported_symbols['usdt_pairs']:
            if self._is_symbol_available(symbol):
                base = symbol[:-4]  # USDTを除去
                internal_symbol = f"{base}/USDT"
                display_symbol = f"{base}/JPY"  # 表示はJPY換算
                pairs_to_collect.append((internal_symbol, display_symbol, 'USDT'))
        
        # 3. USD建て比較用データも収集
        usd_pairs = []
        for symbol in self.supported_symbols['usdt_pairs']:
            if self._is_symbol_available(symbol):
                base = symbol[:-4]
                internal_symbol = f"{base}/USDT"
                display_symbol = f"{base}/USD"  # USD表示
                usd_pairs.append((internal_symbol, display_symbol, 'USD'))
        
        # 並列でデータ取得
        tasks = []
        for internal_symbol, display_symbol, quote_type in pairs_to_collect:
            tasks.append(self._collect_pair_data(internal_symbol, display_symbol, quote_type))
        
        # USD建てデータも並列で取得
        for internal_symbol, display_symbol, quote_type in usd_pairs:
            tasks.append(self._collect_pair_data_usd(internal_symbol, display_symbol))
        
        collected_data = await asyncio.gather(*tasks, return_exceptions=True)
        
        for data in collected_data:
            if isinstance(data, dict) and data:
                results.append(data)
        
        # クロスレート分析用データも追加
        await self._add_cross_rate_opportunities(results)
        
        return results
    
    async def _collect_pair_data(self, internal_symbol: str, display_symbol: str, quote_type: str) -> Optional[Dict]:
        """個別通貨ペアのデータを収集（JPY換算）"""
        try:
            # ティッカー情報を取得
            ticker = await self.fetch_ticker(internal_symbol)
            if not ticker:
                return None
            
            # オーダーブック情報を取得
            orderbook = await self.fetch_orderbook(internal_symbol)
            
            # データを整形
            return {
                'exchange': 'binance',
                'symbol': display_symbol,
                'internal_symbol': internal_symbol,
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'last': ticker['last'],
                'volume': ticker['volume'],
                'bid_volume': orderbook['bids'][0][1] if orderbook and orderbook['bids'] else Decimal('0'),
                'ask_volume': orderbook['asks'][0][1] if orderbook and orderbook['asks'] else Decimal('0'),
                'timestamp': ticker['timestamp'],
                'quote_type': quote_type,
                'is_native_jpy': ticker.get('is_native_jpy', False),
                'fx_rate': ticker.get('fx_rate'),
                'original_bid': ticker.get('original_bid'),
                'original_ask': ticker.get('original_ask')
            }
            
        except Exception as e:
            logger.error(f"Error collecting data for {internal_symbol}: {e}")
            return None
    
    async def _collect_pair_data_usd(self, internal_symbol: str, display_symbol: str) -> Optional[Dict]:
        """個別通貨ペアのデータを収集（USD建て）"""
        try:
            # ティッカー情報を取得
            ticker = await self.fetch_ticker(internal_symbol)
            if not ticker or 'original_last' not in ticker:
                return None
            
            # USD建てデータとして整形
            return {
                'exchange': 'binance',
                'symbol': display_symbol,
                'internal_symbol': internal_symbol,
                'bid': ticker.get('original_bid', ticker['bid']),
                'ask': ticker.get('original_ask', ticker['ask']),
                'last': ticker.get('original_last', ticker['last']),
                'volume': ticker['volume'],
                'timestamp': ticker['timestamp'],
                'quote_type': 'USD',
                'is_usd_data': True
            }
            
        except Exception as e:
            logger.error(f"Error collecting USD data for {internal_symbol}: {e}")
            return None
    
    async def _add_cross_rate_opportunities(self, results: List[Dict]):
        """クロスレートのアービトラージ機会を追加"""
        try:
            # USDT/JPYの直接レートがあるか確認
            if self._is_symbol_available('USDTJPY'):
                ticker = await self.fetch_ticker('USDT/JPY')
                if ticker:
                    results.append({
                        'exchange': 'binance',
                        'symbol': 'USDT/JPY',
                        'internal_symbol': 'USDT/JPY',
                        'bid': ticker['bid'],
                        'ask': ticker['ask'],
                        'last': ticker['last'],
                        'volume': ticker['volume'],
                        'timestamp': ticker['timestamp'],
                        'quote_type': 'CROSS',
                        'is_cross_rate': True
                    })
            
            # USD/JPYの参考レートも追加（為替市場との比較用）
            if self.fx_service:
                current_rate = await self.fx_service.get_rate('USDJPY')
                results.append({
                    'exchange': 'fx_market',
                    'symbol': 'USD/JPY',
                    'internal_symbol': 'USD/JPY',
                    'bid': current_rate - Decimal('0.01'),  # 仮想的なスプレッド
                    'ask': current_rate + Decimal('0.01'),
                    'last': current_rate,
                    'volume': Decimal('0'),
                    'timestamp': datetime.now(pytz.UTC),
                    'quote_type': 'FX',
                    'is_reference_rate': True
                })
                
        except Exception as e:
            logger.error(f"Error adding cross rate opportunities: {e}")
    
    def get_supported_pairs(self) -> List[str]:
        """対応通貨ペアのリストを返す（表示用）"""
        pairs = []
        
        # JPY建てペア
        for symbol in self.supported_symbols['jpy_pairs']:
            if self._is_symbol_available(symbol):
                base = symbol[:-3]
                pairs.append(f"{base}/JPY")
        
        # USDT建てペア（JPY換算表示）
        for symbol in self.supported_symbols['usdt_pairs']:
            if self._is_symbol_available(symbol):
                base = symbol[:-4]
                # JPY建てが存在しない場合のみ追加
                jpy_symbol = f"{base}JPY"
                if not self._is_symbol_available(jpy_symbol):
                    pairs.append(f"{base}/JPY (via USDT)")
        
        return sorted(list(set(pairs)))
    
    # 基底クラスの抽象メソッドを実装
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得（ExchangeClient互換）"""
        result = await self.fetch_ticker(symbol)
        return result if result else {}
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得（ExchangeClient互換）"""
        result = await self.fetch_orderbook(symbol)
        return result if result else {}
    
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得"""
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'timestamp': timestamp,
                'recvWindow': 5000
            }
            
            # 署名を生成
            params['signature'] = self._generate_signature(params)
            
            headers = {'X-MBX-APIKEY': self.api_key}
            
            async with self.session.get(
                f"{self.base_url}{self.endpoints['account']}",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # 残高情報を整形
                    balances = {}
                    for balance in data.get('balances', []):
                        asset = balance['asset']
                        free = Decimal(balance['free'])
                        locked = Decimal(balance['locked'])
                        total = free + locked
                        
                        if total > 0:
                            balances[asset] = {
                                'free': free,
                                'locked': locked,
                                'total': total
                            }
                    
                    return {
                        'balances': balances,
                        'account_type': data.get('accountType'),
                        'can_trade': data.get('canTrade'),
                        'maker_commission': data.get('makerCommission'),
                        'taker_commission': data.get('takerCommission')
                    }
                else:
                    logger.error(f"Failed to get balance: {response.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
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