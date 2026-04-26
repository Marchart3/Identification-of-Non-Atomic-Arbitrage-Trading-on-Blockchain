import pandas as pd

# ==================== 1. 读取数据 ====================
binance = pd.read_csv('src/data/binance.csv')
uniswap = pd.read_csv('src/data/uniswap.csv')

# ==================== 2. 时间戳统一转换 ====================
# 根据你的数据样本，均为毫秒级 Unix 时间戳
binance['datetime'] = pd.to_datetime(binance['timestamp'], unit='ms', utc=True)
uniswap['datetime'] = pd.to_datetime(uniswap['timestamp'], unit='ms', utc=True)

# ==================== 3. 单位统一 ====================
# Binance 交易量转换为 ETH（假设 volume 是以 USDT 计价）
binance['volume_eth'] = binance['volume'] / binance['price']

# Uniswap 数据已包含 volume_eth，无需额外转换
# 注意：如果 Uniswap price 还未标准化（除以 1e12），请在此处处理：
uniswap['price'] = uniswap['price'] / 1e12
uniswap['price'] = 1 / uniswap['price']
# ==================== 4. 按时间排序（merge_asof 必需） ====================
binance = binance.sort_values('datetime')
uniswap = uniswap.sort_values('datetime')

# ==================== 5. 使用 merge_asof 进行最近时间对齐 ====================
# 以 Uniswap 每笔交易为基准，匹配最接近的 Binance 价格
aligned = pd.merge_asof(
    uniswap[['datetime', 'price', 'volume_eth', 'direction']],
    binance[['datetime', 'price', 'volume_eth', 'direction']],
    on='datetime',
    direction='nearest',                   # 匹配最近时间
    tolerance=pd.Timedelta('2s'),          # 最大时差 2 秒
    suffixes=('_uniswap', '_binance')
)

# ==================== 6. 缺失值处理（兼容新版 pandas） ====================
# 数值列：线性插值
value_cols = ['price_uniswap', 'price_binance', 'volume_eth_uniswap', 'volume_eth_binance']
aligned[value_cols] = aligned[value_cols].interpolate(method='linear', limit_direction='both')

# 方向列：前向填充 + 后向填充（新版 API）
direction_cols = ['direction_uniswap', 'direction_binance']
aligned[direction_cols] = aligned[direction_cols].ffill().bfill()

# ==================== 7. 保存结果 ====================
aligned.to_csv('aligned_data.csv', index=False)
print("对齐完成，结果已保存至 aligned_data.csv")
print(f"总记录数: {len(aligned)}")