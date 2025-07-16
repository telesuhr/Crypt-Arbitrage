import asyncio
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..database.connection import db
from ..database.models import save_price_tick, get_or_create_exchange, get_or_create_pair
from .bitflyer import BitFlyerClient
from .bitbank import BitbankClient
from .coincheck import CoincheckClient
from .gmo import GMOClient


class DataCollector:
    """価格データ収集デーモン"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "exchanges.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.exchanges = {}
        self.scheduler = AsyncIOScheduler()
        self.running = False
        
    async def initialize(self):
        """初期化処理"""
        logger.info("Initializing data collector...")
        
        # 取引所クライアントの初期化
        for exchange_code, exchange_config in self.config['exchanges'].items():
            if not exchange_config.get('enabled', False):
                continue
                
            try:
                if exchange_code == 'bitflyer':
                    client = BitFlyerClient(exchange_config)
                elif exchange_code == 'bitbank':
                    client = BitbankClient(exchange_config)
                elif exchange_code == 'coincheck':
                    client = CoincheckClient(exchange_config)
                elif exchange_code == 'gmo':
                    client = GMOClient(exchange_config)
                else:
                    logger.warning(f"Unsupported exchange: {exchange_code}")
                    continue
                
                self.exchanges[exchange_code] = {
                    'client': client,
                    'config': exchange_config,
                    'pairs': exchange_config.get('supported_pairs', [])
                }
                logger.info(f"Initialized {exchange_code} client")
                
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_code}: {e}")
        
        # データベース接続テスト
        if not db.test_connection():
            raise Exception("Database connection failed")
        
        logger.info(f"Data collector initialized with {len(self.exchanges)} exchanges")
    
    async def collect_price_data(self, exchange_code: str, symbol: str):
        """単一の通貨ペアの価格データを収集"""
        try:
            exchange_info = self.exchanges[exchange_code]
            client = exchange_info['client']
            
            # ティッカー情報を取得
            ticker_data = await client.get_ticker(symbol)
            
            # データベースに保存
            with db.get_session() as session:
                save_price_tick(session, exchange_code, symbol, ticker_data)
            
            logger.debug(f"Collected price data for {symbol} from {exchange_code}")
            
        except Exception as e:
            logger.error(f"Failed to collect price data for {symbol} from {exchange_code}: {e}")
    
    async def collect_orderbook_data(self, exchange_code: str, symbol: str):
        """オーダーブックデータを収集"""
        try:
            exchange_info = self.exchanges[exchange_code]
            client = exchange_info['client']
            
            # オーダーブック情報を取得
            orderbook_data = await client.get_orderbook(symbol)
            
            # データベースに保存
            with db.get_session() as session:
                exchange = get_or_create_exchange(session, exchange_code)
                pair = get_or_create_pair(session, symbol)
                
                if exchange and pair:
                    from ..database.models import OrderbookSnapshot
                    
                    snapshot = OrderbookSnapshot(
                        exchange_id=exchange.id,
                        pair_id=pair.id,
                        timestamp=orderbook_data['timestamp'],
                        bids=orderbook_data['bids'],
                        asks=orderbook_data['asks'],
                        depth=len(orderbook_data['bids'])
                    )
                    session.add(snapshot)
                    session.commit()
            
            logger.debug(f"Collected orderbook data for {symbol} from {exchange_code}")
            
        except Exception as e:
            logger.error(f"Failed to collect orderbook data for {symbol} from {exchange_code}: {e}")
    
    async def collect_all_prices(self):
        """全取引所・全通貨ペアの価格データを収集"""
        tasks = []
        
        for exchange_code, exchange_info in self.exchanges.items():
            client = exchange_info['client']
            
            # セッションを開始
            await client.__aenter__()
            
            for pair in exchange_info['pairs']:
                # 共通シンボル形式に変換
                symbol = pair.replace('_', '/').upper()
                if '/' not in symbol:
                    # BTCJPYのような形式の場合
                    if symbol.endswith('JPY'):
                        symbol = f"{symbol[:-3]}/{symbol[-3:]}"
                    elif symbol.endswith('USDT'):
                        symbol = f"{symbol[:-4]}/{symbol[-4:]}"
                
                tasks.append(self.collect_price_data(exchange_code, symbol))
        
        # 全タスクを並列実行
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # セッションをクローズ
        for exchange_info in self.exchanges.values():
            await exchange_info['client'].__aexit__(None, None, None)
    
    async def collect_orderbooks_periodically(self):
        """定期的にオーダーブックを収集（より低頻度）"""
        tasks = []
        
        for exchange_code, exchange_info in self.exchanges.items():
            client = exchange_info['client']
            
            # セッションを開始
            await client.__aenter__()
            
            # 主要通貨ペアのみオーダーブックを収集
            major_pairs = ['BTC/JPY', 'ETH/JPY']
            for symbol in major_pairs:
                if any(symbol.replace('/', '_').lower() in pair.lower() for pair in exchange_info['pairs']):
                    tasks.append(self.collect_orderbook_data(exchange_code, symbol))
        
        # 全タスクを並列実行
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # セッションをクローズ
        for exchange_info in self.exchanges.values():
            await exchange_info['client'].__aexit__(None, None, None)
    
    def start(self):
        """データ収集を開始"""
        if self.running:
            logger.warning("Data collector is already running")
            return
        
        logger.info("Starting data collector...")
        
        # スケジュールの設定
        # 価格データ: 1秒ごと
        self.scheduler.add_job(
            self.collect_all_prices,
            'interval',
            seconds=1,
            id='price_collection',
            max_instances=1
        )
        
        # オーダーブック: 10秒ごと
        self.scheduler.add_job(
            self.collect_orderbooks_periodically,
            'interval',
            seconds=10,
            id='orderbook_collection',
            max_instances=1
        )
        
        self.scheduler.start()
        self.running = True
        logger.info("Data collector started")
    
    def stop(self):
        """データ収集を停止"""
        if not self.running:
            logger.warning("Data collector is not running")
            return
        
        logger.info("Stopping data collector...")
        self.scheduler.shutdown(wait=True)
        self.running = False
        logger.info("Data collector stopped")
    
    async def run_forever(self):
        """永続的に実行"""
        await self.initialize()
        self.start()
        
        try:
            # 無限ループで実行を継続
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()
            db.close()


async def main():
    """メイン関数"""
    collector = DataCollector()
    await collector.run_forever()


if __name__ == "__main__":
    # ログ設定
    logger.add(
        "logs/data_collector_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    # 実行
    asyncio.run(main())