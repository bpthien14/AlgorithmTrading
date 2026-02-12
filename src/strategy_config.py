from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class StrategyConfig:
    """
    Config cho toàn bộ strategy – tập trung tất cả tham số có thể tối ưu.
    Các default được chọn để khớp với bản PineScript hiện tại.
    """

    # R:R / TP logic
    r_r_ratio_min: float = 2.0          # R:R tối thiểu để chấp nhận entry (hiện tại Pine dùng 1R bắt buộc hợp lệ)
    r_r_ratio_target: float = 3.0       # R:R target khi adjust TP (Pine đang dùng 2R)

    # Trailing SL (dời SL về 1.0R khi đạt 1.5R)
    trailing_sl_trigger: float = 1.5    # Khi lãi đạt bao nhiêu R thì kích hoạt trailing
    trailing_sl_level: float = 1.0      # Dời SL về mức bao nhiêu R (was 0.5R, improved to 1.0R)

    # ADX filter
    adx_max_entry: float = 25.0         # Điều kiện ADX < adx_max_entry
    adx_period: int = 14                # Period tính ADX (Pine mặc định 14)

    # Position sizing (no longer used with risk management removed)
    risk_per_trade: float = 4.0

    # Entry timeout (phút)
    max_entry_timeout_minutes: int = 60  # finding_entry_*_time_out <= 60

    # Zone / liquidity buffer
    zone_touch_buffer: float = 0.5      # Sử dụng cho các điều kiện +0.5 / -0.5 quanh cạnh box

    # Time range filter (theo Pine: nhiều khoảng trong ngày, UTC+7)
    enable_timerange_filter: bool = True
    trading_sessions: List[Tuple[int, int]] = field(
        default_factory=lambda: [
            (7 * 60, 8 * 60),           # 07:00-08:00
            (8 * 60 + 30, 9 * 60 + 30), # 08:30-09:30
            (12 * 60 + 30, 13 * 60 + 30),  # 12:30-13:30
            (14 * 60, 14 * 60 + 30),    # 14:00-14:30
            (17 * 60, 18 * 60),         # 17:00-18:00
            (20 * 60, 20 * 60 + 30),    # 20:00-20:30
        ]
    )

    # Exit features toggles (match current Pine behaviour – mọi thứ đều bật)
    enable_early_exit_opposing_zone: bool = True
    enable_base_breakdown_exit: bool = True
    enable_base_resistance_exit: bool = True

    # =========================================================================
    # Paper Trade Mode (Circuit Breaker) - see research.md Section 5
    # =========================================================================
    enable_paper_mode: bool = True                      # Bật/tắt Paper Mode
    paper_trigger_consecutive_losses: int = 3           # Số lệnh lỗ liên tiếp để trigger
    paper_trigger_win_rate_window: int = 10             # Window size để tính win rate
    paper_trigger_win_rate_threshold: float = 0.20      # Win rate threshold (20%)
    paper_recovery_min_wins: int = 2                    # Số lệnh thắng liên tiếp để recover
    paper_recovery_require_positive_pnl: bool = True    # Yêu cầu Paper PnL > 0
    paper_max_duration_minutes: int = 1440              # Max time in paper mode (24h = 1440 min)

