#!/usr/bin/env python3
"""
監視端末のセットアップヘルパー
別PCでの環境構築を支援
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, check=True):
    """コマンドを実行して結果を表示"""
    print(f"実行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"エラー: {result.stderr}", file=sys.stderr)
    if check and result.returncode != 0:
        print(f"コマンドが失敗しました（終了コード: {result.returncode}）")
        return False
    return True

def main():
    """メイン処理"""
    print("🚀 監視端末セットアップヘルパー")
    print("=" * 50)
    
    # Pythonバージョン確認
    print("\n1. Python環境確認")
    print("-" * 30)
    run_command("python --version")
    
    # 仮想環境作成
    print("\n2. 仮想環境セットアップ")
    print("-" * 30)
    
    venv_exists = Path("venv").exists()
    if not venv_exists:
        print("仮想環境を作成します...")
        if not run_command("python -m venv venv"):
            print("仮想環境の作成に失敗しました")
            return
    else:
        print("仮想環境は既に存在します")
    
    # 仮想環境のアクティベート方法を表示
    print("\n仮想環境をアクティベートしてください:")
    if sys.platform == "win32":
        print("  Windows: .\\venv\\Scripts\\activate")
    else:
        print("  Mac/Linux: source venv/bin/activate")
    
    print("\n3. 依存関係のインストール")
    print("-" * 30)
    print("以下のコマンドを実行してください:")
    print("  pip install -r requirements.txt")
    
    print("\n4. .envファイルの設定")
    print("-" * 30)
    
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists():
        print(".envファイルが存在しません")
        if env_example.exists():
            print(".env.exampleをコピーして作成してください:")
            print("  cp .env.example .env")
        else:
            print("以下の内容で.envファイルを作成してください:")
            print("""
# Database Configuration
# TailScale connection
DATABASE_URL=postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage

# Monitoring only - no API keys needed for read-only access
LOG_LEVEL=INFO
ENVIRONMENT=monitoring
TIMEZONE=Asia/Tokyo

# Discord Webhook for notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
""")
    else:
        print(".envファイルが既に存在します")
        print("DATABASE_URLをTailScale経由の接続に更新してください:")
        print("  DATABASE_URL=postgresql://postgres:password@100.94.216.39:5432/crypto_arbitrage")
    
    print("\n5. PostgreSQL接続テスト")
    print("-" * 30)
    print("以下のコマンドで接続をテストできます:")
    print("  python scripts/test_postgresql_connection.py")
    
    print("\n6. 読み取り専用モニターの起動")
    print("-" * 30)
    print("以下のコマンドでモニターを起動できます:")
    print("  python scripts/readonly_monitor.py")
    
    print("\n✅ セットアップ手順の表示が完了しました")
    print("\n注意事項:")
    print("- TailScaleが起動していることを確認してください")
    print("- データ収集端末のPostgreSQLが外部接続を許可していることを確認してください")
    print("- ファイアウォールでポート5432が開いていることを確認してください")

if __name__ == "__main__":
    main()