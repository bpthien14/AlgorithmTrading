from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional
import uuid
from datetime import datetime


class ZoneType(Enum):
    SUPPLY = auto()
    DEMAND = auto()


class TradeDirection(Enum):
    BUY = auto()
    SELL = auto()


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class LiquidityPoint:
    price: float
    timestamp: datetime
    is_buy_liquidity: bool


@dataclass
class Box:
    """
    Box tổng quát – tương đương object `box` trong PineScript.
    Dùng làm base cho mọi vùng (demand/supply, buy/sell base).
    """

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    price_top: float = 0.0
    price_bottom: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    # bar_index hoặc timestamp tạo box – tuỳ nguồn dữ liệu
    created_bar_index: Optional[int] = None

    # State chung
    touch_count: int = 0
    is_active: bool = True

    def contains_price(self, price: float) -> bool:
        """Giá hiện tại nằm trong box."""
        return self.price_bottom <= price <= self.price_top

    def width(self) -> float:
        """Độ rộng (height) của box theo giá."""
        return max(0.0, self.price_top - self.price_bottom)

    def mark_touched(self) -> None:
        """Cập nhật box khi bị chạm."""
        if not self.is_active:
            return
        self.touch_count += 1

    def deactivate(self) -> None:
        """Vô hiệu hoá box khi bị phá hoặc hết hạn."""
        self.is_active = False


@dataclass
class BuySellBase(Box):
    """
    Box base cho entry Buy / Sell (Buy Base / Sell Base).
    Mapping với `arrayBoxBuyBase`, `arrayBoxSellBase` trong PineScript.
    """

    direction: TradeDirection = TradeDirection.BUY

    # Rule cấu hình
    max_touches: int = 2  # ví dụ: base bị chạm quá 2 lần thì bỏ
    max_age_bars: Optional[int] = None  # timeout theo số bar nếu cần

    # Runtime
    age_in_bars: int = 0

    def register_new_bar(self) -> None:
        """Gọi mỗi bar để tăng tuổi của base và kiểm tra timeout."""
        if not self.is_active:
            return
        self.age_in_bars += 1
        if self.max_age_bars is not None and self.age_in_bars > self.max_age_bars:
            self.deactivate()

    def register_touch(self, price: float) -> None:
        """
        Gọi khi giá chạm base. Nếu chạm quá số lần cho phép thì tự deactivate.
        """
        if not self.contains_price(price) or not self.is_active:
            return

        self.mark_touched()
        if self.touch_count > self.max_touches:
            self.deactivate()


@dataclass
class DemandSupplyZone(Box):
    """
    Box demand / supply zone nâng cao.
    Mapping với `arrayBoxDem`, `arrayBoxSup`.
    """

    zone_type: ZoneType = ZoneType.DEMAND

    # Rule cấu hình
    max_touches: int = 3
    max_age_bars: Optional[int] = None

    # Runtime
    age_in_bars: int = 0

    def register_new_bar(self) -> None:
        """Gọi mỗi bar để tăng tuổi của zone và kiểm tra timeout."""
        if not self.is_active:
            return
        self.age_in_bars += 1
        if self.max_age_bars is not None and self.age_in_bars > self.max_age_bars:
            self.deactivate()

    def is_broken_by(self, price: float) -> bool:
        """
        Kiểm tra zone đã bị phá chưa (tương tự logic TradingZone).
        """
        if self.zone_type == ZoneType.DEMAND:
            return price < self.price_bottom
        return price > self.price_top

    def register_touch(self, price: float) -> None:
        """
        Cập nhật zone khi giá chạm; nếu chạm quá số lần cho phép hoặc bị phá
        thì deactivate.
        """
        if not self.is_active:
            return

        if self.is_broken_by(price):
            self.deactivate()
            return

        if self.contains_price(price):
            self.mark_touched()
            if self.touch_count > self.max_touches:
                self.deactivate()
