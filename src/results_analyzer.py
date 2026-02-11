from typing import List

from .backtest_results import BacktestResult


class ResultsAnalyzer:
    """
    Công cụ tiện ích để xem, lọc và export kết quả tối ưu.
    """

    def __init__(self, results: List[BacktestResult]) -> None:
        self.results = results

    def print_top_configs(self, n: int = 10) -> None:
        print(f"\n=== TOP {n} CONFIGURATIONS ===")
        for i, r in enumerate(self.results[:n], 1):
            print(
                f"Rank {i}: Profit Factor={r.profit_factor:.2f}, "
                f"Win Rate={r.win_rate:.2f}%, "
                f"Trades={r.total_trades}, "
                f"TotalPnL={r.total_pnl:,.0f}"
            )
            cfg = r.config
            print(
                f"  - r_r_ratio_min={cfg.r_r_ratio_min}, "
                f"r_r_ratio_target={cfg.r_r_ratio_target}, "
                f"trailing_sl_trigger={cfg.trailing_sl_trigger}, "
                f"trailing_sl_level={cfg.trailing_sl_level}, "
                f"adx_max_entry={cfg.adx_max_entry}"
            )

    def export_to_csv(self, path: str) -> None:
        """
        Export kết quả ra CSV để phân tích thêm (pandas optional).
        """
        try:
            import pandas as pd
        except ImportError:
            print("pandas not installed, cannot export to CSV.")
            return

        rows = []
        for r in self.results:
            cfg = r.config
            rows.append(
                {
                    "total_pnl": r.total_pnl,
                    "total_trades": r.total_trades,
                    "winning_trades": r.winning_trades,
                    "losing_trades": r.losing_trades,
                    "win_rate": r.win_rate,
                    "profit_factor": r.profit_factor,
                    "avg_win": r.avg_win,
                    "avg_loss": r.avg_loss,
                    "max_drawdown": r.max_drawdown,
                    "sharpe_ratio": r.sharpe_ratio,
                    "backtest_duration_seconds": r.backtest_duration_seconds,
                    # Config fields
                    "r_r_ratio_min": cfg.r_r_ratio_min,
                    "r_r_ratio_target": cfg.r_r_ratio_target,
                    "trailing_sl_trigger": cfg.trailing_sl_trigger,
                    "trailing_sl_level": cfg.trailing_sl_level,
                    "adx_max_entry": cfg.adx_max_entry,
                    "adx_period": cfg.adx_period,
                    "max_entry_timeout_minutes": cfg.max_entry_timeout_minutes,
                    "zone_touch_buffer": cfg.zone_touch_buffer,
                    "enable_timerange_filter": cfg.enable_timerange_filter,
                }
            )

        df = pd.DataFrame(rows)
        df.to_csv(path, index=False)
        print(f"Exported optimization results to {path}")

