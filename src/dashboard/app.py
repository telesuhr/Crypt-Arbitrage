import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.connection import db
from src.database.models import Exchange, CurrencyPair, PriceTick, ArbitrageOpportunity

# ページ設定
st.set_page_config(
    page_title="Crypto Arbitrage Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# タイトル
st.title("🔄 仮想通貨アービトラージダッシュボード")

# サイドバー
st.sidebar.header("フィルター設定")

# 通貨ペア選択
with db.get_session() as session:
    pairs = session.query(CurrencyPair).filter_by(is_active=True).all()
    pair_options = [pair.symbol for pair in pairs]

selected_pair = st.sidebar.selectbox(
    "通貨ペア",
    pair_options,
    index=0 if "BTC/JPY" not in pair_options else pair_options.index("BTC/JPY")
)

# 時間範囲選択
time_range = st.sidebar.selectbox(
    "時間範囲",
    ["1時間", "6時間", "24時間", "7日間"],
    index=1
)

# 時間範囲を計算
time_ranges = {
    "1時間": timedelta(hours=1),
    "6時間": timedelta(hours=6),
    "24時間": timedelta(days=1),
    "7日間": timedelta(days=7)
}
time_delta = time_ranges[time_range]
jst = pytz.timezone('Asia/Tokyo')
start_time = datetime.now(jst) - time_delta

# 自動更新
auto_refresh = st.sidebar.checkbox("自動更新（10秒）", value=True)
if auto_refresh:
    st.empty()
    import time
    time.sleep(10)
    st.rerun()

# メインコンテンツ
col1, col2, col3 = st.columns(3)

# 現在の価格情報
with col1:
    st.subheader("📊 現在の価格")
    
    with db.get_session() as session:
        # 通貨ペアIDを取得
        pair = session.query(CurrencyPair).filter_by(symbol=selected_pair).first()
        if pair:
            # 各取引所の最新価格を取得
            latest_prices = []
            exchanges = session.query(Exchange).filter_by(is_active=True).all()
            
            for exchange in exchanges:
                # Binanceはスキップ
                if exchange.code == 'binance':
                    continue
                    
                latest_tick = session.query(PriceTick).filter_by(
                    exchange_id=exchange.id,
                    pair_id=pair.id
                ).order_by(PriceTick.timestamp.desc()).first()
                
                if latest_tick and latest_tick.timestamp > datetime.now(jst) - timedelta(minutes=5):
                    latest_prices.append({
                        "取引所": exchange.name,
                        "買値": f"¥{latest_tick.ask:,.0f}",
                        "売値": f"¥{latest_tick.bid:,.0f}",
                        "スプレッド": f"{((latest_tick.ask - latest_tick.bid) / latest_tick.bid * 100):.2f}%"
                    })
            
            if latest_prices:
                df_prices = pd.DataFrame(latest_prices)
                st.dataframe(df_prices, use_container_width=True)
            else:
                # デバッグ情報を追加
                active_exchanges = [e.name for e in exchanges if e.code != 'binance']
                st.info(f"価格データがありません")
                st.caption(f"アクティブな取引所: {', '.join(active_exchanges)}")
                st.caption(f"選択された通貨ペア: {pair.symbol if pair else 'None'}")
                st.caption(f"データ取得時間範囲: 過去5分")

# アービトラージ機会
with col2:
    st.subheader("💰 アービトラージ機会")
    
    with db.get_session() as session:
        if pair:
            # 最新のアービトラージ機会を取得
            opportunities = session.query(
                ArbitrageOpportunity,
                Exchange.name.label('buy_exchange_name'),
                Exchange.name.label('sell_exchange_name')
            ).join(
                Exchange, ArbitrageOpportunity.buy_exchange_id == Exchange.id
            ).filter(
                ArbitrageOpportunity.pair_id == pair.id,
                ArbitrageOpportunity.timestamp > start_time,
                ArbitrageOpportunity.estimated_profit_pct > 0
            ).order_by(
                ArbitrageOpportunity.timestamp.desc()
            ).limit(10).all()
            
            if opportunities:
                arb_data = []
                for opp, buy_ex, sell_ex in opportunities:
                    # 売り取引所の名前を正しく取得
                    sell_exchange = session.query(Exchange).filter_by(
                        id=opp.sell_exchange_id
                    ).first()
                    
                    arb_data.append({
                        "時刻": opp.timestamp.strftime("%H:%M:%S"),
                        "買い": buy_ex,
                        "売り": sell_exchange.name if sell_exchange else "Unknown",
                        "利益率": f"{float(opp.estimated_profit_pct):.2f}%",
                        "状態": opp.status
                    })
                
                df_arb = pd.DataFrame(arb_data)
                st.dataframe(df_arb, use_container_width=True)
            else:
                st.info("アービトラージ機会が見つかりません")

# 統計情報
with col3:
    st.subheader("📈 統計情報")
    
    with db.get_session() as session:
        if pair:
            # アービトラージ統計
            from sqlalchemy import func
            
            stats = session.query(
                func.count(ArbitrageOpportunity.id).label('count'),
                func.avg(ArbitrageOpportunity.estimated_profit_pct).label('avg_profit'),
                func.max(ArbitrageOpportunity.estimated_profit_pct).label('max_profit')
            ).filter(
                ArbitrageOpportunity.pair_id == pair.id,
                ArbitrageOpportunity.timestamp > start_time
            ).first()
            
            if stats and stats.count > 0:
                st.metric("検出機会数", f"{stats.count:,}")
                st.metric("平均利益率", f"{float(stats.avg_profit or 0):.3f}%")
                st.metric("最大利益率", f"{float(stats.max_profit or 0):.3f}%")
            else:
                st.info("統計データがありません")

# 価格チャート
st.subheader("📉 価格推移チャート")

with db.get_session() as session:
    if pair:
        # 価格データを取得
        price_data = []
        
        for exchange in exchanges[:2]:  # 最初の2つの取引所のみ表示
            ticks = session.query(PriceTick).filter(
                PriceTick.exchange_id == exchange.id,
                PriceTick.pair_id == pair.id,
                PriceTick.timestamp > start_time
            ).order_by(PriceTick.timestamp).all()
            
            if ticks:
                for tick in ticks:
                    price_data.append({
                        'timestamp': tick.timestamp,
                        'exchange': exchange.name,
                        'bid': float(tick.bid),
                        'ask': float(tick.ask)
                    })
        
        if price_data:
            df_chart = pd.DataFrame(price_data)
            
            # Plotlyでチャート作成
            fig = go.Figure()
            
            for exchange_name in df_chart['exchange'].unique():
                exchange_data = df_chart[df_chart['exchange'] == exchange_name]
                
                # Bid価格
                fig.add_trace(go.Scatter(
                    x=exchange_data['timestamp'],
                    y=exchange_data['bid'],
                    mode='lines',
                    name=f'{exchange_name} - Bid',
                    line=dict(width=2)
                ))
                
                # Ask価格
                fig.add_trace(go.Scatter(
                    x=exchange_data['timestamp'],
                    y=exchange_data['ask'],
                    mode='lines',
                    name=f'{exchange_name} - Ask',
                    line=dict(width=2, dash='dash')
                ))
            
            fig.update_layout(
                title=f"{selected_pair} 価格推移",
                xaxis_title="時刻",
                yaxis_title="価格 (JPY)",
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("チャートデータがありません")

# アービトラージ機会の分布
st.subheader("🎯 アービトラージ機会の分布")

col1, col2 = st.columns(2)

with col1:
    # 取引所ペア別の機会数
    with db.get_session() as session:
        if pair:
            # 取引所ペア別の集計
            pair_stats = session.query(
                ArbitrageOpportunity.buy_exchange_id,
                ArbitrageOpportunity.sell_exchange_id,
                func.count(ArbitrageOpportunity.id).label('count')
            ).filter(
                ArbitrageOpportunity.pair_id == pair.id,
                ArbitrageOpportunity.timestamp > start_time
            ).group_by(
                ArbitrageOpportunity.buy_exchange_id,
                ArbitrageOpportunity.sell_exchange_id
            ).all()
            
            if pair_stats:
                # 取引所名を取得してデータフレーム作成
                heatmap_data = []
                for buy_id, sell_id, count in pair_stats:
                    buy_ex = session.query(Exchange).filter_by(id=buy_id).first()
                    sell_ex = session.query(Exchange).filter_by(id=sell_id).first()
                    
                    if buy_ex and sell_ex:
                        heatmap_data.append({
                            '買い取引所': buy_ex.name,
                            '売り取引所': sell_ex.name,
                            '機会数': count
                        })
                
                if heatmap_data:
                    df_heatmap = pd.DataFrame(heatmap_data)
                    pivot_table = df_heatmap.pivot(
                        index='買い取引所',
                        columns='売り取引所',
                        values='機会数'
                    ).fillna(0)
                    
                    fig_heatmap = px.imshow(
                        pivot_table,
                        labels=dict(x="売り取引所", y="買い取引所", color="機会数"),
                        title="取引所ペア別アービトラージ機会",
                        color_continuous_scale="Blues"
                    )
                    
                    st.plotly_chart(fig_heatmap, use_container_width=True)

with col2:
    # 利益率の分布
    with db.get_session() as session:
        if pair:
            profit_data = session.query(
                ArbitrageOpportunity.estimated_profit_pct
            ).filter(
                ArbitrageOpportunity.pair_id == pair.id,
                ArbitrageOpportunity.timestamp > start_time,
                ArbitrageOpportunity.estimated_profit_pct > 0
            ).all()
            
            if profit_data:
                profits = [float(p[0]) for p in profit_data]
                
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=profits,
                    nbinsx=30,
                    name='利益率分布'
                ))
                
                fig_hist.update_layout(
                    title="利益率の分布",
                    xaxis_title="利益率 (%)",
                    yaxis_title="頻度",
                    showlegend=False
                )
                
                st.plotly_chart(fig_hist, use_container_width=True)

# フッター
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        Crypto Arbitrage System v0.1.0 | 
        データ更新: リアルタイム | 
        ⚠️ 投資は自己責任で行ってください
    </div>
    """,
    unsafe_allow_html=True
)