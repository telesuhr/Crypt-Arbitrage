"""
高度なアービトラージ分析器
JPY建て、USD建て、クロスレート、三角アービトラージなど複数の戦略を実装
"""

from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from loguru import logger

from ..database.connection import db
from ..database.models import PriceTick, Exchange, CurrencyPair
from ..notifications.manager import notification_manager


class AdvancedArbitrageAnalyzer:
    """高度なアービトラージ機会を分析"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # 閾値設定
        self.min_profit_threshold = Decimal(str(self.config.get('min_profit_threshold', 0.003)))  # 0.3%
        self.cross_rate_threshold = Decimal('0.001')  # クロスレート用の低い閾値 0.1%
        self.triangle_threshold = Decimal('0.002')  # 三角アービトラージ用 0.2%
        
        # 手数料設定（取引所別）
        self.exchange_fees = {
            'bitflyer': Decimal('0.0015'),    # 0.15%
            'bitbank': Decimal('0.0012'),     # 0.12%
            'coincheck': Decimal('0.0015'),   # 0.15%
            'gmo': Decimal('0.0005'),         # 0.05%
            'bybit': Decimal('0.001'),        # 0.1%
            'binance': Decimal('0.001'),      # 0.1%
        }
        
        # 分析履歴（重複通知防止）
        self.notified_opportunities = {}
        self.notification_cooldown = timedelta(minutes=5)
    
    async def analyze_all_opportunities(self) -> List[Dict[str, Any]]:
        """全種類のアービトラージ機会を分析"""
        opportunities = []
        
        # 1. 従来の直接アービトラージ（同一通貨ペア）
        direct_ops = await self.analyze_direct_arbitrage()
        opportunities.extend(direct_ops)
        
        # 2. クロスレートアービトラージ（JPY建て vs USDT経由）
        cross_rate_ops = await self.analyze_cross_rate_arbitrage()
        opportunities.extend(cross_rate_ops)
        
        # 3. USD建て比較（海外取引所間）
        usd_ops = await self.analyze_usd_arbitrage()
        opportunities.extend(usd_ops)
        
        # 4. 三角アービトラージ（3通貨間）
        triangle_ops = await self.analyze_triangle_arbitrage()
        opportunities.extend(triangle_ops)
        
        # 5. 時間差アービトラージ（市場の反応速度差）
        latency_ops = await self.analyze_latency_arbitrage()
        opportunities.extend(latency_ops)
        
        # 利益率でソート
        opportunities.sort(key=lambda x: x.get('profit_percentage', 0), reverse=True)
        
        # 通知処理
        await self._notify_opportunities(opportunities)
        
        return opportunities
    
    async def analyze_direct_arbitrage(self) -> List[Dict[str, Any]]:
        """従来の直接アービトラージ分析"""
        opportunities = []
        
        with db.get_session() as session:
            # 最新の価格データを取得（5分以内）
            recent_time = datetime.now(pytz.UTC) - timedelta(minutes=5)
            
            query = session.query(
                PriceTick,
                Exchange.code.label('exchange_code'),
                Exchange.name.label('exchange_name'),
                CurrencyPair.symbol.label('pair_symbol')
            ).join(
                Exchange, PriceTick.exchange_id == Exchange.id
            ).join(
                CurrencyPair, PriceTick.pair_id == CurrencyPair.id
            ).filter(
                PriceTick.timestamp >= recent_time
            ).order_by(
                PriceTick.timestamp.desc()
            )
            
            # 通貨ペアごとにグループ化（取引所ごとに最新データのみ保持）
            price_data = {}
            for tick, exchange_code, exchange_name, pair_symbol in query:
                if pair_symbol not in price_data:
                    price_data[pair_symbol] = {}
                
                # 各取引所の最新データのみを保持（古いデータは上書き）
                if exchange_code not in price_data[pair_symbol] or \
                   tick.timestamp > price_data[pair_symbol][exchange_code]['timestamp']:
                    price_data[pair_symbol][exchange_code] = {
                        'exchange_code': exchange_code,
                        'exchange_name': exchange_name,
                        'bid': tick.bid,
                        'ask': tick.ask,
                        'timestamp': tick.timestamp
                    }
            
            # 各通貨ペアでアービトラージ機会を検出
            for pair_symbol, exchanges_dict in price_data.items():
                if len(exchanges_dict) < 2:
                    continue
                
                # 取引所のリストを作成
                exchanges_list = list(exchanges_dict.values())
                
                # 全ての組み合わせをチェック
                for i in range(len(exchanges_list)):
                    for j in range(i + 1, len(exchanges_list)):
                        # 同じ取引所同士は比較しない
                        if exchanges_list[i]['exchange_code'] == exchanges_list[j]['exchange_code']:
                            continue
                            
                        opportunity = self._check_arbitrage_opportunity(
                            pair_symbol,
                            exchanges_list[i],
                            exchanges_list[j],
                            'direct'
                        )
                        
                        if opportunity:
                            opportunities.append(opportunity)
        
        return opportunities
    
    async def analyze_cross_rate_arbitrage(self) -> List[Dict[str, Any]]:
        """クロスレートアービトラージ分析（JPY直接 vs USDT経由）"""
        opportunities = []
        
        with db.get_session() as session:
            recent_time = datetime.now(pytz.UTC) - timedelta(minutes=5)
            
            # Binanceのデータを特別に処理
            binance_exchange = session.query(Exchange).filter_by(code='binance').first()
            if not binance_exchange:
                return opportunities
            
            # BTCを例に分析（他の通貨も同様に可能）
            currencies = ['BTC', 'ETH', 'XRP', 'LTC']
            
            for currency in currencies:
                # JPY建て価格を取得
                jpy_pair = session.query(CurrencyPair).filter_by(
                    symbol=f'{currency}/JPY'
                ).first()
                
                if not jpy_pair:
                    continue
                
                # 最新のJPY価格（複数取引所）
                jpy_prices = session.query(
                    PriceTick,
                    Exchange.code
                ).join(
                    Exchange
                ).filter(
                    PriceTick.pair_id == jpy_pair.id,
                    PriceTick.timestamp >= recent_time
                ).all()
                
                # USDT建て価格を取得
                usdt_pair = session.query(CurrencyPair).filter_by(
                    symbol=f'{currency}/USDT'
                ).first()
                
                if not usdt_pair:
                    continue
                
                usdt_prices = session.query(
                    PriceTick,
                    Exchange.code
                ).join(
                    Exchange
                ).filter(
                    PriceTick.pair_id == usdt_pair.id,
                    PriceTick.timestamp >= recent_time
                ).all()
                
                # クロスレート分析
                for jpy_tick, jpy_exchange in jpy_prices:
                    for usdt_tick, usdt_exchange in usdt_prices:
                        # 実際のクロスレート計算はPriceTickのメタデータに依存
                        # ここでは簡略化
                        opportunity = self._analyze_cross_rate(
                            currency,
                            jpy_tick,
                            jpy_exchange,
                            usdt_tick,
                            usdt_exchange
                        )
                        
                        if opportunity:
                            opportunities.append(opportunity)
        
        return opportunities
    
    async def analyze_usd_arbitrage(self) -> List[Dict[str, Any]]:
        """USD建てアービトラージ分析（海外取引所間）"""
        opportunities = []
        
        # Binance vs Bybitなど、USDT建ての価格差を分析
        with db.get_session() as session:
            recent_time = datetime.now(pytz.UTC) - timedelta(minutes=5)
            
            # USDT建てペアのみ
            usdt_pairs = session.query(CurrencyPair).filter(
                CurrencyPair.symbol.like('%/USDT')
            ).all()
            
            for pair in usdt_pairs:
                prices = session.query(
                    PriceTick,
                    Exchange.code,
                    Exchange.name
                ).join(
                    Exchange
                ).filter(
                    PriceTick.pair_id == pair.id,
                    PriceTick.timestamp >= recent_time,
                    Exchange.code.in_(['binance', 'bybit'])  # 海外取引所のみ
                ).all()
                
                if len(prices) >= 2:
                    # 各取引所の最新データのみを保持
                    latest_prices = {}
                    for tick, code, name in prices:
                        if code not in latest_prices or tick.timestamp > latest_prices[code][0].timestamp:
                            latest_prices[code] = (tick, code, name)
                    
                    # 異なる取引所間でのみ比較
                    price_list = list(latest_prices.values())
                    for i in range(len(price_list)):
                        for j in range(i + 1, len(price_list)):
                            tick1, code1, name1 = price_list[i]
                            tick2, code2, name2 = price_list[j]
                            
                            # 同じ取引所同士は比較しない
                            if code1 == code2:
                                continue
                            
                            opportunity = self._check_arbitrage_opportunity(
                                pair.symbol,
                                {
                                    'exchange_code': code1,
                                    'exchange_name': name1,
                                    'bid': tick1.bid,
                                    'ask': tick1.ask,
                                    'timestamp': tick1.timestamp
                                },
                                {
                                    'exchange_code': code2,
                                    'exchange_name': name2,
                                    'bid': tick2.bid,
                                    'ask': tick2.ask,
                                    'timestamp': tick2.timestamp
                                },
                                'usd'
                            )
                            
                            if opportunity:
                                opportunities.append(opportunity)
        
        return opportunities
    
    async def analyze_triangle_arbitrage(self) -> List[Dict[str, Any]]:
        """三角アービトラージ分析（例: BTC→ETH→USDT→BTC）"""
        opportunities = []
        
        # 実装予定：3つの通貨ペア間での循環取引機会を検出
        # 例: BTC/JPY → JPY/USD → USD/BTC のような循環
        
        return opportunities
    
    async def analyze_latency_arbitrage(self) -> List[Dict[str, Any]]:
        """時間差アービトラージ分析（価格反映の遅延を利用）"""
        opportunities = []
        
        # 実装予定：価格更新の遅い取引所を検出
        
        return opportunities
    
    def _check_arbitrage_opportunity(
        self,
        pair_symbol: str,
        exchange1: Dict,
        exchange2: Dict,
        arb_type: str = 'direct'
    ) -> Optional[Dict[str, Any]]:
        """2つの取引所間のアービトラージ機会をチェック"""
        
        # 買い取引所と売り取引所を決定
        if exchange1['ask'] < exchange2['bid']:
            buy_exchange = exchange1
            sell_exchange = exchange2
        elif exchange2['ask'] < exchange1['bid']:
            buy_exchange = exchange2
            sell_exchange = exchange1
        else:
            return None
        
        # 利益計算
        buy_price = buy_exchange['ask']
        sell_price = sell_exchange['bid']
        
        # 手数料を考慮
        buy_fee = self.exchange_fees.get(buy_exchange['exchange_code'], Decimal('0.002'))
        sell_fee = self.exchange_fees.get(sell_exchange['exchange_code'], Decimal('0.002'))
        
        # 実効価格（手数料込み）
        effective_buy_price = buy_price * (Decimal('1') + buy_fee)
        effective_sell_price = sell_price * (Decimal('1') - sell_fee)
        
        # 利益計算
        profit = effective_sell_price - effective_buy_price
        profit_percentage = (profit / effective_buy_price) * Decimal('100')
        
        # 閾値チェック
        threshold = self.min_profit_threshold
        if arb_type == 'cross_rate':
            threshold = self.cross_rate_threshold
        elif arb_type == 'triangle':
            threshold = self.triangle_threshold
        
        if profit_percentage < threshold * Decimal('100'):
            return None
        
        return {
            'type': arb_type,
            'pair': pair_symbol,
            'buy_exchange': buy_exchange['exchange_name'],
            'buy_exchange_code': buy_exchange['exchange_code'],
            'sell_exchange': sell_exchange['exchange_name'],
            'sell_exchange_code': sell_exchange['exchange_code'],
            'buy_price': float(buy_price),
            'sell_price': float(sell_price),
            'effective_buy_price': float(effective_buy_price),
            'effective_sell_price': float(effective_sell_price),
            'profit': float(profit),
            'profit_percentage': float(profit_percentage),
            'buy_fee_rate': float(buy_fee),
            'sell_fee_rate': float(sell_fee),
            'timestamp': datetime.now(pytz.UTC),
            'buy_timestamp': buy_exchange['timestamp'],
            'sell_timestamp': sell_exchange['timestamp']
        }
    
    def _analyze_cross_rate(
        self,
        currency: str,
        jpy_tick: Any,
        jpy_exchange: str,
        usdt_tick: Any,
        usdt_exchange: str
    ) -> Optional[Dict[str, Any]]:
        """クロスレートアービトラージの詳細分析"""
        # 実装予定：JPY直接価格とUSDT経由価格の比較
        # メタデータから為替レートを取得して計算
        
        return None
    
    async def _notify_opportunities(self, opportunities: List[Dict[str, Any]]):
        """検出した機会を通知"""
        for opp in opportunities:
            # 重複通知を防ぐ
            key = f"{opp['type']}_{opp['pair']}_{opp['buy_exchange_code']}_{opp['sell_exchange_code']}"
            
            now = datetime.now(pytz.UTC)
            if key in self.notified_opportunities:
                last_notified = self.notified_opportunities[key]
                if now - last_notified < self.notification_cooldown:
                    continue
            
            # 通知送信 - notification_managerを使用してしきい値チェック
            # profit_pctフィールドを追加（profit_percentageと同じ値）
            opp['profit_pct'] = opp['profit_percentage']
            
            # notification_managerが適切なしきい値チェックを行う
            if notification_manager.send_arbitrage_alert(opp):
                self.notified_opportunities[key] = now
                logger.info(f"Arbitrage opportunity notified: {opp['type']} {opp['pair']} "
                          f"{opp['profit_percentage']:.2f}%")


# グローバルインスタンス
advanced_analyzer = AdvancedArbitrageAnalyzer()