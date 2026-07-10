// AI 服务商预设配置：常用端点 + 默认模型，便于一键切换
// 仅修改 URL 和模型名称，API Key 需用户自行填写以避免硬编码
// apiKeyUrl：厂商 API Key 申请页，用于在 API Key 输入框旁渲染「获取」超链接
export const PRESETS = {
  openai: {
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    vision_model: 'gpt-4o',
    label: 'OpenAI',
    color: '#10a37f',
    apiKeyUrl: 'https://platform.openai.com/api-keys',
  },
  deepseek: {
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    vision_model: 'deepseek-chat',
    label: 'DeepSeek',
    color: '#4d6bfe',
    apiKeyUrl: 'https://platform.deepseek.com/api_keys',
  },
  zhipu: {
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'glm-4-flash',
    vision_model: 'glm-4v-flash',
    label: '智谱 GLM',
    color: '#0066ff',
    apiKeyUrl: 'https://open.bigmodel.cn/usercenter/apikeys',
  },
  moonshot: {
    base_url: 'https://api.moonshot.cn/v1',
    model: 'moonshot-v1-8k',
    vision_model: 'moonshot-v1-8k',
    label: 'Moonshot',
    color: '#6666ff',
    apiKeyUrl: 'https://platform.moonshot.cn/console/api-keys',
  },
  qwen: {
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
    vision_model: 'qwen-vl-plus',
    label: '通义千问',
    color: '#ff6a00',
    apiKeyUrl: 'https://dashscope.console.aliyun.com/apiKey',
  },
  ernie: {
    base_url: 'https://qianfan.baidubce.com/v2',
    model: 'ernie-speed-128k',
    vision_model: 'ernie-vision-4k',
    label: '文心一言',
    color: '#2932e1',
    apiKeyUrl: 'https://console.bce.baidu.com/iam/#/iam/apikey/list',
  },
  doubao: {
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    model: 'doubao-pro-32k',
    vision_model: 'doubao-vision-pro-32k',
    label: '豆包',
    color: '#0066ff',
    apiKeyUrl: 'https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey',
  },
  agnes: {
    // Agnes AI 兼容 OpenAI 接口，文档参考 https://agnes-ai.com/zh-Hans/docs/
    // 免费额度覆盖文本/图像/视频生成，API Key 从 platform.agnes-ai.com 获取
    base_url: 'https://apihub.agnes-ai.com/v1',
    model: 'agnes-2.0-flash',
    vision_model: 'agnes-2.0-flash',
    label: 'Agnes AI',
    color: '#8b5cf6',
    apiKeyUrl: 'https://platform.agnes-ai.com/',
  },
  ollama: {
    base_url: 'http://localhost:11434/v1',
    model: 'qwen2.5:7b',
    vision_model: 'llava:7b',
    label: 'Ollama 本地',
    color: '#555555',
    // Ollama 本地无需 API Key
  },
}

// 根据当前 base_url 反查预设，用于「获取」超链接等派生 UI
// 用户可能手动改过 base_url 末尾斜杠或路径，按 startsWith 容错匹配
export function findPresetByBaseUrl(base_url: string): { apiKeyUrl?: string; label?: string } | undefined {
  if (!base_url) return undefined
  const normalized = base_url.replace(/\/+$/, '')
  return Object.values(PRESETS).find((p) => p.base_url.replace(/\/+$/, '') === normalized)
}

// Embedding 服务商预设：与 LLM 预设分离
// 原因：DeepSeek/智谱等国产 LLM 厂商大多不支持 /v1/embeddings，
// 需独立配置 embedding 端点（如本地 Python 或 Jina AI）
export const EMBEDDING_PRESETS = {
  // 本地 Python 推理：sentence-transformers + bge-small-zh-v1.5
  // 优势：无外部依赖，无需 Ollama/网络；首次加载约 95MB 模型
  // base_url 留空 → 后端识别为本地模式
  local: {
    embedding_base_url: '',
    embedding_model: 'BAAI/bge-small-zh-v1.5',
    embedding_dimensions: 512,
    label: 'Python 本地',
    color: '#52c41a',
    // 本地模式无需 API Key
  },
  openai: {
    embedding_base_url: 'https://api.openai.com/v1',
    embedding_model: 'text-embedding-3-small',
    embedding_dimensions: 1536,
    label: 'OpenAI',
    color: '#10a37f',
    apiKeyUrl: 'https://platform.openai.com/api-keys',
  },
  jina: {
    embedding_base_url: 'https://api.jina.ai/v1',
    embedding_model: 'jina-embeddings-v3',
    embedding_dimensions: 1024,
    label: 'Jina AI',
    color: '#0f6fff',
    apiKeyUrl: 'https://jina.ai/api-key/',
  },
  // Ollama 本地：需先安装 Ollama + llama-server.exe，下载 nomic-embed-text 模型
  // Windows 上 Ollama 安装包不完整时缺 llama-server.exe，建议改用 Python 本地
  ollama: {
    embedding_base_url: 'http://localhost:11434/v1',
    embedding_model: 'nomic-embed-text',
    embedding_dimensions: 768,
    label: 'Ollama 本地',
    color: '#555555',
    // Ollama 本地无需 API Key
  },
  // "复用 LLM 配置"：清空 embedding 配置，fallback 到 OPENAI_*
  // 适用于 OpenAI 等同时支持 LLM 和 embedding 的厂商
  inherit: {
    embedding_base_url: '',
    embedding_model: '',
    embedding_dimensions: 0,
    label: '复用 LLM 配置',
    color: '#999999',
    // 复用 LLM 配置时由 LLM 的获取链接负责
  },
}

// 根据 embedding_base_url 反查 Embedding 预设
export function findEmbeddingPresetByBaseUrl(base_url: string): { apiKeyUrl?: string; label?: string } | undefined {
  if (!base_url) return undefined
  const normalized = base_url.replace(/\/+$/, '')
  return Object.values(EMBEDDING_PRESETS).find((p) => p.embedding_base_url.replace(/\/+$/, '') === normalized)
}

// 端点中文标签映射：用量统计中将后端 endpoint key 转为可读文本
export const ENDPOINT_LABELS: Record<string, string> = {
  parse_task: '自然语言解析',
  evaluate_condition: '成色评估',
  deep_analyze: '深度分析',
  seller_template_check: '模板检测',
  test_connection: '连接测试',
}

// 格式化 Token 数值（K/M 单位），避免长数字影响阅读
export function formatTokens(n: number): string {
  if (!n) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

// 根据百分比返回进度条颜色（绿/黄/红），直观反映预算消耗风险
export function getProgressColor(pct: number): string {
  if (pct >= 90) return '#ff4d4f'
  if (pct >= 70) return '#faad14'
  return '#52c41a'
}
