/**
 * 目录编辑页面
 */
import React, { useState } from 'react';
import { AnalysisReport, OutlineData, OutlineItem } from '../types';
import { outlineApi, expandApi } from '../services/api';
import { ChevronRightIcon, ChevronDownIcon, DocumentTextIcon, PencilIcon, TrashIcon, PlusIcon } from '@heroicons/react/24/outline';
import { consumeSseStream } from '../utils/sse';

interface OutlineEditProps {
  projectOverview: string;
  techRequirements: string;
  analysisReport?: AnalysisReport;
  outlineData: OutlineData | null;
  onOutlineGenerated: (outline: OutlineData) => void;
}

const OutlineEdit: React.FC<OutlineEditProps> = ({
  projectOverview,
  techRequirements,
  analysisReport,
  outlineData,
  onOutlineGenerated,
}) => {
  const uploadFileFormatMessage = '仅支持 PDF 和 DOCX 文件，暂不支持 DOC，请先另存为 DOCX';
  const [generating, setGenerating] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [streamingContent, setStreamingContent] = useState('');
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [expandFile, setExpandFile] = useState<File | null>(null);
  const [uploadedExpand, setuploadedExpand] = useState(false);
  const [oldOutline, setOldOutline] = useState<string | null>(null);
  const [oldDocument, setOldDocument] = useState<string | null>(null);
  const activeAnalysisReport = analysisReport || outlineData?.analysis_report;

  const countMappedNodes = (items: OutlineItem[]): number => items.reduce((sum, item) => {
    const mapped = Boolean(
      item.scoring_item_ids?.length
      || item.requirement_ids?.length
      || item.risk_ids?.length
      || item.material_ids?.length,
    );
    return sum + (mapped ? 1 : 0) + (item.children ? countMappedNodes(item.children) : 0);
  }, 0);

  const countOutlineNodes = (items: OutlineItem[]): number => items.reduce(
    (sum, item) => sum + 1 + (item.children ? countOutlineNodes(item.children) : 0),
    0,
  );

  const renderMappingChips = (item: OutlineItem) => {
    const chips = [
      { label: '评分', value: item.scoring_item_ids?.length || 0 },
      { label: '要求', value: item.requirement_ids?.length || 0 },
      { label: '风险', value: item.risk_ids?.length || 0 },
      { label: '材料', value: item.material_ids?.length || 0 },
    ].filter(chip => chip.value > 0);

    if (chips.length === 0) {
      return (
        <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-400">
          未映射
        </span>
      );
    }

    return (
      <div className="flex flex-wrap gap-1.5">
        {chips.map(chip => (
          <span
            key={chip.label}
            className="rounded-full border border-sky-100 bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700"
          >
            {chip.label} {chip.value}
          </span>
        ))}
      </div>
    );
  };

  const extractJsonPayload = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      return trimmed;
    }

    const fencedMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    const candidate = fencedMatch ? fencedMatch[1].trim() : trimmed;

    try {
      JSON.parse(candidate);
      return candidate;
    } catch {
      // 继续尝试提取主体 JSON
    }

    const startIndexes = [candidate.indexOf('{'), candidate.indexOf('[')].filter((index) => index >= 0);
    if (startIndexes.length === 0) {
      return candidate;
    }

    const start = Math.min(...startIndexes);
    const opening = candidate[start];
    const closing = opening === '{' ? '}' : ']';
    let depth = 0;
    let inString = false;
    let escaped = false;

    for (let index = start; index < candidate.length; index += 1) {
      const char = candidate[index];

      if (inString) {
        if (escaped) {
          escaped = false;
        } else if (char === '\\') {
          escaped = true;
        } else if (char === '"') {
          inString = false;
        }
        continue;
      }

      if (char === '"') {
        inString = true;
        continue;
      }

      if (char === opening) {
        depth += 1;
        continue;
      }

      if (char === closing) {
        depth -= 1;
        if (depth === 0) {
          return candidate.slice(start, index + 1).trim();
        }
      }
    }

    return candidate;
  };

  // 处理方案扩写文件上传
  const handleExpandUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.pdf') && !fileName.endsWith('.docx')) {
      setMessage({ type: 'error', text: uploadFileFormatMessage });
      event.target.value = '';
      return;
    }

    try {
      setuploadedExpand(true);
      setMessage(null);

      const response = await expandApi.uploadExpandFile(file);

      if (response.data.success) {
        setExpandFile(file);
        setOldOutline(response.data.old_outline || null);
        setOldDocument(response.data.file_content || null);
        setMessage({ type: 'success', text: `方案扩写文件上传成功：${file.name}` });
      } else {
        throw new Error(response.data.message || '文件上传失败');
      }
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.message || error.message || '文件上传失败' });
    } finally {

    }
  };

  const handleGenerateOutline = async () => {
    if (!projectOverview || !techRequirements) {
      setMessage({ type: 'error', text: '请先完成文档分析' });
      return;
    }

    try {
      setGenerating(true);
      setMessage(null);
      setStreamingContent('');

      const response = await outlineApi.generateOutlineStream({
        overview: projectOverview,
        requirements: techRequirements,
        uploaded_expand: uploadedExpand,
        old_outline: oldOutline || undefined,
        old_document: oldDocument || undefined,
        analysis_report: analysisReport,
        bid_mode: analysisReport?.bid_mode_recommendation,
      });

      let result = '';
      await consumeSseStream(response, (payload) => {
        if (payload.error) {
          throw new Error(payload.message || '目录生成失败');
        }
        if (typeof payload.chunk !== 'string' || !payload.chunk) {
          return;
        }
        result += payload.chunk;
        setStreamingContent(result);
      });

      if (!result.trim()) {
        throw new Error('目录生成结果为空，请检查模型配置后重试');
      }

      // 解析最终结果
      try {
        const outlineJson = JSON.parse(extractJsonPayload(result));
        onOutlineGenerated({
          ...outlineJson,
          analysis_report: analysisReport,
          bid_mode: analysisReport?.bid_mode_recommendation,
        });
        setMessage({ type: 'success', text: '目录结构生成完成' });
        setStreamingContent(''); // 清空流式内容
        
        // 默认展开所有项目
        const allIds = new Set<string>();
        const collectIds = (items: OutlineItem[]) => {
          items.forEach(item => {
            allIds.add(item.id);
            if (item.children) {
              collectIds(item.children);
            }
          });
        };
        collectIds(outlineJson.outline);
        setExpandedItems(allIds);
        
      } catch (parseError) {
        throw new Error('解析目录结构失败');
      }
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || '目录生成失败' });
      setStreamingContent(''); // 出错时也清空
    } finally {
      setGenerating(false);
    }
  };


  const toggleExpanded = (itemId: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId);
    } else {
      newExpanded.add(itemId);
    }
    setExpandedItems(newExpanded);
  };

  // 开始编辑目录项
  const startEditing = (item: OutlineItem) => {
    setEditingItem(item.id);
    setEditTitle(item.title);
    setEditDescription(item.description);
  };

  // 取消编辑
  const cancelEditing = () => {
    setEditingItem(null);
    setEditTitle('');
    setEditDescription('');
  };

  // 保存编辑
  const saveEdit = () => {
    if (!outlineData || !editingItem) return;

    const updateItem = (items: OutlineItem[]): OutlineItem[] => {
      return items.map(item => {
        if (item.id === editingItem) {
          return {
            ...item,
            title: editTitle.trim(),
            description: editDescription.trim()
          };
        }
        if (item.children) {
          return {
            ...item,
            children: updateItem(item.children)
          };
        }
        return item;
      });
    };

    const updatedData = {
      ...outlineData,
      outline: updateItem(outlineData.outline)
    };

    onOutlineGenerated(updatedData);
    cancelEditing();
    setMessage({ type: 'success', text: '目录项更新成功' });
  };

  // 重新分配序号的函数
  const reorderItems = (items: OutlineItem[], parentPrefix: string = ''): OutlineItem[] => {
    return items.map((item, index) => {
      const newId = parentPrefix ? `${parentPrefix}.${index + 1}` : `${index + 1}`;
      return {
        ...item,
        id: newId,
        children: item.children ? reorderItems(item.children, newId) : undefined
      };
    });
  };

  // 删除目录项
  const deleteItem = (itemId: string) => {
    if (!outlineData) return;

    if (window.confirm('确定要删除这个目录项吗？')) {
      const deleteFromItems = (items: OutlineItem[]): OutlineItem[] => {
        return items.filter(item => {
          if (item.id === itemId) {
            return false;
          }
          if (item.children) {
            item.children = deleteFromItems(item.children);
          }
          return true;
        });
      };

      // 删除项目后重新排序
      const filteredItems = deleteFromItems(outlineData.outline);
      const reorderedItems = reorderItems(filteredItems);

      const updatedData = {
        ...outlineData,
        outline: reorderedItems
      };

      onOutlineGenerated(updatedData);
      setMessage({ type: 'success', text: '目录项删除成功' });
    }
  };

  // 添加子目录项
  const addChildItem = (parentId: string) => {
    if (!outlineData) return;

    // 查找父项并计算下一个编号
    const findParentAndGetNextId = (items: OutlineItem[], targetParentId: string): string | null => {
      for (const item of items) {
        if (item.id === targetParentId) {
          // 找到父项，计算下一个子项编号
          const existingChildren = item.children || [];
          let maxChildNum = 0;
          
          existingChildren.forEach(child => {
            const childIdParts = child.id.split('.');
            const lastPart = childIdParts[childIdParts.length - 1];
            const num = parseInt(lastPart);
            if (!isNaN(num)) {
              maxChildNum = Math.max(maxChildNum, num);
            }
          });
          
          return `${parentId}.${maxChildNum + 1}`;
        }
        
        if (item.children) {
          const result = findParentAndGetNextId(item.children, targetParentId);
          if (result) return result;
        }
      }
      return null;
    };

    const newId = findParentAndGetNextId(outlineData.outline, parentId) || `${parentId}.1`;
    const newItem: OutlineItem = {
      id: newId,
      title: '新目录项',
      description: '请编辑描述',
      scoring_item_ids: [],
      requirement_ids: [],
      risk_ids: [],
      material_ids: [],
    };

    const addToItems = (items: OutlineItem[]): OutlineItem[] => {
      return items.map(item => {
        if (item.id === parentId) {
          return {
            ...item,
            children: [...(item.children || []), newItem]
          };
        }
        if (item.children) {
          return {
            ...item,
            children: addToItems(item.children)
          };
        }
        return item;
      });
    };

    const updatedData = {
      ...outlineData,
      outline: addToItems(outlineData.outline)
    };

    onOutlineGenerated(updatedData);
    
    // 展开父项
    setExpandedItems(prev => {
      const newSet = new Set(prev);
      newSet.add(parentId);
      return newSet;
    });
    
    // 自动开始编辑新项
    setTimeout(() => {
      startEditing(newItem);
    }, 100);
    
    setMessage({ type: 'success', text: '子目录添加成功' });
  };

  // 添加根目录项
  const addRootItem = () => {
    if (!outlineData) return;

    // 计算下一个根目录编号
    let maxRootNum = 0;
    outlineData.outline.forEach(item => {
      const idParts = item.id.split('.');
      const firstPart = idParts[0];
      const num = parseInt(firstPart);
      if (!isNaN(num)) {
        maxRootNum = Math.max(maxRootNum, num);
      }
    });

    const newId = `${maxRootNum + 1}`;
    const newItem: OutlineItem = {
      id: newId,
      title: '新目录项',
      description: '请编辑描述',
      scoring_item_ids: [],
      requirement_ids: [],
      risk_ids: [],
      material_ids: [],
    };

    const updatedData = {
      ...outlineData,
      outline: [...outlineData.outline, newItem]
    };

    onOutlineGenerated(updatedData);
    
    // 自动开始编辑新项
    setTimeout(() => {
      startEditing(newItem);
    }, 100);
    
    setMessage({ type: 'success', text: '目录项添加成功' });
  };

  const renderOutlineItem = (item: OutlineItem, level: number = 0) => {
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = expandedItems.has(item.id);
    const isLeaf = !hasChildren;
    const isEditing = editingItem === item.id;

    return (
      <div key={item.id} className={`${level > 0 ? 'ml-6' : ''}`}>
        <div className="group flex items-start space-x-2 py-2 hover:bg-gray-50 rounded px-2">
          {hasChildren ? (
            <button
              onClick={() => toggleExpanded(item.id)}
              className="mt-1 p-0.5 rounded hover:bg-gray-200"
            >
              {isExpanded ? (
                <ChevronDownIcon className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronRightIcon className="h-4 w-4 text-gray-400" />
              )}
            </button>
          ) : (
            <DocumentTextIcon className="mt-1 h-4 w-4 text-gray-400" />
          )}
          
          <div className="flex-1 min-w-0">
            {isEditing ? (
              // 编辑模式
              <div className="space-y-2">
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                  placeholder="目录标题"
                />
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={2}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-xs resize-none"
                  placeholder="目录描述"
                />
                <div className="flex space-x-2">
                  <button
                    onClick={saveEdit}
                    className="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-white bg-green-600 hover:bg-green-700"
                  >
                    保存
                  </button>
                  <button
                    onClick={cancelEditing}
                    className="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50"
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              // 正常显示模式
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className={`text-sm font-medium ${
                      level === 0 ? 'text-blue-600' :
                      level === 1 ? 'text-green-600' :
                      'text-gray-700'
                    }`}>
                      {item.id} {item.title}
                    </span>
                    {item.content && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        已生成内容
                      </span>
                    )}
                    {renderMappingChips(item)}
                  </div>
                  
                  {/* 操作按钮组 */}
                  <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => startEditing(item)}
                      className="p-1 rounded hover:bg-blue-100 text-blue-600"
                      title="编辑"
                    >
                      <PencilIcon className="h-3 w-3" />
                    </button>
                    <button
                      onClick={() => addChildItem(item.id)}
                      className="p-1 rounded hover:bg-green-100 text-green-600"
                      title="添加子目录"
                    >
                      <PlusIcon className="h-3 w-3" />
                    </button>
                    <button
                      onClick={() => deleteItem(item.id)}
                      className="p-1 rounded hover:bg-red-100 text-red-600"
                      title="删除"
                    >
                      <TrashIcon className="h-3 w-3" />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">{item.description}</p>
                
                {/* 显示生成的内容（如果有） */}
                {item.content && isLeaf && (
                  <div className="mt-2 p-3 bg-gray-50 rounded-md border-l-4 border-blue-200">
                    <div className="text-xs text-gray-600 whitespace-pre-wrap">{item.content}</div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
        
        {hasChildren && isExpanded && (
          <div>
            {item.children!.map(child => renderOutlineItem(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="workspace-shell">
      <section className="workspace-intro">
        <span className="workspace-kicker">Step 02</span>
        <h2 className="workspace-title">目录结构工作台</h2>
        <p className="workspace-copy">
          将招标要求和扩写材料压缩成一套可编辑目录树，方便演示“从评分条款到技术章节框架”的生成过程。
        </p>
      </section>

      {/* 操作按钮 */}
      <div className="surface-panel">
        <div className="mb-5">
          <p className="workspace-kicker">Outline Studio</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">目录管理</h2>
        </div>

        {activeAnalysisReport && (
          <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="soft-stat">
              <span className="soft-stat__label">生成模式</span>
              <span className="soft-stat__value">
                {activeAnalysisReport.bid_mode_recommendation === 'full_bid' ? '完整投标文件' : '技术标优先'}
              </span>
            </div>
            <div className="soft-stat">
              <span className="soft-stat__label">采标结构</span>
              <span className="soft-stat__value">{(activeAnalysisReport.bid_structure || []).length} 项</span>
            </div>
            <div className="soft-stat">
              <span className="soft-stat__label">固定格式/签章</span>
              <span className="soft-stat__value">
                {(activeAnalysisReport.fixed_format_forms || []).length + (activeAnalysisReport.signature_requirements || []).length} 项
              </span>
            </div>
            <div className="soft-stat">
              <span className="soft-stat__label">证据链</span>
              <span className="soft-stat__value">{(activeAnalysisReport.evidence_chain_requirements || []).length} 项</span>
            </div>
          </div>
        )}
        
        <div className="flex space-x-4">
          {/* 方案扩写按钮 */}
          <div className="relative">
            <input
              type="file"
              id="expand-file-upload"
              accept=".pdf,.docx"
              onChange={handleExpandUpload}
              className="hidden"
              disabled={uploadedExpand}
            />
            <label
              htmlFor="expand-file-upload"
              className={`inline-flex items-center rounded-2xl px-4 py-3 text-sm font-medium text-white cursor-pointer transition ${
                uploadedExpand
                  ? 'bg-slate-300 cursor-not-allowed'
                  : 'bg-gradient-to-r from-emerald-600 to-teal-600 shadow-[0_18px_40px_-20px_rgba(5,150,105,0.7)] hover:-translate-y-0.5'
              }`}
            >
              {uploadedExpand ? (
                <>
                  <div className="animate-spin -ml-1 mr-3 h-4 w-4 text-white">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </div>
                  正在分析...
                </>
              ) : (
                '方案扩写'
              )}
            </label>
          </div>

          <button
            onClick={handleGenerateOutline}
            disabled={generating || !projectOverview || !techRequirements}
            className="primary-button"
          >
            {generating ? (
              <>
                <div className="animate-spin -ml-1 mr-3 h-4 w-4 text-white">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
                正在生成目录...
              </>
            ) : (
              '生成目录结构'
            )}
          </button>

        </div>

        {/* 显示已上传的方案扩写文件 */}
        {expandFile && (
          <div className="notice-banner notice-banner--success mt-4">
            <div className="flex items-center">
              <DocumentTextIcon className="h-5 w-5 text-green-600 mr-2" />
              <span className="text-sm text-green-800">
                已上传方案扩写文件：<span className="font-medium">{expandFile.name}</span>
              </span>
            </div>
          </div>
        )}

        {!projectOverview && !techRequirements && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
            <p className="text-sm text-yellow-800">
              请先在"标书解析"步骤中完成文档分析，获取项目概述和技术评分要求。
            </p>
          </div>
        )}

        {/* 流式生成内容显示 */}
        {generating && streamingContent && (
          <div className="mt-4 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4">
            <h4 className="text-sm font-medium text-blue-800 mb-2">正在生成目录结构...</h4>
            <div className="surface-panel-soft max-h-48 overflow-y-auto">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">
                {streamingContent}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* 目录结构显示 */}
      {outlineData && (
        <div className="surface-panel">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-medium text-gray-900">目录结构</h3>
              <p className="mt-1 text-sm text-slate-500">
                已映射 {countMappedNodes(outlineData.outline)} / {countOutlineNodes(outlineData.outline)} 个节点
              </p>
            </div>
            <button
              onClick={addRootItem}
              className="secondary-button"
            >
              <PlusIcon className="h-4 w-4 mr-1" />
              添加目录项
            </button>
          </div>
          <div className="surface-panel-soft max-h-96 overflow-y-auto">
            {outlineData.outline.map(item => renderOutlineItem(item))}
          </div>
        </div>
      )}

      {/* 消息提示 */}
      {message && (
        <div className={`notice-banner ${
          message.type === 'success'
            ? 'notice-banner--success'
            : 'notice-banner--error'
        }`}>
          {message.text}
        </div>
      )}
    </div>
  );
};

export default OutlineEdit;
