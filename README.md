# Crypto Arbitrage System

日本の仮想通貨取引所間のアービトラージ機会を検出・分析するシステム

## 🚀 クイックスタート（3ステップ）

```bash
# 1. データ収集を開始（必須・バックグラウンド推奨）
nohup python src/main.py collect > logs/collector.log 2>&1 &

# 2. アービトラージ監視を開始（メイン機能）
python scripts/production/monitor_advanced_arbitrage.py

# 3. Discord通知を確認（自動送信されます）
```

詳細は [📚 QUICKSTART.md](QUICKSTART.md) を参照

## 概要

このシステムは、複数の仮想通貨取引所（bitFlyer、bitbank、Coincheck、GMOコイン、Bybit、Binance）から価格データをリアルタイムで収集し、取引所間の価格差を利用したアービトラージ機会を自動検出します。

## 主な機能

- **リアルタイム価格監視**: 5秒ごとに最新価格を取得
- **マルチ取引所対応**: 国内4取引所 + 海外2取引所（Bybit、Binance）
- **高度なアービトラージ検出**: 直接・クロスレート・USD建て・三角裁定に対応
- **Discord通知機能**: アービトラージ機会をDiscordで即座にiPhoneに通知
- **Webダッシュボード**: リアルタイムで価格差と機会を可視化
- **データベース記録**: PostgreSQLで全データを保存・分析
- **為替レート自動変換**: USDT建て価格を自動的にJPY換算

## 対応取引所

### 国内取引所

| 取引所 | Maker手数料 | Taker手数料 | 送金手数料 | 特徴 | API対応 |
|--------|------------|------------|-----------|------|--------|
| bitFlyer | 0.15% | 0.15% | BTC: 0.0004 | 国内最大級の取引量 | ✅ |
| bitbank | -0.02% | 0.12% | BTC: 0.0006 | Maker手数料がマイナス | ✅ |
| Coincheck | 0% | 0% | BTC: 0.0005 | 取引手数料無料 | ✅ |
| GMOコイン | -0.01% | 0.04% | **無料** | 送金手数料無料 | ✅ |

### 海外取引所

| 取引所 | Maker手数料 | Taker手数料 | 特徴 | 通貨ペア |
|--------|------------|------------|------|---------|
| Bybit | 0.1% | 0.1% | USDT建て、高流動性 | BTC/USDT等 |
| Binance | 0.1% | 0.1% | JPY建て直接取引可能 | BTC/JPY、BTC/USDT等 |

## システム構成

```
Crypt/
├── src/                         # コアアプリケーション
│   ├── main.py                 # メインエントリポイント
│   ├── collectors/             # 取引所APIクライアント
│   │   ├── base.py            # 基底クラス
│   │   ├── bitflyer.py        # bitFlyer
│   │   ├── bitbank.py         # bitbank
│   │   ├── coincheck.py       # Coincheck
│   │   ├── gmo.py             # GMOコイン
│   │   ├── bybit.py           # Bybit（国際取引所）
│   │   ├── binance.py         # Binance（国際取引所）
│   │   └── data_collector.py  # 統合コレクター
│   ├── analyzers/              # アービトラージ分析エンジン
│   │   ├── arbitrage_detector.py    # 基本的な検出
│   │   └── advanced_arbitrage.py    # 高度な分析（三角裁定等）
│   ├── notifications/          # 通知システム
│   │   ├── discord_notify.py  # Discord通知
│   │   ├── line_notify.py     # LINE通知
│   │   ├── config.py          # 通知設定
│   │   └── manager.py         # 通知マネージャー
│   ├── database/               # データベース関連
│   │   ├── connection.py      # DB接続
│   │   └── models.py          # データモデル
│   └── dashboard/              # Webダッシュボード
│       └── app.py             # Streamlitアプリ
├── scripts/                    # 運用・管理スクリプト
│   ├── monitor_advanced_arbitrage.py  # 本番監視（推奨）
│   ├── check_arbitrage.py            # 状況確認
│   ├── manage_notifications.py       # 通知管理
│   └── その他...                    # セットアップ・テスト用
├── config/                     # 設定ファイル
│   ├── database.yaml          # DB設定
│   ├── exchanges.yaml         # 取引所設定
│   └── notifications.json     # 通知設定
├── docs/                       # ドキュメント
├── logs/                       # ログファイル
├── analysis/                   # 分析ノートブック
└── requirements.txt            # 依存パッケージ
```

## セットアップ

### 1. 環境準備

