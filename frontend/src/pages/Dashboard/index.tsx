import { useEffect, useState } from 'react'
import { Card, Col, Row, Statistic, Table, Tag, Typography } from 'antd'
import { RiseOutlined, FallOutlined, WalletOutlined, PieChartOutlined } from '@ant-design/icons'
import { fetchDashboard } from '../../api'
import type { DashboardData } from '../../types'

const { Title } = Typography

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const d = await fetchDashboard()
      setData(d)
    } catch {
      // offline
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])

  const positionCols = [
    { title: '代码', dataIndex: 'stock_code', key: 'stock_code' },
    { title: '名称', dataIndex: 'stock_name', key: 'stock_name' },
    { title: '持仓', dataIndex: 'volume', key: 'volume' },
    {
      title: '成本价', dataIndex: 'avg_cost', key: 'avg_cost',
      render: (v: number) => v?.toFixed(4) ?? '-',
    },
    {
      title: '现价', dataIndex: 'current_price', key: 'current_price',
      render: (v: number) => v?.toFixed(4) ?? '-',
    },
    {
      title: '市值', dataIndex: 'market_value', key: 'market_value',
      render: (v: number) => v?.toFixed(2) ?? '-',
    },
    {
      title: '盈亏', dataIndex: 'profit_loss', key: 'profit_loss',
      render: (v: number) => (
        <span style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
          {v?.toFixed(2) ?? '-'}
        </span>
      ),
    },
  ]

  const tradeCols = [
    { title: '时间', dataIndex: 'trade_time', key: 'trade_time', width: 160 },
    { title: '股票', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
    {
      title: '方向', dataIndex: 'side', key: 'side', width: 60,
      render: (v: string) => <Tag color={v === 'buy' ? 'green' : 'red'}>{v === 'buy' ? '买入' : '卖出'}</Tag>,
    },
    { title: '数量', dataIndex: 'volume', key: 'volume', width: 80 },
    {
      title: '金额', dataIndex: 'amount', key: 'amount', width: 100,
      render: (v: number) => v?.toFixed(2) ?? '-',
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag>{v}</Tag>,
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>总览面板</Title>

      <Row gutter={16}>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic title="总资产" value={data?.total_asset ?? 0} precision={2} prefix={<WalletOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic title="可用资金" value={data?.available_cash ?? 0} precision={2} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic title="持仓市值" value={data?.market_value ?? 0} precision={2} prefix={<PieChartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title="累计盈亏"
              value={data?.total_profit_loss ?? 0}
              precision={2}
              prefix={data && data.total_profit_loss >= 0 ? <RiseOutlined /> : <FallOutlined />}
              valueStyle={{ color: data && data.total_profit_loss >= 0 ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="持仓明细" style={{ marginTop: 16 }}>
        <Table
          dataSource={data?.positions ?? []}
          columns={positionCols}
          rowKey="stock_code"
          size="small"
          pagination={false}
        />
      </Card>

      <Card title="最近交易" style={{ marginTop: 16 }}>
        <Table
          dataSource={data?.recent_trades ?? []}
          columns={tradeCols}
          rowKey="id"
          size="small"
          pagination={false}
        />
      </Card>
    </div>
  )
}
