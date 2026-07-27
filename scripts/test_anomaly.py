import pandas as pd
from src.analytics.history import load_status_history, add_time_features, disruption_rate_by, detect_anomalies

df = load_status_history()
feat = add_time_features(df)

# Find a line x hour that HAS a disruption in history, to test against
disrupted = feat[feat['is_disrupted']]
print('Sample disrupted observations (line, hour):')
print(disrupted.groupby(['line_name','hour']).size().head(10))
print()

# Show the baseline the detector would compare against
baseline = disruption_rate_by(df, 'line_id', 'hour')
print('Buckets with enough data to judge (>=8 obs):')
print(baseline[baseline['observations'] >= 8].sort_values('rate_pct').head(15).to_string(index=False))