export interface ProviderPreset {
  id: string;
  label: string;
  caption: string;
  baseUrl: string;
  models: string[];
  requiresApiKey: boolean;
  keyPlaceholder: string;
  note: string;
}

export const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: 'openai',
    label: 'OpenAI',
    caption: '官方 GPT 系列',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini'],
    requiresApiKey: true,
    keyPlaceholder: '输入 OpenAI API Key',
    note: '适合英文能力、长上下文与高稳定性场景。',
  },
  {
    id: 'codex',
    label: 'Codex',
    caption: 'OpenAI 编码模型',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-5.2-codex', 'gpt-5.1-codex', 'gpt-5.1-codex-mini', 'gpt-5.1-codex-max'],
    requiresApiKey: true,
    keyPlaceholder: '输入 OpenAI API Key',
    note: '通过 OpenAI 官方接口接入，后端会自动切到 Responses API，适合代码、脚本和结构化生成任务。',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    caption: '中文推理与性价比',
    baseUrl: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    requiresApiKey: true,
    keyPlaceholder: '输入 DeepSeek API Key',
    note: '适合中文长文生成、技术方案和高性价比部署。',
  },
  {
    id: 'anthropic',
    label: 'Claude API',
    caption: 'Claude 原生接口',
    baseUrl: 'https://api.anthropic.com',
    models: ['claude-sonnet-4-6', 'claude-opus-4-6'],
    requiresApiKey: true,
    keyPlaceholder: '输入 Anthropic API Key',
    note: '支持官方 Claude 接口，也支持自定义 Claude 网关地址；模型同步走 /v1/models，生成走 /v1/messages。',
  },
  {
    id: 'gemini',
    label: 'Gemini API',
    caption: '通过兼容层接入 Gemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    models: ['gemini-3-flash-preview', 'gemini-2.5-flash', 'gemini-2.5-pro'],
    requiresApiKey: true,
    keyPlaceholder: '输入 Gemini API Key',
    note: '适合速度优先、多模态工作流与 Google 生态调用。',
  },
  {
    id: 'dashscope',
    label: '阿里云百炼',
    caption: '通义千问兼容模式',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-plus', 'qwen-max', 'qwen3-max'],
    requiresApiKey: true,
    keyPlaceholder: '输入阿里云 DashScope API Key',
    note: '适合中文场景、本地政企客户以及通义模型栈。',
  },
  {
    id: 'moonshot',
    label: 'Moonshot Kimi',
    caption: 'Kimi / Moonshot 官方',
    baseUrl: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2.5', 'kimi-k2', 'kimi-k2-thinking'],
    requiresApiKey: true,
    keyPlaceholder: '输入 Moonshot API Key',
    note: '适合中文长文本、资料梳理与提案生成。',
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    caption: '一套 Key 聚合多家模型',
    baseUrl: 'https://openrouter.ai/api/v1',
    models: ['openai/gpt-4.1-mini', 'anthropic/claude-sonnet-4-6', 'google/gemini-2.5-flash'],
    requiresApiKey: true,
    keyPlaceholder: '输入 OpenRouter API Key',
    note: '适合需要统一切换 GPT / Claude / Gemini 的团队。',
  },
  {
    id: 'ollama',
    label: 'Ollama',
    caption: '本地模型服务',
    baseUrl: 'http://localhost:11434/v1',
    models: ['llama3.2', 'qwen3:8b', 'gpt-oss:20b'],
    requiresApiKey: false,
    keyPlaceholder: '本地模式通常不需要 API Key',
    note: '适合离线内网、私有部署与本地推理实验。',
  },
  {
    id: 'custom',
    label: 'Custom',
    caption: 'OpenAI / Claude 自定义网关',
    baseUrl: '',
    models: [],
    requiresApiKey: false,
    keyPlaceholder: '代理 / 网关 / 本地兼容层可选填',
    note: '支持 OpenAI 兼容网关，也会在失败后自动尝试 Claude 原生协议。若同步失败，通常是 API Key 无效或网关未开放模型列表。',
  },
];

export const DEFAULT_PROVIDER_ID = 'openai';

export const getProviderPreset = (providerId?: string): ProviderPreset =>
  PROVIDER_PRESETS.find((provider) => provider.id === providerId) ??
  PROVIDER_PRESETS.find((provider) => provider.id === DEFAULT_PROVIDER_ID)!;
