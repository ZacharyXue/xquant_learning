import { useState, useEffect } from 'react'
import {
  Card, Row, Col, Statistic, Typography, Spin, Empty, Button, Divider,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { fetchBacktestResult } from '../../api'
import type { BacktestResult } from '../../types'

const { Title, Text } = Typography

interface Props {
  runId: number
  stockCode: string
  strategyName: string
  onBack: () => void
}

export default function BacktestResultView({ runId, stockCode, strategyName, onBack }: Props) {
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

  const fmtPct = (v: number) => `${((v ?? 0) * 100).toFixed(2)}%`
  const fmtMoney = (v: number | undefined | null) => (v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })

  const equityData = (result.equity_curve || []).map((p: any) => ({
    date: p.date?.replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3'),
    策略: p.value,
  }))

  // Merge benchmark equity into same chart data
  const benchCurve = result.benchmark?.equity_curve || []
  equityData.forEach((pt: any, i: number) => {
    if (i < benchCurve.length) {
      pt['固定定投基准'] = benchCurve[i].value
    }
  })

  const bm = result.benchmark

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={onBack} style={{ marginBottom: 16 }}>
        返回
      </Button>

      <Title level={4}>
        {stockCode} &mdash; {strategyName} (第 #{runId} 次回测)
      </Title>

      {result.error_msg && (
        <Card style={{ marginBottom: 16, background: '#fff2f0' }}>
          <Text type="danger">错误: {result.error_msg}</Text>
        </Card>
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="交易次数" value={result.total_trades ?? 0} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="胜率" value={fmtPct(result.win_rate ?? 0)} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="收益率"
              value={fmtPct(result.return_rate ?? 0)}
              valueStyle={{ color: (result.return_rate ?? 0) >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="最终价值" value={`¥${fmtMoney(result.final_value)}`} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="夏普比率" value={(result.sharpe_ratio ?? 0).toFixed(2)} /></Card></Col>
        <Col span={6}><Card><Statistic title="最大回撤" value={fmtPct(result.max_drawdown ?? 0)} /></Card></Col>
        <Col span={6}><Card><Statistic title="年化收益" value={fmtPct(result.annualized_return ?? 0)} /></Card></Col>
        <Col span={6}><Card><Statistic title="累计投入" value={`¥${fmtMoney(result.total_investment)}`} /></Card></Col>
      </Row>

      {bm && (
        <>
          <Divider orientation="left">基准对比 (同期固定金额定投)</Divider>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card><Statistic title="基准收益" value={fmtPct(bm.return_rate)} valueStyle={{ color: '#fa8c16' }} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="基准夏普" value={bm.sharpe_ratio?.toFixed(2)} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="基准最大回撤" value={fmtPct(bm.max_drawdown)} /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="基准最终价值" value={`¥${fmtMoney(bm.final_value)}`} /></Card>
            </Col>
          </Row>
        </>
      )}

      <Card title="权益曲线">
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={equityData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={Math.floor(Math.max(equityData.length / 10, 1))} />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip formatter={(v: any) => `¥${fmtMoney(Number(v))}`} />
            <ReferenceLine y={100000} stroke="#999" strokeDasharray="5 5" label="初始资金" />
            <Legend />
            <Line type="monotone" dataKey="策略" name="策略" stroke="#1677ff" dot={false} strokeWidth={2} />
            {bm && (
              <Line type="monotone" dataKey="固定定投基准" name="固定定投基准" stroke="#fa8c16" dot={false} strokeWidth={2} strokeDasharray="5 5" />
            )}
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {result.buy_signals && result.buy_signals.length > 0 && (
        <Card title={`买入信号 (${result.buy_signals.length})`} style={{ marginTop: 16 }}>
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <th style={{ padding: 8, textAlign: 'left' }}>日期</th>
                  <th style={{ padding: 8, textAlign: 'right' }}>价格</th>
                </tr>
              </thead>
              <tbody>
                {result.buy_signals.slice(-50).reverse().map((s: any, i: number) => (
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
