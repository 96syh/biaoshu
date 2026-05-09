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

export const OutlinePage = ({ controller }: PageProps) => {
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
    <div className="ops-page-stack">
                    <div className="flow-panel">
                      {FLOW_STEPS.map((step, index) => (
                        <div key={step} className={`flow-step ${index <= flowIndex ? 'flow-step--done' : ''}`}>
                          <span>{index <= flowIndex ? <CheckCircleIcon className="h-4 w-4" /> : index + 1}</span>
                          <strong>{step}</strong>
                        </div>
                      ))}
                      <button type="button" className="solid-button" onClick={runOutline} disabled={busy === 'outline' || !state.analysisReport}>生成目录</button>
                    </div>
                    <div className="outline-panel">
                      <div className="ops-panel__head">
                        <div>
                          <h2>目录结构与评分项映射</h2>
                          <span>{effectiveOutline ? `共 ${countNodes(effectiveOutline.outline)} 章，已映射 ${countMapped(effectiveOutline.outline)} 项` : '等待模型生成目录和映射'}</span>
                        </div>
                        <div className="outline-actions">
                          {effectiveOutline && <button type="button" className="solid-button" onClick={() => goToPage('content')}>去生成正文</button>}
                          <button type="button" onClick={openAssetsWorkspace} disabled={!effectiveOutline || !state.analysisReport}>
                            {busy === 'blocks' ? '规划中' : '图表素材规划'}
                          </button>
                          <button type="button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>智能建议</button>
                          <button type="button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>{effectiveOutline ? '重新生成' : '生成目录'}</button>
                        </div>
                      </div>
                      {Object.keys(displayDocumentBlocksPlan || {}).length ? (
                        <div className="field-hint">
                          文档块规划已接入：{((displayDocumentBlocksPlan as any).document_blocks || []).length || 0} 个表格/图片/承诺书块，
                          导出 Word 时会生成可替换占位。
                        </div>
                      ) : (
                        <div className="field-hint">目录生成后可单独执行图表素材规划，补齐表格、流程图、组织架构图、图片和承诺书位置。</div>
                      )}
                      {busy === 'outline' && <TaskProgress progress={progress} />}
                      {activeResponseMatrix && (
                        <div className="matrix-strip">
                          <strong>响应矩阵</strong>
                          <span>{activeResponseMatrix.coverage_summary || `共 ${responseMatrixItems.length} 项，待覆盖 ${uncoveredMatrixCount} 项`}</span>
                        </div>
                      )}
                      {editingOutlineItem && (
                        <div className="outline-edit-panel">
                          <div className="outline-edit-panel__head">
                            <div>
                              <strong>编辑目录节点</strong>
                              <span>修改会直接进入当前草稿，并用于后续正文生成。</span>
                            </div>
                            <button type="button" className="ops-icon-button" onClick={closeOutlineEditor} aria-label="关闭编辑面板">
                              <XMarkIcon className="h-4 w-4" />
                            </button>
                          </div>
                          <div className="outline-edit-grid">
                            <label className="outline-edit-field">
                              <span>编号</span>
                              <input value={outlineEditorForm.id} disabled />
                            </label>
                            <label className="outline-edit-field">
                              <span>标题</span>
                              <input
                                value={outlineEditorForm.title}
                                onChange={event => setOutlineEditorForm(prev => ({ ...prev, title: event.target.value }))}
                                placeholder="请输入章节标题"
                              />
                            </label>
                            <label className="outline-edit-field outline-edit-field--wide">
                              <span>写作说明</span>
                              <textarea
                                value={outlineEditorForm.description}
                                onChange={event => setOutlineEditorForm(prev => ({ ...prev, description: event.target.value }))}
                                rows={3}
                                placeholder="补充本章写作范围、响应重点、材料要求"
                              />
                            </label>
                          </div>
                          <div className="outline-edit-actions">
                            <button type="button" onClick={() => handleAddOutlineChild(editingOutlineItem)}>新增子级</button>
                            <button type="button" className="danger-text-button" onClick={() => handleDeleteOutlineItem(editingOutlineItem)}>删除节点</button>
                            <button type="button" className="solid-button" onClick={saveOutlineEditor}>保存修改</button>
                          </div>
                        </div>
                      )}
                      {effectiveOutline ? (
                        <div className="outline-table outline-table--page">
                          <div className="outline-table__head">
                            <span>章节名称</span><span>操作</span><span>评分项映射</span><span>风险</span><span>材料</span>
                          </div>
                          {effectiveOutline.outline.map(section => (
                            <OutlineRows
                              key={section.id}
                              item={section}
                              report={activeReport}
                              selectedId={selectedEntry?.item.id}
                              editingId={editingOutlineId}
                              onSelect={updateSelectedChapter}
                              onEdit={openOutlineEditor}
                              onAddChild={handleAddOutlineChild}
                              onDelete={handleDeleteOutlineItem}
                              getScoringIds={effectiveScoringIds}
                            />
                          ))}
                        </div>
                      ) : (
                        busy === 'outline' ? (
                          <OutlineDraftPreview rows={outlineDraftRows} />
                        ) : (
                          <div className={`empty-state ${outlineErrorText ? 'empty-state--error' : ''}`}>
                            <strong>{outlineErrorText ? '目录生成失败' : '目录还没有生成'}</strong>
                            <span>
                              {outlineErrorText || '完成标准解析后，点击“生成目录”，后端会把招标结构、评分项、风险和材料要求映射到章节。'}
                            </span>
                            <button type="button" className="solid-button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>
                              {outlineErrorText ? '重新调用模型生成目录' : '调用模型生成目录'}
                            </button>
                          </div>
                        )
                      )}
                    </div>
                  </div>
  );
};
