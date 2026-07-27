import pandas as pd
from src.analytics.history import load_status_history, load_weather_history
t = pd.Series(sorted(load_status_history()['polled_at'].unique()))
w = pd.Series(sorted(load_weather_history()['polled_at'].unique()))
paired = pd.merge_asof(pd.DataFrame({'t':t}), pd.DataFrame({'w':w,'w2':w}),
    left_on='t', right_on='w', direction='nearest', tolerance=pd.Timedelta('2min'))
misses = paired[paired['w2'].isna()]['t']
print('Missing-weather polls by hour:')
print(misses.dt.hour.value_counts().sort_index())