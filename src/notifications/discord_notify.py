"""
Discord Webhook による通知機能
"""

import requests
import json
from datetime import datetime
import pytz
from typing import Optional, Dict, Any
from loguru import logger
import os


class DiscordNotifier:
    """Discord Webhook を使用した通知システム"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Discord通知クライアントを初期化
        
        Args:
            webhook_url: Discord Webhook URL（環境変数から取得可能）
        """
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        
        if not self.webhook_url:
            logger.warning("Discord Webhook URL not found. Set DISCORD_WEBHOOK_URL environment variable.")
    
    def send_message(self, content: str, embeds: Optional[list] = None) -> bool:
        """
        Discordでメッセージを送信
        
        Args:
            content: 送信するメッセージ
            embeds: 埋め込みコンテンツ（オプション）
        
        Returns:
            送信成功の場合True
        """
        if not self.webhook_url:
            logger.error("Discord Webhook URL not configured")
            return False
        
        payload = {
            'content': content,
            'username': '仮想通貨アービトラージBot',
            'avatar_url': 'https://cdn-icons-png.flaticon.com/512/6001/6001368.png'
        }
        
        if embeds:
            payload['embeds'] = embeds
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
                return True
            else:
                logger.error(f"Discord notification failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
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
        
        # 利益率に応じて色を設定
        profit_pct = arbitrage_data.get('profit_pct', 0)
        if profit_pct >= 0.5:
            color = 0x00ff00  # 緑（高利益）
        elif profit_pct >= 0.1:
            color = 0xffff00  # 黄（中利益）
        else:
            color = 0xff8800  # オレンジ（低利益）
        
        embed = {
            "title": "🚀 アービトラージ機会発見！",
            "color": color,
            "timestamp": now.isoformat(),
            "fields": [
                {
                    "name": "💰 利益率",
                    "value": f"{profit_pct:.3f}%",
                    "inline": True
                },
                {
                    "name": "💴 予想利益",
                    "value": f"¥{arbitrage_data.get('profit', 0):,.0f}",
                    "inline": True
                },
                {
                    "name": "💱 通貨ペア",
                    "value": arbitrage_data.get('pair_symbol', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "🔸 買い取引所",
                    "value": f"{arbitrage_data.get('buy_exchange', 'Unknown')}\n¥{arbitrage_data.get('buy_price', 0):,.0f}",
                    "inline": True
                },
                {
                    "name": "🔹 売り取引所", 
                    "value": f"{arbitrage_data.get('sell_exchange', 'Unknown')}\n¥{arbitrage_data.get('sell_price', 0):,.0f}",
                    "inline": True
                },
                {
                    "name": "🕐 検出時刻",
                    "value": now.strftime('%H:%M:%S'),
                    "inline": True
                }
            ],
            "footer": {
                "text": "⚠️ 手数料・送金時間を考慮して判断してください"
            }
        }
        
        return self.send_message(
            f"💎 **{arbitrage_data.get('pair_symbol', 'BTC/JPY')}** で利益率 **{profit_pct:.3f}%** のアービトラージ機会を検出しました！",
            [embed]
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
        color = 0x00ff00 if direction == "above" else 0xff0000
        
        embed = {
            "title": f"{arrow} 価格アラート",
            "color": color,
            "timestamp": now.isoformat(),
            "fields": [
                {
                    "name": "💱 通貨ペア",
                    "value": symbol,
                    "inline": True
                },
                {
                    "name": "💴 現在価格",
                    "value": f"¥{price:,.0f}",
                    "inline": True
                },
                {
                    "name": "🎯 閾値",
                    "value": f"¥{threshold:,.0f}",
                    "inline": True
                }
            ],
            "description": f"価格が閾値を{direction_text}しました！"
        }
        
        return self.send_message(f"{arrow} **{symbol}** の価格アラート", [embed])
    
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
        
        color_map = {
            'ERROR': 0xff0000,    # 赤
            'WARNING': 0xffff00,  # 黄
            'INFO': 0x0099ff      # 青
        }
        
        emoji = emoji_map.get(alert_type, '📢')
        color = color_map.get(alert_type, 0x808080)
        
        embed = {
            "title": f"{emoji} システム通知",
            "color": color,
            "timestamp": now.isoformat(),
            "fields": [
                {
                    "name": "🔧 タイプ",
                    "value": alert_type,
                    "inline": True
                },
                {
                    "name": "📝 内容",
                    "value": message,
                    "inline": False
                }
            ]
        }
        
        return self.send_message(f"{emoji} **{alert_type}**: {message}", [embed])
    
    def test_connection(self) -> bool:
        """
        Discord Webhook接続をテスト
        
        Returns:
            接続成功の場合True
        """
        embed = {
            "title": "🔔 接続テスト",
            "color": 0x00ff00,
            "description": "仮想通貨アービトラージシステムのDiscord通知機能が正常に動作しています",
            "timestamp": datetime.now(pytz.timezone('Asia/Tokyo')).isoformat(),
            "footer": {
                "text": "システム正常稼働中"
            }
        }
        
        return self.send_message("🤖 **Discord通知テスト**", [embed])


# グローバルインスタンス
discord_notifier = DiscordNotifier()


def send_arbitrage_notification(arbitrage_data: Dict[str, Any]) -> bool:
    """
    アービトラージ通知の便利関数
    
    Args:
        arbitrage_data: アービトラージ機会のデータ
    
    Returns:
        送信成功の場合True
    """
    return discord_notifier.send_arbitrage_alert(arbitrage_data)


def send_system_notification(alert_type: str, message: str) -> bool:
    """
    システム通知の便利関数
    
    Args:
        alert_type: アラートタイプ
        message: メッセージ内容
    
    Returns:
        送信成功の場合True
    """
    return discord_notifier.send_system_alert(alert_type, message)