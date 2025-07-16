#!/usr/bin/env python3
"""
LINE通知機能のテストスクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.notifications.line_notify import line_notifier
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
    
    if not line_notifier.token:
        print("❌ LINE_NOTIFY_TOKEN が設定されていません")
        print("   環境変数またはクライアントに設定してください")
        return False
    
    print("🔔 テストメッセージを送信中...")
    success = line_notifier.test_connection()
    
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


def check_notification_stats():
    """通知統計の確認"""
    print_header("通知統計確認")
    
    stats = notification_manager.get_notification_stats()
    
    print("📈 通知統計:")
    print(f"   過去1時間: {stats['past_hour']['total']}件")
    print(f"     - アービトラージ: {stats['past_hour']['by_type'].get('arbitrage', 0)}件")
    print(f"     - システム: {stats['past_hour']['by_type'].get('system', 0)}件")
    print(f"   過去24時間: {stats['past_24h']['total']}件")
    
    if stats['cooldown_status']:
        print("   クールダウン状況:")
        for pair, minutes_since in stats['cooldown_status'].items():
            if minutes_since < 60:  # 1時間以内のみ表示
                print(f"     - {pair}: {minutes_since:.1f}分前")
    
    return True


def main():
    """メイン関数"""
    print("🔔 LINE通知機能テストプログラム")
    print("=" * 60)
    
    try:
        # 各テストを実行
        tests = [
            ("通知設定確認", check_notification_config),
            ("基本メッセージ送信", test_basic_message),
            ("システム通知", test_system_notification),
            ("アービトラージ通知", test_arbitrage_notification),
            ("通知統計確認", check_notification_stats)
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
            status = "✅ 成功" if result else "❌ 失敗"
            print(f"  {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n📊 結果: {passed}/{len(results)} テスト成功")
        
        if passed == len(results):
            print("🎉 すべてのテストが成功しました！")
        else:
            print("⚠️ 一部のテストが失敗しました。設定を確認してください。")
            print("\n💡 ヒント:")
            print("   - LINE_NOTIFY_TOKENが正しく設定されているか確認")
            print("   - インターネット接続を確認")
            print("   - LINE Notifyトークンの有効性を確認")
        
    except KeyboardInterrupt:
        print("\n\n⛔ テストが中断されました")
    except Exception as e:
        print(f"\n💥 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()