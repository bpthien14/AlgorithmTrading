import os
import sys
import io
import argparse
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# LOGGING SETUP
# ============================================================================
class TeeOutput:
    """Ghi output vào cả console và file đồng thời."""
    def __init__(self, file_path):
        self.terminal = sys.stdout
        self.log_file = open(file_path, 'w', encoding='utf-8')
    
    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
    
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
    
    def close(self):
        self.log_file.close()


# Fix encoding for Windows
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.data_loader import (
    load_dukascopy_csv,
    resample_to_m15,
)
from src.pinescript_port import PineScriptStrategy


def calculate_monthly_pnl(trades):
    """
    Tính PnL theo từng tháng từ danh sách trades.
    
    Returns:
        dict: {(year, month): {'pnl': float, 'trades': int, 'wins': int, 'losses': int}}
    """
    monthly_stats = defaultdict(lambda: {'pnl': 0.0, 'trades': 0, 'wins': 0, 'losses': 0})
    
    for trade in trades:
        if trade.exit_time is None:
            continue
        
        # Group by exit time (khi trade đóng)
        year = trade.exit_time.year
        month = trade.exit_time.month
        
        key = (year, month)
        monthly_stats[key]['pnl'] += trade.pnl
        monthly_stats[key]['trades'] += 1
        
        if trade.pnl > 0:
            monthly_stats[key]['wins'] += 1
        elif trade.pnl < 0:
            monthly_stats[key]['losses'] += 1
    
    return dict(monthly_stats)


def print_monthly_pnl(trades, initial_capital):
    """
    In bảng thống kê PnL theo tháng.
    """
    if not trades:
        return
    
    monthly_stats = calculate_monthly_pnl(trades)
    
    if not monthly_stats:
        return
    
    print("\n" + "="*90)
    print("THỐNG KÊ PNL THEO THÁNG")
    print("="*90)
    
    # Sort by year, month
    sorted_months = sorted(monthly_stats.keys())
    
    # Header
    print(f"{'Tháng':<15} {'Trades':>8} {'Win':>6} {'Loss':>6} {'Win%':>7} {'PnL (USD)':>15} {'PnL %':>10}")
    print("-" * 90)
    
    # Running equity để tính % theo equity cuối tháng trước
    running_equity = initial_capital
    total_pnl = 0.0
    
    for year, month in sorted_months:
        stats = monthly_stats[(year, month)]
        
        pnl = stats['pnl']
        trades_count = stats['trades']
        wins = stats['wins']
        losses = stats['losses']
        win_rate = (wins / trades_count * 100) if trades_count > 0 else 0.0
        
        # % tính theo equity đầu tháng
        pnl_pct = (pnl / running_equity * 100) if running_equity > 0 else 0.0
        
        # Month name
        month_name = datetime(year, month, 1).strftime('%Y-%m')
        
        # Color coding
        pnl_sign = '+' if pnl >= 0 else ''
        
        print(
            f"{month_name:<15} "
            f"{trades_count:>8} "
            f"{wins:>6} "
            f"{losses:>6} "
            f"{win_rate:>6.1f}% "
            f"{pnl_sign}{pnl:>14,.0f} "
            f"{pnl_sign}{pnl_pct:>9.2f}%"
        )
        
        running_equity += pnl
        total_pnl += pnl
    
    # Footer
    print("-" * 90)
    
    # Totals
    total_trades = sum(s['trades'] for s in monthly_stats.values())
    total_wins = sum(s['wins'] for s in monthly_stats.values())
    total_losses = sum(s['losses'] for s in monthly_stats.values())
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
    total_pnl_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0
    
    pnl_sign = '+' if total_pnl >= 0 else ''
    
    print(
        f"{'TỔNG':<15} "
        f"{total_trades:>8} "
        f"{total_wins:>6} "
        f"{total_losses:>6} "
        f"{overall_win_rate:>6.1f}% "
        f"{pnl_sign}{total_pnl:>14,.0f} "
        f"{pnl_sign}{total_pnl_pct:>9.2f}%"
    )
    
    print(f"\nVốn đầu:  ${initial_capital:>12,.0f}")
    print(f"Vốn cuối: ${running_equity:>12,.0f}")
    print("="*90)


# ============================================================================
# YEAR-BASED DATA FILE SELECTION
# ============================================================================
AVAILABLE_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


