import pandas as pd
import numpy as np

# ==================== 参数设置 ====================
INPUT_FILE = 'aligned_data.csv'       # 原始对齐数据
OUTPUT_FILE = 'aligned_data_clean.csv'  # 清洗后数据
ANOMALY_FILE = 'anomaly_records.csv'    # 被剔除的异常记录（可选）

# 价格比率阈值：允许 Uniswap 价格在 Binance 价格的 0.8 ~ 1.2 倍之间
LOWER_RATIO = 0.8
UPPER_RATIO = 1.2

# ==================== 读取数据 ====================
print("正在读取数据...")
df = pd.read_csv(INPUT_FILE, parse_dates=['datetime'])

# 计算价格比率
df['price_ratio'] = df['price_uniswap'] / df['price_binance']

# ==================== 识别异常 ====================
anomaly_mask = (df['price_ratio'] < LOWER_RATIO) | (df['price_ratio'] > UPPER_RATIO)

# 提取异常记录以备核查
anomalies = df[anomaly_mask].copy()
normal = df[~anomaly_mask].copy()

# ==================== 输出统计 ====================
print(f"原始记录总数: {len(df)}")
print(f"剔除异常记录数: {len(anomalies)} ({len(anomalies)/len(df)*100:.2f}%)")
print(f"保留正常记录数: {len(normal)}")
print(f"\n异常记录价格比率范围: {anomalies['price_ratio'].min():.2f} ~ {anomalies['price_ratio'].max():.2f}")

# ==================== 保存结果 ====================
# 清理后数据（删除辅助列 price_ratio, 可选保留）
normal.drop(columns=['price_ratio'], inplace=True)
normal.to_csv(OUTPUT_FILE, index=False)
print(f"\n清洗后数据已保存至: {OUTPUT_FILE}")

# 保存异常记录供人工复核
anomalies.to_csv(ANOMALY_FILE, index=False)
print(f"异常记录已保存至: {ANOMALY_FILE} （可手动检查）")