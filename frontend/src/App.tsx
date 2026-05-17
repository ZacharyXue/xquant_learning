import { useState } from 'react'
import { Layout, Tabs, Typography } from 'antd'
import {
  DashboardOutlined, CodeOutlined, HistoryOutlined,
  ExperimentOutlined, SettingOutlined,
} from '@ant-design/icons'
import DashboardPage from './pages/Dashboard'
import StrategyPage from './pages/Strategy'
import TradeHistoryPage from './pages/TradeHistory'
import BacktestPage from './pages/Backtest'
import SettingsPage from './pages/Settings'

const { Header, Content } = Layout
const { Title } = Typography

const tabs = [
  { key: 'dashboard', label: '总览', icon: <DashboardOutlined />, children: <DashboardPage /> },
  { key: 'strategy', label: '策略', icon: <CodeOutlined />, children: <StrategyPage /> },
  { key: 'trade', label: '交易记录', icon: <HistoryOutlined />, children: <TradeHistoryPage /> },
  { key: 'backtest', label: '回测', icon: <ExperimentOutlined />, children: <BacktestPage /> },
  { key: 'settings', label: '设置', icon: <SettingOutlined />, children: <SettingsPage /> },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 24px' }}>
        <Title level={4} style={{ color: '#fff', margin: 0 }}>XTQuant 交易系统</Title>
      </Header>
      <Content style={{ padding: 24 }}>
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={tabs}
          size="large"
        />
      </Content>
    </Layout>
  )
}
