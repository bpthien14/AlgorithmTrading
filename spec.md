# XAUUSD Trading Algorithm - Technical Specification

## 1. Project Overview

**Project Name**: AlgorithmTrading - XAUUSD Pine Script to Python Port

**Purpose**: A Python implementation of the "Tổng - dời SL 05R - Đã Visual" Pine Script trading strategy for backtesting XAUUSD (Gold) trading on multi-timeframe (M1/M15) data.

**Version**: 1.0

**Last Updated**: February 6, 2026

---

## 2. Executive Summary

This project is a complete 1-to-1 port of a complex Pine Script trading strategy from TradingView to Python. The strategy operates on **M1 (1-minute)** price data while utilizing **M15 (15-minute)** indicators and structural analysis to identify:

- **Supply/Demand Zones** (Market Structure Cases)
- **Liquidity Sweep Points** (Swing highs/lows)
- **Major MTF Pivot Levels** (Multi-timeframe support/resistance)
- **Buy/Sell Bases** (Entry trigger zones)
- **Filtered Entry Conditions** (ADX, Time filters, Touch counts)

The strategy is **state-heavy**, requiring persistent tracking of zones, touches, timeouts, and complex pattern recognition across multiple bars.

---

## 3. Technical Architecture

### 3.1. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   main.py                           │
│  (Entry point, data source configuration)          │
└──────────────┬──────────────────────────────────────┘
               │
               ├─> src/data_loader.py
               │   - Load CSV (OANDA)
               │   - Fetch Yahoo Finance (GC=F)
               │   - Fetch Twelve Data API (XAU/USD)
               │   - Resample M1 → M15
               │
               ├─> src/pinescript_port.py
               │   - PineScriptStrategy (main backtest engine)
               │   - LongState (state management)
               │   - Trade execution & management
               │   - Pattern recognition logic
               │
               └─> src/models.py
                   - Data structures:
                     * Candle, Box, TradingZone
                     * BuySellBase, DemandSupplyZone
                     * LiquidityPoint, MajorLevel
                     * Trade, TradeDirection, ZoneType
```

### 3.2. Core Components

#### 3.2.1. Data Layer (`src/data_loader.py`)

**Purpose**: Data acquisition and preprocessing

**Functions**:

- `load_dukascopy_csv(filepath)` - Load M1 data from Dukascopy CSV (primary source)
- `fetch_dukascopy_xauusd(start_date, end_date, timeframe)` - Fetch historical data from Dukascopy API
- `load_oanda_xauusd_m1(filepath)` - Load M1 data from OANDA CSV (legacy support)
- `load_oanda_xauusd_240(filepath)` - Load H4 data (for future MTF analysis)
- `resample_to_m15(df_m1)` - Resample M1 OHLCV to M15 intervals
- `align_mtf_data(df_m1, df_m15)` - Align M15 data to M1 index with forward-fill

**Data Format**:

```python
DataFrame with DatetimeIndex:
  - timestamp (index): pd.Timestamp (UTC, tz-naive)
  - open: float
  - high: float
  - low: float
  - close: float
  - volume: float
```

#### 3.2.2. Model Layer (`src/models.py`)

**Purpose**: Define data structures for strategy entities

**Key Classes**:

1. **`Candle`** (frozen dataclass)
   - Immutable OHLCV representation
   - Used for M15 buffer storage

2. **`Box`** (base dataclass)
   - Generic price zone with top/bottom boundaries
   - Methods: `contains_price()`, `mark_touched()`, `deactivate()`
   - Properties: id (UUID), touch_count, is_active, timeout counters

3. **`DemandSupplyZone(Box)`**
   - Market structure zones (Supply/Demand)
   - Type: `ZoneType.DEMAND` or `ZoneType.SUPPLY`
   - Methods: `is_broken_by()`, `register_touch()`

4. **`BuySellBase(Box)`**
   - Entry trigger zones
   - Direction: `TradeDirection.BUY` or `TradeDirection.SELL`
   - Max touches & age tracking

5. **`LiquidityPoint`**
   - Swing high/low markers ("Magnet"/"Clover")
   - Properties: price, timestamp, is_buy_liquidity

6. **`MajorLevel`**
   - MTF pivot levels (Lv1/Lv2 from higher timeframes)

7. **`Trade`**
   - Trade record with entry/exit data
   - Properties: entry_time, exit_time, direction, entry_price, exit_price, stop_loss, take_profit, lot_size, pnl

**Enums**:

- `ZoneType`: SUPPLY, DEMAND
- `TradeDirection`: BUY, SELL

#### 3.2.3. Strategy Engine (`src/pinescript_port.py`)

**Purpose**: 1-to-1 port of Pine Script strategy logic

**Main Classes**:

1. **`LongState`** (dataclass)
   - Persistent state for Long (Buy) side
   - M15 buffers: `m15_opens`, `m15_closes`, `m15_highs`, `m15_lows` (deque, maxlen=7)
   - Zone arrays: `arrayBoxDem`, `arrayBoxBuyBase`
   - Liquidity arrays: `arrayBuyLiquidity`, `arrayHighGiaNenGiam`
   - State flags: `demand_finding_buy_base`, `liquid_finding_buy_base`, `finding_entry_buy`, etc.
   - Position tracking: `in_position`, `entry_price`, `stop_loss`, `take_profit`, `entry_time`
   - Timers: `finding_entry_buy_time_out`, `muoi_bay_phut_time_out`, etc.

2. **`PineScriptStrategy`**
   - Main backtest engine
   - Methods:
     - `run()` - Bar-by-bar backtest loop on M1 data
     - `_update_m15_buffer()` - Synchronize M15 candles
     - `_detect_red_candle()` - Store bearish candle highs for base formation
     - `_manage_demand_zones()` - Touch/break/timeout logic
     - `_check_buy_liquidity_crossed()` - Activate base-finding when liquidity swept
     - `_create_buy_base_from_liquidity()` - Pattern recognition for base from liquidity
     - `_create_buy_base_from_demand()` - Pattern recognition for base from demand
     - `_manage_buy_base_timeout()` - Remove expired bases
     - `_check_buy_base_touched()` - Trigger entry search on base retest
     - `_calculate_adx()` - ADX indicator calculation (14-period)
     - `_entry_long()` - Entry logic with filters (ADX < 30, time range, position sizing)
     - `_manage_position()` - TP/SL management, trailing stop (0.5R)
   - ADX State: Custom implementation matching Pine Script's RMA smoothing

---

## 4. Strategy Logic Specification

### 4.1. Multi-Timeframe Data Flow

```
M1 Data → Bar-by-bar iteration
    ↓
M15 Data → Resampled & buffered (last 7 candles)
    ↓
Pattern Recognition on M15 structure
    ↓
Entry Signals executed on M1 bars
```

**Critical**: M15 candles are considered "closed" when M1 timestamp advances beyond the 15-minute boundary. The strategy uses M15 structure but enters/exits on M1 precision.

### 4.2. Core Strategy Flow

```
1. M15 STRUCTURE ANALYSIS
   ├─> Identify Demand Zones (Case 2/4/5 patterns)
   └─> Create Liquidity Points (Swing lows)

2. LIQUIDITY SWEEP
   ├─> Price crosses Buy Liquidity
   └─> Activate: liquid_finding_buy_base = True

3. BASE FORMATION
   ├─> Specific candle patterns form "Buy Base"
   └─> Store in arrayBoxBuyBase

4. BASE RE-TEST
   ├─> Price touches Buy Base zone
   └─> Activate: finding_entry_buy = True

5. ENTRY FILTERS
   ├─> ADX < 30 (no strong trend)
   ├─> Within time range (configurable)
   ├─> Timeout counters < max
   └─> Position size calculation

6. ENTRY EXECUTION
   ├─> Place trade at current close
   ├─> Set SL/TP (risk-reward ratio)
   └─> Track position

