#!/usr/bin/env python3
"""
タスク管理スクリプト - プロセスの確認・開始・停止
"""

import subprocess
import sys
import time
import argparse
import signal
import os
from pathlib import Path

def get_project_processes():
    """プロジェクト関連のプロセスを取得"""
    try:
        # プロジェクト関連のプロセスを検索
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )
        
        lines = result.stdout.split('\n')
        processes = []
        
        for line in lines:
            if any(keyword in line for keyword in ['collect', 'analyze', 'dashboard', 'arbitrage']):
                if 'python' in line and 'grep' not in line:
                    parts = line.split()
                    if len(parts) >= 11:
                        processes.append({
                            'pid': int(parts[1]),
                            'cpu': parts[2],
                            'mem': parts[3],
                            'start_time': parts[8],
                            'command': ' '.join(parts[10:])
                        })
        
        return processes
    except subprocess.CalledProcessError:
        return []

def show_status():
    """現在のプロセス状況を表示"""
    processes = get_project_processes()
    
    print("=" * 80)
    print("🔍 仮想通貨アービトラージシステム - プロセス状況")
    print("=" * 80)
    
    if not processes:
        print("✅ 現在実行中のプロセスはありません")
        return
    
    print(f"{'PID':>8} {'CPU':>6} {'MEM':>6} {'開始時刻':>8} {'コマンド':>20}")
    print("-" * 80)
    
    for proc in processes:
        command_short = proc['command'][:50] + "..." if len(proc['command']) > 50 else proc['command']
        print(f"{proc['pid']:>8} {proc['cpu']:>6} {proc['mem']:>6} {proc['start_time']:>8} {command_short}")
    
    print(f"\n合計: {len(processes)}個のプロセスが実行中")

def stop_all_processes():
    """全てのプロジェクト関連プロセスを停止"""
    processes = get_project_processes()
    
    if not processes:
        print("✅ 停止するプロセスはありません")
        return
    
    print(f"🛑 {len(processes)}個のプロセスを停止中...")
    
    for proc in processes:
        try:
            print(f"  PID {proc['pid']} を停止中...")
            os.kill(proc['pid'], signal.SIGTERM)
        except ProcessLookupError:
            print(f"  PID {proc['pid']} は既に停止済み")
        except PermissionError:
            print(f"  PID {proc['pid']} の停止に失敗（権限不足）")
    
    # 少し待って確認
    time.sleep(2)
    remaining = get_project_processes()
    
    if remaining:
        print(f"⚠️  {len(remaining)}個のプロセスが残っています。強制終了を試行...")
        for proc in remaining:
            try:
                os.kill(proc['pid'], signal.SIGKILL)
                print(f"  PID {proc['pid']} を強制終了")
            except ProcessLookupError:
                pass
    else:
        print("✅ 全てのプロセスが停止されました")

def start_data_collection():
    """データ収集を開始"""
    print("📊 データ収集を開始...")
    subprocess.Popen([
        sys.executable, "src/main.py", "collect"
    ], cwd=Path(__file__).parent.parent)
    print("✅ データ収集が開始されました")

def start_analysis():
    """アービトラージ分析を開始"""
    print("🔍 アービトラージ分析を開始...")
    subprocess.Popen([
        sys.executable, "src/main.py", "analyze"
    ], cwd=Path(__file__).parent.parent)
    print("✅ アービトラージ分析が開始されました")

def start_dashboard():
    """ダッシュボードを開始"""
    print("🌐 ダッシュボードを開始...")
    subprocess.Popen([
        sys.executable, "src/main.py", "dashboard"
    ], cwd=Path(__file__).parent.parent)
    print("✅ ダッシュボードが開始されました")
    print("   ブラウザで http://localhost:8501 にアクセス")

def start_monitor():
    """リアルタイム監視を開始"""
    print("📈 リアルタイム監視を開始...")
    script_path = Path(__file__).parent / "monitor_arbitrage.py"
    subprocess.Popen([
        sys.executable, str(script_path)
    ])
    print("✅ リアルタイム監視が開始されました")

def main():
    parser = argparse.ArgumentParser(description="仮想通貨アービトラージシステム タスク管理")
    parser.add_argument("action", choices=[
        "status", "stop", "start-collect", "start-analyze", 
        "start-dashboard", "start-monitor", "start-all"
    ], help="実行するアクション")
    
    args = parser.parse_args()
    
    if args.action == "status":
        show_status()
    elif args.action == "stop":
        stop_all_processes()
    elif args.action == "start-collect":
        start_data_collection()
    elif args.action == "start-analyze":
        start_analysis()
    elif args.action == "start-dashboard":
        start_dashboard()
    elif args.action == "start-monitor":
        start_monitor()
    elif args.action == "start-all":
        print("🚀 全てのサービスを開始...")
        start_data_collection()
        time.sleep(1)
        start_analysis()
        time.sleep(1)
        start_dashboard()
        print("✅ 全てのサービスが開始されました")
        print("   数秒後にプロセス状況を確認...")
        time.sleep(3)
        show_status()

if __name__ == "__main__":
    main()