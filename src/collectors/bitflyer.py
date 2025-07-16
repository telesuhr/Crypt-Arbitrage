import os
import time
import hmac
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import pytz
from decimal import Decimal
import aiohttp
from loguru import logger

from .base import ExchangeClient, PriceData, OrderbookData


class BitFlyerClient(ExchangeClient):
    """bitFlyer APIクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("bitflyer", config)
        self.api_key = os.getenv("BITFLYER_API_KEY")
        self.api_secret = os.getenv("BITFLYER_API_SECRET")
        self.base_url = config['api']['base_url']
        self.ws_url = config['api']['ws_url']
        
    def _generate_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """認証ヘッダーを生成"""
        timestamp = str(int(time.time()))
        text = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode() if self.api_secret else b"",
            text.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "ACCESS-KEY": self.api_key or "",
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-SIGN": signature,
            "Content-Type": "application/json"
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """シンボルをbitFlyer形式に変換 (BTC/JPY -> BTC_JPY)"""
        return symbol.replace("/", "_")
    
    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """bitFlyer形式のシンボルを共通形式に変換 (BTC_JPY -> BTC/JPY)"""
        return exchange_symbol.replace("_", "/")
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得"""
        product_code = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v1/ticker?product_code={product_code}"
        
        try:
            data = await self._request("GET", url)
            
            # PriceDataオブジェクトに変換
            price_data = PriceData(
                exchange_code=self.exchange_code,
                symbol=symbol,
                # bitFlyer APIはUTC時刻を返すが、Zサフィックスなし
                timestamp=pytz.UTC.localize(datetime.fromisoformat(data['timestamp'])).astimezone(pytz.timezone('Asia/Tokyo')),
                bid=Decimal(str(data['best_bid'])),
                ask=Decimal(str(data['best_ask'])),
                bid_size=Decimal(str(data['best_bid_size'])),
                ask_size=Decimal(str(data['best_ask_size'])),
                last_price=Decimal(str(data['ltp'])),
                volume_24h=Decimal(str(data['volume']))
            )
            
            return price_data.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol} from bitFlyer: {e}")
            raise
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得"""
        product_code = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v1/board?product_code={product_code}"
        
        try:
            data = await self._request("GET", url)
            
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
                timestamp=datetime.now(pytz.timezone('Asia/Tokyo')),
                bids=bids,
                asks=asks
            )
            
            return orderbook.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get orderbook for {symbol} from bitFlyer: {e}")
            raise
    
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitFlyer")
        
        path = "/v1/me/getbalance"
        headers = self._generate_headers("GET", path)
        url = f"{self.base_url}{path}"
        
        try:
            data = await self._request("GET", url, headers=headers)
            
            # 残高情報を正規化
            balances = {}
            for balance in data:
                currency = balance['currency_code']
                balances[currency] = {
                    'available': Decimal(str(balance['available'])),
                    'amount': Decimal(str(balance['amount']))
                }
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get balance from bitFlyer: {e}")
            raise
    
    async def place_order(self, symbol: str, side: str, size: Decimal,
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict[str, Any]:
        """注文を発注"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitFlyer")
        
        product_code = self.normalize_symbol(symbol)
        
        body = {
            "product_code": product_code,
            "child_order_type": order_type.upper(),
            "side": side.upper(),
            "size": float(size)
        }
        
        if order_type.lower() == "limit" and price is not None:
            body["price"] = float(price)
        
        body_json = json.dumps(body)
        path = "/v1/me/sendchildorder"
        headers = self._generate_headers("POST", path, body_json)
        url = f"{self.base_url}{path}"
        
        try:
            data = await self._request("POST", url, headers=headers, data=body_json)
            
            return {
                'order_id': data['child_order_acceptance_id'],
                'status': 'accepted'
            }
            
        except Exception as e:
            logger.error(f"Failed to place order on bitFlyer: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """注文をキャンセル"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitFlyer")
        
        body = {}
        
        if symbol:
            body["product_code"] = self.normalize_symbol(symbol)
            body["child_order_acceptance_id"] = order_id
        else:
            # シンボルが指定されていない場合は、child_order_idとして扱う
            body["child_order_id"] = order_id
        
        body_json = json.dumps(body)
        path = "/v1/me/cancelchildorder"
        headers = self._generate_headers("POST", path, body_json)
        url = f"{self.base_url}{path}"
        
        try:
            await self._request("POST", url, headers=headers, data=body_json)
            
            return {
                'order_id': order_id,
                'status': 'cancelled'
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel order on bitFlyer: {e}")
            raise
    
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """注文一覧を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitFlyer")
        
        params = {}
        if symbol:
            params["product_code"] = self.normalize_symbol(symbol)
        if status:
            params["child_order_state"] = status.upper()
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        path = f"/v1/me/getchildorders{f'?{query_string}' if query_string else ''}"
        headers = self._generate_headers("GET", path)
        url = f"{self.base_url}{path}"
        
        try:
            data = await self._request("GET", url, headers=headers)
            
            orders = []
            for order in data:
                orders.append({
                    'order_id': order['child_order_acceptance_id'],
                    'symbol': self.denormalize_symbol(order['product_code']),
                    'side': order['side'].lower(),
                    'order_type': order['child_order_type'].lower(),
                    'price': Decimal(str(order.get('price', 0))),
                    'size': Decimal(str(order['size'])),
                    'executed_size': Decimal(str(order['executed_size'])),
                    'status': order['child_order_state'].lower(),
                    'created_at': datetime.fromisoformat(order['child_order_date'].replace('Z', '+00:00')).astimezone(pytz.timezone('Asia/Tokyo'))
                })
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders from bitFlyer: {e}")
            raise
    
    async def subscribe_ticker(self, symbol: str):
        """WebSocketでティッカー情報を購読"""
        if not self.ws_session:
            self.ws_session = await aiohttp.ClientSession().__aenter__()
        
        product_code = self.normalize_symbol(symbol)
        channel = f"lightning_ticker_{product_code}"
        
        async with self.ws_session.ws_connect(self.ws_url) as ws:
            # チャンネル購読
            await ws.send_json({
                "method": "subscribe",
                "params": {"channel": channel}
            })
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("method") == "channelMessage":
                        yield self._parse_ws_ticker(data["params"]["message"])
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
    
    def _parse_ws_ticker(self, data: Dict[str, Any]) -> PriceData:
        """WebSocketのティッカーデータをパース"""
        return PriceData(
            exchange_code=self.exchange_code,
            symbol=self.denormalize_symbol(data['product_code']),
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00')).astimezone(pytz.timezone('Asia/Tokyo')),
            bid=Decimal(str(data['best_bid'])),
            ask=Decimal(str(data['best_ask'])),
            bid_size=Decimal(str(data['best_bid_size'])),
            ask_size=Decimal(str(data['best_ask_size'])),
            last_price=Decimal(str(data['ltp'])),
            volume_24h=Decimal(str(data['volume']))
        )