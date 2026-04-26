export interface ProviderPreset {
  id: string;
  label: string;
  caption: string;
  baseUrl: string;
  models: string[];
  requiresApiKey: boolean;
  apiMode: 'chat';
  keyPlaceholder: string;
  note: string;
}

export const LITELLM_PROVIDER: ProviderPreset = {
  id: 'litellm',
  label: 'LiteLLM Proxy',
  caption: '统一 OpenAI 格式网关',
  baseUrl: 'http://localhost:4000/v1',
  models: [],
  requiresApiKey: false,
  apiMode: 'chat',
  keyPlaceholder: 'LiteLLM master key / virtual key，可选',
  note: '所有模型都先接入 LiteLLM，再由本应用以 OpenAI Chat Completions 格式调用。',
};

export const PROVIDER_PRESETS: ProviderPreset[] = [LITELLM_PROVIDER];
export const DEFAULT_PROVIDER_ID = LITELLM_PROVIDER.id;

export const getProviderPreset = (_providerId?: string) => LITELLM_PROVIDER;
