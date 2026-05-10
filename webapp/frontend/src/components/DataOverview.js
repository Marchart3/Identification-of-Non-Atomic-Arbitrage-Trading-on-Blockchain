import React from 'react';

const DataOverview = ({ data }) => (
  <div className="overview">
    <h2>数据概览</h2>
    <ul>
      <li>交易对: {data.pair}</li>
      <li>数据时间范围: {data.data_start} ~ {data.data_end}</li>
      <li>总记录数: {data.total_records}</li>
      <li>DEX: {data.dex}</li>
      <li>CEX: {data.cex}</li>
    </ul>
  </div>
);

export default DataOverview;