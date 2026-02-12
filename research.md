# Research & Specifications: Pine Script to Python Conversion

## 1. Executive Summary

This document analyzes the "Tổng - dời SL 05R - Đã Visual" Pine Script strategy and defines the specifications for its Python implementation. The strategy is a complex, state-heavy system relying on **Multi-Timeframe (MTF) Analysis** (M1 data driving M15 indicators), **Market Structure Identification** (Supply/Demand Zones), and **Liquidity Traps**.

## 2. Pine Script Component Analysis

### 2.1. Data Handling

- **Source**: The strategy operates on an M1 (1-minute) chart but calculates logic based on M15 (15-minute) candles.
- **Mechanism**: Uses `request.security(..., "15", ...)` to fetch M15 OHLC data.
- **Python Spec**:
  - Load M1 OHLCV data.
  - Resample M1 data to 15-minute intervals (`df.resample('15min')`).
  - Align M15 data to M1 timestamps (forward-fill to simulate `request.security` without lookahead bias, or manage dual-index pointers).

### 2.2. Core Indicators

- **ADX (Average Directional Index)**: Used for trend strength filtering (Threshold < 30).
- **Pivots**: Used for Market Structure (`ta.pivothigh`, `ta.pivotlow`) on multiple timeframes (default 5m/15m/1h implicit via inputs).

### 2.3. State Management (Crucial)

The script relies heavily on `var` variables to maintain state across bars. This functionality must be replicated using a persistent **Strategy Class**.

| Pine Script Variable         | Functionality                               | Python Equivalent                            |
| :--------------------------- | :------------------------------------------ | :------------------------------------------- |
| `arrayBoxDem`, `arrayBoxSup` | Stores active Supply/Demand zones.          | `List[TradingZone]`                          |
| `muoi_bay_phut_time_out`     | 17-bar (minute) timer for zone validity.    | `int` counter in `TradingZone` or `Strategy` |
| `finding_entry_buy/sell`     | Boolean state machine for entry logic.      | `bool` flags or `Enum` state                 |
| `so_lan` (in arrays)         | Counts how many times price touched a zone. | Attribute `touch_count` in `TradingZone`     |
| `m15_opens` (array)          | Circular buffer of recent M15 candle data.  | `collections.deque(maxlen=N)`                |

## 3. Detailed Logic Specifications

### 3.1. Market Structure Patterns (Zone Creation)

The script identifies specific bar patterns ("Cases") to create zones.

- **Case 2 (Reversal)**: Strong rejection/engulfing pattern.
- **Case 4 (Structure)**: Breaks multiple prior candles.
- **Case 5 (Continuation)**: Momentum continuation.
  _Spec_: Implement distinct recognition functions like `_check_case_2(candles: Deque)`, returning a `TradingZone` object if matched.

### 3.2. Zone Management Lifecycle

1.  **Creation**: When a "Case" pattern confirms.
2.  **Active Monitoring**:
    - Check if current Low/High touches the zone (`y_top` / `y_bottom`).
    - Increment `touch_count`.
3.  **Invalidation/Deletion**:
    - **Price Cross**: If price closes beyond the zone (Liquidated).
    - **Timeout**: If `muoi_bay_phut_time_out` > 19 (approx 17-20 bars).
    - **Max Touches**: Usually invalidated after 2 or 3 touches depending on logic.

### 3.3. Entry Logic (Liquidity Sweep)

The strategy does _not_ enter immediately on zone creation. It waits for a specific sequence:

1.  **Liquidity Line Creation**: Identifies swing points (`label` "Magnet" or "Clover").
2.  **Sweep**: Price crosses this liquidity line.
3.  **Base Formation**: A new "Buy/Sell Base" (micro-structure) forms.
4.  **Confirmation**: Price re-tests the base with specific criteria (ADX < 30, Timeouts).
5.  **Trigger**: Place Limit/Market order.

### ### 3.3. Entry Logic (Liquidity Sweep & Major Levels)

The strategy does _not_ enter immediately on zone creation. It waits for a specific sequence:

1.  **Liquidity / Level Break**:
    - **Minor Liquidity**: Swing Highs/Lows on M15 identified as "Magnet" (Sell) or "Clover" (Buy).
    - **Major Levels**: MTF Pivot Highs/Lows defined as `Lv1` (TF1) and `Lv2` (TF2).
    - _Trigger_: Price crossing these lines activates `liquid_finding_buy_base = true`.