7. POSITION MANAGEMENT
   ├─> Check TP/SL hit
   ├─> Trailing stop at 0.5R profit
   └─> Close & record trade
```

### 4.3. Pattern Recognition ("Cases")

The strategy identifies specific M15 candle patterns to create Demand Zones:

**Case 2 (Reversal)**:

```
Conditions (simplified):
- c[-2]: Red candle (open > close) with weak body
- c[-1]: Green candle (open < close) engulfing c[-2]
- c[-1].close > c[-2].high
- c[-2].low < c[-1].low
- Specific ratio conditions on wick/body sizes
```

**Case 4 (Structure Break)**:

- Price breaks through multiple prior candles
- Strong momentum continuation

**Case 5 (Continuation)**:

- Momentum-based zone creation
- Follow-through from existing structure

### 4.4. Zone Management Rules

**Demand Zones**:

- **Created**: When Case pattern confirmed on M15 close
- **Boundaries**: Top = c[-2].high, Bottom = c[-1].low (varies by case)
- **Touch Detection**: M1 low enters zone → increment touch_count
- **Break**: M1 low < zone.bottom → deactivate
- **Timeout**: > 20 bars (approximately 17-20 minutes) → deactivate
- **Max Touches**: Typically 2-3 touches before invalidation

**Buy Bases**:

- **Created**: After liquidity sweep or demand touch, specific pattern forms
- **Boundaries**: Based on recent red candle high and pattern structure
- **Touch**: Triggers `finding_entry_buy = True`
- **Timeout**: Managed separately with counter thresholds

**Liquidity Points**:

- **Created**: M15 swing low (c[-2].low < c[-1].low AND c[-2].low < c[-3].low)
- **Sweep**: M1 low < liquidity_price
- **Removed**: After sweep (single use)

### 4.5. ADX Calculation

Custom implementation matching Pine Script's `ta.adx()`:

```python
TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
+DM = max(high - prev_high, 0) if > -DM else 0
-DM = max(prev_low - low, 0) if > +DM else 0

Smoothed TR  = RMA(TR, 14)
Smoothed +DM = RMA(+DM, 14)
Smoothed -DM = RMA(-DM, 14)

+DI = 100 * Smoothed +DM / Smoothed TR
-DI = 100 * Smoothed -DM / Smoothed TR

DX = 100 * abs(+DI - -DI) / (+DI + -DI)
ADX = RMA(DX, 14)

Where RMA (Running Moving Average) = EMA with alpha = 1/length
```

**Filter**: Entry only when `ADX < 30` (low trend strength, favors ranging conditions)

### 4.6. Entry Logic Detail

```python
if finding_entry_buy:
    # Tăng timeout counters
    finding_entry_buy_time_out += 1
    finding_entry_buy_ten_minutes += 1

    # Kiểm tra điều kiện entry
    if (ADX < 30
        and is_within_timerange(current_time)
        and finding_entry_buy_time_out >= 3
        and finding_entry_buy_ten_minutes <= 10
        and not in_position):

        # Position sizing (% of equity)
        lot_size = equity * risk_percent / (entry_price - stop_loss)

        # Execute entry
        entry_price = close
        stop_loss = buy_base.bottom
        take_profit = entry_price + 2 * (entry_price - stop_loss)  # 2R target

        in_position = True
        entry_time = current_timestamp
