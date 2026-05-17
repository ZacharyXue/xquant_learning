import { useState, useEffect } from 'react'
import { Form, Select, Input, Button, message } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import { getStrategies, getDurations, runBacktest } from '../../api'
import type { Strategy, Duration, BacktestResult } from '../../types'

interface Props {
  onResult: (result: BacktestResult) => void
  loading: boolean
  setLoading: (loading: boolean) => void
}

export default function BacktestForm({ onResult, loading, setLoading }: Props) {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [durations, setDurations] = useState<Duration[]>([])
  const [form] = Form.useForm()

  useEffect(() => {
    loadOptions()
  }, [])

  const loadOptions = async () => {
    try {
      const [strategyList, durationList] = await Promise.all([
        getStrategies(),
        getDurations(),
      ])
      setStrategies(strategyList)
      setDurations(durationList)
    } catch (err) {
      message.error('加载选项失败')
    }
  }

  const handleSubmit = async (values: any) => {
    setLoading(true)
    try {
      const res = await runBacktest({
        strategy: values.strategy,
        stock_code: String(values.stock_code),
        duration: values.duration,
      })
      if (res.success && res.data) {
        onResult(res.data)
        message.success('回测完成')
      } else {
        message.error(res.error || '回测失败')
      }
    } catch (err: any) {
      message.error(err.message || '回测失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      initialValues={{
        strategy: 'bonus_stocks',
        stock_code: '515650.SH',
        duration: '1y',
      }}
    >
      <Form.Item label="策略" name="strategy" rules={[{ required: true }]}>
        <Select placeholder="选择策略">
          {strategies.map(s => (
            <Select.Option key={s.id} value={s.id}>
              {s.name}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      <Form.Item
        label="股票代码"
        name="stock_code"
        rules={[{ required: true, message: '请输入股票代码' }]}
      >
        <Input placeholder="如: 515650.SH" />
      </Form.Item>

      <Form.Item label="回测时长" name="duration" rules={[{ required: true }]}>
        <Select placeholder="选择回测时长">
          {durations.map(d => (
            <Select.Option key={d.id} value={d.id}>
              {d.name}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          icon={<PlayCircleOutlined />}
          loading={loading}
          block
        >
          运行回测
        </Button>
      </Form.Item>
    </Form>
  )
}