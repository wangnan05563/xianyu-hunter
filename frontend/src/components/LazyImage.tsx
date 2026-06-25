import { useState, useRef, useEffect, type ImgHTMLAttributes } from 'react'

// 阿里云占位图特征标记：2x2 或 1x1 透明 PNG
// 闲鱼搜索 API 对部分商品只返回这类占位图，前端需检测并显示占位符
const PLACEHOLDER_MARKS = ['tps-2-2', '2-2.png', '1x1.png']

function isPlaceholderUrl(url: string): boolean {
  return PLACEHOLDER_MARKS.some(m => url.includes(m))
}

/**
 * 懒加载图片组件
 *
 * 使用 Intersection Observer 仅在图片进入视口时加载，
 * 避免一次性加载几十张图片导致的网络拥塞和渲染卡顿。
 * 配合占位符实现平滑过渡。
 *
 * 特殊处理：
 * - 检测阿里云2x2占位图URL，直接显示占位符而非加载透明像素
 * - src 变化时重置加载状态，避免旧图片状态影响新图片
 * - onError 处理：图片加载失败时显示错误占位符，不再无限等待
 */
export default function LazyImage({
  src,
  alt,
  width,
  height,
  style,
  ...rest
}: ImgHTMLAttributes<HTMLImageElement> & { width?: number | string; height?: number | string }) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const [inView, setInView] = useState(false)
  const imgRef = useRef<HTMLDivElement>(null)

  // 检测占位图URL：如果是2x2占位图，直接显示占位符
  const isPlaceholder = src ? isPlaceholderUrl(src) : false

  // src 变化时重置加载状态：实时搜索返回新数据时，旧图片的 loaded/error
  // 状态不应影响新图片，否则会出现新图片 opacity:0 永远不显示的问题
  useEffect(() => {
    setLoaded(false)
    setError(false)
  }, [src])

  useEffect(() => {
    const el = imgRef.current
    if (!el) return
    // 已有原生 loading="lazy" 支持的浏览器直接标记可见
    if ('loading' in HTMLImageElement.prototype) {
      setInView(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { rootMargin: '100px' } // 提前 100px 开始加载，用户滚动时无感知
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // 占位图直接显示占位符，不加载2x2透明图
  if (isPlaceholder) {
    return (
      <div
        ref={imgRef}
        style={{
          width,
          height,
          position: 'relative',
          overflow: 'hidden',
          background: '#f5f5f5',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#bfbfbf',
          fontSize: 20,
          ...style,
        }}
      >
        🖼️
      </div>
    )
  }

  return (
    <div
      ref={imgRef}
      style={{
        width,
        height,
        position: 'relative',
        overflow: 'hidden',
        background: '#f5f5f5',
        ...style,
      }}
    >
      {(!loaded || error) && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#bfbfbf',
            fontSize: 20,
          }}
        >
          {error ? '⚠️' : '🖼️'}
        </div>
      )}
      {inView && src && !error && (
        <img
          src={src}
          alt={alt || ''}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            opacity: loaded ? 1 : 0,
            transition: 'opacity 0.3s ease',
          }}
          {...rest}
        />
      )}
    </div>
  )
}
