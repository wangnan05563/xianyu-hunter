import React, { useEffect, useRef, useState } from 'react'
import { Tooltip, Button, type ButtonProps } from 'antd'

/**
 * 统一的「带悬浮提示的按钮」组件。
 *
 * 设计目标：为页面中所有交互按钮提供一致、简洁的鼠标悬浮提示（tooltip），
 * 清晰描述按钮的具体功能与用途，并在桌面端与移动端都具备恰当的触发行为。
 *
 * 触发策略：
 * - 桌面端（主指针可悬停，hover: hover）：鼠标移入 0.3s 后显示；键盘聚焦也会显示（a11y）。
 * - 移动端（触屏，无 hover 能力）：长按 400ms 显示提示；短按（<400ms）正常触发按钮动作，
 *   长按不会误触发动作；松手后提示保留约 1.8s 自动消失。
 *
 * 禁用态提示：antd v5 的 Tooltip 不会为 disabled 子元素自动包裹 span，而浏览器不会向
 * disabled <button> 派发鼠标/触摸事件，导致禁用按钮无法显示提示。本组件在检测到
 * `disabled` 时额外用一层 <span> 包裹 Button，使提示在桌面（hover）与触屏（长按）下均可触发。
 *
 * 用法：把原来的 <Button ...> 替换为 <TipButton tip="按钮功能说明" ...>，
 * tip 即为悬浮提示文案（应简短、准确对应按钮实际功能）。其余 props 与 antd Button 完全一致。
 */

/** 检测主指针是否具备 hover 能力（桌面鼠标为 true，触屏设备为 false）。 */
function useCanHover(): boolean {
  const [canHover, setCanHover] = useState<boolean>(true)
  useEffect(() => {
    if (globalThis.window === undefined) return
    const mql = globalThis.matchMedia('(hover: hover) and (pointer: fine)')
    const update = () => setCanHover(mql.matches)
    update()
    mql.addEventListener('change', update)
    return () => mql.removeEventListener('change', update)
  }, [])
  return canHover
}

export interface TipButtonProps extends ButtonProps {
  /** 悬浮提示文案：简短、准确描述该按钮的具体功能与用途。 */
  tip: React.ReactNode
}

export const TipButton = ({ tip, title, children, ...rest }: TipButtonProps) => {
  const canHover = useCanHover()
  const [open, setOpen] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const longPressed = useRef(false)

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    [],
  )

  // antd v5 Tooltip 不为 disabled 子元素包裹 span；浏览器也不向 disabled<button> 派发事件，
  // 因此禁用态按钮原本无法显示提示。此处统一用 span 包裹以恢复提示触发。
  const isDisabled = rest.disabled === true
  const wrapStyle = rest.block ? { display: 'block', width: '100%' as const } : undefined

  if (!canHover) {
    // 触屏：长按显示提示，短按触发动作（避免长按误触）
    const buttonEl = (
      <Button {...rest} title={undefined}>
        {children}
      </Button>
    )

    if (isDisabled) {
      // 禁用态：事件绑定到外层 span（disabled button 自身不接收事件），仅保留长按看提示的能力
      return (
        <Tooltip title={tip} open={open} trigger={[]} placement="top">
          <span
            className="xh-tipbtn-disabled-wrap"
            style={wrapStyle}
            onTouchStart={() => {
              longPressed.current = false // 每次新触摸先归位，避免上一次长按残留标志吞掉本次短按
              if (timer.current) clearTimeout(timer.current)
              timer.current = setTimeout(() => {
                longPressed.current = true
                setOpen(true)
              }, 400)
            }}
            onTouchEnd={() => {
              if (timer.current) clearTimeout(timer.current)
              timer.current = setTimeout(() => setOpen(false), 1800)
            }}
            onClick={(e) => {
              if (longPressed.current) {
                // 长按仅用于查看提示，吞掉本次点击
                e.preventDefault()
                e.stopPropagation()
                longPressed.current = false
              }
            }}
          >
            {buttonEl}
          </span>
        </Tooltip>
      )
    }

    return (
      <Tooltip title={tip} open={open} trigger={[]} placement="top">
        <Button
          {...rest}
          title={undefined}
          onTouchStart={(e) => {
            rest.onTouchStart?.(e)
            longPressed.current = false // 每次新触摸先归位，避免上一次长按残留标志吞掉本次短按
            if (timer.current) clearTimeout(timer.current)
            timer.current = setTimeout(() => {
              longPressed.current = true
              setOpen(true)
            }, 400)
          }}
          onTouchEnd={(e) => {
            rest.onTouchEnd?.(e)
            if (timer.current) clearTimeout(timer.current)
            timer.current = setTimeout(() => setOpen(false), 1800)
          }}
          onClick={(e) => {
            if (longPressed.current) {
              // 长按仅用于查看提示，吞掉本次点击，不触发按钮动作
              e.preventDefault()
              e.stopPropagation()
              longPressed.current = false
              return
            }
            rest.onClick?.(e)
          }}
        >
          {children}
        </Button>
      </Tooltip>
    )
  }

  // 桌面端：鼠标移入 0.3s 显示；键盘聚焦也会显示
  const buttonEl = (
    <Button {...rest} title={undefined}>
      {children}
    </Button>
  )

  if (isDisabled) {
    // 禁用态：用 span 包裹，使 hover 可触发提示（disabled button 自身不接收鼠标事件）
    return (
      <Tooltip title={tip} placement="top" mouseEnterDelay={0.3} trigger={['hover', 'focus']}>
        <span className="xh-tipbtn-disabled-wrap" style={wrapStyle}>
          {buttonEl}
        </span>
      </Tooltip>
    )
  }

  return (
    <Tooltip title={tip} placement="top" mouseEnterDelay={0.3} trigger={['hover', 'focus']}>
      {buttonEl}
    </Tooltip>
  )
}

export default TipButton
