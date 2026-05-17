import { Card, Row, Col, Table, Statistic, Badge } from 'antd'
import { FundOutlined, DollarOutlined, RiseOutlined, AlertOutlined } from '@ant-design/icons'
import type { BacktestResult } from '../../types'
import PriceChart from '../Chart'

interface Props {
  result: BacktestResult
}

export default function Results({ result }: Props) {
  const { total_trades: trades } = result
  const {
    total_trades,
    total_investment,
    final_value,
    return_rate,
    annualized_return,
    max_drawdown,
    volatility,
    sharpe_ratio,
    calmar_ratio,
    win_rate,
    buy_records,
    strategy,
    stock_code,
    start_time,
    end_time,
  } = result

  const columns = [
    {
      title: '时间',
      dataIndex: 'time',
      key: 'time',
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (v: number) => v.toFixed(3),
    },
    {
      title: '数量',
      dataIndex: 'volume',
      key: 'volume',
    },
    {
      title: '成本',
      dataIndex: 'cost',
      key: 'cost',
      render: (v: number) => v.toFixed(2),
    },
    {
      title: 'RSI',
      dataIndex: 'rsi',
      key: 'rsi',
      render: (v: number | null) => v?.toFixed(2) ?? '-',
    },
    {
      title: '乖离率',
      dataIndex: 'bias',
      key: 'bias',
      render: (v: number | null) => v ? `${(v * 100).toFixed(2)}%` : '-',
    },
  ]

  const statCards = [
    { label: '交易次数', value: total_trades, icon: <FundOutlined /> },
    { label: '总投入', value: total_investment.toFixed(2), icon: <DollarOutlined />, prefix: '¥' },
    { label: '最终价值', value: final_value.toFixed(2), icon: <DollarOutlined />, prefix: '¥' },
    { label: '总收益率', value: return_rate.toFixed(2), suffix: '%', color: return_rate >= 0 ? 'positive' : 'negative', icon: <RiseOutlined /> },
    { label: '年化收益率', value: annualized_return?.toFixed(2) || '-', suffix: '%', color: (annualized_return ?? 0) >= 0 ? 'positive' : 'negative', icon: <RiseOutlined /> },
    { label: '最大回撤', value: max_drawdown ? `${(max_drawdown * 100).toFixed(2)}%` : '-', color: 'negative', icon: <AlertOutlined /> },
    { label: '波动率', value: (volatility * 100).toFixed(2), suffix: '%' },
    { label: '夏普比率', value: sharpe_ratio?.toFixed(4) || '-' },
    { label: '卡玛比率', value: calmar_ratio?.toFixed(4) || '-' },
    { label: '胜率', value: win_rate ? `${(win_rate * 100).toFixed(2)}%` : '-' },
  ]

  return (
    <Card
      title={`回测结果 - ${strategy} ${stock_code} (${start_time} ~ ${end_time})`}
      extra={<Badge text={trades > 0 ? "真实数据" : "无数据"} status={trades > 0 ? "success" : "warning"} />}
    >
      <Row gutter={[16, 16]}>
        {statCards.map((stat, i) => (
          <Col xs={12} sm={8} md={4} key={i}>
            <Statistic
              title={stat.label}
              value={stat.value}
              prefix={stat.prefix}
              suffix={stat.suffix}
              valueStyle={{ color: stat.color === 'positive' ? '#52c41a' : stat.color === 'negative' ? '#ff4d4f' : undefined }}
              prefixIcon={stat.icon}
            />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="收益曲线" size="small">
            <PriceChart prices={result.prices || []} times={result.times || []} buyRecords={buy_records} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="买入记录" size="small">
            <Table
              dataSource={buy_records}
              columns={columns}
              rowKey={(r, i) => i.toString()}
              size="small"
              pagination={{ pageSize: 10 }}
              scroll={{ x: true }}
            />
          </Card>
        </Col>
      </Row>
    </Card>
  )
}