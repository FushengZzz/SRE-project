import React from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import App from './App';
import './styles.css';

dayjs.locale('zh-cn');

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1d4ed8',
          colorInfo: '#2563eb',
          colorSuccess: '#16a34a',
          colorWarning: '#d97706',
          colorError: '#dc2626',
          colorText: '#1f2937',
          colorTextSecondary: '#64748b',
          colorBorder: '#e2e8f0',
          colorBgLayout: '#f5f7fa',
          borderRadius: 10,
          controlHeight: 36,
          fontSize: 14,
          fontFamily:
            "'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, -apple-system, sans-serif",
        },
        components: {
          Table: {
            headerBg: '#f8fafc',
            headerColor: '#475569',
            rowHoverBg: '#f8fbff',
            borderColor: '#eef2f7',
            headerSplitColor: '#eef2f7',
          },
          Tabs: {
            itemSelectedColor: '#1d4ed8',
            inkBarColor: '#1d4ed8',
            titleFontSize: 15,
          },
          Button: {
            primaryShadow: 'none',
          },
        },
      }}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
);
