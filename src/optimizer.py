import itertools
import random
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Iterable, List, Any, Optional

import pandas as pd

from .strategy_config import StrategyConfig
from .pinescript_port import PineScriptStrategy
from .backtest_results import BacktestResult


def _run_single_backtest(args: Any) -> BacktestResult:
    """
    Hàm worker top-level để ProcessPoolExecutor có thể pickle được.
    Nhận (m1_data, m15_data, config) và trả về BacktestResult.
    """
    m1_data, m15_data, config = args

    start = time.time()
    strat = PineScriptStrategy(m1_data=m1_data, m15_data=m15_data, config=config)
    trades = strat.run()
    duration = time.time() - start

    return BacktestResult.from_trades(
        config=config,
        trades=trades,
        initial_capital=strat.initial_capital,
        equity_curve=strat.equity_curve,
        backtest_duration_seconds=duration,
    )


class GridSearchOptimizer:
    """
    Chạy grid search trên không gian parameters của StrategyConfig.
    """

    def __init__(
        self,
        m1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        param_grid: Dict[str, Iterable],
    ) -> None:
        self.m1_data = m1_data
        self.m15_data = m15_data
        self.param_grid = param_grid

    def _generate_configs(self) -> List[StrategyConfig]:
        keys = list(self.param_grid.keys())
        values_product = itertools.product(*(self.param_grid[k] for k in keys))

        configs: List[StrategyConfig] = []
        for values in values_product:
            kwargs = dict(zip(keys, values))
            cfg = StrategyConfig(**kwargs)
            configs.append(cfg)
        return configs

    def run(
        self,
        n_jobs: int = -1,
        max_configs: Optional[int] = None,
        random_subset: bool = False,
    ) -> List[BacktestResult]:
        """
        Chạy grid search.

        - n_jobs = -1      => dùng tất cả CPU cores
        - n_jobs = 1       => chạy tuần tự (debug)
        - max_configs != None và random_subset=True:
              chỉ chạy ngẫu nhiên max_configs cấu hình
        """
        configs = self._generate_configs()

        if max_configs is not None and max_configs < len(configs):
            if random_subset:
                configs = random.sample(configs, k=max_configs)
            else:
                configs = configs[:max_configs]

        # Chuẩn bị args cho worker
        args_list = [(self.m1_data, self.m15_data, cfg) for cfg in configs]

        if n_jobs == 1:
            results = [_run_single_backtest(args) for args in args_list]
        else:
            max_workers = None if n_jobs < 0 else n_jobs
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(_run_single_backtest, args_list))

        # Sắp xếp theo profit_factor giảm dần
        results.sort(key=lambda r: r.profit_factor, reverse=True)
        return results

