import { useEffect, useState } from 'react'
import {
  Card, Form, InputNumber, Select, Button, Typography,
  message, Divider, Switch, Space, Descriptions, Spin,
} from 'antd'
import {
  fetchFeeConfig, updateFeeConfig,
  fetchSlippageConfig, updateSlippageConfig,
  fetchTradingHours, fetchTradeMode, updateTradeMode,
} from '../../api'

const { Title } = Typography

export default function SettingsPage() {
  const [feeForm] = Form.useForm()
  const [slipForm] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [tradeMode, setTradeMode] = useState('sim')
  const [tradingHours, setTradingHours] = useState<any>({})

  const load = async () => {
    setLoading(true)
    try {
      const fee = await fetchFeeConfig()
      const slip = await fetchSlippageConfig()
      const hours = await fetchTradingHours()
      const mode = await fetchTradeMode()

      feeForm.setFieldsValue(fee)
      slipForm.setFieldsValue(slip)
      setTradingHours(hours)
      setTradeMode(mode)
    } catch {
      // offline
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const saveFee = async () => {
    const vals = feeForm.getFieldsValue()
    await updateFeeConfig(vals)
    message.success('费率配置已保存')
  }

  const saveSlippage = async () => {
    const vals = slipForm.getFieldsValue()
    await updateSlippageConfig(vals)
    message.success('滑点配置已保存')
  }

  const handleModeChange = async (checked: boolean) => {
    const mode = checked ? 'real' : 'sim'
    await updateTradeMode(mode)
    setTradeMode(mode)
    message.success(`已切换为 ${mode === 'real' ? '真实' : '模拟'} 交易模式`)
  }

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>系统设置</Title>

      <Spin spinning={loading}>
        <Card title="交易模式" style={{ marginBottom: 16 }}>
          <Space>
            <Switch
              checked={tradeMode === 'real'}
              onChange={handleModeChange}
              checkedChildren="真实交易"
              unCheckedChildren="模拟交易"
            />
            <span>{tradeMode === 'real' ? '真实交易 (连接QMT)' : '模拟交易 (虚拟账户)'}</span>
          </Space>
        </Card>

        <Card title="费率配置" style={{ marginBottom: 16 }}>
          <Form form={feeForm} layout="inline">
            <Form.Item name="commission_rate" label="佣金率">
              <InputNumber step={0.00001} precision={5} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="stamp_tax_rate" label="印花税率">
              <InputNumber step={0.0001} precision={4} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="transfer_fee_rate" label="过户费率">
              <InputNumber step={0.00001} precision={5} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="min_commission" label="最低佣金">
              <InputNumber step={0.1} precision={1} style={{ width: 100 }} prefix="¥" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" onClick={saveFee}>保存费率</Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="滑点配置" style={{ marginBottom: 16 }}>
          <Form form={slipForm} layout="inline">
            <Form.Item name="rate" label="滑点率">
              <InputNumber step={0.001} precision={3} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="mode" label="模式">
              <Select style={{ width: 140 }} options={[
                { label: '固定比例', value: 'fixed_rate' },
                { label: '基于盘口', value: 'spread_based' },
              ]} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" onClick={saveSlippage}>保存滑点</Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="交易时段">
          <Descriptions bordered size="small">
            <Descriptions.Item label="连续竞价开始">{tradingHours.start}</Descriptions.Item>
            <Descriptions.Item label="连续竞价结束">{tradingHours.end}</Descriptions.Item>
            <Descriptions.Item label="收盘撤单">{tradingHours.cancel_unfilled_at}</Descriptions.Item>
          </Descriptions>
        </Card>
      </Spin>
    </div>
  )
}
