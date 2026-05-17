import { useState, useEffect } from 'react'
import { Layout, Typography, Card, Row, Col, message } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import BacktestForm from './components/BacktestForm'
import Results from './components/Results'
import HistoryList from './components/HistoryList'
import { getBacktestData } from './api'
import type { BacktestResult } from './types'

const { Header, Content } = Layout
const { Title } = Typography

export default function App() {
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedHistory, setSelectedHistory] = useState<string | null>(null)

  useEffect(() => {
    if (selectedHistory) {
      loadHistoryResult(selectedHistory)
    }
  }, [selectedHistory])

  const loadHistoryResult = async (filename: string) => {
    // filename format: strategy_stock.json
    const match = filename.match(/^(.+)_([^_]+)\.json$/)
    if (!match) {
      message.error('无效的文件名格式')
      return
    }
    const [, strategy, stock] = match
    setLoading(true)
    try {
      const data = await getBacktestData(strategy, stock)
      setResult(data)
    } catch (err: any) {
      message.error(err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout className="layout">
      <Header className="header">
        <LineChartOutlined className="logo" />
        <Title level={4} className="title">xtquant 回测系统</Title>
      </Header>
      <Content className="content">
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={8}>
            <Card title="回测参数" className="form-card">
              <BacktestForm onResult={setResult} loading={loading} setLoading={setLoading} />
            </Card>
          </Col>
          <Col xs={24} lg={16}>
            {result ? (
              <Results result={result} />
            ) : (
              <Card className="empty-card">
                <div className="empty-tip">请设置回测参数并运行回测</div>
              </Card>
            )}
          </Col>
        </Row>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col span={24}>
            <HistoryList onSelect={setSelectedHistory} />
          </Col>
        </Row>
      </Content>
    </Layout>
  )
}