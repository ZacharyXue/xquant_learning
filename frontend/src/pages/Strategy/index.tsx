import { useEffect, useState } from 'react'
import { Card, Switch, List, Typography, Tag, Descriptions, Spin } from 'antd'
import { fetchStrategies, toggleStrategy } from '../../api'
import type { Strategy } from '../../types'

const { Title, Text, Paragraph } = Typography

export default function StrategyPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(false)

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
            </Card>
          )}
          locale={{ emptyText: '暂无可用的策略' }}
        />
      </Spin>
    </div>
  )
}
