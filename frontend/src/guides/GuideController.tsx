import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Tour, FloatButton, type TourStepProps } from 'antd'
import {
  CompassOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import type { GuideStep, GuidePlayMode } from './types'
import { findMenuGuide } from './menuGuides'
import { isGuideDone, markGuideDone } from './guideStorage'

/** 自动播放时每步停留时长（毫秒） */
const AUTO_PLAY_INTERVAL = 3000

/**
 * 全站引导向导控制器
 *
 * 职责（单一组件收敛所有引导逻辑，注入 MainLayout 一次即可全局生效）：
 * 1. 路由变化时匹配当前页引导配置，首次访问自动弹出 Tour（用 localStorage 记忆）
 * 2. 悬浮常驻按钮：手动唤起当前页引导；右键/二次唤起可"重新开始全部"
 * 3. 全流程演示：支持手动步进与自动播放（点击演示按钮即时播放）
 *
 * 容错：selector 目标元素未渲染时，Tour 步骤 target 返回空 → 居中展示说明，
 * 不会因找不到元素崩溃（S8053 空目标由 antd 兜底渲染）。
 */
export function GuideController() {
  const location = useLocation()

  // 当前路由对应的引导配置（含动态路由前缀匹配 /tasks/:id）
  const guide = useMemo(
    () => findMenuGuide(location.pathname),
    [location.pathname],
  )

  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState(0)
  const [mode, setMode] = useState<GuidePlayMode>('manual')
  const autoTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const routesReady = !!guide && guide.steps.length > 0

  // 单步自动播放计时器：仅在自动模式下且已打开时启动
  const stopAuto = useCallback(() => {
    if (autoTimer.current) {
      clearInterval(autoTimer.current)
      autoTimer.current = null
    }
  }, [])

  const startAutoPlay = useCallback(
    (stepsLength: number) => {
      stopAuto()
      setMode('auto')
      autoTimer.current = setInterval(() => {
        setCurrent((c) => {
          // 播完最后一步：停表并保持打开让用户看到结尾（由 next 触发关闭或循环）
          if (c >= stepsLength - 1) {
            stopAuto()
            return c
          }
          return c + 1
        })
      }, AUTO_PLAY_INTERVAL)
    },
    [stopAuto],
  )

  // 切换到手动模式并停止自动播放
  const switchToManual = useCallback(() => {
    stopAuto()
    setMode('manual')
  }, [stopAuto])

  // 打开引导：默认手动模式
  const openGuide = useCallback(() => {
    setMode('manual')
    setCurrent(0)
    setOpen(true)
  }, [])

  // 首次访问自动触发：仅当该路由存在引导且未标记完成
  useEffect(() => {
    if (!routesReady) {
      setOpen(false)
      return
    }
    if (isGuideDone(location.pathname)) return
    // 延迟一帧等待页面渲染完成，确保 .page-container 等目标元素已挂载
    const id = requestAnimationFrame(() => {
      // 再次确认：rAF 期间路由可能已切换
      if (document.querySelector('.page-container') === null) return
      openGuide()
    })
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routesReady, location.pathname])

  // 卸载时清理自动播放计时器
  useEffect(() => stopAuto, [stopAuto])

  // 把 GuideStep 配置映射为 antd Tour 步骤
  // 为什么用 IIFE 赋值 target：让 selector 的类型收窄在闭包内清晰可见，
  // 直接内联三元会因箭头函数捕获 string|undefined 触发 TS2769
  const tourSteps: TourStepProps[] = useMemo(() => {
    if (!guide) return []
    return guide.steps.map((s: GuideStep) => {
      const target = s.selector
        ? (((() => document.querySelector(s.selector as string) as HTMLElement | null)) as TourStepProps['target'])
        : undefined
      return {
        // target 缺省时为 undefined → antd 居中展示；selector 找不到时 querySelector 返回 null
        // 同样走向中展示，保证容错
        target,
        title: s.title,
        description: s.description,
        // 无目标时 antd 默认 center 放置；有目标时缺省 bottom
        placement: (s.placement ?? 'bottom') as TourStepProps['placement'],
      }
    })
  }, [guide])

  const onTourClose = useCallback(() => {
    stopAuto()
    setOpen(false)
    // 关闭视为引导结束，标记该路由首次引导完成
    if (guide) markGuideDone(guide.route)
  }, [guide, stopAuto])

  // 手动步进时的操作回调
  const onStepChange = useCallback(
    (step: number) => {
      // 用户手动操作即视为切换回手动模式，避免自动播放与手动冲突
      setCurrent(step)
    },
    [],
  )

  // 常驻按钮区：仅当存在可用引导时显示（避免无意义悬浮按钮）
  if (!routesReady) return null

  return (
    <>
      <Tour
        open={open}
        current={current}
        onClose={onTourClose}
        steps={tourSteps}
        onChange={onStepChange}
        onFinish={() => {
          stopAuto()
          setOpen(false)
          if (guide) markGuideDone(guide.route)
        }}
      />

      {/* 常驻悬浮交互按钮组：引导唤起 + 自动演示 + 帮助入口
          为什么用 Button.Group：将首次引导、演示、帮助收敛在一个悬浮簇，避免页面堆叠多个浮动按钮 */}
      <FloatButton.Group shape="square" style={{ right: 24, bottom: 120 }}>
        <FloatButton
          icon={<CompassOutlined />}
          onClick={openGuide}
          tooltip="开始本页引导（首次访问会自动弹出）"
        />
        <FloatButton
          icon={mode === 'auto' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          onClick={() => {
            if (mode === 'auto') {
              switchToManual()
            } else {
              setCurrent(0)
              startAutoPlay(tourSteps.length)
            }
          }}
          tooltip={mode === 'auto' ? '暂停自动播放' : '自动播放本页全流程演示'}
        />
        <FloatButton
          icon={<QuestionCircleOutlined />}
          href="#/help"
          tooltip="查看完整帮助文档"
        />
      </FloatButton.Group>
    </>
  )
}

export default GuideController