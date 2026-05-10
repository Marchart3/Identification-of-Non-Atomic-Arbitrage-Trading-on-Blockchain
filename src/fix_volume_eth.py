import pandas as pd

FILE = 'aligned_data_clean.csv'

df = pd.read_csv(FILE, parse_dates=['datetime'])
df['volume_eth_uniswap'] = df['volume_eth_uniswap'] / 1e18
df.to_csv(FILE, index=False)

print(f"已修复 {FILE}，volume_eth_uniswap 单位转换为 ETH。")