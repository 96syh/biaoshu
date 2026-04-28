import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { saveAs } from 'file-saver';
import {
  ArrowDownTrayIcon,
  Bars3BottomLeftIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  Cog6ToothIcon,
  DocumentArrowUpIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  FolderIcon,
  PauseIcon,
  PencilSquareIcon,
  PlayIcon,
  ShieldCheckIcon,
  SparklesIcon,
  StopIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useAppState } from './hooks/useAppState';
import { DEFAULT_PROVIDER_ID, LITELLM_PROVIDER } from './constants/providers';
import {
  ChapterContentRequest,
  ProviderVerifyResponse,
  configApi,
  contentApi,
  documentApi,
  outlineApi,
} from './services/api';
import {
  AnalysisReport,
  BidMode,
  ConfigData,
  OutlineData,
  OutlineItem,
  ReviewReport,
} from './types';
import { consumeSseStream } from './utils/sse';
import { DraftHistoryRecord, draftStorage } from './utils/draftStorage';

type Notice = { type: 'success' | 'error' | 'info'; text: string };
type NavKey = 'project' | 'analysis' | 'outline' | 'content' | 'review' | 'config';
type ProgressState = {
  label: string;
  detail: string;
  percent: number;
  stepIndex: number;
  steps: string[];
  status: 'running' | 'success' | 'error';
  error?: string;
};
type GenerationControlState = 'idle' | 'running' | 'paused' | 'stopped';
type DraftOutlineRow = { id: string; title: string; level: number; status: string };
type ProjectSummary = Partial<AnalysisReport['project']> & { __fallback?: boolean };

interface ChapterEntry {
  item: OutlineItem;
  parents: OutlineItem[];
  top: OutlineItem;
}

const PAGE_META: Record<Exclude<NavKey, 'config'>, { title: string; description: string }> = {
  project: {
    title: '上传文件',
    description: '上传招标文件并查看项目基础信息、材料缺失提示和解析入口。',
  },
  analysis: {
    title: '开始解析',
    description: '抽取项目概况、评分办法、资格审查、实质性要求和材料清单。',
  },
  outline: {
    title: '生成目录',
    description: '把评分项、审查项、风险项和材料项映射到正式投标文件目录。',
  },
  content: {
    title: '生成正文',
    description: '选择章节生成正文，预览当前章节内容，并支持批量生成与导出。',
  },
  review: {
    title: '执行审校',
    description: '检查覆盖率、阻塞项、固定格式、签章、报价和证据链风险。',
  },
};

const NAV_ITEMS: Array<{ key: NavKey; label: string; description: string; icon: React.ElementType; target?: string }> = [
  { key: 'project', label: '上传文件', description: '选择招标文件', icon: FolderIcon, target: 'panel-analysis' },
  { key: 'analysis', label: '开始解析', description: '抽取条款与评分', icon: DocumentTextIcon, target: 'panel-analysis' },
  { key: 'outline', label: '生成目录', description: '映射评分风险', icon: Bars3BottomLeftIcon, target: 'panel-outline' },
  { key: 'content', label: '生成正文', description: '写入选中章节', icon: PencilSquareIcon, target: 'panel-content' },
  { key: 'review', label: '执行审校', description: '检查合规风险', icon: ShieldCheckIcon, target: 'panel-review' },
  { key: 'config', label: '模型配置', description: 'LiteLLM 接入', icon: Cog6ToothIcon },
];

const FLOW_STEPS = ['上传', '标准解析', '目录映射', '正文生成', '合规审校', '导出'];
const ANALYSIS_STEPS = ['文件解析', '条款识别', '评分项提取', '合规要求提取'];
const toLiteLLMConfig = (config?: Partial<ConfigData>): ConfigData => ({
  provider: DEFAULT_PROVIDER_ID,
  api_key: config?.api_key || '',
  base_url: config?.base_url || LITELLM_PROVIDER.baseUrl,
  model_name: config?.model_name || '',
  api_mode: 'chat',
});

const extractJsonPayload = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  const candidate = fenced ? fenced[1].trim() : trimmed;
  const starts = [candidate.indexOf('{'), candidate.indexOf('[')].filter(index => index >= 0);
  if (starts.length === 0) return candidate;
  const start = Math.min(...starts);
  const closing = candidate[start] === '{' ? '}' : ']';
  const end = candidate.lastIndexOf(closing);
  return end > start ? candidate.slice(start, end + 1).trim() : candidate;
};

const collectEntries = (items: OutlineItem[], parents: OutlineItem[] = [], top?: OutlineItem): ChapterEntry[] =>
  items.flatMap((item) => {
    const currentTop = top || item;
    if (!item.children?.length) return [{ item, parents, top: currentTop }];
    return collectEntries(item.children, [...parents, item], currentTop);
  });

const findFirstLeaf = (item: OutlineItem): OutlineItem => {
  if (!item.children?.length) return item;
  return findFirstLeaf(item.children[0]);
};

