from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.analytics.history import add_time_features

SPARK_RATE_TABLE = Path("data/spark_analysis/disruption_rate_by_bucket")

PRIOR_STRENGTH = 8.0

@dataclass
class DisruptionRateModel:

    global_rate: float
    by_line: dict[str, tuple[float, int]] = field(default_factory=dict)
    by_line_hour: dict[tuple[str, int], tuple[float, int]] = field(default_factory=dict)
    by_full: dict[tuple[str, int, bool], tuple[float, int]] = field(default_factory=dict)
    line_names: dict[str, str] = field(default_factory=dict)

    def _shrink(self, bucket_rate: float, n: int, prior: float) -> float:
        return (bucket_rate * n + prior * PRIOR_STRENGTH) / (n + PRIOR_STRENGTH)

    def predict(self, line_id: str, hour: int, is_weekend: bool) -> float:
        rate = self.global_rate

        line_entry = self.by_line.get(line_id)
        if line_entry is not None:
            line_rate, line_n = line_entry
            rate = self._shrink(line_rate, line_n, rate)

        lh_entry = self.by_line_hour.get((line_id, hour))
        if lh_entry is not None:
            lh_rate, lh_n = lh_entry
            rate = self._shrink(lh_rate, lh_n, rate)

        full_entry = self.by_full.get((line_id, hour, bool(is_weekend)))
        if full_entry is not None:
            full_rate, full_n = full_entry
            rate = self._shrink(full_rate, full_n, rate)

        return rate

    def predict_rate(self, line_id: str, hour: int, is_weekend: bool) -> float:
        return 100.0 * self.predict(line_id, hour, is_weekend)

    def support(self, line_id: str, hour: int, is_weekend: bool) -> int:
        full_entry = self.by_full.get((line_id, hour, bool(is_weekend)))
        if full_entry is not None:
            return full_entry[1]
        lh_entry = self.by_line_hour.get((line_id, hour))
        if lh_entry is not None:
            return lh_entry[1]
        line_entry = self.by_line.get(line_id)
        return line_entry[1] if line_entry is not None else 0

def _rate_table(featured: pd.DataFrame, group_cols: list[str]) -> dict:
    grouped = featured.groupby(group_cols)["is_disrupted"].agg(["mean", "size"])
    out = {}
    for key, row in grouped.iterrows():
        out[key] = (float(row["mean"]), int(row["size"]))
    return out

def fit_model(status_df: pd.DataFrame) -> DisruptionRateModel:
    if status_df.empty:
        return DisruptionRateModel(global_rate=0.0)

    featured = add_time_features(status_df)

    global_rate = float(featured["is_disrupted"].mean())
    by_line = _rate_table(featured, ["line_id"])
    by_line_hour = _rate_table(featured, ["line_id", "hour"])

    raw_full = _rate_table(featured, ["line_id", "hour", "is_weekend"])
    by_full = {
        (line_id, int(hour), bool(weekend)): val
        for (line_id, hour, weekend), val in raw_full.items()
    }

    line_names = (
        featured[["line_id", "line_name"]]
        .drop_duplicates()
        .set_index("line_id")["line_name"]
        .to_dict()
    )

    return DisruptionRateModel(
        global_rate=global_rate,
        by_line=by_line,
        by_line_hour={(l, int(h)): v for (l, h), v in by_line_hour.items()},
        by_full=by_full,
        line_names=line_names,
    )

def fit_model_from_spark_table(
    rate_table: pd.DataFrame, line_names: dict[str, str] | None = None
) -> DisruptionRateModel:
    if rate_table.empty:
        return DisruptionRateModel(global_rate=0.0)

    rt = rate_table.copy()
    rt["isWeekend"] = rt["isWeekend"].astype(bool)
    rt["weighted"] = rt["disruptionRate"] * rt["observations"]

    total_obs = rt["observations"].sum()
    global_rate = float(rt["weighted"].sum() / total_obs) if total_obs else 0.0

    def _collapse(keys: list[str]) -> dict:
        g = rt.groupby(keys).agg(
            w=("weighted", "sum"), n=("observations", "sum")
        )
        return {
            (idx if len(keys) > 1 else idx): (float(r["w"] / r["n"]), int(r["n"]))
            for idx, r in g.iterrows()
        }

    by_line = _collapse(["lineId"])
    by_line_hour = {
        (lid, int(h)): v for (lid, h), v in _collapse(["lineId", "hour"]).items()
    }
    by_full = {
        (row["lineId"], int(row["hour"]), bool(row["isWeekend"])): (
            float(row["disruptionRate"]),
            int(row["observations"]),
        )
        for _, row in rt.iterrows()
    }

    if line_names is None:
        if "lineName" in rt.columns:
            line_names = (
                rt[["lineId", "lineName"]]
                .drop_duplicates()
                .set_index("lineId")["lineName"]
                .to_dict()
            )
        else:
            line_names = {lid: lid for lid in rt["lineId"].unique()}

    return DisruptionRateModel(
        global_rate=global_rate,
        by_line=by_line,
        by_line_hour=by_line_hour,
        by_full=by_full,
        line_names=line_names,
    )

def load_spark_model() -> DisruptionRateModel | None:
    if not SPARK_RATE_TABLE.exists():
        return None
    df = pd.read_parquet(SPARK_RATE_TABLE)
    if df.empty:
        return None
    return fit_model_from_spark_table(df)

def predictions_frame(model: DisruptionRateModel) -> pd.DataFrame:
    rows = []
    for line_id, line_name in sorted(model.line_names.items(), key=lambda x: x[1]):
        for hour in range(24):
            for is_weekend in (False, True):
                rows.append(
                    {
                        "line_id": line_id,
                        "Line": line_name,
                        "Hour": hour,
                        "Weekend": is_weekend,
                        "Predicted disruption %": round(
                            model.predict_rate(line_id, hour, is_weekend), 1
                        ),
                        "Support (obs)": model.support(line_id, hour, is_weekend),
                    }
                )
    return pd.DataFrame(rows)