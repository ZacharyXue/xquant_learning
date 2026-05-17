import { useState, useEffect } from 'react'
import {
  Card, Form, Input, Select, Button, Statistic, Row, Col, Table,
  Typography, message, Spin,
} from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { runBacktest, fetchBacktestHistory, fetchBacktestResult, fetchStrategies } from '../../api'
import type { BacktestResult, BacktestRun } from '../../types'

const { Title, Text } = Typography

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [history, setHistory] = useState<BacktestRun[]>([])

  useEffect(() => {
    fetchStrategies().then(list => setStrategies(list.map(s => s.name)))
    fetchBacktestHistory().then(setHistory)
  }, [])

  const onFinish = async (values: any) => {
    setLoading(true)
    try {
      const res = await runBacktest({
        strategy_name: values.strategy_name,
        stock_code: values.stock_code,
        start_date: values.start_date,
        end_date: values.end_date,
      })
      if (res.status === 'accepted') {
        message.success('回测任务已提交')
      }
    } catch {
      message.error('回测失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>回测中心</Title>

      <Card title="运行回测">
        <Form layout="inline" onFinish={onFinish}>
          <Form.Item name="strategy_name" label="策略" rules={[{ required: true }]}>
            <Select style={{ width: 160 }} options={strategies.map(s => ({ label: s, value: s }))} />
          </Form.Item>
          <Form.Item name="stock_code" label="股票代码" rules={[{ required: true }]}>
            <Input placeholder="000001.SZ" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="start_date" label="开始" rules={[{ required: true }]}>
            <Input placeholder="20240101" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="end_date" label="结束" rules={[{ required: true }]}>
            <Input placeholder="20241231" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={loading}>
              开始回测
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {result && (
        <Card title="回测结果" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={4}><Statistic title="交易次数" value={result.total_trades} /></Col>
            <Col span={4}><Statistic title="胜率" value={result.win_rate} precision={2} suffix="%" /></Col>
            <Col span={4}><Statistic title="收益率" value={result.return_rate * 100} precision={2} suffix="%" /></Col>
            <Col span={4}><Statistic title="年化收益" value={result.annualized_return * 100} precision={2} suffix="%" /></Col>
            <Col span={4}><Statistic title="最大回撤" value={result.max_drawdown * 100} precision={2} suffix="%" /></Col>
            <Col span={4}><Statistic title="夏普比率" value={result.sharpe_ratio} precision={2} /></Col>
          </Row>

          {result.equity_curve?.length > 0 && (
            <ResponsiveContainer width="100%" height={300} style={{ marginTop: 24 }}>
              <LineChart data={result.equity_curve}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#1677ff" name="权益曲线" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      )}

      <Card title="历史回测" style={{ marginTop: 16 }}>
        <Table
          dataSource={history}
          columns={[
            { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
            { title: '策略', dataIndex: 'strategy_name', key: 'strategy_name' },
            { title: '股票', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
            { title: '开始', dataIndex: 'start_date', key: 'start_date', width: 100 },
            { title: '结束', dataIndex: 'end_date', key: 'end_date', width: 100 },
            {
              title: '状态', dataIndex: 'status', key: 'status', width: 80,
              render: (v: string) => {
                const colors: Record<string, string> = { completed: 'green', running: 'blue', failed: 'red' }
                return <span style={{ color: colors[v] ?? '#666' }}>{v}</span>
              },
            },
            { title: '时间', dataIndex: 'started_at', key: 'started_at', width: 170,
              render: (v: string) => v?.replace('T', ' ').substring(0, 19) ?? '-' },
          ]}
          rowKey="id"
          size="small"
          pagination={false}
        />
      </Card>
    </div>
  )
}
