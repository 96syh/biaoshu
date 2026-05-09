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

export const ContentPage = ({ controller }: PageProps) => {
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
    <div className="word-workspace">
                    <aside className="word-toc-panel">
                      <div className="ops-panel__head">
                        <div>
                          <h2>目录</h2>
                          <span>{effectiveOutline ? `已生成 ${completedLeaves}/${entries.length} 章` : '等待目录'}</span>
                        </div>
                        <button type="button" className="text-link" onClick={() => goToPage('outline')}>查看目录页</button>
                      </div>
                      {effectiveOutline ? (
                        <div className="word-toc">
                          {effectiveOutline.outline.map(section => (
                            <DocumentTocRows
                              key={section.id}
                              item={section}
                              activeId={activeDocId || selectedEntry?.item.id}
                              onSelect={scrollToDocumentNode}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state empty-state--compact">
                          <strong>等待目录生成</strong>
                          <span>生成目录后，这里会显示可选择的章节。</span>
                        </div>
                      )}
                    </aside>
    
                    <div className="word-editor-panel">
                      <div className="preview-actions">
                        <button type="button" className="solid-button" onClick={runCurrentChapter} disabled={!selectedEntry || busy.startsWith('chapter')}>
                          <PlayIcon className="h-4 w-4" /> 生成本章
                        </button>
                        <button type="button" onClick={runBatch} disabled={!effectiveOutline || busy === 'batch'}>批量生成</button>
                        {(busy.startsWith('chapter') || busy === 'batch') && (
                          <div className="generation-controls">
                            {generationControl === 'paused' ? (
                              <button type="button" onClick={resumeGeneration}><PlayIcon className="h-4 w-4" /> 继续</button>
                            ) : (
                              <button type="button" onClick={pauseGeneration}><PauseIcon className="h-4 w-4" /> 暂停</button>
                            )}
                            <button type="button" className="danger-button" onClick={stopGeneration}><StopIcon className="h-4 w-4" /> 停止</button>
                          </div>
                        )}
                        <button type="button" onClick={exportWord} disabled={!effectiveOutline || busy === 'export' || !manualReviewConfirmed}>
                          <ArrowDownTrayIcon className="h-4 w-4" /> 导出 Word
                        </button>
                      </div>
                      <label className="manual-review-control">
                        <input
                          type="checkbox"
                          checked={manualReviewConfirmed}
                          onChange={event => setManualReviewConfirmed(event.target.checked)}
                        />
                        <span>已人工复核模型结果、缺失材料、页码目录、版式、签章位置、图表占位和固定格式风险。</span>
                      </label>
                      <label className="export-path-control">
                        <span>保存目录</span>
                        <input
                          value={exportDirectory}
                          onChange={event => setExportDirectory(event.target.value)}
                          placeholder="例如 ~/Downloads 或 /Users/songyuheng/Desktop"
                        />
                      </label>
                      {generationProgress && (
                        <div className="content-progress-strip">
                          <TaskProgress progress={generationProgress} />
                        </div>
                      )}
                      <div ref={docStageRef} className="word-document-stage">
                        <div className="word-ruler" aria-hidden="true">
                          <span />
                          <i />
                          <span />
                        </div>
                        <article ref={docPreviewRef} className="word-document" style={wordPreviewStyle}>
                          {effectiveOutline ? (
                            <>
                              <div className="word-document__cover">
                                <h1>投标文件</h1>
                                <p>项目名称：{effectiveOutline.project_name || project?.name || '〖待补充：项目名称〗'}</p>
                                <p>投标人：〖待补充：投标人名称〗（盖单位章）</p>
                                <p>日期：〖待补充：投标日期〗</p>
                              </div>
                              {effectiveOutline.outline.map(section => (
                                <DocumentPreviewNode
                                  key={section.id}
                                  item={section}
                                  level={1}
                                  activeId={activeDocId || selectedEntry?.item.id}
                                  streamingId={streamingChapterId}
                                  onSelect={scrollToDocumentNode}
                                  visualBlocksByChapter={visualBlocksByChapter}
                                />
                              ))}
                            </>
                          ) : (
                            <div className="word-empty-page">
                              <strong>等待目录生成</strong>
                              <span>正文区不会显示示例文本；生成目录并选择章节后，再调用模型写入正式内容。</span>
                            </div>
                          )}
                        </article>
                      </div>
                    </div>
                  </div>
  );
};
