#!/bin/bash
# スクリプトファイルを整理するシェルスクリプト

echo "📁 スクリプトファイルを整理します..."

# ディレクトリ作成
mkdir -p scripts/production
mkdir -p scripts/test
mkdir -p scripts/setup
mkdir -p scripts/archive

# 本番用スクリプトを移動
echo "🚀 本番用スクリプトを整理..."
cp scripts/monitor_advanced_arbitrage.py scripts/production/ 2>/dev/null
cp scripts/check_arbitrage.py scripts/production/ 2>/dev/null
cp scripts/manage_notifications.py scripts/production/ 2>/dev/null
cp scripts/check_all_pairs.py scripts/production/ 2>/dev/null

# テストスクリプトを移動
echo "🧪 テストスクリプトを整理..."
cp scripts/test_*.py scripts/test/ 2>/dev/null

# セットアップスクリプトを移動
echo "🔧 セットアップスクリプトを整理..."
cp scripts/setup_*.py scripts/setup/ 2>/dev/null
cp scripts/add_*.py scripts/setup/ 2>/dev/null
cp scripts/enable_*.py scripts/setup/ 2>/dev/null
cp scripts/update_*.py scripts/setup/ 2>/dev/null

# アーカイブ（非推奨）スクリプトを移動
echo "📦 非推奨スクリプトをアーカイブ..."
cp scripts/monitor_arbitrage.py scripts/archive/ 2>/dev/null
cp scripts/monitor_all_pairs.py scripts/archive/ 2>/dev/null
cp scripts/readonly_monitor.py scripts/archive/ 2>/dev/null

# 使用ガイドを作成
cat > scripts/README.md << 'EOF'
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
EOF

echo "✅ 整理完了！"
echo ""
echo "📋 整理結果:"
echo "  - production/: $(ls scripts/production 2>/dev/null | wc -l) ファイル"
echo "  - test/: $(ls scripts/test 2>/dev/null | wc -l) ファイル"
echo "  - setup/: $(ls scripts/setup 2>/dev/null | wc -l) ファイル"
echo "  - archive/: $(ls scripts/archive 2>/dev/null | wc -l) ファイル"
echo ""
echo "💡 使用方法は scripts/README.md を参照してください"