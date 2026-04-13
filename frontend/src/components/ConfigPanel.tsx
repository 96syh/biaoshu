/**
 * 配置面板组件
 */
import React, { useCallback, useEffect, useState } from 'react';
import { ConfigData } from '../types';
import { configApi } from '../services/api';
import { DEFAULT_PROVIDER_ID, PROVIDER_PRESETS, getProviderPreset } from '../constants/providers';

interface ConfigPanelProps {
  config: ConfigData;
  onConfigChange: (config: ConfigData) => void;
}

const mergeModelOptions = (presetModels: string[], remoteModels: string[]) =>
  Array.from(new Set([...remoteModels, ...presetModels]));

const ConfigPanel: React.FC<ConfigPanelProps> = ({ config, onConfigChange }) => {
  const normalizedConfig: ConfigData = {
    provider: config.provider || DEFAULT_PROVIDER_ID,
    api_key: config.api_key || '',
    base_url: config.base_url || '',
    model_name: config.model_name || 'gpt-4.1-mini',
  };

  const [localConfig, setLocalConfig] = useState<ConfigData>(normalizedConfig);
  const [models, setModels] = useState<string[]>(getProviderPreset(normalizedConfig.provider).models);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const currentPreset = getProviderPreset(localConfig.provider);

  const syncConfigState = useCallback((nextConfig: ConfigData) => {
    const preset = getProviderPreset(nextConfig.provider);
    setLocalConfig(nextConfig);
    setModels(mergeModelOptions(preset.models, []));
    onConfigChange(nextConfig);
  }, [onConfigChange]);

  const loadConfig = useCallback(async () => {
    try {
      const response = await configApi.loadConfig();
      if (response.data) {
        const loadedProvider = response.data.provider || DEFAULT_PROVIDER_ID;
        const preset = getProviderPreset(loadedProvider);
        const nextConfig: ConfigData = {
          provider: loadedProvider,
          api_key: response.data.api_key || '',
          base_url: response.data.base_url || preset.baseUrl,
          model_name: response.data.model_name || preset.models[0] || 'gpt-4.1-mini',
        };
        syncConfigState(nextConfig);
      }
    } catch (error) {
      console.error('加载配置失败:', error);
    }
  }, [syncConfigState]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const updateConfigField = (patch: Partial<ConfigData>) => {
    setLocalConfig((prev) => ({ ...prev, ...patch }));
  };

  const handleProviderChange = (providerId: string) => {
    const preset = getProviderPreset(providerId);
    setMessage(null);
    setModels(mergeModelOptions(preset.models, []));
    setLocalConfig((prev) => ({
      ...prev,
      provider: providerId,
      base_url: providerId === 'custom' ? prev.base_url : preset.baseUrl,
      model_name: preset.models.includes(prev.model_name) ? prev.model_name : (preset.models[0] || prev.model_name),
    }));
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      const response = await configApi.saveConfig(localConfig);

      if (response.data.success) {
        onConfigChange(localConfig);
        setMessage({ type: 'success', text: '模型工作台配置已保存' });
        setTimeout(() => setMessage(null), 3000);
      } else {
        setMessage({ type: 'error', text: response.data.message || '配置保存失败' });
      }
    } catch (error) {
      console.error('保存配置错误:', error);
      setMessage({ type: 'error', text: '配置保存失败' });
    } finally {
      setLoading(false);
    }
  };

  const handleGetModels = async () => {
    if (currentPreset.requiresApiKey && !localConfig.api_key) {
      setMessage({ type: 'error', text: '当前供应商需要先填写 API Key' });
      return;
    }

    try {
      setLoading(true);
      const response = await configApi.getModels(localConfig);

      if (response.data.success) {
        const remoteModels = response.data.models || [];
        const mergedModels = mergeModelOptions(currentPreset.models, remoteModels);
        const nextConfig: ConfigData = {
          ...localConfig,
          model_name: remoteModels.length > 0 && !remoteModels.includes(localConfig.model_name)
            ? remoteModels[0]
            : localConfig.model_name,
        };

        setModels(mergedModels);
        setLocalConfig(nextConfig);

        const saveResponse = await configApi.saveConfig(nextConfig);
        if (saveResponse.data.success) {
          onConfigChange(nextConfig);
        } else {
          setMessage({ type: 'error', text: saveResponse.data.message || '同步成功但保存配置失败' });
          return;
        }

        setMessage({ type: 'success', text: response.data.message || `已同步 ${mergedModels.length} 个模型` });
        setTimeout(() => setMessage(null), 3500);
      } else {
        setMessage({ type: 'error', text: response.data.message || '获取模型列表失败' });
      }
    } catch (error) {
      console.error('获取模型列表失败:', error);
      setMessage({ type: 'error', text: '获取模型列表失败' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <aside className="glass-sidebar w-[360px] shrink-0 overflow-y-auto">
      <div className="space-y-8 p-6">
        <div className="space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/70 bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-sky-700 shadow-sm">
            Bid Studio
          </div>
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="font-display text-[2rem] font-semibold tracking-[-0.04em] text-slate-950">
                  华正 AI 标书创作平台
                </h1>
                <p className="mt-2 max-w-xs text-sm leading-6 text-slate-600">
                  面向提案团队的多模型控制台。切换供应商、校准模型、保存交付配置，一套界面完成。
                </p>
              </div>
              <div className="hero-orb h-14 w-14 shrink-0 rounded-2xl" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="soft-stat">
                <span className="soft-stat__label">当前供应商</span>
                <span className="soft-stat__value">{currentPreset.label}</span>
              </div>
              <div className="soft-stat">
                <span className="soft-stat__label">默认模型</span>
                <span className="soft-stat__value truncate">{localConfig.model_name}</span>
              </div>
            </div>
          </div>
        </div>

        <form
          className="space-y-6"
          onSubmit={(event) => {
            event.preventDefault();
            handleSave();
          }}
        >
          <section className="config-section">
            <div className="config-section__header">
              <span className="config-section__eyebrow">Provider Matrix</span>
              <h2 className="config-section__title">选择模型供应商</h2>
              <p className="config-section__desc">支持 OpenAI、Codex、Claude、Gemini、DeepSeek、Qwen、Kimi、OpenRouter 和本地 Ollama。</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {PROVIDER_PRESETS.map((provider) => {
                const active = provider.id === localConfig.provider;
                return (
                  <button
                    key={provider.id}
                    type="button"
                    onClick={() => handleProviderChange(provider.id)}
                    className={`provider-tile ${active ? 'provider-tile--active' : ''}`}
                  >
                    <span className="provider-tile__label">{provider.label}</span>
                    <span className="provider-tile__caption">{provider.caption}</span>
                  </button>
                );
              })}
            </div>

            <div className="provider-note">
              <span className="provider-note__tag">{currentPreset.label}</span>
              <p>{currentPreset.note}</p>
            </div>
          </section>

          <section className="config-section">
            <div className="config-section__header">
              <span className="config-section__eyebrow">Connection</span>
              <h2 className="config-section__title">接入配置</h2>
            </div>

            <div className="space-y-4">
              <div className="field-group">
                <label htmlFor="api_key" className="field-group__label">
                  API Key {currentPreset.requiresApiKey ? '' : '（可选）'}
                </label>
                <input
                  type="password"
                  id="api_key"
                  value={localConfig.api_key}
                  onChange={(event) => updateConfigField({ api_key: event.target.value })}
                  className="field-input"
                  placeholder={currentPreset.keyPlaceholder}
                />
              </div>

              <div className="field-group">
                <label htmlFor="base_url" className="field-group__label">
                  Base URL
                </label>
                <input
                  type="text"
                  id="base_url"
                  value={localConfig.base_url || ''}
                  onChange={(event) => updateConfigField({ base_url: event.target.value })}
                  className="field-input"
                  placeholder={currentPreset.baseUrl || '输入兼容 OpenAI 的服务地址'}
                />
              </div>
            </div>
          </section>

          <section className="config-section">
            <div className="config-section__header">
              <span className="config-section__eyebrow">Model Routing</span>
              <h2 className="config-section__title">模型选择</h2>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleGetModels}
                disabled={loading}
                className="primary-button flex-1"
              >
                {loading ? '同步中...' : '同步模型列表'}
              </button>
              <a
                href="/client-demo.html"
                target="_blank"
                rel="noopener noreferrer"
                className="secondary-button whitespace-nowrap"
              >
                演示页
              </a>
            </div>

            <div className="field-group">
              <label htmlFor="model_name" className="field-group__label">
                模型名称
              </label>
              {models.length > 0 ? (
                <select
                  id="model_name"
                  value={localConfig.model_name}
                  onChange={(event) => updateConfigField({ model_name: event.target.value })}
                  className="field-input"
                >
                  {models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  id="model_name"
                  value={localConfig.model_name}
                  onChange={(event) => updateConfigField({ model_name: event.target.value })}
                  className="field-input"
                  placeholder="输入模型名称，例如 claude-sonnet-4-6"
                />
              )}
            </div>

            {currentPreset.models.length > 0 && (
              <div className="space-y-3">
                <span className="field-group__label">推荐模型</span>
                <div className="flex flex-wrap gap-2">
                  {currentPreset.models.map((model) => (
                    <button
                      key={model}
                      type="button"
                      onClick={() => updateConfigField({ model_name: model })}
                      className={`model-chip ${localConfig.model_name === model ? 'model-chip--active' : ''}`}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          <button
            type="submit"
            disabled={loading}
            className="success-button w-full"
          >
            {loading ? '保存中...' : '保存当前工作台配置'}
          </button>

          {message && (
            <div className={`notice-banner ${message.type === 'success' ? 'notice-banner--success' : 'notice-banner--error'}`}>
              {message.text}
            </div>
          )}
        </form>

        <section className="config-section">
          <div className="config-section__header">
            <span className="config-section__eyebrow">Usage</span>
            <h2 className="config-section__title">演示建议</h2>
          </div>
          <div className="space-y-2 text-sm leading-6 text-slate-600">
            <p>1. 先选供应商，再同步模型列表或点选推荐模型。</p>
            <p>2. 现场演示时推荐切到 DeepSeek、Claude 或 Gemini 形成对比。</p>
            <p>3. 客户展示可直接打开 <code>/client-demo.html</code> 作为独立讲解页。</p>
          </div>
        </section>

        <div className="flex items-center justify-between border-t border-slate-200/70 pt-4 text-sm text-slate-500">
          <span className="text-slate-400">华正AI标书创作平台</span>
          <a
            href="mailto:support@huazheng-ai.com"
            className="text-slate-500 transition hover:text-slate-900"
          >
            联系我们
          </a>
        </div>
      </div>
    </aside>
  );
};

export default ConfigPanel;
