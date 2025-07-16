"""
通知設定の管理
"""

from typing import Dict, Any, List
import json
import os
from pathlib import Path
from loguru import logger


class NotificationConfig:
    """通知設定の管理クラス"""
    
    def __init__(self, config_file: str = "config/notifications.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """設定ファイルから設定を読み込み"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load notification config: {e}")
        
        # デフォルト設定
        return self.get_default_config()
    
    def save_config(self) -> bool:
        """設定をファイルに保存"""
        try:
            # ディレクトリが存在しない場合は作成
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Notification config saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save notification config: {e}")
            return False
    
    def get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を取得"""
        return {
            "arbitrage_alerts": {
                "enabled": True,
                "min_profit_threshold": 0.05,  # 最小利益率 0.05%
                "min_profit_amount": 1000,     # 最小利益額 1000円
                "cooldown_minutes": 5,         # 同じペアでの通知間隔（分）
                "max_notifications_per_hour": 20  # 1時間あたりの最大通知数
            },
            "price_alerts": {
                "enabled": False,
                "symbols": {
                    "BTC/JPY": {
                        "upper_threshold": 20000000,  # 2000万円
                        "lower_threshold": 15000000   # 1500万円
                    }
                }
            },
            "system_alerts": {
                "enabled": True,
                "alert_types": ["ERROR", "WARNING"],
                "data_collection_errors": True,
                "analysis_errors": True,
                "api_failures": True
            },
            "discord": {
                "enabled": True,
                "use_embeds": True,
                "quiet_hours": {
                    "enabled": False,
                    "start": "23:00",
                    "end": "07:00"
                }
            }
        }
    
    def is_arbitrage_notification_enabled(self) -> bool:
        """アービトラージ通知が有効かチェック"""
        return (self.config.get("arbitrage_alerts", {}).get("enabled", False) and
                self.config.get("discord", {}).get("enabled", False))
    
    def get_arbitrage_threshold(self) -> float:
        """アービトラージ通知の利益率閾値を取得"""
        return self.config.get("arbitrage_alerts", {}).get("min_profit_threshold", 0.05)
    
    def get_arbitrage_amount_threshold(self) -> float:
        """アービトラージ通知の利益額閾値を取得"""
        return self.config.get("arbitrage_alerts", {}).get("min_profit_amount", 1000)
    
    def get_notification_cooldown(self) -> int:
        """通知のクールダウン時間（分）を取得"""
        return self.config.get("arbitrage_alerts", {}).get("cooldown_minutes", 5)
    
    def get_max_notifications_per_hour(self) -> int:
        """1時間あたりの最大通知数を取得"""
        return self.config.get("arbitrage_alerts", {}).get("max_notifications_per_hour", 20)
    
    def is_quiet_hours(self) -> bool:
        """現在が静寂時間かチェック"""
        quiet_config = self.config.get("discord", {}).get("quiet_hours", {})
        if not quiet_config.get("enabled", False):
            return False
        
        from datetime import datetime
        import pytz
        
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        current_time = now.strftime("%H:%M")
        
        start_time = quiet_config.get("start", "23:00")
        end_time = quiet_config.get("end", "07:00")
        
        if start_time <= end_time:
            # 同日内の時間範囲
            return start_time <= current_time <= end_time
        else:
            # 日をまたぐ時間範囲
            return current_time >= start_time or current_time <= end_time
    
    def should_send_arbitrage_notification(self, profit_pct: float, 
                                         profit_amount: float) -> bool:
        """アービトラージ通知を送信すべきかチェック"""
        if not self.is_arbitrage_notification_enabled():
            return False
        
        if self.is_quiet_hours():
            return False
        
        # 利益率チェック
        if profit_pct < self.get_arbitrage_threshold():
            return False
        
        # 利益額チェック
        if profit_amount < self.get_arbitrage_amount_threshold():
            return False
        
        return True
    
    def update_arbitrage_settings(self, **kwargs) -> bool:
        """アービトラージ設定を更新"""
        arbitrage_config = self.config.setdefault("arbitrage_alerts", {})
        
        for key, value in kwargs.items():
            if key in ["min_profit_threshold", "min_profit_amount", 
                      "cooldown_minutes", "max_notifications_per_hour"]:
                arbitrage_config[key] = value
        
        return self.save_config()
    
    def enable_arbitrage_notifications(self, enabled: bool = True) -> bool:
        """アービトラージ通知の有効/無効を設定"""
        self.config.setdefault("arbitrage_alerts", {})["enabled"] = enabled
        return self.save_config()
    
    def set_quiet_hours(self, start_time: str, end_time: str, enabled: bool = True) -> bool:
        """静寂時間を設定"""
        quiet_config = self.config.setdefault("discord", {}).setdefault("quiet_hours", {})
        quiet_config["enabled"] = enabled
        quiet_config["start"] = start_time
        quiet_config["end"] = end_time
        return self.save_config()


# グローバルインスタンス
notification_config = NotificationConfig()