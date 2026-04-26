#!/usr/bin/env python3
"""
数据收集脚本 - USDT/ETH 交易对（仅2025年12月1日）
- 使用 requests 直接调用 Dune REST API
- 修复 Binance 连接超时问题（支持代理）
"""

import os
import csv
import time
import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ==================== 配置区域 ====================
# Dune Analytics API Key（必需）
DUNE_API_KEY = "zoHPlqdEbSP5Ssadfq555v8QjysePcd9"

# Binance API Key（可选，留空则使用公开端点）
BINANCE_API_KEY = ""
BINANCE_API_SECRET = ""

# 网络代理设置（如果无法直连 Binance 或 Dune API，请配置代理）
# 例如：{"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
PROXY = None   # 请根据实际代理地址修改

# 请求超时时间（秒）
REQUEST_TIMEOUT = 30
# =================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_collection_20251201.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    timestamp: int      # Unix时间戳（毫秒）
    price: float
    volume: float
    direction: str      # 'buy', 'sell', 'unknown'
    trade_id: str
    source: str         # 'binance' 或 'uniswap'
    symbol: str         # 'ETHUSDT'

    def to_dict(self) -> Dict:
        return asdict(self)


class RateLimiter:
    def __init__(self, max_requests_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.requests_made = []

    def wait_if_needed(self):
        now = time.time()
        self.requests_made = [t for t in self.requests_made if now - t < 60]
        if len(self.requests_made) >= self.max_requests:
            oldest = self.requests_made[0]
            wait_time = 60 - (now - oldest) + 0.1
            if wait_time > 0:
                logger.info(f"速率限制: 等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
        self.requests_made.append(now)


class ExponentialBackoffRetry:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    def execute(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                logger.info(f"等待 {delay:.2f} 秒后重试...")
                time.sleep(delay)
        return None


class BinanceDataCollector:
    SYMBOL = "ETHUSDT"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret

        requests_params = {}
        if PROXY:
            requests_params['proxies'] = PROXY
        if REQUEST_TIMEOUT:
            requests_params['timeout'] = REQUEST_TIMEOUT

        client_kwargs = {}
        if requests_params:
            client_kwargs['requests_params'] = requests_params

        try:
            if self.api_key and self.api_secret:
                self.client = Client(api_key=self.api_key, api_secret=self.api_secret, **client_kwargs)
            else:
                self.client = Client("", "", **client_kwargs)
                logger.warning("未配置Binance API密钥，将使用公开端点")
            # 测试连接
            self.client.ping()
            logger.info("Binance 连接测试成功")
        except Exception as e:
            logger.error(f"Binance 连接失败: {e}")
            raise

        self.rate_limiter = RateLimiter(max_requests_per_minute=1200)
        self.retry = ExponentialBackoffRetry(max_retries=3)

    def fetch_historical_trades(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[TradeRecord]:
        trades = []
        current_start = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)

        logger.info(f"开始获取Binance数据: {start_time} 至 {end_time}")

        while current_start < end_timestamp:
            self.rate_limiter.wait_if_needed()

            def _fetch():
                return self.client.get_aggregate_trades(
                    symbol=self.SYMBOL,
                    startTime=current_start,
                    endTime=end_timestamp,
                    limit=limit
                )

            try:
                data = self.retry.execute(_fetch)
                if data is None:
                    break

                if not data:
                    current_start += 3600000
                    continue

                for trade in data:
                    is_buyer_maker = trade['m']
                    direction = 'sell' if is_buyer_maker else 'buy'
                    record = TradeRecord(
                        timestamp=trade['T'],
                        price=float(trade['p']),
                        volume=float(trade['q']),
                        direction=direction,
                        trade_id=str(trade['a']),
                        source='binance',
                        symbol=self.SYMBOL
                    )
                    trades.append(record)

                last_timestamp = trades[-1].timestamp if trades else current_start
                current_start = last_timestamp + 1

                logger.info(f"Binance: 已获取 {len(data)} 条记录，累计 {len(trades)} 条")

                if len(data) < limit:
                    break

            except BinanceAPIException as e:
                logger.error(f"Binance API 错误: {e}")
                current_start += 3600000
            except Exception as e:
                logger.error(f"获取Binance数据失败: {e}")
                current_start += 3600000

        logger.info(f"Binance数据收集完成，共 {len(trades)} 条记录")
        return trades


class UniswapDataCollector:
    """使用 Dune REST API 直接调用，避免库版本问题"""
    POOL_ADDRESS = "0x11b815efB8f581194ae79006d24E0d814B7697F6".lower()
    DUNE_API_URL = "https://api.dune.com/api/v1"

    def __init__(self, api_key: str):
        if not api_key or api_key == "your_dune_api_key_here":
            raise ValueError("请先在脚本开头填写有效的 DUNE_API_KEY")
        self.api_key = api_key
        self.headers = {"X-Dune-Api-Key": self.api_key}
        self.session = requests.Session()
        if PROXY:
            self.session.proxies.update(PROXY)
        self.rate_limiter = RateLimiter(max_requests_per_minute=15)
        self.retry = ExponentialBackoffRetry(max_retries=3)

    def _create_swap_query(self, start_date: str, end_date: str) -> str:
        return f"""
WITH swap_events AS (
    SELECT
        evt_block_time AS block_time,
        evt_tx_hash AS tx_hash,
        amount0,
        amount1
    FROM uniswap_v3_ethereum.Pair_evt_Swap
    WHERE contract_address = 0x11b815efb8f581194ae79006d24e0d814b7697f6
        AND evt_block_time >= TIMESTAMP '2025-12-01'
        AND evt_block_time < TIMESTAMP '2026-12-02'
),
priced_swaps AS (
    SELECT
        block_time,
        tx_hash,
        ABS(amount1) AS volume_eth,
        ABS(amount0 / amount1) AS price,
        CASE WHEN amount1 > 0 THEN 'sell' ELSE 'buy' END AS direction
    FROM swap_events
    WHERE amount0 != 0 AND amount1 != 0
)
SELECT
    TO_UNIXTIME(block_time) * 1000 AS timestamp,
    price,
    volume_eth,
    direction,
    tx_hash AS trade_id
FROM priced_swaps
ORDER BY block_time
        """

    def _execute_query(self, query_sql: str, query_name: str) -> pd.DataFrame:
        """通过 REST API 执行查询并返回 DataFrame"""
        # 1. 创建查询
        create_payload = {
            "name": query_name,
            "query_sql": query_sql,
            "private": False
        }
        create_resp = self.session.post(
            f"{self.DUNE_API_URL}/query",
            headers=self.headers,
            json=create_payload,
            timeout=REQUEST_TIMEOUT
        )
        create_resp.raise_for_status()
        query_id = create_resp.json()["query_id"]

        # 2. 执行查询
        exec_resp = self.session.post(
            f"{self.DUNE_API_URL}/query/{query_id}/execute",
            headers=self.headers,
            json={"performance": "medium"},
            timeout=REQUEST_TIMEOUT
        )
        exec_resp.raise_for_status()
        execution_id = exec_resp.json()["execution_id"]

        # 3. 轮询直到完成
        max_wait = 300
        start = time.time()
        while time.time() - start < max_wait:
            status_resp = self.session.get(
                f"{self.DUNE_API_URL}/execution/{execution_id}/status",
                headers=self.headers,
                timeout=REQUEST_TIMEOUT
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()
            state = status_data["state"]
            if state == "QUERY_STATE_COMPLETED":
                break
            elif state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
                raise Exception(f"查询失败: {status_data}")
            time.sleep(5)
        else:
            raise TimeoutError("查询超时")

        # 4. 获取结果
        result_resp = self.session.get(
            f"{self.DUNE_API_URL}/execution/{execution_id}/results",
            headers=self.headers,
            timeout=REQUEST_TIMEOUT
        )
        result_resp.raise_for_status()
        result_data = result_resp.json()
        rows = result_data["result"]["rows"]
        return pd.DataFrame(rows)

    def fetch_historical_swaps(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TradeRecord]:
        trades = []
        start_date = start_time.strftime('%Y-%m-%d')
        end_date = end_time.strftime('%Y-%m-%d')

        logger.info(f"开始获取Uniswap V3数据: {start_date} 至 {end_date}")
        query_sql = self._create_swap_query(start_date, end_date)
        query_name = f"Uniswap V3 ETH-USDT {start_date}"

        self.rate_limiter.wait_if_needed()

        def _execute():
            return self._execute_query(query_sql, query_name)

        try:
            df = self.retry.execute(_execute)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    record = TradeRecord(
                        timestamp=int(row.get('timestamp', 0)),
                        price=float(row.get('price', 0)),
                        volume=float(row.get('volume_eth', 0)),
                        direction=str(row.get('direction', 'unknown')),
                        trade_id=str(row.get('trade_id', '')),
                        source='uniswap',
                        symbol='ETHUSDT'
                    )
                    trades.append(record)
                logger.info(f"Uniswap: 已获取 {len(df)} 条记录")
            else:
                logger.warning(f"日期 {start_date} 无数据")
        except Exception as e:
            logger.error(f"获取Uniswap数据失败: {e}")

        logger.info(f"Uniswap数据收集完成，共 {len(trades)} 条记录")
        return trades


class DataStorage:
    def __init__(self, output_dir: str = "data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def save_to_csv(self, trades: List[TradeRecord], filename: str):
        if not trades:
            return
        filepath = self.output_dir / filename
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['timestamp', 'price', 'volume', 'direction', 'trade_id', 'source', 'symbol']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for trade in trades:
                writer.writerow(trade.to_dict())
        logger.info(f"数据已保存到 {filepath} ({len(trades)} 条记录)")

    def save_to_parquet(self, trades: List[TradeRecord], filename: str):
        if not trades:
            return
        filepath = self.output_dir / filename
        df = pd.DataFrame([t.to_dict() for t in trades])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.to_parquet(filepath, index=False)
        logger.info(f"数据已保存到 {filepath} ({len(trades)} 条记录)")

    def save_to_sqlite(self, trades: List[TradeRecord], db_name: str = "trades.db"):
        if not trades:
            return
        import sqlite3
        db_path = self.output_dir / db_name
        conn = sqlite3.connect(db_path)
        df = pd.DataFrame([t.to_dict() for t in trades])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset=['trade_id', 'source'])
        df.to_sql('trades', conn, if_exists='append', index=False)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_source ON trades(source)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trade_id ON trades(trade_id)')
        conn.close()
        logger.info(f"数据已保存到数据库 {db_path} ({len(trades)} 条记录)")


def aggregate_minute_data(trades: List[TradeRecord]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame([t.to_dict() for t in trades])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['minute'] = df['datetime'].dt.floor('min')
    aggregated = []
    for source in df['source'].unique():
        source_df = df[df['source'] == source]
        minute_df = source_df.groupby('minute').agg({
            'price': ['first', 'max', 'min', 'last'],
            'volume': 'sum',
            'trade_id': 'count'
        }).reset_index()
        minute_df.columns = ['minute', 'open', 'high', 'low', 'close', 'volume', 'trade_count']
        minute_df['source'] = source
        minute_df['symbol'] = 'ETHUSDT'
        aggregated.append(minute_df)
    if aggregated:
        return pd.concat(aggregated, ignore_index=True)
    return pd.DataFrame()


def main():
    logger.info("=" * 60)
    logger.info("开始执行数据收集任务（仅2025-12-01）")
    logger.info("=" * 60)

    start_time = datetime(2025, 12, 1, 0, 0, 0)
    end_time = datetime(2025, 12, 1, 23, 59, 59)

    logger.info(f"数据收集时间范围: {start_time} 至 {end_time}")

    all_trades = []

    # 1. Binance
    try:
        binance_collector = BinanceDataCollector(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_API_SECRET
        )
        binance_trades = binance_collector.fetch_historical_trades(start_time, end_time)
        all_trades.extend(binance_trades)
    except Exception as e:
        logger.error(f"Binance数据收集失败: {e}")

    # 2. Uniswap
    try:
        uniswap_collector = UniswapDataCollector(api_key=DUNE_API_KEY)
        uniswap_trades = uniswap_collector.fetch_historical_swaps(start_time, end_time)
        all_trades.extend(uniswap_trades)
    except Exception as e:
        logger.error(f"Uniswap数据收集失败: {e}")

    if all_trades:
        storage = DataStorage(output_dir="data_20251201")
        date_str = start_time.strftime('%Y%m%d')
        storage.save_to_csv(all_trades, f"trades_{date_str}.csv")
        storage.save_to_parquet(all_trades, f"trades_{date_str}.parquet")
        storage.save_to_sqlite(all_trades, f"trades_{date_str}.db")

        logger.info("生成分钟级聚合数据...")
        minute_df = aggregate_minute_data(all_trades)
        if not minute_df.empty:
            minute_path = Path("data_20251201") / f"minute_{date_str}.parquet"
            minute_df.to_parquet(minute_path, index=False)
            logger.info(f"分钟级聚合数据已保存到 {minute_path}")
            minute_csv_path = Path("data_20251201") / f"minute_{date_str}.csv"
            minute_df.to_csv(minute_csv_path, index=False)
            logger.info(f"分钟级聚合数据(CSV)已保存到 {minute_csv_path}")

        logger.info("=" * 60)
        logger.info(f"数据收集完成！共收集 {len(all_trades)} 条交易记录")
        logger.info(f"  - Binance: {len([t for t in all_trades if t.source == 'binance'])} 条")
        logger.info(f"  - Uniswap: {len([t for t in all_trades if t.source == 'uniswap'])} 条")
        logger.info("=" * 60)
    else:
        logger.warning("未收集到任何数据")


if __name__ == "__main__":
    main()