import { useState, useRef, useEffect, type ImgHTMLAttributes } from 'react'

/**
 * 懒加载图片组件
 *
 * 使用 Intersection Observer 仅在图片进入视口时加载，
 * 避免一次性加载几十张图片导致的网络拥塞和渲染卡顿。
 * 配合占位符实现平滑过渡。
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
  const [inView, setInView] = useState(false)
  const imgRef = useRef<HTMLDivElement>(null)

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
      {!loaded && (
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
          🖼️
        </div>
      )}
      {inView && src && (
        <img
          src={src}
          alt={alt || ''}
          loading="lazy"
          onLoad={() => setLoaded(true)}
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
