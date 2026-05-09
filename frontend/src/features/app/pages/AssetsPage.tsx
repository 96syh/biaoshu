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

export const AssetsPage = ({ controller }: PageProps) => {
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
    <div className="asset-workspace">
                    <div className="asset-hero ops-panel">
                      <div>
                        <p className="workspace-kicker">Visual Assets</p>
                        <h2>图表素材规划与生成</h2>
                        <span>把目录中的组织图、流程图、方案信息图和证明材料位集中管理，生成后可作为 Word 正文插图素材。</span>
                      </div>
                      <div className="asset-actions">
                        <button type="button" className="solid-button" onClick={runDocumentBlocksPlan} disabled={!effectiveOutline || !activeReport || busy === 'blocks'}>
                          <SparklesIcon className="h-4 w-4" /> {plannedBlocksCount ? '重新规划' : '生成规划'}
                        </button>
                        <button type="button" onClick={() => goToPage('content')} disabled={!effectiveOutline}>去生成正文</button>
                      </div>
                    </div>
    
                    {busy === 'blocks' && <TaskProgress progress={progress} />}
    
                    <div className="asset-metrics">
                      <div><span>规划章节</span><strong>{plannedBlockGroups.length}</strong></div>
                      <div><span>素材块</span><strong>{plannedBlocksCount}</strong></div>
                      <div><span>可生成图形</span><strong>{visualBlocksCount}</strong></div>
                      <div><span>已生成</span><strong>{generatedVisualCount}</strong></div>
                    </div>
    
                    <div className="asset-layout">
                      <section className="asset-panel">
                        {selectedReferenceSlot && (
                          <ReferenceSlotShowcase slot={selectedReferenceSlot} />
                        )}
                        <div className="ops-panel__head">
                          <div>
                            <h2>图表素材清单</h2>
                            <span>{plannedBlocksCount ? '按章节展示规划出的图表、表格、图片和承诺书' : '等待生成素材规划'}</span>
                          </div>
                        </div>
    
                        {plannedBlockGroups.length ? plannedBlockGroups.map((group, groupIndex) => (
                          <div key={`${group.chapter_id}-${groupIndex}`} className="asset-group">
                            <div className="asset-group__head">
                              <strong>{group.chapter_id} {group.chapter_title || '未命名章节'}</strong>
                              <span>{group.blocks.length} 个素材块</span>
                            </div>
                            <div className="asset-block-list">
                              {group.blocks.map((block, blockIndex) => {
                                const assetKey = blockAssetKey(group.chapter_id, groupIndex, blockIndex, block);
                                const result = visualAssetResults[assetKey] || visualAssetResultFromBlock(block);
                                const src = result?.imageUrl || (result?.b64Json ? (result.b64Json.startsWith('data:image') ? result.b64Json : `data:image/png;base64,${result.b64Json}`) : '');
                                const visual = isVisualBlockType(block.block_type);
                                const columns = Array.isArray(block.table_schema?.columns) ? block.table_schema.columns : [];
                                const nodes = Array.isArray(block.chart_schema?.nodes) ? block.chart_schema.nodes : [];
                                const edges = Array.isArray(block.chart_schema?.edges) ? block.chart_schema.edges : [];
                                return (
                                  <article key={assetKey} className={`asset-block ${visual ? 'asset-block--visual' : ''}`}>
                                    <div className="asset-block__top">
                                      <span>{blockTypeLabel(block.block_type)}</span>
                                      <strong>{block.block_name || block.name || '未命名素材'}</strong>
                                      {block.required && <em>必需</em>}
                                    </div>
                                    <p>{block.placeholder || block.fallback_placeholder || block.data_source || '按当前目录与解析结果生成素材占位。'}</p>
                                    {columns.length > 0 && (
                                      <div className="asset-chip-row">
                                        {columns.slice(0, 8).map((column: unknown, index: number) => <span key={`${assetKey}-col-${index}`}>{String(column)}</span>)}
                                      </div>
                                    )}
                                    {(nodes.length > 0 || edges.length > 0) && (
                                      <div className="asset-schema-note">结构：{nodes.length} 个节点 / {edges.length} 条连接</div>
                                    )}
                                    {visual && (
                                      <div className="asset-block__actions">
                                        <button
                                          type="button"
                                          className="solid-button"
                                          onClick={() => runVisualAssetGeneration(group, groupIndex, block, blockIndex, assetKey)}
                                          disabled={busy.startsWith('asset:') || busy === 'blocks'}
                                        >
                                          <SparklesIcon className="h-4 w-4" />
                                          {result?.status === 'running' ? '生成中' : src ? '重新生成图' : '生成图'}
                                        </button>
                                        {src && <span className="asset-inline-status">已接入正文和导出</span>}
                                      </div>
                                    )}
                                    {result?.status === 'error' && <div className="asset-error">{result.error}</div>}
                                    {src && (
                                      <div className="asset-image-card">
                                        <img src={src} alt={`${block.block_name || blockTypeLabel(block.block_type)} 生成图`} />
                                        {result?.prompt && (
                                          <details>
                                            <summary>查看生成提示词</summary>
                                            <pre>{result.prompt}</pre>
                                          </details>
                                        )}
                                      </div>
                                    )}
                                  </article>
                                );
                              })}
                            </div>
                          </div>
                        )) : (
                          <div className="empty-state">
                            <strong>还没有图表素材规划</strong>
                            <span>点击“生成规划”，系统会根据目录、响应矩阵和成熟样例中的表格/图片位生成素材清单。</span>
                            <button type="button" className="solid-button" onClick={runDocumentBlocksPlan} disabled={!effectiveOutline || !activeReport || busy === 'blocks'}>
                              生成图表素材规划
                            </button>
                          </div>
                        )}
                      </section>
    
                      <aside className="asset-panel asset-panel--side">
                        <div className="ops-panel__head">
                          <div>
                            <h2>样例风格依据</h2>
                            <span>来自成熟样例解析出的图片位和表格模型</span>
                          </div>
                        </div>
                        <div className="asset-reference-list">
                          {referenceImageSlots.slice(0, 8).map((item: any, index: number) => (
                            <button
                              type="button"
                              key={`image-slot-${index}`}
                              className={`asset-reference-item ${index === activeReferenceSlotIndex ? 'asset-reference-item--active' : ''}`}
                              onClick={() => setActiveReferenceSlotIndex(index)}
                            >
                              <strong>{item.name || item.slot_name || `图片位 ${index + 1}`}</strong>
                              <span>{item.purpose || item.description || item.position || item.fallback_placeholder || '样例中的图片/素材位置'}</span>
                            </button>
                          ))}
                          {!listCount(activeReferenceRecord.image_slots) && <span className="asset-muted">当前成熟样例未解析出明确图片位；系统会优先按目录 expected_blocks 和图表规划生成。</span>}
                        </div>
                        {selectedReferenceSlot && (
                          <ReferenceSlotPreview slot={selectedReferenceSlot} />
                        )}
                        <div className="asset-prompt-note">
                          <strong>提示词策略</strong>
                          <span>按联网资料采用正式商务图表、组织架构图、流程图和投标文件图表模板的组合约束：白底、扁平矢量、清晰中文标签、少色、适合 A4 Word 正文。</span>
                        </div>
                      </aside>
                    </div>
                  </div>
  );
};
