import { useMemo } from "react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts"
import type { BuyRecord } from "../../types"

interface Props {
  prices: number[]
  times: string[]
  buyRecords: BuyRecord[]
}

export default function PriceChart({ prices, times, buyRecords }: Props) {
  const data = useMemo(() => {
    if (!prices.length || !times.length) {
      return []
    }

    const buyTimes = new Set(buyRecords.map((r) => r.time))

    return prices.map((price, i) => {
      return {
        index: i,
        time: times[i],
        price: price,
        isBuy: buyTimes.has(times[i]),
      }
    })
  }, [prices, times, buyRecords])

  if (!data.length) {
    return <div style={{ textAlign: "center", color: "#999" }}>暂无数据</div>
  }

  // 采样
  const step = Math.max(1, Math.floor(data.length / 100))
  const sampled = data.filter((_, i) => i % step === 0 || data.length - i <= 5)

  // 自定义 dot，只在买入点显示
  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props
    if (payload && payload.isBuy) {
      return <circle key={props.key} cx={cx} cy={cy} r={5} fill="#52c41a" stroke="#fff" strokeWidth={2} />
    }
    return null
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={sampled} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 12 }}
          tickFormatter={(v) => String(v).slice(0, 6)}
          interval="preserveStartEnd"
        />
        <YAxis domain={["auto", "auto"]} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value: any) => [Number(value).toFixed(3), "价格"]}
          labelFormatter={(label: any) => `时间: ${label}`}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="price"
          stroke="#1890ff"
          strokeWidth={1.5}
          dot={CustomDot}
          name="价格"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}