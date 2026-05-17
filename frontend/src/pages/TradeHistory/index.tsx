import { useEffect, useState } from 'react'
import { Card, Table, Tag, Select, Space, Typography, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { fetchTrades } from '../../api'
import type { TradeRecord } from '../../types'

const { Title } = Typography

export default function TradeHistoryPage() {
  const [trades, setTrades] = useState<TradeRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [filterSide, setFilterSide] = useState<string | undefined>()
  const [filterStatus, setFilterStatus] = useState<string | undefined>()

  const load = async (p: number) => {
    setLoading(true)
    try {
      const res = await fetchTrades({
        side: filterSide || undefined,
        status: filterStatus || undefined,
        page: p,
        page_size: 20,
      })
      setTrades(res.items)
      setTotal(res.total)
    } catch {
      // offline
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(page)
  }, [page, filterSide, filterStatus])

  const cols = [
    { title: '时间', dataIndex: 'trade_time', key: 'trade_time', width: 170,
      render: (v: string) => v?.replace('T', ' ').substring(0, 19) ?? '-' },
    { title: '股票', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
    {
      title: '方向', dataIndex: 'side', key: 'side', width: 70,
      render: (v: string) => <Tag color={v === 'buy' ? 'green' : 'red'}>{v === 'buy' ? '买入' : '卖出'}</Tag>,
    },
    { title: '数量', dataIndex: 'volume', key: 'volume', width: 80 },
    {
      title: '委托价', dataIndex: 'order_price', key: 'order_price', width: 90,
      render: (v: number) => v?.toFixed(4) ?? '市价',
    },
    {
      title: '成交价', dataIndex: 'filled_price', key: 'filled_price', width: 90,
      render: (v: number) => v?.toFixed(4) ?? '-',
    },
    {
      title: '佣金', dataIndex: 'commission', key: 'commission', width: 80,
      render: (v: number) => v?.toFixed(2) ?? '-',
    },
    {
      title: '印花税', dataIndex: 'stamp_tax', key: 'stamp_tax', width: 80,
      render: (v: number) => v?.toFixed(2) ?? '-',
    },
    {
      title: '滑点', dataIndex: 'slippage', key: 'slippage', width: 80,
      render: (v: number) => v?.toFixed(2) ?? '-',
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => {
        const colors: Record<string, string> = { filled: 'green', pending: 'blue', cancelled: 'orange', rejected: 'red' }
        return <Tag color={colors[v] ?? 'default'}>{v}</Tag>
      },
    },
    {
      title: '模式', dataIndex: 'trade_mode', key: 'trade_mode', width: 70,
      render: (v: string) => <Tag>{v}</Tag>,
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>交易记录</Title>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="方向" allowClear style={{ width: 100 }}
            value={filterSide} onChange={setFilterSide}
            options={[{ label: '买入', value: 'buy' }, { label: '卖出', value: 'sell' }]}
          />
          <Select
            placeholder="状态" allowClear style={{ width: 120 }}
            value={filterStatus} onChange={setFilterStatus}
            options={[
              { label: '已成交', value: 'filled' },
              { label: '委托中', value: 'pending' },
              { label: '已撤单', value: 'cancelled' },
            ]}
          />
        </Space>

        <Table
          dataSource={trades}
          columns={cols}
          rowKey="id"
          size="small"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: setPage,
            showTotal: (t: number) => `共 ${t} 条`,
          }}
        />
      </Card>
    </div>
  )
}
