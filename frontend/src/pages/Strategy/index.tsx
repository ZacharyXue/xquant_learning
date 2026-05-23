import { useEffect, useState } from 'react'
import {
  Card, Switch, List, Typography, Tag, Descriptions, Spin,
  Button, Modal, Form, InputNumber, Select,
} from 'antd'
import { EditOutlined } from '@ant-design/icons'
import { fetchStrategies, toggleStrategy, updateStrategyConfig } from '../../api'
import type { Strategy } from '../../types'

const { Title, Paragraph } = Typography

const CONFIG_FIELD_META: Record<string, { label: string; min?: number; max?: number; step?: number; type: 'number' | 'select' | 'text'; options?: { label: string; value: any }[] }> = {
  investment_days: { label: '定投日', type: 'select', options: [
    { label: '周一', value: 'Monday' }, { label: '周二', value: 'Tuesday' },
    { label: '周三', value: 'Wednesday' }, { label: '周四', value: 'Thursday' },
    { label: '周五', value: 'Friday' },
  ]},
  base_volume: { label: '基础份数', type: 'number', min: 100, step: 100 },
  lot_size: { label: '每手股数', type: 'number', min: 1 },
  rsi_period: { label: 'RSI周期', type: 'number', min: 5, max: 50 },
  rsi_overbought: { label: 'RSI超买', type: 'number', min: 50, max: 90 },
  rsi_oversold: { label: 'RSI超卖', type: 'number', min: 10, max: 50 },
  rsi_additional: { label: 'RSI加仓', type: 'number', min: 0, max: 500 },
  bias_ma_period: { label: '均线周期', type: 'number', min: 50, max: 500 },
  bias_upper: { label: '乖离上限', type: 'number', min: 0.01, max: 0.50, step: 0.01 },
  bias_lower: { label: '乖离下限', type: 'number', min: -0.50, max: -0.01, step: 0.01 },
  bias_additional: { label: '乖离加仓', type: 'number', min: 0, max: 500 },
  open_change_threshold: { label: '跳空阈值', type: 'number', min: 0.001, max: 0.10, step: 0.001 },
}

export default function StrategyPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(false)
  const [editModal, setEditModal] = useState<{ name: string; config: Record<string, any> } | null>(null)
  const [editForm] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const list = await fetchStrategies()
      setStrategies(list)
    } catch {
      // offline
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleToggle = async (name: string, enabled: boolean) => {
    await toggleStrategy(name, enabled)
    setStrategies(prev =>
      prev.map(s => s.name === name ? { ...s, enabled } : s)
    )
  }

  const openEdit = (s: Strategy) => {
    const config = { ...s.config }
    // Convert investment_days array to select value
    if (Array.isArray(config.investment_days)) {
      config.investment_days = config.investment_days[0] || 'Wednesday'
    }
    editForm.setFieldsValue(config)
    setEditModal({ name: s.name, config: s.config })
  }

  const saveConfig = async () => {
    if (!editModal) return
    const vals = editForm.getFieldsValue()
    // Convert single value back to array
    if (typeof vals.investment_days === 'string') {
      vals.investment_days = [vals.investment_days]
    }
    await updateStrategyConfig(editModal.name, vals)
    setEditModal(null)
    setTimeout(load, 500)
  }

  const renderConfigField = (key: string, _value: any) => {
    const meta = CONFIG_FIELD_META[key]
    if (!meta) {
      return <Form.Item key={key} name={key} label={key}>
        <InputNumber style={{ width: 160 }} />
      </Form.Item>
    }
    if (meta.type === 'select') {
      return <Form.Item key={key} name={key} label={meta.label}>
        <Select style={{ width: 160 }} options={meta.options} />
      </Form.Item>
    }
    return <Form.Item key={key} name={key} label={meta.label}>
      <InputNumber style={{ width: 160 }} min={meta.min} max={meta.max} step={meta.step || 1} />
    </Form.Item>
  }

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>策略管理</Title>

      <Spin spinning={loading}>
        <List
          dataSource={strategies}
          renderItem={s => (
            <Card style={{ marginBottom: 16 }}>
              <Descriptions title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span>{s.display_name}</span>
                  <Tag color={s.enabled ? 'green' : 'default'}>{s.enabled ? '运行中' : '已停止'}</Tag>
                  <Switch
                    checked={s.enabled}
                    onChange={(v) => handleToggle(s.name, v)}
                    checkedChildren="开"
                    unCheckedChildren="关"
                  />
                </div>
              } />
              <Paragraph type="secondary">{s.description}</Paragraph>
              {s.config && Object.keys(s.config).length > 0 && (
                <Descriptions size="small" bordered style={{ marginTop: 8 }}>
                  {Object.entries(s.config).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              )}
              <Button icon={<EditOutlined />} size="small" style={{ marginTop: 8 }}
                onClick={() => openEdit(s)}>
                编辑参数
              </Button>
            </Card>
          )}
          locale={{ emptyText: '暂无可用的策略' }}
        />
      </Spin>

      <Modal
        title="编辑策略参数"
        open={!!editModal}
        onOk={saveConfig}
        onCancel={() => setEditModal(null)}
        width={500}
      >
        <Form form={editForm} labelCol={{ span: 8 }} wrapperCol={{ span: 16 }}>
          {editModal && Object.keys(editModal.config).map(k => renderConfigField(k, editModal.config[k]))}
        </Form>
      </Modal>
    </div>
  )
}
