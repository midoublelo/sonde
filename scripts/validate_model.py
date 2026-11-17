import numpy as np
import pandas as pd

from src.analytics.baseline_model import fit_model
from src.analytics.history import add_time_features, load_status_history

TRAIN_FRACTION = 0.8

def _logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

def _brier(y, p):
    return float(np.mean((y - p) ** 2))

def main() -> None:
    df = load_status_history()
    if df.empty:
        print("No data to validate against.")
        return

    feat = add_time_features(df).sort_values("polled_at").reset_index(drop=True)
    split = int(len(feat) * TRAIN_FRACTION)
    train, test = feat.iloc[:split], feat.iloc[split:]

    model = fit_model(train)

    p = test.apply(
        lambda r: model.predict(r["line_id"], r["hour"], r["is_weekend"]), axis=1
    ).to_numpy()
    y = test["is_disrupted"].astype(float).to_numpy()
    base = np.full_like(y, float(train["is_disrupted"].mean()))

    print(f"Train rows: {len(train)}   Test rows: {len(test)}")
    print(f"Test period: {test['polled_at'].min()}  ->  {test['polled_at'].max()}")
    print()
    print(f"{'':24} {'LogLoss':>10} {'Brier':>10}")
    print(f"{'Global-rate baseline':24} {_logloss(y, base):>10.4f} {_brier(y, base):>10.4f}")
    print(f"{'Smoothed model':24} {_logloss(y, p):>10.4f} {_brier(y, p):>10.4f}")
    print()

    dfc = pd.DataFrame({"p": p, "y": y})
    dfc["bin"] = (dfc["p"] * 10).astype(int).clip(0, 9)
    cal = dfc.groupby("bin").agg(
        predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")
    )
    print("Calibration (predicted vs actual disruption rate per probability band):")
    print(cal.round(3).to_string())

if __name__ == "__main__":
    main()
