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

// 响应拦截器：401 跳转登录
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('xh_token')
      // 不强制跳转，让用户在当前页面看到未登录提示
    }
    return Promise.reject(error)
  },
)

export default client
