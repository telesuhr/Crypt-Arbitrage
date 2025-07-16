# TailScale + PostgreSQL 接続設定ガイド

## 正しい接続方法

### 1. IPアドレスを使用（あなたの設定）
```bash
DATABASE_URL=postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage
```

✅ **これで正しいです！**

### 2. より安定した接続のための推奨設定

#### オプション1: TailScaleのマシン名を使用
```bash
# TailScaleのマシン名を確認
tailscale status

# マシン名での接続（例）
DATABASE_URL=postgresql://postgres:password@your-machine-name:5432/crypto_arbitrage
```

#### オプション2: 接続パラメータの追加
```bash
# タイムアウトやSSL設定を追加
DATABASE_URL=postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage?connect_timeout=10&sslmode=prefer
```

## PostgreSQL側の設定確認

### 1. postgresql.conf の設定
```bash
# リモート接続を許可
listen_addresses = '*'  # または '100.94.216.39,localhost'
```

### 2. pg_hba.conf の設定
```bash
# TailScaleネットワークからの接続を許可
host    all             all             100.64.0.0/10        md5
# または特定のIPのみ
host    all             all             100.94.216.39/32     md5
```

### 3. PostgreSQLの再起動
```bash
# Mac
brew services restart postgresql@14

# Linux
sudo systemctl restart postgresql
```

## 接続テスト

### 1. psqlでの確認
```bash
# 監視端末から実行
psql postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage

# 接続成功したら
\dt  # テーブル一覧表示
\q   # 終了
```

### 2. Pythonスクリプトでの確認
```bash
# 監視端末で実行
python scripts/test_postgresql_connection.py
```

## トラブルシューティング

### 接続できない場合

1. **TailScaleの状態確認**
```bash
# 両端末で実行
tailscale status
ping 100.94.216.39
```

2. **PostgreSQLのログ確認**
```bash
# Mac
tail -f /usr/local/var/log/postgresql@14.log

# Linux
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

3. **ファイアウォール確認**
```bash
# Mac
sudo pfctl -s rules

# Linux
sudo ufw status
```

### よくある問題

#### "connection refused" エラー
- PostgreSQLが起動していない
- listen_addressesの設定ミス
- ポート5432がブロックされている

#### "authentication failed" エラー
- パスワードが間違っている
- pg_hba.confの設定ミス
- ユーザーが存在しない

#### "timeout" エラー
- ネットワークの問題
- TailScaleが切断されている
- PostgreSQLの負荷が高い

## セキュリティのベストプラクティス

1. **読み取り専用ユーザーの作成**
```sql
-- PostgreSQLで実行
CREATE USER monitor_user WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE crypto_arbitrage TO monitor_user;
GRANT USAGE ON SCHEMA public TO monitor_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitor_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO monitor_user;
```

2. **監視端末での読み取り専用接続**
```bash
# .env ファイル
DATABASE_URL=postgresql://monitor_user:secure_password@100.94.216.39:5432/crypto_arbitrage
```

3. **SSL接続の有効化（推奨）**
```bash
DATABASE_URL=postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage?sslmode=require
```

## パフォーマンス最適化

1. **接続プーリング設定**
```python
# src/database/connection.py で既に設定済み
poolclass=NullPool  # 長時間接続対応
```

2. **接続数の監視**
```sql
-- 現在の接続数を確認
SELECT count(*) FROM pg_stat_activity;

-- 接続の詳細を確認
SELECT pid, usename, application_name, client_addr, state 
FROM pg_stat_activity 
WHERE datname = 'crypto_arbitrage';
```

## まとめ

あなたの設定 `DATABASE_URL=postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage` は**完全に正しい**です。

これで：
- ✅ TailScaleの安全なVPN接続
- ✅ PostgreSQLへの直接アクセス
- ✅ SQLiteファイル共有不要
- ✅ リアルタイムデータ同期

が実現できています！