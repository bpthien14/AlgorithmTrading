"""
Vẽ chart phân tích kết quả backtest
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import sys
import io
import os

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import strategy
from src.pinescript_port import PineScriptStrategy
from src.strategy_config import StrategyConfig
from src.data_loader import load_dukascopy_csv

def create_visualization(trades, equity_curve, initial_capital):
    """Tạo các chart phân tích"""
    
    # Setup figure với 6 subplots
    fig = plt.figure(figsize=(16, 12))
    
    # 1. Equity Curve
    ax1 = plt.subplot(3, 2, 1)
    times = [t.entry_time for t in trades]
    equities = equity_curve[:len(trades)+1]
    
    ax1.plot(equities, linewidth=2, color='#2E86AB')
    ax1.axhline(y=initial_capital, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    ax1.fill_between(range(len(equities)), initial_capital, equities, 
                      where=[e >= initial_capital for e in equities], 
                      alpha=0.3, color='green', label='Profit')
    ax1.fill_between(range(len(equities)), initial_capital, equities, 
                      where=[e < initial_capital for e in equities], 
                      alpha=0.3, color='red', label='Loss')
    ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Trade Number')
    ax1.set_ylabel('Equity ($)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # 2. Drawdown Chart
    ax2 = plt.subplot(3, 2, 2)
    peak = initial_capital
    drawdowns = []
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = ((eq - peak) / peak) * 100
        drawdowns.append(dd)
    
    ax2.fill_between(range(len(drawdowns)), 0, drawdowns, alpha=0.5, color='red')
    ax2.plot(drawdowns, linewidth=2, color='darkred')
    ax2.set_title('Drawdown (%)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Trade Number')
    ax2.set_ylabel('Drawdown (%)')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    # 3. PnL Distribution
    ax3 = plt.subplot(3, 2, 3)
    pnls = [t.pnl for t in trades]
    colors = ['green' if p > 0 else 'red' for p in pnls]
    ax3.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax3.set_title('PnL per Trade', fontsize=14, fontweight='bold')
    ax3.set_xlabel('Trade Number')
    ax3.set_ylabel('PnL ($)')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Win/Loss Analysis
    ax4 = plt.subplot(3, 2, 4)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [abs(t.pnl) for t in trades if t.pnl < 0]
    
    data_to_plot = [wins, losses]
    labels = [f'Wins ({len(wins)})', f'Losses ({len(losses)})']
    colors_box = ['green', 'red']
    
    bp = ax4.boxplot(data_to_plot, tick_labels=labels, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors_box):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    
    ax4.set_title('Win/Loss Distribution', fontsize=14, fontweight='bold')
    ax4.set_ylabel('Amount ($)')
    ax4.grid(True, alpha=0.3, axis='y')
    
    # 5. Cumulative PnL
    ax5 = plt.subplot(3, 2, 5)
    cumulative_pnl = []
    cum = 0
    for t in trades:
        cum += t.pnl
        cumulative_pnl.append(cum)
    
    ax5.plot(cumulative_pnl, linewidth=2, color='#A23B72')
    ax5.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax5.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl,
                      where=[c >= 0 for c in cumulative_pnl],
                      alpha=0.3, color='green')
    ax5.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl,
                      where=[c < 0 for c in cumulative_pnl],
                      alpha=0.3, color='red')
    ax5.set_title('Cumulative PnL', fontsize=14, fontweight='bold')
    ax5.set_xlabel('Trade Number')
    ax5.set_ylabel('Cumulative PnL ($)')
    ax5.grid(True, alpha=0.3)
    
    # 6. Statistics Summary
    ax6 = plt.subplot(3, 2, 6)
    ax6.axis('off')
    
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t.pnl > 0])
    losing_trades = len([t for t in trades if t.pnl < 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_profit = sum([t.pnl for t in trades if t.pnl > 0])
    total_loss = sum([t.pnl for t in trades if t.pnl < 0])
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else 0
    
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    final_equity = equities[-1]
    total_pnl = final_equity - initial_capital
    total_return = (total_pnl / initial_capital) * 100
    
    max_dd = min(drawdowns)
    
    stats_text = f"""
STATISTICS SUMMARY
{'='*40}

OVERVIEW:
  Initial Capital:    ${initial_capital:,.0f}
  Final Equity:       ${final_equity:,.0f}
  Total PnL:          ${total_pnl:+,.0f} ({total_return:+.2f}%)

TRADES:
  Total Trades:       {total_trades}
  Winning Trades:     {winning_trades}
  Losing Trades:      {losing_trades}
  Win Rate:           {win_rate:.2f}%

PROFIT/LOSS:
  Total Profit:       ${total_profit:+,.0f}
  Total Loss:         ${total_loss:,.0f}
  Profit Factor:      {profit_factor:.2f}
  Avg Win:            ${avg_win:+,.0f}
  Avg Loss:           ${avg_loss:,.0f}
  Avg Win/Loss:       {abs(avg_win/avg_loss):.2f}x

RISK:
  Max Drawdown:       {max_dd:.2f}%
  Largest Win:        ${max(pnls):+,.0f}
  Largest Loss:       ${min(pnls):,.0f}
    """
    
    ax6.text(0.1, 0.5, stats_text, fontsize=10, family='monospace',
             verticalalignment='center', bbox=dict(boxstyle='round', 
             facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    
    # Save
    output_file = 'backtest_analysis.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Chart đã được lưu: {output_file}")
    
    # Show
    plt.show()

def main():
    print("Loading data...")
    
    # Load data
    csv_path = os.environ.get("DUKASCOPY_CSV_PATH", "dukascopy_xauusd_m1.csv")
    
    if not os.path.exists(csv_path):
        print(f"❌ File không tồn tại: {csv_path}")
        print("Vui lòng đảm bảo file data đã được download.")
        return
    
    # Load M1 data
    from src.data_loader import resample_to_m15
    m1_df = load_dukascopy_csv(csv_path)
    
    if m1_df.empty:
        print("❌ Không load được data.")
        return
    
    print("Resampling M1 -> M15...")
    m15_df = resample_to_m15(m1_df)
    
    print("Running backtest...")
    config = StrategyConfig()
    strat = PineScriptStrategy(m1_data=m1_df, m15_data=m15_df, config=config)
    trades = strat.run()
    
    print(f"\n✅ Backtest completed! Total trades: {len(trades)}")
    
    if len(trades) == 0:
        print("❌ Không có trade nào. Không thể vẽ chart.")
        return
    
    print("\nCreating visualization...")
    create_visualization(trades, strat.equity_curve, strat.initial_capital)

if __name__ == "__main__":
    main()
