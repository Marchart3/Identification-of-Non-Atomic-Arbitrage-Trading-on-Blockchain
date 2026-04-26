import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ---------- 如需 ARIMA/GARCH 验证，请确保已安装 statsmodels 和 arch ----------
try:
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.tsa.arima.model import ARIMA
    from arch import arch_model
    STATS_MODELS_AVAILABLE = True
except ImportError:
    STATS_MODELS_AVAILABLE = False
    print("提示：statsmodels 或 arch 未安装，将跳过 ARIMA/GARCH 验证。")
    print("若要启用，请运行: pip install statsmodels arch")

# ==================== 配置参数 ====================
INPUT_FILE = 'aligned_data_clean.csv'
OUTPUT_EVENTS = 'arbitrage_events.csv'
OUTPUT_DETAILS = 'arbitrage_details.csv'
OUTPUT_ANOMALIES = 'arima_anomalies.csv'

COST_PERCENT = 0.003          # 总成本 0.3%（手续费+滑点）
AVG_PRICE_REF = 3000          # 参考均价，计算绝对成本
GROUP_INTERVAL = '5s'         # 同一套利事件内最大交易间隔
ZSCORE_WINDOW = '1h'          # 滚动统计窗口
ZSCORE_THRESHOLD = 3.0        # z-score 异常阈值

# 高级验证开关
ENABLE_ARIMA_GARCH = True     # 是否执行 ARIMA/GARCH 辅助验证
RESAMPLE_FREQ = '1min'        # 重采样频率（用于时间序列建模）
ARIMA_ORDER = (1, 1, 1)       # ARIMA 阶数
TEST_SPLIT = 0.2              # 建模测试集比例

# ==================== 1. 数据加载与预处理 ====================
print("加载数据...")
df = pd.read_csv(INPUT_FILE, parse_dates=['datetime'])
df = df.sort_values('datetime').reset_index(drop=True)

# 计算价差及成本
df['spread'] = df['price_binance'] - df['price_uniswap']
cost_per_eth = AVG_PRICE_REF * COST_PERCENT

# ==================== 2. 启发式规则 ====================
print("应用启发式规则...")

# 2.1 价差阈值
df['over_threshold'] = np.abs(df['spread']) > cost_per_eth

# 2.2 方向一致性检查
def check_direction(row):
    if not row['over_threshold']:
        return False
    if row['spread'] > 0:  # Binance 贵，应在 Uniswap 买入
        return row['direction_uniswap'] == 'buy'
    else:                   # Uniswap 贵，应在 Uniswap 卖出
        return row['direction_uniswap'] == 'sell'

df['direction_ok'] = df.apply(check_direction, axis=1)

# 初步套利候选
df['candidate'] = df['over_threshold'] & df['direction_ok']

# ==================== 3. 统计验证：滚动 z-score ====================
print("计算滚动 z-score...")
df_indexed = df.set_index('datetime').sort_index()
rolling_mean = df_indexed['spread'].rolling(ZSCORE_WINDOW, min_periods=10).mean()
rolling_std = df_indexed['spread'].rolling(ZSCORE_WINDOW, min_periods=10).std()
df_indexed['spread_zscore'] = (df_indexed['spread'] - rolling_mean) / rolling_std

# 强信号：候选且 z-score 超标
df_indexed['strong_signal'] = (df_indexed['candidate'] &
                               (np.abs(df_indexed['spread_zscore']) > ZSCORE_THRESHOLD))
df = df_indexed.reset_index()

# ==================== 4. 套利事件聚合（时间间隔） ====================
print("聚合套利事件...")
arb_candidates = df[df['candidate']].copy()

if len(arb_candidates) == 0:
    print("未发现任何套利机会，退出。")
    pd.DataFrame().to_csv(OUTPUT_EVENTS)
    pd.DataFrame().to_csv(OUTPUT_DETAILS)
    exit()

# 单笔理论利润
arb_candidates['profit'] = (arb_candidates['volume_eth_uniswap'] *
                            (np.abs(arb_candidates['spread']) - cost_per_eth))

# 生成事件ID：间隔超过 GROUP_INTERVAL 视为新事件
arb_candidates = arb_candidates.sort_values('datetime')
time_diff = arb_candidates['datetime'].diff()
new_event = time_diff > pd.Timedelta(GROUP_INTERVAL)
arb_candidates['event_id'] = new_event.cumsum()

