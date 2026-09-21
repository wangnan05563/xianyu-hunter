/**
 * 全站引导向导系统 —— 类型定义
 *
 * 为什么用 type 而非 interface：与项目数据结构规范保持一致（见 api/menu.ts 注释）
 * 为什么导出所有类型：引导配置数据（menuGuides.ts）、存储层（guideStorage.ts）、
 * 渲染组件（GuideController.tsx）各自独立，跨文件共享同一套契约避免漂移。
 */

/** 引导步骤的定位放置方式，对齐 antd Tour placement 语义 */
export type GuidePlacement =
  | 'top' | 'left' | 'right' | 'bottom'
  | 'topLeft' | 'topRight' | 'bottomLeft' | 'bottomRight'
  | 'leftTop' | 'leftBottom' | 'rightTop' | 'rightBottom'

/**
 * 单条引导步骤
 *
 * selector 为可选：提供时高亮目标元素并显示箭头；缺省时 Tour 在主内容区居中展示
 * （适配无法用选择器稳定定位的页面/元素未加载的容错场景）
 */
export interface GuideStep {
  /** 目标元素 CSS 选择器（可选）。指向页面内稳定容器，如 .page-container 或具体功能块 */
  selector?: string
  /** 引导标题 */
  title: string
  /** 引导说明文案 */
  description: string
  /** 气泡相对目标元素的放置方向，默认 bottom（选择器缺省时用 center） */
  placement?: GuidePlacement
}

/**
 * 一个菜单路由对应的引导流程
 *
 * route 作为唯一键：与 sheetRegistry / MainLayout 的 path 对齐，首次访问触发、
 * 常驻按钮唤起时按当前 path 匹配
 */
export interface MenuGuide {
  /** 路由路径，如 /tasks、/config/price */
  route: string
  /** 引导步骤序列（按数组顺序播放） */
  steps: GuideStep[]
}

/** 演示播放模式：手动步进 / 自动播放 */
export type GuidePlayMode = 'manual' | 'auto'