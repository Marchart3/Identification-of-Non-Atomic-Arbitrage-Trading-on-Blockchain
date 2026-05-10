import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DataOverview from './components/DataOverview';
import PriceCharts from './components/PriceCharts';
import ArbitrageTable from './components/ArbitrageTable';
import ConfigPanel from './components/ConfigPanel';
import ExportButton from './components/ExportButton';
import './App.css';

const API_BASE = 'http://localhost:5000/api';

function App() {
  const [overview, setOverview] = useState({});
  const [chartData, setChartData] = useState(null);
  const [events, setEvents] = useState([]);
  const [params, setParams] = useState({ price_threshold: 0.3, time_interval: 5, zscore_threshold: 3.0 });

  const fetchOverview = async () => {
    const res = await axios.get(`${API_BASE}/overview`);
    setOverview(res.data);
  };

  const fetchChart = async () => {
    const res = await axios.get(`${API_BASE}/chart_data`);
    setChartData(res.data);
  };

  const fetchArbitrage = async (p = params) => {
    const res = await axios.post(`${API_BASE}/arbitrage`, p);
    setEvents(res.data.events);
  };

  useEffect(() => {
    fetchOverview();
    fetchChart();
    fetchArbitrage();
  }, []);

  const handleRun = (newParams) => {
    setParams(newParams);
    fetchArbitrage(newParams);
  };

  return (
    <div className="App">
      <h1>非原子套利行为识别系统</h1>
      <DataOverview data={overview} />
      <hr />
      <PriceCharts data={chartData} />
      <hr />
      <ConfigPanel onRun={handleRun} initialParams={params} />
      <hr />
      <ArbitrageTable events={events} />
      <ExportButton />
    </div>
  );
}

export default App;