```bash
# リポジトリのクローン
git clone https://github.com/telesuhr/Crypt-Arbitrage.git
cd Crypt-Arbitrage

# Python仮想環境の作成
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 2. データベース設定

```bash
# PostgreSQLデータベースの作成
createdb crypto_arbitrage

# テーブルの作成
psql -d crypto_arbitrage -f scripts/setup_database.sql

# または自動セットアップ
python src/main.py setup-db
```

### 3. API設定

`.env`ファイルを作成し、各取引所のAPIキーとLINE通知設定を行う：

```bash
cp .env.example .env
# .envファイルを編集してAPIキーを設定
```

#### Discord通知の設定（推奨）

**🚀 自動セットアップ（初心者向け）:**
```bash
# 対話式セットアップガイド実行
python scripts/setup_discord.py
```

**📖 詳細ガイド:**
Discordが初めての方は [Discord設定ガイド](docs/discord_setup_guide.md) をご覧ください。

**⚡ 手動設定（上級者向け）:**
1. Discordサーバーでウェブフックを作成
2. `.env`ファイルに`DISCORD_WEBHOOK_URL`を設定
3. 通知設定を確認・変更

```bash
# Discord通知設定の確認
python scripts/manage_notifications.py --show

# 通知テスト
python scripts/test_discord_notify.py
```

### 4. 接続テスト

```bash
python src/main.py test-connection
```

## 使用方法

### 🚀 クイックスタート（推奨）

3つのターミナルで以下を実行:

```bash
# ターミナル1: 価格データ収集
python src/main.py collect

# ターミナル2: 高度なアービトラージ監視（リッチUI付き）
python scripts/monitor_advanced_arbitrage.py

# ターミナル3: Webダッシュボード
python src/main.py dashboard
# ブラウザで http://localhost:8501 にアクセス
```

### 📊 個別機能の使用

#### データ収集

```bash
# 価格データ収集を開始
python src/main.py collect
```

#### アービトラージ分析

```bash
# 基本的なアービトラージ検出（バックグラウンド用）
python src/main.py analyze

# 高度なリアルタイム監視（推奨）
python scripts/monitor_advanced_arbitrage.py

# 現在の状況を一回だけ確認
python scripts/check_arbitrage.py
```

#### ダッシュボード

```bash
# Webダッシュボード起動
python src/main.py dashboard
# ブラウザで http://localhost:8501 にアクセス
```

#### 分析・レポート

```bash
# Jupyter Notebookでの詳細分析
jupyter notebook analysis/arbitrage_analysis.ipynb
```

## コマンド一覧

| コマンド | 説明 |
|---------|------|
| `setup-db` | データベースのセットアップ |
| `test-connection` | 接続テスト |
| `collect` | 価格データ収集開始 |
| `analyze` | アービトラージ分析開始 |
| `dashboard` | Webダッシュボード起動 |
| `test-ticker <exchange> <symbol>` | 特定取引所の価格取得テスト |

### 運用スクリプト

#### 📈 監視・分析

| スクリプト | 説明 | 使用場面 |
|-----------|------|----------|
| `scripts/monitor_advanced_arbitrage.py` | **高度なアービトラージ監視（推奨）** | 本番運用での常時監視 |
| `scripts/check_arbitrage.py` | 現在のアービトラージ機会を確認 | スポット確認 |
| `scripts/readonly_monitor.py` | 読み取り専用監視 | 別PC/タブレットからの監視 |
| `analysis/arbitrage_analysis.ipynb` | Jupyter Notebookでの詳細分析 | 履歴データ分析 |

#### ⚙️ 設定・管理

| スクリプト | 説明 | 使用場面 |
|-----------|------|----------|
| `scripts/manage_notifications.py` | 通知設定の管理 | 通知条件の調整 |
| `scripts/manage_tasks.py` | タスク管理 | 定期実行タスクの設定 |
| `scripts/add_currency_pair.py` | 通貨ペアの追加 | 新規通貨ペア監視 |
| `scripts/enable_all_pairs.py` | 全通貨ペアの有効化 | 一括設定 |
| `scripts/add_bybit_exchange.py` | Bybit取引所の追加 | 取引所拡張 |

#### 🧪 テスト・検証（初回セットアップ時）

| スクリプト | 説明 | 使用場面 |
|-----------|------|----------|
| `scripts/test_discord_notify.py` | Discord通知のテスト | 初期設定確認 |
| `scripts/test_postgresql_connection.py` | DB接続テスト | DB設定確認 |
| `scripts/test_binance_connection.py` | Binance API接続テスト | API設定確認 |
| `scripts/setup_discord.py` | Discord初期設定 | 初回のみ |

## Discord通知機能

### 通知設定の管理

```bash
# 現在の設定を確認
python scripts/manage_notifications.py --show

