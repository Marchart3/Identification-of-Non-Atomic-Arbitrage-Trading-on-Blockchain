import React from 'react';
import ReactECharts from 'echarts-for-react';

const PriceCharts = ({ data }) => {
  if (!data) return <div>加载图表...</div>;

  const option1 = {
    title: { text: 'ETH/USDT 价格走势' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['Uniswap', 'Binance'] },
    xAxis: { type: 'category', data: data.timestamps, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: 'Price (USDT)' },
    series: [
      { name: 'Uniswap', type: 'line', data: data.price_uniswap, smooth: true, lineStyle: { width: 1 } },
      { name: 'Binance', type: 'line', data: data.price_binance, smooth: true, lineStyle: { width: 1 } }
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider' }]
  };

  const option2 = {
    title: { text: '价格差异 (Binance - Uniswap)' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.timestamps, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: 'Spread (USDT)' },
    series: [
      { type: 'line', data: data.spread, smooth: false, lineStyle: { width: 1, color: '#ff4d4f' } }
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider' }]
  };

  return (
    <div>
      <ReactECharts option={option1} style={{ height: 400 }} />
      <ReactECharts option={option2} style={{ height: 300 }} />
    </div>
  );
};

export default PriceCharts;