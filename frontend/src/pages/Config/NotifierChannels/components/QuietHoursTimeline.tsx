interface QuietHoursTimelineProps {
  start: string
  end: string
}

export default function QuietHoursTimeline({ start, end }: QuietHoursTimelineProps) {
  const startHour = parseInt(start.split(':')[0])
  const endHour = parseInt(end.split(':')[0])
  // 起始小时 > 结束小时表示跨午夜（如 23:00-07:00）
  const isCrossMidnight = startHour > endHour

  // 生成 24 小时时间轴，逐小时判断是否处于静默时段
  const hours = Array.from({ length: 24 }, (_, i) => i)
  const isQuiet = (hour: number) => {
    if (isCrossMidnight) {
      return hour >= startHour || hour < endHour
    }
    return hour >= startHour && hour < endHour
  }

  return (
    <div>
      <div style={{ display: 'flex', height: 24, borderRadius: 4, overflow: 'hidden' }}>
        {hours.map((h) => (
          <div
            key={h}
            style={{
              flex: 1,
              background: isQuiet(h) ? '#ff4d4f' : '#52c41a',
              opacity: isQuiet(h) ? 0.7 : 0.5,
            }}
            title={`${h}:00 - ${h + 1}:00 ${isQuiet(h) ? '（静默）' : '（推送）'}`}
          />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
        <span style={{ color: '#ff4d4f' }}>■</span> 静默时段 &nbsp;
        <span style={{ color: '#52c41a' }}>■</span> 推送时段
      </div>
    </div>
  )
}
