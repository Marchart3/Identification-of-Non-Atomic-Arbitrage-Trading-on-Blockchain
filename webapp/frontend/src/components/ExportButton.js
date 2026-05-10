import React from 'react';

const ExportButton = () => {
  const handleExport = () => {
    window.open('http://localhost:5000/api/export', '_blank');
  };
  return <button onClick={handleExport}>导出 Excel</button>;
};

export default ExportButton;