import React from 'react';
import {
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  Cog6ToothIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { MainRouter } from '../../app/MainRouter';
import { useWorkspace } from '../../app/WorkspaceProvider';
import { LITELLM_PROVIDER } from '../../constants/providers';
import { VerifyLine } from '../config/VerifyLine';

export const AppView = () => {
  const controller = useWorkspace();
  const {
    activeNav,
    availableModels,
    BID_MODE_OPTIONS,
    busy,
    configOpen,
    coverage,
    entries,
    handleModeChange,
    handleWorkflowAction,
    historyOpen,
    historyRecords,
    localConfig,
    NAV_ITEMS,
    navCollapsed,
    projectProgressText,
    projectTitle,
    restoreHistoryRecord,
    runtimeEvent,
    runtimeIsCurrentTaskActive,
    runtimeStatus,
    runtimeStatusText,
    saveConfig,
    selectedBidMode,
    setConfigOpen,
    setLocalConfig,
    setNavCollapsed,
    setVerifyResult,
    state,
    syncModels,
    toggleHistoryPanel,
    toLiteLLMConfig,
    verifyConfig,
    verifyResult,
    workflowAccess,
    workflowStatus,
  } = controller;

  const stageMetaMap: Record<string, { index: number; title: string }> = {
    project: { index: 1, title: '上传与项目准备' },
    analysis: { index: 2, title: '标准解析工作台' },
    outline: { index: 3, title: '目录规划' },
    assets: { index: 4, title: '图表素材规划' },
    content: { index: 5, title: '正文生成与审校' },
    review: { index: 6, title: '审校与导出' },
    config: { index: 0, title: '系统配置' },
  };
  const stageMeta = stageMetaMap[activeNav] || { index: 1, title: '上传与项目准备' };

  return (
    <div className={`ops-app ${navCollapsed ? 'ops-app--nav-collapsed' : ''}`}>
      <aside className="ops-nav">
        <div className="ops-brand">
          <span className="ops-brand__mark">A</span>
          <span className="ops-brand__text">华正ai标书系统</span>
          <button
            type="button"
            className="ops-nav-toggle"
            onClick={() => setNavCollapsed(value => !value)}
            aria-label={navCollapsed ? '展开侧边栏' : '收起侧边栏'}
            title={navCollapsed ? '展开' : '收起'}
          >
            {navCollapsed ? <ChevronRightIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
          </button>
        </div>
        <nav className="ops-nav__list">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeNav === item.key;
            const access = workflowAccess(item.key);
            const disabled = !access.enabled && !active;
            return (
              <button
                key={item.key}
                type="button"
                className={`ops-nav__item ${active ? 'ops-nav__item--active' : ''}`}
                onClick={() => handleWorkflowAction(item)}
                disabled={disabled}
                title={disabled ? access.reason : navCollapsed ? item.label : undefined}
              >
                <Icon className="h-4 w-4" />
                <span className="ops-nav__copy">
                  <strong>{item.label}</strong>
                  <em>{item.description}</em>
                </span>
                <span className="ops-nav__state">{workflowStatus(item.key)}</span>
              </button>
            );
          })}
        </nav>
        <div className="history-panel">
          <div className="history-panel__head">
            <strong>项目数据库</strong>
            <button type="button" className="text-link" onClick={toggleHistoryPanel}>
              {historyOpen ? '收起' : '查看'}
            </button>
          </div>
          {historyOpen ? (
            <div className="history-list">
              {historyRecords.length ? historyRecords.slice(0, 4).map(record => (
                <button
                  key={record.id}
                  type="button"
                  className="history-item"
                  onClick={() => restoreHistoryRecord(record)}
                >
                  <strong>{record.title}</strong>
                  <span>{record.total ? `${record.completed}/${record.total} 章` : '待生成目录'} · {new Date(record.updatedAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
                </button>
              )) : (
                <div className="history-empty">暂无项目记录</div>
              )}
            </div>
          ) : (
            <div className="history-empty">历史项目已隐藏，点击查看后加载。</div>
          )}
        </div>
        <div className="ops-progress-card">
          <div className="ops-progress-card__ring">{coverage}%</div>
          <div>
            <strong>当前项目进度</strong>
            <span>{projectProgressText}</span>
            <span>字数统计 {entries.reduce((sum, entry) => sum + (entry.item.content?.length || 0), 0).toLocaleString()}</span>
          </div>
        </div>
        <div className="ops-user">
          <span className="ops-user__avatar">本</span>
          <div>
            <strong>本地工作台</strong>
            <span>{state.fileContent ? '招标文件已载入' : '待上传文件'}</span>
          </div>
          <ChevronDownIcon className="h-4 w-4 text-slate-400" />
        </div>
      </aside>

      <main className="ops-main">
        <header className="ops-topbar">
          <div className="ops-stage-title">
            <span>{stageMeta.index}</span>
            <strong>{stageMeta.title}</strong>
          </div>
          <div className="ops-topbar__center">
            <span>当前项目：</span>
            <strong>{projectTitle}</strong>
            <ChevronDownIcon className="h-4 w-4" />
            <span>生成模式：</span>
            <div className="ops-mode-toggle" role="group" aria-label="生成模式">
              {BID_MODE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={selectedBidMode === option.value ? 'active' : ''}
                  onClick={() => handleModeChange(option.value)}
                  aria-pressed={selectedBidMode === option.value}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <span>当前模型：</span>
            <strong>{state.config.model_name || '未选择模型'}</strong>
            <span
              className={`model-runtime-pill model-runtime-pill--${runtimeIsCurrentTaskActive ? 'running' : runtimeStatus === 'error' ? 'error' : 'idle'}`}
              title={runtimeEvent?.message || runtimeStatusText}
            >
              <i aria-hidden="true" />
              {runtimeStatusText}
            </span>
          </div>
          <div className="ops-topbar__status">
            <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
            <span>{state.fileContent ? '已保存草稿' : '等待上传'}</span>
            <button type="button" className="ops-icon-button" onClick={() => setConfigOpen(true)}>
              <Cog6ToothIcon className="h-4 w-4" />
              模型配置
            </button>
          </div>
        </header>

        <div className="ops-body ops-body--page">
          <section className="ops-page">
            <MainRouter />
          </section>
        </div>
      </main>

      {configOpen && (
        <aside className="model-drawer">
          <div className="drawer-head">
            <h2>模型接入</h2>
            <button type="button" onClick={() => setConfigOpen(false)}><XMarkIcon className="h-5 w-5" /></button>
          </div>
          <div className="provider-lock">
            <strong>{LITELLM_PROVIDER.label}</strong>
            <span>{LITELLM_PROVIDER.note}</span>
          </div>
          <label>LiteLLM Base URL</label>
          <input
            value={localConfig.base_url || ''}
            onChange={(event) => {
              setVerifyResult(null);
              setLocalConfig(prev => toLiteLLMConfig({ ...prev, base_url: event.target.value }));
            }}
            placeholder={LITELLM_PROVIDER.baseUrl}
          />
          <label>模型名</label>
          <input
            value={localConfig.model_name}
            onChange={(event) => {
              setVerifyResult(null);
              setLocalConfig(prev => toLiteLLMConfig({ ...prev, model_name: event.target.value }));
            }}
            list="available-models"
            placeholder="从 /models 同步后选择，或手动输入模型 ID"
          />
          <datalist id="available-models">
            {availableModels.map(model => <option key={model} value={model} />)}
          </datalist>
          <div className="model-tools">
            <button type="button" onClick={syncModels} disabled={busy === 'models'}>{busy === 'models' ? '同步中' : '同步模型'}</button>
            {availableModels.length > 0 && <span>{availableModels.length} 个可用模型</span>}
          </div>
          {availableModels.length > 0 && (
            <div className="model-list">
              {availableModels.slice(0, 8).map(model => (
                <button
                  type="button"
                  key={model}
                  className={`model-chip ${localConfig.model_name === model ? 'model-chip--active' : ''}`}
                  onClick={() => {
                    setVerifyResult(null);
                    setLocalConfig(prev => toLiteLLMConfig({ ...prev, model_name: model }));
                  }}
                >
                  {model}
                </button>
              ))}
            </div>
          )}
          <label>API Key</label>
          <input
            type="password"
            value={localConfig.api_key}
            onChange={(event) => {
              setVerifyResult(null);
              setLocalConfig(prev => toLiteLLMConfig({ ...prev, api_key: event.target.value }));
            }}
            placeholder={LITELLM_PROVIDER.keyPlaceholder}
          />
          <div className="drawer-actions">
            <button type="button" className="solid-button" onClick={verifyConfig} disabled={busy === 'verify'}>验证端点</button>
            <button type="button" onClick={saveConfig} disabled={busy === 'config'}>保存配置</button>
          </div>
          <div className="verify-card">
            <h3>验证结果</h3>
            <VerifyLine ok={verifyResult?.checks.find(check => check.stage === 'chat')?.success} label="对话接口可用" />
            <VerifyLine ok={verifyResult?.checks.find(check => check.stage === 'models')?.success} label="模型列表可用" />
            <p>{verifyResult?.resolved_base_url || `${localConfig.base_url || LITELLM_PROVIDER.baseUrl}/chat/completions`}</p>
          </div>
        </aside>
      )}

    </div>
  );
};
