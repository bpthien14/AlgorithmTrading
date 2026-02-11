from collections import deque
from typing import List, Optional
import pandas as pd
import numpy as np
from datetime import timedelta

from .models import TradingZone, ZoneType, Candle, LiquidityPoint, MajorLevel

class StrategyEngine:
    def __init__(self, m1_df: pd.DataFrame, m15_df: pd.DataFrame):
        self.m1_data = m1_df
        # Ensure M15 data has indicators pre-calculated
        self.m15_data = m15_df
        
        # State Arrays (Buffers for M15 Structure)
        # We need at least 3-4 closed candles for pattern recognition
        self.m15_buffer: deque[Candle] = deque(maxlen=20)
        
        # Active Zones
        self.demand_zones: List[TradingZone] = []
        self.supply_zones: List[TradingZone] = []
        
        # Liquidity & Levels
        self.buy_liquidity: List[LiquidityPoint] = []
        self.sell_liquidity: List[LiquidityPoint] = []
        self.major_levels: List[MajorLevel] = []
        
        # Operational State
        self.liquid_finding_buy_base: bool = False
        self.liquid_finding_sell_base: bool = False
        self.current_open_position = None # Simplistic position tracking
        
        # Debug / Logging
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)

    def on_tick(self, m1_candle: pd.Series):

        current_time = m1_candle.name
        
        # 1. Update Zone Timeouts (17 min rule)
        self._update_zone_timers()
        
        # 2. Check for Zone Touches / Breaks with CURRENT M1 PRICE
        self._check_zone_interactions(m1_candle)
        
        # 3. M15 Synchronization Logic
        # We check our M15 dataframe to see if a new bar has closed relative to this M1 time.
        # In a generic realtime system, you might compute M1 from ticks and build M15.
        # Here, we assume we have pre-loaded M15 data for the backtest context.
        # For Realtime, this method would need to receive the "Completed M15 candle" event separately
        # or derive it.
        
        # BACKTEST MODE:
        if self.m15_data is not None:
             total_m15 = len(self.m15_data)
             if self.m15_idx < total_m15:
                next_m15_bar = self.m15_data.iloc[self.m15_idx]
                # If current M1 time is >= next M15 time + 15 min, it means next M15 has closed
                bar_end_time = next_m15_bar.name + timedelta(minutes=15)
                
                if current_time >= bar_end_time:
                    # New M15 Bar Closed!
                    self._on_m15_close(next_m15_bar)
                    self.m15_idx += 1

    def _on_m15_close(self, bar_data: pd.Series):
        """Handle logic that runs once per M15 bar close."""
        closed_candle = Candle(
            timestamp=bar_data.name,
            open=bar_data['open'],
            high=bar_data['high'],
            low=bar_data['low'],
            close=bar_data['close'],
            volume=bar_data.get('volume', 0)
        )
        self.m15_buffer.append(closed_candle)
        
        if len(self.m15_buffer) >= 3:
            self._process_market_structure()
            self._process_liquidity_creation()

    def run(self):
        """
        Backtest Loop.
        """
        self.m15_idx = 0 
        for i in range(len(self.m1_data)):
            current_m1 = self.m1_data.iloc[i]
            self.on_tick(current_m1)

    def _update_zone_timers(self):
        """Increment counters for active zones."""
        # This is a simplification. 
        # Pine: 'muoi_bay_phut_time_out' increments every bar if condition met.
        # We can just increment active zones count.
        for z in self.demand_zones:
            if z.is_active:
                z.timeout_counter += 1
                if z.timeout_counter > 20: # Approx 19-20 limit
                     z.is_active = False
                     self.log(f"Demand Zone {z.id} expired due to timeout")

    def _check_zone_interactions(self, m1_bar):
        low = m1_bar['low']
        # Demand Zones
        for z in self.demand_zones:
            if not z.is_active: continue
            
            if z.is_broken_by(low):
                z.is_active = False
                self.log(f"Demand Zone {z.id} broken by price {low}")
                continue
            
            if z.contains(low):
                z.mark_touched()
                self.log(f"Demand Zone {z.id} touched (Count: {z.touch_count})")
    
    def _process_market_structure(self):
        # Need at least 3 candles: [..., -3, -2, -1]
        c1 = self.m15_buffer[-3]
        c2 = self.m15_buffer[-2]
        c3 = self.m15_buffer[-1] # Most recent closed
        
        # Case 2 Bullish (Simplified translation)
        # open2 > close2 (Red)
        # open3 < close3 (Green)
        # weak body 2
        # Engulfing properties...
        
        # Implementation of Line 475 logic
        #     if open_nen_second > close_nen_second and open_nen_third < close_nen_third 
        #     and math.abs(low_nen_second - close_nen_second) > math.abs(close_nen_second - open_nen_second) 
        #     and open_nen_second - close_nen_second <= 0.5*(close_nen_third - open_nen_third) 
        #     and close_nen_third > high_nen_second 
        #     and low_nen_second < low_nen_third 
        #     and high_nen_second - open_nen_second < open_nen_second - close_nen_second 
        #     and high_nen_third - close_nen_third < 0.25 * (close_nen_third - open_nen_third)

        is_red_2 = c2.open > c2.close
        is_green_3 = c3.open < c3.close
        is_weak_body_2 = abs(c2.low - c2.close) > abs(c2.close - c2.open)
        is_engulfing_2_3 = c2.open - c2.close <= 0.5*(c3.close - c3.open)
        is_engulfing_3_2 = c3.close > c2.high and c2.low < c3.low
        is_engulfing_2_3 = c2.high - c2.open < c2.open - c2.close
        is_engulfing_3_2 = c3.high - c3.close < 0.25 * (c3.close - c3.open)
        
        if is_red_2 and is_green_3 and is_weak_body_2 and is_engulfing_2_3 and is_engulfing_3_2 and is_engulfing_2_3 and is_engulfing_3_2:
            # Add detailed math conditions here from Pine
            # For prototype, we use simple Engulfing
            if c3.close > c2.open and c3.open < c2.close:
                new_zone = TradingZone(
                    zone_type=ZoneType.DEMAND,
                    price_top=c2.high,      
                    price_bottom=c3.low,    
                    created_at=c3.timestamp
                )
                self.demand_zones.append(new_zone)
                self.log(f"Created Demand Zone via Case 2 at {c3.timestamp}")

    def _process_liquidity_creation(self):
        """Logic for Clover/Magnet labels."""
        # Last 3 candles
        c1 = self.m15_buffer[-3]
        c2 = self.m15_buffer[-2]
        c3 = self.m15_buffer[-1]
        
        # Buy Liquidity (Swing Low) at c2
        if c2.low < c1.low and c2.low < c3.low:
            # Created Clover
            lp = LiquidityPoint(price=c2.low, timestamp=c2.timestamp, is_buy_liquidity=True)
            self.buy_liquidity.append(lp)
            self.log(f"Buy Liquidity created at {c2.low}")
