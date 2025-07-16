import os
import time
import hmac
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
import aiohttp
from loguru import logger

from .base import ExchangeClient, PriceData, OrderbookData


class CoincheckClient(ExchangeClient):
    """Coincheck APIクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("coincheck", config)
        self.api_key = os.getenv("COINCHECK_API_KEY")
        self.api_secret = os.getenv("COINCHECK_API_SECRET")
        self.base_url = config['api']['base_url']
        
    def _generate_headers(self, url: str, body: str = "") -> Dict[str, str]:
        """認証ヘッダーを生成"""
        nonce = str(int(time.time() * 1000000))
        message = nonce + url + body
        signature = hmac.new(
            self.api_secret.encode() if self.api_secret else b"",
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "ACCESS-KEY": self.api_key or "",
            "ACCESS-NONCE": nonce,
            "ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json"
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """シンボルをCoincheck形式に変換 (BTC/JPY -> btc_jpy)"""
        return symbol.replace("/", "_").lower()
    
    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """Coincheck形式のシンボルを共通形式に変換 (btc_jpy -> BTC/JPY)"""
        parts = exchange_symbol.upper().split("_")
        return f"{parts[0]}/{parts[1]}" if len(parts) == 2 else exchange_symbol
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得"""
        # Coincheckは全ペアのティッカーを一度に返す
        url = f"{self.base_url}/ticker"
        
        try:
            data = await self._request("GET", url)
            
            # 現在の価格情報から計算
            last_price = Decimal(str(data['last']))
            # Coincheckはbid/askを直接提供しないので、last価格を使用
            # 実際の取引では板情報から取得する必要がある
            
            price_data = PriceData(
                exchange_code=self.exchange_code,
                symbol=symbol,
                timestamp=datetime.fromtimestamp(int(data['timestamp'])),
                bid=last_price,  # 簡易実装
                ask=last_price,  # 簡易実装
                bid_size=Decimal("0"),
                ask_size=Decimal("0"),
                last_price=last_price,
                volume_24h=Decimal(str(data['volume']))
            )
            
            return price_data.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol} from Coincheck: {e}")
            raise
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得"""
        url = f"{self.base_url}/order_books"
        
        try:
            data = await self._request("GET", url)
            
            # データを正規化
            bids = [
                {'price': Decimal(str(bid[0])), 'size': Decimal(str(bid[1]))}
                for bid in data['bids'][:depth]
            ]
            asks = [
                {'price': Decimal(str(ask[0])), 'size': Decimal(str(ask[1]))}
                for ask in data['asks'][:depth]
            ]
            
            orderbook = OrderbookData(
                exchange_code=self.exchange_code,
                symbol=symbol,
                timestamp=datetime.now(),
                bids=bids,
                asks=asks
            )
            
            return orderbook.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get orderbook for {symbol} from Coincheck: {e}")
            raise
    
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for Coincheck")
        
        url = f"{self.base_url}/accounts/balance"
        headers = self._generate_headers(url)
        
        try:
            data = await self._request("GET", url, headers=headers)
            
            # 残高情報を正規化
            balances = {}
            
            # 通貨ごとに残高を抽出
            for key, value in data.items():
                if key == "success":
                    continue
                
                # Coincheckのレスポンス形式: "jpy", "btc", "jpy_reserved", "btc_reserved"
                if "_reserved" in key:
                    continue
                    
                currency = key.upper()
                available = Decimal(str(value))
                reserved_key = f"{key}_reserved"
                reserved = Decimal(str(data.get(reserved_key, 0)))
                
                balances[currency] = {
                    'available': available,
                    'locked': reserved,
                    'total': available + reserved
                }
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get balance from Coincheck: {e}")
            raise
    
    async def place_order(self, symbol: str, side: str, size: Decimal,
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict[str, Any]:
        """注文を発注（未実装）"""
        raise NotImplementedError("Coincheck order placement not implemented")
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """注文をキャンセル（未実装）"""
        raise NotImplementedError("Coincheck order cancellation not implemented")
    
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """注文一覧を取得（未実装）"""
        raise NotImplementedError("Coincheck order list not implemented")