// 前端 API 请求基础路径（与 SPA 部署子路径 / vite base 保持一致）
//
// 根因：本项目前端以 /xianyu/ 为子路径部署（vite base + BrowserRouter basename），
// 但历史代码里所有 API 请求都写成了根路径 /api/...（axios baseURL='' + 绝对路径）。
// 在「域名模式」下整套应用经反向代理挂在 /xianyu 子路径，前缀剥离后后端只收到 /xianyu/*，
// 而前端发出的 /api/* 会落到域名根路径，被代理拦截（代理只转发 /xianyu/*），
// 导致登录等接口请求失败、前端统一兜底报「请求失败」。
//
// 修复：所有 API 请求统一带上部署子路径前缀（BASE_URL，即 /xianyu/），
// 后端已同步在 /xianyu/api 下重复挂载了一份 API 路由，
// 无论代理是否剥离 /xianyu 前缀都能命中（剥离→/api/*，不剥离→/xianyu/api/*）。
// 本地/打包模式（localhost:8001）base 同样为 /xianyu/，配合后端 /xianyu/api 双挂载仍可正常工作。
export const API_BASE: string = import.meta.env.BASE_URL // 构建后为 '/xianyu/'
