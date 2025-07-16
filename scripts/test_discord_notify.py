#!/usr/bin/env python3
"""
Discord通知機能のテストスクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.notifications.discord_notify import discord_notifier
from src.notifications.manager import notification_manager
from datetime import datetime
from decimal import Decimal


def print_header(title):
    """見出しを表示"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_basic_message():
    """基本的なメッセージ送信テスト"""
    print_header("基本メッセージ送信テスト")
    
    if not discord_notifier.webhook_url:
        print("❌ DISCORD_WEBHOOK_URL が設定されていません")
        print("   環境変数に設定してください")
        print("   Discord サーバー設定 → インテグレーション → ウェブフック → 新しいウェブフック")
        return False
    
    print("🔔 テストメッセージを送信中...")
    success = discord_notifier.test_connection()
    
    if success:
        print("✅ テストメッセージが正常に送信されました")
        return True
    else:
        print("❌ テストメッセージの送信に失敗しました")
        return False


def test_arbitrage_notification():
    """アービトラージ通知テスト"""
    print_header("アービトラージ通知テスト")
    
    # テスト用のアービトラージデータ
    test_arbitrage_data = {
        'profit_pct': 0.15,  # 0.15%
        'profit': 1500,      # 1500円
        'buy_exchange': 'bitFlyer',
        'sell_exchange': 'Coincheck',
        'buy_price': 10000000,  # 1000万円
        'sell_price': 10015000,  # 1001.5万円
        'pair_symbol': 'BTC/JPY'
    }
    
    print(f"📊 テストデータ:")
    print(f"   通貨ペア: {test_arbitrage_data['pair_symbol']}")
    print(f"   利益率: {test_arbitrage_data['profit_pct']:.3f}%")
    print(f"   予想利益: ¥{test_arbitrage_data['profit']:,.0f}")
    print(f"   買い: {test_arbitrage_data['buy_exchange']} (¥{test_arbitrage_data['buy_price']:,.0f})")
    print(f"   売り: {test_arbitrage_data['sell_exchange']} (¥{test_arbitrage_data['sell_price']:,.0f})")
    
    print("\n🚀 アービトラージ通知を送信中...")
    success = notification_manager.send_arbitrage_alert(test_arbitrage_data)
    
    if success:
        print("✅ アービトラージ通知が正常に送信されました")
        return True
    else:
        print("❌ アービトラージ通知の送信に失敗しました")
        return False


def test_system_notification():
    """システム通知テスト"""
    print_header("システム通知テスト")
    
    print("⚠️ システム通知を送信中...")
    success = notification_manager.send_system_alert(
        "INFO", 
        "仮想通貨アービトラージシステムが正常に動作しています"
    )
    
    if success:
        print("✅ システム通知が正常に送信されました")
        return True
    else:
        print("❌ システム通知の送信に失敗しました")
        return False


def test_different_profit_levels():
    """異なる利益率レベルでのテスト"""
    print_header("利益率別通知テスト")
    
    test_cases = [
        {"profit_pct": 0.05, "label": "低利益（0.05%）", "color": "オレンジ"},
        {"profit_pct": 0.15, "label": "中利益（0.15%）", "color": "黄色"},
        {"profit_pct": 0.75, "label": "高利益（0.75%）", "color": "緑"}
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📈 テスト {i}/3: {case['label']} - 埋め込み色: {case['color']}")
        
        test_data = {
            'profit_pct': case['profit_pct'],
            'profit': int(case['profit_pct'] * 100000),  # 仮の利益額
            'buy_exchange': 'TEST取引所A',
            'sell_exchange': 'TEST取引所B',
            'buy_price': 10000000,
            'sell_price': int(10000000 * (1 + case['profit_pct'] / 100)),
            'pair_symbol': 'BTC/JPY'
        }
        
        success = discord_notifier.send_arbitrage_alert(test_data)
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"   結果: {status}")


def check_notification_config():
    """通知設定の確認"""
    print_header("通知設定確認")
    
    from src.notifications.config import notification_config
    
    print("📋 現在の通知設定:")
    print(f"   アービトラージ通知: {'有効' if notification_config.is_arbitrage_notification_enabled() else '無効'}")
    print(f"   利益率閾値: {notification_config.get_arbitrage_threshold():.3f}%")
    print(f"   利益額閾値: ¥{notification_config.get_arbitrage_amount_threshold():,.0f}")
    print(f"   クールダウン時間: {notification_config.get_notification_cooldown()}分")
    print(f"   1時間制限: {notification_config.get_max_notifications_per_hour()}件")
    print(f"   静寂時間: {'有効' if notification_config.is_quiet_hours() else '無効'}")
    
    return True


def show_discord_setup_guide():
    """Discord設定ガイドを表示"""
    print_header("Discord ウェブフック設定ガイド")
    
    print("🔧 Discord ウェブフックの設定方法:")
    print("   1. Discordサーバーを開く")
    print("   2. 設定（歯車アイコン）→ インテグレーション")
    print("   3. ウェブフック → 新しいウェブフック")
    print("   4. 名前を設定（例：仮想通貨Bot）")
    print("   5. チャンネルを選択")
    print("   6. ウェブフックURLをコピー")
    print("   7. .envファイルのDISCORD_WEBHOOK_URLに設定")
    print("\n📱 iPhoneでの通知受信:")
    print("   1. Discord iPhoneアプリをインストール")
    print("   2. 設定 → 通知 → プッシュ通知を有効化")
    print("   3. サーバー通知設定で該当チャンネルを有効化")
    print("\n🔔 通知のメリット:")
    print("   ✅ 無料で無制限")
    print("   ✅ リアルタイム通知")
    print("   ✅ リッチな埋め込みメッセージ")
    print("   ✅ iPhone・Android対応")
    print("   ✅ PCでも確認可能")


def main():
    """メイン関数"""
    print("🤖 Discord通知機能テストプログラム")
    print("=" * 60)
    
    try:
        # Discord設定ガイドを表示
        show_discord_setup_guide()
        
        # 各テストを実行
        tests = [
            ("通知設定確認", check_notification_config),
            ("基本メッセージ送信", test_basic_message),
            ("システム通知", test_system_notification),
            ("アービトラージ通知", test_arbitrage_notification),
            ("利益率別通知", test_different_profit_levels)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name}でエラーが発生: {e}")
                results.append((test_name, False))
        
        # 結果サマリー
        print_header("テスト結果サマリー")
        passed = 0
        for test_name, result in results:
            if result is not None:  # 設定確認などはNoneを返すことがある
                status = "✅ 成功" if result else "❌ 失敗"
                print(f"  {test_name}: {status}")
                if result:
                    passed += 1
            else:
                print(f"  {test_name}: 📋 確認済み")
        
        success_tests = [r for r in results if r[1] is True]
        total_tests = [r for r in results if r[1] is not None]
        
        print(f"\n📊 結果: {len(success_tests)}/{len(total_tests)} テスト成功")
        
        if len(success_tests) == len(total_tests):
            print("🎉 すべてのテストが成功しました！")
            print("📱 iPhoneのDiscordアプリで通知を確認してください。")
        else:
            print("⚠️ 一部のテストが失敗しました。設定を確認してください。")
            print("\n💡 トラブルシューティング:")
            print("   - DISCORD_WEBHOOK_URLが正しく設定されているか確認")
            print("   - ウェブフックURLが有効か確認")
            print("   - インターネット接続を確認")
            print("   - Discordサーバーの権限を確認")
        
    except KeyboardInterrupt:
        print("\n\n⛔ テストが中断されました")
    except Exception as e:
        print(f"\n💥 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()