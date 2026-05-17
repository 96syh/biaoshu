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

export const AnalysisPage = ({ controller }: PageProps) => {
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
    activeSourceLineHighlightIndex,
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
    sourcePreviewHtmlWithLocateHighlight,
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
  const sourcePreviewHtmlForDisplay = sourcePreviewHtmlWithLocateHighlight || state.sourcePreviewHtml || '';
  const hasDocxSourcePreview = Boolean(sourcePreviewHtmlForDisplay && stripPreviewInlineMarkup(sourcePreviewHtmlForDisplay).trim());

  const renderParseContentLine = (line: string) => {
    const parts = line.split('\n').map(part => part.trim()).filter(Boolean);
    if (parts.length <= 1) {
      return <span className="source-jump-item__content source-jump-item__content--plain">{line}</span>;
    }
    const [title, ...details] = parts;
    return (
      <span className="source-jump-item__content">
        <span className="source-jump-item__title">
          <span className="source-jump-item__marker" aria-hidden="true">◆</span>
          <span>{title}</span>
        </span>
        {details.map((detail, detailIndex) => (
          <span key={`${title}-detail-${detailIndex}`} className="source-jump-item__detail">{detail}</span>
        ))}
      </span>
    );
  };

  return (
    <div className="ops-page-grid ops-page-grid--analysis">
                    <div className="ops-panel tender-parse-panel">
                      <div className="ops-panel__head">
                        <h2>招标文件解析归纳</h2>
                        <div className="panel-head-actions">
                          <span>
                            {checkingHistoryRequirements
                              ? '要求匹配中'
                              : activeReport ? '按评审页签组织' : '待解析'}
                          </span>
                          {activeReport && (
                            <button
                              type="button"
                              className="text-link"
                              onClick={() => runHistoryRequirementCheck(activeReport)}
                              disabled={checkingHistoryRequirements}
                            >
                              {checkingHistoryRequirements ? '匹配中' : '要求匹配'}
                            </button>
                          )}
                          <button type="button" className="text-link" onClick={runAnalysis} disabled={!state.fileContent || busy === 'analysis'}>
                            {busy === 'analysis' ? '解析中' : activeReport ? '重新解析' : '开始解析'}
                          </button>
                        </div>
                      </div>
                      {tenderParseProgress && <TaskProgress progress={tenderParseProgress} onRetry={runAnalysis} />}
                      {(busy === 'analysis' || analysisControl === 'paused') && (
                        <div className="analysis-control-row">
                          <button
                            type="button"
                            onClick={() => controlAnalysisTask('pause')}
                            disabled={!analysisTaskId || analysisControl === 'paused'}
                          >
                            <PauseIcon className="h-4 w-4" /> 暂停
                          </button>
                          <button
                            type="button"
                            onClick={() => controlAnalysisTask('resume')}
                            disabled={!analysisTaskId || analysisControl !== 'paused'}
                          >
                            <PlayIcon className="h-4 w-4" /> 继续
                          </button>
                          <button
                            type="button"
                            className="danger-button"
                            onClick={() => controlAnalysisTask('stop')}
                            disabled={!analysisTaskId || analysisControl === 'stopped'}
                          >
                            <StopIcon className="h-4 w-4" /> 停止
                          </button>
                        </div>
                      )}
                      {streamText && <pre className="stream-box stream-box--large">{streamText}</pre>}
                      <div className={`analysis-next-card ${activeReport ? 'analysis-next-card--ready' : ''}`}>
                        <div>
                          <span>下一步</span>
                          <strong>生成目录规划</strong>
                          <p>{activeReport ? '解析结果已就绪，可进入章节目录与评分项映射。' : '完成标准解析后开放目录规划。'}</p>
                        </div>
                        <button
                          type="button"
                          className="solid-button"
                          onClick={() => goToPage('outline')}
                          disabled={!activeReport || busy === 'analysis'}
                        >
                          <span>{activeReport ? '生成目录' : '等待解析'}</span>
                          <ChevronRightIcon className="h-4 w-4" />
                        </button>
                      </div>
                      {tenderParseReady ? (
                        <>
                          <div className="tender-parse-tabs">
                            {tenderParseTabs.map(tab => (
                              <button
                                key={tab.key}
                                type="button"
                                className={tab.key === activeParseTab.key ? 'active' : ''}
                                onClick={() => {
                                  setActiveParseTabKey(tab.key);
                                  selectParseSection(tab.sections[0]?.id || '');
                                }}
                              >
                                <CheckCircleIcon className="h-4 w-4" />
                                <span>{tab.label}</span>
                                <em>{tab.sections.reduce((sum, section) => sum + section.count, 0)}</em>
                              </button>
                            ))}
                          </div>
                          <div className="tender-parse-layout">
                            <div className="tender-parse-main">
                              {isScoringParseTab(activeParseTab.key) ? (
                                <div className="tender-score-table-wrap">
                              <table className="tender-score-table">
                                <thead>
                                  <tr>
                                    <th>评分项</th>
                                    <th>分值</th>
                                    <th>得分要求</th>
                                    <th>匹配</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {activeScoringRows.length ? activeScoringRows.map(row => (
                                    <tr key={row.id}>
                                      <td>{row.item}</td>
                                      <td>{row.score}</td>
                                      <td>
                                        <div className="score-requirement">
                                          {(row.subitems.length ? row.subitems : [row.requirement]).map((subitem, index) => (
                                            <button
                                              key={`${row.id}-subitem-${index}`}
                                              type="button"
                                              className="source-jump-item source-jump-item--compact"
                                              onClick={() => locateSourceItem(`${row.item} · 要求 ${index + 1}`, subitem)}
                                              title="定位到右侧原文"
                                            >
                                              <span>{subitem}</span>
                                              <em>定位</em>
                                            </button>
                                          ))}
                                          {row.evidence.length > 0 && (
                                            <div className="score-evidence">
                                              {row.evidence.slice(0, 2).map((line, index) => (
                                                <button
                                                  key={`${row.id}-evidence-${index}`}
                                                  type="button"
                                                  className="source-jump-item source-jump-item--evidence"
                                                  onClick={() => locateSourceItem(`${row.item} · 证据 ${index + 1}`, line)}
                                                  title="定位到右侧原文"
                                                >
                                                  <span>{line}</span>
                                                  <em>定位</em>
                                                </button>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </td>
                                      <td>{renderRequirementMatchIcon(getRequirementCheckForItem(row.id, row.item), true)}</td>
                                    </tr>
                                  )) : (
                                    <tr>
                                      <td colSpan={4}>当前解析报告未返回该类评分表，建议重新解析或人工核对评分办法章节。</td>
                                    </tr>
                                  )}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <div className="tender-parse-workbench">
                              <nav className="tender-parse-sections" aria-label="解析章节">
                                {activeParseTab.sections.map(section => {
                                  const sectionCheck = getRequirementCheckForItem(section.id, section.title);
                                  const riskTitle = activeParseTab.key === 'risk' && sectionCheck
                                    ? sectionCheck.satisfied
                                      ? '历史库匹配满足：可避免成为废标'
                                      : '历史库未满足：需要补充或修改材料/响应'
                                    : undefined;
                                  const riskAria = activeParseTab.key === 'risk' && sectionCheck
                                    ? sectionCheck.satisfied
                                      ? '历史库满足，非废标'
                                      : '历史库不满足，需补改'
                                    : undefined;
                                  const riskMissingTitle = activeParseTab.key === 'risk'
                                    ? '历史库未匹配到满足证据：需要补充或修改材料/响应'
                                    : undefined;
                                  return (
                                    <button
                                      key={section.id}
                                      type="button"
                                      className={section.id === activeParseSection.id ? 'active' : ''}
                                      onClick={() => selectParseSection(section.id)}
                                    >
                                      <span>{section.title}</span>
                                      <em>{section.count ? `${section.count} 项` : '待核对'}</em>
                                      {renderRequirementMatchIcon(sectionCheck, true, riskTitle, riskAria, riskMissingTitle)}
                                    </button>
                                  );
                                })}
                              </nav>
                              <article className="tender-parse-detail">
                                <div className="tender-parse-detail__head">
                                  <strong>{activeParseSection.title}</strong>
                                  <span>{activeParseTab.label}</span>
                                </div>
                                <div className="tender-parse-content">
                                  {activeParseSection.content.map((line, index) => (
                                    <button
                                      key={`${activeParseSection.id}-content-${index}`}
                                      type="button"
                                      className="source-jump-item"
                                      onClick={() => locateSourceItem(`${activeParseSection.title} · 第 ${index + 1} 项`, line)}
                                      title="定位到右侧原文"
                                    >
                                      {renderParseContentLine(line)}
                                      <em>定位</em>
                                    </button>
                                  ))}
                                </div>
                              </article>
                            </div>
                          )}
                            </div>
                            <aside
                              ref={evidencePanelRef}
                              className={`tender-source-panel ${evidenceHighlighted ? 'tender-source-panel--highlight' : ''}`}
                              aria-live="polite"
                            >
                              {sourceLocateResult.status === 'found' && sourceLocateResult.snippet ? (
                                <div className="tender-source-locate-hint">
                                  <strong>{sourceLocateResult.label || '原文位置'}</strong>
                                  <span>{sourceLocateResult.snippet}</span>
                                </div>
                              ) : sourceLocateResult.status === 'not-found' ? (
                                <div className="tender-source-locate-hint tender-source-locate-hint--miss">
                                  <strong>未找到完全一致的原文段落</strong>
                                  <span>已显示上传文档全文，请点击左侧更具体的要求文本继续定位。</span>
                                </div>
                              ) : null}
                              <div className="tender-source-word" role="document" aria-label="上传文档原文预览">
                                {renderedSourcePages.length ? renderedSourcePages.map(page => (
                                  <section
                                    key={`rendered-source-page-${page.page_number}`}
                                    className="tender-source-rendered-page"
                                    aria-label={`Word 原文第 ${page.page_number} 页`}
                                  >
                                    <img src={backendAssetUrl(page.image_url)} alt={`Word 原文第 ${page.page_number} 页`} />
                                    {(page.text_blocks || []).map(block => {
                                      const isActive = activeRenderedSourceBlock?.pageNumber === page.page_number
                                        && activeRenderedSourceBlock.blockId === block.id;
                                      return (
                                        <div
                                          id={`source-rendered-block-${page.page_number}-${block.id}`}
                                          key={`${page.page_number}-${block.id}`}
                                          className={`rendered-source-block ${isActive ? 'rendered-source-block--active' : ''}`}
                                          style={renderedBlockStyle(page, block.bbox)}
                                          title={block.text}
                                          aria-label={block.text}
                                        >
                                          {isActive && <span>{sourceLocateResult.label || '原文位置'}</span>}
                                        </div>
                                      );
                                    })}
                                  </section>
                                )) : hasDocxSourcePreview ? (
                                  <div className="tender-source-docx-stage">
                                    <section
                                      className="tender-source-docx-page"
                                      dangerouslySetInnerHTML={{ __html: sourcePreviewHtmlForDisplay }}
                                    />
                                  </div>
                                ) : sourcePreviewPages.length ? sourcePreviewPages.map(page => (
                                  <section
                                    key={`source-page-${page.pageNumber}`}
                                    className="tender-source-page"
                                    aria-label={`第 ${page.pageNumber} 页 / 共 ${sourcePreviewPages.length} 页`}
                                  >
                                    <div className="tender-source-page__crop tender-source-page__crop--tl" aria-hidden="true" />
                                    <div className="tender-source-page__crop tender-source-page__crop--tr" aria-hidden="true" />
                                    <div className="tender-source-page__body">
                                      {page.blocks.map(block => (
                                        block.type === 'blank' ? (
                                          <div
                                            id={`source-line-${block.sourceIndex}`}
                                            key={`source-line-${block.sourceIndex}`}
                                            className={`tender-source-block tender-source-block--blank ${block.sourceIndex === activeSourceLineHighlightIndex ? 'tender-source-block--active' : ''}`}
                                            aria-hidden="true"
                                          />
                                        ) : (
                                          <p
                                            id={`source-line-${block.sourceIndex}`}
                                            key={`source-line-${block.sourceIndex}`}
                                            className={`tender-source-block tender-source-block--${block.type} ${block.sourceIndex === activeSourceLineHighlightIndex ? 'tender-source-block--active' : ''}`}
                                          >
                                            {block.text}
                                          </p>
                                        )
                                      ))}
                                    </div>
                                    <div className="tender-source-page__footer">第 {page.pageNumber} 页 / 共 {sourcePreviewPages.length} 页</div>
                                    <div className="tender-source-page__crop tender-source-page__crop--bl" aria-hidden="true" />
                                    <div className="tender-source-page__crop tender-source-page__crop--br" aria-hidden="true" />
                                  </section>
                                )) : (
                                  <section className="tender-source-page">
                                    <div className="tender-source-page__body">
                                      <p className="tender-source-block tender-source-block--active">
                                        未读取到上传文件原文，请重新上传招标文件。
                                      </p>
                                    </div>
                                  </section>
                                )}
                              </div>
                            </aside>
                          </div>
                        </>
                      ) : tenderParseProgress ? null : (
                        <div className="empty-state empty-state--compact">
                          <strong>等待标准解析</strong>
                          <span>完成后会按基础信息、资格审查、技术评分、废标项、投标文件要求等页签展示，并保留每项原文证据。</span>
                        </div>
                      )}
                    </div>
    
                  </div>
  );
};
