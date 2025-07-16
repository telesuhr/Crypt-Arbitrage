# 複数端末での分散運用ガイド

## 概要

このシステムは複数端末で分散運用が可能です。データベースを共有することで、一台はデータ収集専用、もう一台は監視・分析専用といった運用ができます。

## アーキテクチャ

```
┌─────────────────┐     ┌─────────────────┐
│  データ収集端末   │     │  監視・分析端末   │
├─────────────────┤     ├─────────────────┤
│ ・API接続        │     │ ・モニタリング    │
│ ・価格データ取得  │     │ ・アービトラージ  │
│ ・DB書き込み     │     │   検出          │
└────────┬────────┘     │ ・通知送信      │
         │              └────────┬────────┘
         │                       │
         ▼                       ▼
    ┌─────────────────────────────────┐
    │        共有データベース           │
    │      (SQLite/PostgreSQL)        │
    └─────────────────────────────────┘
```

## 設定方法

### 方法1: ネットワーク共有（推奨）

#### 1. PostgreSQLサーバーのセットアップ

```bash
# PostgreSQLのインストール（サーバー機）
brew install postgresql@14  # Mac
# または
sudo apt install postgresql  # Ubuntu

# データベースの作成
createdb crypto_arbitrage

# リモート接続を許可
# /usr/local/var/postgres/postgresql.conf を編集
listen_addresses = '*'

# /usr/local/var/postgres/pg_hba.conf を編集
# 同一ネットワークからの接続を許可
host    all    all    192.168.1.0/24    md5
```

#### 2. .envファイルの設定

データ収集端末と監視端末の両方で同じデータベースを指定：

```env
# PostgreSQL接続の場合
DATABASE_URL=postgresql://user:password@192.168.1.100:5432/crypto_arbitrage

# その他の設定
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 方法2: ファイル共有（SQLite）

#### 1. 共有フォルダの設定

```bash
# Macの場合
# システム環境設定 → 共有 → ファイル共有を有効化
# 共有フォルダ: /Users/Shared/crypto_arbitrage

# データベースファイルを共有フォルダに配置
mkdir -p /Users/Shared/crypto_arbitrage
cp crypto_arbitrage.db /Users/Shared/crypto_arbitrage/
```

#### 2. .envファイルの設定

```env
# 共有SQLiteファイルを指定
DATABASE_URL=sqlite:////Users/Shared/crypto_arbitrage/crypto_arbitrage.db
```

## 端末別の役割分担

### データ収集端末（24時間稼働）

```bash
# データ収集のみ実行
python src/main.py collect

# または個別に起動
python scripts/start_collection.py
```

特徴：
- API接続とデータ取得に専念
- 低スペックでも動作可能（Raspberry Pi等）
- 安定した電源とネット接続が必要

### 監視・分析端末（必要時のみ）

```bash
# モニタリング実行
python scripts/monitor_all_pairs.py

# アービトラージ分析
python src/main.py analyze

# ダッシュボード
streamlit run src/dashboard/app.py
```

特徴：
- データの読み取りのみ
- 高い計算能力が有利
- 必要な時だけ起動可能

## 実装例

### 1. 読み取り専用モニター

`scripts/readonly_monitor.py`:

```python
#!/usr/bin/env python3
"""
読み取り専用のアービトラージモニター
データ収集は行わず、既存データの監視のみ実行
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from src.database.connection import db
from src.analyzers.arbitrage_detector import ArbitrageDetector
from scripts.monitor_all_pairs import MultiPairMonitor

class ReadOnlyMonitor(MultiPairMonitor):
    """読み取り専用モニター"""
    
    async def monitor_once(self):
        """DBから最新データを読み取って分析"""
        opportunities_by_pair = {}
        detector = ArbitrageDetector()
        
        with db.get_session() as session:
            # 各通貨ペアの最新価格をDBから取得
            pairs = session.query(CurrencyPair).filter_by(is_active=True).all()
            
            for pair in pairs:
                # DBから直接価格を取得（API呼び出しなし）
                prices = detector.get_latest_prices_from_db(pair.symbol)
                
                if len(prices) >= 2:
                    opportunities = detector.detect_opportunities(prices, pair.symbol)
                    if opportunities:
                        filtered = [
                            opp for opp in opportunities 
                            if opp['estimated_profit_pct'] >= self.min_profit_threshold
                        ]
                        if filtered:
                            opportunities_by_pair[pair.symbol] = filtered[0]
        
        return opportunities_by_pair

if __name__ == "__main__":
    monitor = ReadOnlyMonitor()
    asyncio.run(monitor.run())
```

### 2. PostgreSQL対応版のDB接続

`src/database/connection_pg.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os

class DatabaseConnection:
    def __init__(self):
        # PostgreSQL接続文字列
        self.database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://user:password@localhost:5432/crypto_arbitrage'
        )
        
        # 接続プール設定
        self.engine = create_engine(
            self.database_url,
            poolclass=NullPool,  # 長時間接続対応
            connect_args={
                "connect_timeout": 10,
                "application_name": "crypto_arbitrage"
            }
        )
```

## パフォーマンス最適化

### 1. インデックスの追加

```sql
-- 高速な価格検索のため
CREATE INDEX idx_price_tick_pair_timestamp 
ON price_ticks(pair_id, timestamp DESC);

-- アービトラージ機会の検索用
CREATE INDEX idx_arbitrage_timestamp 
ON arbitrage_opportunities(timestamp DESC);
```

### 2. 読み取り専用接続

監視端末では読み取り専用の接続を使用：

```python
# 読み取り専用セッション
read_only_engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-c default_transaction_read_only=on"}
)
```

## セキュリティ考慮事項

1. **ネットワークセキュリティ**
   - VPNまたはSSHトンネル経由での接続推奨
   - ファイアウォールで特定IPのみ許可

2. **認証情報の管理**
   - データ収集端末のみにAPIキーを保存
   - 監視端末には読み取り権限のみ付与

3. **バックアップ**
   - 定期的なデータベースバックアップ
   - 複数端末でのバックアップ冗長化

## トラブルシューティング

### 接続エラー

```bash
# PostgreSQL接続テスト
psql -h 192.168.1.100 -U user -d crypto_arbitrage

# SQLiteファイルロック解除
sqlite3 /path/to/database.db "PRAGMA journal_mode=WAL;"
```

### パフォーマンス問題

```bash
# PostgreSQLの場合
# 統計情報の更新
ANALYZE;

# バキューム実行
VACUUM ANALYZE;
```

## まとめ

複数端末での分散運用により：
- **信頼性向上**: 一台が停止しても他が継続
- **負荷分散**: 各端末の役割を最適化
- **柔軟性**: 必要に応じて端末追加可能

特に24時間データ収集と、必要時のみの監視を分離することで、効率的な運用が可能になります。