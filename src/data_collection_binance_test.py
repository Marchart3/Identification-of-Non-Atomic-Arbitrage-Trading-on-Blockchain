import requests
import pandas as pd
import time
from datetime import datetime

def fetch_trades(symbol, limit=1000):
    """
    从币安获取最近的交易数据
    """
    url = "https://api.binance.com/api/v3/trades"  # 注意：这里用 trades 而不是 historicalTrades
    params = {
        'symbol': symbol,
        'limit': limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None

def main():
    symbol = "ETHUSDT"
    
    print(f"正在获取 {symbol} 的最近交易数据...")
    
    # 获取交易数据（最多 1000 条）
    trades = fetch_trades(symbol, limit=100)
    
    if trades:
        print(f"成功获取 {len(trades)} 条交易数据")
        # 转换为 DataFrame
        df = pd.DataFrame(trades)
        print(df.head())
        
        # 保存到 CSV
        df.to_csv(f"{symbol}_trades.csv", index=False)
        print(f"数据已保存到 {symbol}_trades.csv")
    else:
        print("未能获取交易数据")

if __name__ == "__main__":
    main()