# 通知を有効化
python scripts/manage_notifications.py --enable

# 利益率閾値を0.1%に設定
python scripts/manage_notifications.py --threshold 0.1

# 利益額閾値を2000円に設定
python scripts/manage_notifications.py --amount 2000

# 静寂時間を設定（23:00-07:00）
python scripts/manage_notifications.py --quiet 23:00 07:00

# テスト通知を送信
python scripts/manage_notifications.py --test
```

### 通知条件

- **利益率閾値**: デフォルト0.05%以上
- **利益額閾値**: デフォルト1000円以上
- **クールダウン**: 同一ペアに5分間の制限
- **1時間制限**: 最大20件まで
- **静寂時間**: 設定可能（デフォルト無効）

### 通知内容

- アービトラージ機会の詳細（リッチ埋め込み形式）
- 予想利益率・利益額
- 取引所と価格情報
- 通貨ペア
- 検出時刻
- 利益率に応じたカラーコーディング

### iPhone通知設定

1. Discord iPhoneアプリをインストール
2. 設定 → 通知 → プッシュ通知を有効化
3. サーバー通知設定で該当チャンネルを有効化
4. 即座にアービトラージ機会をiPhoneで受信可能

## アーキテクチャ

### データフロー

1. **データ収集層**
   - 各取引所のWebSocket/REST APIから価格データを取得
   - 5秒間隔でポーリング（API制限を考慮）

2. **データ処理層**
   - 価格データの正規化
   - PostgreSQLへの保存
   - リアルタイム分析

3. **分析層**
   - 取引所間の価格差計算
   - 手数料を考慮した収益性評価
   - アービトラージ機会の検出

4. **通知層**
   - Discord Webhook APIによる即座の通知
   - 頻度制限とクールダウン管理
   - 通知履歴管理
   - iPhoneプッシュ通知対応

5. **可視化層**
   - Streamlitベースのダッシュボード
   - リアルタイムチャート
   - 機会アラート

### データベース構造

- `exchanges`: 取引所マスター
- `currency_pairs`: 通貨ペア情報
- `price_ticks`: 価格ティックデータ（パーティション化）
- `orderbook_snapshots`: オーダーブック履歴
- `arbitrage_opportunities`: 検出されたアービトラージ機会
- `balances`: 残高履歴

## 技術スタック

- **言語**: Python 3.9+
- **非同期処理**: asyncio, aiohttp
- **データベース**: PostgreSQL 13+
- **Web Framework**: Streamlit
- **データ分析**: pandas, numpy
- **可視化**: Plotly
- **APIクライアント**: 各取引所専用実装 + ccxt

## セキュリティ

- APIキーは環境変数で管理（.envファイル）
- .gitignoreでAPIキーを含むファイルを除外
- 最小権限の原則（読み取り専用APIを推奨）

## 注意事項

- 本システムは教育・研究目的で作成されています
- 実際の取引を行う場合は、各取引所の利用規約を確認してください
- アービトラージ取引にはリスクが伴います
- 価格変動、送金遅延、システム障害などのリスクを十分に理解してください

## 今後の開発予定

- [ ] 自動取引機能の実装
- [ ] より詳細なリスク管理機能
- [ ] バックテスト機能
- [ ] 機械学習による価格予測
- [ ] モバイルアプリ対応
- [ ] 海外取引所（Binance等）の追加

## コントリビューション

プルリクエストを歓迎します。大きな変更の場合は、まずイシューを作成して変更内容を議論してください。

## ライセンス

MIT License

## メンテナンス

### プロジェクトの整理

スクリプトファイルを用途別に整理するには：

```bash
# スクリプトの自動整理
bash scripts/organize_scripts.sh
```

これにより、スクリプトが以下のように整理されます：
- `scripts/production/` - 本番運用スクリプト
- `scripts/test/` - テスト・検証スクリプト  
- `scripts/setup/` - 初期設定スクリプト
- `scripts/archive/` - 非推奨スクリプト

### ログファイルの管理

```bash
# 7日以上古いログを削除
find logs/ -name "*.log" -mtime +7 -delete

# ログサイズの確認
du -sh logs/
```

## 作者

[@telesuhr](https://github.com/telesuhr)

## 謝辞

このプロジェクトは以下のオープンソースプロジェクトを使用しています：
- pandas, numpy - データ処理
- Streamlit - ダッシュボード
- PostgreSQL - データベース
- その他多数の素晴らしいPythonライブラリ