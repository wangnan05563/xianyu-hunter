import axios, { AxiosInstance } from 'axios'

// Axios 实例：自动携带认证凭证
const client: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 30000,
  withCredentials: true,
})

// 请求拦截器：附加 Bearer Token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('xh_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 跳转防抖标记：避免并发请求同时返回 401 时触发多次跳转，
// 多次 location.href 跳转会在渲染过程中断页面，可能造成白屏
let isRedirecting = false

// 响应拦截器：认证 401 自动跳转登录页
// 为什么区分 detail：业务逻辑（如采集 cookie 失效）也可能返回 401，
// 但只有认证中间件返回 {"detail":"Unauthorized"} 才是真正的 token 失效，
// 业务 401 由调用方 catch 自行处理（如显示错误提示），不应跳转登录页
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthUnauthorized =
      error.response?.status === 401 &&
      error.response?.data?.detail === 'Unauthorized'
    if (isAuthUnauthorized) {
      localStorage.removeItem('xh_token')
      // 避免在登录页本身触发跳转（防止死循环）
      // 路径匹配必须用 /xianyu/login：SPA 挂载在 /xianyu/ 下（vite base + BrowserRouter basename）
      const currentPath = globalThis.location.pathname + globalThis.location.search
      const isLoginPage = currentPath.startsWith('/xianyu/login')
      if (!isLoginPage && !isRedirecting) {
        isRedirecting = true
        // 保存当前路径，登录后跳转回来
        const redirect = encodeURIComponent(currentPath)
        // 使用 replace 避免在历史记录中留下当前页面，
        // 防止用户后退回到已失效的认证态页面
        // 必须用 /xianyu/login：浏览器原生跳转不走 react-router，
        // 不会自动补 basename 前缀，直接用 /login 会被后端返回 404
        globalThis.location.replace(`/xianyu/login?redirect=${redirect}`)
      }
    }
    return Promise.reject(error)
  },
)

export default client
