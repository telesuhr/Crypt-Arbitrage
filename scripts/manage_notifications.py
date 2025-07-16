#!/usr/bin/env python3
"""
LINE通知設定管理スクリプト
"""

import sys
import os
import argparse
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.notifications.config import notification_config
from src.notifications.manager import notification_manager


def show_config():
    """現在の設定を表示"""
    print("📋 現在の通知設定")
    print("=" * 50)
    
    print(f"🔔 アービトラージ通知:")
    print(f"   有効: {'✅' if notification_config.is_arbitrage_notification_enabled() else '❌'}")
    print(f"   利益率閾値: {notification_config.get_arbitrage_threshold():.3f}%")
    print(f"   利益額閾値: ¥{notification_config.get_arbitrage_amount_threshold():,.0f}")
    print(f"   クールダウン時間: {notification_config.get_notification_cooldown()}分")
    print(f"   1時間制限: {notification_config.get_max_notifications_per_hour()}件")
    
    print(f"\n⏰ 静寂時間:")
    quiet_config = notification_config.config.get("discord", {}).get("quiet_hours", {})
    print(f"   有効: {'✅' if quiet_config.get('enabled', False) else '❌'}")
    if quiet_config.get('enabled', False):
        print(f"   時間: {quiet_config.get('start', 'N/A')} - {quiet_config.get('end', 'N/A')}")
    
    print(f"\n🔧 システム通知:")
    system_config = notification_config.config.get("system_alerts", {})
    print(f"   有効: {'✅' if system_config.get('enabled', False) else '❌'}")
    print(f"   対象: {', '.join(system_config.get('alert_types', []))}")


def show_stats():
    """通知統計を表示"""
    print("📊 通知統計")
    print("=" * 50)
    
    stats = notification_manager.get_notification_stats()
    
    print(f"⏰ 過去1時間: {stats['past_hour']['total']}件")
    for notif_type, count in stats['past_hour']['by_type'].items():
        print(f"   - {notif_type}: {count}件")
    print(f"   制限: {stats['past_hour']['limit']}件")
    
    print(f"\n📅 過去24時間: {stats['past_24h']['total']}件")
    for notif_type, count in stats['past_24h']['by_type'].items():
        print(f"   - {notif_type}: {count}件")
    
    if stats['cooldown_status']:
        print(f"\n❄️ クールダウン状況:")
        for pair, minutes_since in stats['cooldown_status'].items():
            status = "✅ 可能" if minutes_since >= notification_config.get_notification_cooldown() else "❌ 制限中"
            print(f"   - {pair}: {minutes_since:.1f}分前 ({status})")


def enable_notifications(enabled: bool):
    """通知の有効/無効を設定"""
    success = notification_config.enable_arbitrage_notifications(enabled)
    status = "有効" if enabled else "無効"
    
    if success:
        print(f"✅ アービトラージ通知を{status}にしました")
    else:
        print(f"❌ 設定の保存に失敗しました")


def set_thresholds(profit_pct: float = None, profit_amount: float = None):
    """閾値を設定"""
    updates = {}
    
    if profit_pct is not None:
        updates['min_profit_threshold'] = profit_pct
        print(f"📈 利益率閾値を {profit_pct:.3f}% に設定")
    
    if profit_amount is not None:
        updates['min_profit_amount'] = profit_amount
        print(f"💴 利益額閾値を ¥{profit_amount:,.0f} に設定")
    
    if updates:
        success = notification_config.update_arbitrage_settings(**updates)
        if success:
            print("✅ 設定を保存しました")
        else:
            print("❌ 設定の保存に失敗しました")


def set_cooldown(minutes: int):
    """クールダウン時間を設定"""
    success = notification_config.update_arbitrage_settings(cooldown_minutes=minutes)
    
    if success:
        print(f"✅ クールダウン時間を {minutes}分 に設定しました")
    else:
        print("❌ 設定の保存に失敗しました")


def set_quiet_hours(start_time: str, end_time: str, enabled: bool = True):
    """静寂時間を設定"""
    success = notification_config.set_quiet_hours(start_time, end_time, enabled)
    
    if success:
        status = "有効" if enabled else "無効"
        print(f"✅ 静寂時間を設定しました: {start_time}-{end_time} ({status})")
    else:
        print("❌ 設定の保存に失敗しました")


def test_notification():
    """テスト通知を送信"""
    print("🔔 Discord テスト通知を送信中...")
    
    # テスト用のアービトラージデータ
    test_data = {
        'profit_pct': 0.1,
        'profit': 1000,
        'buy_exchange': 'TEST取引所A',
        'sell_exchange': 'TEST取引所B',
        'buy_price': 10000000,
        'sell_price': 10010000,
        'pair_symbol': 'BTC/JPY'
    }
    
    success = notification_manager.send_arbitrage_alert(test_data)
    
    if success:
        print("✅ Discord テスト通知を送信しました")
        print("📱 iPhoneのDiscordアプリで通知を確認してください")
    else:
        print("❌ テスト通知の送信に失敗しました")
        print("💡 DISCORD_WEBHOOK_URLが正しく設定されているか確認してください")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="LINE通知設定管理ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python manage_notifications.py --show              # 現在の設定表示
  python manage_notifications.py --stats             # 通知統計表示
  python manage_notifications.py --enable            # 通知を有効化
  python manage_notifications.py --disable           # 通知を無効化
  python manage_notifications.py --threshold 0.1     # 利益率閾値を0.1%に設定
  python manage_notifications.py --amount 2000       # 利益額閾値を2000円に設定
  python manage_notifications.py --cooldown 10       # クールダウンを10分に設定
  python manage_notifications.py --quiet 23:00 07:00 # 静寂時間を23:00-07:00に設定
  python manage_notifications.py --test              # テスト通知を送信
        """
    )
    
    # コマンドライン引数
    parser.add_argument('--show', action='store_true', help='現在の設定を表示')
    parser.add_argument('--stats', action='store_true', help='通知統計を表示')
    parser.add_argument('--enable', action='store_true', help='通知を有効化')
    parser.add_argument('--disable', action='store_true', help='通知を無効化')
    parser.add_argument('--threshold', type=float, metavar='PCT', help='利益率閾値を設定（%）')
    parser.add_argument('--amount', type=float, metavar='YEN', help='利益額閾値を設定（円）')
    parser.add_argument('--cooldown', type=int, metavar='MIN', help='クールダウン時間を設定（分）')
    parser.add_argument('--quiet', nargs=2, metavar=('START', 'END'), help='静寂時間を設定（HH:MM HH:MM）')
    parser.add_argument('--test', action='store_true', help='テスト通知を送信')
    
    args = parser.parse_args()
    
    try:
        # 引数に応じて処理を実行
        if args.show:
            show_config()
        elif args.stats:
            show_stats()
        elif args.enable:
            enable_notifications(True)
        elif args.disable:
            enable_notifications(False)
        elif args.threshold is not None:
            set_thresholds(profit_pct=args.threshold)
        elif args.amount is not None:
            set_thresholds(profit_amount=args.amount)
        elif args.cooldown is not None:
            set_cooldown(args.cooldown)
        elif args.quiet:
            set_quiet_hours(args.quiet[0], args.quiet[1])
        elif args.test:
            test_notification()
        else:
            # デフォルトで設定を表示
            show_config()
            
    except KeyboardInterrupt:
        print("\n⛔ 処理が中断されました")
    except Exception as e:
        print(f"💥 エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()