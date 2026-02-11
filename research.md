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

| Pine Script Variable | Functionality | Python Equivalent |
| :--- | :--- | :--- |
| `arrayBoxDem`, `arrayBoxSup` | Stores active Supply/Demand zones. | `List[TradingZone]` |
| `muoi_bay_phut_time_out` | 17-bar (minute) timer for zone validity. | `int` counter in `TradingZone` or `Strategy` |
| `finding_entry_buy/sell` | Boolean state machine for entry logic. | `bool` flags or `Enum` state |
| `so_lan` (in arrays) | Counts how many times price touched a zone. | Attribute `touch_count` in `TradingZone` |
| `m15_opens` (array) | Circular buffer of recent M15 candle data. | `collections.deque(maxlen=N)` |

## 3. Detailed Logic Specifications

### 3.1. Market Structure Patterns (Zone Creation)
The script identifies specific bar patterns ("Cases") to create zones.
- **Case 2 (Reversal)**: Strong rejection/engulfing pattern.
- **Case 4 (Structure)**: Breaks multiple prior candles.
- **Case 5 (Continuation)**: Momentum continuation.
*Spec*: Implement distinct recognition functions like `_check_case_2(candles: Deque)`, returning a `TradingZone` object if matched.

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
The strategy does *not* enter immediately on zone creation. It waits for a specific sequence:
1.  **Liquidity Line Creation**: Identifies swing points (`label` "Magnet" or "Clover").
2.  **Sweep**: Price crosses this liquidity line.
3.  **Base Formation**: A new "Buy/Sell Base" (micro-structure) forms.
4.  **Confirmation**: Price re-tests the base with specific criteria (ADX < 30, Timeouts).
5.  **Trigger**: Place Limit/Market order.

### ### 3.3. Entry Logic (Liquidity Sweep & Major Levels)
The strategy does *not* enter immediately on zone creation. It waits for a specific sequence:

1.  **Liquidity / Level Break**:
    *   **Minor Liquidity**: Swing Highs/Lows on M15 identified as "Magnet" (Sell) or "Clover" (Buy).
    *   **Major Levels**: MTF Pivot Highs/Lows defined as `Lv1` (TF1) and `Lv2` (TF2).
    *   *Trigger*: Price crossing these lines activates `liquid_finding_buy_base = true`.

2.  **Base Formation**: A new "Buy/Sell Base" (micro-structure) forms.
    *   Requires `liquid_finding_buy_base` to be TRUE.
    *   Uses pattern matching on recent candles (similar to "Cases").

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
- **`backtesting`** (Optional): Can be used for the engine, or we build a custom event loop for granule control over the complex "Case" logic. *Recommendation: Custom Loop due to specific state management needs.*
