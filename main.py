import os
import sys
import io

from dotenv import load_dotenv

load_dotenv()

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.data_loader import (
    load_dukascopy_csv,
    resample_to_m15,
)
from src.pinescript_port import PineScriptStrategy


if __name__ == "__main__":
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
    
    # Configure data source
    DUKASCOPY_CSV = os.environ.get("DUKASCOPY_CSV_PATH", "dukascopy_xauusd_m1.csv")
    
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

    print(f"\n=== TRADE DETAILS ===")
    print(f"Total Trades: {len(trades)}")
    print()
    for i, t in enumerate(trades, 1):
        if t.exit_time:
            result = "WIN" if t.pnl > 0 else "LOSS" if t.pnl < 0 else "BE"
            print(
                f"{i:2d}. {t.entry_time.strftime('%Y-%m-%d %H:%M')} -> {t.exit_time.strftime('%Y-%m-%d %H:%M')} | "
                f"Entry: {t.entry_price:7.2f}, Exit: {t.exit_price:7.2f} | "
                f"PnL: {t.pnl:+10,.0f} USD | {result}"
            )
        else:
            print(
                f"{i}. {t.entry_time} (OPEN) | "
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
