import { useState, useEffect } from 'react'
import {
  Card, Form, Input, Select, Button, Table, Tooltip,
  Typography, message, Tag,
} from 'antd'
import { PlayCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { runBacktest, fetchBacktestHistory, fetchStrategies } from '../../api'
import type { BacktestRun } from '../../types'

const { Title, Text } = Typography

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<BacktestRun[]>([])

  const loadHistory = () => fetchBacktestHistory().then(setHistory)

  useEffect(() => {
    fetchStrategies().then(list => setStrategies(list.map(s => s.name)))
    loadHistory()
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
        message.success(`回测已提交 (run_id=${res.run_id})，稍后刷新查看结果`)
        setTimeout(loadHistory, 5000)
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
        <Form layout="inline" onFinish={onFinish}
          initialValues={{ stock_code: '510880.SH', start_date: '20220101', end_date: '20241231' }}>
          <Form.Item name="strategy_name" label="策略" rules={[{ required: true }]}>
            <Select style={{ width: 160 }} options={strategies.map(s => ({ label: s, value: s }))} />
          </Form.Item>
          <Form.Item name="stock_code" label="股票代码" rules={[{ required: true }]}>
            <Input placeholder="510880.SH" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="start_date" label="开始" rules={[{ required: true }]}
            extra={<Text type="secondary" style={{ fontSize: 11 }}>建议3年以上</Text>}>
            <Input placeholder="20220101" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="end_date" label="结束" rules={[{ required: true }]}>
            <Input placeholder="20241231" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={loading}>
              开始回测
            </Button>
            <Button style={{ marginLeft: 8 }} onClick={loadHistory}>刷新</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="历史回测" style={{ marginTop: 16 }}>
        <Table
          dataSource={history}
          columns={[
            { title: 'ID', dataIndex: 'id', key: 'id', width: 50 },
            { title: '策略', dataIndex: 'strategy_name', key: 'strategy_name' },
            { title: '股票', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
            { title: '开始', dataIndex: 'start_date', key: 'start_date', width: 100 },
            { title: '结束', dataIndex: 'end_date', key: 'end_date', width: 100 },
            {
              title: '状态', dataIndex: 'status', key: 'status', width: 90,
              render: (v: string) => {
                const colors: Record<string, string> = { completed: 'green', running: 'blue', failed: 'red' }
                return <Tag color={colors[v]}>{v}</Tag>
              },
            },
            {
              title: '错误', dataIndex: 'error_msg', key: 'error_msg', width: 200,
              render: (v: string) => v ? (
                <Tooltip title={v}>
                  <Text type="danger" ellipsis style={{ maxWidth: 180 }}>{v}</Text>
                </Tooltip>
              ) : '-',
            },
            { title: '时间', dataIndex: 'started_at', key: 'started_at', width: 160,
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
