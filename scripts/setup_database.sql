-- Crypto Arbitrage Database Setup
-- 仮想通貨アービトラージシステム用データベース

-- データベース作成
-- Note: このコマンドはpsqlで直接実行する必要があります
-- CREATE DATABASE crypto_arbitrage;

-- crypto_arbitrageデータベースに接続してから以下を実行
-- \c crypto_arbitrage

-- 拡張機能（必要に応じて）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. 取引所マスターテーブル
CREATE TABLE exchanges (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50),
    api_base_url VARCHAR(255),
    ws_url VARCHAR(255),
    maker_fee DECIMAL(6,4),
    taker_fee DECIMAL(6,4),
    withdrawal_fees JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 取引所の初期データ
INSERT INTO exchanges (code, name, country, api_base_url, ws_url, maker_fee, taker_fee, withdrawal_fees) VALUES
('bitflyer', 'bitFlyer', 'JP', 'https://api.bitflyer.com', 'wss://ws.lightstream.bitflyer.com', 0.0015, 0.0015, 
 '{"BTC": 0.0004, "ETH": 0.005, "XRP": 0, "JPY": 550}'::jsonb),
('bitbank', 'bitbank', 'JP', 'https://public.bitbank.cc', 'wss://stream.bitbank.cc', -0.0002, 0.0012, 
 '{"BTC": 0.0006, "ETH": 0.005, "XRP": 0.15, "JPY": 550}'::jsonb),
('coincheck', 'Coincheck', 'JP', 'https://coincheck.com', NULL, 0.0000, 0.0000, 
 '{"BTC": 0.0005, "ETH": 0.01, "XRP": 0.15, "JPY": 407}'::jsonb),
('gmo', 'GMOコイン', 'JP', 'https://api.coin.z.com', 'wss://api.coin.z.com/ws', -0.0001, 0.0004, 
 '{"BTC": 0, "ETH": 0, "XRP": 0, "JPY": 0}'::jsonb),
('binance', 'Binance', 'GLOBAL', 'https://api.binance.com', 'wss://stream.binance.com:9443', 0.0010, 0.0010, 
 '{"BTC": 0.0002, "ETH": 0.003, "USDT": 1}'::jsonb);

-- 2. 通貨ペアマスター
CREATE TABLE currency_pairs (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    base_currency VARCHAR(10) NOT NULL,
    quote_currency VARCHAR(10) NOT NULL,
    min_order_size DECIMAL(20,8),
    size_increment DECIMAL(20,8),
    price_increment DECIMAL(20,8),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_currency_pairs_symbol ON currency_pairs(symbol);

-- 主要通貨ペアの初期データ
INSERT INTO currency_pairs (symbol, base_currency, quote_currency, min_order_size, size_increment, price_increment) VALUES
('BTC/JPY', 'BTC', 'JPY', 0.001, 0.00000001, 1),
('ETH/JPY', 'ETH', 'JPY', 0.01, 0.00000001, 1),
('XRP/JPY', 'XRP', 'JPY', 1, 0.000001, 0.001),
('BTC/USDT', 'BTC', 'USDT', 0.00001, 0.00000001, 0.01),
('ETH/USDT', 'ETH', 'USDT', 0.0001, 0.00000001, 0.01);

-- 3. 価格ティックデータ（パーティション付き）
CREATE TABLE price_ticks (
    exchange_id INTEGER NOT NULL,
    pair_id INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    bid DECIMAL(20,8),
    ask DECIMAL(20,8),
    bid_size DECIMAL(20,8),
    ask_size DECIMAL(20,8),
    last_price DECIMAL(20,8),
    volume_24h DECIMAL(20,8),
    PRIMARY KEY (exchange_id, pair_id, timestamp),
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id),
    FOREIGN KEY (pair_id) REFERENCES currency_pairs(id)
) PARTITION BY RANGE (timestamp);

-- 2024年1月のパーティション作成
CREATE TABLE price_ticks_2024_01 PARTITION OF price_ticks
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- 2024年2月のパーティション作成
CREATE TABLE price_ticks_2024_02 PARTITION OF price_ticks
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- インデックス作成
CREATE INDEX idx_price_ticks_composite ON price_ticks(exchange_id, pair_id, timestamp DESC);