```

### 4.7. Position Management

**Take Profit**: 2R (Risk-Reward ratio of 1:2)

- TP = Entry + 2 \* (Entry - SL)

**Stop Loss**: Below Buy Base bottom

- Initial SL = Base.bottom
- **Trailing**: When profit >= 0.5R, move SL to Entry (breakeven)

**Exit Conditions**:

1. High >= Take Profit → Exit at TP
2. Low <= Stop Loss → Exit at SL
3. Trailing stop triggered → Exit at adjusted SL

---

## 5. File Structure

```
AlgorithmTrading/
│
├── main.py                          # Entry point, data source config
├── requirements.txt                 # Python dependencies
├── research.md                      # Original strategy analysis & specs
├── spec.md                          # This document
├── pinescriptStrategy.txt           # Original Pine Script code (2358 lines)
│
├── OANDA_XAUUSD, 1.csv             # Sample M1 data from OANDA
├── output.txt                       # (Likely backtest output)
│
├── check_zone_touch.py             # Utility: Debug zone touch detection
├── compare_oanda_twelvedata.py     # Utility: Compare data sources
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py              # Data acquisition & resampling
│   ├── models.py                   # Data structures & entities
│   ├── pinescript_port.py          # Core strategy engine (1126 lines)
│   └── strategy.py                 # (Incomplete/alternative engine draft)
│
└── tests/
    ├── __init__.py
    └── test_indicators.py          # (Empty - test suite placeholder)
```

---

## 6. Dependencies

### 6.1. Python Requirements (`requirements.txt`)

```
pandas          # Data manipulation, time series
pandas_ta       # Technical indicators (if used for RSI/other)
numpy           # Numerical operations
requests        # HTTP requests (Dukascopy API)
python-dotenv   # Environment variable management
```

**Optional (for automated Dukascopy downloads)**:

```bash
npm install -g dukascopy-node  # Node.js CLI tool for Dukascopy data
```

### 6.2. External Data Sources

#### Primary Source: **Dukascopy** (Recommended) ✅

- **Provider**: Dukascopy Bank SA (Swiss)
- **Symbol**: `XAUUSD` (Gold vs US Dollar)
- **Cost**: **100% FREE**
- **Data Quality**: Institutional-grade (widely considered the gold standard)
- **Historical Range**: May 2003 - Present (22+ years)
- **Resolution**: Tick, M1, M5, M15, M30, H1, H4, D1, MN1
- **Format**: CSV or JSON
- **Access Methods**:
  1. **CLI** (Recommended): `npx dukascopy-node -i xauusd -from 2024-01-01 -to 2024-12-31 -t m1 -f csv`
  2. **Web Interface**: https://www.dukascopy.com/swiss/english/marketwatch/historical/
  3. **Python Library**: Custom wrapper or API integration
- **Advantages**:
  - No API keys or rate limits
  - Download once, use forever (offline backtesting)
  - Consistent, reproducible results
  - Minimal data gaps
  - Trusted by quant community

#### Legacy Support: **OANDA CSV Export**

- **Format**: `time` (epoch seconds), `open`, `high`, `low`, `close`, `Volume`
- **Resolution**: M1, H4
- **Example**: `OANDA_XAUUSD, 1.csv`
- **Status**: Supported for backward compatibility with existing CSV files

---

## 7. Configuration & Usage

### 7.1. Environment Variables (`.env`)

```bash
# Dukascopy CSV Path (optional - defaults to dukascopy_xauusd_m1.csv)
DUKASCOPY_CSV_PATH=path/to/your/dukascopy_data.csv
```

### 7.2. Running the Backtest

**Step 1: Download Dukascopy Data**

```powershell
# Install dukascopy-node (one-time setup)
npm install -g dukascopy-node

# Download XAUUSD M1 data (example: 1 year)
npx dukascopy-node -i xauusd -from 2024-01-01 -to 2024-12-31 -t m1 -f csv

# Rename downloaded file
Rename-Item "xauusd-2024-01-01-2024-12-31-m1.csv" "dukascopy_xauusd_m1.csv"
```

**Step 2: Run Backtest**

```powershell
python main.py
```

**Custom CSV Path** (optional):

```powershell
$env:DUKASCOPY_CSV_PATH="path\to\your\data.csv"
python main.py
```

**Expected Output**:

```
Loading XAUUSD M1 data from Dukascopy CSV: dukascopy_xauusd_m1.csv
Resampling M1 -> M15 ...
Running PineScript 1-1 port strategy backtest (M1/M15 CSV)...
[PineScriptStrategy] Starting backtest...
[2026-02-01 10:30:00] Demand Zone created! Total: 1
[2026-02-01 11:15:00] Buy Base created from Liquidity! Top=2678.50, Bottom=2675.20
[2026-02-01 11:45:00] Buy Base touched! finding_entry_buy = True
[2026-02-01 11:47:00] ENTRY LONG @ 2676.30, SL=2675.20, TP=2678.50

