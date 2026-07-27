import pandas as pd
from src.analytics.history import detect_anomalies

# Minimal fake history: Victoria line, mostly good at 3am (quiet hour),
# then one CURRENT disruption at 3am -> should flag Anomalous.
now = pd.Timestamp.now(tz="UTC").normalize() + pd.Timedelta(hours=3)
rows = []
# 10 historical good-service observations at 3am (establishes low baseline)
for i in range(10):
    rows.append({
        "line_id": "victoria", "line_name": "Victoria",
        "status_severity": 10, "status_description": "Good Service",
        "reason": None,
        "polled_at": now - pd.Timedelta(days=i+1),
    })
# The current observation: disrupted, at 3am
rows.append({
    "line_id": "victoria", "line_name": "Victoria",
    "status_severity": 6, "status_description": "Severe Delays",
    "reason": "Test", "polled_at": now,
})
df = pd.DataFrame(rows)
df["polled_at"] = pd.to_datetime(df["polled_at"], utc=True)
df["is_good"] = df["status_description"].str.strip().str.lower() == "good service"

print(detect_anomalies(df).to_string(index=False))