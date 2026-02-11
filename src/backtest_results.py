from dataclasses import dataclass
from typing import List
import math

from .strategy_config import StrategyConfig
from .pinescript_port import Trade


@dataclass
class BacktestResult:
    """
    Kết quả 1 lần backtest với 1 bộ StrategyConfig.
    Dùng cho optimizer để so sánh các cấu hình.
    """

    config: StrategyConfig
    trades: List[Trade]

    # Performance metrics
    total_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    sharpe_ratio: float

    # Execution time
    backtest_duration_seconds: float

    @classmethod
    def from_trades(
        cls,
        config: StrategyConfig,
        trades: List[Trade],
        initial_capital: float,
        equity_curve: List[float],
        backtest_duration_seconds: float,
    ) -> "BacktestResult":
        total_trades = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]

        total_profit = sum(t.pnl for t in wins)
        total_loss = sum(t.pnl for t in losses)  # âm
        total_pnl = total_profit + total_loss

        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0

        avg_win = total_profit / winning_trades if winning_trades > 0 else 0.0
        avg_loss = total_loss / losing_trades if losing_trades > 0 else 0.0

        profit_factor = (
            total_profit / abs(total_loss) if total_loss < 0 else math.inf if total_profit > 0 else 0.0
        )

        # Max drawdown từ equity_curve
        max_drawdown = 0.0
        peak = initial_capital
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            drawdown = peak - eq
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Sharpe ratio đơn giản trên returns theo trade
        returns = []
        prev_eq = initial_capital
        for eq in equity_curve:
            if prev_eq > 0:
                r = (eq - prev_eq) / prev_eq
                returns.append(r)
            prev_eq = eq

        if len(returns) > 1:
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            std_r = math.sqrt(var_r)
            sharpe = (mean_r / std_r) * math.sqrt(len(returns)) if std_r > 0 else 0.0
        else:
            sharpe = 0.0

        return cls(
            config=config,
            trades=trades,
            total_pnl=total_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            backtest_duration_seconds=backtest_duration_seconds,
        )

