# Crypto Arbitrage System

日本の仮想通貨取引所間のアービトラージ機会を検出・分析するシステム

## 概要

このシステムは、複数の仮想通貨取引所（bitFlyer、bitbank、Coincheck、GMOコイン）から価格データをリアルタイムで収集し、取引所間の価格差を利用したアービトラージ機会を自動検出します。

## 主な機能

- **リアルタイム価格監視**: 1秒ごとに最新価格を取得
- **マルチ取引所対応**: 4つの主要国内取引所に対応
- **自動アービトラージ検出**: 手数料を考慮した収益性計算
- **Webダッシュボード**: リアルタイムで価格差と機会を可視化
- **データベース記録**: PostgreSQLで全データを保存・分析

## 対応取引所

| 取引所 | Maker手数料 | Taker手数料 | 送金手数料 | 特徴 |
|--------|------------|------------|-----------|------|
| bitFlyer | 0.15% | 0.15% | BTC: 0.0004 | 国内最大級の取引量 |
| bitbank | -0.02% | 0.12% | BTC: 0.0006 | Maker手数料がマイナス |
| Coincheck | 0% | 0% | BTC: 0.0005 | 取引手数料無料 |
| GMOコイン | -0.01% | 0.04% | **無料** | 送金手数料無料 |

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

`.env`ファイルを作成し、各取引所のAPIキーを設定：

```bash
cp .env.example .env
# .envファイルを編集してAPIキーを設定
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

4. **可視化層**
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