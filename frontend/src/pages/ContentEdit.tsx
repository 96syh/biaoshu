/**
 * 内容编辑页面 - 完整标书预览和生成
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { ConfigData, OutlineData, OutlineItem } from '../types';
import {
  DocumentTextIcon,
  PlayIcon,
  DocumentArrowDownIcon,
  ArrowUpIcon,
  EyeIcon,
  SparklesIcon,
  ChevronRightIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { configApi, contentApi, ChapterContentRequest, documentApi } from '../services/api';
import { saveAs } from 'file-saver';
import { draftStorage } from '../utils/draftStorage';
import { consumeSseStream } from '../utils/sse';

interface ContentEditProps {
  outlineData: OutlineData | null;
  selectedChapter: string;
  onChapterSelect: (chapterId: string) => void;
}

interface GenerationProgress {
  total: number;
  completed: number;
  current: string;
  failed: string[];
  generating: Set<string>; // 正在生成的项目ID集合
}

interface StatusMessage {
  type: 'success' | 'error';
  text: string;
}

interface ChapterEntry {
  item: OutlineItem;
  topSection: OutlineItem;
  parents: OutlineItem[];
}

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const truncateText = (text: string, maxLength: number) => {
  if (!text) {
    return '';
  }
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
};

const buildPreviewPlaceholder = (item: OutlineItem, projectName: string) => {
  const topic = item.title || '当前章节';
  const summary = item.description || `${topic}的正文内容将在生成后自动填充到此处。`;
  return [
    `${projectName}的“${topic}”章节将围绕本节描述展开撰写，正文会按照技术标书常见的 Word 版式自动排版，并保留章节编号、段落间距与正式书面语气。`,
    `当前章节说明：${summary}`,
    `点击左侧“生成标书”后，系统会把该章节的正式内容写入此页，右侧预览将实时接近最终导出的 Word 成稿效果。`,
  ];
};

const isQuotaErrorMessage = (message: string) =>
  /quota exceeded|resource_exhausted|rate limit|429|配额限制|限流/i.test(message);

const normalizeGenerationErrorMessage = (message: string, provider?: string) => {
  if (isQuotaErrorMessage(message)) {
    if (provider === 'gemini') {
      return '当前 Gemini Key 已触发配额限制，批量生成无法继续。请更换有额度的 Gemini Key，或切换到 DeepSeek / OpenAI 后重试。';
    }
    return '当前模型供应商已触发限流或配额限制，批量生成已停止。请稍后重试，或切换到其他可用模型。';
  }

  if (/结果为空|空内容/i.test(message)) {
    return '模型返回了空内容，通常是兼容模式异常、内容拦截或额度问题导致。请更换模型后重试。';
  }

  return message;
};

const getBatchStrategy = (config?: ConfigData | null) => {
  if (config?.provider === 'gemini') {
    return {
      concurrency: 1,
      batchDelayMs: 15000,
    };
  }

  return {
    concurrency: 5,
    batchDelayMs: 0,
  };
};


const ContentEdit: React.FC<ContentEditProps> = ({
  outlineData,
  selectedChapter,
  onChapterSelect,
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<GenerationProgress>({
    total: 0,
    completed: 0,
    current: '',
    failed: [],
    generating: new Set<string>()
  });
  const [message, setMessage] = useState<StatusMessage | null>(null);
  const [leafItems, setLeafItems] = useState<OutlineItem[]>([]);
  const [showScrollToTop, setShowScrollToTop] = useState(false);
  const previewScrollRef = useRef<HTMLDivElement | null>(null);
  const previewNodeRefs = useRef<Record<string, HTMLElement | null>>({});

  // 收集所有叶子节点
  const collectLeafItems = useCallback((items: OutlineItem[]): OutlineItem[] => {
    let leaves: OutlineItem[] = [];
    items.forEach(item => {
      if (!item.children || item.children.length === 0) {
        leaves.push(item);
      } else {
        leaves = leaves.concat(collectLeafItems(item.children));
      }
    });
    return leaves;
  }, []);

  const collectChapterEntries = useCallback((
    items: OutlineItem[],
    parents: OutlineItem[] = [],
    topSection?: OutlineItem,
  ): ChapterEntry[] => {
    let entries: ChapterEntry[] = [];

    items.forEach((item) => {
      const currentTopSection = topSection || item;
      if (!item.children || item.children.length === 0) {
        entries.push({
          item,
          topSection: currentTopSection,
          parents,
        });
        return;
      }

      entries = entries.concat(
        collectChapterEntries(item.children, [...parents, item], currentTopSection),
      );
    });

    return entries;
  }, []);

  // 获取章节的上级章节信息
  const getParentChapters = useCallback((targetId: string, items: OutlineItem[], parents: OutlineItem[] = []): OutlineItem[] => {
    for (const item of items) {
      if (item.id === targetId) {
        return parents;
      }
      if (item.children && item.children.length > 0) {
        const found = getParentChapters(targetId, item.children, [...parents, item]);
        if (found.length > 0 || item.children.some(child => child.id === targetId)) {
          return found.length > 0 ? found : [...parents, item];
        }
      }
    }
    return [];
  }, []);

  // 获取章节的同级章节信息
  const getSiblingChapters = useCallback((targetId: string, items: OutlineItem[]): OutlineItem[] => {
    // 直接在当前级别查找
    if (items.some(item => item.id === targetId)) {
      return items;
    }
    
    // 递归在子级别查找
    for (const item of items) {
      if (item.children && item.children.length > 0) {
        const siblings = getSiblingChapters(targetId, item.children);
        if (siblings.length > 0) {
          return siblings;
        }
      }
    }
    
    return [];
  }, []);

  useEffect(() => {
    if (outlineData) {
      const leaves = collectLeafItems(outlineData.outline);
      // 恢复本地缓存的正文内容（仅对叶子节点生效）
      const filtered = draftStorage.filterContentByOutlineLeaves(outlineData.outline);
      const mergedLeaves = leaves.map((leaf) => {
        const cached = filtered[leaf.id];
        return cached ? { ...leaf, content: cached } : leaf;
      });

      // 目录变更时，顺手清理掉无效的旧缓存（只保留当前叶子节点）
      draftStorage.saveContentById(filtered);

      setLeafItems(mergedLeaves);
      setProgress(prev => ({ ...prev, total: leaves.length }));
    }
  }, [outlineData, collectLeafItems]);

  useEffect(() => {
    if (leafItems.length === 0) {
      return;
    }

    const hasSelectedChapter = leafItems.some((item) => item.id === selectedChapter);
    if (!hasSelectedChapter) {
      onChapterSelect(leafItems[0].id);
    }
  }, [leafItems, selectedChapter, onChapterSelect]);

  useEffect(() => {
    if (!selectedChapter) {
      return;
    }

    const targetNode = previewNodeRefs.current[selectedChapter];
    const container = previewScrollRef.current;
    if (!targetNode || !container) {
      return;
    }

    const offsetTop = targetNode.offsetTop - 28;
    container.scrollTo({
      top: Math.max(0, offsetTop),
      behavior: 'smooth',
    });
  }, [selectedChapter]);

  // 监听页面滚动，控制回到顶部按钮的显示
  useEffect(() => {
    // 现在主内容区为内部滚动容器（App.tsx: #app-main-scroll），不能只监听 window
    const scrollContainer = document.getElementById('app-main-scroll');

    const handleScroll = () => {
      const scrollTop = scrollContainer
        ? scrollContainer.scrollTop
        : (window.pageYOffset || document.documentElement.scrollTop);
      setShowScrollToTop(scrollTop > 300);
    };

    // 初始化计算一次，避免刷新后位置不对
    handleScroll();

    const target: any = scrollContainer || window;
    target.addEventListener('scroll', handleScroll);
    return () => target.removeEventListener('scroll', handleScroll);
  }, []);

  // 获取叶子节点的实时内容
  const getLeafItemContent = (itemId: string): string | undefined => {
    const leafItem = leafItems.find(leaf => leaf.id === itemId);
    return leafItem?.content;
  };

  // 检查是否为叶子节点
  const isLeafNode = (item: OutlineItem): boolean => {
    return !item.children || item.children.length === 0;
  };

  // 生成单个章节内容
  const generateItemContent = async (
    item: OutlineItem,
    projectOverview: string,
    provider?: string,
  ): Promise<OutlineItem> => {
    if (!outlineData) throw new Error('缺少目录数据');
    
    // 将当前项目添加到正在生成的集合中
    setProgress(prev => ({ 
      ...prev, 
      current: item.title,
      generating: new Set([...Array.from(prev.generating), item.id])
    }));
    
    try {
      // 获取上级章节和同级章节信息
      const parentChapters = getParentChapters(item.id, outlineData.outline);
      const siblingChapters = getSiblingChapters(item.id, outlineData.outline);

      const request: ChapterContentRequest = {
        chapter: item,
        parent_chapters: parentChapters,
        sibling_chapters: siblingChapters,
        project_overview: projectOverview
      };

      const response = await contentApi.generateChapterContentStream(request);

      let content = '';
      const updatedItem = { ...item };
      
      await consumeSseStream(response, (parsed) => {
        if (parsed.status === 'error') {
          throw new Error(parsed.message || '章节内容生成失败');
        }

        if (parsed.status === 'streaming' && parsed.full_content) {
          // 实时更新内容
          content = parsed.full_content;
          updatedItem.content = content;
          draftStorage.upsertChapterContent(item.id, content);

          setLeafItems(prevItems => {
            const newItems = [...prevItems];
            const index = newItems.findIndex(i => i.id === item.id);
            if (index !== -1) {
              newItems[index] = { ...updatedItem };
            }
            return newItems;
          });
        } else if (parsed.status === 'completed' && parsed.content) {
          content = parsed.content;
          updatedItem.content = content;
          draftStorage.upsertChapterContent(item.id, content);
        }
      });

      if (!content.trim()) {
        throw new Error('章节内容生成结果为空，请检查模型配置后重试');
      }

      return updatedItem;
    } catch (error: any) {
      const errorMessage = normalizeGenerationErrorMessage(
        error?.message || '章节内容生成失败',
        provider,
      );
      setProgress(prev => ({
        ...prev,
        failed: [...prev.failed, item.title]
      }));
      setMessage(prev => prev ?? {
        type: 'error',
        text: `${item.title} 生成失败：${errorMessage}`,
      });
      throw error;
    } finally {
      // 从正在生成的集合中移除当前项目
      setProgress(prev => {
        const newGenerating = new Set(Array.from(prev.generating));
        newGenerating.delete(item.id);
        return {
          ...prev,
          generating: newGenerating
        };
      });
    }
  };

  // 开始生成所有内容
  const handleGenerateContent = async () => {
    if (!outlineData || leafItems.length === 0) return;

    setIsGenerating(true);
    setMessage(null);
    setProgress({
      total: leafItems.length,
      completed: 0,
      current: '',
      failed: [],
      generating: new Set<string>()
    });

    try {
      const configResponse = await configApi.loadConfig();
      const runtimeConfig = (configResponse.data || null) as ConfigData | null;
      const { concurrency, batchDelayMs } = getBatchStrategy(runtimeConfig);
      const updatedItems = [...leafItems];
      let shouldAbort = false;
      
      for (let i = 0; i < leafItems.length && !shouldAbort; i += concurrency) {
        const batch = leafItems.slice(i, i + concurrency);
        let batchShouldAbort = false;
        const promises = batch.map(item => 
          generateItemContent(
            item,
            outlineData.project_overview || '',
            runtimeConfig?.provider,
          )
            .then(updatedItem => {
              const index = updatedItems.findIndex(ui => ui.id === updatedItem.id);
              if (index !== -1) {
                updatedItems[index] = updatedItem;
              }
              setProgress(prev => ({ ...prev, completed: prev.completed + 1 }));
              return updatedItem;
            })
            .catch(error => {
              console.error(`生成内容失败 ${item.title}:`, error);
              const normalizedMessage = normalizeGenerationErrorMessage(
                error?.message || '章节内容生成失败',
                runtimeConfig?.provider,
              );
              if (isQuotaErrorMessage(normalizedMessage)) {
                batchShouldAbort = true;
                setMessage({
                  type: 'error',
                  text: normalizedMessage,
                });
              }
              setProgress(prev => ({ ...prev, completed: prev.completed + 1 }));
              return item; // 返回原始项目
            })
        );

        await Promise.all(promises);
        if (batchShouldAbort) {
          shouldAbort = true;
        }
        if (shouldAbort) {
          break;
        }
        if (batchDelayMs > 0 && i + concurrency < leafItems.length) {
          await sleep(batchDelayMs);
        }
      }

      // 更新状态
      setLeafItems(updatedItems);
      setMessage(prev => {
        if (prev?.type === 'error') {
          return prev;
        }
        return {
          type: 'success',
          text: `正文生成完成，已生成 ${updatedItems.filter(item => item.content?.trim()).length} 个章节`,
        };
      });
      
      // 这里需要更新整个outlineData，但由于我们只有props，需要通过回调通知父组件
      // 暂时只更新本地状态
      
    } catch (error) {
      console.error('生成内容时出错:', error);
    } finally {
      setIsGenerating(false);
      setProgress(prev => ({ ...prev, current: '', generating: new Set<string>() }));
    }
  };

  // 获取叶子节点的最新内容（包括生成的内容）
  const getLatestContent = (item: OutlineItem): string => {
    if (!item.children || item.children.length === 0) {
      // 叶子节点，从 leafItems 获取最新内容
      const leafItem = leafItems.find(leaf => leaf.id === item.id);
      return leafItem?.content || item.content || '';
    }
    return item.content || '';
  };

  // 解析Markdown内容为Word段落
  // （已提取到文件顶层，供后续导出Word等复用）

  // 滚动到页面顶部
  const scrollToTop = () => {
    const scrollContainer = document.getElementById('app-main-scroll');
    if (scrollContainer) {
      scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // 导出Word文档
  const handleExportWord = async () => {
    if (!outlineData) return;

    try {
      // 构建带有最新内容的导出数据（leafItems 中存的是实时内容）
      const buildExportOutline = (items: OutlineItem[]): OutlineItem[] => {
        return items.map(item => {
          const latestContent = getLatestContent(item);
          const exportedItem: OutlineItem = {
            ...item,
            content: latestContent,
          };
          if (item.children && item.children.length > 0) {
            exportedItem.children = buildExportOutline(item.children);
          }
          return exportedItem;
        });
      };

      const exportPayload = {
        project_name: outlineData.project_name,
        project_overview: outlineData.project_overview,
        outline: buildExportOutline(outlineData.outline),
      };

      const response = await documentApi.exportWord(exportPayload);
      if (!response.ok) {
        throw new Error('导出失败');
      }
      const blob = await response.blob();
      saveAs(blob, `${outlineData.project_name || '标书文档'}.docx`);
      
    } catch (error) {
      console.error('导出失败:', error);
      alert('导出失败，请重试');
    }
  };

  const chapterEntries = outlineData ? collectChapterEntries(outlineData.outline) : [];
  const selectedEntry = chapterEntries.find((entry) => entry.item.id === selectedChapter) || chapterEntries[0] || null;
  const activeTopSection = selectedEntry?.topSection || outlineData?.outline[0] || null;
  const visibleEntries = activeTopSection
    ? chapterEntries.filter((entry) => entry.topSection.id === activeTopSection.id)
    : [];
  const previewProjectName = outlineData?.project_name || '投标技术文件';
  const previewOverview = truncateText(outlineData?.project_overview || '', 220);
  const completedItems = leafItems.filter(item => item.content).length;
  const completionRate = leafItems.length > 0 ? Math.round((completedItems / leafItems.length) * 100) : 0;
  const totalWords = leafItems.reduce((sum, item) => sum + (item.content?.length || 0), 0);

  const openTopSection = (topSectionId: string) => {
    const firstEntry = chapterEntries.find((entry) => entry.topSection.id === topSectionId);
    if (firstEntry) {
      onChapterSelect(firstEntry.item.id);
    }
  };

  const renderWordSections = (items: OutlineItem[], level: number = 1): React.ReactElement[] => {
    return items.map((item) => {
      const isLeaf = isLeafNode(item);
      const currentContent = isLeaf ? getLeafItemContent(item.id) : item.content;
      const isActiveLeaf = isLeaf && item.id === selectedChapter;
      const placeholderParagraphs = buildPreviewPlaceholder(item, previewProjectName);

      return (
        <section
          key={item.id}
          ref={(node) => {
            if (isLeaf) {
              previewNodeRefs.current[item.id] = node;
            }
          }}
          className={`word-section ${isActiveLeaf ? 'word-section--active' : ''}`}
        >
          <div className={`word-section__heading word-section__heading--${Math.min(level, 3)}`}>
            {item.id} {item.title}
          </div>

          {item.description && (
            <p className="word-section__summary">{item.description}</p>
          )}

          {isLeaf ? (
            currentContent?.trim() ? (
              <div className="word-markdown">
                <ReactMarkdown>{currentContent}</ReactMarkdown>
              </div>
            ) : (
              <div className="word-placeholder">
                {placeholderParagraphs.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            )
          ) : (
            item.children && item.children.length > 0 && renderWordSections(item.children, level + 1)
          )}
        </section>
      );
    });
  };

  if (!outlineData) {
    return (
      <div className="space-y-6">
        <section className="workspace-intro">
          <span className="workspace-kicker">Step 03</span>
          <h2 className="workspace-title">正文生成与导出</h2>
          <p className="workspace-copy">目录准备完成后，这里会作为最后的成稿台展示完整技术标内容与导出结果。</p>
        </section>
        <div className="editor-layout">
          <section className="surface-panel">
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 px-6 py-16 text-center">
              <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-base font-semibold text-gray-900">正文工作台待初始化</h3>
              <p className="mt-2 text-sm leading-6 text-gray-500">
                先在“目录编辑”步骤生成结构，左侧章节导航和右侧 Word 预览才会同步展开。
              </p>
            </div>
          </section>

          <aside className="doc-window">
            <div className="doc-window__toolbar">
              <div className="doc-window__file">
                <DocumentTextIcon className="h-5 w-5 text-sky-600" />
                <span>投标技术文件.docx</span>
              </div>
              <div className="doc-window__meta">
                <span>预览待命</span>
              </div>
            </div>
            <div className="doc-window__stage">
              <article className="doc-page">
                <p className="doc-page__eyebrow">WORD PREVIEW</p>
                <h1 className="doc-page__title">投标技术文件</h1>
                <p className="doc-page__lead">
                  生成正文后，这里会以接近 Word 成稿的纸面样式展示章节标题、正文段落与实时预览效果。
                </p>
              </article>
            </div>
          </aside>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="workspace-intro">
        <span className="workspace-kicker">Step 03</span>
        <h2 className="workspace-title">正文生成与导出</h2>
        <p className="workspace-copy">
          左侧管理章节与生成进度，右侧以 Word 页面视图实时预览技术标成稿，减少留白，更适合现场演示与客户讲解。
        </p>
      </section>

      <div className="editor-layout">
        <div className="space-y-6">
          <section className="surface-panel">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
              <div className="space-y-4">
                <div>
                  <p className="workspace-kicker">Draft Control</p>
                  <h3 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">标书内容总控台</h3>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                    当前共 {leafItems.length} 个叶子章节，已完成 {completedItems} 个，成稿进度 {completionRate}%。
                    {progress.failed.length > 0 ? ` 当前失败 ${progress.failed.length} 个。` : ''}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="soft-stat">
                    <span className="soft-stat__label">已完成章节</span>
                    <span className="soft-stat__value">{completedItems} / {leafItems.length}</span>
                  </div>
                  <div className="soft-stat">
                    <span className="soft-stat__label">累计字数</span>
                    <span className="soft-stat__value">{totalWords}</span>
                  </div>
                  <div className="soft-stat">
                    <span className="soft-stat__label">当前预览</span>
                    <span className="soft-stat__value truncate">
                      {selectedEntry ? `${selectedEntry.item.id} ${selectedEntry.item.title}` : '未选择章节'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={handleGenerateContent}
                  disabled={isGenerating}
                  className="primary-button"
                >
                  <PlayIcon className="mr-2 h-4 w-4" />
                  {isGenerating ? '生成中...' : '生成标书'}
                </button>

                <button
                  onClick={handleExportWord}
                  disabled={isGenerating}
                  className="secondary-button"
                >
                  <DocumentArrowDownIcon className="mr-2 h-4 w-4" />
                  导出Word
                </button>
              </div>
            </div>

            {isGenerating && (
              <div className="mt-6 rounded-[24px] border border-sky-100 bg-sky-50/80 p-4">
                <div className="mb-3 flex items-center justify-between text-sm text-slate-600">
                  <span>正在生成：{progress.current || '准备中'}</span>
                  <span>{progress.completed} / {progress.total}</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-200">
                  <div
                    className="h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${progress.total > 0 ? (progress.completed / progress.total) * 100 : 0}%`,
                      background: 'linear-gradient(135deg, #2563eb, #0f766e)',
                    }}
                  />
                </div>
              </div>
            )}
          </section>

          {message && (
            <div
              className={`notice-banner ${
                message.type === 'success'
                  ? 'notice-banner--success'
                  : 'notice-banner--error'
              }`}
            >
              {message.text}
            </div>
          )}

          <section className="surface-panel">
            <div className="flex flex-col gap-4">
              <div className="space-y-3">
                <div>
                  <p className="workspace-kicker">Chapter Routing</p>
                  <div className="mt-2 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">章节导航</h3>
                    <div className="inline-flex items-center gap-2 self-start rounded-full border border-slate-200 bg-white/85 px-3 py-2 text-xs font-medium text-slate-500 xl:self-auto">
                      <EyeIcon className="h-4 w-4 text-sky-600" />
                      当前分组：{activeTopSection ? `${activeTopSection.id} ${activeTopSection.title}` : '未选择'}
                    </div>
                  </div>
                  <p className="text-sm leading-6 text-slate-600">
                    点击左侧章节即可联动右侧 Word 纸面预览，并自动定位到对应段落。
                  </p>
                </div>
              </div>

              <div className="flex gap-2 overflow-x-auto pb-2">
                {outlineData.outline.map((section) => {
                  const sectionCount = chapterEntries.filter((entry) => entry.topSection.id === section.id).length;
                  const active = activeTopSection?.id === section.id;
                  return (
                    <button
                      key={section.id}
                      type="button"
                      onClick={() => openTopSection(section.id)}
                      className={`section-tab ${active ? 'section-tab--active' : ''}`}
                    >
                      <span className="section-tab__index">{section.id}</span>
                      <span className="truncate">{section.title}</span>
                      <span className="section-tab__count">{sectionCount}</span>
                    </button>
                  );
                })}
              </div>

              <div className="space-y-3">
                {visibleEntries.map((entry) => {
                  const currentContent = getLeafItemContent(entry.item.id);
                  const generating = progress.generating.has(entry.item.id);
                  const failed = progress.failed.includes(entry.item.title);
                  const completed = Boolean(currentContent?.trim());
                  const active = selectedChapter === entry.item.id;
                  const statusLabel = generating
                    ? '生成中'
                    : failed
                      ? '失败'
                      : completed
                        ? '已生成'
                        : '待生成';

                  return (
                    <button
                      key={entry.item.id}
                      type="button"
                      onClick={() => onChapterSelect(entry.item.id)}
                      className={`chapter-card ${active ? 'chapter-card--active' : ''}`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`chapter-card__status chapter-card__status--${
                              generating ? 'working' : failed ? 'error' : completed ? 'done' : 'idle'
                            }`} />
                            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                              {entry.parents.map((parent) => parent.title).join(' / ') || '正文章节'}
                            </span>
                          </div>
                          <div className="mt-2 flex items-start gap-3">
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                              {entry.item.id}
                            </span>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-semibold text-slate-900">{entry.item.title}</div>
                              <p className="mt-1 text-sm leading-6 text-slate-500">
                                {truncateText(entry.item.description || '等待生成本章节正文内容。', 90)}
                              </p>
                            </div>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-2 text-xs font-medium text-slate-400">
                          <span>{statusLabel}</span>
                          <ChevronRightIcon className="h-4 w-4" />
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                        <span>{currentContent?.trim() ? `${currentContent.length} 字` : '尚未生成'}</span>
                        <span>{entry.topSection.title}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          <section className="surface-panel">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <SparklesIcon className="h-5 w-5 text-sky-600" />
                <div>
                  <div className="text-sm font-semibold text-slate-900">演示建议</div>
                  <p className="text-sm leading-6 text-slate-500">
                    先切到需要讲解的章节，再点击生成，右侧预览会立即贴近最终导出文档。
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50/80 px-4 py-2 text-xs font-medium text-slate-500">
                <ClockIcon className="h-4 w-4 text-slate-400" />
                实时预览已开启
              </div>
            </div>
          </section>
        </div>

        <aside className="doc-window">
          <div className="doc-window__toolbar">
            <div className="doc-window__file">
              <DocumentTextIcon className="h-5 w-5 text-sky-600" />
              <span>{previewProjectName}.docx</span>
            </div>
            <div className="doc-window__meta">
              <span>A4 纵向</span>
              <span>实时预览</span>
            </div>
          </div>

          <div ref={previewScrollRef} className="doc-window__stage">
            <article className="doc-page">
              <div className="doc-page__header">
                <p className="doc-page__eyebrow">TECHNICAL BID DOCUMENT</p>
                <h1 className="doc-page__title">{previewProjectName}</h1>
                <p className="doc-page__lead">
                  {activeTopSection
                    ? `${activeTopSection.id} ${activeTopSection.title}`
                    : '当前未选择章节'}
                </p>
              </div>

              {previewOverview && (
                <section className="doc-overview">
                  <div className="doc-overview__title">项目概述</div>
                  <p>{previewOverview}</p>
                </section>
              )}

              <div className="doc-page__content">
                {activeTopSection ? renderWordSections([activeTopSection]) : null}
              </div>

              <div className="doc-page__footer">
                华正 AI 标书创作平台 · 预览页
              </div>
            </article>
          </div>
        </aside>
      </div>

      {showScrollToTop && (
        <button
          onClick={scrollToTop}
          className="fixed bottom-24 right-6 z-[60] rounded-full bg-gradient-to-r from-blue-600 to-teal-600 p-3 text-white shadow-[0_18px_40px_-18px_rgba(29,78,216,0.7)] transition-all duration-300 hover:-translate-y-1"
          aria-label="回到顶部"
        >
          <ArrowUpIcon className="h-5 w-5" />
        </button>
      )}
    </div>
  );
};

export default ContentEdit;
