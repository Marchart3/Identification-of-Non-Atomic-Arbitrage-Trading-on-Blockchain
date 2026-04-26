import requests
import pandas as pd
import time
from datetime import datetime, timedelta

# 配置参数
START_DATE = datetime(2025, 12, 1)
END_DATE = datetime(2025, 12, 31)
UNISWAP_V3_CONTRACT = "0x11b815efB8f581194ae79006d24E0d814B7697F6"
BINANCE_API_KEY = "S5g6QLgs1fvl2KgVENcd2Yq3mvtPKbYwwmyzMBTI524cA1ku5ImfcQigOBosZULa"  # 替换为你的Binance API密钥
DUNE_API_ENDPOINT = "https://api.dune.com/api/v1/query/7337666/results"  # 替换为你的Dune查询ID和API端点
# THE_GRAPH_API_ENDPOINT = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"  # 根据实际情况调整
# ETHERSCAN_API_KEY = "your_etherscan_api_key"  # 替换为你的Etherscan API密钥

# 采样窗口：每分钟一次
SAMPLE_INTERVAL = timedelta(minutes=1)

# 初始化数据列表
uniswap_data = []
binance_data = []

# 辅助函数：指数退避重试
def exponential_backoff_retry(func, max_retries=3):
    retry_delay = 1  # 初始延迟1秒
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数增加延迟
    raise Exception("Max retries exceeded")

# 从Dune Analytics获取数据（示例，实际需根据Dune查询调整）
# def fetch_dune_data(start_timestamp, end_timestamp):
#     params = {
#         "api_key": "zoHPlqdEbSP5Ssadfq555v8QjysePcd9",  # 替换为你的Dune API密钥
#         "start_timestamp": int(start_timestamp.timestamp()),
#         "end_timestamp": int(end_timestamp.timestamp())
#     }

#     def query_dune():
#         response = requests.get(DUNE_API_ENDPOINT, params=params)
#         response.raise_for_status()
#         return response.json()

#     data = exponential_backoff_retry(query_dune)
#     # 假设返回的数据格式为包含'timestamp', 'price', 'volume'等字段的列表
#     # 实际处理需根据Dune返回的实际数据结构调整
#     return data.get('result', [])

# 从The Graph获取Uniswap V3数据（示例，实际需根据The Graph子图调整）
# def fetch_the_graph_data(start_timestamp, end_timestamp):
#     query = """
#     query GetSwaps($startTimestamp: BigInt!, $endTimestamp: BigInt!) {
#         swaps(
#             where: {
#                 timestamp_gte: $startTimestamp,
#                 timestamp_lte: $endTimestamp,
#                 pair: "%s"
#             }
#         ) {
#             timestamp
#             price
#             amountUSD
#             amountToken0
#             amountToken1
#             transaction {
#                 id
#             }
#         }
#     }
#     """ % UNISWAP_V3_CONTRACT

#     variables = {
#         "startTimestamp": int(start_timestamp.timestamp()),
#         "endTimestamp": int(end_timestamp.timestamp())
#     }

#     def query_the_graph():
#         headers = {"Content-Type": "application/json"}
#         response = requests.post(THE_GRAPH_API_ENDPOINT, json={"query": query, "variables": variables}, headers=headers)
#         response.raise_for_status()
#         return response.json()

#     data = exponential_backoff_retry(query_the_graph)
    # 假设返回的数据格式为包含'timestamp', 'price', 'amountUSD'等字段的列表
    # 实际处理需根据The Graph返回的实际数据结构调整
    # swaps = data.get('data', {}).get('swaps', [])
    # return [{
    #     "timestamp": swap['timestamp'],
    #     "price": swap['price'],
    #     "volume": swap['amountToken0'] if swap.get('amountToken0') else swap.get('amountToken1'),  # 根据实际情况调整
    #     "transaction_hash": swap['transaction']['id']
    # } for swap in swaps]

# 从Binance Spot API获取数据
def fetch_binance_data(start_timestamp, end_timestamp):
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    params = {
        "symbol": "ETHUSDT",
        "startTime": int(start_timestamp.timestamp() * 1000),  # Binance API需要毫秒级时间戳
        "endTime": int(end_timestamp.timestamp() * 1000),
        "limit": 1000  # 根据Binance API文档调整
    }

    def query_binance():
        response = requests.get("https://api.binance.com/api/v3/klines", params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    data = exponential_backoff_retry(query_binance)
    # Binance返回的K线数据格式为[timestamp, open, high, low, close, volume, close_time, asset_volume, trades, buy_base, buy_asset, ignore]
    # 这里我们取close作为价格，volume作为交易量
    return [{
        "timestamp": datetime.fromtimestamp(item[0] / 1000),  # 转换为秒级时间戳
        "price": float(item[4]),
        "volume": float(item[5]),
        # Binance API不直接提供交易方向和交易ID，这些信息可能需要从其他接口获取或忽略
    } for item in data]

# 从Etherscan获取特定交易详情（备用）
# def fetch_etherscan_transaction(tx_hash):
#     params = {
#         "module": "proxy",
#         "action": "eth_getTransactionByHash",
#         "txhash": tx_hash,
#         "apikey": ETHERSCAN_API_KEY
#     }

#     def query_etherscan():
#         response = requests.get("https://api.etherscan.io/api", params=params)
#         response.raise_for_status()
#         return response.json()

#     data = exponential_backoff_retry(query_etherscan)
#     # 实际处理需根据Etherscan返回的实际数据结构调整
#     return data.get('result', {})

# 主循环：按分钟采样数据
current_time = START_DATE
while current_time <= END_DATE:
    print(f"Fetching data for {current_time}")

    # 从Dune Analytics获取数据（示例，实际可能不需要或根据情况调整）
    # dune_data = fetch_dune_data(current_time, current_time + SAMPLE_INTERVAL - timedelta(seconds=1))
    # uniswap_data.extend(dune_data)

    # 从The Graph获取Uniswap V3数据
    # the_graph_data = fetch_the_graph_data(current_time, current_time + SAMPLE_INTERVAL - timedelta(seconds=1))
    # uniswap_data.extend(the_graph_data)

    # 从Binance Spot API获取数据
    binance_data_chunk = fetch_binance_data(current_time, current_time + SAMPLE_INTERVAL - timedelta(seconds=1))
    binance_data.extend(binance_data_chunk)

    # 移动到下一个采样点
    current_time += SAMPLE_INTERVAL

    # 遵守速率限制，适当休眠
    time.sleep(1)  # 根据实际API速率限制调整

# 将数据保存为CSV文件
# pd.DataFrame(uniswap_data).to_csv("uniswap_v3_usdt_eth_trades.csv", index=False)
pd.DataFrame(binance_data).to_csv("binance_usdt_eth_trades.csv", index=False)

print("Data collection completed.")
