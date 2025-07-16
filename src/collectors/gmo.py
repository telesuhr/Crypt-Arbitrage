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


class GMOClient(ExchangeClient):
    """GMOコイン APIクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("gmo", config)
        self.api_key = os.getenv("GMO_API_KEY")
        self.api_secret = os.getenv("GMO_API_SECRET")
        self.public_url = config['api']['base_url']
        self.private_url = config['api']['private_url']
        self.ws_url = config['api']['ws_url']
        
    def _generate_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """認証ヘッダーを生成"""
        timestamp = str(int(time.time() * 1000))
        text = timestamp + method + path + body
        
        signature = hmac.new(
            self.api_secret.encode() if self.api_secret else b"",
            text.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "API-KEY": self.api_key or "",
            "API-TIMESTAMP": timestamp,
            "API-SIGN": signature,
            "Content-Type": "application/json"
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """シンボルをGMO形式に変換 (BTC/JPY -> BTC_JPY)"""
        return symbol.replace("/", "_")
    
    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """GMO形式のシンボルを共通形式に変換 (BTC_JPY -> BTC/JPY)"""
        return exchange_symbol.replace("_", "/")
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得"""
        gmo_symbol = self.normalize_symbol(symbol)
        url = f"{self.public_url}/v1/ticker?symbol={gmo_symbol}"
        
        try:
            response = await self._request("GET", url)
            data = response['data'][0]  # GMOは配列で返す
            
            price_data = PriceData(
                exchange_code=self.exchange_code,
                symbol=symbol,
                timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00')),
                bid=Decimal(str(data['bid'])),
                ask=Decimal(str(data['ask'])),
                bid_size=Decimal("0"),  # GMOのtickerAPIではサイズ情報なし
                ask_size=Decimal("0"),
                last_price=Decimal(str(data['last'])),
                volume_24h=Decimal(str(data['volume']))
            )
            
            return price_data.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol} from GMO: {e}")
            raise
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得"""
        gmo_symbol = self.normalize_symbol(symbol)
        url = f"{self.public_url}/v1/orderbooks?symbol={gmo_symbol}"
        
        try:
            response = await self._request("GET", url)
            data = response['data']
            
            # データを正規化
            bids = [
                {'price': Decimal(str(bid['price'])), 'size': Decimal(str(bid['size']))}
                for bid in data['bids'][:depth]
            ]
            asks = [
                {'price': Decimal(str(ask['price'])), 'size': Decimal(str(ask['size']))}
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
            logger.error(f"Failed to get orderbook for {symbol} from GMO: {e}")
            raise
    
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for GMO")
        
        path = "/v1/account/assets"
        headers = self._generate_headers("GET", path)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("GET", url, headers=headers)
            data = response['data']
            
            # 残高情報を正規化
            balances = {}
            for asset in data:
                currency = asset['symbol']
                balances[currency] = {
                    'available': Decimal(str(asset['available'])),
                    'locked': Decimal(str(asset['conversionRate'])) * Decimal(str(asset['amount'])) - Decimal(str(asset['available'])) if asset.get('conversionRate') else Decimal("0"),
                    'total': Decimal(str(asset['amount']))
                }
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get balance from GMO: {e}")
            raise
    
    async def place_order(self, symbol: str, side: str, size: Decimal,
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict[str, Any]:
        """注文を発注"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for GMO")
        
        gmo_symbol = self.normalize_symbol(symbol)
        
        body = {
            "symbol": gmo_symbol,
            "side": side.upper(),
            "executionType": "LIMIT" if order_type.lower() == "limit" else "MARKET",
            "size": str(size)
        }
        
        if order_type.lower() == "limit" and price is not None:
            body["price"] = str(price)
        
        body_json = json.dumps(body)
        path = "/v1/order"
        headers = self._generate_headers("POST", path, body_json)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("POST", url, headers=headers, data=body_json)
            data = response['data']
            
            return {
                'order_id': data['orderId'],
                'status': 'accepted'
            }
            
        except Exception as e:
            logger.error(f"Failed to place order on GMO: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """注文をキャンセル"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for GMO")
        
        body = {"orderId": order_id}
        body_json = json.dumps(body)
        path = "/v1/cancelOrder"
        headers = self._generate_headers("POST", path, body_json)
        url = f"{self.private_url}{path}"
        
        try:
            await self._request("POST", url, headers=headers, data=body_json)
            
            return {
                'order_id': order_id,
                'status': 'cancelled'
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel order on GMO: {e}")
            raise
    
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """注文一覧を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for GMO")
        
        path = "/v1/activeOrders"
        headers = self._generate_headers("GET", path)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("GET", url, headers=headers)
            data = response['data']
            
            orders = []
            for order in data.get('list', []):
                # シンボルフィルタリング
                if symbol and self.denormalize_symbol(order['symbol']) != symbol:
                    continue
                
                orders.append({
                    'order_id': order['orderId'],
                    'symbol': self.denormalize_symbol(order['symbol']),
                    'side': order['side'].lower(),
                    'order_type': 'limit' if order['executionType'] == 'LIMIT' else 'market',
                    'price': Decimal(str(order.get('price', 0))),
                    'size': Decimal(str(order['size'])),
                    'executed_size': Decimal(str(order.get('executedSize', 0))),
                    'status': order['status'].lower(),
                    'created_at': datetime.fromisoformat(order['timestamp'].replace('Z', '+00:00'))
                })
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders from GMO: {e}")
            raise