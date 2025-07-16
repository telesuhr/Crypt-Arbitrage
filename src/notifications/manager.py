"""
通知管理システム
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pytz
from collections import defaultdict, deque
from loguru import logger

from .discord_notify import send_arbitrage_notification, send_system_notification
from .config import notification_config


class NotificationManager:
    """通知の送信頻度制限と履歴管理"""
    
    def __init__(self):
        self.jst = pytz.timezone('Asia/Tokyo')
        
        # 通知履歴（過去1時間分のみ保持）
        self.notification_history = deque(maxlen=1000)
        
        # 取引所ペア別の最後の通知時刻
        self.last_arbitrage_notification = {}
        
        # 1時間あたりの通知カウンター
        self.hourly_notification_count = deque(maxlen=100)
    
    def _is_cooldown_active(self, pair_key: str) -> bool:
        """指定された取引所ペアのクールダウンが有効かチェック"""
        if pair_key not in self.last_arbitrage_notification:
            return False
        
        last_notification = self.last_arbitrage_notification[pair_key]
        cooldown_minutes = notification_config.get_notification_cooldown()
        cooldown_delta = timedelta(minutes=cooldown_minutes)
        
        return datetime.now(self.jst) - last_notification < cooldown_delta
    
    def _is_hourly_limit_reached(self) -> bool:
        """1時間あたりの通知上限に達しているかチェック"""
        now = datetime.now(self.jst)
        one_hour_ago = now - timedelta(hours=1)
        
        # 過去1時間の通知をカウント
        recent_notifications = [
            ts for ts in self.hourly_notification_count
            if ts > one_hour_ago
        ]
        
        max_notifications = notification_config.get_max_notifications_per_hour()
        return len(recent_notifications) >= max_notifications
    
    def _update_notification_records(self, pair_key: str):
        """通知記録を更新"""
        now = datetime.now(self.jst)
        
        # 取引所ペア別の最後の通知時刻を更新
        self.last_arbitrage_notification[pair_key] = now
        
        # 1時間カウンターに追加
        self.hourly_notification_count.append(now)
        
        # 履歴に追加
        self.notification_history.append({
            'timestamp': now,
            'type': 'arbitrage',
            'pair_key': pair_key
        })
    
    def send_arbitrage_alert(self, arbitrage_data: Dict[str, Any]) -> bool:
        """
        アービトラージアラートを送信（頻度制限付き）
        
        Args:
            arbitrage_data: アービトラージ機会のデータ
        
        Returns:
            送信成功の場合True
        """
        try:
            profit_pct = float(arbitrage_data.get('profit_pct', 0))
            profit_amount = float(arbitrage_data.get('profit', 0))
            
            # 通知すべきかチェック
            if not notification_config.should_send_arbitrage_notification(profit_pct, profit_amount):
                logger.debug("Arbitrage notification skipped: threshold not met")
                return False
            
            # 取引所ペアキーを生成
            buy_exchange = arbitrage_data.get('buy_exchange', '')
            sell_exchange = arbitrage_data.get('sell_exchange', '')
            pair_symbol = arbitrage_data.get('pair_symbol', '')
            pair_key = f"{pair_symbol}:{buy_exchange}->{sell_exchange}"
            
            # クールダウンチェック
            if self._is_cooldown_active(pair_key):
                logger.debug(f"Arbitrage notification skipped: cooldown active for {pair_key}")
                return False
            
            # 1時間制限チェック
            if self._is_hourly_limit_reached():
                logger.warning("Arbitrage notification skipped: hourly limit reached")
                return False
            
            # 通知送信
            success = send_arbitrage_notification(arbitrage_data)
            
            if success:
                self._update_notification_records(pair_key)
                logger.info(f"Arbitrage notification sent for {pair_key}: {profit_pct:.3f}%")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send arbitrage alert: {e}")
            return False
    
    def send_system_alert(self, alert_type: str, message: str) -> bool:
        """
        システムアラートを送信
        
        Args:
            alert_type: アラートタイプ
            message: メッセージ内容
        
        Returns:
            送信成功の場合True
        """
        try:
            # システム通知設定をチェック
            system_config = notification_config.config.get("system_alerts", {})
            
            if not system_config.get("enabled", False):
                return False
            
            # アラートタイプが有効かチェック
            enabled_types = system_config.get("alert_types", [])
            if alert_type not in enabled_types:
                return False
            
            # 静寂時間チェック（ERRORは除く）
            if alert_type != "ERROR" and notification_config.is_quiet_hours():
                return False
            
            # 通知送信
            success = send_system_notification(alert_type, message)
            
            if success:
                # 履歴に追加
                self.notification_history.append({
                    'timestamp': datetime.now(self.jst),
                    'type': 'system',
                    'alert_type': alert_type,
                    'message': message
                })
                logger.info(f"System notification sent: {alert_type} - {message}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send system alert: {e}")
            return False
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """通知統計を取得"""
        now = datetime.now(self.jst)
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        
        # 過去1時間の通知
        recent_notifications = [
            notif for notif in self.notification_history
            if notif['timestamp'] > one_hour_ago
        ]
        
        # 過去24時間の通知
        daily_notifications = [
            notif for notif in self.notification_history
            if notif['timestamp'] > one_day_ago
        ]
        
        # タイプ別カウント
        hourly_by_type = defaultdict(int)
        daily_by_type = defaultdict(int)
        
        for notif in recent_notifications:
            hourly_by_type[notif['type']] += 1
        
        for notif in daily_notifications:
            daily_by_type[notif['type']] += 1
        
        return {
            'past_hour': {
                'total': len(recent_notifications),
                'by_type': dict(hourly_by_type),
                'limit': notification_config.get_max_notifications_per_hour()
            },
            'past_24h': {
                'total': len(daily_notifications),
                'by_type': dict(daily_by_type)
            },
            'cooldown_status': {
                pair: (datetime.now(self.jst) - last_time).total_seconds() / 60
                for pair, last_time in self.last_arbitrage_notification.items()
            }
        }
    
    def clear_old_records(self):
        """古い記録をクリーンアップ"""
        now = datetime.now(self.jst)
        one_day_ago = now - timedelta(days=1)
        
        # 24時間以上古い履歴を削除
        self.notification_history = deque([
            notif for notif in self.notification_history
            if notif['timestamp'] > one_day_ago
        ], maxlen=1000)
        
        # 1時間以上古いクールダウン記録を削除
        one_hour_ago = now - timedelta(hours=1)
        self.last_arbitrage_notification = {
            pair: last_time
            for pair, last_time in self.last_arbitrage_notification.items()
            if last_time > one_hour_ago
        }


# グローバルインスタンス
notification_manager = NotificationManager()