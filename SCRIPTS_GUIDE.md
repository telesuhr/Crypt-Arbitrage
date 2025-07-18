# 📚 スクリプト使用ガイド

## 🎯 実際に使うべきファイル（本番運用）

### 1️⃣ データ収集（必須・常時起動）
```bash
python src/main.py collect
```
または
```bash
python -m src.collectors.data_collector
```

### 2️⃣ アービトラージ監視（メイン機能）

#### 🌟 推奨：高度な監視
```bash
python scripts/production/monitor_advanced_arbitrage.py
# または整理前の場所
python scripts/monitor_advanced_arbitrage.py
```

**特徴:**
- リッチなUI（カラフルな表示）
- 複数種類のアービトラージ検出
- リアルタイム更新
- Discord自動通知

#### シンプル版
```bash
python scripts/production/check_arbitrage.py
# または整理前の場所
python scripts/check_arbitrage.py
```

### 3️⃣ Webダッシュボード（オプション）
```bash
python src/main.py dashboard
```
ブラウザで http://localhost:8501 にアクセス

## 📁 ファイル整理状況

### ✅ 本番で使うファイル
- `src/main.py` - メインプログラム
- `scripts/monitor_advanced_arbitrage.py` - 高度な監視（推奨）
- `scripts/check_arbitrage.py` - シンプルな価格差確認
- `scripts/manage_notifications.py` - 通知設定管理

### 📦 アーカイブ（使わない）
- `scripts/monitor_arbitrage.py` - 古いバージョン
- `scripts/monitor_all_pairs.py` - 機能が統合済み
- `scripts/readonly_monitor.py` - 読み取り専用版

### 🧪 テスト用
- `scripts/test_*.py` - 各種テストスクリプト

### 🔧 初期設定用
- `scripts/setup_*.py` - セットアップ用
- `scripts/add_*.py` - データ追加用

## 💡 運用のコツ

### tmuxを使った24時間運用
```bash
# データ収集用
tmux new -s collect
python src/main.py collect
# Ctrl+B, D でデタッチ

# 監視用
tmux new -s monitor
python scripts/monitor_advanced_arbitrage.py
# Ctrl+B, D でデタッチ

# 再接続
tmux attach -t collect
tmux attach -t monitor
```

### プロセス管理
```bash
# 起動確認
ps aux | grep python | grep -E "(collect|monitor)"

# 停止
pkill -f "main.py collect"
pkill -f "monitor_advanced_arbitrage"
```

### ログ確認
```bash
# データ収集ログ
tail -f logs/data_collector_*.log

# アービトラージ検出ログ
tail -f logs/advanced_arbitrage_*.log

# エラーのみ
tail -f logs/*.log | grep ERROR
```

## 🚨 トラブルシューティング

### データが表示されない
1. データ収集が起動しているか確認
2. 5分程度待ってデータが蓄積されるのを待つ
3. データベース接続を確認

### Discord通知が来ない
1. 利益率が0.3%以上あるか確認
2. 静音時間（0:00-9:00）でないか確認
3. Discord Webhook URLが正しいか確認

### エラーが出る
1. PostgreSQLが起動しているか確認
2. .envファイルの設定を確認
3. APIキーが有効か確認

## 📞 サポート

問題が解決しない場合は、以下の情報と共に報告してください：
- エラーメッセージ
- 実行したコマンド
- ログファイルの内容（最後の50行程度）