import React, { useState } from 'react';

const ArbitrageTable = ({ events }) => {
  const [sortField, setSortField] = useState('total_profit');
  const [sortOrder, setSortOrder] = useState('desc');
  const [filter, setFilter] = useState('');

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  let sorted = [...events].sort((a, b) => {
    const aVal = a[sortField] || 0;
    const bVal = b[sortField] || 0;
    return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
  });

  if (filter) {
    sorted = sorted.filter(e => e.type?.includes(filter) || e.start_time?.includes(filter));
  }

  if (events.length === 0) return <p>暂无套利事件</p>;

  return (
    <div>
      <h2>套利机会识别结果</h2>
      <input placeholder="搜索类型或时间" value={filter} onChange={e => setFilter(e.target.value)} />
      <table className="arb-table">
        <thead>
          <tr>
            <th onClick={() => handleSort('start_time')}>开始时间</th>
            <th>结束时间</th>
            <th onClick={() => handleSort('trade_count')}>交易笔数</th>
            <th onClick={() => handleSort('total_volume_eth')}>总成交量(ETH)</th>
            <th onClick={() => handleSort('total_profit')}>预估利润(USDT)</th>
            <th>方向</th>
            <th onClick={() => handleSort('strong_signal_ratio')}>强信号占比</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((e, i) => (
            <tr key={i}>
              <td>{e.start_time}</td>
              <td>{e.end_time}</td>
              <td>{e.trade_count}</td>
              <td>{e.total_volume_eth?.toFixed(4)}</td>
              <td>{e.total_profit?.toFixed(2)}</td>
              <td>{e.type}</td>
              <td>{(e.strong_signal_ratio * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ArbitrageTable;