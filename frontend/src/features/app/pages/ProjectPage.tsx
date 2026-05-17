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
import { LITELLM_PROVIDER } from '../../../constants/providers';
import { BidMode } from '../../../types';
import { blockAssetKey, blockTypeLabel, isVisualBlockType, visualAssetResultFromBlock } from '../../../utils/visualAssets';
import { ReferenceSlotPreview } from '../../assets/ReferenceSlotPreview';
import { ReferenceSlotShowcase } from '../../assets/ReferenceSlotShowcase';
import { DocumentPreviewNode } from '../../content/DocumentPreviewNode';
import { DocumentTocRows } from '../../content/DocumentTocRows';
import { VerifyLine } from '../../config/VerifyLine';
import { OutlineDraftPreview } from '../../outline/OutlineDraftPreview';
import { OutlineRows } from '../../outline/OutlineRows';
import { Metric } from '../../review/Metric';
import { TaskProgress } from '../../shared/TaskProgress';
import type { BidWorkspaceController } from '../useBidWorkspaceController';

type PageProps = {
  controller: BidWorkspaceController;
};

export const ProjectPage = ({ controller }: PageProps) => {
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

  const referenceStatusText = busy === 'reference-match'
    ? '正在自动匹配'
    : busy === 'reference'
      ? '正在解析样例'
      : hasReferenceProfile
        ? matchedHistoryCase
          ? `已匹配：${matchedHistoryCase.primary_domain || '历史案例'}`
          : '参考模板已生成'
        : referenceFile
          ? '已选择样例，待解析'
          : '可选补充成熟标书';
  const referenceTableRows = [
    {
      group: '匹配来源',
      item: '范本名称',
      result: String(activeReferenceRecord.profile_name || referenceFileName || '成熟样例写作模板'),
      usage: '确定正文结构与写作口径',
    },
    {
      group: '匹配来源',
      item: '适用场景',
      result: String(activeReferenceRecord.recommended_use_case || '用于目录框架、正文风格、表格版式与审校口径参考。'),
      usage: '作为本项目响应策略参考',
    },
    {
      group: '匹配来源',
      item: '样例范围',
      result: String(activeReferenceRecord.document_scope || 'unknown'),
      usage: '界定可复用内容边界',
    },
    ...(matchedHistoryCase ? [
      {
        group: '历史案例',
        item: '匹配项目',
        result: String(matchedHistoryCase.project_title || '已匹配'),
        usage: '优先复用相近项目经验',
      },
      {
        group: '历史案例',
        item: '匹配领域',
        result: String(matchedHistoryCase.primary_domain || '未标明'),
        usage: '对齐行业术语与技术口径',
      },
    ] : []),
    ...referenceProfileStats.map(([label, value]) => ({
      group: '结构模板',
      item: label,
      result: value,
      usage: label.includes('目录')
        ? '生成目录层级'
        : label.includes('章')
          ? '组织章节骨架'
          : label.includes('表格')
            ? '套用表格版式'
            : '补齐素材位置',
    })),
    {
      group: '版式规范',
      item: '正文字体',
      result: `${String(referenceWordStyle.body_font_family || DEFAULT_WORD_STYLE_PROFILE.body_font_family)} / ${String(referenceWordStyle.body_font_size || DEFAULT_WORD_STYLE_PROFILE.body_font_size)}`,
      usage: '统一正文排版',
    },
    {
      group: '版式规范',
      item: '标题层级',
      result: `${String(referenceWordStyle.heading_font_family || DEFAULT_WORD_STYLE_PROFILE.heading_font_family)} / ${String(referenceWordStyle.heading_1_size || DEFAULT_WORD_STYLE_PROFILE.heading_1_size)}`,
      usage: '统一章节标题',
    },
    {
      group: '版式规范',
      item: '页边距',
      result: `${String(referenceWordStyle.margin_top || DEFAULT_WORD_STYLE_PROFILE.margin_top)} · ${String(referenceWordStyle.margin_left || DEFAULT_WORD_STYLE_PROFILE.margin_left)}`,
      usage: '控制 Word 页面版心',
    },
    {
      group: '版式规范',
      item: '表格字体',
      result: String(referenceWordStyle.table_font_size || DEFAULT_WORD_STYLE_PROFILE.table_font_size),
      usage: '统一表格字号',
    },
  ];
  return (
    <>
                    <div className="upload-simple-layout">
                      <div className="ops-panel workflow-step-panel upload-primary-panel">
                        <div className="workflow-step-header">
                          <span className="workflow-step-number">1</span>
                          <div>
                            <div className="simple-step-label">必做 · 第一步</div>
                            <h2>上传招标文件</h2>
                            <p className="simple-panel-note">导入本项目招标文件，作为投标响应依据。</p>
                          </div>
                        </div>
                        <div className="workflow-step-main">
                          <div
                            className={`upload-zone upload-zone--large upload-zone--native ${state.fileContent ? 'upload-zone--done' : ''}`}
                            role="button"
                            tabIndex={0}
                            onClick={(event) => {
                              if (event.target instanceof HTMLInputElement) return;
                              fileInputRef.current?.click();
                            }}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                fileInputRef.current?.click();
                              }
                            }}
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={(event) => {
                              event.preventDefault();
                              const file = event.dataTransfer.files?.[0];
                              if (file) handleUpload(file);
                            }}
                          >
                            {state.fileContent ? <CheckCircleIcon className="h-12 w-12 text-emerald-600" /> : <DocumentArrowUpIcon className="h-12 w-12" />}
                            <strong>{state.fileContent ? '招标文件已导入' : '选择招标文件'}</strong>
                            <span>{state.fileContent ? '文件已导入，可进入案例匹配。' : '支持拖拽上传。'}</span>
                            <input
                              ref={fileInputRef}
                              type="file"
                              className="file-input-visible"
                              accept=".pdf,.docx"
                              aria-label="选择招标文件"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) handleUpload(file);
                                event.target.value = '';
                              }}
                            />
                            <span>文件大小不超过 500MB。</span>
                          </div>
                          <div className="file-pill file-pill--large">
                            <DocumentTextIcon className="h-5 w-5 text-rose-600" />
                            <div>
                              <strong>{uploadedFileName || '还没有选择文件'}</strong>
                              <span>{state.fileContent ? '已完成文件导入' : '待导入招标文件'}</span>
                            </div>
                            {state.fileContent && <CheckCircleIcon className="h-5 w-5 text-emerald-600" />}
                          </div>
                          <div className="upload-readiness-card">
                            <div>
                              <strong>{state.fileContent ? '招标文件已准备' : '等待招标文件'}</strong>
                              <span>{state.fileContent ? '请在第二步执行案例库智能比选。' : '导入后进入案例比选。'}</span>
                            </div>
                            <CheckCircleIcon className={`h-5 w-5 ${state.fileContent ? 'text-emerald-600' : 'text-slate-300'}`} />
                          </div>
                        </div>
                      </div>

                    <div className="ops-panel workflow-step-panel optional-sample-panel">
                      <div className="workflow-step-header">
                        <span className="workflow-step-number">2</span>
                        <div>
                          <span className="simple-step-label">推荐 · 第二步</span>
                          <h2>自动匹配历史案例</h2>
                          <p className="simple-panel-note">基于项目类型、评分办法与技术要求筛选可参考案例。</p>
                        </div>
                      </div>
                      <div className="workflow-step-main">
                        <div className="reference-match-hero">
                          <div className="reference-match-copy">
                            <span className="reference-match-icon"><SparklesIcon className="h-6 w-6" /></span>
                            <div>
                              <strong>优先进行案例库智能比选</strong>
                              <span>匹配相似项目范本，辅助确定目录框架、响应策略与素材口径。</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="sample-match-button sample-match-button--primary"
                            onClick={runHistoryReferenceMatch}
                            disabled={!state.fileContent || busy === 'reference-match' || busy === 'reference'}
                          >
                            <SparklesIcon className="h-5 w-5" />
                            <span>{busy === 'reference-match' ? '正在匹配历史案例' : '开始自动匹配'}</span>
                          </button>
                          {!state.fileContent ? <div className="field-hint reference-match-hint">导入招标文件后可启动案例比选。</div> : null}
                          <div className="file-pill reference-match-status">
                            <DocumentTextIcon className="h-5 w-5 text-sky-600" />
                            <div>
                              <strong>{referenceFileName || matchedHistoryCase?.project_title || (hasReferenceProfile ? '已接入参考案例' : '尚未匹配参考案例')}</strong>
                              <span>{referenceStatusText}</span>
                            </div>
                            {hasReferenceProfile ? <CheckCircleIcon className="h-5 w-5 text-emerald-600" /> : null}
                          </div>
                        </div>
                        <details className="optional-sample-box">
                          <summary>
                            <span className="optional-sample-box__icon">
                              <DocumentArrowUpIcon className="h-5 w-5" />
                            </span>
                            <span className="optional-sample-box__copy">
                              <span className="simple-step-label simple-step-label--optional">补充资料 · 可选</span>
                              <strong>上传成熟样例标书</strong>
                              <em>没有样例可跳过，不影响标准解析。</em>
                            </span>
                            <span className="optional-sample-box__action">点击上传</span>
                          </summary>
                          <div
                            className="upload-zone upload-zone--compact upload-zone--native"
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={(event) => {
                              event.preventDefault();
                              const file = event.dataTransfer.files?.[0];
                              if (file) handleReferenceSelect(file);
                            }}
                          >
                            <DocumentArrowUpIcon className="h-7 w-7" />
                            <strong>选择样例标书</strong>
                            <input
                              ref={referenceInputRef}
                              type="file"
                              className="file-input-visible"
                              accept=".pdf,.docx"
                              aria-label="选择样例标书"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) handleReferenceSelect(file);
                                event.target.value = '';
                              }}
                            />
                            <span>可选，支持 PDF 或 DOCX。</span>
                          </div>
                          {referenceFile ? <button type="button" className="ghost-action-button" onClick={runReferenceAnalysis} disabled={busy === 'reference'}>
                            {busy === 'reference' ? '正在解析样例' : hasReferenceProfile ? '重新解析样例' : '解析这个样例'}
                          </button> : null}
                        </details>
                      </div>
                    </div>

                    <div className="ops-panel workflow-step-panel parse-step-panel">
                      <div className="workflow-step-header">
                        <span className="workflow-step-number">3</span>
                        <div>
                          <div className="parse-step-kicker">
                            <span className="simple-step-label">必做 · 第三步</span>
                            <span className="parse-mode-pill">当前：{bidModeLabel(selectedBidMode)}</span>
                          </div>
                          <h2>标准解析</h2>
                          <p className="simple-panel-note">形成投标响应要点、评审规则、资格条件与偏离风险清单。</p>
                        </div>
                      </div>
                      <div className="workflow-step-main">
                        <div className="upload-next-action upload-next-action--parse">
                          <div>
                            <strong>{state.fileContent ? hasReferenceProfile ? '可开始标准化解析' : '建议先完成案例比选' : '等待导入招标文件'}</strong>
                            <span>{state.fileContent ? hasReferenceProfile ? '参考案例已接入，可进入响应要点梳理。' : '也可直接解析招标文件。' : '完成文件导入后开放。'}</span>
                          </div>
                          <button
                            type="button"
                            className="solid-button"
                            onClick={() => goToPage('analysis')}
                            disabled={!state.fileContent || busy === 'reference-match' || busy === 'reference'}
                          >
                            {state.fileContent ? '开始解析' : '等待上传'}
                          </button>
                        </div>
                        <div className="parse-deliverable-list">
                          <div className="parse-deliverable-item">
                            <span>01</span>
                            <strong>评审规则</strong>
                            <em>评分办法、分值权重、响应优先级</em>
                          </div>
                          <div className="parse-deliverable-item">
                            <span>02</span>
                            <strong>资格条件</strong>
                            <em>资质、业绩、人员与信誉要求</em>
                          </div>
                          <div className="parse-deliverable-item">
                            <span>03</span>
                            <strong>技术响应</strong>
                            <em>服务范围、实施要求、成果标准</em>
                          </div>
                          <div className="parse-deliverable-item">
                            <span>04</span>
                            <strong>风险条款</strong>
                            <em>偏离风险、承诺事项、关键时限</em>
                          </div>
                        </div>
                      </div>
                    </div>
    
                    {hasReferenceProfile ? <div className="ops-panel reference-profile-panel">
                      <div className="ops-panel__head">
                        <h2>参考范本画像</h2>
                        <span className="text-link">{busy === 'reference' ? '解析中' : hasReferenceProfile ? '已生成' : '未接入'}</span>
                      </div>
                      {!hasReferenceProfile ? (
                        <div className="empty-state empty-state--compact">
                          <strong>{busy === 'reference' ? '正在解析成熟样例' : referenceFile ? '已选择样例，待解析' : '上传成熟样例后生成'}</strong>
                          <span>{referenceFile ? '解析后生成目录层级、章节结构、版式规范与素材位置。' : '用于沉淀目录层级、章节结构、版式规范与素材位置。'}</span>
                        </div>
                      ) : (
                        <>
                          <div className="reference-profile-summary">
                            <strong>{String(activeReferenceRecord.profile_name || referenceFileName || '成熟样例写作模板')}</strong>
                            <span>{String(activeReferenceRecord.recommended_use_case || '用于目录框架、正文风格、表格版式与审校口径参考。')}</span>
                          </div>
                          <div className="reference-profile-table" role="table" aria-label="参考范本画像明细">
                            <div className="reference-profile-table__head" role="row">
                              <span>类别</span>
                              <span>项目</span>
                              <span>提取结果</span>
                              <span>用途</span>
                            </div>
                            {referenceTableRows.map((row, index) => (
                              <div className="reference-profile-table__row" role="row" key={`${row.group}-${row.item}-${index}`}>
                                <span>{row.group}</span>
                                <strong>{row.item}</strong>
                                <em>{row.result}</em>
                                <span>{row.usage}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div> : null}
    
                    </div>
                  </>
  );
};
