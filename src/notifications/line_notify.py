"""
LINE Notify による通知機能
"""

import requests
import json
from datetime import datetime
import pytz
from typing import Optional, Dict, Any
from loguru import logger
import os


class LineNotifier:
    """LINE Notify API を使用した通知システム"""
    
    def __init__(self, token: Optional[str] = None):
        """
        LINE Notifyクライアントを初期化
        
        Args:
            token: LINE Notify トークン（環境変数から取得可能）
        """
        self.token = token or os.getenv('LINE_NOTIFY_TOKEN')
        self.api_url = 'https://notify-api.line.me/api/notify'
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        if not self.token:
            logger.warning("LINE Notify token not found. Set LINE_NOTIFY_TOKEN environment variable.")
    
    def send_message(self, message: str, sticker_package_id: Optional[int] = None, 
                    sticker_id: Optional[int] = None) -> bool:
        """
        LINE Notifyでメッセージを送信
        
        Args:
            message: 送信するメッセージ
            sticker_package_id: スタンプパッケージID（オプション）
            sticker_id: スタンプID（オプション）
        
        Returns:
            送信成功の場合True
        """
        if not self.token:
            logger.error("LINE Notify token not configured")
            return False
        
        data = {
            'message': message
        }
        
        if sticker_package_id and sticker_id:
            data['stickerPackageId'] = sticker_package_id
            data['stickerId'] = sticker_id
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("LINE notification sent successfully")
                return True
            else:
                logger.error(f"LINE notification failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send LINE notification: {e}")
            return False
    
    def send_arbitrage_alert(self, arbitrage_data: Dict[str, Any]) -> bool:
        """
        アービトラージ機会の通知を送信
        
        Args:
            arbitrage_data: アービトラージ機会のデータ
        
        Returns:
            送信成功の場合True
        """
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        
        # メッセージを構築
        message = f"""🚀 アービトラージ機会発見！

💰 利益率: {arbitrage_data.get('profit_pct', 0):.3f}%
💴 予想利益: ¥{arbitrage_data.get('profit', 0):,.0f}

📊 取引詳細:
🔸 買い: {arbitrage_data.get('buy_exchange', 'Unknown')}
   価格: ¥{arbitrage_data.get('buy_price', 0):,.0f}
🔹 売り: {arbitrage_data.get('sell_exchange', 'Unknown')}
   価格: ¥{arbitrage_data.get('sell_price', 0):,.0f}

💱 通貨ペア: {arbitrage_data.get('pair_symbol', 'Unknown')}
🕐 検出時刻: {now.strftime('%H:%M:%S')}

⚠️ 手数料・送金時間を考慮して判断してください"""
        
        # スタンプ付きで送信（お金のスタンプ）
        return self.send_message(
            message, 
            sticker_package_id=11537,  # お金関連スタンプ
            sticker_id=52002734       # 💰スタンプ
        )
    
    def send_price_alert(self, symbol: str, price: float, threshold: float, 
                        direction: str) -> bool:
        """
        価格アラートを送信
        
        Args:
            symbol: 通貨ペア
            price: 現在価格
            threshold: アラート閾値
            direction: 'above' または 'below'
        
        Returns:
            送信成功の場合True
        """
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        
        arrow = "📈" if direction == "above" else "📉"
        direction_text = "上昇" if direction == "above" else "下落"
        
        message = f"""{arrow} 価格アラート

💱 {symbol}
💴 現在価格: ¥{price:,.0f}
🎯 閾値: ¥{threshold:,.0f}

価格が閾値を{direction_text}しました！
🕐 {now.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return self.send_message(message)
    
    def send_system_alert(self, alert_type: str, message: str) -> bool:
        """
        システムアラートを送信
        
        Args:
            alert_type: アラートタイプ（ERROR, WARNING, INFO）
            message: メッセージ内容
        
        Returns:
            送信成功の場合True
        """
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst)
        
        emoji_map = {
            'ERROR': '🚨',
            'WARNING': '⚠️',
            'INFO': 'ℹ️'
        }
        
        emoji = emoji_map.get(alert_type, '📢')
        
        notification_message = f"""{emoji} システム通知

🔧 タイプ: {alert_type}
📝 内容: {message}
🕐 時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return self.send_message(notification_message)
    
    def test_connection(self) -> bool:
        """
        LINE Notify接続をテスト
        
        Returns:
            接続成功の場合True
        """
        test_message = "🔔 仮想通貨アービトラージシステム\nLINE通知機能のテストです"
        return self.send_message(test_message)


# グローバルインスタンス
line_notifier = LineNotifier()


def send_arbitrage_notification(arbitrage_data: Dict[str, Any]) -> bool:
    """
    アービトラージ通知の便利関数
    
    Args:
        arbitrage_data: アービトラージ機会のデータ
    
    Returns:
        送信成功の場合True
    """
    return line_notifier.send_arbitrage_alert(arbitrage_data)


def send_system_notification(alert_type: str, message: str) -> bool:
    """
    システム通知の便利関数
    
    Args:
        alert_type: アラートタイプ
        message: メッセージ内容
    
    Returns:
        送信成功の場合True
    """
    return line_notifier.send_system_alert(alert_type, message)