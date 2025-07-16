# Crypto Arbitrage System

日本の仮想通貨取引所間のアービトラージ機会を検出・分析するシステム

## 概要

このシステムは、複数の仮想通貨取引所（bitFlyer、bitbank、Coincheck、GMOコイン）から価格データをリアルタイムで収集し、取引所間の価格差を利用したアービトラージ機会を自動検出します。

## 主な機能

- **リアルタイム価格監視**: 1秒ごとに最新価格を取得
- **マルチ取引所対応**: 4つの主要国内取引所に対応
- **自動アービトラージ検出**: 手数料を考慮した収益性計算
- **Discord通知機能**: アービトラージ機会をDiscordで即座にiPhoneに通知
- **Webダッシュボード**: リアルタイムで価格差と機会を可視化
- **データベース記録**: PostgreSQLで全データを保存・分析

## 対応取引所

| 取引所 | Maker手数料 | Taker手数料 | 送金手数料 | 特徴 | API対応 |
|--------|------------|------------|-----------|------|--------|
| bitFlyer | 0.15% | 0.15% | BTC: 0.0004 | 国内最大級の取引量 | ✅ |
| bitbank | -0.02% | 0.12% | BTC: 0.0006 | Maker手数料がマイナス | ✅ |
| Coincheck | 0% | 0% | BTC: 0.0005 | 取引手数料無料 | ✅ |
| GMOコイン | -0.01% | 0.04% | **無料** | 送金手数料無料 | ✅ |
| SBI VCトレード | -0.01% | 0.05% | BTC: 0.0007 | SBIグループ運営 | ❌ |

**注意**: SBI VCトレードは現在公開APIを提供していないため、自動データ取得はできません。

## システム構成

```
crypto_arbitrage/
├── src/
│   ├── collectors/      # 取引所APIクライアント
│   │   ├── bitflyer.py
│   │   ├── bitbank.py
│   │   ├── coincheck.py
│   │   └── gmo.py
│   ├── analyzers/       # アービトラージ分析エンジン
│   │   └── arbitrage_detector.py
│   ├── notifications/   # LINE通知システム
│   │   ├── line_notify.py
│   │   ├── config.py
│   │   └── manager.py
│   ├── database/        # データベース関連
│   │   ├── connection.py
│   │   └── models.py
│   └── dashboard/       # Webダッシュボード
│       └── app.py
├── config/              # 設定ファイル
├── scripts/             # セットアップスクリプト
└── requirements.txt     # 依存パッケージ
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

### データ収集の開始

```bash
# ターミナル1: 価格データ収集
python src/main.py collect
```

### アービトラージ分析

```bash
# ターミナル2: アービトラージ検出
python src/main.py analyze
```

### リアルタイム監視

```bash
# ターミナルでのリアルタイム監視
python scripts/monitor_arbitrage.py

# 現在の状況を一回だけ確認
python scripts/check_arbitrage.py

# Jupyter Notebookでの詳細分析
jupyter notebook analysis/arbitrage_analysis.ipynb
```

### ダッシュボード起動

```bash
# ターミナル3: Webダッシュボード
python src/main.py dashboard
# ブラウザで http://localhost:8501 にアクセス
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

### 分析スクリプト

| スクリプト | 説明 |
|-----------|------|
| `scripts/check_arbitrage.py` | 現在のアービトラージ機会を確認 |
| `scripts/monitor_arbitrage.py` | リアルタイムアービトラージ監視 |
| `scripts/test_discord_notify.py` | Discord通知のテスト |
| `scripts/manage_notifications.py` | 通知設定の管理 |
| `analysis/arbitrage_analysis.ipynb` | Jupyter Notebookでの詳細分析 |

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

## 作者

[@telesuhr](https://github.com/telesuhr)

## 謝辞

このプロジェクトは以下のオープンソースプロジェクトを使用しています：
- pandas, numpy - データ処理
- Streamlit - ダッシュボード
- PostgreSQL - データベース
- その他多数の素晴らしいPythonライブラリ