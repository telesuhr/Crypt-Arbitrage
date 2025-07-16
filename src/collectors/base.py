from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime
from decimal import Decimal
import aiohttp
from loguru import logger


class ExchangeClient(ABC):
    """取引所APIクライアントの基底クラス"""
    
    def __init__(self, exchange_code: str, config: Dict[str, Any]):
        self.exchange_code = exchange_code
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_session = None
        
    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリ"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーのイグジット"""
        if self.session:
            await self.session.close()
        if self.ws_session:
            await self.ws_session.close()
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得"""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得"""
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得"""
        pass
    
    @abstractmethod
    async def place_order(self, symbol: str, side: str, size: Decimal, 
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict[str, Any]:
        """注文を発注"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """注文をキャンセル"""
        pass
    
    @abstractmethod
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """注文一覧を取得"""
        pass
    
    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """HTTP リクエストの共通処理"""
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Request failed for {self.exchange_code}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in request for {self.exchange_code}: {e}")
            raise
    
    def normalize_symbol(self, symbol: str) -> str:
        """シンボルを取引所固有の形式に正規化"""
        # デフォルトは変更なし、各取引所で必要に応じてオーバーライド
        return symbol
    
    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """取引所固有のシンボルを共通形式に変換"""
        # デフォルトは変更なし、各取引所で必要に応じてオーバーライド
        return exchange_symbol


class PriceData:
    """価格データを表すクラス"""
    
    def __init__(self, exchange_code: str, symbol: str, timestamp: datetime,
                 bid: Decimal, ask: Decimal, bid_size: Decimal, ask_size: Decimal,
                 last_price: Optional[Decimal] = None, volume_24h: Optional[Decimal] = None):
        self.exchange_code = exchange_code
        self.symbol = symbol
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.bid_size = bid_size
        self.ask_size = ask_size
        self.last_price = last_price
        self.volume_24h = volume_24h
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'exchange_code': self.exchange_code,
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'bid': float(self.bid),
            'ask': float(self.ask),
            'bid_size': float(self.bid_size),
            'ask_size': float(self.ask_size),
            'last_price': float(self.last_price) if self.last_price else None,
            'volume_24h': float(self.volume_24h) if self.volume_24h else None
        }
    
    @property
    def spread(self) -> Decimal:
        """スプレッドを計算"""
        return self.ask - self.bid
    
    @property
    def spread_percentage(self) -> Decimal:
        """スプレッド率を計算"""
        mid_price = (self.bid + self.ask) / 2
        return (self.spread / mid_price) * 100 if mid_price > 0 else Decimal(0)


class OrderbookData:
    """オーダーブックデータを表すクラス"""
    
    def __init__(self, exchange_code: str, symbol: str, timestamp: datetime,
                 bids: List[Dict[str, Decimal]], asks: List[Dict[str, Decimal]]):
        self.exchange_code = exchange_code
        self.symbol = symbol
        self.timestamp = timestamp
        self.bids = bids  # [{'price': Decimal, 'size': Decimal}, ...]
        self.asks = asks  # [{'price': Decimal, 'size': Decimal}, ...]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'exchange_code': self.exchange_code,
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'bids': [{'price': float(b['price']), 'size': float(b['size'])} for b in self.bids],
            'asks': [{'price': float(a['price']), 'size': float(a['size'])} for a in self.asks]
        }
    
    def get_best_bid(self) -> Optional[Dict[str, Decimal]]:
        """最良買い注文を取得"""
        return self.bids[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[Dict[str, Decimal]]:
        """最良売り注文を取得"""
        return self.asks[0] if self.asks else None
    
    def calculate_depth(self, side: str, volume: Decimal) -> Optional[Decimal]:
        """指定ボリュームでの平均価格を計算"""
        orders = self.bids if side == 'buy' else self.asks
        remaining_volume = volume
        total_cost = Decimal(0)
        
        for order in orders:
            if remaining_volume <= 0:
                break
            
            fill_volume = min(remaining_volume, order['size'])
            total_cost += fill_volume * order['price']
            remaining_volume -= fill_volume
        
        if remaining_volume > 0:
            # 板が薄くて全量約定できない
            return None
        
        return total_cost / volume