=== BACKTEST RESULTS ===
Total trades: 3
1. 2026-02-01 11:47:00 -> 2026-02-01 12:15:00 | Entry: 2676.30, SL: 2675.20, TP: 2678.50, Exit: 2678.50, PnL: 45000.00
...
```

### 7.3. Utility Scripts

**Check Zone Touch** (`check_zone_touch.py`):

```powershell
python check_zone_touch.py
```

- Manually verify if price touched a specific zone in CSV data
- Used for debugging zone detection logic

---

## 8. Implementation Notes

### 8.1. State Management

The strategy is **heavily stateful**, requiring careful management of:

- **Zone Arrays**: Active demand zones, buy bases, liquidity points
- **Touch Counters**: Per-zone touch tracking
- **Timeout Counters**: Bar-based expiration tracking
- **State Flags**: Boolean switches for logic branches (e.g., `liquid_finding_buy_base`)
- **M15 Buffers**: Circular buffers (deque) of recent M15 candles

**Critical**: Each M1 bar must update all state variables in correct order to match Pine Script behavior.

### 8.2. M15 Synchronization

**Challenge**: Pine Script's `request.security()` seamlessly fetches MTF data. Python requires explicit synchronization.

**Solution**:

1. Resample M1 → M15 using pandas
2. Track M15 index separately (`self.m15_idx`)
3. On each M1 bar, check if new M15 closed (`m15_ts <= current_ts`)
4. Append to M15 buffer (deque with maxlen=7)
5. Run M15-based logic (pattern recognition)

### 8.3. Pattern Recognition Complexity

The original Pine Script contains **hundreds of lines** of intricate candle pattern logic with nested conditions. The Python port:

- Translates conditions **exactly** (no optimization yet)
- Uses M15 buffer indexing: `c[-1]`, `c[-2]`, `c[-3]` → `deque[-1]`, `deque[-2]`, `deque[-3]`
- Maintains multiple "Case" checks per bar

**Performance**: Not yet optimized. Future work could vectorize some checks.

### 8.4. ADX Custom Implementation

Pine Script's `ta.adx()` uses specific RMA (Running Moving Average) smoothing. Standard Python libraries (pandas_ta, ta-lib) may differ slightly. This port implements custom ADX matching Pine's algorithm exactly.

### 8.5. Time Zone Handling

- **OANDA CSV**: Epoch seconds → UTC datetime (tz-naive)
- **Yahoo Finance**: Returns tz-aware data → converted to tz-naive UTC
- **Twelve Data**: ISO8601 strings → parsed to tz-naive UTC

**Critical**: All timestamps must be tz-naive UTC for consistent alignment.

### 8.6. Known Limitations

1. **Long Only**: Current port only implements Long (Buy) side. Short (Sell) side logic exists in Pine Script but not yet ported.

2. **Single Position**: Strategy handles only 1 open position at a time (no pyramiding).

3. **No Commission/Slippage**: Backtest assumes perfect fills at close price. Real fills would require:
   - Bid/Ask spread modeling
   - Slippage estimation
   - Commission fees

4. **Data Gaps**: Yahoo Finance and Twelve Data may have gaps during market close hours. Strategy does not explicitly handle gap logic.

5. **Performance**: Bar-by-bar iteration on large M1 datasets (millions of bars) can be slow. No vectorization yet.

6. **Incomplete Tests**: `tests/test_indicators.py` is a placeholder. No unit/integration tests written.

---

## 9. Data Source Migration

### 9.1. Why Dukascopy?

The strategy has been migrated from mixed data sources to **Dukascopy** as the primary source:

**Previous Setup** (Deprecated):

- OANDA CSV (manual export, limited range)
- Yahoo Finance (API unreliable, max 7 days M1)
- Twelve Data (paid API, rate limits)

**Current Setup** (Dukascopy):

- ✅ **FREE** institutional-grade data
- ✅ **22+ years** of history (2003-present)
- ✅ **Consistent** and reproducible
- ✅ **No API keys** or rate limits
- ✅ **Offline** backtesting capability
- ✅ **Tick-level precision** (aggregate to any timeframe)

### 9.2. Data Quality Comparison

| Aspect          | Dukascopy     | OANDA          | Yahoo          | Twelve Data   |
| --------------- | ------------- | -------------- | -------------- | ------------- |
| **Cost**        | Free          | Free (manual)  | Free           | $79/mo        |
| **History**     | 22+ years     | Limited export | 7 days M1      | 1-2 years     |
| **Quality**     | ⭐⭐⭐⭐⭐    | ⭐⭐⭐⭐       | ⭐⭐           | ⭐⭐⭐        |
| **Gaps**        | Minimal       | Low            | High           | Medium        |
| **Access**      | Download once | Manual export  | API (unstable) | API (limited) |
| **Backtesting** | ✅ Excellent  | ✅ Good        | ❌ Poor        | ⚠️ Expensive  |

### 9.3. Migration Guide

If you have existing OANDA CSV files, the codebase maintains backward compatibility:

1. **Keep using OANDA CSV**: The system will automatically use `OANDA_XAUUSD, 1.csv` if Dukascopy CSV is not found
2. **Switch to Dukascopy**: Download new data and place as `dukascopy_xauusd_m1.csv`
3. **Compare results**: Both sources should yield similar trades (minor OHLC differences may occur)

---

## 10. Future Enhancements

### 10.1. Short-Term (Next Phase)

1. **Short Side Implementation**
   - Port Short (Sell) logic from Pine Script
   - Mirror Long logic with inverted conditions

2. **Unit Testing**
   - Test individual methods: `_detect_red_candle()`, `_create_buy_base()`, etc.
   - Mock M1/M15 data for isolated tests

3. **Performance Optimization**
   - Vectorize zone touch detection where possible
   - Profile bottlenecks (likely pattern recognition loops)

4. **Commission/Slippage Modeling**
   - Add configurable spread/commission parameters
   - Adjust entry/exit prices for realistic fills

### 10.2. Medium-Term

1. **Real-Time Paper Trading**
   - WebSocket integration with broker API
   - Live M1 tick processing
   - Real-time M15 aggregation

2. **Parameter Optimization**
   - Grid search on ADX threshold, timeout values, R-multiples
   - Walk-forward analysis

3. **Risk Management**
   - Max drawdown limits
   - Daily loss limits
   - Position sizing adjustments

### 10.3. Long-Term

1. **Machine Learning Integration**
   - Feature engineering from zones/liquidity
   - ML model for entry/exit timing
   - Hybrid rule-based + ML approach

2. **Multi-Symbol Support**
   - Abstract strategy for any forex/commodity pair
   - Portfolio-level backtesting

3. **GUI Dashboard**
   - Visualize zones, bases, trades on charts
   - Real-time monitoring
   - Performance analytics

---

## 11. Troubleshooting

### 11.1. Common Issues

**Issue**: "No M1 data loaded"

- **Cause**: CSV file not found or empty
- **Fix**: Check file path, ensure CSV has correct columns (`time`, `open`, `high`, `low`, `close`, `Volume`)

**Issue**: "Dukascopy CSV not found"

- **Cause**: Data file not downloaded or wrong path
- **Fix**: Download data using `npx dukascopy-node -i xauusd -from YYYY-MM-DD -to YYYY-MM-DD -t m1 -f csv`

**Issue**: Different trade count vs. Pine Script

- **Cause**: Data source difference, or logic port error
- **Fix**:
  1. Use exact same data (OANDA CSV)
  2. Enable debug logs around entry time
  3. Compare state variables (zones, bases, flags) bar-by-bar

**Issue**: "Index out of range" in M15 buffer

- **Cause**: Insufficient M15 history (strategy needs 3-7 candles)
- **Fix**: Ensure M1 data covers at least 2 hours (to generate 7+ M15 bars)

### 11.2. Debug Logging

The strategy includes extensive debug logging:

```python
# Enable verbose logs around specific timestamp
if ts >= pd.Timestamp('2026-02-01 23:30:00') and ts <= pd.Timestamp('2026-02-02 00:30:00'):
    print(f"[DEBUG-Demand] {ts} | Demand exists: Bottom={zone.price_bottom:.2f}, ...")
