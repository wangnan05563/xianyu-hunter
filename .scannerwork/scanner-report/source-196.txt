import {
  useEffect, useRef, forwardRef, useImperativeHandle, type CSSProperties,
} from 'react'
// 使用 echarts/core 按需导入，仅注册项目实际使用的图表类型和组件
// 相比全量导入 echarts，可显著降低 bundle 体积（从 ~1000kB 降至 ~300kB）
import * as echarts from 'echarts/core'
import { BarChart, LineChart, HeatmapChart, RadarChart, PieChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  VisualMapComponent,
  RadarComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type {
  EChartsType,
  EChartsCoreOption,
  EChartsInitOpts,
  SetOptionOpts,
} from 'echarts/core'

// 一次性注册所有项目用到的图表与组件，后续 echarts.init 只会包含这些能力
echarts.use([
  BarChart, LineChart, HeatmapChart, RadarChart, PieChart,
  TooltipComponent, GridComponent, LegendComponent,
  MarkLineComponent, VisualMapComponent, RadarComponent,
  CanvasRenderer,
])

// option 类型与 echarts-for-react 保持兼容
// echarts-for-react 将 EChartsOption 定义为 any，这里使用 EChartsCoreOption 保持类型安全
// 允许 null 是因为现有调用方中部分 option 构造函数可能返回 null（外层有条件渲染保护）
export type EChartOption = EChartsCoreOption

export interface EChartProps {
  /** echarts 配置项 */
  option: EChartOption | null
  /** 容器行内样式，默认高度 300 */
  style?: CSSProperties
  /** 容器自定义类名 */
  className?: string
  /** setOption 的 notMerge 参数，默认 false */
  notMerge?: boolean
  /** setOption 的 replaceMerge 参数 */
  replaceMerge?: string | string[]
  /** setOption 的 lazyUpdate 参数，默认 false */
  lazyUpdate?: boolean
  /** 是否显示 loading 遮罩，默认 false */
  showLoading?: boolean
  /** loading 遮罩配置 */
  loadingOption?: EChartsCoreOption
  /** echarts 主题名称或主题对象 */
  theme?: string | EChartsCoreOption
  /** echarts.init 的初始化参数 */
  opts?: EChartsInitOpts
  /** 实例就绪后回调 */
  onChartReady?: (instance: EChartsType) => void
  /** 事件绑定映射，key 为事件名，value 为处理函数 */
  onEvents?: Record<string, (params: unknown, instance: EChartsType) => void>
  /** 容器尺寸变化时是否自动 resize，默认 true */
  autoResize?: boolean
}

/**
 * 暴露给父组件的命令式 API，与 echarts-for-react 的 ref 形态保持一致，
 * 便于通过 ref.current.getEchartsInstance() 获取底层 echarts 实例。
 */
export interface EChartRef {
  getEchartsInstance: () => EChartsType | undefined
  ele: HTMLDivElement | null
}

const EChart = forwardRef<EChartRef, EChartProps>(function EChart(props, ref) {
  const {
    option, style, className, notMerge = false, replaceMerge, lazyUpdate = false,
    showLoading = false, loadingOption, theme, opts, onChartReady, onEvents,
    autoResize = true,
  } = props

  const containerRef = useRef<HTMLDivElement | null>(null)
  const instanceRef = useRef<EChartsType | null>(null)
  // 保存当前已绑定的事件处理函数引用，便于更新时解绑
  const eventsRef = useRef<Record<string, (param: unknown) => void>>({})
  // 保存最新的 onEvents 引用，供事件回调使用，避免闭包过期
  const onEventsRef = useRef(onEvents)
  onEventsRef.current = onEvents

  useImperativeHandle(ref, () => ({
    getEchartsInstance: () => instanceRef.current ?? undefined,
    ele: containerRef.current,
  }), [])

  // 初始化与销毁 echarts 实例
  // theme/opts 变化时需要重建实例（与 echarts-for-react 行为一致）
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const instance = echarts.init(el, theme, opts)
    instanceRef.current = instance

    if (onChartReady) onChartReady(instance)

    // 使用原生 ResizeObserver 监听容器尺寸变化，替代 echarts-for-react 的 size-sensor 依赖
    let resizeObserver: ResizeObserver | null = null
    if (autoResize) {
      resizeObserver = new ResizeObserver(() => {
        instance.resize()
      })
      resizeObserver.observe(el)
    }

    return () => {
      if (resizeObserver) resizeObserver.disconnect()
      Object.entries(eventsRef.current).forEach(([eventName, handler]) => {
        instance.off(eventName, handler)
      })
      eventsRef.current = {}
      echarts.dispose(el)
      instanceRef.current = null
    }
    // theme/opts 为对象时每次渲染引用不同，用 JSON.stringify 稳定化以避免无谓重建
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(theme), JSON.stringify(opts)])

  // option 或相关参数变化时更新图表
  useEffect(() => {
    const instance = instanceRef.current
    if (!instance || !option) return

    const setOptionOpts: SetOptionOpts = {
      notMerge,
      lazyUpdate,
    }
    // replaceMerge 未传时不写入，保持 echarts 默认行为
    if (replaceMerge !== undefined) {
      // echarts 内部类型为 ComponentMainType 联合，这里做受控断言
      setOptionOpts.replaceMerge = replaceMerge as SetOptionOpts['replaceMerge']
    }
    instance.setOption(option, setOptionOpts)

    if (showLoading) {
      instance.showLoading(loadingOption)
    } else {
      instance.hideLoading()
    }
  }, [option, notMerge, replaceMerge, lazyUpdate, showLoading, loadingOption])

  // onEvents 变化时重新绑定事件
  useEffect(() => {
    const instance = instanceRef.current
    if (!instance) return

    // 先解绑旧事件
    Object.entries(eventsRef.current).forEach(([eventName, handler]) => {
      instance.off(eventName, handler)
    })
    eventsRef.current = {}

    // 绑定新事件
    if (onEvents) {
      Object.entries(onEvents).forEach(([eventName, handler]) => {
        const wrappedHandler = (param: unknown) => handler(param, instance)
        instance.on(eventName, wrappedHandler)
        eventsRef.current[eventName] = wrappedHandler
      })
    }
  }, [onEvents])

  // 与 echarts-for-react 保持一致：默认高度 300，可通过 style 覆盖
  const mergedStyle: CSSProperties = { height: 300, ...style }

  return (
    <div
      ref={containerRef}
      style={mergedStyle}
      className={`echarts-for-react ${className ?? ''}`}
    />
  )
})

EChart.displayName = 'EChart'

export default EChart
