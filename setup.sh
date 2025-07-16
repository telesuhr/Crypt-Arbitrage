#!/bin/bash

# 仮想通貨アービトラージシステムのセットアップスクリプト

echo "🚀 仮想通貨アービトラージシステムのセットアップを開始します..."

# Python仮想環境の作成
echo "📦 Python仮想環境を作成中..."
python3 -m venv venv

# 仮想環境を有効化
echo "🔧 仮想環境を有効化中..."
source venv/bin/activate

# 依存パッケージのインストール
echo "📚 依存パッケージをインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

# .envファイルの作成
if [ ! -f .env ]; then
    echo "⚙️ 環境変数ファイルを作成中..."
    cp .env.example .env
    echo "⚠️  .envファイルを編集して、データベース接続情報とAPIキーを設定してください"
fi

# ログディレクトリの作成
echo "📁 ログディレクトリを作成中..."
mkdir -p logs

# データベースのセットアップ
echo "🗄️ データベースをセットアップしますか？ (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    python src/main.py setup-db
fi

echo "✅ セットアップが完了しました！"
echo ""
echo "次のステップ:"
echo "1. .envファイルを編集して設定を完了してください"
echo "2. 接続テスト: python src/main.py test-connection"
echo "3. データ収集開始: python src/main.py collect"
echo "4. ダッシュボード起動: python src/main.py dashboard"