```

**To add custom logs**:

1. Identify target timestamp from Pine Script backtest
2. Add conditional print in relevant method
3. Run backtest, grep for `[DEBUG-...]` output

---

## 12. References

### 12.1. Original Strategy

- **Name**: "Tổng - dời SL 05R - Đã Visual"
- **Platform**: TradingView (Pine Script v6)
- **Author**: thienbui0143
- **License**: Mozilla Public License 2.0

### 12.2. Pine Script Documentation

- [Pine Script Reference](https://www.tradingview.com/pine-script-reference/v6/)
- `ta.adx()` - Average Directional Index
- `ta.pivothigh()`, `ta.pivotlow()` - Pivot point detection
- `request.security()` - Multi-timeframe data requests

### 12.3. Data Sources & Libraries

- [Dukascopy Historical Data](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- [dukascopy-node GitHub](https://github.com/Leo4815162342/dukascopy-node)
- [pandas Documentation](https://pandas.pydata.org/docs/)

---

## 13. Version History

| Version | Date       | Changes                                        |
| ------- | ---------- | ---------------------------------------------- |
| 1.1     | 2026-02-06 | Migrated to Dukascopy as primary data source   |
|         |            | - Removed Yahoo Finance and Twelve Data        |
|         |            | - Simplified data loading architecture         |
|         |            | - Updated documentation and usage instructions |
| 1.0     | 2026-02-06 | Initial spec.md creation                       |
|         |            | - Documented complete architecture             |
|         |            | - Long side fully ported from Pine Script      |
|         |            | - Multiple data source support implemented     |

---

## 14. Contact & Contribution

**Project Maintainer**: thien (thienbui0143)

**Known Collaborators**: N/A

**Contribution Guidelines**:

- Follow existing code structure (1-1 Pine Script mapping)
- Add unit tests for new methods
- Update this spec.md when adding features
- Use descriptive commit messages (in English or Vietnamese as appropriate)

---

## 15. Glossary

| Term            | Definition                                                           |
| --------------- | -------------------------------------------------------------------- |
| **M1**          | 1-minute timeframe/bars                                              |
| **M15**         | 15-minute timeframe/bars                                             |
| **MTF**         | Multi-TimeFrame analysis                                             |
| **Demand Zone** | Support area where buyers are expected (Case 2/4/5 patterns)         |
| **Supply Zone** | Resistance area where sellers are expected                           |
| **Liquidity**   | Swing high/low points that attract price (stop-loss clusters)        |
| **Sweep**       | Price briefly crosses liquidity to trigger stops, then reverses      |
| **Buy Base**    | Entry trigger zone formed after liquidity sweep or demand activation |
| **ADX**         | Average Directional Index - measures trend strength (0-100)          |
| **R**           | Risk unit (e.g., 1R = distance from entry to stop loss)              |
| **0.5R**        | Half risk - used for trailing stop (breakeven at +0.5R profit)       |
| **2R**          | Target profit at 2x risk (1:2 risk-reward ratio)                     |
| **Touch**       | Price enters a zone (low/high penetrates boundaries)                 |
| **Break**       | Price closes beyond zone boundary, invalidating it                   |
| **Timeout**     | Time-based expiration of a zone (17-20 bars typical)                 |
| **RMA**         | Running Moving Average (EMA with alpha=1/length)                     |
| **Case 2/4/5**  | Specific M15 candlestick patterns for zone creation                  |

---

**End of Specification Document**
