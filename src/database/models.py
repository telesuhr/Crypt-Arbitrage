from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Exchange(Base):
    """取引所マスター"""
    __tablename__ = 'exchanges'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    country = Column(String(50))
    api_base_url = Column(String(255))
    ws_url = Column(String(255))
    maker_fee = Column(DECIMAL(6, 4))
    taker_fee = Column(DECIMAL(6, 4))
    withdrawal_fees = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CurrencyPair(Base):
    """通貨ペアマスター"""
    __tablename__ = 'currency_pairs'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    base_currency = Column(String(10), nullable=False)
    quote_currency = Column(String(10), nullable=False)
    min_order_size = Column(DECIMAL(20, 8))
    size_increment = Column(DECIMAL(20, 8))
    price_increment = Column(DECIMAL(20, 8))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_currency_pairs_symbol', 'symbol'),
    )


class PriceTick(Base):
    """価格ティックデータ"""
    __tablename__ = 'price_ticks'
    
    exchange_id = Column(Integer, ForeignKey('exchanges.id'), primary_key=True)
    pair_id = Column(Integer, ForeignKey('currency_pairs.id'), primary_key=True)
    timestamp = Column(DateTime(timezone=True), primary_key=True)
    bid = Column(DECIMAL(20, 8))
    ask = Column(DECIMAL(20, 8))
    bid_size = Column(DECIMAL(20, 8))
    ask_size = Column(DECIMAL(20, 8))
    last_price = Column(DECIMAL(20, 8))
    volume_24h = Column(DECIMAL(20, 8))
    
    exchange = relationship("Exchange")
    pair = relationship("CurrencyPair")
    
    __table_args__ = (
        Index('idx_price_ticks_composite', 'exchange_id', 'pair_id', 'timestamp'),
    )


class OrderbookSnapshot(Base):
    """オーダーブックスナップショット"""
    __tablename__ = 'orderbook_snapshots'
    
    id = Column(Integer, primary_key=True)
    exchange_id = Column(Integer, ForeignKey('exchanges.id'), nullable=False)
    pair_id = Column(Integer, ForeignKey('currency_pairs.id'), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    bids = Column(JSON, nullable=False)
    asks = Column(JSON, nullable=False)
    depth = Column(Integer, default=20)
    
    exchange = relationship("Exchange")
    pair = relationship("CurrencyPair")
    
    __table_args__ = (
        Index('idx_orderbook_timestamp', 'timestamp'),
        Index('idx_orderbook_exchange_pair', 'exchange_id', 'pair_id'),
    )


class ArbitrageOpportunity(Base):
    """アービトラージ機会"""
    __tablename__ = 'arbitrage_opportunities'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    buy_exchange_id = Column(Integer, ForeignKey('exchanges.id'), nullable=False)
    sell_exchange_id = Column(Integer, ForeignKey('exchanges.id'), nullable=False)
    pair_id = Column(Integer, ForeignKey('currency_pairs.id'), nullable=False)
    buy_price = Column(DECIMAL(20, 8), nullable=False)
    sell_price = Column(DECIMAL(20, 8), nullable=False)
    price_diff_pct = Column(DECIMAL(6, 4), nullable=False)
    estimated_profit_pct = Column(DECIMAL(6, 4))
    max_profitable_volume = Column(DECIMAL(20, 8))
    buy_fees = Column(DECIMAL(20, 8))
    sell_fees = Column(DECIMAL(20, 8))
    transfer_fee = Column(DECIMAL(20, 8))
    total_fees_pct = Column(DECIMAL(6, 4))
    status = Column(String(20), default='detected')
    skip_reason = Column(String(100))
    execution_details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    buy_exchange = relationship("Exchange", foreign_keys=[buy_exchange_id])
    sell_exchange = relationship("Exchange", foreign_keys=[sell_exchange_id])
    pair = relationship("CurrencyPair")
    
    __table_args__ = (
        Index('idx_arb_timestamp', 'timestamp'),
        Index('idx_arb_profit', 'estimated_profit_pct'),
        Index('idx_arb_status', 'status'),
        Index('idx_arb_exchanges', 'buy_exchange_id', 'sell_exchange_id'),
    )


class Balance(Base):
    """残高管理"""
    __tablename__ = 'balances'
    
    exchange_id = Column(Integer, ForeignKey('exchanges.id'), primary_key=True)
    currency = Column(String(10), primary_key=True)
    timestamp = Column(DateTime(timezone=True), primary_key=True)
    available = Column(DECIMAL(20, 8), nullable=False)
    locked = Column(DECIMAL(20, 8), default=0)
    
    exchange = relationship("Exchange")
    
    __table_args__ = (
        Index('idx_balances_latest', 'exchange_id', 'currency', 'timestamp'),
    )
    
    @property
    def total(self) -> Decimal:
        return self.available + self.locked


# データベース操作のヘルパー関数
def get_or_create_exchange(session, code: str) -> Optional[Exchange]:
    """取引所を取得または作成"""
    exchange = session.query(Exchange).filter_by(code=code).first()
    return exchange


def get_or_create_pair(session, symbol: str) -> Optional[CurrencyPair]:
    """通貨ペアを取得または作成"""
    pair = session.query(CurrencyPair).filter_by(symbol=symbol).first()
    if not pair:
        parts = symbol.split('/')
        if len(parts) == 2:
            pair = CurrencyPair(
                symbol=symbol,
                base_currency=parts[0],
                quote_currency=parts[1]
            )
            session.add(pair)
            session.commit()
    return pair


def save_price_tick(session, exchange_code: str, symbol: str, price_data: Dict[str, Any]):
    """価格データを保存"""
    exchange = get_or_create_exchange(session, exchange_code)
    pair = get_or_create_pair(session, symbol)
    
    if exchange and pair:
        tick = PriceTick(
            exchange_id=exchange.id,
            pair_id=pair.id,
            timestamp=price_data['timestamp'],
            bid=Decimal(str(price_data['bid'])),
            ask=Decimal(str(price_data['ask'])),
            bid_size=Decimal(str(price_data['bid_size'])),
            ask_size=Decimal(str(price_data['ask_size'])),
            last_price=Decimal(str(price_data.get('last_price', 0))),
            volume_24h=Decimal(str(price_data.get('volume_24h', 0)))
        )
        session.add(tick)
        session.commit()