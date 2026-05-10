import pandas as pd
import numpy as np

# ==================== 配置 ====================
ALIGNED_FILE = 'aligned_data_clean.csv'
EVENTS_FILE  = 'arbitrage_events.csv'
DETAILS_FILE = 'arbitrage_details.csv'

# 价格比率合理范围（与清洗时一致）
RATIO_LOWER = 0.8
RATIO_UPPER = 1.2

# ==================== 读取数据 ====================
print("读取数据...")
try:
    aligned = pd.read_csv(ALIGNED_FILE, parse_dates=['datetime'])
    events = pd.read_csv(EVENTS_FILE, parse_dates=['start_time', 'end_time'])
    details = pd.read_csv(DETAILS_FILE, parse_dates=['datetime'])
except FileNotFoundError as e:
    print(f"缺少文件：{e}")
    exit()

# 计算原始对齐数据中的价格比率
aligned['price_ratio'] = aligned['price_uniswap'] / aligned['price_binance']

# ==================== 1. 套利事件整体统计 ====================
print("\n" + "="*60)
print("套利事件统计摘要")
print("="*60)
print(f"事件总数：{len(events)}")
print(f"交易明细总数：{len(details)}")
print(f"\n[利润分布]")
print(events['total_profit'].describe())
print(f"\n[平均价差分布]")
print(events['avg_spread'].describe())
print(f"\n[总成交量分布 (ETH)]")
print(events['total_volume_eth'].describe())

# 利润为负的事件（理论上不应该出现）
negative_profit = events[events['total_profit'] < 0]
if len(negative_profit) > 0:
    print(f"\n⚠️ 警告：发现 {len(negative_profit)} 个利润为负的事件！")
    print(negative_profit[['start_time', 'total_profit', 'avg_spread']].head())

# 强信号事件占比
strong_events = events[events['strong_signal_ratio'] > 0.5]
print(f"\n强信号事件 (z>3 占比>50%)：{len(strong_events)} 个"
      f" ({len(strong_events)/len(events)*100:.1f}%)")

# ==================== 2. 利润最高的事件抽查 ====================
print("\n" + "="*60)
print("利润最高的 5 个事件")
print("="*60)
top5 = events.sort_values('total_profit', ascending=False).head(5)
for _, row in top5.iterrows():
    print(f"\n事件 ID {row['event_id']}:")
    print(f"  时间：{row['start_time']} ~ {row['end_time']}")
    print(f"  平均价差：{row['avg_spread']:.4f} USDT")
    print(f"  总成交量：{row['total_volume_eth']:.6f} ETH")
    print(f"  预估利润：{row['total_profit']:.2f} USDT")
    print(f"  交易笔数：{row['trade_count']}")
    print(f"  强信号占比：{row['strong_signal_ratio']:.2f}")
    print(f"  方向：{row['arbitrage_type']}")

    # 提取该事件时间窗口内的原始对齐数据
    mask = (aligned['datetime'] >= row['start_time']) & (aligned['datetime'] <= row['end_time'])
    event_data = aligned[mask]
    if not event_data.empty:
        # 价格比率统计
        ratio_mean = event_data['price_ratio'].mean()
        ratio_min = event_data['price_ratio'].min()
        ratio_max = event_data['price_ratio'].max()
        print(f"  窗口内价格比率 (Uni/Bin)：均值 {ratio_mean:.4f}，"
              f"最小 {ratio_min:.4f}，最大 {ratio_max:.4f}")
        if ratio_min < RATIO_LOWER or ratio_max > RATIO_UPPER:
            print(f"  ⚠️ 警告：价格比率超出 [{RATIO_LOWER}, {RATIO_UPPER}]，可能存在异常数据！")

# ==================== 3. 全局价格比率异常检查 ====================
print("\n" + "="*60)
print("全局价格比率异常检查")
print("="*60)
# 统计 aligned 中比率超出合理范围的行
anomaly_ratio = aligned[(aligned['price_ratio'] < RATIO_LOWER) |
                        (aligned['price_ratio'] > RATIO_UPPER)]
print(f"对齐数据中价格比率异常记录数：{len(anomaly_ratio)} / {len(aligned)}"
      f" ({len(anomaly_ratio)/len(aligned)*100:.2f}%)")

# 若存在异常，列出时间范围
if len(anomaly_ratio) > 0:
    print("异常时间段示例：")
    print(anomaly_ratio[['datetime', 'price_uniswap', 'price_binance', 'price_ratio']].head(10))

# ==================== 4. 成交量单位合理性检查 ====================
print("\n" + "="*60)
print("成交量字段检查")
print("="*60)
print("aligned_data 中 volume_eth_uniswap 描述：")
print(aligned['volume_eth_uniswap'].describe())
# 中位数是否在合理 ETH 范围内
med = aligned['volume_eth_uniswap'].median()
if med < 1e-6:
    print("⚠️ 警告：volume_eth_uniswap 中位数极小，可能单位仍是 wei 或过度除 1e18！")
elif med > 1e6:
    print("⚠️ 警告：volume_eth_uniswap 中位数极大，可能仍是原始整数！")
else:
    print("✅ volume_eth_uniswap 单位看似正常。")

# 同样检查 details 中的 volume
if 'volume_eth_uniswap' in details.columns:
    print("\narbitrage_details 中 volume_eth_uniswap 描述：")
    print(details['volume_eth_uniswap'].describe())

# ==================== 5. 成本与利润覆盖 ====================
print("\n" + "="*60)
print("成本阈值与利润覆盖")
print("="*60)
cost_per_eth = 3000 * 0.003  # 与主脚本一致
details['abs_spread'] = details['spread'].abs()
above_cost = details[details['abs_spread'] > cost_per_eth]
print(f"价差超过成本 ({cost_per_eth:.2f} USDT) 的交易比例："
      f"{len(above_cost)/len(details)*100:.2f}%")

# 实际利润为正的交易比例
details_profit_pos = details[details['profit_per_trade'] > 0] if 'profit_per_trade' in details.columns else details
if 'profit_per_trade' in details.columns:
    print(f"单笔利润为正的比例：{len(details_profit_pos)/len(details)*100:.2f}%")

print("\n验证完成。")