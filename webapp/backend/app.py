import os
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)

# ---------- 加载数据 ----------
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'aligned_data_clean.csv')
df_full = pd.read_csv(DATA_PATH, parse_dates=['datetime'])
df_full['spread'] = df_full['price_binance'] - df_full['price_uniswap']

# ---------- 套利识别核心函数 ----------
def detect_arbitrage(price_threshold_pct=0.3, time_interval_sec=5, zscore_threshold=3.0):
    cost = df_full['price_binance'].mean() * (price_threshold_pct / 100)
    df = df_full.copy()

    df['over_threshold'] = np.abs(df['spread']) > cost
    def check_dir(row):
        if not row['over_threshold']: return False
        if row['spread'] > 0:
            return row['direction_uniswap'] == 'buy'
        else:
            return row['direction_uniswap'] == 'sell'
    df['direction_ok'] = df.apply(check_dir, axis=1)
    df['candidate'] = df['over_threshold'] & df['direction_ok']

    # 滚动 z-score
    df_idx = df.set_index('datetime').sort_index()
    roll_mean = df_idx['spread'].rolling('1h', min_periods=10).mean()
    roll_std = df_idx['spread'].rolling('1h', min_periods=10).std()
    df_idx['zscore'] = (df_idx['spread'] - roll_mean) / roll_std
    df_idx['strong'] = df_idx['candidate'] & (np.abs(df_idx['zscore']) > zscore_threshold)
    df = df_idx.reset_index()

    # 筛选候选
    arb = df[df['candidate']].copy()
    if arb.empty:
        return []

    # 计算利润
    arb['profit'] = arb['volume_eth_uniswap'] * (np.abs(arb['spread']) - cost)

    # 时间聚合
    arb = arb.sort_values('datetime')
    arb['time_diff'] = arb['datetime'].diff()
    arb['event_id'] = (arb['time_diff'] > pd.Timedelta(seconds=time_interval_sec)).cumsum()

    events = arb.groupby('event_id').agg(
        start_time=('datetime', 'min'),
        end_time=('datetime', 'max'),
        trade_count=('profit', 'count'),
        total_volume_eth=('volume_eth_uniswap', 'sum'),
        total_profit=('profit', 'sum'),
        avg_spread=('spread', 'mean'),
        direction=('direction_uniswap', lambda x: x.mode()[0] if not x.mode().empty else 'unknown'),
        strong_signal_ratio=('strong', 'mean')
    ).reset_index()

    # 转换为字典
    event_list = events.to_dict(orient='records')
    for e in event_list:
        e['start_time'] = e['start_time'].isoformat()
        e['end_time'] = e['end_time'].isoformat()
        e['type'] = 'Buy on Uniswap, Sell on Binance' if e['avg_spread'] > 0 else 'Sell on Uniswap, Buy on Binance'
    return event_list

# ---------- API 路由 ----------
@app.route('/api/overview')
def data_overview():
    return jsonify({
        'data_start': df_full['datetime'].min().isoformat(),
        'data_end': df_full['datetime'].max().isoformat(),
        'total_records': len(df_full),
        'pair': 'ETH/USDT',
        'dex': 'Uniswap V3 (Ethereum)',
        'cex': 'Binance'
    })

@app.route('/api/chart_data')
def chart_data():
    # 下采样到1分钟减少前端压力
    df_min = df_full.set_index('datetime').resample('1min').agg({
        'price_uniswap': 'last',
        'price_binance': 'last',
        'spread': 'mean'
    }).dropna().reset_index()
    return jsonify({
        'timestamps': df_min['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%S').tolist(),
        'price_uniswap': df_min['price_uniswap'].round(2).tolist(),
        'price_binance': df_min['price_binance'].round(2).tolist(),
        'spread': df_min['spread'].round(4).tolist()
    })

@app.route('/api/arbitrage', methods=['GET', 'POST'])
def get_arbitrage():
    if request.method == 'POST':
        params = request.json
        threshold = float(params.get('price_threshold', 0.3))
        interval = int(params.get('time_interval', 5))
        zscore = float(params.get('zscore_threshold', 3.0))
        events = detect_arbitrage(threshold, interval, zscore)
        return jsonify({'events': events, 'count': len(events)})
    else:
        # GET 默认参数
        events = detect_arbitrage(0.3, 5, 3.0)
        return jsonify({'events': events, 'count': len(events)})

@app.route('/api/export')
def export_data():
    # 导出当前显示的事件 (实际中可根据请求参数导出)
    events = detect_arbitrage(0.3, 5, 3.0)
    df_export = pd.DataFrame(events)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Arbitrage Events')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='arbitrage_events.xlsx')

if __name__ == '__main__':
    app.run(debug=True, port=5000)