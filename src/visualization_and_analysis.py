import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ==================== 1. 读取对齐数据 ====================
df = pd.read_csv('aligned_data_clean.csv', parse_dates=['datetime'])

# 计算价格差异（绝对差与相对差）
df['price_spread'] = df['price_binance'] - df['price_uniswap']
df['price_spread_pct'] = (df['price_spread'] / df['price_uniswap']) * 100  # 以 Uniswap 价格为基准的百分比

# ==================== 2. 统计量计算 ====================
# 基本信息
print("=" * 60)
print("价格差异统计分析")
print("=" * 60)

# 相关系数
corr, p_value = stats.pearsonr(df['price_uniswap'], df['price_binance'])
print(f"皮尔逊相关系数: {corr:.6f} (p-value: {p_value:.2e})")

spearman_corr, spearman_p = stats.spearmanr(df['price_uniswap'], df['price_binance'])
print(f"斯皮尔曼相关系数: {spearman_corr:.6f} (p-value: {spearman_p:.2e})")

# 价格差异的统计量
spread_mean = df['price_spread'].mean()
spread_std = df['price_spread'].std()
spread_min = df['price_spread'].min()
spread_max = df['price_spread'].max()
print(f"\n价格差异 (Binance - Uniswap):")
print(f"  均值: {spread_mean:.6f} USDT")
print(f"  标准差: {spread_std:.6f} USDT")
print(f"  最小值: {spread_min:.6f} USDT")
print(f"  最大值: {spread_max:.6f} USDT")

# 分位数
quantiles = df['price_spread'].quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
print(f"  分位数:")
for q, val in quantiles.items():
    print(f"    {int(q*100)}%: {val:.6f} USDT")

# 价格水平统计
print(f"\nUniswap 价格: 均值={df['price_uniswap'].mean():.2f}, 标准差={df['price_uniswap'].std():.2f}")
print(f"Binance 价格: 均值={df['price_binance'].mean():.2f}, 标准差={df['price_binance'].std():.2f}")

# ==================== 3. 绘图设置 ====================
sns.set_style("whitegrid")
sns.set_palette("Set2")
plt.rcParams['figure.dpi'] = 120
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10

# 时间范围限制（可选：只显示有数据的时间段）
df = df.set_index('datetime').sort_index()

# ==================== 4. 图表生成 ====================

# ---- 4.1 价格走势对比图 ----
fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# 主图：双价格曲线
axes[0].plot(df.index, df['price_uniswap'], label='Uniswap V3', linewidth=0.8, alpha=0.8)
axes[0].plot(df.index, df['price_binance'], label='Binance', linewidth=0.8, alpha=0.8)
axes[0].set_ylabel('Price (USDT/ETH)')
axes[0].set_title('ETH/USDT Price Comparison: Uniswap V3 vs Binance')
axes[0].legend(loc='upper left')
axes[0].grid(True, linestyle='--', alpha=0.5)

# 附图：价格差异 (spread)
axes[1].plot(df.index, df['price_spread'], color='red', linewidth=0.6, alpha=0.9)
axes[1].axhline(y=0, color='black', linestyle='--', linewidth=0.8)
axes[1].set_ylabel('Price Spread (USDT)')
axes[1].set_xlabel('Time')
axes[1].grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('price_trend_comparison.png', bbox_inches='tight')
plt.show()

# ---- 4.2 价格差异分布图 ----
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 直方图 + KDE
sns.histplot(df['price_spread'], bins=80, kde=True, ax=axes[0], color='steelblue')
axes[0].axvline(x=0, color='red', linestyle='--', linewidth=1)
axes[0].set_title('Distribution of Price Spread (Binance - Uniswap)')
axes[0].set_xlabel('Price Spread (USDT)')
axes[0].set_ylabel('Frequency')

# Q-Q 图检查正态性
stats.probplot(df['price_spread'].dropna(), dist="norm", plot=axes[1])
axes[1].set_title('Q-Q Plot of Price Spread')
axes[1].grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('spread_distribution.png', bbox_inches='tight')
plt.show()

# ---- 4.3 散点图与回归分析 ----
fig, ax = plt.subplots(figsize=(8, 7))
# 采样以提高绘图效率（若数据量 > 100k，随机采样 20000 点）
plot_df = df if len(df) <= 20000 else df.sample(20000, random_state=42)

sns.regplot(data=plot_df, x='price_uniswap', y='price_binance',
            scatter_kws={'alpha':0.3, 's':5},
            line_kws={'color':'red', 'linewidth':1.5},
            ax=ax)

# 添加 y=x 参考线
min_val = min(plot_df['price_uniswap'].min(), plot_df['price_binance'].min())
max_val = max(plot_df['price_uniswap'].max(), plot_df['price_binance'].max())
ax.plot([min_val, max_val], [min_val, max_val], 'k--', linewidth=0.8, label='y = x')

ax.set_xlabel('Uniswap V3 Price (USDT/ETH)')
ax.set_ylabel('Binance Price (USDT/ETH)')
ax.set_title(f'Price Correlation (r = {corr:.4f})')
ax.legend()
ax.grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('price_scatter_regression.png', bbox_inches='tight')
plt.show()

# ---- 4.4 相对差异百分比的箱线图 ----
fig, ax = plt.subplots(figsize=(10, 4))
sns.boxplot(x=df['price_spread_pct'], orient='h', color='lightblue', width=0.5, ax=ax)
ax.set_title('Boxplot of Relative Price Spread (%)')
ax.set_xlabel('Relative Spread (% of Uniswap Price)')
ax.axvline(x=0, color='red', linestyle='--', linewidth=1)
plt.tight_layout()
plt.savefig('relative_spread_boxplot.png', bbox_inches='tight')
plt.show()

# ---- 4.5 随时间变化的绝对价差移动统计 ----
# 计算滚动窗口的均值与标准差（窗口大小可根据数据密度调整，例如 1 小时）
window = '1h'  # 可按数据频率调整，如 '30min', '4h'
df_roll = df[['price_spread']].copy()
df_roll['spread_rolling_mean'] = df_roll['price_spread'].rolling(window).mean()
df_roll['spread_rolling_std'] = df_roll['price_spread'].rolling(window).std()

fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(df_roll.index, df_roll['price_spread'], color='gray', alpha=0.3, linewidth=0.4, label='Spread')
ax.plot(df_roll.index, df_roll['spread_rolling_mean'], color='red', linewidth=1.2, label=f'Rolling Mean ({window})')
ax.fill_between(df_roll.index,
                df_roll['spread_rolling_mean'] - 2*df_roll['spread_rolling_std'],
                df_roll['spread_rolling_mean'] + 2*df_roll['spread_rolling_std'],
                color='red', alpha=0.15, label='±2 Std')
ax.axhline(y=0, color='black', linestyle='--')
ax.set_ylabel('Price Spread (USDT)')
ax.set_title('Price Spread with Rolling Statistics')
ax.legend(loc='upper right')
plt.tight_layout()
plt.savefig('spread_rolling_stats.png', bbox_inches='tight')
plt.show()