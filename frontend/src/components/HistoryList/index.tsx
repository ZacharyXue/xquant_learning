import { useState, useEffect } from 'react'
import { Card, Table, Button, message, Popconfirm } from 'antd'
import { DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { getHistory } from '../../api'
import type { HistoryRecord } from '../../types'

interface Props {
  onSelect: (filename: string) => void
}

export default function HistoryList({ onSelect }: Props) {
  const [records, setRecords] = useState<HistoryRecord[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    setLoading(true)
    try {
      const data = await getHistory()
      // 根据文件名解析出strategy和stock_code
      const parsed = data.map((r: any) => {
        const match = r.filename?.match(/^(.+)_([^_]+)\.json$/)
        return {
          ...r,
          strategy: match?.[1] || '',
          stock_code: match?.[2] || '',
        }
      })
      setRecords(parsed)
    } catch (err) {
      console.error('加载历史记录失败', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (filename: string) => {
    message.success(`删除 ${filename}`)
    loadHistory()
  }

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
    },
    {
      title: '策略',
      dataIndex: 'strategy',
      key: 'strategy',
    },
    {
      title: '股票代码',
      dataIndex: 'stock_code',
      key: 'stock_code',
    },
    {
      title: '交易次数',
      dataIndex: 'total_trades',
      key: 'total_trades',
    },
    {
      title: '收益率',
      dataIndex: 'return_rate',
      key: 'return_rate',
      render: (v: number) => `${v?.toFixed(2) || 0}%`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: HistoryRecord) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => onSelect(record.filename)}
        >
          查看
        </Button>
      ),
    },
  ]

  return (
    <Card
      title="历史回测记录"
      extra={
        <Button type="link" size="small" onClick={loadHistory}>
          刷新
        </Button>
      }
    >
      {records.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#999', padding: 24 }}>
          暂无历史记录
        </div>
      ) : (
        <Table
          dataSource={records}
          columns={columns}
          rowKey="filename"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: true }}
        />
      )}
    </Card>
  )
}