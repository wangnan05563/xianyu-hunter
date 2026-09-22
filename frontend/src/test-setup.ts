// Vitest 全局 setup：注册 jest-dom 匹配器，提供 DOM 断言能力
import '@testing-library/jest-dom/vitest'

// jsdom 未实现 matchMedia，而 TipButton 通过它判断"是否可 hover 的粗指针设备"
// （移动端长按提示 vs 桌面端 hover 提示）。缺失会导致渲染 TipButton 的组件
// 抛出 "matchMedia is not a function"。这里补一个最小实现，让其返回不可 hover，
// 走桌面端 hover 分支即可，断言不依赖触摸行为。
if (typeof globalThis.matchMedia !== 'function') {
  Object.defineProperty(globalThis, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}
