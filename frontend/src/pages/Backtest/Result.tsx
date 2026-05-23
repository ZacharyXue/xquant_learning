import { useState, useEffect } from 'react'
import {
  Card, Row, Col, Statistic, Typography, Spin, Empty, Button,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { fetchBacktestResult } from '../../api'
import type { BacktestResult } from '../../types'

const { Title, Text } = Typography

interface Props {
  runId: number
  onBack: () => void
}

export default function BacktestResultView({ runId, onBack }: Props) {
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchBacktestResult(runId).then(r => {
      setResult(r)
      setLoading(false)
    })
  }, [runId])

  if (loading) return <Spin style={{ display: 'block', margin: '40px auto' }} />
  if (!result) return <Empty description="结果未找到" />

  const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`
  const fmtMoney = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 })

  const equityData = (result.equity_curve || []).map((p: any) => ({
    date: p.date?.replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3'),
    value: p.value,
  }))

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={onBack} style={{ marginBottom: 16 }}>
        返回
      </Button>

      <Title level={4}>回测结果 #{runId}</Title>

      {result.error_msg && (
        <Card style={{ marginBottom: 16, background: '#fff2f0' }}>
          <Text type="danger">错误: {result.error_msg}</Text>
        </Card>
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card><Statistic title="总交易" value={result.total_trades} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="胜率" value={fmtPct(result.win_rate)} /></Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="收益率"
              value={fmtPct(result.return_rate)}
              valueStyle={{ color: result.return_rate >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="年化收益" value={fmtPct(result.annualized_return)} /></Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="最终价值" value={`¥${fmtMoney(result.final_value)}`} />
          </Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="最大回撤" value={fmtPct(result.max_drawdown)} /></Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="夏普比率" value={result.sharpe_ratio.toFixed(2)} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="卡玛比率" value={result.calmar_ratio.toFixed(2)} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="总投资" value={`¥${fmtMoney(result.total_investment)}`} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="盈利交易" value={result.profitable_trades} /></Card>
        </Col>
      </Row>

      <Card title="权益曲线" style={{ marginBottom: 16 }}>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={equityData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={Math.floor(equityData.length / 10)} />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip formatter={(v: any) => `¥${fmtMoney(Number(v))}`} />
            <ReferenceLine y={100000} stroke="#999" strokeDasharray="5 5" label="初始资金" />
            <Line type="monotone" dataKey="value" stroke="#1677ff" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {result.buy_signals && result.buy_signals.length > 0 && (
        <Card title={`买入信号 (${result.buy_signals.length})`}>
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <th style={{ padding: 8, textAlign: 'left' }}>日期</th>
                  <th style={{ padding: 8, textAlign: 'right' }}>价格</th>
                </tr>
              </thead>
              <tbody>
                {result.buy_signals.map((s: any, i: number) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '4px 8px' }}>{s.date}</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right' }}>{s.price?.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
