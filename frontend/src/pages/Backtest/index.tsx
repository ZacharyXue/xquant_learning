import { useState, useEffect } from 'react'
import {
  Card, Form, Input, Select, Button, Table, Tooltip, Modal, Checkbox,
  Typography, message, Tag, Space,
} from 'antd'
import { PlayCircleOutlined, ExperimentOutlined } from '@ant-design/icons'
import { runBacktest, runOptimize, fetchBacktestHistory, fetchStrategies } from '../../api'
import type { BacktestRun } from '../../types'
import BacktestResultView from './Result'

const { Title, Text } = Typography

const OPT_PARAMS = [
  { key: 'rsi_period', label: 'RSI周期', values: [7, 14, 21] },
  { key: 'rsi_overbought', label: 'RSI超买', values: [60, 65, 70, 75, 80] },
  { key: 'rsi_oversold', label: 'RSI超卖', values: [20, 25, 30, 35, 40] },
  { key: 'rsi_additional', label: 'RSI加仓', values: [0, 50, 100, 150] },
  { key: 'bias_ma_period', label: '均线周期', values: [120, 250] },
  { key: 'bias_upper', label: '乖离上限', values: [0.05, 0.08, 0.10, 0.12, 0.15] },
  { key: 'bias_lower', label: '乖离下限', values: [-0.15, -0.12, -0.10, -0.08, -0.05] },
  { key: 'bias_additional', label: '乖离加仓', values: [0, 50, 100, 150] },
]

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [optLoading, setOptLoading] = useState(false)
  const [history, setHistory] = useState<BacktestRun[]>([])
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [optModalOpen, setOptModalOpen] = useState(false)
  const [optForm] = Form.useForm()

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

  const onOptimize = async () => {
    const vals = await optForm.validateFields().catch(() => null)
    if (!vals) return
    setOptLoading(true)
    try {
      const param_grid: Record<string, number[]> = {}
      for (const p of OPT_PARAMS) {
        if (vals[p.key]) {
          param_grid[p.key] = p.values
        }
      }
      const res = await runOptimize({
        strategy_name: vals.strategy_name,
        stock_code: vals.stock_code,
        start_date: vals.start_date,
        end_date: vals.end_date,
        param_grid,
      })
      if (res.status === 'accepted') {
        message.success(`优化已提交 (run_id=${res.run_id}, ${res.total_combos}组参数)，完成后刷新查看`)
        setOptModalOpen(false)
        setTimeout(loadHistory, 8000)
      }
    } catch {
      message.error('优化提交失败')
    } finally {
      setOptLoading(false)
    }
  }

  if (selectedRun) {
    return <BacktestResultView runId={selectedRun} onBack={() => { setSelectedRun(null); loadHistory() }} />
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
            <Space>
              <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={loading}>
                开始回测
              </Button>
              <Button icon={<ExperimentOutlined />} onClick={() => setOptModalOpen(true)}>
                参数优化
              </Button>
              <Button onClick={loadHistory}>刷新</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="历史回测" style={{ marginTop: 16 }}>
        <Table
          dataSource={history}
          onRow={r => ({
            onClick: () => r.status === 'completed' && setSelectedRun(r.id),
            style: { cursor: r.status === 'completed' ? 'pointer' : 'default' },
          })}
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

      <Modal
        title="参数优化"
        open={optModalOpen}
        onOk={onOptimize}
        onCancel={() => setOptModalOpen(false)}
        confirmLoading={optLoading}
        width={700}
      >
        <Form form={optForm} layout="vertical"
          initialValues={{ stock_code: '510880.SH', start_date: '20220101', end_date: '20241231' }}>
          <Space wrap style={{ width: '100%' }}>
            <Form.Item name="strategy_name" label="策略" rules={[{ required: true }]} style={{ width: 160 }}>
              <Select options={strategies.map(s => ({ label: s, value: s }))} />
            </Form.Item>
            <Form.Item name="stock_code" label="股票代码" rules={[{ required: true }]} style={{ width: 120 }}>
              <Input />
            </Form.Item>
            <Form.Item name="start_date" label="开始" rules={[{ required: true }]} style={{ width: 110 }}>
              <Input />
            </Form.Item>
            <Form.Item name="end_date" label="结束" rules={[{ required: true }]} style={{ width: 110 }}>
              <Input />
            </Form.Item>
          </Space>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>选择优化参数 (至少选2个)</Text>
          {OPT_PARAMS.map(p => (
            <Form.Item key={p.key} name={p.key} valuePropName="checked" style={{ marginBottom: 4 }}>
              <Checkbox>{p.label}: [{p.values.join(', ')}]</Checkbox>
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </div>
  )
}
