import os
import time

from dotenv import load_dotenv

load_dotenv()

from src.data_loader import load_dukascopy_csv, resample_to_m15
from src.optimizer import GridSearchOptimizer
from src.results_analyzer import ResultsAnalyzer


if __name__ == "__main__":
    # Load data giống main.py
    DUKASCOPY_CSV = os.environ.get("DUKASCOPY_CSV_PATH", "dukascopy_xauusd_m1.csv")

    if not os.path.exists(DUKASCOPY_CSV):
        raise SystemExit(
            f"Dukascopy CSV not found at {DUKASCOPY_CSV}. "
            "Set DUKASCOPY_CSV_PATH or download data first."
        )

    print(f"Loading XAUUSD M1 data from Dukascopy CSV: {DUKASCOPY_CSV}")
    m1_data = load_dukascopy_csv(DUKASCOPY_CSV)
    if m1_data.empty:
        raise SystemExit("No M1 data loaded. Check data source / file path / format.")

    print("Resampling M1 -> M15 ...")
    m15_data = resample_to_m15(m1_data)

    # Define parameter grid (ưu tiên R:R, trailing SL, ADX)
    param_grid = {
        "r_r_ratio_min": [1.5, 2.0],
        "r_r_ratio_target": [2.0, 2.5],
        # "trailing_sl_trigger": [1.5],
        # "trailing_sl_level": [0.5],
        # "adx_max_entry": [30.0],
        # Các tham số khác có thể add thêm sau
    }

    print("Starting randomized grid search optimization (subset of configs)...")
    optimizer = GridSearchOptimizer(m1_data=m1_data, m15_data=m15_data, param_grid=param_grid)

    t0 = time.time()
    # Dùng random subset để giảm thời gian: ví dụ tối đa 40 cấu hình, 2 core.
    results = optimizer.run(n_jobs=1, max_configs=1, random_subset=True)
    elapsed = time.time() - t0

    print(f"Optimization finished in {elapsed:.1f} seconds. Total configs tested: {len(results)}")

    analyzer = ResultsAnalyzer(results)
    analyzer.print_top_configs(n=10)

    # Optional: export để phân tích thêm
    try:
        analyzer.export_to_csv("optimization_results.csv")
    except Exception as e:
        print(f"Could not export results to CSV: {e}")

