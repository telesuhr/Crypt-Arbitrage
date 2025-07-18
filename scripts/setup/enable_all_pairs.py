#!/usr/bin/env python3
"""
全ての可能な通貨ペアの組み合わせを有効化するスクリプト
"""

import sys
import os
from pathlib import Path
import yaml

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import db
from src.database.models import CurrencyPair, Exchange
from loguru import logger
from datetime import datetime, timedelta
from sqlalchemy import func
import pytz


def get_exchange_supported_pairs():
    """各取引所のサポート通貨ペアを取得"""
    with open('config/exchanges.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    exchange_pairs = {}
    
    for exchange_code, settings in config['exchanges'].items():
        if not settings.get('enabled', True):
            continue
            
        supported = settings.get('supported_pairs', [])
        # 標準形式に変換
        normalized_pairs = []
        for pair in supported:
            # アンダースコアをスラッシュに変換し、大文字化
            normalized = pair.replace('_', '/').upper()
            # BCCはBCHに統一（ビットコインキャッシュ）
            if normalized == 'BCC/JPY':
                normalized = 'BCH/JPY'
            normalized_pairs.append(normalized)
        
        exchange_pairs[exchange_code] = normalized_pairs
    
    return exchange_pairs


def analyze_pair_coverage():
    """通貨ペアのカバレッジを分析"""
    exchange_pairs = get_exchange_supported_pairs()
    
    # 全通貨ペアのリストを作成
    all_pairs = set()
    for pairs in exchange_pairs.values():
        all_pairs.update(pairs)
    
    # 各通貨ペアがいくつの取引所でサポートされているか
    pair_coverage = {}
    for pair in all_pairs:
        coverage = []
        for exchange, pairs in exchange_pairs.items():
            if pair in pairs:
                coverage.append(exchange)
        pair_coverage[pair] = coverage
    
    return pair_coverage, exchange_pairs


def check_current_status():
    """現在のデータ収集状況を確認"""
    jst = pytz.timezone('Asia/Tokyo')
    one_hour_ago = datetime.now(jst) - timedelta(hours=1)
    
    with db.get_session() as session:
        pairs = session.query(CurrencyPair).all()
        pair_status = {}
        
        for pair in pairs:
            # 過去1時間のデータ件数を確認
            from src.database.models import PriceTick
            count = session.query(func.count(PriceTick.timestamp)).filter(
                PriceTick.pair_id == pair.id,
                PriceTick.timestamp > one_hour_ago
            ).scalar()
            
            pair_status[pair.symbol] = {
                'id': pair.id,
                'active': pair.is_active,
                'data_count': count
            }
    
    return pair_status


def enable_all_supported_pairs():
    """サポートされている全通貨ペアを有効化"""
    pair_coverage, exchange_pairs = analyze_pair_coverage()
    current_status = check_current_status()
    
    print("📊 通貨ペアのカバレッジ分析")
    print("=" * 70)
    
    # カバレッジ順（多い順）にソート
    sorted_pairs = sorted(pair_coverage.items(), key=lambda x: len(x[1]), reverse=True)
    
    enabled_count = 0
    already_active = 0
    
    with db.get_session() as session:
        for pair_symbol, exchanges in sorted_pairs:
            base, quote = pair_symbol.split('/')
            
            # 現在の状態を確認
            status = current_status.get(pair_symbol, None)
            
            if status and status['active'] and status['data_count'] > 0:
                print(f"✅ {pair_symbol:10} - {len(exchanges)}取引所 - 既に稼働中（{status['data_count']}件/時）")
                already_active += 1
            else:
                # データベースに存在するか確認
                existing = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
                
                if existing:
                    if not existing.is_active:
                        existing.is_active = True
                        print(f"🔄 {pair_symbol:10} - {len(exchanges)}取引所 - 再有効化")
                        enabled_count += 1
                    else:
                        print(f"⚠️  {pair_symbol:10} - {len(exchanges)}取引所 - 有効だがデータなし")
                else:
                    # 新規追加
                    new_pair = CurrencyPair(
                        symbol=pair_symbol,
                        base_currency=base,
                        quote_currency=quote,
                        is_active=True
                    )
                    session.add(new_pair)
                    print(f"➕ {pair_symbol:10} - {len(exchanges)}取引所 - 新規追加")
                    enabled_count += 1
                
                # 対応取引所を表示
                print(f"   対応取引所: {', '.join(exchanges)}")
        
        session.commit()
    
    print("\n" + "=" * 70)
    print(f"📈 結果サマリー:")
    print(f"   既に稼働中: {already_active}ペア")
    print(f"   新規/再有効化: {enabled_count}ペア")
    print(f"   合計: {already_active + enabled_count}ペア")
    
    print("\n🔍 各取引所の対応状況:")
    print("=" * 70)
    
    for exchange, pairs in exchange_pairs.items():
        print(f"{exchange}: {len(pairs)}ペア対応")
        print(f"  {', '.join(sorted(pairs))}")
    
    if enabled_count > 0:
        print("\n⚠️  重要: データ収集を再起動してください！")
        print("1. 現在のデータ収集プロセスを停止")
        print("   Ctrl+C または python scripts/manage_tasks.py stop")
        print("2. データ収集を再開")
        print("   python src/main.py collect")
        print("3. アービトラージ分析も再起動")
        print("   python src/main.py analyze")


def main():
    """メイン関数"""
    print("🚀 全通貨ペアのアービトラージ監視を有効化します")
    print()
    
    try:
        enable_all_supported_pairs()
        
        print("\n💡 アービトラージ機会を増やすヒント:")
        print("1. より多くの通貨ペアを監視することで機会が増加")
        print("2. アルトコインは価格差が大きくなりやすい")
        print("3. 取引量の少ない通貨ほど価格差が発生しやすい")
        print("4. 特にMONA/JPY、LSK/JPYなどは要注目")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()