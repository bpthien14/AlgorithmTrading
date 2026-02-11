from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class StrategyConfig:
    """
    Config cho toàn bộ strategy – tập trung tất cả tham số có thể tối ưu.
    Các default được chọn để khớp với bản PineScript hiện tại.
    """

    # R:R / TP logic
    r_r_ratio_min: float = 1.0          # R:R tối thiểu để chấp nhận entry (hiện tại Pine dùng 1R bắt buộc hợp lệ)
    r_r_ratio_target: float = 2.0       # R:R target khi adjust TP (Pine đang dùng 2R)

    # Trailing SL (dời SL về 0.5R khi đạt 1.5R)
    trailing_sl_trigger: float = 1.5    # Khi lãi đạt bao nhiêu R thì kích hoạt trailing
    trailing_sl_level: float = 1.0      # Dời SL về mức bao nhiêu R

    # ADX filter
    adx_max_entry: float = 30.0         # Điều kiện ADX < adx_max_entry
    adx_period: int = 14                # Period tính ADX (Pine mặc định 14)

    # Position sizing – risk theo % vốn mỗi lệnh
    # FIXED: Đã sửa công thức từ /100000 thành /100
    # → Bây giờ risk_per_trade = 1.0 nghĩa là risk 1% vốn mỗi lệnh
    # → risk_per_trade = 2.0 nghĩa là risk 2% vốn mỗi lệnh
    # Ví dụ: vốn 10M, risk 1% = 100K, nếu SL cách 5 USD thì lot_size = 200,000
    risk_per_trade: float = 4.0  # 1% vốn mỗi lệnh

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