-- 4. オーダーブックスナップショット
CREATE TABLE orderbook_snapshots (
    id BIGSERIAL PRIMARY KEY,
    exchange_id INTEGER NOT NULL,
    pair_id INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    bids JSONB NOT NULL, -- [{price, size}, ...]
    asks JSONB NOT NULL, -- [{price, size}, ...]
    depth INTEGER DEFAULT 20,
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id),
    FOREIGN KEY (pair_id) REFERENCES currency_pairs(id)
);

CREATE INDEX idx_orderbook_timestamp ON orderbook_snapshots(timestamp);
CREATE INDEX idx_orderbook_exchange_pair ON orderbook_snapshots(exchange_id, pair_id);

-- 5. アービトラージ機会
CREATE TABLE arbitrage_opportunities (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    buy_exchange_id INTEGER NOT NULL,
    sell_exchange_id INTEGER NOT NULL,
    pair_id INTEGER NOT NULL,
    buy_price DECIMAL(20,8) NOT NULL,
    sell_price DECIMAL(20,8) NOT NULL,
    price_diff_pct DECIMAL(6,4) NOT NULL,
    estimated_profit_pct DECIMAL(6,4),
    max_profitable_volume DECIMAL(20,8),
    buy_fees DECIMAL(20,8),
    sell_fees DECIMAL(20,8),
    transfer_fee DECIMAL(20,8),
    total_fees_pct DECIMAL(6,4),
    status VARCHAR(20) DEFAULT 'detected', -- detected, executed, expired, skipped
    skip_reason VARCHAR(100),
    execution_details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buy_exchange_id) REFERENCES exchanges(id),
    FOREIGN KEY (sell_exchange_id) REFERENCES exchanges(id),
    FOREIGN KEY (pair_id) REFERENCES currency_pairs(id)
);

CREATE INDEX idx_arb_timestamp ON arbitrage_opportunities(timestamp);
CREATE INDEX idx_arb_profit ON arbitrage_opportunities(estimated_profit_pct);
CREATE INDEX idx_arb_status ON arbitrage_opportunities(status);
CREATE INDEX idx_arb_exchanges ON arbitrage_opportunities(buy_exchange_id, sell_exchange_id);

-- 6. 送金記録
CREATE TABLE transfers (
    id BIGSERIAL PRIMARY KEY,
    from_exchange_id INTEGER NOT NULL,
    to_exchange_id INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    fee DECIMAL(20,8),
    tx_hash VARCHAR(100),
    status VARCHAR(20) NOT NULL, -- pending, confirmed, failed
    initiated_at TIMESTAMP NOT NULL,
    confirmed_at TIMESTAMP,
    block_confirmations INTEGER,
    estimated_time_minutes INTEGER,
    actual_time_minutes INTEGER,
    notes TEXT,
    FOREIGN KEY (from_exchange_id) REFERENCES exchanges(id),
    FOREIGN KEY (to_exchange_id) REFERENCES exchanges(id)
);

CREATE INDEX idx_transfers_status ON transfers(status);
CREATE INDEX idx_transfers_currency ON transfers(currency);

-- 7. 取引実行履歴
CREATE TABLE trade_executions (
    id BIGSERIAL PRIMARY KEY,
    arbitrage_id BIGINT,
    exchange_id INTEGER NOT NULL,
    pair_id INTEGER NOT NULL,
    side VARCHAR(4) NOT NULL, -- buy, sell
    order_type VARCHAR(10) NOT NULL, -- market, limit
    requested_price DECIMAL(20,8),
    requested_size DECIMAL(20,8) NOT NULL,
    executed_price DECIMAL(20,8),
    executed_size DECIMAL(20,8),
    fee DECIMAL(20,8),
    fee_currency VARCHAR(10),
    status VARCHAR(20) NOT NULL, -- pending, filled, partial, cancelled, failed
    order_id VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,
    FOREIGN KEY (arbitrage_id) REFERENCES arbitrage_opportunities(id),
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id),
    FOREIGN KEY (pair_id) REFERENCES currency_pairs(id)
);

CREATE INDEX idx_trades_arbitrage ON trade_executions(arbitrage_id);
CREATE INDEX idx_trades_status ON trade_executions(status);
CREATE INDEX idx_trades_created ON trade_executions(created_at);

-- 8. 残高管理
CREATE TABLE balances (
    exchange_id INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    available DECIMAL(20,8) NOT NULL,
    locked DECIMAL(20,8) DEFAULT 0,
    total DECIMAL(20,8) GENERATED ALWAYS AS (available + locked) STORED,
    PRIMARY KEY (exchange_id, currency, timestamp),
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
);

CREATE INDEX idx_balances_latest ON balances(exchange_id, currency, timestamp DESC);

-- 9. システム設定
CREATE TABLE system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初期設定値
INSERT INTO system_config (key, value, description) VALUES
('min_profit_threshold', '{"value": 0.003}', '最小利益率（0.3%）'),
('max_position_size', '{"BTC": 0.1, "ETH": 1.0, "XRP": 10000}', '最大ポジションサイズ'),
('transfer_time_estimates', '{"BTC": 30, "ETH": 15, "XRP": 5}', '送金時間見積もり（分）'),
('price_update_interval', '{"seconds": 1}', '価格更新間隔'),
('orderbook_depth', '{"levels": 20}', 'オーダーブック取得深度'),
('api_rate_limits', '{"bitflyer": 500, "bitbank": 60, "binance": 1200}', 'API レート制限（リクエスト/分）');

-- 10. API認証情報（暗号化して保存すること）
CREATE TABLE api_credentials (
    id SERIAL PRIMARY KEY,
    exchange_id INTEGER NOT NULL,
    api_key VARCHAR(255),
    api_secret VARCHAR(255), -- 実際は暗号化して保存
    passphrase VARCHAR(255), -- 一部の取引所で必要
    permissions JSONB, -- ["read", "trade", "withdraw"]
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
);

-- ビューの作成

-- 最新価格ビュー
CREATE VIEW latest_prices AS
SELECT DISTINCT ON (e.code, cp.symbol)
    e.code as exchange_code,
    e.name as exchange_name,
    cp.symbol,
    cp.base_currency,
    cp.quote_currency,
    pt.bid,
    pt.ask,
    pt.last_price,
    pt.volume_24h,
    pt.timestamp
FROM price_ticks pt
JOIN exchanges e ON pt.exchange_id = e.id
JOIN currency_pairs cp ON pt.pair_id = cp.id
WHERE pt.timestamp > NOW() - INTERVAL '5 minutes'
ORDER BY e.code, cp.symbol, pt.timestamp DESC;

-- アービトラージサマリービュー
CREATE VIEW arbitrage_summary AS
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as opportunities_count,
    COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed_count,
    AVG(estimated_profit_pct) as avg_profit_pct,
    MAX(estimated_profit_pct) as max_profit_pct,
    SUM(CASE WHEN status = 'executed' THEN estimated_profit_pct * max_profitable_volume ELSE 0 END) as total_profit
FROM arbitrage_opportunities
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- 取引所別残高ビュー
CREATE VIEW current_balances AS
SELECT DISTINCT ON (e.code, b.currency)
    e.code as exchange_code,
    e.name as exchange_name,
    b.currency,
    b.available,
    b.locked,
    b.total,
    b.timestamp
FROM balances b
JOIN exchanges e ON b.exchange_id = e.id
ORDER BY e.code, b.currency, b.timestamp DESC;

-- パーティション自動作成関数
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    partition_name text;
BEGIN
    start_date := date_trunc('month', CURRENT_DATE);
    end_date := start_date + interval '1 month';
    partition_name := 'price_ticks_' || to_char(start_date, 'YYYY_MM');
    
    -- パーティションが存在しない場合のみ作成
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE tablename = partition_name
    ) THEN
        EXECUTE format('CREATE TABLE %I PARTITION OF price_ticks FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 更新日時自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_exchanges_updated_at BEFORE UPDATE ON exchanges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_api_credentials_updated_at BEFORE UPDATE ON api_credentials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- アクセス権限の設定（必要に応じて）
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO crypto_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO crypto_app_user;