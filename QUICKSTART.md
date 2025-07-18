# 🚀 クイックスタートガイド

## 📋 基本的な使い方

### 1. データ収集を開始（必須）
```bash
# バックグラウンドで実行推奨
python src/main.py collect
# または
nohup python src/main.py collect > logs/collector.log 2>&1 &
```

### 2. アービトラージ監視を開始（メイン機能）
```bash
# 推奨：高度な監視（リッチUI、全機能対応）
python scripts/monitor_advanced_arbitrage.py

# シンプル版（軽量）
python scripts/check_arbitrage.py
```

### 3. Webダッシュボード（オプション）
```bash
# ブラウザで http://localhost:8501 にアクセス
python src/main.py dashboard
```

## 📱 Discord通知の確認

1. Discordアプリを開く
2. 作成したサーバーの通知チャンネルを確認
3. アービトラージ機会が検出されると自動通知

### 通知の見方
- 🟢 緑: 利益率 0.5%以上（高収益）
- 🟡 黄: 利益率 0.1%以上（要確認）
- ⚪ 白: 利益率 0.1%未満（参考）

## 🔧 便利なコマンド

### 現在の価格差を確認
```bash
python scripts/check_arbitrage.py --pair BTC/JPY
```

### 通知設定の変更
```bash
python scripts/manage_notifications.py
```

### データベースの状態確認
```bash
python scripts/check_all_pairs.py
```

## 💡 Tips

1. **24時間運用する場合**
   ```bash
   # tmuxまたはscreenを使用
   tmux new -s crypto
   python src/main.py collect
   # Ctrl+B, D でデタッチ
   
   tmux new -s monitor
   python scripts/monitor_advanced_arbitrage.py
   # Ctrl+B, D でデタッチ
   ```

2. **ログの確認**
   ```bash
   tail -f logs/data_collector_*.log
   tail -f logs/advanced_arbitrage_*.log
   ```

3. **プロセスの確認**
   ```bash
   ps aux | grep python | grep -E "(collect|monitor)"
   ```

## ⚠️ 注意事項

- データ収集を先に起動してから監視を開始
- 初回は5分程度データが蓄積されるまで待つ
- 深夜0時〜朝9時はDiscord通知が静音モード
- 手数料を考慮して実際の取引判断を行う

## 🆘 トラブルシューティング

### Q: 価格データが表示されない
A: データ収集が起動しているか確認
```bash
ps aux | grep "main.py collect"
```

### Q: Discord通知が来ない
A: 利益率が閾値（0.3%）以上か確認、または設定を確認
```bash
cat config/notifications.json
```

### Q: エラーが発生する
A: ログを確認
```bash
tail -100 logs/data_collector_*.log | grep ERROR
```