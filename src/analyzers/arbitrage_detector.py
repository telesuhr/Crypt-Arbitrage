import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import yaml
from pathlib import Path
from loguru import logger
from sqlalchemy import and_, func
import pytz

from ..database.connection import db
from ..database.models import (
    Exchange, CurrencyPair, PriceTick, ArbitrageOpportunity,
    OrderbookSnapshot, Balance
)


class ArbitrageDetector:
    """アービトラージ機会を検出するクラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "exchanges.yaml"
        
        with open(config_path, 'r') as f:
            self.exchanges_config = yaml.safe_load(f)['exchanges']
        
        # システム設定をロード
        self.min_profit_threshold = Decimal("0.003")  # 0.3%
        self.max_position_sizes = {
            "BTC": Decimal("0.1"),
            "ETH": Decimal("1.0"),
            "XRP": Decimal("10000")
        }
        self.transfer_time_estimates = {
            "BTC": 30,  # minutes
            "ETH": 15,
            "XRP": 5
        }
        
        self._load_system_config()
    
    def _load_system_config(self):
        """データベースからシステム設定をロード"""
        try:
            with db.get_session() as session:
                from sqlalchemy import text
                result = session.execute(
                    text("SELECT key, value FROM system_config")
                ).fetchall()
                
                for row in result:
                    if row['key'] == 'min_profit_threshold':
                        self.min_profit_threshold = Decimal(str(row['value']['value']))
                    elif row['key'] == 'max_position_size':
                        self.max_position_sizes.update(row['value'])
                    elif row['key'] == 'transfer_time_estimates':
                        self.transfer_time_estimates.update(row['value'])
        except Exception as e:
            logger.warning(f"Failed to load system config: {e}, using defaults")
    
    def calculate_fees(self, exchange_code: str, side: str, amount: Decimal, price: Decimal) -> Decimal:
        """取引手数料を計算"""
        exchange_config = self.exchanges_config.get(exchange_code, {})
        
        if side == "buy":
            # 買い注文は通常taker
            fee_rate = Decimal(str(exchange_config.get('taker_fee', 0)))
        else:
            # 売り注文はmaker/takerどちらも可能だが、保守的にtakerで計算
            fee_rate = Decimal(str(exchange_config.get('taker_fee', 0)))
        
        return amount * price * fee_rate
    
    def calculate_transfer_fee(self, from_exchange: str, to_exchange: str, currency: str) -> Decimal:
        """送金手数料を計算"""
        from_config = self.exchanges_config.get(from_exchange, {})
        withdrawal_fees = from_config.get('withdrawal_fees', {})
        
        # 送金手数料を取得（デフォルトは0）
        fee = withdrawal_fees.get(currency, 0)
        return Decimal(str(fee))
    
    async def get_latest_prices(self, pair_symbol: str) -> Dict[str, Dict]:
        """指定通貨ペアの最新価格を全取引所から取得"""
        prices = {}
        
        with db.get_session() as session:
            # 通貨ペアIDを取得
            pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
            if not pair:
                return prices
            
            # 最新価格を取得（過去1分以内）
            jst = pytz.timezone('Asia/Tokyo')
            time_threshold = datetime.now(jst) - timedelta(minutes=1)
            
            # 各取引所の最新価格を取得
            subquery = session.query(
                PriceTick.exchange_id,
                func.max(PriceTick.timestamp).label('max_timestamp')
            ).filter(
                and_(
                    PriceTick.pair_id == pair.id,
                    PriceTick.timestamp > time_threshold
                )
            ).group_by(PriceTick.exchange_id).subquery()
            
            results = session.query(PriceTick, Exchange).join(
                subquery,
                and_(
                    PriceTick.exchange_id == subquery.c.exchange_id,
                    PriceTick.timestamp == subquery.c.max_timestamp
                )
            ).join(Exchange).filter(
                PriceTick.pair_id == pair.id
            ).all()
            
            for tick, exchange in results:
                prices[exchange.code] = {
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'bid_size': tick.bid_size,
                    'ask_size': tick.ask_size,
                    'timestamp': tick.timestamp
                }
        
        return prices
    
    async def get_orderbook_depth(self, exchange_code: str, pair_symbol: str, 
                                 side: str, volume: Decimal) -> Optional[Decimal]:
        """オーダーブックから指定ボリュームでの平均価格を計算"""
        with db.get_session() as session:
            # 取引所と通貨ペアのIDを取得
            exchange = session.query(Exchange).filter_by(code=exchange_code).first()
            pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
            
            if not exchange or not pair:
                return None
            
            # 最新のオーダーブックスナップショットを取得
            snapshot = session.query(OrderbookSnapshot).filter_by(
                exchange_id=exchange.id,
                pair_id=pair.id
            ).order_by(OrderbookSnapshot.timestamp.desc()).first()
            
            if not snapshot:
                return None
            
            # ボリューム加重平均価格を計算
            orders = snapshot.bids if side == 'sell' else snapshot.asks
            remaining_volume = volume
            total_cost = Decimal(0)
            
            for order in orders:
                price = Decimal(str(order['price']))
                size = Decimal(str(order['size']))
                
                if remaining_volume <= 0:
                    break
                
                fill_volume = min(remaining_volume, size)
                total_cost += fill_volume * price
                remaining_volume -= fill_volume
            
            if remaining_volume > 0:
                # 板が薄くて全量約定できない
                return None
            
            return total_cost / volume
    
    def detect_opportunities(self, prices: Dict[str, Dict], pair_symbol: str) -> List[Dict]:
        """価格データからアービトラージ機会を検出"""
        opportunities = []
        base_currency = pair_symbol.split('/')[0]
        
        # 全取引所の組み合わせをチェック
        exchanges = list(prices.keys())
        for i, buy_exchange in enumerate(exchanges):
            for sell_exchange in exchanges[i+1:]:
                # 買い価格と売り価格を取得
                buy_price = prices[buy_exchange].get('ask')  # 買うときはask価格
                sell_price = prices[sell_exchange].get('bid')  # 売るときはbid価格
                
                # 逆方向もチェック
                buy_price_rev = prices[sell_exchange].get('ask')
                sell_price_rev = prices[buy_exchange].get('bid')
                
                # 価格データの検証
                if not all([buy_price, sell_price, buy_price_rev, sell_price_rev]):
                    continue
                if any(p <= 0 for p in [buy_price, sell_price, buy_price_rev, sell_price_rev]):
                    continue
                
                # より利益の大きい方向を選択
                if sell_price > buy_price:
                    final_buy_exchange = buy_exchange
                    final_sell_exchange = sell_exchange
                    final_buy_price = buy_price
                    final_sell_price = sell_price
                    price_diff = sell_price - buy_price
                else:
                    final_buy_exchange = sell_exchange
                    final_sell_exchange = buy_exchange
                    final_buy_price = buy_price_rev
                    final_sell_price = sell_price_rev
                    price_diff = sell_price_rev - buy_price_rev
                
                # 価格差率を計算（ゼロ除算を防ぐ）
                if final_buy_price == 0 or final_buy_price is None:
                    continue
                price_diff_pct = (price_diff / final_buy_price) * Decimal(100)
                
                # 最小利益閾値をチェック
                if price_diff_pct < self.min_profit_threshold * Decimal(100):
                    continue
                
                # 最大取引可能量を計算（板の薄い方に合わせる）
                max_buy_size = prices[final_buy_exchange]['ask_size']
                max_sell_size = prices[final_sell_exchange]['bid_size']
                max_volume = min(max_buy_size, max_sell_size)
                
                # ポジションサイズ制限
                max_position = self.max_position_sizes.get(base_currency, Decimal("0.1"))
                max_volume = min(max_volume, max_position)
                
                # 手数料を計算
                buy_fees = self.calculate_fees(final_buy_exchange, "buy", max_volume, final_buy_price)
                sell_fees = self.calculate_fees(final_sell_exchange, "sell", max_volume, final_sell_price)
                transfer_fee = self.calculate_transfer_fee(final_buy_exchange, final_sell_exchange, base_currency)
                
                # 総手数料（比率）
                total_fees = buy_fees + sell_fees + transfer_fee
                
                # ゼロボリュームのチェック
                if max_volume == 0 or final_buy_price == 0:
                    continue
                    
                total_fees_pct = (total_fees / (max_volume * final_buy_price)) * Decimal(100)
                
                # 実質利益率
                estimated_profit_pct = price_diff_pct - total_fees_pct
                
                if estimated_profit_pct > 0:
                    opportunities.append({
                        'buy_exchange': final_buy_exchange,
                        'sell_exchange': final_sell_exchange,
                        'pair_symbol': pair_symbol,
                        'buy_price': final_buy_price,
                        'sell_price': final_sell_price,
                        'price_diff_pct': price_diff_pct,
                        'max_volume': max_volume,
                        'buy_fees': buy_fees,
                        'sell_fees': sell_fees,
                        'transfer_fee': transfer_fee,
                        'total_fees_pct': total_fees_pct,
                        'estimated_profit_pct': estimated_profit_pct,
                        'timestamp': datetime.utcnow()
                    })
        
        # 利益率の高い順にソート
        opportunities.sort(key=lambda x: x['estimated_profit_pct'], reverse=True)
        
        return opportunities
    
    async def save_opportunities(self, opportunities: List[Dict]):
        """検出したアービトラージ機会をデータベースに保存"""
        with db.get_session() as session:
            for opp in opportunities:
                # 取引所とペアのIDを取得
                buy_exchange = session.query(Exchange).filter_by(code=opp['buy_exchange']).first()
                sell_exchange = session.query(Exchange).filter_by(code=opp['sell_exchange']).first()
                pair = session.query(CurrencyPair).filter_by(symbol=opp['pair_symbol']).first()
                
                if not all([buy_exchange, sell_exchange, pair]):
                    continue
                
                # アービトラージ機会を保存
                arb_opp = ArbitrageOpportunity(
                    timestamp=opp['timestamp'],
                    buy_exchange_id=buy_exchange.id,
                    sell_exchange_id=sell_exchange.id,
                    pair_id=pair.id,
                    buy_price=opp['buy_price'],
                    sell_price=opp['sell_price'],
                    price_diff_pct=opp['price_diff_pct'],
                    estimated_profit_pct=opp['estimated_profit_pct'],
                    max_profitable_volume=opp['max_volume'],
                    buy_fees=opp['buy_fees'],
                    sell_fees=opp['sell_fees'],
                    transfer_fee=opp['transfer_fee'],
                    total_fees_pct=opp['total_fees_pct'],
                    status='detected'
                )
                
                session.add(arb_opp)
            
            session.commit()
            
            if opportunities:
                logger.info(f"Saved {len(opportunities)} arbitrage opportunities")
    
    async def analyze_single_pair(self, pair_symbol: str):
        """単一通貨ペアのアービトラージ分析"""
        try:
            # 最新価格を取得
            prices = await self.get_latest_prices(pair_symbol)
            
            if len(prices) < 2:
                logger.debug(f"Not enough price data for {pair_symbol}, found {len(prices)} exchanges")
                return
            
            logger.debug(f"Analyzing {pair_symbol} with price data from: {list(prices.keys())}")
            
            # アービトラージ機会を検出
            opportunities = self.detect_opportunities(prices, pair_symbol)
            
            # データベースに保存
            if opportunities:
                await self.save_opportunities(opportunities)
                
                # ログに出力
                for opp in opportunities[:3]:  # 上位3件のみ表示
                    logger.info(
                        f"Arbitrage opportunity: {opp['pair_symbol']} "
                        f"{opp['buy_exchange']}({opp['buy_price']}) -> "
                        f"{opp['sell_exchange']}({opp['sell_price']}) "
                        f"Profit: {opp['estimated_profit_pct']:.2f}%"
                    )
            else:
                logger.debug(f"No arbitrage opportunities found for {pair_symbol}")
                
        except Exception as e:
            import traceback
            logger.error(f"Error in analyze_single_pair for {pair_symbol}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def analyze_all_pairs(self):
        """全通貨ペアのアービトラージ分析"""
        # アクティブな通貨ペアを取得
        with db.get_session() as session:
            pairs = session.query(CurrencyPair).filter_by(is_active=True).all()
            pair_symbols = [pair.symbol for pair in pairs]
        
        # 並列で分析実行
        logger.info(f"Analyzing {len(pair_symbols)} pairs: {pair_symbols}")
        tasks = [self.analyze_single_pair(symbol) for symbol in pair_symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # エラーをログ出力
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error analyzing {pair_symbols[i]}: {result}")
    
    async def run_continuous_analysis(self, interval: int = 5):
        """継続的なアービトラージ分析"""
        logger.info(f"Starting continuous arbitrage analysis (interval: {interval}s)")
        
        while True:
            try:
                start_time = datetime.now()
                await self.analyze_all_pairs()
                
                # 処理時間を計算
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Analysis completed in {elapsed:.2f} seconds")
                
                # 次の実行まで待機
                wait_time = max(0, interval - elapsed)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(interval)


async def main(interval: int = 5):
    """メイン関数"""
    detector = ArbitrageDetector()
    await detector.run_continuous_analysis(interval)


if __name__ == "__main__":
    # ログ設定
    logger.add(
        "logs/arbitrage_detector_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    # 実行
    asyncio.run(main())