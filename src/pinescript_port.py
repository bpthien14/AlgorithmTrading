"""
Port 1-1 của PineScript strategy sang Python.
Chạy bar-by-bar với state giống hệt Pine.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Deque
from collections import deque
import pandas as pd
import numpy as np

from .models import Box, BuySellBase, DemandSupplyZone, LiquidityPoint, TradeDirection, ZoneType
from .strategy_config import StrategyConfig


@dataclass
class Trade:
    """Một lệnh giao dịch."""
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp] = None
    direction: TradeDirection = TradeDirection.BUY
    entry_price: float = 0.0
    exit_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    lot_size: float = 0.0
    pnl: float = 0.0
    is_paper: bool = False  # True = paper trade (không ảnh hưởng equity)


@dataclass
class PaperModeState:
    """
    State cho Paper Trade Mode (Circuit Breaker).
    See research.md Section 5.
    """
    is_active: bool = False                              # Đang trong paper mode?
    activated_at: Optional[pd.Timestamp] = None          # Thời điểm bắt đầu paper mode
    paper_trades: List[Trade] = field(default_factory=list)  # Các lệnh trong paper mode
    paper_pnl: float = 0.0                               # Tổng PnL paper mode
    paper_consecutive_wins: int = 0                      # Chuỗi thắng liên tiếp trong paper
    
    # Tracking cho trigger conditions (dùng cho cả live và paper)
    recent_results: Deque[float] = field(default_factory=lambda: deque(maxlen=10))
    consecutive_losses: int = 0
    
    # Stats
    activation_count: int = 0                            # Số lần kích hoạt paper mode
    total_time_in_paper_minutes: float = 0.0             # Tổng thời gian trong paper mode


@dataclass
class LongState:
    """State cho Long side (Buy), mapping trực tiếp từ Pine var."""
    
    # M15 buffer (giữ 7 nến M15 gần nhất)
    m15_opens: Deque[float] = field(default_factory=lambda: deque(maxlen=7))
    m15_closes: Deque[float] = field(default_factory=lambda: deque(maxlen=7))
    m15_highs: Deque[float] = field(default_factory=lambda: deque(maxlen=7))
    m15_lows: Deque[float] = field(default_factory=lambda: deque(maxlen=7))
    
    # Demand Zones
    arrayBoxDem: List[DemandSupplyZone] = field(default_factory=list)
    arrayBoxDem_cham: List[int] = field(default_factory=list)
    arrayBoxDem_status_touched: List[int] = field(default_factory=list)
    
    # Buy Base
    arrayBoxBuyBase: List[BuySellBase] = field(default_factory=list)
    mang_so_lan_cham_buy_base: List[int] = field(default_factory=list)
    
    # Buy Liquidity
    arrayBuyLiquidity: List[float] = field(default_factory=list)
    
    # Nến đỏ (high của nến đỏ để tìm Buy Base)
    arrayHighGiaNenGiam: List[float] = field(default_factory=list)
    
    # State flags
    make_color_tang: bool = False
    make_color_cho_rieng_case_4_tang: bool = False
    make_color_giam: bool = False
    
    demand_finding_buy_base: bool = False
    liquid_finding_buy_base: bool = False
    
    keep_finding_demand: bool = False
    hai_phut_hon_demand: int = 0
    
    keep_finding_liquid_buy: bool = False
    hai_phut_hon_liquid: int = 0
    
    making_buy_base: bool = False
    do_buy_base_2_lan: int = 0
    
    finding_entry_buy: bool = False
    finding_entry_buy_time_out: int = 0
    finding_entry_buy_ten_minutes: int = 0
    
    # Remove prices (để quản lý khi bị cross)
    removePrice: float = 0.0
    removePriceDemand: float = 0.0
    removeCandle_OpenPrice: float = 0.0
    
    # Timeout
    muoi_bay_phut_time_out: int = 0
    
    # Index
    index_of_high_nearest: int = 1
    
    # Lệnh hiện tại
    in_position: bool = False
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    lot_size: float = 0.0
    entry_time: Optional[pd.Timestamp] = None
    doi_sl_05R: bool = False


@dataclass
class ShortState:
    """State cho Short side (Sell), mapping trực tiếp từ Pine var."""
    
    # M15 buffer (dùng chung với Long - sẽ share từ LongState)
    # Không cần duplicate buffer M15, sẽ dùng long_state.m15_*
    
    # Supply Zones (tương tự arrayBoxDem nhưng cho Short)
    arrayBoxSup: List[DemandSupplyZone] = field(default_factory=list)
    arrayBoxSup_cham: List[int] = field(default_factory=list)
    arrayBoxSup_status_touched: List[int] = field(default_factory=list)
    
    # Sell Base
    arrayBoxSellBase: List[BuySellBase] = field(default_factory=list)
    mang_so_lan_cham_sell_base: List[int] = field(default_factory=list)
    
    # Sell Liquidity
    arraySellLiquidity: List[float] = field(default_factory=list)
    
    # Nến xanh (low của nến xanh để tìm Sell Base) - Pine dùng arrayLowGiaNenTang
    arrayLowGiaNenTang: List[float] = field(default_factory=list)
    
    # State flags
    make_color_giam: bool = False
    make_color_cho_rieng_case_4_giam: bool = False
    make_color_tang: bool = False
    
    supply_finding_sell_base: bool = False
    liquid_finding_sell_base: bool = False
    
    keep_finding_supply: bool = False
    hai_phut_hon_supply: int = 0
    
    keep_finding_liquid_sell: bool = False
    hai_phut_hon_liquid_sell: int = 0
    
    making_sell_base: bool = False
    do_sell_base_2_lan: int = 0
    
    finding_entry_sell: bool = False
    finding_entry_sell_time_out: int = 0
    finding_entry_sell_ten_minutes: int = 0
    
    # Remove prices
    removePriceSupply: float = 10000.0
    removeCandle_OpenPrice_Sell: float = 100000.0
    
    # Timeout
    muoi_bay_phut_time_out_sell_zone: int = 0
    
    # Index
    index_of_low_nearest: int = 1
    
    # Lệnh hiện tại
    in_position: bool = False
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    lot_size: float = 0.0
    entry_time: Optional[pd.Timestamp] = None
    doi_sl_05R_sell: bool = False


class PineScriptStrategy:
    """
    Port hoàn toàn từ PineScript, chạy bar-by-bar trên M1, 
    lấy M15 từ resample, tính toán state giống Pine.
    """
    
    def __init__(
        self,
        m1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        config: Optional[StrategyConfig] = None,
    ):
        self.m1 = m1_data.copy()
        self.m15 = m15_data.copy()

        # Config (tập trung tất cả tham số tối ưu được)
        self.config: StrategyConfig = config or StrategyConfig()
        
        # State cho Long side
        self.long_state = LongState()
        
        # State cho Short side
        self.short_state = ShortState()
        
        # Trades
        self.trades: List[Trade] = []
        
        # M15 index (để biết đến đâu rồi trong M15)
        self.m15_idx = 0
        
        # Constants / parameters (lấy từ config để dễ tối ưu)
        self.diff = self.config.zone_touch_buffer  # Chênh lệch cho liquidity (input trong Pine)
        self.initial_capital = 1000  # Vốn ban đầu
        self.current_equity = self.initial_capital
        
        # Equity curve tracking for drawdown calculation
        self.equity_curve: List[float] = [self.initial_capital]
        self.peak_equity = self.initial_capital
        
        # ADX state
        self.adx_len = self.config.adx_period
        self.SmoothedTrueRange = 0.0
        self.SmoothedDirectionalMovementPlus = 0.0
        self.SmoothedDirectionalMovementMinus = 0.0
        self.ADX = 0.0
        self.DX_buffer = deque(maxlen=self.adx_len)
        
        # Paper Trade Mode state (Circuit Breaker)
        self.paper_state = PaperModeState(
            recent_results=deque(maxlen=self.config.paper_trigger_win_rate_window)
        )
    
    def _calculate_pnl(self, entry_price: float, exit_price: float, lot_size: float, direction: TradeDirection) -> float:
        """
        Tính PnL với lot_size là position value (cash amount).
        
        Formula: pnl = lot_size × (exit_price - entry_price) / entry_price
        
        Ví dụ:
        - lot_size = $100 (1% vốn $10K)
        - entry = 2700, exit = 2750 (+50 USD)
        - PnL = 100 × (2750 - 2700) / 2700 = 100 × 50 / 2700 = $1.85
        
        Args:
            entry_price: Giá entry
            exit_price: Giá exit
            lot_size: Position value (cash amount)
            direction: BUY hoặc SELL
        
        Returns:
            PnL (dương = lãi, âm = lỗ)
        """
        if direction == TradeDirection.BUY:
            # Long: lãi khi exit > entry
            price_change_pct = (exit_price - entry_price) / entry_price
        else:
            # Short: lãi khi exit < entry
            price_change_pct = (entry_price - exit_price) / entry_price
        
        return lot_size * price_change_pct
        
    def run(self) -> List[Trade]:
        """Chạy backtest bar-by-bar trên M1."""
        print("[PineScriptStrategy] Starting backtest...")
        
        demand_zones_created = 0
        buy_bases_created = 0
        finding_entry_count = 0
        
        supply_zones_created = 0
        sell_bases_created = 0
        finding_entry_sell_count = 0
        
        for idx in range(len(self.m1)):
            row_m1 = self.m1.iloc[idx]
            ts = self.m1.index[idx]
            
            # Lấy M1 bar hiện tại
            o = row_m1['open']
            h = row_m1['high']
            l = row_m1['low']
            c = row_m1['close']
            
            # Cập nhật M15 buffer nếu có M15 mới close
            prev_demand_count = len(self.long_state.arrayBoxDem)
            prev_supply_count = len(self.short_state.arrayBoxSup)
            self._update_m15_buffer(ts)
            if len(self.long_state.arrayBoxDem) > prev_demand_count:
                demand_zones_created += 1
                print(f"[{ts}] Demand Zone created! Total: {len(self.long_state.arrayBoxDem)}")
            if len(self.short_state.arrayBoxSup) > prev_supply_count:
                supply_zones_created += 1
                print(f"[{ts}] Supply Zone created! Total: {len(self.short_state.arrayBoxSup)}")
            
            # Reset flags mỗi bar (line 1372-1373)
            self.long_state.making_buy_base = False
            self.long_state.make_color_tang = False
            self.long_state.make_color_giam = False
            
            self.short_state.making_sell_base = False
            self.short_state.make_color_giam = False
            self.short_state.make_color_tang = False
            
            # 1. Phát hiện nến đỏ (line 850) và nến xanh (cho Sell Base)
            self._detect_red_candle(idx, o, h, l, c)
            self._detect_green_candle(idx, o, h, l, c)
            
            # 2. Quản lý Demand Zone (touch, remove khi phá đáy / chạm 2 lần)
            # DEBUG: Log Demand Zone state quanh target time
            if ts >= pd.Timestamp('2026-02-01 23:30:00') and ts <= pd.Timestamp('2026-02-02 00:30:00'):
                if len(self.long_state.arrayBoxDem) > 0:
                    zone = self.long_state.arrayBoxDem[-1]
                    print(f"[DEBUG-Demand] {ts} | Demand exists: Bottom={zone.price_bottom:.2f}, Top={zone.price_top:.2f}, low={l:.2f}")
            
            self._manage_demand_zones(idx, o, h, l, c)
            
            # 3. Buy Liquidity crossed (line 381-472)
            # DEBUG: Log Liquidity state quanh target time
            if ts >= pd.Timestamp('2026-02-01 23:30:00') and ts <= pd.Timestamp('2026-02-02 00:30:00'):
                if len(self.long_state.arrayBuyLiquidity) > 0:
                    print(f"[DEBUG-Liq] {ts} | Liquidity exists: {self.long_state.arrayBuyLiquidity[-1]:.2f}, low={l:.2f}")
            
            self._check_buy_liquidity_crossed(idx, ts, o, h, l, c)
            
            # 4. Tạo Buy Base từ Liquidity (line 856-937)
            prev_base_count = len(self.long_state.arrayBoxBuyBase)
            self._create_buy_base_from_liquidity(idx, ts, o, h, l, c)
            if len(self.long_state.arrayBoxBuyBase) > prev_base_count:
                buy_bases_created += 1
                base = self.long_state.arrayBoxBuyBase[-1]
                print(f"[{ts}] Buy Base created from Liquidity! Top={base.price_top:.2f}, Bottom={base.price_bottom:.2f}")
            
            # 5. Tạo Buy Base từ Demand (line 943-1032)
            prev_base_count = len(self.long_state.arrayBoxBuyBase)
            self._create_buy_base_from_demand(idx, ts, o, h, l, c)
            if len(self.long_state.arrayBoxBuyBase) > prev_base_count:
                buy_bases_created += 1
                print(f"[{ts}] Buy Base created from Demand! Total: {len(self.long_state.arrayBoxBuyBase)}")
            
            # 6. Timeout cho Buy Base (line 1033-1071)
            self._manage_buy_base_timeout(idx, ts, h, l)
            
            # 7. Touch Buy Base → finding_entry_buy (line 1074-1099)
            was_finding = self.long_state.finding_entry_buy
            
            # DEBUG: Log Buy Base state quanh 00:00
            if ts >= pd.Timestamp('2026-02-01 23:50:00') and ts <= pd.Timestamp('2026-02-02 00:10:00') and len(self.long_state.arrayBoxBuyBase) > 0:
                base = self.long_state.arrayBoxBuyBase[-1]
                print(f"[DEBUG-Base] {ts} | Buy Base exists: Top={base.price_top:.2f}, Bottom={base.price_bottom:.2f}, close={c:.2f}, low={l:.2f}, touched={was_finding}")
            
            self._check_buy_base_touched(idx, ts, o, h, l, c)
            if not was_finding and self.long_state.finding_entry_buy:
                finding_entry_count += 1
                print(f"[{ts}] Buy Base touched! finding_entry_buy = True")
            
            # 7b. Check Buy Base invalidation (phá base hoặc chạm cản)
            self._check_buy_base_invalidation(idx, ts, o, h, l, c)
            
            # 8. Tính ADX
            self._calculate_adx(idx, o, h, l, c)
            
            # 9. Entry Long (line 1100-1277)
            was_in_position = self.long_state.in_position
            
            # DEBUG: Log khi finding_entry_buy = True quanh 00:00
            if self.long_state.finding_entry_buy and ts >= pd.Timestamp('2026-02-01 23:55:00') and ts <= pd.Timestamp('2026-02-02 00:10:00'):
                print(f"[DEBUG-Entry] {ts} | finding_entry_buy=True, in_timerange={self._is_within_timerange(ts)}, ADX={self.ADX:.2f}, close={c:.2f}")
            
            self._entry_long(idx, ts, o, h, l, c)
            if not was_in_position and self.long_state.in_position:
                mode_prefix = "📝 [PAPER] " if self._is_paper_mode() else ""
                print(f"{mode_prefix}[{self._log_timestamp(ts)}] ENTRY LONG @ {self.long_state.entry_price:.2f}, SL={self.long_state.stop_loss:.2f}, TP={self.long_state.take_profit:.2f}")
            
            # 10. SHORT SIDE LOGIC
            # 10.1. Quản lý Supply Zone (touch, remove khi phá trần / chạm 2 lần)
            self._manage_supply_zones(idx, o, h, l, c, ts)
            
            # 10.2. Sell Liquidity crossed
            self._check_sell_liquidity_crossed(idx, ts, o, h, l, c)
            
            # 10.3. Tạo Sell Base từ Liquidity
            prev_sell_base_count = len(self.short_state.arrayBoxSellBase)
            self._create_sell_base_from_liquidity(idx, ts, o, h, l, c)
            if len(self.short_state.arrayBoxSellBase) > prev_sell_base_count:
                sell_bases_created += 1
                base = self.short_state.arrayBoxSellBase[-1]
                print(f"[{ts}] Sell Base created from Liquidity! Top={base.price_top:.2f}, Bottom={base.price_bottom:.2f}")
            
            # 10.4. Tạo Sell Base từ Supply
            prev_sell_base_count = len(self.short_state.arrayBoxSellBase)
            self._create_sell_base_from_supply(idx, ts, o, h, l, c)
            if len(self.short_state.arrayBoxSellBase) > prev_sell_base_count:
                sell_bases_created += 1
                print(f"[{ts}] Sell Base created from Supply! Total: {len(self.short_state.arrayBoxSellBase)}")
            
            # 10.5. Timeout cho Sell Base
            self._manage_sell_base_timeout(idx, ts, h, l)
            
            # 10.6. Touch Sell Base → finding_entry_sell
            was_finding_sell = self.short_state.finding_entry_sell
            self._check_sell_base_touched(idx, ts, o, h, l, c)
            if not was_finding_sell and self.short_state.finding_entry_sell:
                finding_entry_sell_count += 1
                print(f"[{ts}] Sell Base touched! finding_entry_sell = True")
            
            # 10.6b. Check Sell Base invalidation (phá base hoặc chạm cản)
            self._check_sell_base_invalidation(idx, ts, o, h, l, c)
            
            # 10.7. Entry Short
            was_in_position_short = self.short_state.in_position
            self._entry_short(idx, ts, o, h, l, c)
            if not was_in_position_short and self.short_state.in_position:
                mode_prefix = "📝 [PAPER] " if self._is_paper_mode() else ""
                print(f"{mode_prefix}[{self._log_timestamp(ts)}] ENTRY SHORT @ {self.short_state.entry_price:.2f}, SL={self.short_state.stop_loss:.2f}, TP={self.short_state.take_profit:.2f}")
            
            # 11. Quản lý position hiện tại (TP/SL) - cả Long & Short
            self._manage_position(idx, ts, o, h, l, c)
        
        print(f"\n[PineScriptStrategy] Summary:")
        print(f"  - Demand Zones created: {demand_zones_created}")
        print(f"  - Supply Zones created: {supply_zones_created}")
        print(f"  - Buy Bases created: {buy_bases_created}")
        print(f"  - Sell Bases created: {sell_bases_created}")
        print(f"  - Finding entry (Long) triggered: {finding_entry_count}")
        print(f"  - Finding entry (Short) triggered: {finding_entry_sell_count}")
        print(f"  - Total trades: {len(self.trades)}")
        
        # Calculate final statistics
        self._print_statistics()
        
        return self.trades
    
    def _update_m15_buffer(self, current_ts: pd.Timestamp):
        """
        Cập nhật buffer M15 khi có nến M15 mới đóng.
        Pine: dùng request.security + is_new_m15_candle_close (minute % 15 == 14).
        Ở đây ta dùng M15 đã resample sẵn.
        """
        # Kiểm tra xem có M15 bar mới chưa
        while self.m15_idx < len(self.m15):
            m15_bar = self.m15.iloc[self.m15_idx]
            m15_ts = self.m15.index[self.m15_idx]
            
            # Nếu thời điểm M15 đã qua (tức đã close), thì thêm vào buffer
            if m15_ts <= current_ts:
                self.long_state.m15_opens.append(m15_bar['open'])
                self.long_state.m15_closes.append(m15_bar['close'])
                self.long_state.m15_highs.append(m15_bar['high'])
                self.long_state.m15_lows.append(m15_bar['low'])
                
                # Tạo Demand Zone khi có đủ 3 nến M15 (Case 2/4/5)
                if len(self.long_state.m15_closes) >= 3:
                    # DEBUG: Log M15 buffer quanh Jan 30 18:45
                    if m15_ts >= pd.Timestamp('2026-01-30 18:00:00') and m15_ts <= pd.Timestamp('2026-01-30 19:15:00'):
                        print(f"[DEBUG-M15-Buffer] {m15_ts} | Buffer size: {len(self.long_state.m15_closes)}")
                    self._detect_demand_zones_m15()
                    # Tạo Supply Zone (Case 2/4/5 giảm)
                    self._detect_supply_zones_m15()
                
                # Tạo Buy Liquidity khi có đủ 3 nến M15
                if len(self.long_state.m15_closes) >= 3:
                    self._detect_buy_liquidity_m15()
                    # Tạo Sell Liquidity
                    self._detect_sell_liquidity_m15()
                
                self.m15_idx += 1
            else:
                break
    
    def _detect_demand_zones_m15(self):
        """
        Phát hiện Demand Zone (Case 2/4/5) khi có M15 mới close.
        Mapping line 474-532 trong Pine.
        """
        if len(self.long_state.m15_closes) < 3:
            return
        
        # 3 nến gần nhất
        opens = list(self.long_state.m15_opens)
        closes = list(self.long_state.m15_closes)
        highs = list(self.long_state.m15_highs)
        lows = list(self.long_state.m15_lows)
        
        # DEBUG: Log quanh target time (Feb 1-2)
        m15_time = self.m15.index[self.m15_idx - 1] if self.m15_idx > 0 else None
        if m15_time and m15_time >= pd.Timestamp('2026-02-01 22:00:00') and m15_time <= pd.Timestamp('2026-02-02 02:00:00'):
            print(f"[DEBUG-M15-Check] {m15_time} | Checking 3 candles:")
        
        open_nen_first = opens[-3]
        open_nen_second = opens[-2]
        open_nen_third = opens[-1]
        
        close_nen_first = closes[-3]
        close_nen_second = closes[-2]
        close_nen_third = closes[-1]
        
        high_nen_first = highs[-3]
        high_nen_second = highs[-2]
        high_nen_third = highs[-1]
        
        low_nen_first = lows[-3]
        low_nen_second = lows[-2]
        low_nen_third = lows[-1]
        
        # Case 2 tăng (line 475)
        case2 = (
            open_nen_second > close_nen_second
            and open_nen_third < close_nen_third
            and abs(low_nen_second - close_nen_second) > abs(close_nen_second - open_nen_second)
            and open_nen_second - close_nen_second <= 0.5 * (close_nen_third - open_nen_third)
            and close_nen_third > high_nen_second
            and low_nen_second < low_nen_third
            and (high_nen_second - open_nen_second) < (open_nen_second - close_nen_second)
            and (high_nen_third - close_nen_third) < 0.25 * (close_nen_third - open_nen_third)
        )
        
        # Case 4 tăng (line 490)
        case4 = (
            close_nen_first < open_nen_first
            and open_nen_second < close_nen_second
            and open_nen_third < close_nen_third
            and (low_nen_third - low_nen_second) > 1
            and (high_nen_third - close_nen_third) < (close_nen_third - open_nen_third)
            and close_nen_third > open_nen_first
            and (close_nen_first - low_nen_first) < (open_nen_first - close_nen_first)
        )
        
        # Case 5 tăng (line 522)
        case5 = (
            open_nen_second > close_nen_second
            and open_nen_third < close_nen_third
            and low_nen_third < low_nen_second
            and close_nen_third > high_nen_second
            and (open_nen_third - low_nen_third) >= 0.5 * (close_nen_third - open_nen_third)
            and (high_nen_third - close_nen_third) >= 0.5 * (close_nen_third - open_nen_third)
            and (low_nen_third - low_nen_second) > 0.5
        )
        
        # DEBUG logging
        if m15_time and m15_time >= pd.Timestamp('2026-02-01 22:00:00') and m15_time <= pd.Timestamp('2026-02-02 02:00:00'):
            print(f"  Candle 1: o={open_nen_first:.2f}, h={high_nen_first:.2f}, l={low_nen_first:.2f}, c={close_nen_first:.2f}")
            print(f"  Candle 2: o={open_nen_second:.2f}, h={high_nen_second:.2f}, l={low_nen_second:.2f}, c={close_nen_second:.2f}")
            print(f"  Candle 3: o={open_nen_third:.2f}, h={high_nen_third:.2f}, l={low_nen_third:.2f}, c={close_nen_third:.2f}")
            print(f"  Case2={case2}, Case4={case4}, Case5={case5}")
        
        if case2 or case4 or case5:
            self.long_state.make_color_tang = True
            
            # Pine: box.new(bar_index-1, low_nen_third, last_bar_index, low_nen_second)
            # Trong Python ta map về bottom/top
            if case2 or case4:
                bottom = min(low_nen_second, low_nen_third)
                top = max(low_nen_second, low_nen_third)
            elif case5:
                bottom = low_nen_third
                top = low_nen_second
            
            # Case 4 đặc biệt: xoá zone cũ nếu zone mới bao toàn bộ (line 494-510)
            if case4 and len(self.long_state.arrayBoxDem) > 0:
                last_zone = self.long_state.arrayBoxDem[-1]
                if top > last_zone.price_top and bottom < last_zone.price_bottom:
                    self.long_state.arrayBoxDem.pop()
                    self.long_state.arrayBoxDem_cham.pop()
                    self.long_state.arrayBoxDem_status_touched.pop()
            
            zone = DemandSupplyZone(
                price_top=top,
                price_bottom=bottom,
                zone_type=ZoneType.DEMAND,
            )
            self.long_state.arrayBoxDem.append(zone)
            self.long_state.arrayBoxDem_cham.append(0)
            self.long_state.arrayBoxDem_status_touched.append(0)
    
    def _detect_buy_liquidity_m15(self):
        """
        Phát hiện Buy Liquidity (Clover) khi có M15 mới close.
        Mapping line 328-348 trong Pine.
        """
        if len(self.long_state.m15_closes) < 3:
            return
        
        lows = list(self.long_state.m15_lows)
        closes = list(self.long_state.m15_closes)
        opens = list(self.long_state.m15_opens)
        
        low_nen_first = lows[-3]
        low_nen_second = lows[-2]
        low_nen_third = lows[-1]
        
        close_nen_third = closes[-1]
        open_nen_first = opens[-3]
        
        # conditionBuyLiquidity (line 328)
        conditionBuyLiquidity = (
            low_nen_second < low_nen_first
            and low_nen_second < low_nen_third
            and close_nen_third > open_nen_first - self.diff
        )
        
        if conditionBuyLiquidity:
            # Kiểm tra không nằm trong Demand Zone hiện có (line 337)
            if len(self.long_state.arrayBoxDem) > 0:
                lastBoxBull = self.long_state.arrayBoxDem[-1]
                canhTrenLastBoxBull = lastBoxBull.price_top
                if not (low_nen_second < canhTrenLastBoxBull):
                    self.long_state.arrayBuyLiquidity.append(low_nen_second)
            else:
                self.long_state.arrayBuyLiquidity.append(low_nen_second)
    
    def _detect_supply_zones_m15(self):
        """
        Phát hiện Supply Zone (Case 2/4/5 giảm) khi có M15 mới close.
        Mapping line 1530-1586 trong Pine.
        """
        if len(self.long_state.m15_closes) < 3:
            return
        
        opens = list(self.long_state.m15_opens)
        closes = list(self.long_state.m15_closes)
        highs = list(self.long_state.m15_highs)
        lows = list(self.long_state.m15_lows)
        
        open_nen_first = opens[-3]
        open_nen_second = opens[-2]
        open_nen_third = opens[-1]
        
        close_nen_first = closes[-3]
        close_nen_second = closes[-2]
        close_nen_third = closes[-1]
        
        high_nen_first = highs[-3]
        high_nen_second = highs[-2]
        high_nen_third = highs[-1]
        
        low_nen_first = lows[-3]
        low_nen_second = lows[-2]
        low_nen_third = lows[-1]
        
        # Case 2 giảm (line 1530)
        case2 = (
            open_nen_second < close_nen_second
            and open_nen_third > close_nen_third
            and (close_nen_second - open_nen_second) <= 0.5 * (open_nen_third - close_nen_third)
            and close_nen_third < low_nen_second
            and high_nen_second > high_nen_third
            and abs(high_nen_second - close_nen_second) > abs(open_nen_second - close_nen_second)
            and (open_nen_second - low_nen_second) < (close_nen_second - open_nen_second)
            and (close_nen_third - low_nen_third) <= 0.25 * (open_nen_third - close_nen_third)
        )
        
        # Case 4 giảm (line 1542)
        case4 = (
            open_nen_first < close_nen_first
            and open_nen_second > close_nen_second
            and open_nen_third > close_nen_third
            and (high_nen_second - high_nen_third) > 1
            and (close_nen_third - low_nen_third) < (open_nen_third - close_nen_third)
            and close_nen_third < open_nen_first
            and (high_nen_first - close_nen_first) < (close_nen_first - open_nen_first)
        )
        
        # Case 5 giảm (line 1578)
        case5 = (
            open_nen_second < close_nen_second
            and open_nen_third > close_nen_third
            and high_nen_third > high_nen_second
            and close_nen_third < low_nen_second
            and (close_nen_third - low_nen_third) >= 0.5 * (open_nen_third - close_nen_third)
            and (high_nen_third - open_nen_third) >= 0.5 * (open_nen_third - close_nen_third)
            and (high_nen_third - high_nen_second) > 0.5
        )
        
        if case2 or case4 or case5:
            self.short_state.make_color_giam = True
            
            if case2 or case4:
                top = max(high_nen_second, high_nen_third)
                bottom = min(high_nen_second, high_nen_third)
            elif case5:
                top = high_nen_third
                bottom = high_nen_second
            
            # Case 4 đặc biệt: xoá zone cũ nếu zone mới bao toàn bộ (line 1552-1561)
            if case4 and len(self.short_state.arrayBoxSup) > 0:
                last_zone = self.short_state.arrayBoxSup[-1]
                if top > last_zone.price_top and bottom < last_zone.price_bottom:
                    self.short_state.arrayBoxSup.pop()
                    self.short_state.arrayBoxSup_cham.pop()
                    self.short_state.arrayBoxSup_status_touched.pop()
            
            zone = DemandSupplyZone(
                price_top=top,
                price_bottom=bottom,
                zone_type=ZoneType.SUPPLY,
            )
            self.short_state.arrayBoxSup.append(zone)
            self.short_state.arrayBoxSup_cham.append(0)
            self.short_state.arrayBoxSup_status_touched.append(0)
    
    def _detect_sell_liquidity_m15(self):
        """
        Phát hiện Sell Liquidity khi có M15 mới close.
        Mapping line 1403-1423 trong Pine.
        """
        if len(self.long_state.m15_closes) < 3:
            return
        
        highs = list(self.long_state.m15_highs)
        closes = list(self.long_state.m15_closes)
        opens = list(self.long_state.m15_opens)
        
        high_nen_first = highs[-3]
        high_nen_second = highs[-2]
        high_nen_third = highs[-1]
        
        close_nen_third = closes[-1]
        open_nen_first = opens[-3]
        
        # conditionSellLiquidity (line 1403)
        conditionSellLiquidity = (
            high_nen_second > high_nen_first
            and high_nen_second > high_nen_third
            and close_nen_third < open_nen_first - self.diff
        )
        
        if conditionSellLiquidity:
            # Kiểm tra không nằm trong Supply Zone hiện có (line 1406-1417)
            if len(self.short_state.arrayBoxSup) > 0:
                lastBoxBear = self.short_state.arrayBoxSup[-1]
                canhDuoiLastBoxBear = lastBoxBear.price_bottom
                if not (high_nen_second > canhDuoiLastBoxBear):
                    self.short_state.arraySellLiquidity.append(high_nen_second)
            else:
                self.short_state.arraySellLiquidity.append(high_nen_second)
    
    def _detect_red_candle(self, idx: int, o: float, h: float, l: float, c: float):
        """
        Phát hiện nến đỏ (line 850-855).
        Pine dùng open[1], close[1], high[1], low[1], high, open.
        """
        if idx < 1:
            return
        
        prev = self.m1.iloc[idx - 1]
        o1, h1, l1, c1 = prev['open'], prev['high'], prev['low'], prev['close']
        
        # Điều kiện nến đỏ (line 850)
        cond1 = (
            o1 > c1
            and (c1 - l1) < (o1 - c1) + 0.1
            and (h - o) < 0.33 * (h1 - c1)
        )
        cond2 = (
            c1 > o1
            and (h1 - c1) > (c1 - o1)
            and (o1 - l1) < (c1 - o1) + 0.1
            and (h - o) <= 0.33 * (h1 - o1)
        )
        
        if cond1 or cond2:
            self.long_state.make_color_giam = True
            self.long_state.arrayHighGiaNenGiam.append(h1)
            if len(self.long_state.arrayHighGiaNenGiam) > 9:
                self.long_state.arrayHighGiaNenGiam.pop(0)
            
            # DEBUG: Log red candle quanh target time
            ts = self.m1.index[idx]
            if ts >= pd.Timestamp('2026-02-01 23:30:00') and ts <= pd.Timestamp('2026-02-02 00:30:00'):
                print(f"[DEBUG-Red] {ts} | Red candle detected! high={h1:.2f}, total_red_candles={len(self.long_state.arrayHighGiaNenGiam)}")
    
    def _detect_green_candle(self, idx: int, o: float, h: float, l: float, c: float):
        """
        Phát hiện nến xanh (để tạo Sell Base) - ngược lại với nến đỏ.
        Tương tự logic line 850 nhưng điều kiện đảo ngược.
        """
        if idx < 1:
            return
        
        prev = self.m1.iloc[idx - 1]
        o1, h1, l1, c1 = prev['open'], prev['high'], prev['low'], prev['close']
        
        # Điều kiện nến xanh (ngược với nến đỏ)
        # Nến trước là xanh mạnh, nến hiện tại không có body dài về phía trên
        cond1 = (
            c1 > o1
            and (h1 - c1) < (c1 - o1) + 0.1
            and (o - l) < 0.33 * (c1 - l1)
        )
        cond2 = (
            o1 > c1
            and (c1 - l1) > (o1 - c1)
            and (h1 - o1) < (o1 - c1) + 0.1
            and (o - l) <= 0.33 * (o1 - l1)
        )
        
        if cond1 or cond2:
            self.short_state.make_color_tang = True
            self.short_state.arrayLowGiaNenTang.append(l1)
            if len(self.short_state.arrayLowGiaNenTang) > 9:
                self.short_state.arrayLowGiaNenTang.pop(0)
    
    def _manage_demand_zones(self, idx: int, o: float, h: float, l: float, c: float):
        """
        Quản lý Demand Zone: touch, xoá khi bị phá đáy hoặc chạm > 1 lần.
        (ĐÃ BỎ logic 17 phút timeout theo yêu cầu, chỉ giữ đúng 2 rule:
         1) giá phá cạnh dưới demand zone,
         2) zone bị chạm lần 2 sau khi hồi lên.)
        Mapping line 352-380, 572-620 (bỏ nhánh muoi_bay_phut_time_out).
        """
        # Xoá zone nếu cham > 1 lần (rule 2)
        if len(self.long_state.arrayBoxDem) > 0:
            for i in range(len(self.long_state.arrayBoxDem) - 1, -1, -1):
                zone = self.long_state.arrayBoxDem[i]
                so_lan = self.long_state.arrayBoxDem_cham[i]
                
                if so_lan > 1:
                    ts = self.m1.index[idx]
                    print(f"[{ts}] Demand Zone REMOVED (touched > 1): {zone.price_bottom:.2f}-{zone.price_top:.2f}, touches={so_lan}")
                    self.long_state.removePriceDemand = zone.price_top
                    self.long_state.arrayBoxDem.pop(i)
                    self.long_state.arrayBoxDem_cham.pop(i)
                    self.long_state.arrayBoxDem_status_touched.pop(i)
        
        # Touch Demand Zone (line 572-620)
        if len(self.long_state.arrayBoxDem) > 0 and not self.long_state.make_color_tang:
            for i in range(len(self.long_state.arrayBoxDem) - 1, -1, -1):
                zone = self.long_state.arrayBoxDem[i]
                so_lan = self.long_state.arrayBoxDem_cham[i]
                status_touched = self.long_state.arrayBoxDem_status_touched[i]
                
                canhDuoiLastBoxBull = zone.price_bottom
                canhTrenLastBoxBull = zone.price_top
                
                # Điều kiện touch (line 582)
                if ((l < canhTrenLastBoxBull and l > canhDuoiLastBoxBull) or (c < canhTrenLastBoxBull)):
                    if so_lan == 1 and status_touched == 0:
                        # ⭐ Xoá SELL BASE + Đóng SHORT (Pine line 672-682)
                        if len(self.short_state.arrayBoxSellBase) > 0:
                            self.short_state.arrayBoxSellBase.clear()
                            self.short_state.mang_so_lan_cham_sell_base.clear()
                            self.short_state.finding_entry_sell = False
                            self.short_state.finding_entry_sell_ten_minutes = 0
                            self.short_state.finding_entry_sell_time_out = 0
                            
                            # Đóng lệnh SHORT nếu có
                            if self.short_state.in_position:
                                ts = self.m1.index[idx]
                                self._force_exit_short(idx, ts, "Demand zone touched")
                            
                            ts = self.m1.index[idx]
                            print(f"[{ts}] ⚠️  CANCEL SELL FLOW (Demand zone touched)")
                        
                        # Xoá Buy Base cũ nếu có (line 603-613)
                        if len(self.long_state.arrayBoxBuyBase) > 0:
                            self.long_state.arrayBoxBuyBase.pop()
                            self.long_state.mang_so_lan_cham_buy_base.pop()
                            self.long_state.finding_entry_buy = False
                            self.long_state.finding_entry_buy_ten_minutes = 0
                            self.long_state.finding_entry_buy_time_out = 0
                        
                        if idx >= 2:
                            self.long_state.removeCandle_OpenPrice = self.m1.iloc[idx - 2]['open']
                        
                        self.long_state.liquid_finding_buy_base = False
                        self.long_state.demand_finding_buy_base = True
                        self.long_state.finding_entry_buy_time_out = 0
                        so_lan += 1
                        self.long_state.arrayBoxDem_cham[i] = so_lan
                        self.long_state.arrayBoxDem_status_touched[i] = 1
                        
                        print(f"[{ts}] Demand Zone TOUCHED (2nd time) @ {canhDuoiLastBoxBull:.2f}-{canhTrenLastBoxBull:.2f}! Now searching for Buy Base...")
                    
                    elif so_lan == 0 and not self.long_state.make_color_tang:
                        # Touch LẦN ĐẦU (line 660-713)
                        ts = self.m1.index[idx]
                        
                        # ⭐ Xoá SELL BASE + Đóng SHORT (Pine line 672-682)
                        if len(self.short_state.arrayBoxSellBase) > 0:
                            self.short_state.arrayBoxSellBase.clear()
                            self.short_state.mang_so_lan_cham_sell_base.clear()
                            self.short_state.finding_entry_sell = False
                            self.short_state.finding_entry_sell_ten_minutes = 0
                            self.short_state.finding_entry_sell_time_out = 0
                            
                            # Đóng lệnh SHORT nếu có
                            if self.short_state.in_position:
                                self._force_exit_short(idx, ts, "Demand zone touched (1st)")
                            
                            print(f"[{ts}] ⚠️  CANCEL SELL FLOW (Demand zone touched 1st)")
                        
                        # Xoá Buy Base cũ nếu có (line 661-670)
                        if len(self.long_state.arrayBoxBuyBase) > 0:
                            self.long_state.arrayBoxBuyBase.pop()
                            self.long_state.mang_so_lan_cham_buy_base.pop()
                            self.long_state.finding_entry_buy = False
                            self.long_state.finding_entry_buy_ten_minutes = 0
                            self.long_state.finding_entry_buy_time_out = 0
                        
                        if idx >= 2:
                            self.long_state.removeCandle_OpenPrice = self.m1.iloc[idx - 2]['open']
                        
                        so_lan += 1
                        self.long_state.liquid_finding_buy_base = False
                        self.long_state.demand_finding_buy_base = True
                        self.long_state.finding_entry_buy_time_out = 0
                        
                        self.long_state.arrayBoxDem_cham[i] = so_lan
                        self.long_state.arrayBoxDem_status_touched[i] = 1
                        
                        print(f"[{ts}] Demand Zone TOUCHED (1st time) @ {canhDuoiLastBoxBull:.2f}-{canhTrenLastBoxBull:.2f}! Now searching for Buy Base...")
    
    def _check_buy_liquidity_crossed(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Kiểm tra Buy Liquidity bị crossed (line 381-472).
        """
        if len(self.long_state.arrayBuyLiquidity) == 0:
            return
        
        for i in range(len(self.long_state.arrayBuyLiquidity) - 1, -1, -1):
            BuyLiquidity = self.long_state.arrayBuyLiquidity[i]
            
            if l < BuyLiquidity:
                # ⭐ Xoá SELL BASE + Đóng SHORT khi cross Buy Liquidity (Pine line 413-423)
                if len(self.short_state.arrayBoxSellBase) > 0:
                    self.short_state.arrayBoxSellBase.clear()
                    self.short_state.mang_so_lan_cham_sell_base.clear()
                    self.short_state.finding_entry_sell = False
                    self.short_state.finding_entry_sell_ten_minutes = 0
                    self.short_state.finding_entry_sell_time_out = 0
                    
                    # Đóng lệnh SHORT nếu có
                    if self.short_state.in_position:
                        self._force_exit_short(idx, ts, "Buy Liquidity crossed")
                    
                    print(f"[{ts}] ⚠️  CANCEL SELL FLOW (Buy Liquidity crossed)")
                
                # Xoá Demand Zone nếu cần (line 386-399)
                if len(self.long_state.arrayBoxDem) > 0:
                    lastBoxBull = self.long_state.arrayBoxDem[-1]
                    canhDuoiLastBoxBull = lastBoxBull.price_bottom
                    if l < canhDuoiLastBoxBull and self.long_state.muoi_bay_phut_time_out > 0:
                        self.long_state.muoi_bay_phut_time_out = 0
                        self.long_state.demand_finding_buy_base = False
                        self.long_state.arrayBoxDem.pop()
                        self.long_state.arrayBoxDem_cham.pop()
                        self.long_state.arrayBoxDem_status_touched.pop()
                
                # Xoá Buy Base cũ nếu có (line 400-440)
                if len(self.long_state.arrayBoxBuyBase) > 0:
                    self.long_state.arrayBoxBuyBase.pop()
                    self.long_state.mang_so_lan_cham_buy_base.pop()
                    self.long_state.finding_entry_buy = False
                    self.long_state.finding_entry_buy_time_out = 0
                    self.long_state.finding_entry_buy_ten_minutes = 0
                
                # Xoá liquidity và set state (line 425-430)
                self.long_state.arrayBuyLiquidity.pop(i)
                self.long_state.removePrice = BuyLiquidity
                self.long_state.removeCandle_OpenPrice = o
                self.long_state.liquid_finding_buy_base = True
                self.long_state.demand_finding_buy_base = False
                self.long_state.do_buy_base_2_lan = 0
                
                print(f"[{ts}] Buy Liquidity CROSSED @ {BuyLiquidity:.2f}! Now searching for Buy Base...")
                
                break
        
        # Thoát nếu giá quá xa liquidity (line 456-471)
        if l < self.long_state.removePrice - 5:
            self.long_state.liquid_finding_buy_base = False
            self.long_state.demand_finding_buy_base = False
            self.long_state.removePrice = 0
            self.long_state.finding_entry_buy = False
            self.long_state.finding_entry_buy_ten_minutes = 0
            self.long_state.finding_entry_buy_time_out = 0
            self.long_state.do_buy_base_2_lan = 0
            if len(self.long_state.arrayBoxBuyBase) > 0:
                self.long_state.arrayBoxBuyBase.pop()
                self.long_state.mang_so_lan_cham_buy_base.pop()
    
    def _create_buy_base_from_liquidity(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Tạo Buy Base từ Liquidity (line 856-937).
        """
        if not self.long_state.liquid_finding_buy_base or len(self.long_state.arrayHighGiaNenGiam) == 0:
            return
        
        high_giam = self.long_state.arrayHighGiaNenGiam[-1]
        
        if h > high_giam or self.long_state.keep_finding_liquid_buy:
            if not self.long_state.keep_finding_liquid_buy:
                # Tìm index của high gần nhất
                self.long_state.index_of_high_nearest = 1
                for j in range(1, min(idx, 20)):
                    if self.m1.iloc[idx - j]['high'] == high_giam:
                        self.long_state.index_of_high_nearest = j
                        break
            
            self.long_state.hai_phut_hon_liquid += 1
            self.long_state.keep_finding_liquid_buy = True
            
            if self.long_state.hai_phut_hon_liquid > 2:
                self.long_state.hai_phut_hon_liquid = 0
                self.long_state.keep_finding_liquid_buy = False
                
                # Xoá các high đã vượt qua
                while len(self.long_state.arrayHighGiaNenGiam) > 0:
                    if h > self.long_state.arrayHighGiaNenGiam[-1]:
                        self.long_state.arrayHighGiaNenGiam.pop()
                    else:
                        break
                
                # Tìm Buy Base trong vòng for j = 0 to 5 (line 890-936)
                buy_base = self._find_buy_base_in_window(idx, is_from_liquidity=True)
                if buy_base is not None:
                    self.long_state.arrayBoxBuyBase.append(buy_base)
                    self.long_state.mang_so_lan_cham_buy_base.append(0)
                    self.long_state.liquid_finding_buy_base = False
                    self.long_state.making_buy_base = True
                    self.long_state.finding_entry_buy_time_out = self.long_state.index_of_high_nearest + 2
                    self.long_state.do_buy_base_2_lan += 1
    
    def _create_buy_base_from_demand(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Tạo Buy Base từ Demand (line 943-1032).
        """
        if not self.long_state.demand_finding_buy_base or len(self.long_state.arrayHighGiaNenGiam) == 0:
            return
        
        high_giam = self.long_state.arrayHighGiaNenGiam[-1]
        
        if h > high_giam or self.long_state.keep_finding_demand:
            if not self.long_state.keep_finding_demand:
                self.long_state.index_of_high_nearest = 1
                for j in range(1, min(idx, 20)):
                    if self.m1.iloc[idx - j]['high'] == high_giam:
                        self.long_state.index_of_high_nearest = j
                        break
            
            self.long_state.keep_finding_demand = True
            self.long_state.hai_phut_hon_demand += 1
            
            if self.long_state.hai_phut_hon_demand > 2:
                self.long_state.arrayHighGiaNenGiam.pop()
                self.long_state.hai_phut_hon_demand = 0
                self.long_state.keep_finding_demand = False
                
                while len(self.long_state.arrayHighGiaNenGiam) > 0:
                    if h > self.long_state.arrayHighGiaNenGiam[-1]:
                        self.long_state.arrayHighGiaNenGiam.pop()
                    else:
                        break
                
                buy_base = self._find_buy_base_in_window(idx, is_from_liquidity=False)
                if buy_base is not None:
                    self.long_state.arrayBoxBuyBase.append(buy_base)
                    self.long_state.mang_so_lan_cham_buy_base.append(0)
                    self.long_state.demand_finding_buy_base = False
                    self.long_state.making_buy_base = True
                    self.long_state.finding_entry_buy_time_out = self.long_state.index_of_high_nearest + 2
                    self.long_state.do_buy_base_2_lan += 1
    
    def _find_buy_base_in_window(self, idx: int, is_from_liquidity: bool) -> Optional[BuySellBase]:
        """
        Tìm Buy Base trong window 0-5 nến trước đó.
        Port từ line 890-936 (Liquidity) hoặc 967-1023 (Demand).
        """
        for j in range(6):
            if idx < j + 3:
                continue
            
            # Kiểm tra removeCandle_OpenPrice
            if self.m1.iloc[idx - j]['open'] == self.long_state.removeCandle_OpenPrice:
                break
            
            # Pattern nến (line 905 hoặc 978)
            idx_j = idx - j
            idx_j1 = idx - j - 1
            idx_j2 = idx - j - 2
            
            if idx_j1 < 0 or idx_j2 < 0:
                continue
            
            r_j = self.m1.iloc[idx_j]
            r_j1 = self.m1.iloc[idx_j1]
            r_j2 = self.m1.iloc[idx_j2]
            
            o_j, h_j, l_j, c_j = r_j['open'], r_j['high'], r_j['low'], r_j['close']
            o_j1, h_j1, l_j1, c_j1 = r_j1['open'], r_j1['high'], r_j1['low'], r_j1['close']
            o_j2, h_j2, l_j2, c_j2 = r_j2['open'], r_j2['high'], r_j2['low'], r_j2['close']
            
            # Điều kiện pattern phức tạp (line 905/978)
            cond1 = (
                c_j1 > o_j1
                and (h_j1 - c_j1) < (c_j1 - o_j1) + 0.1
                and (o_j - l_j) < 0.33 * (c_j1 - l_j1)
            )
            cond2 = (
                o_j1 > c_j1
                and (c_j1 - l_j1) > (o_j1 - c_j1)
                and (h_j1 - o_j1) < (o_j1 - c_j1) + 0.1
                and (o_j - l_j) <= 0.33 * (o_j1 - l_j1)
            )
            
            cond_neg1 = (
                c_j2 > o_j2
                and (h_j2 - c_j2) < (c_j2 - o_j2) + 0.1
                and (o_j1 - l_j1) < 0.33 * (c_j2 - l_j2)
            )
            cond_neg2 = (
                o_j2 > c_j2
                and (c_j2 - l_j2) > (o_j2 - c_j2)
                and (h_j2 - o_j2) < (o_j2 - c_j2) + 0.1
                and (o_j1 - l_j1) <= 0.33 * (o_j2 - l_j2)
            )
            
            if (cond1 or cond2) and not (cond_neg1 or cond_neg2):
                # Tính x, y (line 908-925 hoặc 981-999)
                if l_j1 < l_j2:
                    x = l_j1
                    k = j + 2
                else:
                    x = l_j2
                    k = j + 2
                
                y = 0.0
                
                if k >= 2 and idx - k + 2 >= 0:
                    idx_k_minus_2 = idx - k + 2
                    idx_k = idx - k
                    idx_k_minus_1 = idx - k + 1
                    
                    if idx_k >= 0 and idx_k_minus_1 >= 0:
                        r_k = self.m1.iloc[idx_k]
                        r_k_minus_1 = self.m1.iloc[idx_k_minus_1]
                        r_k_minus_2 = self.m1.iloc[idx_k_minus_2]
                        
                        if (r_k_minus_2['low'] - r_k['high']) > 0.05 and r_k_minus_1['open'] < r_k_minus_1['close']:
                            y = r_k_minus_2['low']
                
                if k >= 3 and idx - k + 3 >= 0:
                    idx_k_minus_3 = idx - k + 3
                    idx_k_minus_1 = idx - k + 1
                    idx_k_minus_2 = idx - k + 2
                    
                    if idx_k_minus_1 >= 0 and idx_k_minus_2 >= 0 and idx_k_minus_3 >= 0:
                        r_k_minus_1 = self.m1.iloc[idx_k_minus_1]
                        r_k_minus_2 = self.m1.iloc[idx_k_minus_2]
                        r_k_minus_3 = self.m1.iloc[idx_k_minus_3]
                        
                        if (r_k_minus_3['low'] - r_k_minus_1['high']) > 0.05 and r_k_minus_2['open'] < r_k_minus_2['close']:
                            y = r_k_minus_3['low']
                
                if k >= 4 and idx - k + 4 >= 0:
                    idx_k_minus_4 = idx - k + 4
                    idx_k_minus_3 = idx - k + 3
                    idx_k_minus_2 = idx - k + 2
                    
                    if idx_k_minus_2 >= 0 and idx_k_minus_3 >= 0 and idx_k_minus_4 >= 0:
                        r_k_minus_2 = self.m1.iloc[idx_k_minus_2]
                        r_k_minus_3 = self.m1.iloc[idx_k_minus_3]
                        r_k_minus_4 = self.m1.iloc[idx_k_minus_4]
                        
                        if y == r_k_minus_3['low'] and (r_k_minus_4['low'] - r_k_minus_2['high']) > 0.05 and r_k_minus_3['open'] < r_k_minus_3['close']:
                            y = r_k_minus_4['low']
                
                # Kiểm tra thêm điều kiện từ Demand (line 1001-1014)
                if not is_from_liquidity and x > 0 and y > 0:
                    canhTrenLastBoxBull = 100000
                    if len(self.long_state.arrayBoxDem) > 0:
                        lastBoxBull = self.long_state.arrayBoxDem[-1]
                        canhTrenLastBoxBull = lastBoxBull.price_top
                        current_low = self.m1.iloc[idx]['low']
                        if current_low - canhTrenLastBoxBull > current_low - self.long_state.removePriceDemand:
                            canhTrenLastBoxBull = self.long_state.removePriceDemand
                    else:
                        if self.long_state.removePriceDemand != 0:
                            canhTrenLastBoxBull = self.long_state.removePriceDemand
                    
                    if not (x < canhTrenLastBoxBull + 0.5):
                        return None
                
                if x > 0 and y > 0:
                    return BuySellBase(
                        price_top=y,
                        price_bottom=x,
                        direction=TradeDirection.BUY,
                    )
        
        return None
    
    def _manage_buy_base_timeout(self, idx: int, ts: pd.Timestamp, h: float, l: float):
        """
        Timeout cho Buy Base (line 1033-1071).
        """
        if self.long_state.finding_entry_buy_time_out > 0:
            self.long_state.finding_entry_buy_time_out += 1
        
        # Timeout 60 phút khi finding_entry_buy == True (line 1038-1056)
        if (self.long_state.finding_entry_buy_time_out > 60
            and len(self.long_state.arrayBoxBuyBase) > 0
            and self.long_state.finding_entry_buy):
            
            self.long_state.arrayBoxBuyBase.clear()
            self.long_state.mang_so_lan_cham_buy_base.clear()
            self.long_state.finding_entry_buy_ten_minutes = 0
            self.long_state.finding_entry_buy = False
            self.long_state.finding_entry_buy_time_out = 0
            self.long_state.demand_finding_buy_base = False
            self.long_state.liquid_finding_buy_base = False
        
        # Timeout 80 phút khi finding_entry_buy == False (line 1057-1071)
        if (self.long_state.finding_entry_buy_time_out > 80
            and not self.long_state.finding_entry_buy):
            
            if len(self.long_state.arrayBoxBuyBase) > 0:
                self.long_state.arrayBoxBuyBase.pop()
                self.long_state.mang_so_lan_cham_buy_base.pop()
            
            self.long_state.finding_entry_buy_ten_minutes = 0
            self.long_state.finding_entry_buy = False
            self.long_state.demand_finding_buy_base = False
            self.long_state.liquid_finding_buy_base = False
            self.long_state.finding_entry_buy_time_out = 0
    
    def _check_buy_base_touched(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Kiểm tra Buy Base bị chạm → set finding_entry_buy (line 1074-1099).
        """
        if len(self.long_state.arrayBoxBuyBase) == 0:
            return
        
        lastBoxBull = self.long_state.arrayBoxBuyBase[-1]
        canhTrenLastBoxBull = lastBoxBull.price_top
        canhDuoiLastBoxBullBase = lastBoxBull.price_bottom
        so_lan_cham_buy_base = self.long_state.mang_so_lan_cham_buy_base[-1]
        
        # Touch (line 1082-1087)
        if (
            ((c < canhTrenLastBoxBull and c > canhDuoiLastBoxBullBase)
             or (l < canhTrenLastBoxBull and l > canhDuoiLastBoxBullBase))
            and not self.long_state.finding_entry_buy
            and not self.long_state.making_buy_base
            and so_lan_cham_buy_base == 0
        ):
            so_lan_cham_buy_base += 1
            self.long_state.mang_so_lan_cham_buy_base[-1] = so_lan_cham_buy_base
            self.long_state.finding_entry_buy = True
        
        # Phá đáy Buy Base → ten_minutes (line 1090-1099)
        if l < canhDuoiLastBoxBullBase - 0.5 and self.long_state.finding_entry_buy_ten_minutes == 0:
            self.long_state.finding_entry_buy_ten_minutes += 1
    
    def _check_buy_base_invalidation(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Kiểm tra Buy Base bị phá hoặc chạm cản (Pine line 1322-1368).
        Đóng lệnh nếu đang trong position.
        """
        if len(self.long_state.arrayBoxBuyBase) == 0:
            return
        
        lastBoxBull = self.long_state.arrayBoxBuyBase[-1]
        canhTrenLastBoxBull = lastBoxBull.price_top
        canhDuoiLastBoxBullBase = lastBoxBull.price_bottom
        
        # Increment ten_minutes counter (Pine line 1349-1350)
        if self.long_state.finding_entry_buy_ten_minutes > 0:
            self.long_state.finding_entry_buy_ten_minutes += 1
        
        # Case 1: Sau 10 phút, giá phá đáy base - 0.5 (Pine line 1322-1349)
        if self.long_state.finding_entry_buy_ten_minutes > 10:
            if l < canhDuoiLastBoxBullBase - 0.5:
                # Xóa Buy Base
                self.long_state.arrayBoxBuyBase.pop()
                self.long_state.mang_so_lan_cham_buy_base.pop()
                self.long_state.finding_entry_buy = False
                self.long_state.finding_entry_buy_time_out = 0
                self.long_state.finding_entry_buy_ten_minutes = 0
                
                # Đóng lệnh nếu đang trong position
                if self.long_state.in_position:
                    self._complete_long_trade(ts, c, "Buy Base broken after 10min")
                
                # Xử lý liquidity finding (line 1341-1344)
                if self.long_state.do_buy_base_2_lan == 1:
                    self.long_state.do_buy_base_2_lan += 1
                    self.long_state.liquid_finding_buy_base = True
                
                print(f"[{ts}] Buy Base REMOVED (broken after 10min)")
                return
        
        # Case 2: Giá chạm "cản" (1 khoảng base từ đáy) (Pine line 1352-1368)
        base_height = canhTrenLastBoxBull - canhDuoiLastBoxBullBase
        if l <= canhDuoiLastBoxBullBase - base_height:
            # Xóa Buy Base
            self.long_state.arrayBoxBuyBase.pop()
            self.long_state.mang_so_lan_cham_buy_base.pop()
            self.long_state.finding_entry_buy = False
            self.long_state.finding_entry_buy_time_out = 0
            self.long_state.finding_entry_buy_ten_minutes = 0
            
            # Đóng lệnh nếu đang trong position
            if self.long_state.in_position:
                self._complete_long_trade(ts, c, "Buy Base resistance hit")
            
            # Xử lý liquidity finding (line 1366-1369)
            if self.long_state.do_buy_base_2_lan == 1:
                self.long_state.do_buy_base_2_lan += 1
                self.long_state.liquid_finding_buy_base = False
                self.long_state.demand_finding_buy_base = True
            
            print(f"[{ts}] Buy Base REMOVED (resistance hit)")
            return
    
    def _calculate_adx(self, idx: int, o: float, h: float, l: float, c: float):
        """
        Tính ADX (line 121-142).
        """
        if idx < 1:
            return
        
        prev = self.m1.iloc[idx - 1]
        c1 = prev['close']
        h1 = prev['high']
        l1 = prev['low']
        
        # TrueRange (line 126)
        TrueRange = max(
            h - l,
            abs(h - c1),
            abs(l - c1)
        )
        
        # DirectionalMovement (line 127-128)
        if (h - h1) > (l1 - l):
            DirectionalMovementPlus = max(h - h1, 0)
        else:
            DirectionalMovementPlus = 0
        
        if (l1 - l) > (h - h1):
            DirectionalMovementMinus = max(l1 - l, 0)
        else:
            DirectionalMovementMinus = 0
        
        # Smoothed values (line 130-137)
        self.SmoothedTrueRange = self.SmoothedTrueRange - (self.SmoothedTrueRange / self.adx_len) + TrueRange
        self.SmoothedDirectionalMovementPlus = self.SmoothedDirectionalMovementPlus - (self.SmoothedDirectionalMovementPlus / self.adx_len) + DirectionalMovementPlus
        self.SmoothedDirectionalMovementMinus = self.SmoothedDirectionalMovementMinus - (self.SmoothedDirectionalMovementMinus / self.adx_len) + DirectionalMovementMinus
        
        # DI and DX (line 139-141)
        if self.SmoothedTrueRange > 0:
            DIPlus = self.SmoothedDirectionalMovementPlus / self.SmoothedTrueRange * 100
            DIMinus = self.SmoothedDirectionalMovementMinus / self.SmoothedTrueRange * 100
            
            if (DIPlus + DIMinus) > 0:
                DX = abs(DIPlus - DIMinus) / (DIPlus + DIMinus) * 100
                self.DX_buffer.append(DX)
        
        # ADX = SMA of DX (line 142)
        if len(self.DX_buffer) >= self.adx_len:
            old_adx = self.ADX
            self.ADX = sum(self.DX_buffer) / len(self.DX_buffer)
            
    
    def _log_timestamp(self, ts: pd.Timestamp) -> str:
        """Format timestamp for logging in Bangkok timezone (UTC+7)."""
        ts_bangkok = ts.tz_localize('UTC').tz_convert('Asia/Bangkok')
        return ts_bangkok.strftime('%Y-%m-%d %H:%M:%S %Z')
    
    def _is_within_timerange(self, ts: pd.Timestamp) -> bool:
        """
        Kiểm tra thời gian có trong khoảng trading không (line 144-163).
        Giả sử timezone UTC+7.
        """
        if not self.config.enable_timerange_filter:
            return True

        # Chuyển sang UTC+7
        ts_utc7 = ts.tz_localize('UTC').tz_convert('Asia/Bangkok')
        hour = ts_utc7.hour
        minute = ts_utc7.minute
        time_in_minutes = hour * 60 + minute
        
        # Các khoảng thời gian cấu hình trong config (phút từ 00:00)
        for start_min, end_min in self.config.trading_sessions:
            if start_min <= time_in_minutes < end_min:
                return True
        return False
    
    # =========================================================================
    # PAPER TRADE MODE (Circuit Breaker) - see research.md Section 5
    # =========================================================================
    
    def _check_paper_mode_trigger(self) -> bool:
        """
        Check if should switch to Paper Mode.
        Called after every trade closes in LIVE mode.
        
        Returns:
            True if should activate paper mode.
        """
        if not self.config.enable_paper_mode:
            return False
        
        if self.paper_state.is_active:
            return False  # Already in paper mode
        
        # Condition 1: Consecutive losses >= threshold
        if self.paper_state.consecutive_losses >= self.config.paper_trigger_consecutive_losses:
            return True
        
        # Condition 2: Win rate (last N trades) < threshold
        if len(self.paper_state.recent_results) >= self.config.paper_trigger_win_rate_window:
            wins = sum(1 for r in self.paper_state.recent_results if r > 0)
            win_rate = wins / len(self.paper_state.recent_results)
            if win_rate < self.config.paper_trigger_win_rate_threshold:
                return True
        
        return False
    
    def _check_paper_mode_recovery(self, current_time: pd.Timestamp) -> bool:
        """
        Check if should switch back to LIVE mode.
        Called after every trade closes in PAPER mode.
        
        Returns:
            True if should deactivate paper mode.
        """
        if not self.paper_state.is_active:
            return False
        
        # Time limit check (force exit paper mode)
        if self.paper_state.activated_at is not None:
            duration_minutes = (current_time - self.paper_state.activated_at).total_seconds() / 60
            if duration_minutes >= self.config.paper_max_duration_minutes:
                return True
        
        # Recovery conditions (must meet ALL)
        pnl_ok = (
            not self.config.paper_recovery_require_positive_pnl 
            or self.paper_state.paper_pnl > 0
        )
        wins_ok = self.paper_state.paper_consecutive_wins >= self.config.paper_recovery_min_wins
        
        return pnl_ok and wins_ok
    
    def _activate_paper_mode(self, ts: pd.Timestamp, reason: str):
        """Activate paper trading mode."""
        self.paper_state.is_active = True
        self.paper_state.activated_at = ts
        self.paper_state.paper_pnl = 0.0
        self.paper_state.paper_consecutive_wins = 0
        self.paper_state.paper_trades = []
        self.paper_state.activation_count += 1
        
        print(f"⚠️ [{self._log_timestamp(ts)}] PAPER MODE ON | {reason}")
    
    def _deactivate_paper_mode(self, ts: pd.Timestamp, reason: str):
        """Deactivate paper trading mode and return to live."""
        if self.paper_state.activated_at is not None:
            duration_minutes = (ts - self.paper_state.activated_at).total_seconds() / 60
            self.paper_state.total_time_in_paper_minutes += duration_minutes
        
        # Reset consecutive losses when exiting paper mode successfully
        self.paper_state.consecutive_losses = 0
        self.paper_state.is_active = False
        self.paper_state.activated_at = None
        
        print(f"✅ [{self._log_timestamp(ts)}] PAPER MODE OFF | {reason}")
    
    def _on_trade_closed(self, pnl: float, ts: pd.Timestamp, trade: "Trade"):
        """
        Handle post-trade logic: update tracking, check paper mode trigger/recovery.
        
        Args:
            pnl: The PnL of the closed trade
            ts: Timestamp when trade closed
            trade: The Trade object
        """
        is_win = pnl > 0
        
        if trade.is_paper:
            # Paper trade handling
            self.paper_state.paper_trades.append(trade)
            self.paper_state.paper_pnl += pnl
            
            if is_win:
                self.paper_state.paper_consecutive_wins += 1
            else:
                self.paper_state.paper_consecutive_wins = 0
            
            paper_count = len(self.paper_state.paper_trades)
            print(f"📝 [PAPER #{paper_count}] PnL: {pnl:+.0f} USD | "
                  f"Paper streak: {self.paper_state.paper_consecutive_wins}W | "
                  f"Paper total: {self.paper_state.paper_pnl:+.0f} USD")
            
            # Check recovery
            if self._check_paper_mode_recovery(ts):
                reason = (f"Recovered! Paper PnL: {self.paper_state.paper_pnl:+.0f} USD, "
                         f"Wins: {self.paper_state.paper_consecutive_wins}")
                if self.paper_state.activated_at is not None:
                    duration = (ts - self.paper_state.activated_at).total_seconds() / 60
                    if duration >= self.config.paper_max_duration_minutes:
                        reason = f"Max duration ({self.config.paper_max_duration_minutes}min) reached"
                self._deactivate_paper_mode(ts, reason)
        else:
            # Live trade handling
            self.paper_state.recent_results.append(pnl)
            
            if is_win:
                self.paper_state.consecutive_losses = 0
            else:
                self.paper_state.consecutive_losses += 1
            
            # Check trigger
            if self._check_paper_mode_trigger():
                if self.paper_state.consecutive_losses >= self.config.paper_trigger_consecutive_losses:
                    reason = f"{self.paper_state.consecutive_losses} consecutive losses"
                else:
                    wins = sum(1 for r in self.paper_state.recent_results if r > 0)
                    win_rate = wins / len(self.paper_state.recent_results) * 100
                    reason = f"Win rate {win_rate:.1f}% ({wins}/{len(self.paper_state.recent_results)}) below threshold"
                self._activate_paper_mode(ts, reason)
    
    def _is_paper_mode(self) -> bool:
        """Check if currently in paper mode."""
        return self.config.enable_paper_mode and self.paper_state.is_active
    
    def _complete_long_trade(self, ts: pd.Timestamp, exit_price: float, exit_reason: str):
        """
        Complete a long trade: calculate PnL, update equity, track paper mode.
        
        Args:
            ts: Exit timestamp
            exit_price: Price at exit
            exit_reason: Description of exit reason for logging
        """
        if not self.long_state.in_position:
            return
        
        pnl = (exit_price - self.long_state.entry_price) * self.long_state.lot_size * 0.1
        is_paper = self._is_paper_mode()
        
        trade = Trade(
            entry_time=self.long_state.entry_time,
            exit_time=ts,
            direction=TradeDirection.BUY,
            entry_price=self.long_state.entry_price,
            exit_price=exit_price,
            stop_loss=self.long_state.stop_loss,
            take_profit=self.long_state.take_profit,
            lot_size=self.long_state.lot_size,
            pnl=pnl,
            is_paper=is_paper,
        )
        
        if not is_paper:
            # Live trade: update equity
            self.current_equity += pnl
            self.trades.append(trade)
            self.equity_curve.append(self.current_equity)
            if self.current_equity > self.peak_equity:
                self.peak_equity = self.current_equity
            
            mode_prefix = ""
        else:
            mode_prefix = "📝 [PAPER] "
        
        # Reset position state
        self.long_state.in_position = False
        self.long_state.doi_sl_05R = False
        
        # Log exit
        ts_bkk = self._log_timestamp(ts)
        print(f"{mode_prefix}[{ts_bkk}] EXIT LONG ({exit_reason}) @ {exit_price:.2f}, PnL={pnl:+.0f} USD")
        
        # Handle post-trade logic (paper mode trigger/recovery)
        self._on_trade_closed(pnl, ts, trade)
    
    def _complete_short_trade(self, ts: pd.Timestamp, exit_price: float, exit_reason: str):
        """
        Complete a short trade: calculate PnL, update equity, track paper mode.
        
        Args:
            ts: Exit timestamp
            exit_price: Price at exit
            exit_reason: Description of exit reason for logging
        """
        if not self.short_state.in_position:
            return
        
        pnl = (self.short_state.entry_price - exit_price) * self.short_state.lot_size * 0.1
        is_paper = self._is_paper_mode()
        
        trade = Trade(
            entry_time=self.short_state.entry_time,
            exit_time=ts,
            direction=TradeDirection.SELL,
            entry_price=self.short_state.entry_price,
            exit_price=exit_price,
            stop_loss=self.short_state.stop_loss,
            take_profit=self.short_state.take_profit,
            lot_size=self.short_state.lot_size,
            pnl=pnl,
            is_paper=is_paper,
        )
        
        if not is_paper:
            # Live trade: update equity
            self.current_equity += pnl
            self.trades.append(trade)
            self.equity_curve.append(self.current_equity)
            if self.current_equity > self.peak_equity:
                self.peak_equity = self.current_equity
            
            mode_prefix = ""
        else:
            mode_prefix = "📝 [PAPER] "
        
        # Reset position state
        self.short_state.in_position = False
        self.short_state.doi_sl_05R = False
        
        # Log exit
        ts_bkk = self._log_timestamp(ts)
        print(f"{mode_prefix}[{ts_bkk}] EXIT SHORT ({exit_reason}) @ {exit_price:.2f}, PnL={pnl:+.0f} USD")
        
        # Handle post-trade logic (paper mode trigger/recovery)
        self._on_trade_closed(pnl, ts, trade)
    
    def _entry_long(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Entry Long (line 1103-1275).
        """
        # Kiểm tra điều kiện cơ bản (line 1103)
        if not self.long_state.finding_entry_buy:
            return
        
        if not self._is_within_timerange(ts):
            return
        
        if len(self.long_state.arrayBoxBuyBase) == 0:
            return
        
        lastBoxBull = self.long_state.arrayBoxBuyBase[-1]
        canhTrenLastBoxBull = lastBoxBull.price_top
        canhDuoiLastBoxBullBase = lastBoxBull.price_bottom
        
        # Nếu finding_entry_buy_ten_minutes <= 0 (line 1107)
        if self.long_state.finding_entry_buy_ten_minutes <= 0:
            # Điều kiện nến (line 1109)
            if idx < 2:
                return
            
            prev1 = self.m1.iloc[idx - 1]
            prev2 = self.m1.iloc[idx - 2]
            
            o1, c1 = prev1['open'], prev1['close']
            o2, c2 = prev2['open'], prev2['close']
            l1, l2 = prev1['low'], prev2['low']
            
            if not (o < c and min(l, l1, l2) < canhTrenLastBoxBull + 0.5):
                return
            
            # Case 1: open[2] > close[2] (line 1110-1148)
            if o2 > c2:
                if (
                    (c >= o2)
                    and (h - c) < (c - o)
                    and self.ADX < self.config.adx_max_entry
                    and self.long_state.finding_entry_buy_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_long(idx, ts, c, canhDuoiLastBoxBullBase)
            # Case 2: open[1] > close[1] and open[2] < close[2] (line 1150-1190)
            elif o1 > c1 and o2 < c2:
                if (
                    (c >= c2)
                    and (h - c) < (c - o)
                    and self.ADX < self.config.adx_max_entry
                    and self.long_state.finding_entry_buy_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_long(idx, ts, c, canhDuoiLastBoxBullBase)
        
        # Nếu finding_entry_buy_ten_minutes > 0 (line 1192-1275)
        elif self.long_state.finding_entry_buy_ten_minutes > 0:
            if idx < 2:
                return
            
            prev1 = self.m1.iloc[idx - 1]
            prev2 = self.m1.iloc[idx - 2]
            
            o1, c1 = prev1['open'], prev1['close']
            o2, c2 = prev2['open'], prev2['close']
            l1, l2 = prev1['low'], prev2['low']
            
            if not (o < c and min(l, l1, l2) < canhTrenLastBoxBull + 0.5):
                return
            
            # Tính sl_buy = ta.lowest(10) (line 295)
            sl_buy = min(self.m1.iloc[max(0, idx-9):idx+1]['low'])
            
            if o2 > c2:
                if (
                    (c >= o2)
                    and (h - c) < (c - o)
                    and self.ADX < self.config.adx_max_entry
                    and self.long_state.finding_entry_buy_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_long_with_sl_buy(idx, ts, c, sl_buy)
            elif o1 > c1 and o2 < c2:
                if (
                    (c >= c2)
                    and (h - c) < (c - o)
                    and self.ADX < self.config.adx_max_entry
                    and self.long_state.finding_entry_buy_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_long_with_sl_buy(idx, ts, c, sl_buy)
    
    def _execute_entry_long(self, idx: int, ts: pd.Timestamp, entry_price: float, base_bottom: float):
        """
        Thực hiện entry Long với SL = base_bottom - 0.5.
        Chỉ entry nếu TP hợp lệ (Pine line 1121-1123).
        """
        # ⭐ CHECK CONFLICT: Nếu đang có SHORT → Đóng SHORT trước
        if self.short_state.in_position:
            self._force_exit_short(idx, ts, "Conflict: Opening LONG")
        
        sellLiquidity_entry = 200000.0
        canhDuoiLastBoxSell_entry = 200000.0
        
        # Lấy Supply zone và Sell liquidity
        if len(self.short_state.arrayBoxSup) > 0:
            canhDuoiLastBoxSell_entry = self.short_state.arrayBoxSup[-1].price_bottom
        
        if len(self.short_state.arraySellLiquidity) > 0:
            sellLiquidity_entry = self.short_state.arraySellLiquidity[-1]
        
        closest_tp_buy = min(canhDuoiLastBoxSell_entry, sellLiquidity_entry)
        
        buffer = self.config.zone_touch_buffer
        one_r = entry_price - (base_bottom - buffer)

        # Pine line 1121: if close + (close - canhDuoiLastBoxBullBase + 0.5) < closest_tp_buy
        # CHỈ entry nếu điều kiện này đúng
        if entry_price + one_r < closest_tp_buy:
            # Pine line 1122 – dùng r_r_ratio_target để scale R
            tp_2R = entry_price + self.config.r_r_ratio_target * one_r
            closest_tp_buy = min(tp_2R, closest_tp_buy)
        else:
            # Không entry nếu TP không hợp lý (TP nằm phía dưới entry)
            return
        
        stop_loss = base_bottom - buffer
        take_profit = closest_tp_buy
        
        risk_per_trade = self.config.risk_per_trade
        capital = self.current_equity
        risk_amount = (risk_per_trade / 100) * capital
        pip_value = 0.1
        sl_distance = abs(entry_price - stop_loss)
        
        if sl_distance > 0:
            lot_size = risk_amount / (sl_distance * pip_value)
        else:
            lot_size = 0.0
        
        # Tạo trade
        self.long_state.in_position = True
        self.long_state.entry_price = entry_price
        self.long_state.stop_loss = stop_loss
        self.long_state.take_profit = take_profit
        self.long_state.lot_size = lot_size
        self.long_state.entry_time = ts
        self.long_state.finding_entry_buy = False
        self.long_state.doi_sl_05R = True
    
    def _execute_entry_long_with_sl_buy(self, idx: int, ts: pd.Timestamp, entry_price: float, sl_buy: float):
        """
        Thực hiện entry Long với SL = sl_buy - 0.5.
        Chỉ entry nếu TP hợp lệ (Pine line 1207-1209).
        """
        # ⭐ CHECK CONFLICT: Nếu đang có SHORT → Đóng SHORT trước
        if self.short_state.in_position:
            self._force_exit_short(idx, ts, "Conflict: Opening LONG (with sl_buy)")
        
        sellLiquidity_entry = 200000.0
        canhDuoiLastBoxBear_entry = 200000.0
        
        # Lấy Supply zone và Sell liquidity
        if len(self.short_state.arrayBoxSup) > 0:
            canhDuoiLastBoxBear_entry = self.short_state.arrayBoxSup[-1].price_bottom
        
        if len(self.short_state.arraySellLiquidity) > 0:
            sellLiquidity_entry = self.short_state.arraySellLiquidity[-1]
        
        closest_tp_buy = min(canhDuoiLastBoxBear_entry, sellLiquidity_entry)
        
        buffer = self.config.zone_touch_buffer
        one_r = entry_price - (sl_buy - buffer)

        # Pine line 1207: if close + (close - sl_buy + 0.5) < closest_tp_buy
        # CHỈ entry nếu điều kiện này đúng
        if entry_price + one_r < closest_tp_buy:
            # Pine line 1208
            tp_2R = entry_price + self.config.r_r_ratio_target * one_r
            closest_tp_buy = min(tp_2R, closest_tp_buy)
        else:
            # Không entry nếu TP không hợp lý
            return
        
        stop_loss = sl_buy - buffer
        take_profit = closest_tp_buy
        
        risk_per_trade = self.config.risk_per_trade
        capital = self.current_equity
        risk_amount = (risk_per_trade / 100) * capital
        pip_value = 0.1
        sl_distance = abs(entry_price - stop_loss)
        
        if sl_distance > 0:
            lot_size = risk_amount / (sl_distance * pip_value)
        else:
            lot_size = 0.0
        
        self.long_state.in_position = True
        self.long_state.entry_price = entry_price
        self.long_state.stop_loss = stop_loss
        self.long_state.take_profit = take_profit
        self.long_state.lot_size = lot_size
        self.long_state.entry_time = ts
        self.long_state.finding_entry_buy = False
        self.long_state.doi_sl_05R = True
    
    def _force_exit_long(self, idx: int, ts: pd.Timestamp, reason: str):
        """
        Force exit LONG position (không phải TP/SL).
        Dùng khi có conflict hoặc zone đối lập xuất hiện.
        """
        if not self.long_state.in_position:
            return
        
        exit_price = self.m1.iloc[idx]['close']
        self._complete_long_trade(ts, exit_price, f"FORCE: {reason}")
    
    def _force_exit_short(self, idx: int, ts: pd.Timestamp, reason: str):
        """
        Force exit SHORT position (không phải TP/SL).
        Dùng khi có conflict hoặc zone đối lập xuất hiện.
        """
        if not self.short_state.in_position:
            return
        
        exit_price = self.m1.iloc[idx]['close']
        self._complete_short_trade(ts, exit_price, f"FORCE: {reason}")
    
    def _manage_position(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Quản lý position hiện tại: TP/SL cho cả Long và Short.
        """
        # Quản lý Long position
        if self.long_state.in_position:
            self._manage_long_position(idx, ts, o, h, l, c)
        
        # Quản lý Short position
        if self.short_state.in_position:
            self._manage_short_position(idx, ts, o, h, l, c)
    
    def _manage_long_position(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Quản lý Long position: TP/SL, early exit, trailing stop.
        Mapping Pine line 1277-1320, 1303-1308.
        """
        entry_price = self.long_state.entry_price
        sl = self.long_state.stop_loss
        tp = self.long_state.take_profit
        
        # 1. Early Exit: Supply Zone xuất hiện gần entry hơn SL (Pine line 1277-1290)
        if len(self.short_state.arrayBoxSup) > 0:
            lastBoxBear = self.short_state.arrayBoxSup[-1]
            canhDuoiLastBoxBear = lastBoxBear.price_bottom
            
            # Nếu Supply gần entry hơn SL → Exit ngay
            if abs(canhDuoiLastBoxBear - entry_price) < abs(entry_price - sl):
                self._complete_long_trade(ts, c, "Supply Zone too close")
                return
        
        # 2. Early Exit: Sell Liquidity xuất hiện gần entry hơn SL (Pine line 1291-1301)
        if len(self.short_state.arraySellLiquidity) > 0:
            lineGiam_price = self.short_state.arraySellLiquidity[-1]
            
            if abs(lineGiam_price - entry_price) < abs(entry_price - sl):
                self._complete_long_trade(ts, c, "Sell Liquidity too close")
                return
        
        # 3. Move SL to trailing_sl_level * R khi profit đạt trailing_sl_trigger * R (Pine line 1303-1308)
        risk = entry_price - sl
        if (
            h > entry_price + risk * self.config.trailing_sl_trigger
            and self.long_state.doi_sl_05R
        ):
            new_sl = entry_price + risk * self.config.trailing_sl_level
            self.long_state.stop_loss = new_sl
            self.long_state.doi_sl_05R = False
            print(f"[{ts}] MOVE SL TO 0.5R: LONG @ entry={entry_price:.2f}, new_SL={new_sl:.2f}")
        
        # 4. Hit SL
        if l <= self.long_state.stop_loss:
            self._complete_long_trade(ts, self.long_state.stop_loss, "SL hit")
            return
        
        # 5. Hit TP
        if h >= self.long_state.take_profit:
            self._complete_long_trade(ts, tp, "TP hit")
            return
    
    def _manage_supply_zones(self, idx: int, o: float, h: float, l: float, c: float, ts: pd.Timestamp):
        """
        Quản lý Supply Zone: touch, xoá khi bị phá trần hoặc chạm > 1 lần.
        Mapping line 1620-1757 trong Pine (tương tự _manage_demand_zones nhưng ngược lại).
        """
        # Xoá zone nếu cham > 1 lần
        if len(self.short_state.arrayBoxSup) > 0:
            for i in range(len(self.short_state.arrayBoxSup) - 1, -1, -1):
                zone = self.short_state.arrayBoxSup[i]
                so_lan = self.short_state.arrayBoxSup_cham[i]
                
                if so_lan > 1:
                    print(f"[{ts}] Supply Zone REMOVED (touched > 1): {zone.price_bottom:.2f}-{zone.price_top:.2f}, touches={so_lan}")
                    self.short_state.arrayBoxSup.pop(i)
                    self.short_state.arrayBoxSup_cham.pop(i)
                    self.short_state.arrayBoxSup_status_touched.pop(i)
        
        # Touch Supply Zone (line 1620-1757)
        if len(self.short_state.arrayBoxSup) > 0 and not self.short_state.make_color_giam:
            for i in range(len(self.short_state.arrayBoxSup) - 1, -1, -1):
                zone = self.short_state.arrayBoxSup[i]
                so_lan = self.short_state.arrayBoxSup_cham[i]
                status_touched = self.short_state.arrayBoxSup_status_touched[i]
                
                canhDuoiLastBoxBear = zone.price_bottom
                canhTrenLastBoxBear = zone.price_top
                
                # Điều kiện touch (line 1629) - giá nằm trong supply hoặc close nằm trong
                if ((h < canhTrenLastBoxBear and h > canhDuoiLastBoxBear) 
                    or (c < canhTrenLastBoxBear and c > canhDuoiLastBoxBear)):
                    
                    if so_lan == 1 and status_touched == 0:
                        # Touch LẦN 2 (line 1632)
                        # ⭐ Xoá BUY BASE + Đóng LONG
                        if len(self.long_state.arrayBoxBuyBase) > 0:
                            self.long_state.arrayBoxBuyBase.clear()
                            self.long_state.mang_so_lan_cham_buy_base.clear()
                            self.long_state.finding_entry_buy = False
                            self.long_state.finding_entry_buy_ten_minutes = 0
                            self.long_state.finding_entry_buy_time_out = 0
                            self.long_state.demand_finding_buy_base = False
                            self.long_state.liquid_finding_buy_base = False
                            
                            # Đóng lệnh LONG nếu có
                            if self.long_state.in_position:
                                self._force_exit_long(idx, ts, "Supply zone touched")
                            
                            print(f"[{ts}] ⚠️  CANCEL BUY FLOW (Supply zone touched)")
                        
                        # Xoá Sell Base cũ nếu có
                        if len(self.short_state.arrayBoxSellBase) > 0:
                            self.short_state.arrayBoxSellBase.pop()
                            self.short_state.mang_so_lan_cham_sell_base.pop()
                            self.short_state.finding_entry_sell = False
                            self.short_state.finding_entry_sell_ten_minutes = 0
                            self.short_state.finding_entry_sell_time_out = 0
                        
                        if idx >= 2:
                            self.short_state.removeCandle_OpenPrice_Sell = self.m1.iloc[idx - 2]['open']
                        
                        self.short_state.liquid_finding_sell_base = False
                        self.short_state.supply_finding_sell_base = True
                        self.long_state.demand_finding_buy_base = False
                        self.long_state.liquid_finding_buy_base = False
                        so_lan += 1
                        self.short_state.arrayBoxSup_cham[i] = so_lan
                        self.short_state.arrayBoxSup_status_touched[i] = 1
                        self.short_state.finding_entry_sell_time_out = 0
                        
                        print(f"[{ts}] Supply Zone TOUCHED (2nd time) @ {canhDuoiLastBoxBear:.2f}-{canhTrenLastBoxBear:.2f}! Now searching for Sell Base...")
                    
                    elif so_lan == 0 and not self.short_state.make_color_giam:
                        # Touch LẦN ĐẦU (line 1702)
                        # ⭐ Xoá BUY BASE + Đóng LONG
                        if len(self.long_state.arrayBoxBuyBase) > 0:
                            self.long_state.arrayBoxBuyBase.clear()
                            self.long_state.mang_so_lan_cham_buy_base.clear()
                            self.long_state.finding_entry_buy = False
                            self.long_state.finding_entry_buy_ten_minutes = 0
                            self.long_state.finding_entry_buy_time_out = 0
                            self.long_state.demand_finding_buy_base = False
                            self.long_state.liquid_finding_buy_base = False
                            
                            # Đóng lệnh LONG nếu có
                            if self.long_state.in_position:
                                self._force_exit_long(idx, ts, "Supply zone touched (1st)")
                            
                            print(f"[{ts}] ⚠️  CANCEL BUY FLOW (Supply zone touched 1st)")
                        
                        # Xoá Sell Base cũ nếu có
                        if len(self.short_state.arrayBoxSellBase) > 0:
                            self.short_state.arrayBoxSellBase.pop()
                            self.short_state.mang_so_lan_cham_sell_base.pop()
                            self.short_state.finding_entry_sell = False
                            self.short_state.finding_entry_sell_ten_minutes = 0
                            self.short_state.finding_entry_sell_time_out = 0
                        
                        if idx >= 2:
                            self.short_state.removeCandle_OpenPrice_Sell = self.m1.iloc[idx - 2]['open']
                        
                        so_lan += 1
                        self.short_state.liquid_finding_sell_base = False
                        self.short_state.supply_finding_sell_base = True
                        self.short_state.finding_entry_sell_time_out = 0
                        
                        self.short_state.arrayBoxSup_cham[i] = so_lan
                        self.short_state.arrayBoxSup_status_touched[i] = 1
                        
                        print(f"[{ts}] Supply Zone TOUCHED (1st time) @ {canhDuoiLastBoxBear:.2f}-{canhTrenLastBoxBear:.2f}! Now searching for Sell Base...")
    
    def _manage_short_position(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Quản lý Short position: TP/SL, early exit, trailing stop.
        Mapping Pine line 2229-2271, 2255-2260.
        """
        entry_price = self.short_state.entry_price
        sl = self.short_state.stop_loss
        tp = self.short_state.take_profit
        
        # 1. Early Exit: Demand Zone xuất hiện gần entry hơn SL (Pine line 2231-2242)
        if len(self.long_state.arrayBoxDem) > 0:
            lastBoxBull = self.long_state.arrayBoxDem[-1]
            canhTrenLastBoxBull = lastBoxBull.price_top
            
            # Nếu Demand gần entry hơn SL → Exit ngay
            if abs(canhTrenLastBoxBull - entry_price) < abs(entry_price - sl):
                self._complete_short_trade(ts, c, "Demand Zone too close")
                return
        
        # 2. Early Exit: Buy Liquidity xuất hiện gần entry hơn SL (Pine line 2243-2253)
        if len(self.long_state.arrayBuyLiquidity) > 0:
            lineTang_price = self.long_state.arrayBuyLiquidity[-1]
            
            if abs(lineTang_price - entry_price) < abs(entry_price - sl):
                self._complete_short_trade(ts, c, "Buy Liquidity too close")
                return
        
        # 3. Move SL to trailing_sl_level * R khi profit đạt trailing_sl_trigger * R (Pine line 2255-2260)
        risk = sl - entry_price
        if (
            l < entry_price - risk * self.config.trailing_sl_trigger
            and self.short_state.doi_sl_05R_sell
        ):
            new_sl = entry_price - risk * self.config.trailing_sl_level
            self.short_state.stop_loss = new_sl
            self.short_state.doi_sl_05R_sell = False
            print(f"[{ts}] MOVE SL TO 0.5R: SHORT @ entry={entry_price:.2f}, new_SL={new_sl:.2f}")
        
        # 4. Hit SL (Short: giá chạm SL khi HIGH >= SL)
        if h >= self.short_state.stop_loss:
            self._complete_short_trade(ts, self.short_state.stop_loss, "SL hit")
            return
        
        # 5. Hit TP (Short: giá chạm TP khi LOW <= TP)
        if l <= self.short_state.take_profit:
            self._complete_short_trade(ts, tp, "TP hit")
            return
    
    def _check_sell_liquidity_crossed(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Kiểm tra Sell Liquidity bị crossed (line 1430-1527).
        Tương tự _check_buy_liquidity_crossed nhưng ngược lại.
        """
        if len(self.short_state.arraySellLiquidity) == 0:
            return
        
        for i in range(len(self.short_state.arraySellLiquidity) - 1, -1, -1):
            SellLiquidity = self.short_state.arraySellLiquidity[i]
            
            if h > SellLiquidity:
                # ⭐ Xoá BUY BASE + Đóng LONG khi cross Sell Liquidity (Pine line 1466-1478)
                if len(self.long_state.arrayBoxBuyBase) > 0:
                    self.long_state.arrayBoxBuyBase.clear()
                    self.long_state.mang_so_lan_cham_buy_base.clear()
                    self.long_state.finding_entry_buy = False
                    self.long_state.finding_entry_buy_ten_minutes = 0
                    self.long_state.finding_entry_buy_time_out = 0
                    self.long_state.demand_finding_buy_base = False
                    self.long_state.liquid_finding_buy_base = False
                    
                    # Đóng lệnh LONG nếu có
                    if self.long_state.in_position:
                        self._force_exit_long(idx, ts, "Sell Liquidity crossed")
                    
                    print(f"[{ts}] ⚠️  CANCEL BUY FLOW (Sell Liquidity crossed)")
                
                # Xoá Supply Zone nếu cần (line 1437-1448)
                if len(self.short_state.arrayBoxSup) > 0:
                    lastBoxBear = self.short_state.arrayBoxSup[-1]
                    canhTrenLastBoxBear = lastBoxBear.price_top
                    if h > canhTrenLastBoxBear:
                        self.short_state.arrayBoxSup.pop()
                        self.short_state.arrayBoxSup_cham.pop()
                        self.short_state.arrayBoxSup_status_touched.pop()
                
                # Xoá Sell Base cũ nếu có
                if len(self.short_state.arrayBoxSellBase) > 0:
                    self.short_state.arrayBoxSellBase.pop()
                    self.short_state.mang_so_lan_cham_sell_base.pop()
                    self.short_state.finding_entry_sell = False
                    self.short_state.finding_entry_sell_time_out = 0
                    self.short_state.finding_entry_sell_ten_minutes = 0
                
                # Xoá liquidity và set state
                self.short_state.arraySellLiquidity.pop(i)
                self.short_state.removePriceSupply = SellLiquidity
                self.short_state.removeCandle_OpenPrice_Sell = o
                self.short_state.liquid_finding_sell_base = True
                self.short_state.supply_finding_sell_base = False
                self.short_state.do_sell_base_2_lan = 0
                
                print(f"[{ts}] Sell Liquidity CROSSED @ {SellLiquidity:.2f}! Now searching for Sell Base...")
                
                break
        
        # Thoát nếu giá quá xa liquidity (line 1511-1527)
        if h > self.short_state.removePriceSupply + 5:
            self.short_state.liquid_finding_sell_base = False
            self.short_state.supply_finding_sell_base = False
            self.short_state.removePriceSupply = 10000.0
            self.short_state.finding_entry_sell = False
            self.short_state.finding_entry_sell_ten_minutes = 0
            self.short_state.finding_entry_sell_time_out = 0
            self.short_state.do_sell_base_2_lan = 0
            if len(self.short_state.arrayBoxSellBase) > 0:
                self.short_state.arrayBoxSellBase.pop()
                self.short_state.mang_so_lan_cham_sell_base.pop()
    
    def _create_sell_base_from_liquidity(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Tạo Sell Base từ Liquidity (tương tự _create_buy_base_from_liquidity nhưng ngược lại).
        """
        if not self.short_state.liquid_finding_sell_base or len(self.short_state.arrayLowGiaNenTang) == 0:
            return
        
        low_tang = self.short_state.arrayLowGiaNenTang[-1]
        
        if l < low_tang or self.short_state.keep_finding_liquid_sell:
            if not self.short_state.keep_finding_liquid_sell:
                self.short_state.index_of_low_nearest = 1
                for j in range(1, min(idx, 20)):
                    if self.m1.iloc[idx - j]['low'] == low_tang:
                        self.short_state.index_of_low_nearest = j
                        break
            
            self.short_state.hai_phut_hon_liquid_sell += 1
            self.short_state.keep_finding_liquid_sell = True
            
            if self.short_state.hai_phut_hon_liquid_sell > 2:
                self.short_state.hai_phut_hon_liquid_sell = 0
                self.short_state.keep_finding_liquid_sell = False
                
                while len(self.short_state.arrayLowGiaNenTang) > 0:
                    if l < self.short_state.arrayLowGiaNenTang[-1]:
                        self.short_state.arrayLowGiaNenTang.pop()
                    else:
                        break
                
                sell_base = self._find_sell_base_in_window(idx, is_from_liquidity=True)
                if sell_base is not None:
                    self.short_state.arrayBoxSellBase.append(sell_base)
                    self.short_state.mang_so_lan_cham_sell_base.append(0)
                    self.short_state.liquid_finding_sell_base = False
                    self.short_state.making_sell_base = True
                    self.short_state.finding_entry_sell_time_out = self.short_state.index_of_low_nearest + 2
                    self.short_state.do_sell_base_2_lan += 1
    
    def _create_sell_base_from_supply(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Tạo Sell Base từ Supply (tương tự _create_buy_base_from_demand nhưng ngược lại).
        """
        if not self.short_state.supply_finding_sell_base or len(self.short_state.arrayLowGiaNenTang) == 0:
            return
        
        low_tang = self.short_state.arrayLowGiaNenTang[-1]
        
        if l < low_tang or self.short_state.keep_finding_supply:
            if not self.short_state.keep_finding_supply:
                self.short_state.index_of_low_nearest = 1
                for j in range(1, min(idx, 20)):
                    if self.m1.iloc[idx - j]['low'] == low_tang:
                        self.short_state.index_of_low_nearest = j
                        break
            
            self.short_state.keep_finding_supply = True
            self.short_state.hai_phut_hon_supply += 1
            
            if self.short_state.hai_phut_hon_supply > 2:
                self.short_state.arrayLowGiaNenTang.pop()
                self.short_state.hai_phut_hon_supply = 0
                self.short_state.keep_finding_supply = False
                
                while len(self.short_state.arrayLowGiaNenTang) > 0:
                    if l < self.short_state.arrayLowGiaNenTang[-1]:
                        self.short_state.arrayLowGiaNenTang.pop()
                    else:
                        break
                
                sell_base = self._find_sell_base_in_window(idx, is_from_liquidity=False)
                if sell_base is not None:
                    self.short_state.arrayBoxSellBase.append(sell_base)
                    self.short_state.mang_so_lan_cham_sell_base.append(0)
                    self.short_state.supply_finding_sell_base = False
                    self.short_state.making_sell_base = True
                    self.short_state.finding_entry_sell_time_out = self.short_state.index_of_low_nearest + 2
                    self.short_state.do_sell_base_2_lan += 1
    
    def _find_sell_base_in_window(self, idx: int, is_from_liquidity: bool) -> Optional[BuySellBase]:
        """
        Tìm Sell Base trong window 0-5 nến trước đó (ngược lại với Buy Base).
        Pattern nến đảo ngược: thay vì nến xanh mạnh + nến nhỏ, giờ là nến đỏ mạnh + nến nhỏ.
        """
        for j in range(6):
            if idx < j + 3:
                continue
            
            if self.m1.iloc[idx - j]['open'] == self.short_state.removeCandle_OpenPrice_Sell:
                break
            
            idx_j = idx - j
            idx_j1 = idx - j - 1
            idx_j2 = idx - j - 2
            
            if idx_j1 < 0 or idx_j2 < 0:
                continue
            
            r_j = self.m1.iloc[idx_j]
            r_j1 = self.m1.iloc[idx_j1]
            r_j2 = self.m1.iloc[idx_j2]
            
            o_j, h_j, l_j, c_j = r_j['open'], r_j['high'], r_j['low'], r_j['close']
            o_j1, h_j1, l_j1, c_j1 = r_j1['open'], r_j1['high'], r_j1['low'], r_j1['close']
            o_j2, h_j2, l_j2, c_j2 = r_j2['open'], r_j2['high'], r_j2['low'], r_j2['close']
            
            # Pattern nến đỏ mạnh (ngược lại với Buy Base)
            cond1 = (
                o_j1 > c_j1
                and (c_j1 - l_j1) < (o_j1 - c_j1) + 0.1
                and (h_j - o_j) < 0.33 * (h_j1 - l_j1)
            )
            cond2 = (
                c_j1 > o_j1
                and (h_j1 - c_j1) > (c_j1 - o_j1)
                and (c_j1 - l_j1) < (c_j1 - o_j1) + 0.1
                and (h_j - o_j) <= 0.33 * (h_j1 - l_j1)
            )
            
            cond_neg1 = (
                o_j2 > c_j2
                and (c_j2 - l_j2) < (o_j2 - c_j2) + 0.1
                and (h_j1 - o_j1) < 0.33 * (h_j2 - l_j2)
            )
            cond_neg2 = (
                c_j2 > o_j2
                and (h_j2 - c_j2) > (c_j2 - o_j2)
                and (c_j2 - l_j2) < (c_j2 - o_j2) + 0.1
                and (h_j1 - o_j1) <= 0.33 * (h_j2 - l_j2)
            )
            
            if (cond1 or cond2) and not (cond_neg1 or cond_neg2):
                # Tính x (top của Sell Base), y (bottom)
                if h_j1 > h_j2:
                    x = h_j1
                    k = j + 2
                else:
                    x = h_j2
                    k = j + 2
                
                y = 10000.0
                
                # Logic tương tự Buy Base nhưng ngược lại
                if k >= 2 and idx - k + 2 >= 0:
                    idx_k_minus_2 = idx - k + 2
                    idx_k = idx - k
                    idx_k_minus_1 = idx - k + 1
                    
                    if idx_k >= 0 and idx_k_minus_1 >= 0:
                        r_k = self.m1.iloc[idx_k]
                        r_k_minus_1 = self.m1.iloc[idx_k_minus_1]
                        r_k_minus_2 = self.m1.iloc[idx_k_minus_2]
                        
                        if (r_k['low'] - r_k_minus_2['high']) > 0.05 and r_k_minus_1['open'] > r_k_minus_1['close']:
                            y = r_k_minus_2['high']
                
                if k >= 3 and idx - k + 3 >= 0:
                    idx_k_minus_3 = idx - k + 3
                    idx_k_minus_1 = idx - k + 1
                    idx_k_minus_2 = idx - k + 2
                    
                    if idx_k_minus_1 >= 0 and idx_k_minus_2 >= 0 and idx_k_minus_3 >= 0:
                        r_k_minus_1 = self.m1.iloc[idx_k_minus_1]
                        r_k_minus_2 = self.m1.iloc[idx_k_minus_2]
                        r_k_minus_3 = self.m1.iloc[idx_k_minus_3]
                        
                        if (r_k_minus_1['low'] - r_k_minus_3['high']) > 0.05 and r_k_minus_2['open'] > r_k_minus_2['close']:
                            y = r_k_minus_3['high']
                
                if k >= 4 and idx - k + 4 >= 0:
                    idx_k_minus_4 = idx - k + 4
                    idx_k_minus_3 = idx - k + 3
                    idx_k_minus_2 = idx - k + 2
                    
                    if idx_k_minus_2 >= 0 and idx_k_minus_3 >= 0 and idx_k_minus_4 >= 0:
                        r_k_minus_2 = self.m1.iloc[idx_k_minus_2]
                        r_k_minus_3 = self.m1.iloc[idx_k_minus_3]
                        r_k_minus_4 = self.m1.iloc[idx_k_minus_4]
                        
                        if y == r_k_minus_3['high'] and (r_k_minus_2['low'] - r_k_minus_4['high']) > 0.05 and r_k_minus_3['open'] > r_k_minus_3['close']:
                            y = r_k_minus_4['high']
                
                if x > 0 and y < 10000 and x > y:
                    return BuySellBase(
                        price_top=x,
                        price_bottom=y,
                        direction=TradeDirection.SELL,
                    )
        
        return None
    
    def _manage_sell_base_timeout(self, idx: int, ts: pd.Timestamp, h: float, l: float):
        """
        Timeout cho Sell Base (tương tự _manage_buy_base_timeout).
        """
        if self.short_state.finding_entry_sell_time_out > 0:
            self.short_state.finding_entry_sell_time_out += 1
        
        # Timeout 60 phút khi finding_entry_sell == True
        if (self.short_state.finding_entry_sell_time_out > 60
            and len(self.short_state.arrayBoxSellBase) > 0
            and self.short_state.finding_entry_sell):
            
            self.short_state.arrayBoxSellBase.clear()
            self.short_state.mang_so_lan_cham_sell_base.clear()
            self.short_state.finding_entry_sell_ten_minutes = 0
            self.short_state.finding_entry_sell = False
            self.short_state.finding_entry_sell_time_out = 0
            self.short_state.supply_finding_sell_base = False
            self.short_state.liquid_finding_sell_base = False
        
        # Timeout 80 phút khi finding_entry_sell == False
        if (self.short_state.finding_entry_sell_time_out > 80
            and not self.short_state.finding_entry_sell):
            
            if len(self.short_state.arrayBoxSellBase) > 0:
                self.short_state.arrayBoxSellBase.pop()
                self.short_state.mang_so_lan_cham_sell_base.pop()
            
            self.short_state.finding_entry_sell_ten_minutes = 0
            self.short_state.finding_entry_sell = False
            self.short_state.supply_finding_sell_base = False
            self.short_state.liquid_finding_sell_base = False
            self.short_state.finding_entry_sell_time_out = 0
    
    def _check_sell_base_touched(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Kiểm tra Sell Base bị chạm → set finding_entry_sell.
        Tương tự _check_buy_base_touched nhưng ngược lại.
        """
        if len(self.short_state.arrayBoxSellBase) == 0:
            return
        
        lastBoxBear = self.short_state.arrayBoxSellBase[-1]
        canhTrenLastBoxBear = lastBoxBear.price_top
        canhDuoiLastBoxBear = lastBoxBear.price_bottom
        so_lan_cham_sell_base = self.short_state.mang_so_lan_cham_sell_base[-1]
        
        # Touch
        if (
            ((c < canhTrenLastBoxBear and c > canhDuoiLastBoxBear)
             or (h < canhTrenLastBoxBear and h > canhDuoiLastBoxBear))
            and not self.short_state.finding_entry_sell
            and not self.short_state.making_sell_base
            and so_lan_cham_sell_base == 0
        ):
            so_lan_cham_sell_base += 1
            self.short_state.mang_so_lan_cham_sell_base[-1] = so_lan_cham_sell_base
            self.short_state.finding_entry_sell = True
        
        # Phá trần Sell Base → ten_minutes
        if h > canhTrenLastBoxBear + 0.5 and self.short_state.finding_entry_sell_ten_minutes == 0:
            self.short_state.finding_entry_sell_ten_minutes += 1
    
    def _check_sell_base_invalidation(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Kiểm tra Sell Base bị phá hoặc chạm cản (Pine line 2274-2323).
        Đóng lệnh nếu đang trong position.
        """
        if len(self.short_state.arrayBoxSellBase) == 0:
            return
        
        lastBoxBear = self.short_state.arrayBoxSellBase[-1]
        canhTrenLastBoxBear = lastBoxBear.price_top
        canhDuoiLastBoxBear = lastBoxBear.price_bottom
        
        # Increment ten_minutes counter (Pine line 2299-2300)
        if self.short_state.finding_entry_sell_ten_minutes > 0:
            self.short_state.finding_entry_sell_ten_minutes += 1
        
        # Case 1: Sau 10 phút, giá phá trần base + 0.5 (Pine line 2274-2294)
        if self.short_state.finding_entry_sell_ten_minutes > 10:
            if h > canhTrenLastBoxBear + 0.5:
                # Xóa Sell Base
                self.short_state.arrayBoxSellBase.pop()
                self.short_state.mang_so_lan_cham_sell_base.pop()
                self.short_state.finding_entry_sell = False
                self.short_state.finding_entry_sell_time_out = 0
                self.short_state.finding_entry_sell_ten_minutes = 0
                
                # Đóng lệnh nếu đang trong position
                if self.short_state.in_position:
                    self._complete_short_trade(ts, c, "Sell Base broken after 10min")
                
                # Xử lý liquidity finding (line 2290-2294)
                if self.short_state.do_sell_base_2_lan == 1:
                    self.short_state.do_sell_base_2_lan += 1
                    self.short_state.liquid_finding_sell_base = True
                    self.short_state.supply_finding_sell_base = False
                
                print(f"[{ts}] Sell Base REMOVED (broken after 10min)")
                return
        
        # Case 2: Giá chạm "cản" (1 khoảng base từ trần) (Pine line 2302-2323)
        base_height = canhTrenLastBoxBear - canhDuoiLastBoxBear
        if h >= canhTrenLastBoxBear + base_height:
            # Xóa Sell Base
            self.short_state.arrayBoxSellBase.pop()
            self.short_state.mang_so_lan_cham_sell_base.pop()
            self.short_state.finding_entry_sell = False
            self.short_state.finding_entry_sell_time_out = 0
            self.short_state.finding_entry_sell_ten_minutes = 0
            
            # Đóng lệnh nếu đang trong position
            if self.short_state.in_position:
                self._complete_short_trade(ts, c, "Sell Base resistance hit")
            
            # Xử lý liquidity finding (line 2319-2322)
            if self.short_state.do_sell_base_2_lan == 1:
                self.short_state.do_sell_base_2_lan += 1
                self.short_state.liquid_finding_sell_base = True
            
            print(f"[{ts}] Sell Base REMOVED (resistance hit)")
            return
    
    def _entry_short(self, idx: int, ts: pd.Timestamp, o: float, h: float, l: float, c: float):
        """
        Entry Short (tương tự _entry_long nhưng ngược lại).
        """
        if not self.short_state.finding_entry_sell:
            return
        
        if not self._is_within_timerange(ts):
            return
        
        if len(self.short_state.arrayBoxSellBase) == 0:
            return
        
        lastBoxBear = self.short_state.arrayBoxSellBase[-1]
        canhTrenLastBoxBear = lastBoxBear.price_top
        canhDuoiLastBoxBear = lastBoxBear.price_bottom
        
        # Nếu finding_entry_sell_ten_minutes > 0 (line 2069)
        if self.short_state.finding_entry_sell_ten_minutes > 0:
            if idx < 3:
                return
            
            prev1 = self.m1.iloc[idx - 1]
            prev2 = self.m1.iloc[idx - 2]
            prev3 = self.m1.iloc[idx - 3]
            
            o1, c1 = prev1['open'], prev1['close']
            o2, c2 = prev2['open'], prev2['close']
            h1, h2, h3 = prev1['high'], prev2['high'], prev3['high']
            
            # Pine: max(high, high[1], high[3]) > canhDuoiLastBoxBear
            if not (o > c and max(h, h1, h3) > canhDuoiLastBoxBear):
                return
            
            # Tính sl_sell = ta.highest(10) (line 296)
            sl_sell = max(self.m1.iloc[max(0, idx-9):idx+1]['high'])
            
            # Case 1: open[2] < close[2] (line 2071)
            if o2 < c2:
                if (
                    (c <= o2)
                    and (c - l) < (o - c)
                    and self.ADX < self.config.adx_max_entry
                    and self.short_state.finding_entry_sell_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_short_with_sl_sell(idx, ts, c, sl_sell)
            # Case 2: open[1] < close[1] and open[2] > close[2] (line 2110)
            elif o1 < c1 and o2 > c2:
                if (
                    (c <= c2)
                    and (c - l) < (o - c)
                    and self.ADX < self.config.adx_max_entry
                    and self.short_state.finding_entry_sell_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_short_with_sl_sell(idx, ts, c, sl_sell)
        
        # Nếu finding_entry_sell_ten_minutes <= 0 (line 2149 - else branch)
        else:
            if idx < 3:
                return
            
            prev1 = self.m1.iloc[idx - 1]
            prev2 = self.m1.iloc[idx - 2]
            prev3 = self.m1.iloc[idx - 3]
            
            o1, c1 = prev1['open'], prev1['close']
            o2, c2 = prev2['open'], prev2['close']
            h1, h2, h3 = prev1['high'], prev2['high'], prev3['high']
            
            # Pine: max(high, high[1], high[3]) > canhDuoiLastBoxBear (line 2150)
            if not (o > c and max(h, h1, h3) > canhDuoiLastBoxBear):
                return
            
            # Case 1: open[2] < close[2] (line 2151)
            if o2 < c2:
                if (
                    (c <= o2)
                    and (c - l) < (o - c)
                    and self.ADX < self.config.adx_max_entry
                    and self.short_state.finding_entry_sell_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_short(idx, ts, c, canhTrenLastBoxBear)
            # Case 2: open[1] < close[1] and open[2] > close[2] (line 2190)
            elif o1 < c1 and o2 > c2:
                if (
                    (c <= c2)
                    and (c - l) < (o - c)
                    and self.ADX < self.config.adx_max_entry
                    and self.short_state.finding_entry_sell_time_out <= self.config.max_entry_timeout_minutes
                ):
                    self._execute_entry_short(idx, ts, c, canhTrenLastBoxBear)
    
    def _execute_entry_short(self, idx: int, ts: pd.Timestamp, entry_price: float, base_top: float):
        """
        Thực hiện entry Short với SL = base_top + 0.5.
        Chỉ entry nếu TP hợp lệ (Pine line 2161-2163).
        """
        # ⭐ CHECK CONFLICT: Nếu đang có LONG → Đóng LONG trước
        if self.long_state.in_position:
            self._force_exit_long(idx, ts, "Conflict: Opening SHORT")
        
        buyLiquidity_entry = 0.0
        canhTrenLastBoxBull_entry = 0.0
        
        if len(self.long_state.arrayBoxDem) > 0:
            canhTrenLastBoxBull_entry = self.long_state.arrayBoxDem[-1].price_top
        
        if len(self.long_state.arrayBuyLiquidity) > 0:
            buyLiquidity_entry = self.long_state.arrayBuyLiquidity[-1]
        
        closest_tp_sell = max(canhTrenLastBoxBull_entry, buyLiquidity_entry)

        buffer = self.config.zone_touch_buffer
        one_r = (base_top + buffer) - entry_price
        
        # Pine line 2161: if close - (canhTrenLastBoxBearBase + 0.5 - close) > closest_tp_sell
        # CHỈ entry nếu điều kiện này đúng
        if entry_price - one_r > closest_tp_sell:
            # Pine line 2162: dùng r_r_ratio_target để scale R
            tp_2R = entry_price - self.config.r_r_ratio_target * one_r
            closest_tp_sell = max(tp_2R, closest_tp_sell)
        else:
            # Không entry nếu TP không hợp lý (TP nằm phía trên entry)
            return
        
        stop_loss = base_top + buffer
        take_profit = closest_tp_sell
        
        # Tính lot size
        risk_per_trade = self.config.risk_per_trade
        capital = self.current_equity
        risk_amount = (risk_per_trade / 100) * capital
        pip_value = 0.1
        sl_distance = abs(entry_price - stop_loss)
        
        if sl_distance > 0:
            lot_size = risk_amount / (sl_distance * pip_value)
        else:
            lot_size = 0.0
        
        self.short_state.in_position = True
        self.short_state.entry_price = entry_price
        self.short_state.stop_loss = stop_loss
        self.short_state.take_profit = take_profit
        self.short_state.lot_size = lot_size
        self.short_state.entry_time = ts
        self.short_state.finding_entry_sell = False
        self.short_state.doi_sl_05R_sell = True
    
    def _execute_entry_short_with_sl_sell(self, idx: int, ts: pd.Timestamp, entry_price: float, sl_sell: float):
        """
        Thực hiện entry Short với SL = sl_sell + 0.5.
        Chỉ entry nếu TP hợp lệ (Pine line 2081-2083).
        """
        # ⭐ CHECK CONFLICT: Nếu đang có LONG → Đóng LONG trước
        if self.long_state.in_position:
            self._force_exit_long(idx, ts, "Conflict: Opening SHORT (with sl_sell)")
        
        buyLiquidity_entry = 0.0
        canhTrenLastBoxBull_entry = 0.0
        
        if len(self.long_state.arrayBoxDem) > 0:
            canhTrenLastBoxBull_entry = self.long_state.arrayBoxDem[-1].price_top
        
        if len(self.long_state.arrayBuyLiquidity) > 0:
            buyLiquidity_entry = self.long_state.arrayBuyLiquidity[-1]
        
        closest_tp_sell = max(canhTrenLastBoxBull_entry, buyLiquidity_entry)

        buffer = self.config.zone_touch_buffer
        one_r = (sl_sell + buffer) - entry_price
        
        # Pine line 2081: if close - (sl_sell + 0.5 - close) > closest_tp_sell
        # CHỈ entry nếu điều kiện này đúng
        if entry_price - one_r > closest_tp_sell:
            # Pine line 2082
            tp_2R = entry_price - self.config.r_r_ratio_target * one_r
            closest_tp_sell = max(tp_2R, closest_tp_sell)
        else:
            # Không entry nếu TP không hợp lý
            return
        
        stop_loss = sl_sell + buffer
        take_profit = closest_tp_sell
        
        risk_per_trade = self.config.risk_per_trade
        capital = self.current_equity
        risk_amount = (risk_per_trade / 100) * capital
        pip_value = 0.1
        sl_distance = abs(entry_price - stop_loss)
        
        if sl_distance > 0:
            lot_size = risk_amount / (sl_distance * pip_value)
        else:
            lot_size = 0.0
        
        self.short_state.in_position = True
        self.short_state.entry_price = entry_price
        self.short_state.stop_loss = stop_loss
        self.short_state.take_profit = take_profit
        self.short_state.lot_size = lot_size
        self.short_state.entry_time = ts
        self.short_state.finding_entry_sell = False
        self.short_state.doi_sl_05R_sell = True

    def _print_statistics(self):
        """Tinh toan va in thong ke backtest."""
        if len(self.trades) == 0:
            print("\n=== THONG KE (STATISTICS) ===")
            print("Khong co giao dich nao duoc thuc hien.")
            return
        
        # Tinh toan cac chi so
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        breakeven_trades = [t for t in self.trades if t.pnl == 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        breakeven_count = len(breakeven_trades)
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # Tong lai/lo
        total_pnl = sum(t.pnl for t in self.trades)
        total_profit = sum(t.pnl for t in winning_trades)
        total_loss = sum(t.pnl for t in losing_trades)
        
        # Profit factor
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
        
        # Average trade
        avg_win = (total_profit / win_count) if win_count > 0 else 0
        avg_loss = (total_loss / loss_count) if loss_count > 0 else 0
        avg_trade = total_pnl / total_trades
        
        # Max drawdown
        max_dd = 0
        max_dd_pct = 0
        peak = self.initial_capital
        
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = (dd / peak * 100) if peak > 0 else 0
        
        # Return
        total_return = ((self.current_equity - self.initial_capital) / self.initial_capital * 100)
        
        # In ket qua
        print("\n" + "="*60)
        print("=== BACKTEST STATISTICS ===")
        print("="*60)
        
        print(f"\n[OVERVIEW]")
        print(f"  Initial Capital:          {self.initial_capital:,.0f} USD")
        print(f"  Final Equity:             {self.current_equity:,.0f} USD")
        print(f"  Total P/L:                {total_pnl:+,.0f} USD ({total_return:+.2f}%)")
        
        print(f"\n[TRADES]")
        print(f"  Total Trades:             {total_trades}")
        print(f"  - Winning Trades:         {win_count}")
        print(f"  - Losing Trades:          {loss_count}")
        print(f"  - Breakeven Trades:       {breakeven_count}")
        print(f"  Win Rate:                 {win_rate:.2f}%")
        
        print(f"\n[PROFIT/LOSS]")
        print(f"  Total Profit:             {total_profit:+,.0f} USD")
        print(f"  Total Loss:               {total_loss:+,.0f} USD")
        print(f"  Profit Factor:            {profit_factor:.2f}")
        print(f"  Average Trade:            {avg_trade:+,.0f} USD")
        print(f"  - Avg Winning Trade:      {avg_win:+,.0f} USD")
        print(f"  - Avg Losing Trade:       {avg_loss:+,.0f} USD")
        
        print(f"\n[RISK METRICS]")
        print(f"  Max Drawdown:             {max_dd:,.0f} USD ({max_dd_pct:.2f}%)")
        print(f"  Peak Equity:              {self.peak_equity:,.0f} USD")
        
        # Largest win/loss
        if winning_trades:
            largest_win = max(t.pnl for t in winning_trades)
            print(f"  Largest Win:              {largest_win:+,.0f} USD")
        
        if losing_trades:
            largest_loss = min(t.pnl for t in losing_trades)
            print(f"  Largest Loss:             {largest_loss:+,.0f} USD")
        
        print("\n" + "="*60)
