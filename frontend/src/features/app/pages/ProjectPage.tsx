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

  return (
    <>
                    <div className="ops-page-grid ops-page-grid--upload">
                      <div className="ops-panel">
                        <h2>上传招标文件</h2>
                        <div
                          className="upload-zone upload-zone--large upload-zone--native"
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => {
                            event.preventDefault();
                            const file = event.dataTransfer.files?.[0];
                            if (file) handleUpload(file);
                          }}
                        >
                          <DocumentArrowUpIcon className="h-12 w-12" />
                          <strong>选择 PDF 或 DOCX 招标文件</strong>
                          <span>点击下面的系统文件按钮，或把文件拖到这里。</span>
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
                          <span>文件大小限制在 500MB 以下，上传后系统会读取全文并复用同一份解析结果。</span>
                        </div>
                        <div className="file-pill">
                          <DocumentTextIcon className="h-5 w-5 text-rose-600" />
                          <div>
                            <strong>{uploadedFileName || '等待上传招标文件'}</strong>
                            <span>{state.fileContent ? '已上传并读取文本' : '待上传'}</span>
                          </div>
                          {state.fileContent && <CheckCircleIcon className="h-5 w-5 text-emerald-600" />}
                        </div>
                      </div>
    
                    <div className="ops-panel">
                      <h2>上传成熟样例</h2>
                      <button
                        type="button"
                        className="upload-zone"
                        onClick={runHistoryReferenceMatch}
                        disabled={!state.fileContent || busy === 'reference-match' || busy === 'reference'}
                      >
                        <SparklesIcon className="h-8 w-8" />
                        <strong>自动匹配历史案例库</strong>
                        <span>根据当前招标文件，从 157 个历史项目和 251 份标书中召回候选，用 LLM 选择最合适案例并生成成熟样例模板。</span>
                      </button>
                      <div
                        className="upload-zone upload-zone--native"
                        onDragOver={(event) => event.preventDefault()}
                        onDrop={(event) => {
                          event.preventDefault();
                          const file = event.dataTransfer.files?.[0];
                          if (file) handleReferenceSelect(file);
                        }}
                      >
                        <DocumentArrowUpIcon className="h-8 w-8" />
                        <strong>选择 PDF 或 DOCX 样例标书</strong>
                        <span>点击下面的系统文件按钮，或把文件拖到这里。</span>
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
                        <span>先选择文件，点击“去解析”后抽取目录、段落骨架、表格、承诺书和素材位。</span>
                      </div>
                      <div className="file-pill">
                        <DocumentTextIcon className="h-5 w-5 text-sky-600" />
                        <div>
                          <strong>{referenceFileName || '未接入写作模板'}</strong>
                          <span>
                            {busy === 'reference-match'
                              ? '历史案例匹配中'
                              : busy === 'reference'
                                ? '样例解析中'
                              : hasReferenceProfile
                                ? matchedHistoryCase
                                  ? `已匹配：${matchedHistoryCase.primary_domain || '历史案例'}`
                                  : '样例写作模板已生成'
                                : referenceFile
                                  ? '已选择，待解析'
                                  : '可自动匹配，也可手动上传成熟目标文件'}
                          </span>
                        </div>
                        {hasReferenceProfile ? <CheckCircleIcon className="h-5 w-5 text-emerald-600" /> : null}
                      </div>
                      <div className="page-action-row">
                        <button type="button" className="solid-button" onClick={runReferenceAnalysis} disabled={!referenceFile || busy === 'reference'}>
                          {busy === 'reference' ? '解析中' : hasReferenceProfile ? '重新解析' : '去解析'}
                        </button>
                        <button type="button" onClick={runHistoryReferenceMatch} disabled={!state.fileContent || busy === 'reference-match'}>
                          {busy === 'reference-match' ? '匹配中' : '自动匹配'}
                        </button>
                      </div>
                    </div>
    
                    <div className="ops-panel reference-profile-panel">
                      <div className="ops-panel__head">
                        <h2>成熟样例模板</h2>
                        <span className="text-link">{busy === 'reference' ? '解析中' : hasReferenceProfile ? '已生成' : '未接入'}</span>
                      </div>
                      {!hasReferenceProfile ? (
                        <div className="empty-state empty-state--compact">
                          <strong>{busy === 'reference' ? '正在解析成熟样例' : referenceFile ? '已选择样例，待解析' : '上传成熟样例后生成'}</strong>
                          <span>{referenceFile ? '点击左侧“去解析”后，这里会填充样例的目录层级、章节骨架、Word 字号字体、表格和素材位。' : '这里会展示样例的目录层级、章节骨架、Word 字号字体、表格和素材位，不再显示招标项目占位字段。'}</span>
                        </div>
                      ) : (
                        <>
                          <div className="reference-profile-summary">
                            <strong>{String(activeReferenceRecord.profile_name || referenceFileName || '成熟样例写作模板')}</strong>
                            <span>{String(activeReferenceRecord.recommended_use_case || '用于后续目录、正文、表格和审校模板复用。')}</span>
                          </div>
                          <div className="info-row"><span>样例范围</span><strong>{String(activeReferenceRecord.document_scope || 'unknown')}</strong></div>
                          {matchedHistoryCase ? (
                            <>
                              <div className="info-row"><span>历史案例</span><strong>{String(matchedHistoryCase.project_title || '已匹配')}</strong></div>
                              <div className="info-row"><span>匹配领域</span><strong>{String(matchedHistoryCase.primary_domain || '未标明')}</strong></div>
                            </>
                          ) : null}
                          {referenceProfileStats.map(([label, value]) => (
                            <div key={label} className="info-row"><span>{label}</span><strong>{value}</strong></div>
                          ))}
                          <div className="reference-style-grid">
                            <span>正文 {String(referenceWordStyle.body_font_family || DEFAULT_WORD_STYLE_PROFILE.body_font_family)} / {String(referenceWordStyle.body_font_size || DEFAULT_WORD_STYLE_PROFILE.body_font_size)}</span>
                            <span>标题 {String(referenceWordStyle.heading_font_family || DEFAULT_WORD_STYLE_PROFILE.heading_font_family)} / {String(referenceWordStyle.heading_1_size || DEFAULT_WORD_STYLE_PROFILE.heading_1_size)}</span>
                            <span>页边距 {String(referenceWordStyle.margin_top || DEFAULT_WORD_STYLE_PROFILE.margin_top)} · {String(referenceWordStyle.margin_left || DEFAULT_WORD_STYLE_PROFILE.margin_left)}</span>
                            <span>表格 {String(referenceWordStyle.table_font_size || DEFAULT_WORD_STYLE_PROFILE.table_font_size)}</span>
                          </div>
                        </>
                      )}
                    </div>
    
                    <div className="ops-panel">
                      <div className="ops-panel__head">
                        <h2>企业资料画像</h2>
                        <span>{activeReport ? `待补 ${(activeEnterpriseProfile?.missing_materials || activeReport.missing_company_materials || []).length} 项` : '待解析'}</span>
                      </div>
                      {activeReport ? (
                        (activeEnterpriseProfile?.missing_materials || activeReport.missing_company_materials || []).length ? (
                          <>
                            {activeEnterpriseProfile?.summary ? <div className="field-hint">{activeEnterpriseProfile.summary}</div> : null}
                            {(activeEnterpriseProfile?.missing_materials || activeReport.missing_company_materials || []).slice(0, 8).map(item => (
                            <div key={item.id} className="warning-row">
                              <ExclamationTriangleIcon className="h-4 w-4 text-amber-500" />
                              <span>{item.name}</span>
                              <strong>待补充</strong>
                            </div>
                            ))}
                          </>
                        ) : (
                          <div className="empty-state empty-state--compact">
                            <strong>未识别出缺失材料</strong>
                            <span>企业资料已独立成画像，仍需在审校阶段核验证据链和原件一致性。</span>
                          </div>
                        )
                      ) : (
                        <div className="empty-state empty-state--compact">
                          <strong>完成标准解析后显示</strong>
                          <span>企业资料画像会独立归纳已提供、待补和人工核验任务。</span>
                        </div>
                      )}
                    </div>
                    </div>
    
                    <div className="upload-final-action">
                      <div>
                        <strong>进入标准解析</strong>
                        <span>确认招标文件、成熟样例和资料状态后，再进入条款识别与评分项抽取。</span>
                      </div>
                      <button type="button" className="solid-button" onClick={() => goToPage('analysis')} disabled={!state.fileContent}>
                        去解析
                      </button>
                    </div>
                  </>
  );
};