const docSectionId = (id: string) => `doc-section-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;

const apiErrorMessage = (error: any, fallback: string) => {
  if (error?.response?.data?.detail) return error.response.data.detail;
  if (error?.response?.data?.message) return error.response.data.message;
  if (error?.message === 'Network Error') {
    return '无法连接应用后端服务。请先启动后端 API（默认 http://localhost:8000），再同步模型；LiteLLM/Base URL 是模型代理地址，不是前端直连地址。';
  }
  return error?.message || fallback;
};

const updateOutlineItem = (items: OutlineItem[], id: string, patch: Partial<OutlineItem>): OutlineItem[] =>
  items.map((item) => {
    if (item.id === id) return { ...item, ...patch };
    if (!item.children?.length) return item;
    return { ...item, children: updateOutlineItem(item.children, id, patch) };
  });

const buildExportOutline = (items: OutlineItem[], contentById: Record<string, string>): OutlineItem[] =>
  items.map((item) => ({
    ...item,
    content: contentById[item.id] ?? item.content,
    children: item.children ? buildExportOutline(item.children, contentById) : undefined,
  }));

const countNodes = (items: OutlineItem[]): number =>
  items.reduce((sum, item) => sum + 1 + (item.children ? countNodes(item.children) : 0), 0);

const countMapped = (items: OutlineItem[]): number =>
  items.reduce((sum, item) => {
    const mapped = Boolean(item.scoring_item_ids?.length || item.requirement_ids?.length || item.risk_ids?.length || item.material_ids?.length);
    return sum + (mapped ? 1 : 0) + (item.children ? countMapped(item.children) : 0);
  }, 0);

const riskLevel = (item: OutlineItem) => {
  if (item.risk_ids?.length) return '高风险';
  if ((item.material_ids?.length || 0) > 1) return '中风险';
  return '低风险';
};

const isMeaningfulValue = (value?: string | null) => {
  const normalized = (value || '').trim();
  if (!normalized) return false;
  return !['待模型解析', '待解析', '无', '暂无', '未提供', '未明确', '不详', 'null', 'undefined'].includes(normalized);
};

const findFieldInText = (text: string, labels: string[]) => {
  for (const label of labels) {
    const pattern = new RegExp(`${label}\\s*[：:]\\s*([^\\n；;，,]{2,80})`, 'i');
    const match = text.match(pattern);
    if (match?.[1]) return match[1].replace(/[。；;，,]$/, '').trim();
  }
  return '';
};

const buildProjectSummary = (
  report: AnalysisReport | null,
  overview: string,
  requirements: string,
  fileContent: string,
): ProjectSummary | undefined => {
  if (!report?.project) return undefined;
  const sourceText = [overview, requirements, fileContent.slice(0, 30000)].filter(Boolean).join('\n');
  const project = report.project;
  const fallback: ProjectSummary = {
    ...project,
    name: isMeaningfulValue(project.name) ? project.name : findFieldInText(sourceText, ['项目名称', '采购项目名称', '招标项目名称', '项目']),
    number: isMeaningfulValue(project.number) ? project.number : findFieldInText(sourceText, ['项目编号', '采购项目编号', '招标编号', '项目代码']),
    purchaser: isMeaningfulValue(project.purchaser) ? project.purchaser : findFieldInText(sourceText, ['采购人', '招标人', '采购单位', '建设单位']),
    service_period: isMeaningfulValue(project.service_period) ? project.service_period : findFieldInText(sourceText, ['服务期限', '服务期', '履约期限', '工期']),
    budget: isMeaningfulValue(project.budget) ? project.budget : findFieldInText(sourceText, ['预算金额', '采购预算', '最高限价', '控制价']),
    bid_deadline: isMeaningfulValue(project.bid_deadline) ? project.bid_deadline : findFieldInText(sourceText, ['提交截止时间', '投标截止时间', '响应文件提交截止时间', '开标时间']),
  };
  fallback.__fallback = ['name', 'number', 'purchaser', 'service_period', 'budget', 'bid_deadline'].some((key) => {
    const typedKey = key as keyof AnalysisReport['project'];
    return !isMeaningfulValue(project[typedKey]) && isMeaningfulValue(fallback[typedKey]);
  });
  return fallback;
};

const parseOutlineDraftRows = (raw: string): DraftOutlineRow[] => {
  const rows: DraftOutlineRow[] = [];
  const seen = new Set<string>();
  const objectPattern = /"id"\s*:\s*"([^"]+)"[\s\S]{0,260}?"title"\s*:\s*"([^"]+)"/g;
  let objectMatch: RegExpExecArray | null;
  while ((objectMatch = objectPattern.exec(raw)) && rows.length < 40) {
    const id = objectMatch[1].trim();
    const title = objectMatch[2].trim();
    if (!id || !title || seen.has(id)) continue;
    seen.add(id);
    rows.push({ id, title, level: Math.max(0, id.split('.').length - 1), status: '正在映射' });
  }

  if (rows.length) return rows;

  const titlePattern = /"title"\s*:\s*"([^"]+)"/g;
  let titleMatch: RegExpExecArray | null;
  while ((titleMatch = titlePattern.exec(raw)) && rows.length < 24) {
    const title = titleMatch[1].trim();
    if (!title || seen.has(title)) continue;
    seen.add(title);
    rows.push({ id: `${rows.length + 1}`, title, level: 0, status: '生成中' });
  }
  return rows;
};

const App = () => {
  const {
    state,
    updateConfig,
    updateFileContent,
    updateAnalysisResults,
    updateOutline,
    updateSelectedChapter,
    restoreDraft,
  } = useAppState();

  const [activeNav, setActiveNav] = useState<NavKey>('project');
  const [configOpen, setConfigOpen] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [busy, setBusy] = useState('');
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [streamText, setStreamText] = useState('');
  const [reviewReport, setReviewReport] = useState<ReviewReport | null>(null);
  const [verifyResult, setVerifyResult] = useState<ProviderVerifyResponse | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [localConfig, setLocalConfig] = useState<ConfigData>(state.config);
  const [selectedBidMode, setSelectedBidMode] = useState<BidMode>('full_bid');
  const [activeDocId, setActiveDocId] = useState('');
  const [outlineDraftRows, setOutlineDraftRows] = useState<DraftOutlineRow[]>([]);
  const [streamingChapterId, setStreamingChapterId] = useState('');
  const [generationControl, setGenerationControl] = useState<GenerationControlState>('idle');
  const [generationProgress, setGenerationProgress] = useState<ProgressState | null>(null);
  const [historyRecords, setHistoryRecords] = useState<DraftHistoryRecord[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docPreviewRef = useRef<HTMLElement>(null);
  const progressVersionRef = useRef(0);
  const generationAbortRef = useRef<AbortController | null>(null);
  const generationPausedRef = useRef(false);
  const generationStoppedRef = useRef(false);
  const batchOutlineRef = useRef<OutlineData | null>(null);

  const activeReport = state.analysisReport || state.outlineData?.analysis_report || null;
  const effectiveOutline = state.outlineData;
  const activeResponseMatrix = effectiveOutline?.response_matrix || activeReport?.response_matrix || null;
  const responseMatrixItems = activeResponseMatrix?.items || [];
  const highRiskMatrixCount = responseMatrixItems.filter(item => item.priority === 'high' || item.blocking).length;
  const uncoveredMatrixCount = activeResponseMatrix?.uncovered_ids?.length || responseMatrixItems.filter(item => item.status !== 'covered').length;
  const entries = useMemo(() => effectiveOutline ? collectEntries(effectiveOutline.outline) : [], [effectiveOutline]);
  const selectedEntry = entries.find(entry => entry.item.id === state.selectedChapter) || entries[0];
  const project = useMemo(
    () => buildProjectSummary(activeReport, state.projectOverview, state.techRequirements, state.fileContent),
    [activeReport, state.projectOverview, state.techRequirements, state.fileContent],
  );
  const completedLeaves = entries.filter(entry => entry.item.content?.trim()).length;
  const coverage = entries.length > 0 ? Math.round((completedLeaves / entries.length) * 100) : 0;
  const reviewCoverage = reviewReport?.summary.coverage_rate !== undefined && reviewReport?.summary.coverage_rate !== null
    ? Math.round(reviewReport.summary.coverage_rate)
    : reviewReport?.coverage.length
    ? Math.round((reviewReport.coverage.filter(item => item.covered).length / reviewReport.coverage.length) * 100)
    : null;
  const blockingIssues = reviewReport?.summary.blocking_issues_count ?? reviewReport?.summary.blocking_issues ?? null;
  const warningIssues = reviewReport?.summary.warnings_count ?? reviewReport?.summary.warnings ?? null;
  const infoIssues = reviewReport
    ? reviewReport.duplication_issues.length + reviewReport.fabrication_risks.length + reviewReport.rejection_risks.filter(item => item.handled).length + (reviewReport.revision_plan?.actions.length || 0)
    : null;
  const projectTitle = project?.name || effectiveOutline?.project_name || '待解析项目';

  useEffect(() => setLocalConfig(state.config), [state.config]);

  useEffect(() => {
    setHistoryRecords(draftStorage.loadHistory());
  }, [state.fileContent, state.analysisReport, state.outlineData, state.selectedChapter]);

  useEffect(() => {
    const syncPageFromHash = () => {
      const key = window.location.hash.replace(/^#\/?/, '') as NavKey;
      if (!NAV_ITEMS.some(item => item.key === key)) return;
      if (key === 'config') {
        setConfigOpen(true);
        return;
      }
      setActiveNav(key);
    };

    syncPageFromHash();
    window.addEventListener('hashchange', syncPageFromHash);
    return () => window.removeEventListener('hashchange', syncPageFromHash);
  }, []);

  useEffect(() => {
    configApi.loadConfig()
      .then((response) => {
        if (!response.data) return;
        const nextConfig = toLiteLLMConfig(response.data);
        updateConfig(nextConfig);
        setLocalConfig(nextConfig);
        setAvailableModels(LITELLM_PROVIDER.models);
      })
      .catch(() => {
        // 后端未启动时保留默认配置，避免阻塞 UI 渲染。
      });
  }, [updateConfig]);

  useEffect(() => {
    if (!state.selectedChapter && entries[0]) updateSelectedChapter(entries[0].item.id);
  }, [entries, state.selectedChapter, updateSelectedChapter]);

  useEffect(() => {
    if (!activeDocId && selectedEntry?.item.id) setActiveDocId(selectedEntry.item.id);
  }, [activeDocId, selectedEntry?.item.id]);

  useEffect(() => {
    if (activeReport?.bid_mode_recommendation) setSelectedBidMode(activeReport.bid_mode_recommendation);
  }, [activeReport?.bid_mode_recommendation]);

  const setError = (text: string) => setNotice({ type: 'error', text });
  const setSuccess = (text: string) => setNotice({ type: 'success', text });
  const setInfo = (text: string) => setNotice({ type: 'info', text });
  const refreshHistory = () => setHistoryRecords(draftStorage.loadHistory());

  const clampProgress = (value: number) => Math.max(0, Math.min(100, Math.round(value)));

  const startProgress = (label: string, steps: string[], detail: string, percent = 5) => {
    progressVersionRef.current += 1;
    const version = progressVersionRef.current;
    setProgress({ label, steps, detail, percent: clampProgress(percent), stepIndex: 0, status: 'running' });
    return version;
  };

  const advanceProgress = (detail: string, percent: number, stepIndex?: number, taskVersion = progressVersionRef.current) => {
    if (taskVersion !== progressVersionRef.current) return;
    setProgress(prev => prev
      ? { ...prev, detail, percent: clampProgress(percent), stepIndex: stepIndex ?? prev.stepIndex, status: 'running', error: undefined }
      : { label: '处理中', detail, percent: clampProgress(percent), stepIndex: stepIndex ?? 0, steps: [], status: 'running' });
  };

  const completeProgress = (detail: string, taskVersion = progressVersionRef.current) => {
    if (taskVersion !== progressVersionRef.current) return;
    setProgress(prev => {
      if (!prev) return null;
      return {
        ...prev,
        detail,
        percent: 100,
        stepIndex: Math.max(prev.stepIndex, prev.steps.length - 1),
        status: 'success',
        error: undefined,
      };
    });
    window.setTimeout(() => {
      if (progressVersionRef.current === taskVersion) setProgress(null);
    }, 900);
  };

  const failProgress = (detail: string, stepIndex?: number, taskVersion = progressVersionRef.current) => {
    if (taskVersion !== progressVersionRef.current) return;
    progressVersionRef.current += 1;
    setProgress(prev => ({
      label: prev?.label || '处理失败',
      steps: prev?.steps || [],
      detail: '处理失败',
      percent: prev?.percent || 100,
      stepIndex: stepIndex ?? prev?.stepIndex ?? 0,
      status: 'error',
      error: detail,
    }));
  };

  const withTaskTimeout = async <T,>(promise: Promise<T>, message: string, taskVersion: number, timeoutMs = 300000): Promise<T> => {
    let timeoutId: number | undefined;
    try {
      return await Promise.race([
        promise,
        new Promise<T>((_, reject) => {
          timeoutId = window.setTimeout(() => {
            if (taskVersion === progressVersionRef.current) reject(new Error(message));
          }, timeoutMs);
        }),
      ]);
    } finally {
      if (timeoutId) window.clearTimeout(timeoutId);
    }
  };

  const syncGenerationProgress = (detail: string, percent: number, stepIndex = 0, label = '正文生成') => {
    setGenerationProgress(prev => ({
      label,
      detail,
      percent: clampProgress(percent),
      stepIndex,
      steps: prev?.steps?.length ? prev.steps : ['准备章节', '模型写入', '保存正文'],
      status: 'running',
    }));
  };

  const waitIfGenerationPaused = async () => {
    while (generationPausedRef.current && !generationStoppedRef.current) {
      await new Promise(resolve => window.setTimeout(resolve, 160));
    }
    if (generationStoppedRef.current) {
      throw new DOMException('已停止生成', 'AbortError');
    }
  };

  const resetGenerationControls = () => {
    generationPausedRef.current = false;
    generationStoppedRef.current = false;
    generationAbortRef.current = null;
    setStreamingChapterId('');
    setGenerationControl('idle');
  };

  const pauseGeneration = () => {
    if (!busy.startsWith('chapter') && busy !== 'batch') return;
    generationPausedRef.current = true;
    setGenerationControl('paused');
    setGenerationProgress(prev => prev ? { ...prev, detail: `已暂停：${prev.detail}`, status: 'running' } : prev);
  };

  const resumeGeneration = () => {
    if (!generationPausedRef.current) return;
    generationPausedRef.current = false;
    setGenerationControl('running');
    setGenerationProgress(prev => prev ? { ...prev, detail: prev.detail.replace(/^已暂停：/, ''), status: 'running' } : prev);
  };

  const stopGeneration = () => {
    if (!busy.startsWith('chapter') && busy !== 'batch') return;
    generationStoppedRef.current = true;
    generationPausedRef.current = false;
    generationAbortRef.current?.abort();
    setGenerationControl('stopped');
    setGenerationProgress(prev => prev ? { ...prev, detail: '已停止生成，可重新选择章节继续', status: 'error' } : prev);
  };

  const scrollToDocumentNode = (item: OutlineItem) => {
    const firstLeaf = findFirstLeaf(item);
    setActiveDocId(item.id);
    updateSelectedChapter(firstLeaf.id);
    window.requestAnimationFrame(() => {
      document.getElementById(docSectionId(item.id))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const goToPage = (key: NavKey) => {
    if (key === 'config') {
      setConfigOpen(true);
      window.history.pushState(null, '', '#config');
      return;
    }
    setActiveNav(key);
    window.history.pushState(null, '', `#${key}`);
  };

  const restoreHistoryRecord = (record: DraftHistoryRecord) => {
    const activated = draftStorage.activateHistory(record.id);
    restoreDraft((activated || record).draft);
    setReviewReport(null);
    setActiveDocId(record.draft.selectedChapter || '');
    setUploadedFileName(record.title);
    refreshHistory();
    setSuccess(`已恢复历史记录：${record.title}`);
    if (record.draft.outlineData) {
      goToPage('content');
    } else if (record.draft.analysisReport) {
      goToPage('outline');
    } else if (record.draft.fileContent) {
      goToPage('analysis');
    } else {
      goToPage('project');
    }
  };

  const handleModeChange = (mode: BidMode) => {
    setSelectedBidMode(mode);
    if (effectiveOutline) updateOutline({ ...effectiveOutline, bid_mode: mode });
    setInfo(mode === 'technical_only' ? '已切换为技术标生成，后续目录、正文和审校会按技术标模式请求模型' : '已切换为完整标书生成');
  };

  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().match(/\.(pdf|docx)$/)) {
      setError('仅支持 PDF 和 DOCX 文件');
      return;
    }
    if (file.size > 500 * 1024 * 1024) {
      setError('文件大小不能超过 500MB');
      return;
    }
    setBusy('upload');
    const taskVersion = startProgress('文件上传', ['读取文件', '后端解析文本'], '正在上传并读取招标文件', 12);
    setNotice(null);
    try {
      const response = await documentApi.uploadFile(file);
      if (!response.data.success || !response.data.file_content) throw new Error(response.data.message || '上传失败');
      setUploadedFileName(file.name);
      updateFileContent(response.data.file_content);
      completeProgress('文件已上传，文本读取完成', taskVersion);
      setSuccess('招标文件已上传，开始进行标准解析');
    } catch (error: any) {
      failProgress(error.response?.data?.detail || error.message || '文件上传失败', 1, taskVersion);
      setError(error.response?.data?.detail || error.message || '文件上传失败');
    } finally {
      setBusy('');
    }
  };

  const runAnalysis = async () => {
    if (!state.fileContent) {
      setError('请先上传招标文件');
      return;
    }
    setBusy('analysis');
    const taskVersion = startProgress('标准解析', ANALYSIS_STEPS, '准备调用模型解析招标文件', 6);
    setStreamText('');
    setReviewReport(null);
    try {
      let overview = '';
      advanceProgress('正在抽取项目概况与基础信息', 12, 0, taskVersion);
      let requirements = '';
      const overviewResponse = await documentApi.analyzeDocumentStream({ file_content: state.fileContent, analysis_type: 'overview' });
      await withTaskTimeout(consumeSseStream(overviewResponse, (payload) => {
        if (payload.error) throw new Error(payload.message || '项目概述解析失败');
        if (typeof payload.chunk === 'string') {
          overview += payload.chunk;
          setStreamText(overview);
          advanceProgress('正在抽取项目概况与基础信息', Math.min(30, 12 + Math.floor(overview.length / 160)), 0, taskVersion);
        }
      }), '项目概况解析超时，请检查模型服务是否仍在响应', taskVersion);
      advanceProgress('正在识别招标条款、评分办法和响应要求', 36, 1, taskVersion);
      const requirementsResponse = await documentApi.analyzeDocumentStream({ file_content: state.fileContent, analysis_type: 'requirements' });
      await withTaskTimeout(consumeSseStream(requirementsResponse, (payload) => {
        if (payload.error) throw new Error(payload.message || '评分要求解析失败');
        if (typeof payload.chunk === 'string') {
          requirements += payload.chunk;
          setStreamText(requirements);
          advanceProgress('正在识别招标条款、评分办法和响应要求', Math.min(58, 36 + Math.floor(requirements.length / 180)), 1, taskVersion);
        }
      }), '评分要求解析超时，请检查模型服务是否仍在响应', taskVersion);
      let reportRaw = '';
      advanceProgress('正在结构化评分项、风险项和材料清单', 66, 2, taskVersion);
      const reportResponse = await documentApi.analyzeReportStream({ file_content: state.fileContent });
      await withTaskTimeout(consumeSseStream(reportResponse, (payload) => {
        if (payload.error) throw new Error(payload.message || '结构化解析失败');
        if (typeof payload.chunk === 'string') {
          reportRaw += payload.chunk;
          advanceProgress('正在结构化评分项、风险项和材料清单', Math.min(92, 66 + Math.floor(reportRaw.length / 220)), reportRaw.length > 900 ? 3 : 2, taskVersion);
        }
      }), '结构化解析超时，请检查模型服务或尝试换用更快的模型', taskVersion);
      advanceProgress('正在校验并写入结构化解析结果', 96, 3, taskVersion);
      const report = JSON.parse(extractJsonPayload(reportRaw)) as AnalysisReport;
      updateAnalysisResults(overview.trim(), requirements.trim(), report);
      setStreamText('');
      completeProgress('标准解析完成', taskVersion);
      setSuccess('标准解析完成，已生成项目、评分、风险和材料结构');
    } catch (error: any) {
      failProgress(error.message || '标准解析失败', undefined, taskVersion);
      setError(error.message || '标准解析失败');
    } finally {
      setBusy('');
    }
  };

  const runOutline = async () => {
    if (!state.projectOverview || !state.techRequirements || !state.analysisReport) {
      setError('请先完成标准解析');
      return;
    }
    setBusy('outline');
    const taskVersion = startProgress('目录生成', ['构建输入', '生成目录', '映射评分风险'], '正在准备目录生成上下文', 8);
    setStreamText('');
    setOutlineDraftRows((state.analysisReport?.bid_structure || []).slice(0, 8).map((item, index) => ({
      id: item.id || `${index + 1}`,
      title: item.title || item.purpose || `候选章节 ${index + 1}`,
      level: item.parent_id ? 1 : 0,
      status: '待模型确认',
    })));
    try {
      let raw = '';
      advanceProgress('正在调用模型生成目录和映射关系', 16, 1, taskVersion);
      const response = await outlineApi.generateOutlineStream({
        overview: state.projectOverview,
        requirements: state.techRequirements,
        analysis_report: state.analysisReport,
        bid_mode: selectedBidMode,
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '目录生成失败');
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          setStreamText(raw);
          const draftRows = parseOutlineDraftRows(raw);
          if (draftRows.length) setOutlineDraftRows(draftRows);
          advanceProgress('正在调用模型生成目录和映射关系', Math.min(92, 16 + Math.floor(raw.length / 220)), raw.length > 1000 ? 2 : 1, taskVersion);
        }
      });
      advanceProgress('正在写入目录结构和评分映射', 96, 2, taskVersion);
      const outline = JSON.parse(extractJsonPayload(raw)) as OutlineData;
      const nextOutline = {
        ...outline,
        project_name: state.analysisReport.project?.name || '投标文件',
        project_overview: state.projectOverview,
        analysis_report: state.analysisReport,
        response_matrix: outline.response_matrix || state.analysisReport.response_matrix,
        coverage_summary: outline.coverage_summary || state.analysisReport.response_matrix?.coverage_summary,
        bid_mode: selectedBidMode,
      };
      updateOutline(nextOutline);
      const first = collectEntries(nextOutline.outline)[0];
      if (first) updateSelectedChapter(first.item.id);
      setStreamText('');
      setOutlineDraftRows([]);
      completeProgress('目录生成完成', taskVersion);
      setSuccess('目录映射完成，章节已关联评分、风险和材料项');
    } catch (error: any) {
      failProgress(error.message || '目录生成失败', undefined, taskVersion);
      setError(error.message || '目录生成失败');
    } finally {
      setBusy('');
    }
  };

  const generateChapter = async (
    entry: ChapterEntry,
    options?: {
      signal?: AbortSignal;
      onContent?: (content: string) => void;
      onProgress?: (content: string) => void;
    },
  ) => {
    if (!effectiveOutline) throw new Error('缺少目录数据');
    if (!activeReport) throw new Error('缺少结构化解析结果，请先完成标准解析');
    const siblingItems = entry.parents.length
      ? entry.parents[entry.parents.length - 1].children || []
      : effectiveOutline.outline;
    const request: ChapterContentRequest = {
      chapter: entry.item,
      parent_chapters: entry.parents,
      sibling_chapters: siblingItems,
      project_overview: effectiveOutline.project_overview || state.projectOverview,
      analysis_report: activeReport,
      response_matrix: effectiveOutline.response_matrix || activeReport.response_matrix,
      bid_mode: effectiveOutline.bid_mode || selectedBidMode,
      generated_summaries: entries
        .filter(item => item.item.id !== entry.item.id && item.item.content?.trim())
        .slice(-12)
        .map(item => ({ chapter_id: item.item.id, summary: `${item.item.title}：${(item.item.content || '').slice(0, 260)}` })),
      enterprise_materials: (activeReport.required_materials || []).filter(item => item.status === 'provided'),
      missing_materials: activeReport.missing_company_materials || [],
    };
    const response = await contentApi.generateChapterContentStream(request, options?.signal);
    let content = '';
    await consumeSseStream(response, (payload) => {
      if (payload.status === 'error') throw new Error(payload.message || '正文生成失败');
      if (payload.status === 'streaming' && payload.full_content) {
        content = payload.full_content;
        options?.onContent?.(content);
        options?.onProgress?.(content);
      }
      if (payload.status === 'completed' && payload.content) {
        content = payload.content;
        options?.onContent?.(content);
        options?.onProgress?.(content);
      }
    }, {
      shouldPause: () => generationPausedRef.current,
      isStopped: () => generationStoppedRef.current,
    });
    if (!content.trim()) throw new Error('模型返回空内容');
    return content;
  };

  const saveGeneratedContent = (entry: ChapterEntry, content: string, scroll = true, outlineSource = effectiveOutline) => {
    if (!outlineSource) return outlineSource;
    const nextOutline = {
      ...outlineSource,
      outline: updateOutlineItem(outlineSource.outline, entry.item.id, { content }),
    };
    updateOutline(nextOutline);
    setActiveDocId(entry.item.id);
    if (scroll) {
      window.requestAnimationFrame(() => {
        document.getElementById(docSectionId(entry.item.id))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
    return nextOutline;
  };

  const runCurrentChapter = async () => {
    if (!selectedEntry) return;
    setBusy(`chapter:${selectedEntry.item.id}`);
    const controller = new AbortController();
    generationAbortRef.current = controller;
    generationPausedRef.current = false;
    generationStoppedRef.current = false;
    setGenerationControl('running');
    setStreamingChapterId(selectedEntry.item.id);
    const taskVersion = startProgress('正文生成', ['准备章节', '模型写入', '保存正文'], `正在生成 ${selectedEntry.item.id} ${selectedEntry.item.title}`, 12);
    syncGenerationProgress(`正在生成 ${selectedEntry.item.id} ${selectedEntry.item.title}`, 12, 1, '正文生成');
    try {
      const content = await generateChapter(selectedEntry, {
        signal: controller.signal,
        onContent: (partial) => saveGeneratedContent(selectedEntry, partial, false),
        onProgress: (partial) => {
          const percent = Math.min(84, 18 + Math.floor(partial.length / 120));
          advanceProgress(`正在写入 ${selectedEntry.item.id} ${selectedEntry.item.title}`, percent, 1, taskVersion);
          syncGenerationProgress(`正在写入 ${selectedEntry.item.id} ${selectedEntry.item.title}`, percent, 1, '正文生成');
        },
      });
      advanceProgress('正在保存本章正文', 88, 2, taskVersion);
      saveGeneratedContent(selectedEntry, content);
      syncGenerationProgress('本章正文生成完成', 100, 2, '正文生成');
      setGenerationProgress(prev => prev ? { ...prev, status: 'success', percent: 100, detail: '本章正文生成完成' } : prev);
      completeProgress('本章正文生成完成', taskVersion);
      setSuccess(`已生成 ${selectedEntry.item.id} ${selectedEntry.item.title}`);
    } catch (error: any) {
      if (error?.name === 'AbortError' || generationStoppedRef.current) {
        failProgress('已停止生成', undefined, taskVersion);
        setInfo('已停止生成，可继续生成当前或其他章节');
        return;
      }
      failProgress(error.message || '生成本章失败', undefined, taskVersion);
      setError(error.message || '生成本章失败');
    } finally {
      setBusy('');
      resetGenerationControls();
    }
  };

  const runBatch = async () => {
    if (!effectiveOutline || entries.length === 0) {
      setError('请先生成目录');
      return;
    }
    setBusy('batch');
    const controller = new AbortController();
    generationAbortRef.current = controller;
    generationPausedRef.current = false;
    generationStoppedRef.current = false;
    setGenerationControl('running');
    const taskVersion = startProgress('批量生成', ['排队章节', '逐章生成', '保存正文'], '正在准备批量生成正文', 5);
    syncGenerationProgress('正在准备批量生成正文', 5, 0, '批量生成');
    try {
      let nextOutline = effectiveOutline;
      batchOutlineRef.current = nextOutline;
      const pendingEntries = entries.filter(entry => !entry.item.content?.trim());
      for (let index = 0; index < pendingEntries.length; index += 1) {
        await waitIfGenerationPaused();
        const entry = pendingEntries[index];
        if (entry.item.content?.trim()) continue;
        setStreamingChapterId(entry.item.id);
        setActiveDocId(entry.item.id);
        updateSelectedChapter(entry.item.id);
        const basePercent = Math.min(92, 8 + Math.round((index / Math.max(pendingEntries.length, 1)) * 82));
        advanceProgress(`正在生成 ${entry.item.id} ${entry.item.title}`, basePercent, 1, taskVersion);
        syncGenerationProgress(`正在生成 ${entry.item.id} ${entry.item.title}`, basePercent, 1, '批量生成');
        const content = await generateChapter(entry, {
          signal: controller.signal,
          onContent: (partial) => {
            const currentOutline = batchOutlineRef.current;
            if (!currentOutline) return;
            const patchedOutline = { ...currentOutline, outline: updateOutlineItem(currentOutline.outline, entry.item.id, { content: partial }) };
            batchOutlineRef.current = patchedOutline;
            updateOutline(patchedOutline);
          },
          onProgress: (partial) => {
            const chapterProgress = Math.min(8, Math.floor(partial.length / 260));
            const percent = Math.min(96, basePercent + chapterProgress);
            advanceProgress(`正在写入 ${entry.item.id} ${entry.item.title}`, percent, 1, taskVersion);
            syncGenerationProgress(`正在写入 ${entry.item.id} ${entry.item.title}`, percent, 1, '批量生成');
          },
        });
        nextOutline = batchOutlineRef.current || nextOutline;
        nextOutline = { ...nextOutline, outline: updateOutlineItem(nextOutline.outline, entry.item.id, { content }) };
        batchOutlineRef.current = nextOutline;
        updateOutline(nextOutline);
      }
      syncGenerationProgress('批量正文生成完成', 100, 2, '批量生成');
      setGenerationProgress(prev => prev ? { ...prev, status: 'success', percent: 100, detail: '批量正文生成完成' } : prev);
      completeProgress('批量正文生成完成', taskVersion);
      setSuccess('批量正文生成完成');
    } catch (error: any) {
      if (error?.name === 'AbortError' || generationStoppedRef.current) {
        failProgress('已停止批量生成', undefined, taskVersion);
        setInfo('已停止批量生成，已保留已生成章节');
        return;
      }
      failProgress(error.message || '批量生成失败', undefined, taskVersion);
      setError(error.message || '批量生成失败');
    } finally {
      setBusy('');
      batchOutlineRef.current = null;
      resetGenerationControls();
    }
  };

  const runReview = async () => {
    if (!effectiveOutline || !activeReport) {
      setError('请先完成标准解析并生成目录');
      return;
    }
    if (completedLeaves === 0) {
      setError('请先生成正文内容后再审校');
      return;
    }
    setBusy('review');
    const taskVersion = startProgress('合规审校', ['整理正文', '模型审校', '写入报告'], '正在整理正文和解析结果', 10);
    try {
      const contentById = Object.fromEntries(entries.map(entry => [entry.item.id, entry.item.content || '']));
      const outline = buildExportOutline(effectiveOutline.outline, contentById);
      let raw = '';
      advanceProgress('正在调用模型检查覆盖率、阻塞项和风险项', 24, 1);
      const response = await documentApi.reviewComplianceStream({
        outline,
        project_overview: effectiveOutline.project_overview || state.projectOverview,
        analysis_report: activeReport,
        response_matrix: effectiveOutline.response_matrix || activeReport?.response_matrix,
        bid_mode: effectiveOutline.bid_mode || selectedBidMode,
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '合规审校失败');
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          advanceProgress('正在调用模型检查覆盖率、阻塞项和风险项', Math.min(92, 24 + Math.floor(raw.length / 220)), 1);
        }
      });
      advanceProgress('正在写入合规审校报告', 96, 2);
      const report = JSON.parse(extractJsonPayload(raw)) as ReviewReport;
      setReviewReport(report);
      completeProgress('合规审校完成', taskVersion);
      setSuccess(report.summary.ready_to_export ? '审校通过，可以导出 Word' : '审校完成，请处理阻塞项');
    } catch (error: any) {
      failProgress(error.message || '合规审校失败', undefined, taskVersion);
      setError(error.message || '合规审校失败');
    } finally {
      setBusy('');
    }
  };

  const exportWord = async () => {
    if (!effectiveOutline) {
      setError('请先生成目录和正文');
      return;
    }
    setBusy('export');
    const taskVersion = startProgress('导出 Word', ['整理章节', '生成文件'], '正在整理章节正文', 20);
    try {
      const contentById = Object.fromEntries(entries.map(entry => [entry.item.id, entry.item.content || '']));
      advanceProgress('正在生成 Word 文件', 70, 1);
      const response = await documentApi.exportWord({
        project_name: effectiveOutline.project_name || project?.name || '投标文件',
        project_overview: effectiveOutline.project_overview || state.projectOverview,
        outline: buildExportOutline(effectiveOutline.outline, contentById),
      });
      if (!response.ok) throw new Error('导出失败');
      const blob = await response.blob();
      const filename = `${effectiveOutline.project_name || project?.name || '投标文件'}.docx`;
      const picker = (window as any).showSaveFilePicker;
      if (picker) {
        try {
          const handle = await picker({
            suggestedName: filename,
            types: [{
              description: 'Word 文档',
              accept: {
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
              },
            }],
          });
          const writable = await handle.createWritable();
          await writable.write(blob);
          await writable.close();
        } catch (error: any) {
          if (error?.name === 'AbortError') {
            setProgress(null);
            setInfo('已取消保存 Word 文件');
            return;
          }
          throw error;
        }
      } else {
        saveAs(blob, filename);
      }
      completeProgress('Word 文件已生成', taskVersion);
      setSuccess(`Word 文件已保存：${filename}`);
    } catch (error: any) {
      failProgress(error.message || '导出失败', undefined, taskVersion);
      setError(error.message || '导出失败');
    } finally {
      setBusy('');
    }
  };

  const saveConfig = async () => {
    setBusy('config');
    setProgress(null);
    try {
      const nextConfig = toLiteLLMConfig(localConfig);
      const response = await configApi.saveConfig(nextConfig);
      if (!response.data.success) throw new Error(response.data.message || '保存失败');
      setLocalConfig(nextConfig);
      updateConfig(nextConfig);
      setSuccess('模型配置已保存');
    } catch (error: any) {
      setError(apiErrorMessage(error, '配置保存失败'));
    } finally {
      setBusy('');
    }
  };

  const verifyConfig = async () => {
    setBusy('verify');
    setProgress(null);
    try {
      const response = await configApi.verifyProvider(toLiteLLMConfig(localConfig));
      setVerifyResult(response.data);
      const modelCheck = response.data.checks.find(check => check.stage === 'models');
      if (modelCheck?.models?.length) setAvailableModels(modelCheck.models);
      setNotice({ type: response.data.success ? 'success' : 'error', text: response.data.message });
    } catch (error: any) {
      setError(apiErrorMessage(error, '验证端点失败'));
    } finally {
      setBusy('');
    }
  };

  const syncModels = async () => {
    setBusy('models');
    setProgress(null);
    try {
      const response = await configApi.getModels(toLiteLLMConfig(localConfig));
      const models = response.data.models || [];
      setAvailableModels(models);
      if (!response.data.success) throw new Error(response.data.message || '模型同步失败');
      if (models.length && !models.includes(localConfig.model_name)) {
        setNotice({ type: 'info', text: `已同步 ${models.length} 个模型，请选择其中一个后再验证` });
        return;
      }
      setSuccess(response.data.message || `已同步 ${models.length} 个模型`);
    } catch (error: any) {
      setError(apiErrorMessage(error, '模型同步失败'));
    } finally {
      setBusy('');
    }
  };

  const handleWorkflowAction = (item: typeof NAV_ITEMS[number]) => {
    goToPage(item.key);
  };

  const flowIndex = state.fileContent
    ? state.analysisReport
      ? state.outlineData
        ? completedLeaves > 0
          ? reviewReport
            ? 4
            : 3
          : 2
        : 1
      : 0
    : -1;

  const analysisStepStatus = (index: number) => {
    if (state.analysisReport && busy !== 'analysis') return '已完成';
    if (progress?.label === '标准解析' && progress.status === 'error') {
      if (index < progress.stepIndex) return '已完成';
      if (index === progress.stepIndex) return '失败';
      return '待执行';
    }
    if (busy === 'analysis') {
      const current = progress?.stepIndex ?? 0;
      if (index < current) return '已完成';
      if (index === current) return '进行中';
      return '待执行';
    }
    if (state.fileContent && index === 0) return '待执行';
    return '未开始';
  };

  const workflowStatus = (key: NavKey) => {
    if (busy === 'upload' && key === 'project') return `${progress?.percent ?? 0}%`;
    if (busy === 'analysis' && key === 'analysis') return `${progress?.percent ?? 0}%`;
    if (busy === 'outline' && key === 'outline') return `${progress?.percent ?? 0}%`;
    if (busy.startsWith('chapter') && key === 'content') return `${progress?.percent ?? 0}%`;
    if (busy === 'review' && key === 'review') return `${progress?.percent ?? 0}%`;
    if (key === 'project') return state.fileContent ? '已上传' : '选择';
    if (key === 'analysis') return state.analysisReport ? '已完成' : state.fileContent ? '可执行' : '待上传';
    if (key === 'outline') return effectiveOutline ? '已生成' : state.analysisReport ? '可执行' : '待解析';
    if (key === 'content') return completedLeaves > 0 ? `${completedLeaves}/${entries.length}` : effectiveOutline ? '可执行' : '待目录';
    if (key === 'review') return reviewReport ? '已审校' : completedLeaves > 0 ? '可执行' : '待正文';
    return '设置';
  };

  const busyText = progress?.detail
    || (busy === 'batch'
      ? '正在批量生成正文'
      : busy === 'analysis'
        ? '正在解析招标文件'
        : busy === 'outline'
          ? '正在生成目录映射'
          : busy === 'upload'
            ? '正在上传文件'
            : '正在处理请求');
  const busyPercent = progress?.percent ?? 12;
  const currentPage = activeNav === 'config' ? 'project' : activeNav;
  const pageMeta = PAGE_META[currentPage];

  return (
    <div className="ops-app">
      <aside className="ops-nav">
        <div className="ops-brand">
          <span className="ops-brand__mark">A</span>
          <span>华正ai标书系统</span>
        </div>
        <nav className="ops-nav__list">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeNav === item.key;
            return (
              <button
                key={item.key}
                type="button"
                className={`ops-nav__item ${active ? 'ops-nav__item--active' : ''}`}
                onClick={() => handleWorkflowAction(item)}
              >
                <Icon className="h-4 w-4" />
                <span className="ops-nav__copy">
                  <strong>{item.label}</strong>
                  <em>{item.description}</em>
                </span>
                <span className="ops-nav__state">{workflowStatus(item.key)}</span>
              </button>
            );
          })}
        </nav>
        <div className="history-panel">
          <div className="history-panel__head">
            <strong>历史记录</strong>
            <span>{historyRecords.length}</span>
          </div>
          <div className="history-list">
            {historyRecords.length ? historyRecords.slice(0, 4).map(record => (
              <button
                key={record.id}
                type="button"
                className="history-item"
                onClick={() => restoreHistoryRecord(record)}
              >
                <strong>{record.title}</strong>
                <span>{record.total ? `${record.completed}/${record.total} 章` : '待生成目录'} · {new Date(record.updatedAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
              </button>
            )) : (
              <div className="history-empty">生成后自动保存</div>
            )}
          </div>
        </div>
        <div className="ops-progress-card">
          <div className="ops-progress-card__ring">{coverage}%</div>
          <div>
            <strong>当前项目进度</strong>
            <span>{entries.length ? `已生成 ${completedLeaves}/${entries.length} 章节` : '等待模型生成目录'}</span>
            <span>字数统计 {entries.reduce((sum, entry) => sum + (entry.item.content?.length || 0), 0).toLocaleString()}</span>
          </div>
        </div>
        <div className="ops-user">
          <span className="ops-user__avatar">本</span>
          <div>
            <strong>本地工作台</strong>
            <span>{state.fileContent ? '招标文件已载入' : '待上传文件'}</span>
          </div>
          <ChevronDownIcon className="h-4 w-4 text-slate-400" />
        </div>
      </aside>

      <main className="ops-main">
        <header className="ops-topbar">
          <div className="ops-project-title">
            <span>项目：</span>
            <strong>{projectTitle}</strong>
            <ChevronDownIcon className="h-4 w-4" />
          </div>
          <div className="ops-topbar__center">
            <span>生成模式：</span>
            <div className="ops-segment">
              <button type="button" className={selectedBidMode === 'full_bid' ? 'active' : ''} onClick={() => handleModeChange('full_bid')}>完整标书</button>
              <button type="button" className={selectedBidMode === 'technical_only' ? 'active' : ''} onClick={() => handleModeChange('technical_only')}>技术标</button>
            </div>
            <span>当前模型：</span>
            <strong>{state.config.model_name || '未选择模型'}</strong>
          </div>
          <div className="ops-topbar__status">
            <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
            <span>已保存草稿</span>
            <button type="button" className="ops-icon-button" onClick={() => setConfigOpen(true)}>
              <Cog6ToothIcon className="h-4 w-4" />
              模型配置
            </button>
          </div>
        </header>

        <div className="ops-body ops-body--page">
          <section className="ops-page">
            <div className="ops-page__head">
              <div>
                <span className="ops-page__eyebrow">工作流页面</span>
                <h1>{pageMeta.title}</h1>
                <p>{pageMeta.description}</p>
              </div>
              <div className="ops-page__quicknav">
                {NAV_ITEMS.filter(item => item.key !== 'config').map(item => (
                  <button
                    key={item.key}
                    type="button"
                    className={currentPage === item.key ? 'active' : ''}
                    onClick={() => goToPage(item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {currentPage === 'project' && (
              <div className="ops-page-grid ops-page-grid--upload">
                <div className="ops-panel">
                  <h2>上传招标文件</h2>
                  <button type="button" className="upload-zone upload-zone--large" onClick={() => fileInputRef.current?.click()}>
                    <DocumentArrowUpIcon className="h-12 w-12" />
                    <strong>点击选择 PDF 或 DOCX 招标文件</strong>
                    <span>文件大小限制在 500MB 以下，上传后系统会读取全文并复用同一份解析结果。</span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) handleUpload(file);
                    }}
                  />
                  <div className="file-pill">
                    <DocumentTextIcon className="h-5 w-5 text-rose-600" />
                    <div>
                      <strong>{uploadedFileName || '等待上传招标文件'}</strong>
                      <span>{state.fileContent ? '已上传并读取文本' : '待上传'}</span>
                    </div>
                    {state.fileContent && <CheckCircleIcon className="h-5 w-5 text-emerald-600" />}
                  </div>
                  <div className="page-action-row">
                    <button type="button" className="solid-button" onClick={() => goToPage('analysis')} disabled={!state.fileContent}>
                      去解析
                    </button>
                    <button type="button" onClick={() => fileInputRef.current?.click()}>重新选择</button>
                  </div>
                </div>

                <div className="ops-panel project-info">
                  <div className="ops-panel__head">
                    <h2>项目基础信息</h2>
                    <span className="text-link">{activeReport ? '模型解析结果' : '待解析'}</span>
                  </div>
                  {!activeReport && (
                    <div className="empty-state empty-state--compact">
                      <strong>上传并解析招标文件后生成</strong>
                      <span>项目编号、采购人、预算、截止时间等字段不会使用前端示例占位。</span>
                    </div>
                  )}
                  {[
                    ['项目编号', project?.number],
                    ['采购人', project?.purchaser],
                    ['服务期限', project?.service_period],
                    ['报价要求', activeReport?.price_rules?.quote_method],
                    ['预算金额', project?.budget],
                    ['提交截止时间', project?.bid_deadline],
                  ].map(([label, value]) => (
                    <div key={label} className="info-row"><span>{label}</span><strong>{value || '待模型解析'}</strong></div>
                  ))}
                </div>

                <div className="ops-panel">
                  <div className="ops-panel__head">
                    <h2>材料缺失提示</h2>
                    <span>{activeReport ? `共 ${(activeReport.missing_company_materials || []).length} 项` : '待解析'}</span>
                  </div>
                  {activeReport ? (
                    (activeReport.missing_company_materials || []).length ? (
                      (activeReport.missing_company_materials || []).slice(0, 8).map(item => (
                        <div key={item.id} className="warning-row">
                          <ExclamationTriangleIcon className="h-4 w-4 text-amber-500" />
                          <span>{item.name}</span>
                          <strong>待补充</strong>
                        </div>
                      ))
                    ) : (
                      <div className="empty-state empty-state--compact">
                        <strong>未识别出缺失材料</strong>
                        <span>该结果来自当前解析报告，可在审校阶段继续核验。</span>
                      </div>
                    )
                  ) : (
                    <div className="empty-state empty-state--compact">
                      <strong>完成标准解析后显示</strong>
                      <span>材料清单由模型从资格、商务、签章等要求中抽取。</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {currentPage === 'analysis' && (
              <div className="ops-page-grid ops-page-grid--analysis">
                <div className="ops-panel">
                  <div className="ops-panel__head">
                    <h2>解析状态</h2>
                    <button type="button" className="text-link" onClick={runAnalysis} disabled={!state.fileContent || busy === 'analysis'}>
                      {busy === 'analysis' ? '解析中' : '开始解析'}
                    </button>
                  </div>
                  {(busy === 'analysis' || progress?.label === '标准解析') && <TaskProgress progress={progress} onRetry={runAnalysis} />}
                  {ANALYSIS_STEPS.map((item, index) => {
                    const status = analysisStepStatus(index);
                    return (
                      <div key={item} className={`check-row check-row--${status === '失败' ? 'error' : status === '进行中' ? 'active' : status === '已完成' ? 'done' : 'idle'}`}>
                        <CheckCircleIcon className={`h-4 w-4 ${status === '已完成' ? 'text-emerald-600' : status === '失败' ? 'text-rose-600' : status === '进行中' ? 'text-amber-500' : 'text-slate-300'}`} />
                        <span>{item}</span>
                        <strong>{status}</strong>
                      </div>
                    );
                  })}
                  {streamText && <pre className="stream-box stream-box--large">{streamText}</pre>}
                  <div className="page-action-row">
                    <button type="button" className="solid-button" onClick={runAnalysis} disabled={!state.fileContent || busy === 'analysis'}>
                      {state.analysisReport ? '重新解析' : '开始解析'}
                    </button>
                    <button type="button" onClick={() => goToPage('outline')} disabled={!state.analysisReport}>去生成目录</button>
                  </div>
                </div>

                <div className="ops-panel project-info">
                  <div className="ops-panel__head">
                    <h2>解析结果摘要</h2>
                    <span>{activeReport ? (project?.__fallback ? '已补全关键字段' : selectedBidMode) : '待解析'}</span>
                  </div>
                  {activeReport && project?.__fallback && (
                    <div className="field-hint">部分基础信息来自解析文本兜底提取，后续审校时仍建议核对原文。</div>
                  )}
                  {[
                    ['项目编号', project?.number],
                    ['采购人', project?.purchaser],
                    ['服务期限', project?.service_period],
                    ['预算金额', project?.budget],
                    ['提交截止时间', project?.bid_deadline],
                  ].map(([label, value]) => (
                    <div key={label} className="info-row"><span>{label}</span><strong>{isMeaningfulValue(value) ? value : '未识别到'}</strong></div>
                  ))}
                </div>

                <div className="ops-panel response-matrix-panel">
                  <div className="ops-panel__head">
                    <h2>响应矩阵</h2>
                    <span>{activeResponseMatrix ? `${responseMatrixItems.length} 项` : '待生成'}</span>
                  </div>
                  {activeResponseMatrix ? (
                    <>
                      <div className="review-metrics review-metrics--compact">
                        <Metric label="矩阵项" value={`${responseMatrixItems.length}`} tone="green" />
                        <Metric label="高风险" value={`${highRiskMatrixCount}`} tone="red" />
                        <Metric label="待覆盖" value={`${uncoveredMatrixCount}`} tone="amber" />
                      </div>
                      <div className="matrix-mini-list">
                        {responseMatrixItems.slice(0, 5).map(item => (
                          <div key={item.id} className="matrix-mini-row">
                            <strong>{item.id}</strong>
                            <span>{item.requirement_summary || item.source_item_id}</span>
                            <em>{item.priority === 'high' || item.blocking ? '高优先级' : item.source_type}</em>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="empty-state empty-state--compact">
                      <strong>等待标准解析</strong>
                      <span>解析完成后会生成“要求-章节-材料-风险”的响应矩阵，后续目录、正文和审校都会复用它。</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {currentPage === 'outline' && (
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
                      <button type="button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>智能建议</button>
                      <button type="button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>{effectiveOutline ? '重新生成' : '生成目录'}</button>
                    </div>
                  </div>
                  {busy === 'outline' && <TaskProgress progress={progress} />}
                  {activeResponseMatrix && (
                    <div className="matrix-strip">
                      <strong>响应矩阵</strong>
                      <span>{activeResponseMatrix.coverage_summary || `共 ${responseMatrixItems.length} 项，待覆盖 ${uncoveredMatrixCount} 项`}</span>
                    </div>
                  )}
                  {effectiveOutline ? (
                    <div className="outline-table outline-table--page">
                      <div className="outline-table__head">
                        <span>章节名称</span><span>评分项映射</span><span>风险</span><span>材料</span>
                      </div>
                      {effectiveOutline.outline.map(section => (
                        <OutlineRows key={section.id} item={section} selectedId={selectedEntry?.item.id} onSelect={updateSelectedChapter} />
                      ))}
                    </div>
                  ) : (
                    busy === 'outline' ? (
                      <OutlineDraftPreview rows={outlineDraftRows} raw={streamText} />
                    ) : (
                      <div className="empty-state">
                        <strong>目录还没有生成</strong>
                        <span>完成标准解析后，点击“生成目录”，后端会把招标结构、评分项、风险和材料要求映射到章节。</span>
                        <button type="button" className="solid-button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>调用模型生成目录</button>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}

            {currentPage === 'content' && (
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
                    <button type="button" onClick={exportWord} disabled={!effectiveOutline || busy === 'export'}>
                      <ArrowDownTrayIcon className="h-4 w-4" /> 导出 Word
                    </button>
                  </div>
                  {generationProgress && (
                    <div className="content-progress-strip">
                      <TaskProgress progress={generationProgress} />
                    </div>
                  )}
                  <article ref={docPreviewRef} className="word-document">
                    {effectiveOutline ? (
                      <>
                        <div className="word-document__cover">
                          <span>投标文件正文</span>
                          <h2>{effectiveOutline.project_name || project?.name || '待生成标书'}</h2>
                          <p>左侧目录可跳转到对应章节；未生成正文的章节会保留待编写占位。</p>
                        </div>
                        {effectiveOutline.outline.map(section => (
                          <DocumentPreviewNode
                            key={section.id}
                            item={section}
                            level={1}
                            activeId={activeDocId || selectedEntry?.item.id}
                            streamingId={streamingChapterId}
                            onSelect={scrollToDocumentNode}
                          />
                        ))}
                      </>
                    ) : (
                      <div className="empty-state empty-state--document">
                        <strong>等待目录生成</strong>
                        <span>正文区不会显示示例文本；生成目录并选择章节后，再调用模型写入正式内容。</span>
                      </div>
                    )}
                  </article>
                </div>
              </div>
            )}

            {currentPage === 'review' && (
              <div className="review-panel review-panel--page">
                <div className="ops-panel__head">
                  <h2>合规审校</h2>
                  <button type="button" className="text-link" onClick={runReview} disabled={!effectiveOutline || completedLeaves === 0 || busy === 'review'}>{busy === 'review' ? '审校中' : '执行审校'}</button>
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
              </div>
            )}
          </section>
        </div>
      </main>

      {configOpen && (
        <aside className="model-drawer">
          <div className="drawer-head">
            <h2>模型接入</h2>
            <button type="button" onClick={() => setConfigOpen(false)}><XMarkIcon className="h-5 w-5" /></button>
          </div>
          <div className="provider-lock">
            <strong>{LITELLM_PROVIDER.label}</strong>
            <span>{LITELLM_PROVIDER.note}</span>
          </div>
          <label>LiteLLM Base URL</label>
          <input
            value={localConfig.base_url || ''}
            onChange={(event) => {
              setVerifyResult(null);
              setLocalConfig(prev => toLiteLLMConfig({ ...prev, base_url: event.target.value }));
            }}
            placeholder={LITELLM_PROVIDER.baseUrl}
          />
          <label>模型名</label>
          <input
            value={localConfig.model_name}
            onChange={(event) => {
              setVerifyResult(null);
              setLocalConfig(prev => toLiteLLMConfig({ ...prev, model_name: event.target.value }));
            }}
            list="available-models"
            placeholder="从 /models 同步后选择，或手动输入模型 ID"
          />
          <datalist id="available-models">
            {availableModels.map(model => <option key={model} value={model} />)}
          </datalist>
          <div className="model-tools">
            <button type="button" onClick={syncModels} disabled={busy === 'models'}>{busy === 'models' ? '同步中' : '同步模型'}</button>
            {availableModels.length > 0 && <span>{availableModels.length} 个可用模型</span>}
          </div>
          {availableModels.length > 0 && (
            <div className="model-list">
              {availableModels.slice(0, 8).map(model => (
                <button
                  type="button"
                  key={model}
                  className={`model-chip ${localConfig.model_name === model ? 'model-chip--active' : ''}`}
                  onClick={() => {
                    setVerifyResult(null);
                    setLocalConfig(prev => toLiteLLMConfig({ ...prev, model_name: model }));
                  }}
                >
                  {model}
                </button>
              ))}
            </div>
          )}
          <label>API Key</label>
          <input
            type="password"
            value={localConfig.api_key}
            onChange={(event) => {
              setVerifyResult(null);
              setLocalConfig(prev => toLiteLLMConfig({ ...prev, api_key: event.target.value }));
            }}
            placeholder={LITELLM_PROVIDER.keyPlaceholder}
          />
          <div className="drawer-actions">
            <button type="button" className="solid-button" onClick={verifyConfig} disabled={busy === 'verify'}>验证端点</button>
            <button type="button" onClick={saveConfig} disabled={busy === 'config'}>保存配置</button>
          </div>
          <div className="verify-card">
            <h3>验证结果</h3>
            <VerifyLine ok={verifyResult?.checks.find(check => check.stage === 'chat')?.success} label="对话接口可用" />
            <VerifyLine ok={verifyResult?.checks.find(check => check.stage === 'models')?.success} label="模型列表可用" />
            <p>{verifyResult?.resolved_base_url || `${localConfig.base_url || LITELLM_PROVIDER.baseUrl}/chat/completions`}</p>
          </div>
        </aside>
      )}

      {notice && <div className={`toast toast--${notice.type}`}>{notice.text}</div>}
      {busy && (
        <div className="busy-bar">
          <div className="busy-bar__head">
            <SparklesIcon className="h-4 w-4" />
            <span>{busyText}</span>
            <strong>{busyPercent}%</strong>
          </div>
          <div className="busy-bar__track">
            <span style={{ width: `${busyPercent}%` }} />
          </div>
        </div>
      )}
    </div>
  );
};

interface OutlineRowsProps {
  item: OutlineItem;
  selectedId?: string;
  level?: number;
  onSelect: (id: string) => void;
}

const OutlineRows = ({ item, selectedId, level = 0, onSelect }: OutlineRowsProps) => {
  const hasChildren = Boolean(item.children?.length);
  const isLeaf = !hasChildren;
  const active = item.id === selectedId;
  return (
    <>
      <button
        type="button"
        className={`outline-row ${active ? 'outline-row--active' : ''}`}
        style={{ paddingLeft: 18 + level * 24 }}
        onClick={() => isLeaf ? onSelect(item.id) : item.children?.[0] && onSelect(item.children[0].id)}
      >
        <span className="outline-name">
          {hasChildren ? <ChevronRightIcon className="h-3.5 w-3.5" /> : <span className="tree-branch" />}
          <strong>{item.id}　{item.title}</strong>
        </span>
        <span className="chip chip--green">评分项 {item.scoring_item_ids?.length || '-'}</span>
        <span className={`chip ${riskLevel(item) === '高风险' ? 'chip--red' : riskLevel(item) === '中风险' ? 'chip--amber' : 'chip--green'}`}>{riskLevel(item)}</span>
        <span className="chip">{item.material_ids?.length || 0}/{Math.max(item.material_ids?.length || 0, 1)}</span>
      </button>
      {item.children?.map(child => (
        <OutlineRows key={child.id} item={child} selectedId={selectedId} level={level + 1} onSelect={onSelect} />
      ))}
    </>
  );
};

const OutlineDraftPreview = ({ rows, raw }: { rows: DraftOutlineRow[]; raw: string }) => (
  <div className="outline-draft">
    <div className="outline-draft__head">
      <SparklesIcon className="h-4 w-4" />
      <strong>正在生成目录和映射关系</strong>
      <span>{rows.length ? `已出现 ${rows.length} 个章节` : '等待模型返回章节'}</span>
    </div>
    <div className="outline-draft__list">
      {rows.length ? rows.map((row, index) => (
        <div key={`${row.id}-${index}`} className="outline-draft-row" style={{ paddingLeft: 14 + row.level * 22 }}>
          <span>{row.id}</span>
          <strong>{row.title}</strong>
          <em>{row.status}</em>
        </div>
      )) : (
        Array.from({ length: 5 }).map((_, index) => <div key={index} className="outline-draft-skeleton" />)
      )}
    </div>
    {raw && <pre className="stream-box">模型正在返回结构化目录，已接收 {raw.length.toLocaleString()} 字符...</pre>}
  </div>
);

interface DocumentTocRowsProps {
  item: OutlineItem;
  activeId?: string;
  level?: number;
  onSelect: (item: OutlineItem) => void;
}

const DocumentTocRows = ({ item, activeId, level = 0, onSelect }: DocumentTocRowsProps) => {
  const hasChildren = Boolean(item.children?.length);
  const active = item.id === activeId;
  const generated = Boolean(item.content?.trim());

  return (
    <div className="word-toc-node">
      <button
        type="button"
        className={`word-toc-row ${active ? 'word-toc-row--active' : ''}`}
        style={{ paddingLeft: 10 + level * 18 }}
        onClick={() => onSelect(item)}
      >
        {hasChildren ? <ChevronRightIcon className="h-3.5 w-3.5" /> : <span className="tree-branch" />}
        <span>{item.id} {item.title}</span>
        {generated && <CheckCircleIcon className="h-3.5 w-3.5 text-emerald-600" />}
      </button>
      {item.children?.map(child => (
        <DocumentTocRows
          key={child.id}
          item={child}
          activeId={activeId}
          level={level + 1}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
};

interface DocumentPreviewNodeProps {
  item: OutlineItem;
  level: number;
  activeId?: string;
  streamingId?: string;
  onSelect: (item: OutlineItem) => void;
}

const DocumentPreviewNode = ({ item, level, activeId, streamingId, onSelect }: DocumentPreviewNodeProps) => {
  const hasChildren = Boolean(item.children?.length);
  const active = item.id === activeId;
  const streaming = item.id === streamingId;
  const headingLevel = Math.min(level, 4);
  const headingClass = `word-heading word-heading--${headingLevel}`;

  return (
    <section
      id={docSectionId(item.id)}
      className={`word-section ${active ? 'word-section--active' : ''}`}
    >
      <button type="button" className={headingClass} onClick={() => onSelect(item)}>
        <span>{item.id} {item.title}</span>
        {!hasChildren && <SparklesIcon className="h-4 w-4" />}
      </button>
      {item.description && <p className="word-section__desc">{item.description}</p>}
      {!hasChildren && (
        item.content?.trim() ? (
          <div className={`word-section__content ${streaming ? 'word-section__content--streaming' : ''}`}>
            <ReactMarkdown>{item.content}</ReactMarkdown>
          </div>
        ) : (
          <div className={`word-section__placeholder ${streaming ? 'word-section__placeholder--streaming' : ''}`}>请输入或智能编写...</div>
        )
      )}
      {item.children?.map(child => (
        <DocumentPreviewNode
          key={child.id}
          item={child}
          level={level + 1}
          activeId={activeId}
          streamingId={streamingId}
          onSelect={onSelect}
        />
      ))}
    </section>
  );
};

const Metric = ({ label, value, tone }: { label: string; value: string; tone: 'green' | 'red' | 'amber' | 'blue' }) => (
  <div className="metric-card">
    <span>{label}</span>
    <strong className={`metric-card__value metric-card__value--${tone}`}>{value}</strong>
    {tone === 'green' && <div className="metric-bar"><span style={{ width: value.endsWith('%') ? value : '0%' }} /></div>}
  </div>
);

const VerifyLine = ({ ok, label }: { ok?: boolean; label: string }) => (
  <div className="verify-line">
    {ok === undefined ? (
      <span className="verify-line__pending" />
    ) : ok ? (
      <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
    ) : (
      <XMarkIcon className="h-4 w-4 text-rose-600" />
    )}
    <span>{label}</span>
  </div>
);

const TaskProgress = ({ progress, onRetry }: { progress: ProgressState | null; onRetry?: () => void }) => {
  if (!progress) return null;
  return (
    <div className={`task-progress task-progress--${progress.status}`}>
      <div className="task-progress__head">
        <strong>{progress.detail}</strong>
        <span>{progress.percent}%</span>
      </div>
      <div className="task-progress__bar">
        <span style={{ width: `${progress.percent}%` }} />
      </div>
      {progress.status === 'error' && (
        <div className="task-progress__error">
          <strong>{progress.error || '模型调用失败，请检查端点、模型名或 API Key 后重试。'}</strong>
          {onRetry && <button type="button" onClick={onRetry}>重试解析</button>}
        </div>
      )}
      {progress.steps.length > 0 && (
        <div className="task-progress__steps">
          {progress.steps.map((step, index) => (
            <span key={step} className={index < progress.stepIndex ? 'done' : index === progress.stepIndex ? 'active' : ''}>
              {step}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default App;
