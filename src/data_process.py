import pandas as pd
import numpy as np

# ==================== 0. 参数设置 ====================
INPUT_BINANCE = 'src/data/binance.csv'
INPUT_UNISWAP = 'src/data/uniswap.csv'
OUTPUT_ALIGNED = 'aligned_data.csv'
ALIGN_TOLERANCE = pd.Timedelta('2s')  # 最大对齐时差

# ==================== 1. 读取原始数据 ====================
print("正在读取数据...")
binance_raw = pd.read_csv(INPUT_BINANCE)
uniswap_raw = pd.read_csv(INPUT_UNISWAP)

print(f"Binance 原始记录数: {len(binance_raw)}")
print(f"Uniswap 原始记录数: {len(uniswap_raw)}")

# ==================== 2. 数据清洗与去重 ====================

def clean_binance(df):
    """清洗 Binance 数据：去除无效记录、去重、单位转换"""
    # 2.1 丢弃关键字段缺失的行
    essential = ['timestamp', 'price', 'volume', 'direction']
    df = df.dropna(subset=essential).copy()
    
    # 2.2 去除价格/成交量非正数的异常值
    df = df[(df['price'] > 0) & (df['volume'] > 0)]
    
    # 2.3 只保留有效方向
    df = df[df['direction'].isin(['buy', 'sell'])]
    
    # 2.4 时间戳转为 datetime（毫秒 -> UTC）
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    
    # 2.5 交易量统一为 ETH 单位（假设 volume 以 USDT 计价）
    df['volume_eth'] = df['volume'] / df['price']
    
    # 2.6 去重：基于时间戳+价格+交易量+方向（trade_id 可能为聚合范围，不适合直接去重）
    # 保留第一次出现的记录
    df = df.drop_duplicates(subset=['datetime', 'price', 'volume_eth', 'direction'], keep='first')
    
    # 2.7 按时间排序
    df = df.sort_values('datetime').reset_index(drop=True)
    
    return df[['datetime', 'price', 'volume_eth', 'direction']]


def clean_uniswap(df):
    """清洗 Uniswap V3 数据：去除无效交易、去重、格式标准化"""
    # 2.1 丢弃关键字段缺失的行
    essential = ['timestamp', 'price', 'volume_eth', 'direction', 'trade_id']
    df = df.dropna(subset=essential).copy()
    
    # 2.2 价格与交易量必须为正数
    df = df[(df['price'] > 0) & (df['volume_eth'] > 0)]
    
    # 2.3 仅保留已知方向（buy/sell），排除任何无效值
    df = df[df['direction'].isin(['buy', 'sell'])]
    
    # 2.4 时间戳转为 datetime（毫秒 -> UTC）
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    
    # 2.5 注意：Uniswap 的 Swap 事件本身只记录成功交易，无需额外过滤失败交易。
    # 但可剔除 trade_id 为空或格式异常的记录（如有必要）
    df = df[df['trade_id'].str.strip() != '']
    
    # 2.6 去重：基于交易哈希（trade_id）去重，每笔链上交易唯一
    df = df.drop_duplicates(subset='trade_id', keep='first')
    
    # 2.7 按时间排序
    df = df.sort_values('datetime').reset_index(drop=True)
    
    return df[['datetime', 'price', 'volume_eth', 'direction']]


# 执行清洗
print("\n清洗 Binance 数据...")
binance = clean_binance(binance_raw)
print(f"Binance 清洗后记录数: {len(binance)}")

print("清洗 Uniswap 数据...")
uniswap = clean_uniswap(uniswap_raw)
print(f"Uniswap 清洗后记录数: {len(uniswap)}")

# ==================== 3. 时间对齐（merge_asof） ====================
print("\n正在进行时间对齐...")
aligned = pd.merge_asof(
    uniswap,
    binance,
    on='datetime',
    direction='nearest',
    tolerance=ALIGN_TOLERANCE,
    suffixes=('_uniswap', '_binance')
)

# ==================== 4. 对齐后缺失值处理 ====================
# 价格与交易量：线性插值（只在有数据的时间段内）
value_cols = ['price_uniswap', 'price_binance', 'volume_eth_uniswap', 'volume_eth_binance']
aligned[value_cols] = aligned[value_cols].interpolate(method='linear', limit_direction='both')

# 方向字段：前向填充 + 后向填充
direction_cols = ['direction_uniswap', 'direction_binance']
aligned[direction_cols] = aligned[direction_cols].ffill().bfill()

# 再次检查并剔除插值后仍为空的极端情况（极少）
aligned = aligned.dropna(subset=value_cols)

print(f"对齐后记录数: {len(aligned)}")

# ==================== 5. 保存结果 ====================
aligned.to_csv(OUTPUT_ALIGNED, index=False)
print(f"\n清洗对齐完成，结果已保存至 {OUTPUT_ALIGNED}")