def get_data_file_for_year(year):
    """
    Lấy đường dẫn file data cho năm chỉ định.
    
    Args:
        year: Năm cần backtest (2020-2025), None cho default
    
    Returns:
        str: Đường dẫn đến file CSV
    """
    if year is None:
        # Default: sử dụng env variable hoặc fallback
        return os.environ.get("DUKASCOPY_CSV_PATH", "dukascopy_xauusd_m1.csv")
    
    # Map year to data file
    file_path = f"download/xauusd-m1-bid-{year}-01-01-{year}-12-31.csv"
    return file_path


def parse_args(args=None):
    """
    Parse command line arguments.
    
    Args:
        args: List of arguments (for testing), None to use sys.argv
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Backtest PineScript strategy trên dữ liệu XAUUSD M1',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
Ví dụ sử dụng:
  python main.py                    # Chạy với data mặc định (env DUKASCOPY_CSV_PATH)
  python main.py --year 2022        # Backtest năm 2022
  python main.py --year 2024        # Backtest năm 2024

Các năm có sẵn: {', '.join(map(str, AVAILABLE_YEARS))}
        '''
    )
    
    parser.add_argument(
        '--year',
        type=int,
        default=None,
        choices=AVAILABLE_YEARS,
        help=f'Năm để backtest ({min(AVAILABLE_YEARS)}-{max(AVAILABLE_YEARS)}), không chỉ định = dùng file mặc định'
    )
    
    return parser.parse_args(args)


if __name__ == "__main__":
    # ============================================================================
    # ARGUMENT PARSING
    # ============================================================================
    args = parse_args()
    
    # ============================================================================
    # LOGGING SETUP
    # ============================================================================
    # Create output directory if not exists
    os.makedirs('output', exist_ok=True)
    
    # Generate log filename with timestamp and year
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    year_suffix = f"_year{args.year}" if args.year else ""
    log_file_path = f"output/backtest_{timestamp}{year_suffix}.log"
    
    # Setup TeeOutput to log to both console and file
    tee = TeeOutput(log_file_path)
    sys.stdout = tee
    
    # Print header
    print(f"📝 Logging to: {log_file_path}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.year:
        print(f"📅 Backtesting year: {args.year}")
    print("=" * 90)
    print()
    
    # ============================================================================
    # DUKASCOPY DATA CONFIGURATION
    # ============================================================================
    # Dukascopy provides FREE institutional-grade XAUUSD data (May 2003 - Present)
    # 
    # Download options:
    # 1. Via dukascopy-node CLI (recommended):
    #    npx dukascopy-node -i xauusd -from 2024-01-01 -to 2024-12-31 -t m1 -f csv
    # 
    # 2. Via Dukascopy web interface:
    #    https://www.dukascopy.com/swiss/english/marketwatch/historical/
    # 
    # 3. Place downloaded CSV in project directory and update path below
    # ============================================================================
    
    # Configure data source based on year argument
    DUKASCOPY_CSV = get_data_file_for_year(args.year)
    
    # Try Dukascopy first, fallback to legacy OANDA CSV if not found
    if os.path.exists(DUKASCOPY_CSV):
        print(f"Loading XAUUSD M1 data from Dukascopy CSV: {DUKASCOPY_CSV}")
        m1_data = load_dukascopy_csv(DUKASCOPY_CSV)
    else:
        # Fallback to legacy OANDA CSV for backward compatibility
        legacy_csv = "OANDA_XAUUSD, 1.csv"
        if os.path.exists(legacy_csv):
            print(f"Dukascopy CSV not found. Using legacy OANDA CSV: {legacy_csv}")
            from src.data_loader import load_oanda_xauusd_m1
            m1_data = load_oanda_xauusd_m1(legacy_csv)
        else:
            print(f"\n⚠️  No data file found!")
            print(f"\nPlease download XAUUSD M1 data from Dukascopy:")
            print(f"  1. Install dukascopy-node: npm install -g dukascopy-node")
            print(f"  2. Download data: npx dukascopy-node -i xauusd -from 2024-01-01 -to 2024-12-31 -t m1 -f csv")
            print(f"  3. Rename file to: {DUKASCOPY_CSV}")
            print(f"\nOr set custom path: set DUKASCOPY_CSV_PATH=path/to/your/file.csv")
            raise SystemExit("No data source available.")

    if m1_data.empty:
        raise SystemExit("No M1 data loaded. Check data source / file path / format.")

    print("Resampling M1 -> M15 ...")
    m15_data = resample_to_m15(m1_data)

    print("Running PineScript 1-1 port strategy backtest (M1/M15 CSV)...")
    strat = PineScriptStrategy(m1_data=m1_data, m15_data=m15_data)
    trades = strat.run()

    # ============================================================================
    # MONTHLY PNL STATISTICS
    # ============================================================================
    print_monthly_pnl(trades, strat.initial_capital)
    
    # ============================================================================
    # PAPER TRADE MODE STATISTICS
    # ============================================================================
    if strat.config.enable_paper_mode:
        paper = strat.paper_state
        print(f"\n=== PAPER TRADE MODE STATISTICS ===")
        print(f"Paper Mode Enabled: Yes")
        print(f"Trigger: {strat.config.paper_trigger_consecutive_losses} consecutive losses OR win rate < {strat.config.paper_trigger_win_rate_threshold*100:.0f}%")
        print(f"Recovery: Paper PnL > 0 AND {strat.config.paper_recovery_min_wins} consecutive wins")
        print()
        print(f"Paper Mode Activations: {paper.activation_count}")
        print(f"Total Time in Paper Mode: {paper.total_time_in_paper_minutes:.0f} minutes ({paper.total_time_in_paper_minutes/60:.1f} hours)")
        print(f"Paper Trades: {len(paper.paper_trades)}")
        print(f"Paper PnL (Last Session): {paper.paper_pnl:+.0f} USD")
        
        if len(paper.paper_trades) > 0:
            paper_wins = sum(1 for t in paper.paper_trades if t.pnl > 0)
            paper_losses = sum(1 for t in paper.paper_trades if t.pnl < 0)
            paper_total_pnl = sum(t.pnl for t in paper.paper_trades)
            paper_win_rate = paper_wins / len(paper.paper_trades) * 100
            print(f"Paper Win Rate: {paper_win_rate:.1f}% ({paper_wins}W / {paper_losses}L)")
            print(f"Paper Total PnL: {paper_total_pnl:+.0f} USD (potential losses avoided)")
        print()
    
    # ============================================================================
    # TRADE DETAILS (Bangkok Time: UTC+7)
    # ============================================================================
    print(f"\n=== TRADE DETAILS (Bangkok Time: UTC+7) ===")
    print(f"Total Trades: {len(trades)}")
    print()
    for i, t in enumerate(trades, 1):
        if t.exit_time:
            # Convert UTC timestamps to Bangkok time for display
            entry_bkk = t.entry_time.tz_localize('UTC').tz_convert('Asia/Bangkok')
            exit_bkk = t.exit_time.tz_localize('UTC').tz_convert('Asia/Bangkok')
            result = "WIN" if t.pnl > 0 else "LOSS" if t.pnl < 0 else "BE"
            print(
                f"{i:2d}. {entry_bkk.strftime('%Y-%m-%d %H:%M')} -> {exit_bkk.strftime('%Y-%m-%d %H:%M')} (+07) | "
                f"Entry: {t.entry_price:7.2f}, Exit: {t.exit_price:7.2f} | "
                f"PnL: {t.pnl:+10,.0f} USD | {result}"
            )
        else:
            # For open trades, also convert to Bangkok time
            entry_bkk = t.entry_time.tz_localize('UTC').tz_convert('Asia/Bangkok')
            print(
                f"{i}. {entry_bkk.strftime('%Y-%m-%d %H:%M')} (+07) (OPEN) | "
                f"Entry: {t.entry_price:.2f}, SL: {t.stop_loss:.2f}, TP: {t.take_profit:.2f}"
            )
    
    # ============================================================================
    # AUTO VISUALIZATION
    # ============================================================================
    if len(trades) > 0:
        print("\n" + "="*80)
        print("CREATING BACKTEST VISUALIZATION")
        print("="*80)
        
        try:
            import matplotlib.pyplot as plt
            from visualize_backtest import create_visualization
            
            create_visualization(trades, strat.equity_curve, strat.initial_capital)
            print("✅ Visualization completed!")
            
        except ImportError:
            print("⚠️  matplotlib chưa được cài đặt.")
            print("   Để vẽ chart, chạy: pip install matplotlib")
        except Exception as e:
            print(f"⚠️  Lỗi khi tạo visualization: {e}")
    else:
        print("\n⚠️  Không có trade nào để visualize.")
    
    # ============================================================================
    # CLEANUP & FOOTER
    # ============================================================================
    print("\n" + "="*80)
    print("✅ BACKTEST HOÀN TẤT")
    print("="*80)
    print()
    print(f"📝 Log file saved to: {log_file_path}")
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Close log file
    tee.close()
