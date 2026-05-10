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

export const ReviewPage = ({ controller }: PageProps) => {
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
    <div className="review-panel review-panel--page">
                    <div className="ops-panel__head">
                      <h2>合规审校</h2>
                      <div className="outline-actions">
                        <button type="button" className="text-link" onClick={() => runConsistencyRevision()} disabled={!effectiveOutline || busy === 'consistency'}>
                          {busy === 'consistency' ? '检查中' : '一致性修订'}
                        </button>
                        <button type="button" className="text-link" onClick={runReview} disabled={!effectiveOutline || completedLeaves === 0 || busy === 'review'}>{busy === 'review' ? '审校中' : '执行审校'}</button>
                      </div>
                    </div>
                    <div className="review-metrics">
                      <Metric label="覆盖率" value={reviewCoverage === null ? '--' : `${reviewCoverage}%`} tone="green" />
                      <Metric label="阻塞问题" value={blockingIssues === null ? '--' : `${blockingIssues}`} tone="red" />
                      <Metric label="警告问题" value={warningIssues === null ? '--' : `${warningIssues}`} tone="amber" />
                      <Metric label="提示信息" value={infoIssues === null ? '--' : `${infoIssues}`} tone="blue" />
                    </div>
                    <div className="issue-list">
                      {reviewReport ? (
                        [
                          ...(reviewReport.blocking_issues || []),
                          ...(reviewReport.warnings || []),
                          ...reviewReport.fixed_format_issues,
                          ...reviewReport.signature_issues,
                          ...reviewReport.price_rule_issues,
                          ...reviewReport.evidence_chain_issues,
                          ...reviewReport.page_reference_issues,
                          ...(reviewReport.anonymity_issues || []),
                        ].length ? (
                          [
                            ...(reviewReport.blocking_issues || []),
                            ...(reviewReport.warnings || []),
                            ...reviewReport.fixed_format_issues,
                            ...reviewReport.signature_issues,
                            ...reviewReport.price_rule_issues,
                            ...reviewReport.evidence_chain_issues,
                            ...reviewReport.page_reference_issues,
                            ...(reviewReport.anonymity_issues || []),
                          ].map(item => ({
                            level: item.blocking ? '阻塞' : '警告',
                            text: item.issue,
                            chapter: item.chapter_ids.join('、') || '全篇',
                            suggestion: item.fix_suggestion,
                          })).map((issue, index) => (
                            <div key={`${issue.text}-${index}`} className="issue-row">
                              <span className={`issue-tag issue-tag--${issue.level === '阻塞' ? 'red' : 'amber'}`}>{issue.level}</span>
                              <strong>{issue.text}</strong>
                              <em>{issue.chapter}</em>
                              {issue.suggestion && <small>{issue.suggestion}</small>}
                            </div>
                          ))
                        ) : (
                          <div className="empty-state empty-state--compact">
                            <strong>未发现阻塞或警告项</strong>
                            <span>当前结果来自模型审校报告，可继续导出前复核。</span>
                          </div>
                        )
                      ) : (
                        <div className="review-ready-block">
                          <div className="review-ready-block__icon">
                            <ShieldCheckIcon className="h-7 w-7" />
                          </div>
                          <div className="review-ready-block__copy">
                            <strong>待执行合规审校</strong>
                            <span>模型会检查正文覆盖率、阻塞条款、固定格式、签章、报价和证据链风险。</span>
                            <div className="review-ready-block__checks">
                              <em className={effectiveOutline ? 'ready' : ''}>目录结构</em>
                              <em className={completedLeaves > 0 ? 'ready' : ''}>正文内容</em>
                              <em className={activeReport ? 'ready' : ''}>解析报告</em>
                            </div>
                          </div>
                          <button type="button" className="solid-button" onClick={runReview} disabled={!effectiveOutline || completedLeaves === 0 || busy === 'review'}>
                            {busy === 'review' ? '审校中' : '执行审校'}
                          </button>
                        </div>
                      )}
                    </div>
                    {reviewReport?.revision_plan?.actions.length ? (
                      <div className="revision-plan">
                        <div className="ops-panel__head">
                          <h3>修订计划</h3>
                          <span>{reviewReport.revision_plan.actions.length} 项待处理</span>
                        </div>
                        <p>{reviewReport.revision_plan.summary || reviewReport.summary.blocking_summary}</p>
                        {reviewReport.revision_plan.actions.slice(0, 6).map(action => (
                          <div key={action.id} className="revision-action">
                            <strong>{action.action_type || '修订'}</strong>
                            <span>{action.instruction}</span>
                            <em>{action.target_chapter_ids.join('、') || '全篇'}</em>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {consistencyReport ? (
                      <div className="revision-plan">
                        <div className="ops-panel__head">
                          <h3>全文一致性修订</h3>
                          <span>{consistencyReport.issues?.length || 0} 项问题</span>
                        </div>
                        <p>
                          阻塞 {consistencyReport.summary?.blocking_count || 0} 项，
                          高风险 {consistencyReport.summary?.high_count || 0} 项。
                        </p>
                        {(consistencyReport.issues || []).slice(0, 8).map(issue => (
                          <div key={issue.id} className="revision-action">
                            <strong>{issue.severity}</strong>
                            <span>{issue.problem || issue.fix_suggestion}</span>
                            <em>{issue.chapter_id || '全篇'}</em>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
  );
};
