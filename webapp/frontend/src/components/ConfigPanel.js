import React, { useState } from 'react';

const ConfigPanel = ({ onRun, initialParams }) => {
  const [threshold, setThreshold] = useState(initialParams.price_threshold);
  const [interval, setInterval] = useState(initialParams.time_interval);
  const [zscore, setZscore] = useState(initialParams.zscore_threshold);

  const handleSubmit = () => {
    onRun({ price_threshold: parseFloat(threshold), time_interval: parseInt(interval), zscore_threshold: parseFloat(zscore) });
  };

  return (
    <div className="config-panel">
      <h2>参数配置</h2>
      <label>价格差异阈值 (%) </label>
      <input type="number" step="0.01" value={threshold} onChange={e => setThreshold(e.target.value)} />
      <label>交易时间间隔 (秒) </label>
      <input type="number" step="1" value={interval} onChange={e => setInterval(e.target.value)} />
      <label>Z-score 阈值 </label>
      <input type="number" step="0.1" value={zscore} onChange={e => setZscore(e.target.value)} />
      <button onClick={handleSubmit}>重新运行识别</button>
    </div>
  );
};

export default ConfigPanel;