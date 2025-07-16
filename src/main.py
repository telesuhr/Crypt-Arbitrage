#!/usr/bin/env python3
"""
Crypto Arbitrage System - メインエントリポイント
"""
import click
import asyncio
from loguru import logger
from pathlib import Path
import sys

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

# ログディレクトリの作成
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# ログ設定
logger.add(
    "logs/crypto_arbitrage_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO"
)


@click.group()
def cli():
    """Crypto Arbitrage System CLI"""
    pass


@cli.command()
def collect():
    """価格データ収集を開始"""
    from src.collectors.data_collector import main
    
    logger.info("Starting price data collection...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Data collection stopped by user")
    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        raise


@cli.command()
@click.option('--interval', default=5, help='分析間隔（秒）')
def analyze(interval):
    """アービトラージ分析を実行"""
    from src.analyzers.arbitrage_detector import main
    
    logger.info(f"Starting arbitrage analysis (interval: {interval}s)...")
    try:
        asyncio.run(main(interval))
    except KeyboardInterrupt:
        logger.info("Analysis stopped by user")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise


@cli.command()
def dashboard():
    """ダッシュボードを起動"""
    import subprocess
    
    logger.info("Starting dashboard...")
    try:
        subprocess.run(["streamlit", "run", "src/dashboard/app.py"])
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")
        raise


@cli.command()
def setup_db():
    """データベースをセットアップ"""
    import subprocess
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    db_name = os.getenv('DB_NAME', 'crypto_arbitrage')
    db_user = os.getenv('DB_USER', 'postgres')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    
    logger.info(f"Setting up database {db_name}...")
    
    try:
        # データベース作成
        subprocess.run([
            "createdb",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            db_name
        ], check=True)
        logger.info(f"Database {db_name} created")
    except subprocess.CalledProcessError:
        logger.warning(f"Database {db_name} might already exist")
    
    # SQLスクリプト実行
    sql_file = Path("scripts/setup_database.sql")
    if sql_file.exists():
        try:
            subprocess.run([
                "psql",
                "-h", db_host,
                "-p", db_port,
                "-U", db_user,
                "-d", db_name,
                "-f", str(sql_file)
            ], check=True)
            logger.info("Database tables created successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    else:
        logger.error(f"SQL file not found: {sql_file}")


@cli.command()
def test_connection():
    """接続テスト"""
    from src.database.connection import db
    
    logger.info("Testing database connection...")
    if db.test_connection():
        logger.info("✅ Database connection successful")
    else:
        logger.error("❌ Database connection failed")
        return
    
    logger.info("Testing exchange connections...")
    from src.collectors.data_collector import DataCollector
    
    async def test_exchanges():
        collector = DataCollector()
        await collector.initialize()
        
        for exchange_code in collector.exchanges:
            logger.info(f"✅ {exchange_code} initialized")
    
    asyncio.run(test_exchanges())
    logger.info("All connections tested successfully")


@cli.command()
@click.argument('exchange')
@click.argument('symbol')
def test_ticker(exchange, symbol):
    """指定した取引所・通貨ペアのティッカー情報を取得"""
    import yaml
    from pathlib import Path
    
    config_path = Path("config/exchanges.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if exchange not in config['exchanges']:
        logger.error(f"Unknown exchange: {exchange}")
        return
    
    exchange_config = config['exchanges'][exchange]
    
    async def get_ticker():
        if exchange == 'bitflyer':
            from src.collectors.bitflyer import BitFlyerClient
            client = BitFlyerClient(exchange_config)
        elif exchange == 'bitbank':
            from src.collectors.bitbank import BitbankClient
            client = BitbankClient(exchange_config)
        else:
            logger.error(f"Unsupported exchange: {exchange}")
            return
        
        async with client:
            ticker = await client.get_ticker(symbol)
            logger.info(f"Ticker data for {symbol} on {exchange}:")
            for key, value in ticker.items():
                logger.info(f"  {key}: {value}")
    
    asyncio.run(get_ticker())


if __name__ == "__main__":
    cli()