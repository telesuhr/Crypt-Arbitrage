import os
import time
import hmac
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz
from decimal import Decimal
import aiohttp
from loguru import logger

from .base import ExchangeClient, PriceData, OrderbookData


class BitbankClient(ExchangeClient):
    """bitbank APIクライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("bitbank", config)
        self.api_key = os.getenv("BITBANK_API_KEY")
        self.api_secret = os.getenv("BITBANK_API_SECRET")
        self.public_url = config['api']['base_url']
        self.private_url = config['api']['private_url']
        self.ws_url = config['api']['ws_url']
        
    def _generate_headers(self, nonce: str, message: str) -> Dict[str, str]:
        """認証ヘッダーを生成"""
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
        """シンボルをbitbank形式に変換 (BTC/JPY -> btc_jpy)"""
        return symbol.replace("/", "_").lower()
    
    def denormalize_symbol(self, exchange_symbol: str) -> str:
        """bitbank形式のシンボルを共通形式に変換 (btc_jpy -> BTC/JPY)"""
        parts = exchange_symbol.upper().split("_")
        return f"{parts[0]}/{parts[1]}" if len(parts) == 2 else exchange_symbol
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得"""
        pair = self.normalize_symbol(symbol)
        url = f"{self.public_url}/{pair}/ticker"
        
        try:
            response = await self._request("GET", url)
            data = response['data']
            
            # タイムスタンプはミリ秒単位
            timestamp = datetime.fromtimestamp(int(data['timestamp']) / 1000, tz=pytz.timezone('Asia/Tokyo'))
            
            price_data = PriceData(
                exchange_code=self.exchange_code,
                symbol=symbol,
                timestamp=timestamp,
                bid=Decimal(str(data['buy'])),
                ask=Decimal(str(data['sell'])),
                bid_size=Decimal("0"),  # bitbankのtickerAPIではサイズ情報なし
                ask_size=Decimal("0"),
                last_price=Decimal(str(data['last'])),
                volume_24h=Decimal(str(data['vol']))
            )
            
            return price_data.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol} from bitbank: {e}")
            raise
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """オーダーブック情報を取得"""
        pair = self.normalize_symbol(symbol)
        url = f"{self.public_url}/{pair}/depth"
        
        try:
            response = await self._request("GET", url)
            data = response['data']
            
            # タイムスタンプはミリ秒単位
            timestamp = datetime.fromtimestamp(int(data['timestamp']) / 1000, tz=pytz.timezone('Asia/Tokyo'))
            
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
                timestamp=timestamp,
                bids=bids,
                asks=asks
            )
            
            return orderbook.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to get orderbook for {symbol} from bitbank: {e}")
            raise
    
    async def get_balance(self) -> Dict[str, Any]:
        """残高情報を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitbank")
        
        nonce = str(int(time.time() * 1000))
        path = "/v1/user/assets"
        message = nonce + path
        headers = self._generate_headers(nonce, message)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("GET", url, headers=headers)
            data = response['data']
            
            # 残高情報を正規化
            balances = {}
            for asset in data['assets']:
                currency = asset['asset'].upper()
                balances[currency] = {
                    'available': Decimal(str(asset['free_amount'])),
                    'locked': Decimal(str(asset['locked_amount'])),
                    'total': Decimal(str(asset['onhand_amount']))
                }
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get balance from bitbank: {e}")
            raise
    
    async def place_order(self, symbol: str, side: str, size: Decimal,
                         order_type: str = "market", price: Optional[Decimal] = None) -> Dict[str, Any]:
        """注文を発注"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitbank")
        
        pair = self.normalize_symbol(symbol)
        
        # bitbankのorder typeマッピング
        type_map = {
            "limit": "limit",
            "market": "market",
            "stop": "stop",
            "stop_limit": "stop_limit"
        }
        
        body = {
            "pair": pair,
            "amount": str(size),
            "side": side.lower(),
            "type": type_map.get(order_type.lower(), "limit")
        }
        
        if order_type.lower() in ["limit", "stop_limit"] and price is not None:
            body["price"] = str(price)
        
        nonce = str(int(time.time() * 1000))
        path = "/v1/user/spot/order"
        body_json = json.dumps(body)
        message = nonce + body_json
        headers = self._generate_headers(nonce, message)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("POST", url, headers=headers, data=body_json)
            data = response['data']
            
            return {
                'order_id': str(data['order_id']),
                'status': data['status'],
                'created_at': datetime.fromtimestamp(int(data['ordered_at']) / 1000)
            }
            
        except Exception as e:
            logger.error(f"Failed to place order on bitbank: {e}")
            raise
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """注文をキャンセル"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitbank")
        
        if not symbol:
            raise ValueError("Symbol is required for bitbank order cancellation")
        
        pair = self.normalize_symbol(symbol)
        
        body = {
            "pair": pair,
            "order_id": int(order_id)
        }
        
        nonce = str(int(time.time() * 1000))
        path = "/v1/user/spot/cancel_order"
        body_json = json.dumps(body)
        message = nonce + body_json
        headers = self._generate_headers(nonce, message)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("POST", url, headers=headers, data=body_json)
            data = response['data']
            
            return {
                'order_id': str(data['order_id']),
                'status': 'cancelled',
                'cancelled_at': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel order on bitbank: {e}")
            raise
    
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """注文一覧を取得"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not set for bitbank")
        
        # bitbankは一度に一つのペアの注文しか取得できない
        if not symbol:
            # TODO: 全ペアの注文を取得する実装
            raise ValueError("Symbol is required for bitbank orders query")
        
        pair = self.normalize_symbol(symbol)
        
        body = {
            "pair": pair,
            "count": 100,  # 最大100件
            "since": 0,
            "end": int(time.time() * 1000)
        }
        
        nonce = str(int(time.time() * 1000))
        path = "/v1/user/spot/orders_info"
        body_json = json.dumps(body)
        message = nonce + body_json
        headers = self._generate_headers(nonce, message)
        url = f"{self.private_url}{path}"
        
        try:
            response = await self._request("POST", url, headers=headers, data=body_json)
            data = response['data']
            
            orders = []
            for order in data['orders']:
                # ステータスフィルタリング
                if status and order['status'] != status:
                    continue
                
                orders.append({
                    'order_id': str(order['order_id']),
                    'symbol': symbol,
                    'side': order['side'],
                    'order_type': order['type'],
                    'price': Decimal(str(order.get('price', 0))),
                    'size': Decimal(str(order['start_amount'])),
                    'executed_size': Decimal(str(order['executed_amount'])),
                    'remaining_size': Decimal(str(order['remaining_amount'])),
                    'status': order['status'],
                    'created_at': datetime.fromtimestamp(int(order['ordered_at']) / 1000)
                })
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders from bitbank: {e}")
            raise
    
    async def subscribe_ticker(self, symbol: str):
        """WebSocketでティッカー情報を購読"""
        if not self.ws_session:
            self.ws_session = await aiohttp.ClientSession().__aenter__()
        
        pair = self.normalize_symbol(symbol)
        
        async with self.ws_session.ws_connect(self.ws_url) as ws:
            # チャンネル購読
            await ws.send_json({
                "room_name": f"ticker_{pair}",
                "command": "subscribe"
            })
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("room_name") == f"ticker_{pair}":
                        yield self._parse_ws_ticker(data["message"]["data"], symbol)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
    
    def _parse_ws_ticker(self, data: Dict[str, Any], symbol: str) -> PriceData:
        """WebSocketのティッカーデータをパース"""
        timestamp = datetime.fromtimestamp(int(data['timestamp']) / 1000, tz=pytz.timezone('Asia/Tokyo'))
        
        return PriceData(
            exchange_code=self.exchange_code,
            symbol=symbol,
            timestamp=timestamp,
            bid=Decimal(str(data['buy'])),
            ask=Decimal(str(data['sell'])),
            bid_size=Decimal("0"),  # WebSocketでもサイズ情報なし
            ask_size=Decimal("0"),
            last_price=Decimal(str(data['last'])),
            volume_24h=Decimal(str(data['vol']))
        )