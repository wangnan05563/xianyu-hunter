import { useState, useRef, type ReactNode } from 'react'

interface PullToRefreshProps {
  readonly onRefresh: () => Promise<void>
  readonly children: ReactNode
}

// 下拉刷新包装器：监听 touch 事件，下拉超过阈值触发刷新
export default function PullToRefresh({ onRefresh, children }: PullToRefreshProps) {
  const [pullDistance, setPullDistance] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const startY = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const THRESHOLD = 60 // 下拉 60px 触发刷新

  const handleTouchStart = (e: React.TouchEvent) => {
    // S6582：用可选链替代手动 null 检查
    if (containerRef.current?.scrollTop === 0) {
      startY.current = e.touches[0].clientY
    } else {
      startY.current = 0
    }
  }

  const handleTouchMove = (e: React.TouchEvent) => {
    if (startY.current === 0 || refreshing) return
    const distance = e.touches[0].clientY - startY.current
    // 仅下拉（正距离）且未超过阈值 1.5 倍
    if (distance > 0 && distance < THRESHOLD * 1.5) {
      setPullDistance(distance)
    }
  }

  const handleTouchEnd = async () => {
    if (pullDistance >= THRESHOLD && !refreshing) {
      setRefreshing(true)
      try {
        await onRefresh()
      } finally {
        setRefreshing(false)
      }
    }
    setPullDistance(0)
    startY.current = 0
  }

  return (
    <div
      ref={containerRef}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{
        transform: `translateY(${pullDistance}px)`,
        transition: pullDistance === 0 ? 'transform 0.2s ease' : 'none',
      }}
    >
      {/* 下拉指示器 */}
      {(pullDistance > 0 || refreshing) && (
        <div
          style={{
            textAlign: 'center',
            height: pullDistance,
            opacity: pullDistance / THRESHOLD,
            fontSize: 13,
            color: '#999',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            paddingBottom: 8,
          }}
        >
          {refreshing ? '正在刷新...' : '下拉刷新'}
        </div>
      )}
      {children}
    </div>
  )
}
