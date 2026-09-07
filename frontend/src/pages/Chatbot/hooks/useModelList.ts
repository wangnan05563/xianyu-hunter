import { useState, useEffect, useCallback, useRef } from 'react'
import { aiApi } from '../../../api/ai'
import type { AIModelInfo, AIListModelsResult } from '../../../api/types'

// 最后选择的模型持久化到 localStorage：下次进入自动选中（需求 6）
const MODEL_STORAGE_KEY = 'chatbot_last_model'
const REFRESH_INTERVAL_MS = 60_000 // 需求 5：定时（60s）自动刷新

// 读取持久化的模型：localStorage 不可用时静默降级
function readSavedModel(): string | null {
  try {
    return localStorage.getItem(MODEL_STORAGE_KEY)
  } catch {
    return null
  }
}

// 写入持久化的模型
function writeSavedModel(model: string): void {
  try {
    localStorage.setItem(MODEL_STORAGE_KEY, model)
  } catch {
    // localStorage 不可用时仅内存生效
  }
}

// axios 错误归一化：优先后端 detail（业务错误提示），其次 message
// 后端 /api/ai/models 在 base_url/key 无效时返回带 detail 的 4xx/5xx（需求 4）
function extractErrorMessage(e: unknown): string {
  const err = e as {
    response?: { data?: { detail?: string } }
    message?: string
  }
  return err?.response?.data?.detail || err?.message || '获取模型列表失败'
}

export interface UseModelListResult {
  /** 当前可用模型列表 */
  models: AIModelInfo[]
  /** 当前选中的模型 id（undefined 表示尚未解析出默认） */
  selectedModel: string | undefined
  /** 首次加载中（下拉应禁用/显示占位） */
  loading: boolean
  /** 后台刷新中（定时/聚焦/手动），不阻塞首屏 */
  refreshing: boolean
  /** 错误提示（base_url/key 无效或网络异常），UI 据此展示明确提示 */
  error: string | null
  /** 手动刷新 */
  refresh: () => void
  /** 用户切换模型：立即写入 state + 持久化（需求 3） */
  selectModel: (model: string) => void
}

// 解析默认选中模型：localStorage 优先 → AI 配置 model → 列表首个
// 提取为模块级纯函数便于首屏与"已选模型失效"两种场景复用
async function resolveDefaultModel(res: AIListModelsResult): Promise<string | undefined> {
  const ids = res.models.map((m) => m.id)
  const saved = readSavedModel()
  if (saved && ids.includes(saved)) {
    return saved
  }
  try {
    const cfg = await aiApi.getConfig()
    if (cfg?.model && ids.includes(cfg.model)) {
      return cfg.model
    }
  } catch {
    // AI 配置拉取失败（如未配置）不阻断：回退列表首个
  }
  return res.models.length > 0 ? res.models[0].id : undefined
}

export function useModelList(): UseModelListResult {
  const [models, setModels] = useState<AIModelInfo[]>([])
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 默认已解析标记：解析一次后，后台刷新不再覆盖用户/已存选择
  const resolvedRef = useRef(false)
  // 镜像最新 selectedModel：background 刷新闭包内需读取最新值判断已选是否失效
  const selectedModelRef = useRef<string | undefined>(undefined)

  const selectModel = useCallback((model: string) => {
    selectedModelRef.current = model
    setSelectedModel(model)
    writeSavedModel(model)
  }, [])

  // 拉取模型列表；background=true 表示后台刷新（不切换首屏 loading 态）
  const loadModels = useCallback(
    async (background: boolean) => {
      if (background) setRefreshing(true)
      else setLoading(true)
      setError(null)
      try {
        const res = await aiApi.listModels()
        if (!res.ok || !Array.isArray(res.models)) {
          setError('获取模型列表失败')
          return
        }
        setModels(res.models)
        const ids = res.models.map((m) => m.id)
        if (!resolvedRef.current) {
          // 首次：解析默认选中
          const def = await resolveDefaultModel(res)
          selectedModelRef.current = def
          setSelectedModel(def)
          resolvedRef.current = true
        } else if (selectedModelRef.current && !ids.includes(selectedModelRef.current)) {
          // 已选模型已从上游列表消失（如配置变更）：回退默认，避免下拉指向不存在的项
          const def = await resolveDefaultModel(res)
          selectedModelRef.current = def
          setSelectedModel(def)
        }
      } catch (e) {
        setError(extractErrorMessage(e))
      } finally {
        if (background) setRefreshing(false)
        else setLoading(false)
      }
    },
    [],
  )

  // 挂载：首次拉取（首屏 loading 态）
  useEffect(() => {
    void loadModels(false)
  }, [loadModels])

  // 定时 60s 后台刷新：保证模型信息为最新（需求 5）
  useEffect(() => {
    const timer = setInterval(() => {
      void loadModels(true)
    }, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [loadModels])

  // 窗口聚焦刷新：用户切回页面时立即同步最新模型（需求 5）
  useEffect(() => {
    const onFocus = () => {
      void loadModels(true)
    }
    globalThis.addEventListener('focus', onFocus)
    return () => globalThis.removeEventListener('focus', onFocus)
  }, [loadModels])

  const refresh = useCallback(() => {
    void loadModels(true)
  }, [loadModels])

  return { models, selectedModel, loading, refreshing, error, refresh, selectModel }
}
