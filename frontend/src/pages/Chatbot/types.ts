// 智能客服模块类型定义
// 对应后端 api_chatbot.py / api_kb.py / api_chatbot_config.py 的响应结构

export interface Session {
  id: string
  title: string
  status: 'active' | 'ended' | 'escalated'
  message_count: number
  created_at: string
  updated_at: string
  last_active_at: string
  is_favorite: number  // M2：0=未收藏，1=已收藏
}

export interface Source {
  index: number
  file: string
  section: string
  line_start: number
  line_end: number
  similarity: number
}

export interface ToolCall {
  name: string
  args: Record<string, unknown>
  result?: unknown
}

export interface Message {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources?: Source[]
  tool_calls?: ToolCall[]
  escalated?: boolean
  escalate_reason?: string
  degraded?: boolean
  tokens_used?: number
  created_at: string
  // M3 消息状态：sending=发送中 / sent=已送达 / failed=发送失败
  // 助手消息始终为 sent（成功）或不存在此字段；仅用户消息使用 sending/failed
  status?: 'sending' | 'sent' | 'failed'
  // M3 重试用：失败消息保存原始文本，点击重试时再次发送
  retry_payload?: { text: string; images: string[] }
  // M4：用户消息关联的图片 data URL 列表
  images?: string[] | null
  // M4：消息撤回标记（0=正常，1=已撤回）
  is_recalled?: number
  // M6：反馈星级（1-5，null=未评价）+ 反馈分类
  feedback_rating?: number | null
  feedback_category?: string | null
  // 后续推荐问题：DONE 事件携带，点击后自动发送
  follow_ups?: string[]
}

export interface KBProgress {
  // 与后端 kb_manager._set_progress 的 phase 对齐
  // idle=空闲 / scanning=扫描中 / snapshotting=导出快照 / embedding=向量化中
  // writing=写入向量库 / finalizing=更新版本状态 / done=完成 / failed=失败 / rolling_back=回滚中
  phase: 'idle' | 'scanning' | 'snapshotting' | 'embedding' | 'writing' | 'finalizing' | 'done' | 'failed' | 'rolling_back'
  percent: number
  message: string
}

export interface KBStatus {
  current_version: string | null
  chunk_count: number
  last_build_at: string | null
  building: boolean
  // 与后端 api_kb.py:kb_status 对齐：empty(无版本)/success/partial/failed(构建失败)/building(构建中)
  status: 'empty' | 'success' | 'partial' | 'failed' | 'building' | 'corrupted'
  // 构建进度（building=true 时由后端 _progress 字段填充）
  progress?: KBProgress | null
}

export interface KBVersion {
  id: string
  snapshot_path: string
  doc_hash: string
  chunk_count: number
  failed_chunk_count: number
  // 与后端 kb_manager.py:KBVersion.build_type 对齐：
  // build(全量)/incremental(增量)/rollback(回滚产生)
  build_type: 'build' | 'incremental' | 'rollback' | 'full'
  status: 'success' | 'partial' | 'failed'
  is_current: boolean
  created_at: string
}

export interface FAQ {
  id?: number
  question: string
  answer: string
  category: string
  enabled: boolean
  is_quick_reply?: boolean  // M3 快捷回复：true 时显示在输入区上方
}

// M1 引导卡欢迎语响应
export interface WelcomeInfo {
  message: string
  persona: string
  updated_at: string | null
}

export interface ChatbotConfig {
  enabled: boolean
  max_history_turns: number
  session_timeout_min: number
  rag: { top_k: number; similarity_threshold: number; max_context_chars: number }
  llm: { model: string; temperature: number; max_tokens: number }
  agent: { enable_tools: boolean; max_tool_rounds: number; tool_trigger_mode: string }
  kb: { auto_update_enabled: boolean; update_interval_hours: number }
  faq: { similarity_threshold: number; confirm_threshold: number }
  escalation: {
    feedback_threshold: number
    feedback_window_min: number
    contact: string
    sanitize_pii: boolean
  }
  // 欢迎语：M1 引导卡数据源。null/空串 = 使用后端 _DEFAULT_WELCOME_MESSAGE 兜底文案
  welcome_message: string | null
}

export interface AuditLog {
  id: number
  action: string
  target: string
  source: string
  created_at: string
}

// SSE 事件类型：对应后端 orchestrator.py 的 SSEEventType
export interface SSEEvent {
  type: 'intent' | 'sources' | 'token' | 'tool_call' | 'faq_confirm' | 'done' | 'error' | 'escalate'
  data: Record<string, unknown>
}
