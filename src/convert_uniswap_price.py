import pandas as pd

# 读取数据
df = pd.read_csv('src/data/uniswap.csv')

# 确保 price 列存在且不为 0
if 'price' not in df.columns:
    raise KeyError("CSV 文件中没有 'price' 列，请检查列名。")

# 转换前检查零值，避免除零错误
zero_mask = df['price'] == 0
if zero_mask.any():
    print(f"警告：发现 {zero_mask.sum()} 行 price = 0，这些行将被丢弃。")
    df = df[~zero_mask]

# 核心转换：price = (1/price) * 10^12
df['price'] = (1.0 / df['price']) * 1e12

# 保存回原文件（覆盖）
df.to_csv('src/data/uniswap.csv', index=False)

print(f"转换完成，共处理 {len(df)} 行。price 已更新为 USDT/ETH。")