import pandas as pd

df = pd.read_csv('aligned_data.csv', parse_dates=['datetime'])
extreme = df[df['price_binance'] - df['price_uniswap'] < -2000]  # 找出所有异常大的负价差
print(extreme[['datetime', 'price_uniswap', 'price_binance']].to_string())