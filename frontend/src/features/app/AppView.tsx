import React from 'react';
import {
  ArrowDownTrayIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  Cog6ToothIcon,
  DocumentArrowUpIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  PauseIcon,
  PlayIcon,
  ShieldCheckIcon,
  SparklesIcon,
  StopIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { LITELLM_PROVIDER } from '../../constants/providers';
import { BidMode } from '../../types';
import { blockAssetKey, blockTypeLabel, isVisualBlockType, visualAssetResultFromBlock } from '../../utils/visualAssets';
import { ReferenceSlotPreview } from '../assets/ReferenceSlotPreview';
import { ReferenceSlotShowcase } from '../assets/ReferenceSlotShowcase';
import { DocumentPreviewNode } from '../content/DocumentPreviewNode';
import { DocumentTocRows } from '../content/DocumentTocRows';
import { VerifyLine } from '../config/VerifyLine';
import { OutlineDraftPreview } from '../outline/OutlineDraftPreview';
import { OutlineRows } from '../outline/OutlineRows';
import { Metric } from '../review/Metric';
import { TaskProgress } from '../shared/TaskProgress';
import { useBidWorkspaceController } from './useBidWorkspaceController';
import { ProjectPage } from './pages/ProjectPage';
import { AnalysisPage } from './pages/AnalysisPage';
import { OutlinePage } from './pages/OutlinePage';
import { AssetsPage } from './pages/AssetsPage';
import { ContentPage } from './pages/ContentPage';
import { ReviewPage } from './pages/ReviewPage';

type AppViewProps = {
  controller: ReturnType<typeof useBidWorkspaceController>;
};

export const AppView = ({ controller }: AppViewProps) => {
  const {
    activeAssetLibrary,
    activeDocId,
    activeDocumentBlocksPlan,
    activeEnterpriseProfile,
    activeNav,
    activeParseSection,
    activeParseSectionId,
    activeParseTab,
    activeParseTabKey,
    activeReferenceProfile,
    activeReferenceRecord,
    activeReferenceSlotIndex,
    activeRenderedSourceBlock,
    activeReport,
    activeResponseMatrix,
    activeScoringRows,
    activeSourceLabel,
    activeSourceLineIndex,
    activeSourceQuery,
    activeVisualAssets,
    advanceProgress,
    ANALYSIS_STEPS,
    analysisControl,
    analysisRevealPercent,
    analysisStoppedRef,
    analysisTaskId,
    analysisTaskProgressVisible,
    apiErrorMessage,
    appendParseSection,
    asList,
    AUTO_SECOND_LEVEL_TITLES,
    AUTO_THIRD_LEVEL_TITLES,
    availableModels,
    backendAssetUrl,
    batchOutlineRef,
    BID_MODE_ALIASES,
    BID_MODE_LABELS,
    BID_MODE_OPTIONS,
    BID_MODE_VALUES,
    bidDocumentCompositionLine,
    bidModeLabel,
    BLOCKING_REPORT_WARNING_PATTERN,
    blockingIssues,
    buildClientFallbackOutline,
    buildEvidenceSecondLevelChildren,
    buildEvidenceThirdLevelChildren,
    buildExportOutline,
    buildItemSections,
    buildProjectSummary,
    buildScoringRows,
    buildSourcePreviewBlock,
    buildTenderParseTabs,
    buildWordPreviewStyle,
    busy,
    busyPercent,
    busyText,
    checkingHistoryRequirements,
    clampProgress,
    cleanDisplayTitle,
    clearReferenceProfileFromDraft,
    CLIENT_GENERATION_FALLBACKS_ENABLED,
    closeOutlineEditor,
    collectAutoOutlineBasis,
    collectEntries,
    collectRequirementLines,
    compactOutlineTitle,
    completedLeaves,
    completeProgress,
    configOpen,
    consistencyReport,
    contextualThirdLevelPlans,
    controlAnalysisTask,
    countMapped,
    countNodes,
    coverage,
    currentPage,
    DEFAULT_WORD_STYLE_PROFILE,
    deleteOutlineItem,
    displayDocumentBlocksPlan,
    docPreviewRef,
    docStageRef,
    documentBlocksPlan,
    editingOutlineId,
    editingOutlineItem,
    effectiveOutline,
    effectiveScoringIds,
    EMPTY_REFERENCE_PROFILE,
    ensureOutlineThirdLevel,
    entries,
    estimateSourcePreviewBlockUnits,
    evidenceHighlighted,
    evidencePanelRef,
    exportDirectory,
    exportWord,
    extractJsonPayload,
    extractOutlinePhrases,
    failProgress,
    FALLBACK_SECOND_LEVEL_TITLES,
    FALLBACK_THIRD_LEVEL_TITLES,
    fileInputRef,
    findFieldInText,
    findFirstLeaf,
    findOutlineItem,
    findSourceLineIndex,
    findSourceLineIndexByText,
    fixedRequirementBlock,
    flattenOutlineDraftRows,
    FLOW_STEPS,
    flowIndex,
    generateChapter,
    generatedVisualCount,
    generationAbortRef,
    generationControl,
    generationPausedRef,
    generationProgress,
    generationStoppedRef,
    getBlockingAnalysisReportWarning,
    getRequirementCheckForItem,
    goToPage,
    handleAddOutlineChild,
    handleDeleteOutlineItem,
    handleModeChange,
    handleReferenceSelect,
    handleUpload,
    handleWorkflowAction,
    hasContentInChildren,
    hasParsedDocumentText,
    hasReferenceProfile,
    historyOpen,
    historyRecords,
    historyRequirementCheckList,
    historyRequirementChecks,
    historyRequirementSummary,
    infoIssues,
    isGeneratedMediaTitle,
    isGeneratedSecondLevelGroup,
    isGeneratedThirdLevelGroup,
    isInternalBidDocumentId,
    isMeaningfulValue,
    isPlaceholderOutlineChild,
    isRepeatedThirdLevelGroup,
    isScoringParseTab,
    isUsableReferenceProfile,
    lineOrMissing,
    linesOrMissing,
    listCount,
    localConfig,
    locateSourceItem,
    makeFallbackOutlineNode,
    manualReviewConfirmed,
    markdownImagePattern,
    markdownTableDividerPattern,
    matchedHistoryCase,
    MISSING_PARSE_TEXT,
    modelRuntime,
    NAV_ITEMS,
    navCollapsed,
    normalizeBidMode,
    normalizeCssValue,
    normalizeSourceText,
    notice,
    openAssetsWorkspace,
    openOutlineEditor,
    outlineDraftRows,
    outlineEditorForm,
    outlineErrorText,
    outlineMatchTokens,
    outlineReferenceProfile,
    outlineTextMatches,
    pageErrorText,
    paginateSourcePreviewBlocks,
    parseJsonPayload,
    parseOutlineDraftRows,
    pauseGeneration,
    pickEvidence,
    plannedBlockGroups,
    plannedBlocksCount,
    profileRecord,
    progress,
    project,
    projectTitle,
    rawReferenceProfile,
    referenceFile,
    referenceFileName,
    referenceImageSlots,
    referenceInputRef,
    referenceProfile,
    referenceProfileStats,
    referenceWordStyle,
    refreshHistory,
    renderedBlockStyle,
    renderedSourcePages,
    renderRequirementMatchIcon,
    reportReferenceProfile,
    reportSourceItems,
    requirementLine,
    resetGenerationControls,
    responseMatrixItems,
    restoreDraft,
    restoreHistoryRecord,
    resumeGeneration,
    reviewCoverage,
    reviewReport,
    runAnalysis,
    runBatch,
    runConsistencyRevision,
    runCurrentChapter,
    runDocumentBlocksPlan,
    runHistoryReferenceMatch,
    runHistoryRequirementCheck,
    runOutline,
    runReferenceAnalysis,
    runReview,
    runtimeEvent,
    runtimeStatus,
    runtimeStatusText,
    runVisualAssetGeneration,
    saveConfig,
    saveGeneratedContent,
    saveOutlineEditor,
    scoreSourceNodeMatch,
    scrollDocumentStageTo,
    scrollToDocumentNode,
    SECOND_LEVEL_TITLE_CATALOG,
    selectedBidMode,
    selectedEntry,
    selectedReferenceSlot,
    selectParseSection,
    setActiveDocId,
    setActiveNav,
    setActiveParseSectionId,
    setActiveParseTabKey,
    setActiveReferenceSlotIndex,
    setActiveRenderedSourceBlock,
    setActiveSourceLabel,
    setActiveSourceQuery,
    setAnalysisControl,
    setAnalysisRevealPercent,
    setAnalysisTaskId,
    setAvailableModels,
    setBusy,
    setCheckingHistoryRequirements,
    setConfigOpen,
    setConsistencyReport,
    setContentStreamText,
    setDocumentBlocksPlan,
    setEditingOutlineId,
    setError,
    setEvidenceHighlighted,
    setExportDirectory,
    setGenerationControl,
    setGenerationProgress,
    setHistoryOpen,
    setHistoryRecords,
    setHistoryRequirementChecks,
    setHistoryRequirementSummary,
    setInfo,
    setLocalConfig,
    setManualReviewConfirmed,
    setMatchedHistoryCase,
    setModelRuntime,
    setNavCollapsed,
    setNotice,
    setOutlineDraftRows,
    setOutlineEditorForm,
    setProgress,
    setReferenceFile,
    setReferenceFileName,
    setReferenceProfile,
    setReviewReport,
    setSelectedBidMode,
    setSourceLocateResult,
    setStreamingChapterId,
    setStreamText,
    setSuccess,
    setUploadedFileName,
    setVerifyResult,
    setVisualAssetResults,
    sourceItemDescription,
    sourceItemTitle,
    sourceLines,
    sourceLocateResult,
    sourcePanelStatusText,
    sourcePreviewBlocks,
    sourcePreviewPages,
    sourceSearchTokens,
    sourceSearchTokensForLocate,
    sourceSearchTokensFromText,
    sourceTextOverlapScore,
    sourceTokenFragments,
    sourceTokenParts,
    splitScoringSubitems,
    startProgress,
    state,
    stopGeneration,
    stopProgress,
    streamingChapterId,
    streamText,
    stripPreviewInlineMarkup,
    summarizeAnalysisReport,
    summarizeRequirementsFromReport,
    syncGenerationProgress,
    syncModels,
    tenderParseProgress,
    tenderParseReady,
    tenderParseTabs,
    tenderRevealVisible,
    THIRD_LEVEL_TITLE_CATALOG,
    thirdLevelPattern,
    toggleHistoryPanel,
    toLiteLLMConfig,
    toRecordItems,
    toText,
    uncoveredMatrixCount,
    uniqueTexts,
    updateAnalysisResults,
    updateAnalysisStage,
    updateConfig,
    updateFileContent,
    updateOutline,
    updateOutlineItem,
    updateSelectedChapter,
    uploadedFileName,
    verifyConfig,
    verifyResult,
    visualAssetResults,
    visualBlocksByChapter,
    visualBlocksCount,
    waitIfGenerationPaused,
    warningIssues,
    wordPreviewStyle,
    workflowStatus,
  } = controller;

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
            return (
              <button
                key={item.key}
                type="button"
                className={`ops-nav__item ${active ? 'ops-nav__item--active' : ''}`}
                onClick={() => handleWorkflowAction(item)}
                title={navCollapsed ? item.label : undefined}
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
            <span>{entries.length ? `已生成 ${completedLeaves}/${entries.length} 章节` : '等待模型生成目录'}</span>
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
          <div className="ops-project-title">
            <span>项目：</span>
            <strong>{projectTitle}</strong>
            <ChevronDownIcon className="h-4 w-4" />
          </div>
          <div className="ops-topbar__center">
            <span>生成模式：</span>
            <select
              className="ops-mode-select"
              value={selectedBidMode}
              onChange={(event) => handleModeChange(event.target.value as BidMode)}
              aria-label="生成模式"
            >
              {BID_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span>当前模型：</span>
            <strong>{state.config.model_name || '未选择模型'}</strong>
            <span
              className={`model-runtime-pill model-runtime-pill--${modelRuntime?.active ? 'running' : runtimeStatus === 'error' ? 'error' : runtimeStatus === 'success' ? 'success' : 'idle'}`}
              title={runtimeEvent?.message || runtimeStatusText}
            >
              <i aria-hidden="true" />
              {runtimeStatusText}
            </span>
          </div>
          <div className="ops-topbar__status">
            <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
            <span>已保存草稿</span>
            <button type="button" className="ops-icon-button" onClick={() => setConfigOpen(true)}>
              <Cog6ToothIcon className="h-4 w-4" />
              模型配置
            </button>
          </div>
        </header>

        <div className="ops-body ops-body--page">
          <section className="ops-page">
            {currentPage === 'project' && <ProjectPage controller={controller} />}

            {currentPage === 'analysis' && <AnalysisPage controller={controller} />}

            {currentPage === 'outline' && <OutlinePage controller={controller} />}

            {currentPage === 'assets' && <AssetsPage controller={controller} />}

            {currentPage === 'content' && <ContentPage controller={controller} />}

            {currentPage === 'review' && <ReviewPage controller={controller} />}
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

      {busy && (
        <div className="busy-bar">
          <div className="busy-bar__head">
            <SparklesIcon className="h-4 w-4" />
            <span>{busyText}</span>
            <strong>{busyPercent}%</strong>
          </div>
          <div className="busy-bar__track">
            <span style={{ width: `${busyPercent}%` }} />
          </div>
        </div>
      )}
    </div>
  );
};