2.  **Base Formation**: A new "Buy/Sell Base" (micro-structure) forms.
    - Requires `liquid_finding_buy_base` to be TRUE.
    - Uses pattern matching on recent candles (similar to "Cases").

3.  **Confirmation**: Price re-tests the base with specific criteria (ADX < 30, Timeouts).
4.  **Trigger**: Place Limit/Market order.

### 3.5. Liquidity & Major Levels Specifications

- **Liquidity Points**:
  - Created on M15 Swing Lows (`low < prev1` & `low < prev2`).
  - Stored in `arrayBuyLiquidity` / `arraySellLiquidity`.
  - Removed when `Low < LiquidityPrice`.
- **Major Levels (Lv1/Lv2)**:
  - Derived from `request.security` Pivot Points.
  - Stored in `arrayDemandLv1/2` and `arraySupplyLv1/2`.
  - Crossing these levels also acts as a "Liquidity Sweep" event, enabling base finding.

## 4. Python Architecture Specifications

### 4.1. Class Structure

```python
class ZoneType(Enum):
    SUPPLY = 1
    DEMAND = 2

class TradingZone:
    id: UUID
    type: ZoneType
    top: float
    bottom: float
    created_at: datetime
    touch_count: int = 0
    is_active: bool = True

    def contains(self, price: float) -> bool: ...
    def is_broken_by(self, price: float) -> bool: ...

class StrategyEngine:
    def __init__(self, data: pd.DataFrame):
        self.m1_data = data
        self.m15_data = self._resample_data(data)
        self.zones: List[TradingZone] = []
        self.state = StrategyState()

    def run(self):
        # Main event loop iterating through M1 bars
        # updating M15 buffers as needed
        pass
```

### 4.2. Libraries

- **`pandas`**: Data manipulation and resampling.
- **`pandas_ta`**: Technical indicators (RSI, ADX).
- **`numpy`**: Vectorized calculations where possible.
- **`backtesting`** (Optional): Can be used for the engine, or we build a custom event loop for granule control over the complex "Case" logic. _Recommendation: Custom Loop due to specific state management needs._

## 5. Paper Trade Mode (Circuit Breaker)

### 5.1. Purpose

Tự động chuyển sang paper trading khi strategy đang trong giai đoạn drawdown để bảo vệ vốn. Paper mode hoạt động như một "circuit breaker" - tiếp tục theo dõi signals mà không chịu rủi ro thực.

### 5.2. State Machine

```
                         ┌────────────────────────────────────┐
                         │           LIVE MODE                │
                         │  (Real trades affect equity)       │
                         └─────────────┬──────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │         TRIGGER CONDITIONS          │
                    │  (1) Consecutive Losses >= 3        │
                    │         OR                          │
                    │  (2) Win Rate (last 10) < 20%       │
                    └──────────────────┬──────────────────┘
                                       ▼
                         ┌────────────────────────────────────┐
                         │          PAPER MODE                │
                         │  (Simulated trades, no risk)       │
                         │  Uses LIVE EQUITY for sizing       │
                         └─────────────┬──────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │        RECOVERY CONDITIONS          │
                    │  Paper PnL > 0                      │
                    │         AND                         │
                    │  Consecutive Paper Wins >= 2        │
                    │         AND                         │
                    │  Time in Paper Mode < Max Duration  │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                              (Back to LIVE MODE)
```

### 5.3. Configuration Parameters

| Parameter                             | Type  | Default | Description                             |
| ------------------------------------- | ----- | ------- | --------------------------------------- |
| `enable_paper_mode`                   | bool  | True    | Bật/tắt tính năng Paper Mode            |
| `paper_trigger_consecutive_losses`    | int   | 3       | Số lệnh lỗ liên tiếp để trigger         |
| `paper_trigger_win_rate_window`       | int   | 10      | Window size để tính win rate            |
| `paper_trigger_win_rate_threshold`    | float | 0.20    | Win rate threshold (20%)                |
| `paper_recovery_min_wins`             | int   | 2       | Số lệnh thắng liên tiếp để recover      |
| `paper_recovery_require_positive_pnl` | bool  | True    | Yêu cầu Paper PnL > 0                   |
| `paper_max_duration_minutes`          | int   | 1440    | Thời gian tối đa trong paper mode (24h) |

