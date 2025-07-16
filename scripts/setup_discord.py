#!/usr/bin/env python3
"""
Discord通知セットアップ支援スクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(title):
    """見出しを表示"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def show_welcome():
    """ウェルカムメッセージ"""
    print("🤖 Discord通知セットアップガイド")
    print("=" * 60)
    print("このスクリプトでは、Discord通知の設定方法を段階的にご案内します。")
    print("Discordが初めての方でも安心して設定できます。")


def check_discord_account():
    """Discordアカウント確認"""
    print_header("Step 1: Discordアカウント")
    
    print("📱 Discordアカウントはお持ちですか？")
    print("1. はい、アカウントがあります")
    print("2. いいえ、これから作成します")
    
    while True:
        choice = input("\n選択してください (1/2): ").strip()
        if choice == "1":
            print("✅ 既存アカウントを使用します。")
            return True
        elif choice == "2":
            print("\n📋 Discordアカウント作成手順:")
            print("1. iPhoneでApp Storeを開く")
            print("2. 'Discord'を検索してアプリをダウンロード")
            print("3. アプリを開いて「登録」をタップ")
            print("4. メールアドレス・ユーザー名・パスワードを設定")
            print("5. メール認証を完了")
            
            input("\nアカウント作成が完了したらEnterキーを押してください...")
            return True
        else:
            print("❌ 1または2を入力してください。")


def check_discord_server():
    """Discordサーバー確認"""
    print_header("Step 2: Discordサーバー")
    
    print("🖥️ 通知用のDiscordサーバーはありますか？")
    print("1. はい、専用サーバーがあります")
    print("2. いいえ、これから作成します")
    
    while True:
        choice = input("\n選択してください (1/2): ").strip()
        if choice == "1":
            print("✅ 既存サーバーを使用します。")
            return True
        elif choice == "2":
            print("\n📋 Discordサーバー作成手順:")
            print("1. PCのブラウザで https://discord.com/ にアクセス")
            print("2. 「ブラウザでDiscordを開く」をクリック")
            print("3. 作成したアカウントでログイン")
            print("4. 左側の「+」ボタンをクリック")
            print("5. 「サーバーを作成」→「自分用」を選択")
            print("6. サーバー名：「仮想通貨Bot」と入力")
            print("7. 「作成」をクリック")
            
            input("\nサーバー作成が完了したらEnterキーを押してください...")
            return True
        else:
            print("❌ 1または2を入力してください。")


def guide_webhook_creation():
    """ウェブフック作成ガイド"""
    print_header("Step 3: ウェブフック作成")
    
    print("🔗 通知用のウェブフックを作成します。")
    print("\n📋 ウェブフック作成手順:")
    print("1. Discordサーバーで「#general」チャンネルの設定（⚙️）をクリック")
    print("2. または新しいチャンネル「arbitrage-alerts」を作成")
    print("3. チャンネル設定で「連携サービス」をクリック")
    print("4. 「ウェブフック」をクリック")
    print("5. 「新しいウェブフック」をクリック")
    print("6. 名前：「仮想通貨アービトラージBot」")
    print("7. 「変更を保存」をクリック")
    print("8. 作成したウェブフックをクリック")
    print("9. 「ウェブフックURLをコピー」をクリック")
    
    print("\n⚠️ 重要: ウェブフックURLは誰にも教えないでください！")
    
    input("\nウェブフックURL取得が完了したらEnterキーを押してください...")


def setup_env_file():
    """環境変数設定"""
    print_header("Step 4: 環境変数設定")
    
    env_path = project_root / ".env"
    
    print("📋 ウェブフックURLを設定します。")
    print(f"設定ファイル: {env_path}")
    
    webhook_url = input("\nウェブフックURLを入力してください: ").strip()
    
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        print("❌ 無効なウェブフックURLです。")
        print("正しいURLは https://discord.com/api/webhooks/ で始まります。")
        return False
    
    # .envファイルの読み込み・更新
    env_content = ""
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()
    
    # Discord設定の追加・更新
    if "DISCORD_WEBHOOK_URL=" in env_content:
        # 既存の設定を更新
        lines = env_content.split('\n')
        updated_lines = []
        for line in lines:
            if line.startswith("DISCORD_WEBHOOK_URL="):
                updated_lines.append(f"DISCORD_WEBHOOK_URL={webhook_url}")
            else:
                updated_lines.append(line)
        env_content = '\n'.join(updated_lines)
    else:
        # 新しい設定を追加
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f"\n# Discord Webhook\nDISCORD_WEBHOOK_URL={webhook_url}\n"
    
    # ファイルに保存
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ 環境変数が正常に設定されました。")
    return True


