# スクリプトディレクトリ構成

## 📁 production/ - 本番運用スクリプト
- `monitor_advanced_arbitrage.py` - 🌟 推奨：高度なアービトラージ監視（リッチUI）
- `check_arbitrage.py` - シンプルな価格差確認
- `manage_notifications.py` - 通知設定管理
- `check_all_pairs.py` - 通貨ペア状態確認

## 📁 test/ - テストスクリプト
- `test_binance_*.py` - Binance関連のテスト
- `test_bybit_*.py` - Bybit関連のテスト
- `test_discord_notify.py` - Discord通知テスト
- その他APIテスト

## 📁 setup/ - セットアップスクリプト
- `setup_database.sql` - DB初期設定
- `setup_postgresql.py` - PostgreSQL設定
- `add_*.py` - データ追加系
- `enable_*.py` - 機能有効化

## 📁 archive/ - アーカイブ（非推奨）
- 古いバージョンのスクリプト
- monitor_advanced_arbitrage.pyに統合されたスクリプト

## 🚀 使い方

```bash
# 本番監視を開始（推奨）
python scripts/production/monitor_advanced_arbitrage.py

# 価格差を確認
python scripts/production/check_arbitrage.py
```
