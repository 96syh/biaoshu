/**
 * 文档分析页面
 */
import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { documentApi } from '../services/api';
import { AnalysisReport } from '../types';
import { CloudArrowUpIcon, DocumentIcon } from '@heroicons/react/24/outline';
import { draftStorage } from '../utils/draftStorage';
import { consumeSseStream } from '../utils/sse';

interface DocumentAnalysisProps {
  fileContent: string;
  projectOverview: string;
  techRequirements: string;
  analysisReport?: AnalysisReport;
  onFileUpload: (content: string) => void;
  onAnalysisComplete: (overview: string, requirements: string, analysisReport?: AnalysisReport) => void;
}

const DocumentAnalysis: React.FC<DocumentAnalysisProps> = ({
  fileContent,
  projectOverview,
  techRequirements,
  analysisReport,
  onFileUpload,
  onAnalysisComplete,
}) => {
  const uploadFileFormatMessage = '仅支持 PDF 和 DOCX 文件，暂不支持 DOC，请先另存为 DOCX';
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [localOverview, setLocalOverview] = useState(projectOverview);
  const [localRequirements, setLocalRequirements] = useState(techRequirements);

  useEffect(() => {
    setLocalOverview(projectOverview);
  }, [projectOverview]);

  useEffect(() => {
    setLocalRequirements(techRequirements);
  }, [techRequirements]);
  

  // 处理换行符的函数 - 只做基本转换
  const normalizeLineBreaks = (text: string) => {
    if (!text) return text;
    
    return text
      .replace(/\\n/g, '\n')  // 将字符串 \n 转换为实际换行符
      .replace(/\r\n/g, '\n') // Windows换行符
      .replace(/\r/g, '\n');  // Mac换行符
  };

  const extractJsonPayload = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      return trimmed;
    }

    const fencedMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    const candidate = fencedMatch ? fencedMatch[1].trim() : trimmed;
    const startIndexes = [candidate.indexOf('{'), candidate.indexOf('[')].filter((index) => index >= 0);
    if (startIndexes.length === 0) {
      return candidate;
    }

    const start = Math.min(...startIndexes);
    const opening = candidate[start];
    const closing = opening === '{' ? '}' : ']';
    const end = candidate.lastIndexOf(closing);
    return end > start ? candidate.slice(start, end + 1).trim() : candidate;
  };
  
  // 流式显示状态
  const [currentAnalysisStep, setCurrentAnalysisStep] = useState<'overview' | 'requirements' | 'report' | null>(null);
  const [streamingOverview, setStreamingOverview] = useState('');
  const [streamingRequirements, setStreamingRequirements] = useState('');

  const activeReport = analysisReport;
  const totalReviewItems = activeReport
    ? (activeReport.formal_review_items || []).length
      + (activeReport.qualification_review_items || []).length
      + (activeReport.responsiveness_review_items || []).length
    : 0;
  const totalScoringItems = activeReport
    ? (activeReport.business_scoring_items || []).length
      + (activeReport.technical_scoring_items || []).length
      + (activeReport.price_scoring_items || []).length
    : 0;

  const renderReportList = (
    title: string,
    items: Array<{ id?: string; name?: string; risk?: string; source?: string; target?: string; required_evidence?: string[] }>,
    emptyText: string,
  ) => (
    <div className="surface-panel-soft min-h-[180px]">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate-500">
          {items.length}
        </span>
      </div>
      {items.length > 0 ? (
        <div className="space-y-3">
          {items.slice(0, 5).map((item, index) => (
            <div key={`${item.id || item.name || item.target || title}-${index}`} className="border-t border-slate-200/80 pt-3 first:border-t-0 first:pt-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-slate-800">
                    {item.id ? `${item.id} ` : ''}{item.name || item.target || '未命名项'}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {item.risk || item.source || item.required_evidence?.join('、') || '待模型补全'}
                  </p>
                </div>
              </div>
            </div>
          ))}
          {items.length > 5 && (
            <div className="text-xs font-medium text-slate-400">还有 {items.length - 5} 项未展开</div>
          )}
        </div>
      ) : (
        <p className="text-sm leading-6 text-slate-500">{emptyText}</p>
      )}
    </div>
  );

  // 公共的 ReactMarkdown 组件配置
  const markdownComponents = {
    p: ({ children }: any) => <p className="mb-3 leading-relaxed text-sm" style={{whiteSpace: 'pre-wrap', lineHeight: '1.5'}}>{children}</p>,
    ul: ({ children }: any) => <ul className="mb-4 pl-5 space-y-1.5 list-disc">{children}</ul>,
    ol: ({ children }: any) => <ol className="mb-4 pl-5 space-y-1.5 list-decimal">{children}</ol>,
    li: ({ children }: any) => <li className="text-sm leading-relaxed">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-lg font-semibold mb-3 text-gray-900 border-b border-gray-200 pb-2">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-base font-semibold mb-2 text-gray-900">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-sm font-semibold mb-2 text-gray-800">{children}</h3>,
    strong: ({ children }: any) => <strong className="font-semibold text-gray-900">{children}</strong>,
    em: ({ children }: any) => <em className="italic text-gray-700">{children}</em>,
    blockquote: ({ children }: any) => <blockquote className="border-l-4 border-green-200 pl-4 my-3 italic text-gray-600">{children}</blockquote>,
    code: ({ children }: any) => <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>,
    table: ({ children }: any) => <table className="w-full border-collapse border border-gray-300 my-3">{children}</table>,
    thead: ({ children }: any) => <thead className="bg-gray-50">{children}</thead>,
    th: ({ children }: any) => <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-xs">{children}</th>,
    td: ({ children }: any) => <td className="border border-gray-300 px-3 py-2 text-xs">{children}</td>,
    br: () => <br className="my-1" />,
    text: ({ children }: any) => <span style={{whiteSpace: 'pre-wrap'}}>{children}</span>,
  };

  // 流式显示的紧凑样式配置
  const streamingComponents = {
    p: ({ children }: any) => <p className="mb-2 leading-tight text-xs text-blue-400" style={{whiteSpace: 'pre-wrap', lineHeight: '1.3'}}>{children}</p>,
    ul: ({ children }: any) => <ul className="mb-2 pl-3 space-y-0.5 list-disc text-blue-400">{children}</ul>,
    ol: ({ children }: any) => <ol className="mb-2 pl-3 space-y-0.5 list-decimal text-blue-400">{children}</ol>,
    li: ({ children }: any) => <li className="text-xs leading-tight text-blue-400">{children}</li>,
    h1: ({ children }: any) => <h1 className="text-sm font-semibold mb-2 text-blue-500 border-b border-blue-200 pb-1">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-xs font-semibold mb-1.5 text-blue-500">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-xs font-semibold mb-1 text-blue-400">{children}</h3>,
    strong: ({ children }: any) => <strong className="font-semibold text-blue-500">{children}</strong>,
    em: ({ children }: any) => <em className="italic text-blue-400">{children}</em>,
    blockquote: ({ children }: any) => <blockquote className="border-l-2 border-blue-300 pl-2 my-1.5 italic text-blue-400">{children}</blockquote>,
    code: ({ children }: any) => <code className="bg-blue-50 px-1 py-0.5 rounded text-xs font-mono text-blue-400">{children}</code>,
    table: ({ children }: any) => <table className="w-full border-collapse border border-blue-200 my-2">{children}</table>,
    thead: ({ children }: any) => <thead className="bg-blue-50">{children}</thead>,
    th: ({ children }: any) => <th className="border border-blue-200 px-2 py-1 text-left font-semibold text-xs text-blue-500">{children}</th>,
    td: ({ children }: any) => <td className="border border-blue-200 px-2 py-1 text-xs text-blue-400">{children}</td>,
    br: () => <br className="my-0.5" />,
    text: ({ children }: any) => <span className="text-blue-400" style={{whiteSpace: 'pre-wrap'}}>{children}</span>,
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const fileName = file.name.toLowerCase();
      if (!fileName.endsWith('.pdf') && !fileName.endsWith('.docx')) {
        setUploadedFile(null);
        setMessage({ type: 'error', text: uploadFileFormatMessage });
        event.target.value = '';
        return;
      }
      setUploadedFile(file);
      handleFileUpload(file);
    }
  };

  const handleFileUpload = async (file: File) => {
    try {
      setUploading(true);
      setMessage(null);

      const response = await documentApi.uploadFile(file);
      
      if (response.data.success && response.data.file_content) {
        // 上传新招标文件：清空上一轮 localStorage（按你的需求）
        // 注意：这会同时清掉之前保存的草稿/正文内容缓存等
        draftStorage.clearAll();
        onFileUpload(response.data.file_content);
        setMessage({ type: 'success', text: response.data.message });
      } else {
        setMessage({ type: 'error', text: response.data.message });
      }
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || '文件上传失败' });
    } finally {
      setUploading(false);
    }
  };

  const handleAnalysis = async () => {
    if (!fileContent) {
      setMessage({ type: 'error', text: '请先上传文档' });
      return;
    }

    try {
      setAnalyzing(true);
      setMessage(null);
      setStreamingOverview('');
      setStreamingRequirements('');

      let overviewResult = '';
      let requirementsResult = '';

      // 第一步：分析项目概述
      setCurrentAnalysisStep('overview');
      const overviewResponse = await documentApi.analyzeDocumentStream({
        file_content: fileContent,
        analysis_type: 'overview',
      });

      await consumeSseStream(overviewResponse, (payload) => {
        if (payload.error) {
          throw new Error(payload.message || '项目概述解析失败');
        }
        if (typeof payload.chunk !== 'string' || !payload.chunk) {
          return;
        }
        overviewResult += payload.chunk;
        setStreamingOverview(normalizeLineBreaks(overviewResult));
      });

      const finalOverview = normalizeLineBreaks(overviewResult);
      if (!finalOverview.trim()) {
        throw new Error('项目概述解析结果为空，请检查模型配置后重试');
      }
      setLocalOverview(finalOverview);

      // 第二步：分析技术评分要求
      setCurrentAnalysisStep('requirements');
      const requirementsResponse = await documentApi.analyzeDocumentStream({
        file_content: fileContent,
        analysis_type: 'requirements',
      });

      await consumeSseStream(requirementsResponse, (payload) => {
        if (payload.error) {
          throw new Error(payload.message || '技术评分要求解析失败');
        }
        if (typeof payload.chunk !== 'string' || !payload.chunk) {
          return;
        }
        requirementsResult += payload.chunk;
        setStreamingRequirements(normalizeLineBreaks(requirementsResult));
      });

      const finalRequirements = normalizeLineBreaks(requirementsResult);
      if (!finalRequirements.trim()) {
        throw new Error('技术评分要求解析结果为空，请检查模型配置后重试');
      }
      setLocalRequirements(finalRequirements);

      // 第三步：生成后续目录、正文和审校共用的结构化标准解析报告
      setCurrentAnalysisStep('report');
      const reportResponse = await documentApi.analyzeReportStream({
        file_content: fileContent,
      });

      let reportResult = '';
      await consumeSseStream(reportResponse, (payload) => {
        if (payload.error) {
          throw new Error(payload.message || '结构化标准解析报告生成失败');
        }
        if (typeof payload.chunk !== 'string' || !payload.chunk) {
          return;
        }
        reportResult += payload.chunk;
      });

      const analysisReport = JSON.parse(extractJsonPayload(reportResult)) as AnalysisReport;

      // 完成后更新父组件状态
      onAnalysisComplete(finalOverview, finalRequirements, analysisReport);
      setMessage({ type: 'success', text: '标书解析完成' });
      
      // 清空流式内容
      setStreamingOverview('');
      setStreamingRequirements('');
      setCurrentAnalysisStep(null);

    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || '标书解析失败' });
      setStreamingOverview('');
      setStreamingRequirements('');
      setCurrentAnalysisStep(null);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="workspace-shell">
      <section className="workspace-intro">
        <span className="workspace-kicker">Step 01</span>
        <h2 className="workspace-title">招标资料解析台</h2>
        <p className="workspace-copy">
          上传 PDF 或 DOCX，系统会先抽取原文，再进入项目概述与技术评分拆解。这里建议用真实招标书演示，展示效果最直观。
        </p>
      </section>

      {/* 文件上传区域 */}
      <div className="surface-panel">
        <div className="mb-5">
          <p className="workspace-kicker">Source File</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">文档上传</h2>
        </div>
        
        <div 
          className="rounded-[28px] border border-dashed border-slate-300 bg-slate-50/70 px-8 py-14 text-center transition hover:border-sky-300 hover:bg-white/90 cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-sky-500 to-teal-500 shadow-[0_24px_54px_-26px_rgba(29,78,216,0.55)]">
            <CloudArrowUpIcon className="h-8 w-8 text-white" />
          </div>
          <div className="mt-4">
            <p className="text-lg font-medium text-slate-800">
              {uploadedFile ? uploadedFile.name : '点击选择文件或拖拽文件到这里'}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              支持 PDF 和 DOCX 文档，最大 10MB
            </p>
          </div>
          
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
        
        {uploading && (
          <div className="mt-4 text-center">
            <div className="inline-flex items-center rounded-full bg-sky-50 px-4 py-2 text-sm font-medium text-sky-700">
              <div className="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              正在上传和处理文件...
            </div>
          </div>
        )}
      </div>

      {/* 文档分析区域 */}
      {fileContent && (
        <div className="surface-panel">
          <div className="mb-5">
            <p className="workspace-kicker">Analysis</p>
            <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">文档分析</h2>
          </div>
          
          <div className="flex justify-center mb-6">
            <button
              onClick={handleAnalysis}
              disabled={analyzing}
              className="primary-button min-w-[180px]"
            >
              {analyzing ? (
                <>
                  <div className="animate-spin -ml-1 mr-3 h-5 w-5 text-white">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 714 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </div>
                  {currentAnalysisStep === 'overview' ? '正在分析项目概述...' : 
                   currentAnalysisStep === 'requirements' ? '正在分析技术评分要求...' : 
                   currentAnalysisStep === 'report' ? '正在生成标准解析报告...' :
                   '正在解析标书...'}
                </>
              ) : (
                <>
                  <DocumentIcon className="w-5 h-5 mr-2" />
                  解析标书
                </>
              )}
            </button>
          </div>

          {/* 流式分析内容显示 */}
          {analyzing && (((currentAnalysisStep === 'overview') && streamingOverview) || ((currentAnalysisStep === 'requirements') && streamingRequirements)) && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="mb-3 text-sm font-medium text-blue-800">
                {currentAnalysisStep === 'overview' ? '正在分析项目概述...' : '正在分析技术评分要求...'}
              </h4>
              <div className="surface-panel-soft max-h-64 overflow-y-auto">
                <div className="text-xs prose prose-sm max-w-none">
                  <ReactMarkdown components={streamingComponents}>
                    {currentAnalysisStep === 'overview' ? streamingOverview : streamingRequirements}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}


          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 项目概述 */}
            <div>
              <label className="mb-3 block text-sm font-medium text-slate-700">
                项目概述
              </label>
              <div className="surface-panel-soft max-h-80 overflow-y-auto">
                <div className="prose prose-sm max-w-none text-gray-800">
                  <ReactMarkdown components={markdownComponents}>
                    {localOverview || '项目概述将在这里显示...'}
                  </ReactMarkdown>
                </div>
              </div>
            </div>

            {/* 技术评分要求 */}
            <div>
              <label className="mb-3 block text-sm font-medium text-slate-700">
                技术评分要求
              </label>
              <div className="surface-panel-soft max-h-80 overflow-y-auto">
                <div className="prose prose-sm max-w-none text-gray-800">
                  <ReactMarkdown components={markdownComponents}>
                    {localRequirements || '技术评分要求将在这里显示...'}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          </div>

          {activeReport && (
            <section className="mt-6 space-y-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <p className="workspace-kicker">AnalysisReport</p>
                  <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-950">采标分析报告摘要</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    {activeReport.project.name || '未识别项目名称'} · {activeReport.bid_mode_recommendation === 'full_bid' ? '完整投标文件' : '技术标优先'}
                  </p>
                </div>
                <div className="rounded-full border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-600">
                  {activeReport.project.number || activeReport.project.package_name || '项目编号待识别'}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <div className="soft-stat">
                  <span className="soft-stat__label">投标结构</span>
                  <span className="soft-stat__value">{(activeReport.bid_structure || []).length} 项</span>
                </div>
                <div className="soft-stat">
                  <span className="soft-stat__label">评审条款</span>
                  <span className="soft-stat__value">{totalReviewItems} 项</span>
                </div>
                <div className="soft-stat">
                  <span className="soft-stat__label">评分项</span>
                  <span className="soft-stat__value">{totalScoringItems} 项</span>
                </div>
                <div className="soft-stat">
                  <span className="soft-stat__label">风险点</span>
                  <span className="soft-stat__value">{(activeReport.rejection_risks || []).length} 项</span>
                </div>
                <div className="soft-stat">
                  <span className="soft-stat__label">待补资料</span>
                  <span className="soft-stat__value">{(activeReport.missing_company_materials || []).length} 项</span>
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-3">
                {renderReportList(
                  '废标与高风险',
                  (activeReport.rejection_risks || []).map(item => ({
                    id: item.id,
                    name: item.risk,
                    risk: item.mitigation,
                    source: item.source,
                  })),
                  '未提取到单独废标风险。',
                )}
                {renderReportList(
                  '固定格式与签章',
                  [
                    ...(activeReport.fixed_format_forms || []).map(item => ({
                      id: item.id,
                      name: item.name,
                      risk: item.fill_rules || item.fixed_text,
                      source: item.source,
                    })),
                    ...(activeReport.signature_requirements || []).map(item => ({
                      id: item.id,
                      name: item.target,
                      risk: item.risk || `${item.signer} ${item.seal}`.trim(),
                      source: item.source,
                    })),
                  ],
                  '未提取到固定格式或签章要求。',
                )}
                {renderReportList(
                  '证据链与补料',
                  [
                    ...(activeReport.evidence_chain_requirements || []).map(item => ({
                      id: item.id,
                      target: item.target,
                      required_evidence: item.required_evidence,
                      risk: item.risk || item.validation_rule,
                      source: item.source,
                    })),
                    ...(activeReport.missing_company_materials || []).map(item => ({
                      id: item.id,
                      name: item.name,
                      risk: item.placeholder,
                      source: item.used_by.join('、'),
                    })),
                  ],
                  '暂无证据链或补料项。',
                )}
              </div>
            </section>
          )}
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

export default DocumentAnalysis;
