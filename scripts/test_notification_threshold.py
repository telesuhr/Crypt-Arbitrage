#!/usr/bin/env python3
"""
通知しきい値のテストスクリプト
"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.notifications.manager import notification_manager
from src.notifications.config import notification_config

def test_notification_thresholds():
    """様々な利益率で通知がトリガーされるかテスト"""
    
    print("現在の通知設定:")
    print(f"- 最小利益率しきい値: {notification_config.get_arbitrage_threshold()}%")
    print(f"- 最小利益額しきい値: {notification_config.get_arbitrage_amount_threshold()}円")
    print()
    
    # テストケース
    test_cases = [
        {"profit_pct": 0.0, "profit": 0, "expected": False, "description": "0%利益"},
        {"profit_pct": 0.05, "profit": 500, "expected": False, "description": "0.05%利益、500円"},
        {"profit_pct": 0.05, "profit": 1500, "expected": False, "description": "0.05%利益、1500円（利益率不足）"},
        {"profit_pct": 0.1, "profit": 500, "expected": False, "description": "0.1%利益、500円（利益額不足）"},
        {"profit_pct": 0.1, "profit": 1000, "expected": True, "description": "0.1%利益、1000円（両方OK）"},
        {"profit_pct": 0.15, "profit": 1500, "expected": True, "description": "0.15%利益、1500円"},
        {"profit_pct": 0.3, "profit": 3000, "expected": True, "description": "0.3%利益、3000円"},
    ]
    
    print("テスト結果:")
    print("-" * 80)
    
    for test in test_cases:
        should_send = notification_config.should_send_arbitrage_notification(
            test["profit_pct"], 
            test["profit"]
        )
        
        status = "✅" if should_send == test["expected"] else "❌"
        result = "送信する" if should_send else "送信しない"
        
        print(f"{status} {test['description']}: {result}")
        
        if should_send != test["expected"]:
            print(f"   予期された結果: {'送信する' if test['expected'] else '送信しない'}")

if __name__ == "__main__":
    test_notification_thresholds()