# 聚合事件
events = arb_candidates.groupby('event_id').agg(
    start_time=('datetime', 'min'),
    end_time=('datetime', 'max'),
    trade_count=('profit', 'count'),
    total_volume_eth=('volume_eth_uniswap', 'sum'),
    total_profit=('profit', 'sum'),
    avg_spread=('spread', 'mean'),
    direction=('direction_uniswap', lambda x: x.mode()[0] if not x.mode().empty else 'unknown'),
    strong_signal_ratio=('strong_signal', 'mean')
).reset_index()

# 套利方向描述
def label_direction(row):
    if row['avg_spread'] > 0:
        return 'Buy on Uniswap, Sell on Binance'
    else:
        return 'Sell on Uniswap, Buy on Binance'

events['arbitrage_type'] = events.apply(label_direction, axis=1)

# ==================== 5. 高级统计验证（ARIMA/GARCH） ====================
if ENABLE_ARIMA_GARCH and STATS_MODELS_AVAILABLE:
    print("运行 ARIMA/GARCH 建模...")
    try:
        # 重采样为等间隔价差序列
        spread_resampled = df.set_index('datetime')['spread'].resample(RESAMPLE_FREQ).mean().dropna()
        if len(spread_resampled) < 20:
            print("重采样后数据量不足，跳过 ARIMA/GARCH。")
        else:
            split = int(len(spread_resampled) * (1 - TEST_SPLIT))
            train_s = spread_resampled.iloc[:split]
            test_s = spread_resampled.iloc[split:]

            # ARIMA 建模
            d = 1 if adfuller(train_s)[1] > 0.05 else 0
            model = ARIMA(train_s, order=(ARIMA_ORDER[0], d, ARIMA_ORDER[2]))
            fitted = model.fit()
            forecast = fitted.get_forecast(steps=len(test_s))
            pred_mean = forecast.predicted_mean
            pred_ci = forecast.conf_int()
            pred_mean.index = test_s.index
            pred_ci.index = test_s.index

            # 识别异常点（实际价差超出 95% 置信区间）
            anomalies = (test_s > pred_ci.iloc[:, 1]) | (test_s < pred_ci.iloc[:, 0])
            anomaly_dates = anomalies[anomalies].index
            anomaly_data = pd.DataFrame({
                'datetime': anomaly_dates,
                'actual_spread': test_s[anomaly_dates],
                'forecast_spread': pred_mean[anomaly_dates]
            })
            anomaly_data.to_csv(OUTPUT_ANOMALIES, index=False)
            print(f"ARIMA 异常点数量：{len(anomaly_data)}，已保存至 {OUTPUT_ANOMALIES}")

            # GARCH 波动率建模（可选，此处仅输出波动率，不直接用于过滤）
            log_ret = spread_resampled.pct_change().dropna() * 100
            if len(log_ret) > 20:
                train_ret = log_ret.iloc[:split].dropna()
                if len(train_ret) > 10:
                    garch_m = arch_model(train_ret * 100, vol='Garch', p=1, q=1, mean='Zero')
                    garch_fit = garch_m.fit(disp='off')
                    print("GARCH 模型已拟合，波动率预测完成（用于参考）。")
    except Exception as e:
        print(f"ARIMA/GARCH 建模出错，跳过。错误信息：{e}")
else:
    print("跳过 ARIMA/GARCH 验证。")

# ==================== 6. 输出结果 ====================
print("保存结果...")
events.to_csv(OUTPUT_EVENTS, index=False)
detail_cols = ['datetime', 'price_uniswap', 'price_binance', 'spread',
               'volume_eth_uniswap', 'direction_uniswap', 'profit',
               'spread_zscore', 'strong_signal', 'event_id']
arb_candidates[detail_cols].to_csv(OUTPUT_DETAILS, index=False)

print("\n" + "="*60)
print("套利识别汇总")
print("="*60)
print(f"套利事件数：{len(events)}")
print(f"套利交易总笔数：{len(arb_candidates)}")
print(f"预估总利润：{events['total_profit'].sum():.2f} USDT")
print(f"平均单事件利润：{events['total_profit'].mean():.2f} USDT")
strong_events = events[events['strong_signal_ratio'] > 0.5]
print(f"强统计信号事件（z>{ZSCORE_THRESHOLD} 占比 >50%）：{len(strong_events)}")
print(f"\n事件输出：{OUTPUT_EVENTS}")
print(f"明细输出：{OUTPUT_DETAILS}")
if ENABLE_ARIMA_GARCH and STATS_MODELS_AVAILABLE:
    print(f"ARIMA异常点输出：{OUTPUT_ANOMALIES}")