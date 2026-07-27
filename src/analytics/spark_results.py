from pathlib import Path

import pandas as pd

SPARK_OUTPUT_DIR = Path("data/spark_analysis")

def _load_parquet(name: str) -> pd.DataFrame:
    path = SPARK_OUTPUT_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def load_severity_by_line() -> pd.DataFrame:
    """Average status severity per line (Service Closed excluded)."""
    return _load_parquet("avg_severity_by_line")


def load_severity_by_weather() -> pd.DataFrame:
    """Average status severity per weather condition, hour-bucketed join."""
    return _load_parquet("avg_severity_by_weather")


def load_weather_correlations() -> pd.DataFrame:
    return _load_parquet("weather_correlations")