### 5.4. Implementation Spec

#### 5.4.1. State Variables

```python
@dataclass
class PaperModeState:
    is_active: bool = False                    # Currently in paper mode?
    activated_at: Optional[pd.Timestamp] = None  # When paper mode started
    paper_trades: List[Trade] = field(default_factory=list)  # Trades during paper mode
    paper_pnl: float = 0.0                     # Cumulative PnL in paper mode
    paper_consecutive_wins: int = 0            # Current win streak in paper

    # Tracking for trigger conditions
    recent_results: deque = field(default_factory=lambda: deque(maxlen=10))
    consecutive_losses: int = 0
```

#### 5.4.2. Trigger Logic (Check after each trade closes)

```python
def _check_paper_mode_trigger(self) -> bool:
    """
    Returns True if should switch to Paper Mode.
    Called after every trade closes in LIVE mode.
    """
    # Condition 1: Consecutive losses
    if self.consecutive_losses >= self.config.paper_trigger_consecutive_losses:
        return True

    # Condition 2: Win rate below threshold
    if len(self.recent_results) >= self.config.paper_trigger_win_rate_window:
        wins = sum(1 for r in self.recent_results if r > 0)
        win_rate = wins / len(self.recent_results)
        if win_rate < self.config.paper_trigger_win_rate_threshold:
            return True

    return False
```

#### 5.4.3. Recovery Logic (Check after each paper trade closes)

```python
def _check_paper_mode_recovery(self, current_time: pd.Timestamp) -> bool:
    """
    Returns True if should switch back to LIVE mode.
    Called after every trade closes in PAPER mode.
    """
    # Time limit check
    duration = (current_time - self.paper_state.activated_at).total_seconds() / 60
    if duration >= self.config.paper_max_duration_minutes:
        return True  # Force exit paper mode

    # Recovery conditions (must meet ALL)
    if (
        self.paper_state.paper_pnl > 0
        and self.paper_state.paper_consecutive_wins >= self.config.paper_recovery_min_wins
    ):
        return True

    return False
```

#### 5.4.4. Position Sizing

- Paper mode sử dụng **Actual Live Equity** để tính position size
- Điều này đảm bảo khi quay lại live, sizing consistent với vốn thực

#### 5.4.5. Trade Execution Flow

```python
def _execute_entry(self, direction, price, sl, tp):
    if self.paper_state.is_active:
        # Paper trade - track separately, no equity impact
        trade = self._create_trade(direction, price, sl, tp, is_paper=True)
        self.paper_state.paper_trades.append(trade)
        self._log_paper_entry(trade)
    else:
        # Live trade - affects equity
        trade = self._create_trade(direction, price, sl, tp, is_paper=False)
        self.trades.append(trade)
        self._log_live_entry(trade)
```

### 5.5. Logging Format

```
# Trigger
⚠️ [PAPER MODE ON] 3 consecutive losses. Switching to paper trading.
⚠️ [PAPER MODE ON] Win rate 10.0% (1/10) below threshold. Switching to paper trading.

# Paper trades
📝 [PAPER] ENTRY LONG @ 1850.00 | SL: 1845.00, TP: 1860.00
📝 [PAPER] EXIT LONG @ 1858.00 | PnL: +$80 | Paper streak: 1W, Total: +$80

# Recovery
✅ [PAPER MODE OFF] Recovered! Paper PnL: +$150, Wins: 2. Resuming LIVE trading.

# Time limit
⏰ [PAPER MODE OFF] Max duration (24h) reached. Resuming LIVE trading.
```

### 5.6. Backtest Metrics

Thêm vào summary report:

- **Paper Mode Activations**: Số lần trigger paper mode
- **Time in Paper Mode**: Tổng thời gian (minutes) trong paper mode
- **Paper Trades**: Số lệnh paper
- **Paper PnL**: Tổng PnL của paper trades
- **Losses Avoided**: Estimated losses tránh được (paper losses)
- **Live vs Paper Win Rate**: So sánh performance

### 5.7. Edge Cases

1. **Paper mode timeout**: Khi hết thời gian max, quay lại live ngay cả khi chưa recover
2. **Session end**: Paper mode state được giữ qua các sessions
3. **Reset conditions**: Paper mode state reset khi khởi động lại backtest
4. **No trades in paper**: Nếu không có signal trong paper mode, chờ cho đến khi timeout