def test_discord_notification():
    """Discord通知テスト"""
    print_header("Step 5: 通知テスト")
    
    print("🧪 Discord通知をテストします...")
    
    try:
        from src.notifications.discord_notify import discord_notifier
        
        if not discord_notifier.webhook_url:
            print("❌ ウェブフックURLが設定されていません。")
            return False
        
        print("📤 テスト通知を送信中...")
        success = discord_notifier.test_connection()
        
        if success:
            print("✅ テスト通知が正常に送信されました！")
            print("📱 DiscordチャンネルとiPhoneで通知を確認してください。")
            return True
        else:
            print("❌ テスト通知の送信に失敗しました。")
            return False
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return False


def setup_iphone_notifications():
    """iPhone通知設定ガイド"""
    print_header("Step 6: iPhone通知設定")
    
    print("📱 iPhoneでの通知受信設定を行います。")
    print("\n📋 iPhone設定手順:")
    print("1. iPhoneでDiscordアプリを開く")
    print("2. 左上のメニュー（≡）をタップ")
    print("3. 作成したサーバー「仮想通貨Bot」をタップ")
    print("4. 右上のプロフィールアイコンをタップ")
    print("5. 「設定」（⚙️）をタップ")
    print("6. 「通知」をタップ")
    print("7. 「プッシュ通知」をオンにする")
    print("8. サーバーに戻り、サーバー名をタップ")
    print("9. 「通知設定」をタップ")
    print("10. 「すべてのメッセージ」をオン")
    print("11. 「モバイルプッシュ通知」をオン")
    
    print("\n⚙️ iPhoneの設定アプリでも確認:")
    print("1. 設定 → 通知 → Discord")
    print("2. 「通知を許可」がオンになっていることを確認")
    
    input("\niPhone設定が完了したらEnterキーを押してください...")


def show_final_test():
    """最終テスト"""
    print_header("Step 7: 最終確認")
    
    print("🎯 最終テストを実行します。")
    
    try:
        from src.notifications.manager import notification_manager
        
        # テスト用アービトラージデータ
        test_data = {
            'profit_pct': 0.15,
            'profit': 1500,
            'buy_exchange': 'bitFlyer',
            'sell_exchange': 'Coincheck', 
            'buy_price': 10000000,
            'sell_price': 10015000,
            'pair_symbol': 'BTC/JPY'
        }
        
        print("📤 アービトラージ通知テストを送信中...")
        success = notification_manager.send_arbitrage_alert(test_data)
        
        if success:
            print("✅ アービトラージ通知テストが成功しました！")
            print("📱 iPhoneで実際のアービトラージ通知を確認してください。")
            return True
        else:
            print("❌ アービトラージ通知テストに失敗しました。")
            return False
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return False


def show_next_steps():
    """次のステップ案内"""
    print_header("🎉 セットアップ完了！")
    
    print("✅ Discord通知の設定が完了しました。")
    print("\n📋 次のステップ:")
    print("1. データ収集を開始:")
    print("   python src/main.py collect")
    print("\n2. アービトラージ分析を開始:")
    print("   python src/main.py analyze")
    print("\n3. リアルタイム監視:")
    print("   python scripts/monitor_arbitrage.py")
    
    print("\n⚙️ 通知設定の調整:")
    print("1. 設定確認: python scripts/manage_notifications.py --show")
    print("2. 閾値変更: python scripts/manage_notifications.py --threshold 0.1")
    print("3. 静寂時間: python scripts/manage_notifications.py --quiet 23:00 07:00")
    
    print("\n📱 これで仮想通貨のアービトラージ機会をiPhoneでリアルタイムに受信できます！")


def main():
    """メイン関数"""
    try:
        show_welcome()
        
        # セットアップ手順
        steps = [
            ("Discordアカウント確認", check_discord_account),
            ("Discordサーバー確認", check_discord_server), 
            ("ウェブフック作成ガイド", guide_webhook_creation),
            ("環境変数設定", setup_env_file),
            ("Discord通知テスト", test_discord_notification),
            ("iPhone通知設定", setup_iphone_notifications),
            ("最終確認テスト", show_final_test)
        ]
        
        for step_name, step_func in steps:
            print(f"\n🔄 {step_name}を実行中...")
            success = step_func()
            if success is False:
                print(f"\n⚠️ {step_name}で問題が発生しました。")
                print("詳しい設定方法は docs/discord_setup_guide.md をご覧ください。")
                return
        
        show_next_steps()
        
    except KeyboardInterrupt:
        print("\n\n⛔ セットアップが中断されました")
    except Exception as e:
        print(f"\n💥 予期しないエラーが発生しました: {e}")
        print("詳しい設定方法は docs/discord_setup_guide.md をご覧ください。")


if __name__ == "__main__":
    main()