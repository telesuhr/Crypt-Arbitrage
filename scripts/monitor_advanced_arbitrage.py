#!/usr/bin/env python3
"""
高度なアービトラージ監視スクリプト
あらゆる種類のアービトラージ機会をリアルタイムで検出
"""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import pytz
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analyzers.advanced_arbitrage import advanced_analyzer
from src.database.connection import db
from src.database.models import PriceTick, Exchange, CurrencyPair
from loguru import logger

console = Console()


class AdvancedArbitrageMonitor:
    """高度なアービトラージ監視"""
    
    def __init__(self):
        self.running = True
        self.opportunities = []
        self.price_data = {}
        self.update_interval = 5  # 秒
    
    async def update_data(self):
        """データを更新"""
        while self.running:
            try:
                # 最新の価格データを取得
                self.price_data = await self._fetch_latest_prices()
                
                # アービトラージ機会を分析
                self.opportunities = await advanced_analyzer.analyze_all_opportunities()
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error updating data: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def _fetch_latest_prices(self) -> Dict:
        """最新の価格データを取得"""
        prices = {}
        
        with db.get_session() as session:
            # 主要通貨ペアの最新価格
            pairs = ['BTC/JPY', 'ETH/JPY', 'XRP/JPY', 'BTC/USDT', 'ETH/USDT']
            
            for pair_symbol in pairs:
                pair = session.query(CurrencyPair).filter_by(symbol=pair_symbol).first()
                if not pair:
                    continue
                
                latest_prices = session.query(
                    PriceTick,
                    Exchange.code,
                    Exchange.name
                ).join(
                    Exchange
                ).filter(
                    PriceTick.pair_id == pair.id
                ).order_by(
                    PriceTick.timestamp.desc()
                ).limit(10).all()
                
                prices[pair_symbol] = []
                for tick, code, name in latest_prices:
                    prices[pair_symbol].append({
                        'exchange': name,
                        'code': code,
                        'bid': tick.bid,
                        'ask': tick.ask,
                        'last': tick.last,
                        'timestamp': tick.timestamp
                    })
        
        return prices
    
    def create_display(self) -> Layout:
        """表示レイアウトを作成"""
        layout = Layout()
        
        # ヘッダー
        header = Panel(
            Text("🔄 Advanced Arbitrage Monitor", style="bold cyan", justify="center"),
            title=f"[yellow]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/yellow]"
        )
        
        # メインレイアウト
        layout.split_column(
            Layout(header, size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        # メインセクションを分割
        layout["main"].split_row(
            Layout(name="opportunities", ratio=2),
            Layout(name="prices", ratio=1)
        )
        
        # アービトラージ機会テーブル
        opp_table = self._create_opportunities_table()
        layout["opportunities"].update(Panel(opp_table, title="💰 Arbitrage Opportunities"))
        
        # 価格比較テーブル
        price_table = self._create_price_comparison_table()
        layout["prices"].update(Panel(price_table, title="📊 Price Comparison"))
        
        # フッター情報
        footer_text = self._create_footer_text()
        layout["footer"].update(Panel(footer_text, style="dim"))
        
        return layout
    
    def _create_opportunities_table(self) -> Table:
        """アービトラージ機会のテーブルを作成"""
        table = Table(show_header=True, header_style="bold magenta")
        
        table.add_column("Type", style="cyan", width=12)
        table.add_column("Pair", style="yellow", width=10)
        table.add_column("Buy", style="green", width=15)
        table.add_column("Sell", style="red", width=15)
        table.add_column("Buy Price", justify="right", width=12)
        table.add_column("Sell Price", justify="right", width=12)
        table.add_column("Profit %", justify="right", style="bold", width=10)
        table.add_column("Status", width=10)
        
        # 機会をソート（利益率順）
        sorted_opps = sorted(self.opportunities, key=lambda x: x.get('profit_percentage', 0), reverse=True)
        
        for opp in sorted_opps[:10]:  # 上位10件
            # タイプに応じた色分け
            type_style = "cyan"
            if opp['type'] == 'cross_rate':
                type_style = "magenta"
            elif opp['type'] == 'usd':
                type_style = "blue"
            elif opp['type'] == 'triangle':
                type_style = "yellow"
            
            # 利益率に応じた色
            profit_pct = opp['profit_percentage']
            profit_style = "white"
            status = "Watch"
            
            if profit_pct >= 1.0:
                profit_style = "bold green"
                status = "🔥 HOT"
            elif profit_pct >= 0.5:
                profit_style = "green"
                status = "✅ Good"
            elif profit_pct >= 0.3:
                profit_style = "yellow"
                status = "👀 Check"
            
            table.add_row(
                f"[{type_style}]{opp['type']}[/{type_style}]",
                opp['pair'],
                opp['buy_exchange'],
                opp['sell_exchange'],
                f"¥{opp['buy_price']:,.0f}",
                f"¥{opp['sell_price']:,.0f}",
                f"[{profit_style}]{profit_pct:.2f}%[/{profit_style}]",
                status
            )
        
        if not sorted_opps:
            table.add_row(
                "[dim]No opportunities[/dim]",
                "-", "-", "-", "-", "-", "-", "-"
            )
        
        return table
    
    def _create_price_comparison_table(self) -> Table:
        """価格比較テーブルを作成"""
        table = Table(show_header=True, header_style="bold cyan")
        
        table.add_column("Pair", style="yellow", width=10)
        table.add_column("Exchange", width=12)
        table.add_column("Bid", justify="right", width=12)
        table.add_column("Ask", justify="right", width=12)
        table.add_column("Spread", justify="right", width=8)
        
        # 主要ペアの価格を表示
        for pair, prices in self.price_data.items():
            if not prices:
                continue
                
            # 最初のエントリ
            first = True
            for price in prices[:3]:  # 各ペア最大3取引所
                spread = ((price['ask'] - price['bid']) / price['bid']) * 100
                
                table.add_row(
                    pair if first else "",
                    price['exchange'][:12],
                    f"¥{price['bid']:,.0f}" if 'JPY' in pair else f"${price['bid']:,.2f}",
                    f"¥{price['ask']:,.0f}" if 'JPY' in pair else f"${price['ask']:,.2f}",
                    f"{spread:.2f}%"
                )
                first = False
            
            # セパレータ
            if pair != list(self.price_data.keys())[-1]:
                table.add_row("", "", "", "", "", style="dim")
        
        return table
    
    def _create_footer_text(self) -> Text:
        """フッター情報を作成"""
        text = Text()
        
        # 統計情報
        total_opps = len(self.opportunities)
        hot_opps = len([o for o in self.opportunities if o['profit_percentage'] >= 1.0])
        good_opps = len([o for o in self.opportunities if 0.5 <= o['profit_percentage'] < 1.0])
        
        text.append(f"Total Opportunities: {total_opps} | ", style="dim")
        text.append(f"Hot: {hot_opps} ", style="bold red" if hot_opps > 0 else "dim")
        text.append(f"Good: {good_opps} ", style="green" if good_opps > 0 else "dim")
        text.append("| Press Ctrl+C to exit", style="dim")
        
        return text
    
    async def run(self):
        """監視を実行"""
        # データ更新タスクを開始
        update_task = asyncio.create_task(self.update_data())
        
        try:
            with Live(self.create_display(), refresh_per_second=1, console=console) as live:
                while self.running:
                    live.update(self.create_display())
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping monitor...[/yellow]")
            self.running = False
            update_task.cancel()
            
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            self.running = False
            update_task.cancel()


async def main():
    """メイン処理"""
    console.print("[bold cyan]Starting Advanced Arbitrage Monitor...[/bold cyan]")
    console.print("[dim]Analyzing direct, cross-rate, USD, and triangle arbitrage opportunities[/dim]\n")
    
    # データベース接続確認
    if not db.test_connection():
        console.print("[red]Database connection failed![/red]")
        return
    
    # モニター実行
    monitor = AdvancedArbitrageMonitor()
    await monitor.run()
    
    # クリーンアップ
    db.close()
    console.print("\n[green]Monitor stopped successfully[/green]")


if __name__ == "__main__":
    # ログ設定
    logger.add(
        "logs/advanced_arbitrage_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    asyncio.run(main())