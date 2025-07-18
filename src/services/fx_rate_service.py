"""
為替レートサービス
USDT建て価格をJPY建てに変換するための為替レート管理
"""

import asyncio
import aiohttp
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from loguru import logger


class FXRateService:
    """為替レート管理サービス"""
    
    def __init__(self):
        self.rates = {}
        self.last_update = None
        self.update_interval = timedelta(minutes=5)  # 5分ごとに更新
        self.session = None
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # フォールバック用の固定レート
        self.fallback_rates = {
            'USDJPY': Decimal('155.0'),  # 安全マージンを含む推定値
        }
    
    async def start(self):
        """サービス開始"""
        self.session = aiohttp.ClientSession()
        await self.update_rates()
    
    async def stop(self):
        """サービス停止"""
        if self.session:
            await self.session.close()
    
    async def get_rate(self, pair: str = 'USDJPY') -> Decimal:
        """為替レートを取得"""
        # 更新が必要かチェック
        if self._should_update():
            await self.update_rates()
        
        # レートを返す（なければフォールバック）
        return self.rates.get(pair, self.fallback_rates.get(pair, Decimal('155.0')))
    
    def _should_update(self) -> bool:
        """更新が必要かチェック"""
        if not self.last_update:
            return True
        
        return datetime.now(self.jst) - self.last_update > self.update_interval
    
    async def update_rates(self):
        """為替レートを更新"""
        try:
            # 複数のソースから取得を試みる
            rate = await self._fetch_from_exchangerate_api()
            if not rate:
                rate = await self._fetch_from_fixer()
            if not rate:
                rate = await self._fetch_from_free_api()
            
            if rate:
                self.rates['USDJPY'] = rate
                self.last_update = datetime.now(self.jst)
                logger.info(f"FX rate updated: USDJPY = {rate}")
            else:
                logger.warning("Failed to update FX rates, using fallback")
                self.rates['USDJPY'] = self.fallback_rates['USDJPY']
                
        except Exception as e:
            logger.error(f"Error updating FX rates: {e}")
            self.rates['USDJPY'] = self.fallback_rates['USDJPY']
    
    async def _fetch_from_exchangerate_api(self) -> Optional[Decimal]:
        """exchangerate-api.comから取得（無料枠あり）"""
        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'rates' in data and 'JPY' in data['rates']:
                        return Decimal(str(data['rates']['JPY']))
        except Exception as e:
            logger.debug(f"exchangerate-api failed: {e}")
        return None
    
    async def _fetch_from_fixer(self) -> Optional[Decimal]:
        """fixer.ioから取得（APIキー不要の基本機能）"""
        try:
            url = "https://api.fixer.io/latest?base=USD&symbols=JPY"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'rates' in data and 'JPY' in data['rates']:
                        return Decimal(str(data['rates']['JPY']))
        except Exception as e:
            logger.debug(f"fixer.io failed: {e}")
        return None
    
    async def _fetch_from_free_api(self) -> Optional[Decimal]:
        """フリーAPIから取得"""
        try:
            # CoinGeckoのシンプル価格API（無料）
            url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=jpy"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'tether' in data and 'jpy' in data['tether']:
                        return Decimal(str(data['tether']['jpy']))
        except Exception as e:
            logger.debug(f"CoinGecko API failed: {e}")
        return None
    
    def convert_usdt_to_jpy(self, usdt_amount: Decimal) -> Decimal:
        """USDTをJPYに変換"""
        rate = self.rates.get('USDJPY', self.fallback_rates['USDJPY'])
        return usdt_amount * rate
    
    def convert_jpy_to_usdt(self, jpy_amount: Decimal) -> Decimal:
        """JPYをUSDTに変換"""
        rate = self.rates.get('USDJPY', self.fallback_rates['USDJPY'])
        if rate > 0:
            return jpy_amount / rate
        return Decimal('0')


# グローバルインスタンス
fx_service = FXRateService()


async def get_usdjpy_rate() -> Decimal:
    """USD/JPYレートを取得するヘルパー関数"""
    return await fx_service.get_rate('USDJPY')


def usdt_to_jpy(amount: Decimal) -> Decimal:
    """USDT→JPY変換ヘルパー関数"""
    return fx_service.convert_usdt_to_jpy(amount)


def jpy_to_usdt(amount: Decimal) -> Decimal:
    """JPY→USDT変換ヘルパー関数"""
    return fx_service.convert_jpy_to_usdt(amount)