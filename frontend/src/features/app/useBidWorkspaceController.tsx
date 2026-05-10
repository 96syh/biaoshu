import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  PhotoIcon,
  PlayIcon,
  ShieldCheckIcon,
  SparklesIcon,
  StopIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useAppState } from '../../hooks/useAppState';
import { DEFAULT_PROVIDER_ID, LITELLM_PROVIDER } from '../../constants/providers';
import {
  ChapterContentRequest,
  HistoryRequirementCheck,
  ModelRuntimeResponse,
  ProviderVerifyResponse,
  apiBaseUrl,
  configApi,
  contentApi,
  documentApi,
  outlineApi,
} from '../../services/api';
import {
  AnalysisReport,
  BidMode,
  ConsistencyRevisionReport,
  ConfigData,
  OutlineData,
  OutlineItem,
  ReviewReport,
  SourceRenderedPreviewPage,
} from '../../types';
import { consumeSseStream } from '../../utils/sse';
import { DraftHistoryRecord, draftStorage } from '../../utils/draftStorage';
import {
  GeneratedVisualAsset,
  PlannedBlock,
  PlannedBlockGroup,
  VisualAssetResult,
  attachGeneratedAssetToPlan,
  blockAssetKey,
  blockTypeLabel,
  isVisualBlockType,
  normalizeDocumentBlocksPlan,
  visualAssetResultFromBlock,
  visualAssetsFromPlanGroups,
  visualBlocksByChapterFromGroups,
} from '../../utils/visualAssets';
import { ReferenceSlotPreview } from '../assets/ReferenceSlotPreview';
import { ReferenceSlotShowcase } from '../assets/ReferenceSlotShowcase';
import { DocumentPreviewNode, docSectionId } from '../content/DocumentPreviewNode';
import { DocumentTocRows } from '../content/DocumentTocRows';
import { VerifyLine } from '../config/VerifyLine';
import { OutlineDraftPreview } from '../outline/OutlineDraftPreview';
import { OutlineRows } from '../outline/OutlineRows';
import { Metric } from '../review/Metric';
import { TaskProgress } from '../shared/TaskProgress';
import { ProgressState, useProgressState } from './hooks/useProgressState';

type Notice = { type: 'success' | 'error' | 'info'; text: string };
type NavKey = 'project' | 'analysis' | 'outline' | 'assets' | 'content' | 'review' | 'config';
type GenerationControlState = 'idle' | 'running' | 'paused' | 'stopped';
type TaskStatus = 'idle' | 'blocked' | 'running' | 'success' | 'error' | 'paused' | 'stopped';
type TaskState = {
  id: string;
  label: string;
  status: TaskStatus;
  detail?: string;
  error?: string;
  dependsOn?: string[];
  startedAt?: number;
  finishedAt?: number;
};
type DraftOutlineRow = { id: string; title: string; level: number; status: string };
type OutlineEditorForm = { id: string; title: string; description: string };
type ProjectSummary = Partial<AnalysisReport['project']> & { __fallback?: boolean };
type TenderParseTabKey = 'basic' | 'qualification' | 'technical' | 'business' | 'other' | 'risk' | 'document' | 'process' | 'supplement';
type TenderParseSection = {
  id: string;
  title: string;
  content: string[];
  evidence: string[];
  count: number;
};
type TenderParseTab = {
  key: TenderParseTabKey;
  label: string;
  sections: TenderParseSection[];
};
type SourcePreviewBlockType = 'blank' | 'paragraph' | 'heading1' | 'heading2' | 'heading3' | 'image';
type SourcePreviewBlock = {
  sourceIndex: number;
  text: string;
  type: SourcePreviewBlockType;
};
type SourcePreviewPage = {
  pageNumber: number;
  blocks: SourcePreviewBlock[];
};
type SourceLocateStatus = 'idle' | 'locating' | 'found' | 'not-found';
type SourceLocateResult = {
  status: SourceLocateStatus;
  label: string;
  snippet: string;
};
type RenderedSourceBlockTarget = {
  pageNumber: number;
  blockId: string;
};

const TASK_DAG: Record<string, string[]> = {
  upload_text: [],
  source_preview: ['upload_text'],
  history_match: ['upload_text'],
  analysis: ['upload_text'],
  requirement_check: ['analysis'],
  outline: ['analysis'],
  document_blocks: ['outline'],
  batch: ['outline'],
  review: ['batch'],
  consistency: ['batch'],
  export: ['review', 'consistency'],
};

const TASK_LABELS: Record<string, string> = {
  upload: '文件上传',
  upload_text: '文件上传',
  source_preview: '原文预览',
  reference: '样例解析',
  'reference-match': '历史案例匹配',
  history_match: '历史案例匹配',
  requirement_check: '要求匹配',
  analysis: '标准解析',
  outline: '目录生成',
  blocks: '图表素材规划',
  document_blocks: '图表素材规划',
  batch: '批量生成',
  review: '合规审校',
  consistency: '一致性修订',
  export: 'Word 导出',
  config: '保存配置',
  verify: '验证端点',
  models: '同步模型',
};

const normalizeTaskId = (id: string) => {
  if (id === 'upload') return 'upload_text';
  if (id === 'reference-match') return 'history_match';
  if (id === 'blocks') return 'document_blocks';
  return id;
};

const taskDependencies = (id: string) => {
  const normalizedId = normalizeTaskId(id);
  if (normalizedId.startsWith('chapter:')) return ['outline'];
  if (normalizedId.startsWith('asset:')) return ['document_blocks'];
  return TASK_DAG[normalizedId] || [];
};

const taskLabel = (id: string) => TASK_LABELS[id] || (id.startsWith('chapter:') ? '正文生成' : id.startsWith('asset:') ? '图表生成' : id);

const contentConcurrencyLimit = () => {
  const raw = Number((process.env.REACT_APP_YIBIAO_CONTENT_CONCURRENCY || '2').trim());
  if (!Number.isFinite(raw)) return 2;
  return Math.max(1, Math.min(4, Math.floor(raw)));
};
type TenderScoringRow = {
  id: string;
  item: string;
  score: string;
  requirement: string;
  subitems: string[];
  evidence: string[];
};
const BID_MODE_OPTIONS: Array<{ value: BidMode; label: string }> = [
  { value: 'technical_only', label: '技术标' },
  { value: 'full_bid', label: '完整标' },
];

const BID_MODE_LABELS: Record<BidMode, string> = BID_MODE_OPTIONS.reduce(
  (labels, option) => ({ ...labels, [option.value]: option.label }),
  {} as Record<BidMode, string>,
);

const BID_MODE_VALUES = new Set<BidMode>(BID_MODE_OPTIONS.map(option => option.value));

const BID_MODE_ALIASES: Record<string, BidMode> = {
  technical: 'technical_only',
  technical_bid: 'technical_only',
  tech: 'technical_only',
  tech_bid: 'technical_only',
  technical_service: 'technical_only',
  technical_service_plan: 'technical_only',
  service: 'technical_only',
  service_plan: 'technical_only',
  construction: 'technical_only',
  construction_plan: 'technical_only',
  construction_organization: 'technical_only',
  goods_supply: 'technical_only',
  goods_supply_plan: 'technical_only',
  supply_plan: 'technical_only',
  business: 'full_bid',
  business_technical: 'full_bid',
  business_volume: 'full_bid',
  commercial: 'full_bid',
  commercial_volume: 'full_bid',
  qualification: 'full_bid',
  qualification_volume: 'full_bid',
  qualification_bid: 'full_bid',
  price: 'full_bid',
  price_volume: 'full_bid',
  quote: 'full_bid',
  quotation: 'full_bid',
  full: 'full_bid',
  complete: 'full_bid',
  complete_bid: 'full_bid',
  unknown: 'technical_only',
};

const DEFAULT_WORD_STYLE_PROFILE: Record<string, string> = {
  page_size: 'A4',
  orientation: 'portrait',
  margin_top: '2.2cm',
  margin_bottom: '2.2cm',
  margin_left: '2.7cm',
  margin_right: '2.2cm',
  body_font_family: 'SimSun, STSong, "Songti SC", serif',
  body_font_size: '10.5pt',
  body_line_height: '1.5',
  body_first_line_indent: '2em',
  heading_font_family: 'SimHei, "Heiti SC", "Microsoft YaHei", sans-serif',
  heading_1_size: '16pt',
  heading_2_size: '14pt',
  heading_3_size: '12pt',
  table_font_size: '9pt',
};
const EMPTY_REFERENCE_PROFILE: Record<string, unknown> = {};

const profileRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};

const listCount = (value: unknown): number => (Array.isArray(value) ? value.length : 0);

const isUsableReferenceProfile = (value: unknown): value is Record<string, unknown> => {
  const profile = profileRecord(value);
  const profileName = String(profile.profile_name || '');
  if (!Object.keys(profile).length || /兜底|失败|fallback/i.test(profileName)) return false;
  return listCount(profile.outline_template) > 0 && listCount(profile.chapter_blueprints) > 0;
};

const normalizeCssValue = (value: unknown, fallback: string) => {
  const text = String(value || '').trim();
  return text || fallback;
};

const buildWordPreviewStyle = (referenceProfile?: Record<string, unknown>): React.CSSProperties => {
  const wordStyle = {
    ...DEFAULT_WORD_STYLE_PROFILE,
    ...profileRecord(referenceProfile?.word_style_profile),
  };
  return {
    '--word-margin-top': normalizeCssValue(wordStyle.margin_top, DEFAULT_WORD_STYLE_PROFILE.margin_top),
    '--word-margin-bottom': normalizeCssValue(wordStyle.margin_bottom, DEFAULT_WORD_STYLE_PROFILE.margin_bottom),
    '--word-margin-left': normalizeCssValue(wordStyle.margin_left, DEFAULT_WORD_STYLE_PROFILE.margin_left),
    '--word-margin-right': normalizeCssValue(wordStyle.margin_right, DEFAULT_WORD_STYLE_PROFILE.margin_right),
    '--word-body-font': normalizeCssValue(wordStyle.body_font_family, DEFAULT_WORD_STYLE_PROFILE.body_font_family),
    '--word-body-size': normalizeCssValue(wordStyle.body_font_size, DEFAULT_WORD_STYLE_PROFILE.body_font_size),
    '--word-line-height': normalizeCssValue(wordStyle.body_line_height, DEFAULT_WORD_STYLE_PROFILE.body_line_height),
    '--word-first-indent': normalizeCssValue(wordStyle.body_first_line_indent, DEFAULT_WORD_STYLE_PROFILE.body_first_line_indent),
    '--word-heading-font': normalizeCssValue(wordStyle.heading_font_family, DEFAULT_WORD_STYLE_PROFILE.heading_font_family),
    '--word-h1-size': normalizeCssValue(wordStyle.heading_1_size, DEFAULT_WORD_STYLE_PROFILE.heading_1_size),
    '--word-h2-size': normalizeCssValue(wordStyle.heading_2_size, DEFAULT_WORD_STYLE_PROFILE.heading_2_size),
    '--word-h3-size': normalizeCssValue(wordStyle.heading_3_size, DEFAULT_WORD_STYLE_PROFILE.heading_3_size),
    '--word-table-size': normalizeCssValue(wordStyle.table_font_size, DEFAULT_WORD_STYLE_PROFILE.table_font_size),
  } as React.CSSProperties;
};

const normalizeBidMode = (mode?: unknown): BidMode => {
  const value = String(mode || '').trim();
  if (BID_MODE_VALUES.has(value as BidMode)) return value as BidMode;
  return BID_MODE_ALIASES[value] || 'technical_only';
};
const bidModeLabel = (mode?: unknown) => BID_MODE_LABELS[normalizeBidMode(mode)];

interface ChapterEntry {
  item: OutlineItem;
  parents: OutlineItem[];
  top: OutlineItem;
}

const NAV_ITEMS: Array<{ key: NavKey; label: string; description: string; icon: React.ElementType; target?: string }> = [
  { key: 'project', label: '上传文件', description: '选择招标文件', icon: FolderIcon, target: 'panel-analysis' },
  { key: 'analysis', label: '开始解析', description: '抽取条款与评分', icon: DocumentTextIcon, target: 'panel-analysis' },
  { key: 'outline', label: '生成目录', description: '映射评分风险', icon: Bars3BottomLeftIcon, target: 'panel-outline' },
  { key: 'assets', label: '图表素材', description: '生成图表素材', icon: PhotoIcon, target: 'panel-assets' },
  { key: 'content', label: '生成正文', description: '写入选中章节', icon: PencilSquareIcon, target: 'panel-content' },
  { key: 'review', label: '执行审校', description: '检查合规风险', icon: ShieldCheckIcon, target: 'panel-review' },
  { key: 'config', label: '模型配置', description: 'LiteLLM 接入', icon: Cog6ToothIcon },
];

const FLOW_STEPS = ['上传', '标准解析', '目录映射', '正文生成', '合规审校', '导出'];
const ANALYSIS_STEPS = ['文件解析', '条款识别', '评分项提取', '合规要求提取', '结果校验'];
const BLOCKING_REPORT_WARNING_PATTERN = /兜底|未完整返回|模型输出未完整|解析失败|超时/;
const CLIENT_GENERATION_FALLBACKS_ENABLED = process.env.REACT_APP_ENABLE_GENERATION_FALLBACKS === '1';
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

const parseJsonPayload = <T,>(raw: string, label: string): T => {
  const payload = extractJsonPayload(raw);
  if (!payload) {
    throw new Error(`${label}没有返回可解析的 JSON。系统已停止后续生成，不会使用兜底目录；请重新生成或检查模型输出。`);
  }
  try {
    return JSON.parse(payload) as T;
  } catch (error: any) {
    const message = error?.message === 'Unexpected end of JSON input'
      ? `${label}返回的 JSON 不完整。系统已停止后续生成，不会使用兜底目录；请重新解析。`
      : `${label}返回的 JSON 格式异常：${error?.message || '未知错误'}`;
    throw new Error(message);
  }
};

const getBlockingAnalysisReportWarning = (report?: AnalysisReport | null) => {
  if (!report) return '';
  const warningTexts = (report.generation_warnings || [])
    .filter(item => item.severity === 'blocking')
    .map(item => `${item.severity || ''} ${item.warning || ''}`);
  const riskTexts = (report.rejection_risks || [])
    .filter(item => item.source === '系统解析状态' && /停止后续|阻塞/.test(item.risk || ''))
    .map(item => item.risk || '');
  const matched = [...warningTexts, ...riskTexts].find(text => BLOCKING_REPORT_WARNING_PATTERN.test(text));
  return matched || '';
};

const hasParsedDocumentText = (fileContent?: string) => Boolean((fileContent || '').trim());

const isGeneratedMediaTitle = (value?: string | null) =>
  /-{2,}\s*media\/image\d+\.(png|jpg|jpeg|gif|webp)\s*-{2,}/i.test((value || '').trim());

const cleanDisplayTitle = (value?: string | null) => {
  const title = (value || '').trim();
  if (!title || isGeneratedMediaTitle(title)) return '';
  return title;
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

const findOutlineItem = (items: OutlineItem[], id: string): OutlineItem | null => {
  for (const item of items) {
    if (item.id === id) return item;
    if (item.children?.length) {
      const found = findOutlineItem(item.children, id);
      if (found) return found;
    }
  }
  return null;
};

const deleteOutlineItem = (items: OutlineItem[], id: string): OutlineItem[] =>
  items
    .filter(item => item.id !== id)
    .map(item => item.children?.length ? { ...item, children: deleteOutlineItem(item.children, id) } : item);

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

const isMeaningfulValue = (value?: string | null) => {
  const normalized = (value || '').trim();
  if (!normalized) return false;
  if (isGeneratedMediaTitle(normalized)) return false;
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
  uploadedFileName?: string,
): ProjectSummary | undefined => {
  if (!report?.project) return undefined;
  const sourceText = [overview, requirements, fileContent.slice(0, 30000)].filter(Boolean).join('\n');
  const project = report.project;
  const fallback: ProjectSummary = {
    ...project,
    name: isMeaningfulValue(project.name)
      ? project.name
      : cleanDisplayTitle(findFieldInText(sourceText, ['项目名称', '采购项目名称', '招标项目名称', '项目']))
        || cleanDisplayTitle(uploadedFileName)
        || cleanDisplayTitle(project.number)
        || '未命名标书',
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

const summarizeAnalysisReport = (report: AnalysisReport) => {
  const project = report.project || {};
  return [
    `项目名称：${project.name || '未识别'}`,
    `采购人/招标人：${project.purchaser || '未识别'}`,
    `项目类型：${project.project_type || '未识别'}`,
    `服务/供货/施工范围：${project.service_scope || '未识别'}`,
    `服务期限/工期/交付期：${project.service_period || '未识别'}`,
    `质量要求：${project.quality_requirements || '未识别'}`,
    `推荐生成模式：${bidModeLabel(report.bid_mode_recommendation)}`,
  ].join('\n');
};

const summarizeRequirementsFromReport = (report: AnalysisReport) => {
  const lines: string[] = [];
  const pushItems = (title: string, items: Array<{ id: string; name?: string; requirement?: string; standard?: string; score?: string; risk?: string; clause?: string }>) => {
    if (!items?.length) return;
    lines.push(`【${title}】`);
    items.slice(0, 12).forEach(item => {
      lines.push(`${item.id} ${item.name || item.requirement || item.clause || item.risk || '未命名'}${item.score ? `（${item.score}）` : ''}：${item.standard || item.requirement || item.clause || item.risk || ''}`);
    });
  };
  pushItems('技术评分项', report.technical_scoring_items || []);
  pushItems('商务评分项', report.business_scoring_items || []);
  pushItems('资格/形式/响应要求', [
    ...(report.qualification_requirements || []),
    ...(report.formal_response_requirements || []),
    ...(report.mandatory_clauses || []),
  ]);
  pushItems('废标和高风险项', report.rejection_risks || []);
  return lines.join('\n') || '未识别到明确评分或响应要求，请核对招标文件。';
};

const toText = (value?: unknown) => String(value ?? '').trim();

const asList = <T,>(value?: T[] | null): T[] => (Array.isArray(value) ? value : []);

const toRecordItems = <T,>(value?: T[] | null): Array<Record<string, unknown>> =>
  asList(value).map(item => item as unknown as Record<string, unknown>);

const isInternalBidDocumentId = (value?: unknown) => /^BD(?:-[A-Z0-9]+)+$/i.test(toText(value));

const isScoringParseTab = (key?: TenderParseTabKey) =>
  key === 'technical' || key === 'business' || key === 'other';

const uniqueTexts = (values: string[], limit = 5) => {
  const seen = new Set<string>();
  return values
    .map(value => value.trim())
    .filter(value => {
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    })
    .slice(0, limit);
};

const pickEvidence = (report: AnalysisReport, ...candidates: unknown[]) => {
  const raw = candidates.flatMap(candidate => (Array.isArray(candidate) ? candidate : [candidate])).map(toText).filter(isMeaningfulValue);
  const matchedRefs = asList(report.source_refs).filter(ref => {
    const refTokens = [ref.id, ref.location, ...(ref.related_ids || [])].filter(Boolean);
    return raw.some(value => refTokens.some(token => value.includes(token) || token.includes(value)));
  });
  return uniqueTexts([
    ...matchedRefs.map(ref => `${ref.location}：${ref.excerpt}`),
    ...matchedRefs.map(ref => ref.excerpt),
    ...raw,
  ]);
};

const appendParseSection = (
  sections: TenderParseSection[],
  id: string,
  title: string,
  content: unknown[],
  evidence: unknown[],
  count = 1,
) => {
  const contentLines = uniqueTexts(content.map(toText).filter(isMeaningfulValue), 12);
  const evidenceLines = uniqueTexts(evidence.map(toText).filter(isMeaningfulValue), 6);
  if (!contentLines.length && !evidenceLines.length) return;
  sections.push({ id, title, content: contentLines, evidence: evidenceLines, count });
};

const normalizeSourceText = (value: string) =>
  value.replace(/\s+/g, '').replace(/[：:，,。；;（）()【】《》<>]/g, '').replace(/\[|\]/g, '').toLowerCase();

const sourceTokenParts = (line: string) => {
  const text = String(line || '').trim();
  if (!text) return [];
  const parts = text.split(/[：:\n]/).map(part => part.trim()).filter(Boolean);
  if (parts.length <= 1) return [text];
  return uniqueTexts([...parts.slice(1), text, parts[0]], 6);
};

const sourceSearchTokens = (section?: TenderParseSection) => {
  if (!section) return [];
  return uniqueTexts(
    [...section.evidence, ...section.content]
      .flatMap(sourceTokenParts)
      .filter(value => isMeaningfulValue(value) && value.length >= 4),
    12,
  );
};

const sourceSearchTokensFromText = (text?: string) =>
  uniqueTexts(
    String(text || '')
      .split(/[。；;]/)
      .flatMap(sourceTokenParts)
      .filter(value => isMeaningfulValue(value) && value.length >= 4),
    8,
  );

const sourceSearchTokensForLocate = (text?: string, section?: TenderParseSection) =>
  uniqueTexts(
    [
      ...(section?.evidence || []),
      ...(text ? [text] : []),
      section?.title || '',
      ...(section?.content || []),
    ]
      .flatMap(value => String(value || '').split(/[。；;\n]/))
      .flatMap(sourceTokenParts)
      .filter(value => isMeaningfulValue(value) && value.length >= 4),
    18,
  );

const sourceTokenFragments = (token: string) => {
  const normalized = normalizeSourceText(token);
  if (normalized.length < 8) return [];
  const lengths = [30, 22, 16, 10, 7].filter(length => length < normalized.length);
  const fragments: string[] = [];
  lengths.forEach(length => {
    const step = Math.max(4, Math.floor(length / 2));
    for (let index = 0; index + length <= normalized.length; index += step) {
      fragments.push(normalized.slice(index, index + length));
    }
  });
  return uniqueTexts(fragments.filter(fragment => fragment.length >= 7), 24);
};

const sourceTextOverlapScore = (nodeText: string, token: string) => {
  const chars = Array.from(new Set(token.split(''))).filter(char => /[\u4e00-\u9fa5a-z0-9]/i.test(char));
  if (chars.length < 8) return 0;
  const hits = chars.filter(char => nodeText.includes(char)).length;
  const ratio = hits / chars.length;
  if (ratio < 0.62) return 0;
  return ratio * Math.min(22, chars.length);
};

const scoreSourceNodeMatch = (nodeText: string, tokens: string[]) => {
  const normalizedText = normalizeSourceText(nodeText);
  if (normalizedText.length < 4) return 0;
  return tokens.reduce((score, token, index) => {
    const normalizedToken = normalizeSourceText(token);
    if (normalizedToken.length < 4) return score;
    if (normalizedText.includes(normalizedToken)) {
      return score + Math.min(90, normalizedToken.length) + Math.max(0, 18 - index);
    }
    if (normalizedToken.includes(normalizedText) && normalizedText.length >= 14 && normalizedToken.length <= normalizedText.length * 2.2) {
      return score + Math.min(40, normalizedText.length) * 0.55;
    }
    const fragmentScore = sourceTokenFragments(normalizedToken).reduce(
      (sum, fragment) => normalizedText.includes(fragment) ? sum + Math.min(20, fragment.length) : sum,
      0,
    );
    return score + fragmentScore + sourceTextOverlapScore(normalizedText, normalizedToken);
  }, 0);
};

const findSourceLineIndex = (lines: string[], section?: TenderParseSection) => {
  const tokens = sourceSearchTokens(section).map(normalizeSourceText).filter(token => token.length >= 4);
  if (!tokens.length) return -1;
  return lines.findIndex(line => {
    const normalizedLine = normalizeSourceText(line);
    if (normalizedLine.length < 4) return false;
    return tokens.some(token => normalizedLine.includes(token) || token.includes(normalizedLine));
  });
};

const findSourceLineIndexByText = (lines: string[], text?: string) => {
  const tokens = sourceSearchTokensFromText(text).map(normalizeSourceText).filter(token => token.length >= 4);
  if (!tokens.length) return -1;
  return lines.findIndex(line => {
    const normalizedLine = normalizeSourceText(line);
    if (normalizedLine.length < 4) return false;
    return tokens.some(token => normalizedLine.includes(token) || token.includes(normalizedLine));
  });
};

const backendAssetUrl = (url?: string) => {
  const value = String(url || '').trim();
  if (!value) return '';
  if (/^https?:\/\//i.test(value) || value.startsWith('data:')) return value;
  const base = apiBaseUrl.replace(/\/$/, '');
  return `${base}${value.startsWith('/') ? value : `/${value}`}`;
};

const renderedBlockStyle = (page: SourceRenderedPreviewPage, bbox: [number, number, number, number]): React.CSSProperties => {
  const width = Number(page.width) || 1;
  const height = Number(page.height) || 1;
  const [x0, y0, x1, y1] = bbox;
  return {
    left: `${Math.max(0, Math.min(100, (x0 / width) * 100))}%`,
    top: `${Math.max(0, Math.min(100, (y0 / height) * 100))}%`,
    width: `${Math.max(1, Math.min(100, ((x1 - x0) / width) * 100))}%`,
    height: `${Math.max(1, Math.min(100, ((y1 - y0) / height) * 100))}%`,
  };
};

const markdownImagePattern = /!\[[^\]]*]\(([^)]+)\)/g;
const markdownTableDividerPattern = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;

const stripPreviewInlineMarkup = (value: string) =>
  value
    .replace(/<a\s+[^>]*id=["'][^"']+["'][^>]*>\s*<\/a>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?u>/gi, '')
    .replace(/<\/?(strong|b|em|i)>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .trim();

const buildSourcePreviewBlock = (line: string, sourceIndex: number): SourcePreviewBlock => {
  const raw = line.trimEnd();
  const trimmed = raw.trim();
  if (!trimmed || markdownTableDividerPattern.test(trimmed)) {
    return { sourceIndex, text: '', type: 'blank' };
  }

  if (markdownImagePattern.test(trimmed) && trimmed.replace(markdownImagePattern, '').trim() === '') {
    markdownImagePattern.lastIndex = 0;
    return { sourceIndex, text: '文档图片 / 图示', type: 'image' };
  }
  markdownImagePattern.lastIndex = 0;

  const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
  if (headingMatch) {
    const level = headingMatch[1].length;
    const text = stripPreviewInlineMarkup(headingMatch[2].replace(markdownImagePattern, ''));
    return {
      sourceIndex,
      text,
      type: level === 1 ? 'heading1' : level === 2 ? 'heading2' : 'heading3',
    };
  }

  const imageCleaned = trimmed.replace(markdownImagePattern, '【图片】');
  const tableCleaned = imageCleaned.startsWith('|') && imageCleaned.endsWith('|')
    ? imageCleaned.split('|').map(part => part.trim()).filter(Boolean).join('    ')
    : imageCleaned;
  const text = stripPreviewInlineMarkup(tableCleaned);
  if (!text) return { sourceIndex, text: '', type: 'blank' };
  return { sourceIndex, text, type: 'paragraph' };
};

const estimateSourcePreviewBlockUnits = (block: SourcePreviewBlock) => {
  if (block.type === 'blank') return 0.45;
  if (block.type === 'image') return 4.5;
  if (block.type === 'heading1') return 3.2;
  if (block.type === 'heading2') return 2.4;
  if (block.type === 'heading3') return 2;
  return Math.max(1.2, Math.ceil(block.text.length / 34) * 1.18);
};

const paginateSourcePreviewBlocks = (blocks: SourcePreviewBlock[]) => {
  const pages: SourcePreviewPage[] = [];
  let currentBlocks: SourcePreviewBlock[] = [];
  let currentUnits = 0;
  const pageUnitLimit = 30;

  blocks.forEach(block => {
    const units = estimateSourcePreviewBlockUnits(block);
    if (currentBlocks.length && currentUnits + units > pageUnitLimit) {
      pages.push({ pageNumber: pages.length + 1, blocks: currentBlocks });
      currentBlocks = [];
      currentUnits = 0;
    }
    currentBlocks.push(block);
    currentUnits += units;
  });

  if (currentBlocks.length) {
    pages.push({ pageNumber: pages.length + 1, blocks: currentBlocks });
  }
  return pages;
};

const requirementLine = (item: Record<string, unknown>) => {
  const rawHead = toText(item.name || item.title || item.review_type || item.target || item.clause || item.risk);
  const rawId = toText(item.id);
  const head = rawHead || (isInternalBidDocumentId(rawId) ? '' : rawId);
  const body = toText(item.requirement || item.standard || item.criterion || item.logic || item.clause || item.risk || item.fixed_text);
  const score = toText(item.score);
  const strategy = toText(item.writing_focus || item.response_strategy || item.mitigation || item.fill_rules);
  return [
    head ? `${head}${score ? `（${score}）` : ''}` : '',
    body ? `要求：${body}` : '',
    strategy ? `响应建议：${strategy}` : '',
  ].filter(Boolean).join('\n');
};

const bidDocumentCompositionLine = (item: Record<string, unknown>, index: number) => {
  const title = [
    item.title,
    item.name,
    item.form_name,
    item.chapter_title,
    item.requirement_summary,
  ].map(toText).find(value => value && !isInternalBidDocumentId(value));
  if (!title) return '';
  const fixed = item.fixed_format ? '固定格式' : '';
  const signature = item.signature_required || item.seal_required ? '需签章' : '';
  const attachment = item.attachment_required ? '需附件' : '';
  const tags = [fixed, signature, attachment].filter(Boolean).join('、');
  return `${index + 1}. ${title}${tags ? `（${tags}）` : ''}`;
};

const splitScoringSubitems = (value: string) => {
  const normalized = value
    .replace(/\r/g, '\n')
    .replace(/；/g, '；\n')
    .replace(/。\s*(?=\d+[.、]|[（(]?\d+[）)]|[一二三四五六七八九十]+[、.])/g, '。\n');
  return uniqueTexts(
    normalized
      .split(/\n+/)
      .map(item => item.replace(/^[\s\-•●]+/, '').trim())
      .filter(item => item.length > 0),
    16,
  );
};

const buildScoringRows = (
  report: AnalysisReport,
  key: TenderParseTabKey,
): TenderScoringRow[] => {
  const rawItems = key === 'technical'
    ? toRecordItems(report.technical_scoring_items)
    : key === 'business'
      ? toRecordItems(report.business_scoring_items)
      : [
        ...toRecordItems(report.price_scoring_items),
        ...(report.price_rules ? [{
          id: 'PRICE-RULE',
          name: '投标报价',
          score: toText((report.price_rules as any).score) || '按公式计算',
          logic: [
            report.price_rules.quote_method,
            report.price_rules.maximum_price_rule,
            report.price_rules.abnormally_low_price_rule,
            report.price_rules.arithmetic_correction_rule,
            report.price_rules.missing_item_rule,
          ].filter(isMeaningfulValue).join('\n'),
          source: report.price_rules.source_ref,
        } as Record<string, unknown>] : []),
      ];

  return rawItems.slice(0, 40).map((item, index) => {
    const requirement = toText(item.standard || item.logic || item.requirement || item.criterion || item.risk);
    const evidence = pickEvidence(report, item.id, item.source, item.source_ref);
    return {
      id: toText(item.id) || `${key}-${index + 1}`,
      item: toText(item.name || item.review_type || item.target || item.id) || `评分项${index + 1}`,
      score: toText(item.score || item.weight || item.points || item.value) || '未明确',
      requirement: requirement || '未识别到明确得分要求',
      subitems: splitScoringSubitems(requirement),
      evidence,
    };
  });
};

const buildItemSections = (
  report: AnalysisReport,
  prefix: string,
  items: Array<Record<string, unknown>>,
  fallbackTitle: string,
) => items.slice(0, 10).reduce<TenderParseSection[]>((sections, item, index) => {
  const id = toText(item.id) || `${prefix}-${index + 1}`;
  const title = toText(item.name || item.review_type || item.target || item.risk || item.clause) || `${fallbackTitle}${index + 1}`;
  appendParseSection(
    sections,
    `${prefix}-${id}`,
    title,
    [
      requirementLine(item),
      asList(item.required_materials as string[]).length ? `材料：${asList(item.required_materials as string[]).join('、')}` : '',
      asList(item.evidence_requirements as string[]).length ? `证据：${asList(item.evidence_requirements as string[]).join('、')}` : '',
      asList(item.easy_loss_points as string[]).length ? `易失分点：${asList(item.easy_loss_points as string[]).join('、')}` : '',
    ],
    pickEvidence(report, item.id, item.source, item.source_ref),
  );
  return sections;
}, []);

const MISSING_PARSE_TEXT = '暂未扫描到相关内容描述';

const lineOrMissing = (label: string, value: unknown) => `${label}：${toText(value) || MISSING_PARSE_TEXT}`;

const collectRequirementLines = (
  items: Array<Record<string, unknown>>,
  keywords: string[],
  limit = 8,
) => {
  const matched = items.filter(item => {
    const haystack = [
      item.name,
      item.review_type,
      item.target,
      item.clause,
      item.requirement,
      item.standard,
      item.criterion,
      item.logic,
      item.risk,
      item.source,
    ].map(toText).join(' ');
    return keywords.some(keyword => haystack.includes(keyword));
  });
  return matched.slice(0, limit).map(item => requirementLine(item));
};

const fixedRequirementBlock = (
  title: string,
  items: Array<Record<string, unknown>>,
  keywords: string[],
) => {
  const lines = collectRequirementLines(items, keywords, 4);
  return `${title}\n${lines.length ? lines.join('\n') : MISSING_PARSE_TEXT}`;
};

const linesOrMissing = (lines: string[]) => (lines.length ? lines : [MISSING_PARSE_TEXT]);

const buildTenderParseTabs = (report: AnalysisReport | null): TenderParseTab[] => {
  if (!report) return [];
  const project = report.project || {};
  const bidDoc = (report as any).bid_document_requirements || {};
  const selectedTarget = bidDoc.selected_generation_target || {};
  const baseOutline = asList<Record<string, unknown>>(selectedTarget.base_outline_items);
  const schemeOutline = asList<Record<string, unknown>>(bidDoc.scheme_or_technical_outline_requirements);
  const composition = asList<Record<string, unknown>>(bidDoc.composition);
  const qualificationItems = [
    ...toRecordItems(report.qualification_review_items),
    ...toRecordItems(report.qualification_requirements),
  ];
  const formalItems = toRecordItems(report.formal_review_items);
  const responsivenessItems = [
    ...toRecordItems(report.responsiveness_review_items),
    ...toRecordItems(report.formal_response_requirements),
    ...toRecordItems(report.mandatory_clauses),
  ];
  const riskItems = [
    ...toRecordItems(report.rejection_risks),
    ...toRecordItems(report.mandatory_clauses),
    ...responsivenessItems,
  ];
  const allRequirementItems = [
    ...qualificationItems,
    ...formalItems,
    ...responsivenessItems,
    ...riskItems,
    ...toRecordItems(report.required_materials),
    ...toRecordItems(report.fixed_format_forms),
    ...toRecordItems(report.signature_requirements),
    ...toRecordItems(report.evidence_chain_requirements),
  ];

  const basicSections: TenderParseSection[] = [];
  appendParseSection(basicSections, 'basic-owner', '招标人/代理信息', [
    lineOrMissing('招标人', project.purchaser),
    lineOrMissing('招标代理机构', project.agency),
    lineOrMissing('联系方式', (project as any).contact || (project as any).contact_phone),
    lineOrMissing('联系地址', (project as any).address),
  ], pickEvidence(report, project.name, project.number, project.purchaser));
  appendParseSection(basicSections, 'basic-project', '项目信息', [
    lineOrMissing('项目名称', project.name),
    lineOrMissing('项目编号', project.number),
    lineOrMissing('标包/标段', project.package_name || project.package_or_lot),
    lineOrMissing('采购方式', project.procurement_method),
    lineOrMissing('预算/最高限价', project.budget || project.maximum_price),
  ], pickEvidence(report, project.service_scope, project.quality_requirements));
  appendParseSection(basicSections, 'basic-time', '关键时间/内容', [
    lineOrMissing('投标截止时间', project.bid_deadline),
    lineOrMissing('开标时间', project.opening_time),
    lineOrMissing('服务期限/工期', project.service_period),
    lineOrMissing('采购/服务内容', project.service_scope),
  ], pickEvidence(report, project.service_period, project.bid_deadline, project.opening_time));
  appendParseSection(basicSections, 'basic-bond', '保证金相关', [
    lineOrMissing('投标保证金', project.bid_bond),
    lineOrMissing('履约保证金', project.performance_bond),
  ], pickEvidence(report, project.bid_bond, project.performance_bond));
  appendParseSection(basicSections, 'basic-other', '其他信息', [
    lineOrMissing('服务地点', project.service_location),
    lineOrMissing('质量要求', project.quality_requirements),
    lineOrMissing('投标有效期', project.bid_validity),
    lineOrMissing('递交方式', project.submission_method || project.submission_requirements),
    lineOrMissing('电子平台', project.electronic_platform),
  ], pickEvidence(report, project.service_period, project.bid_deadline, project.opening_time));

  const technicalSections = [
    ...buildItemSections(report, 'tech-score', toRecordItems(report.technical_scoring_items), '技术评分'),
    ...buildItemSections(report, 'tech-outline', [...baseOutline, ...schemeOutline], '服务纲要'),
  ];
  if (!technicalSections.length) {
    appendParseSection(technicalSections, 'tech-empty', '服务纲要', ['未识别到明确服务纲要或技术评分条目。'], []);
  }

  const documentSections: TenderParseSection[] = [];
  const compositionLines = composition.map((item, index) => bidDocumentCompositionLine(item, index)).filter(Boolean);
  appendParseSection(
    documentSections,
    'document-composition',
    '投标文件组成',
    linesOrMissing(compositionLines),
    pickEvidence(report, ...composition.map(item => item.source || item.source_ref)),
    compositionLines.length || composition.length,
  );
  appendParseSection(documentSections, 'document-price', '投标报价要求', [
    lineOrMissing('报价方式', report.price_rules?.quote_method),
    lineOrMissing('最高限价/限价规则', report.price_rules?.maximum_price_rule),
    lineOrMissing('算术修正规则', report.price_rules?.arithmetic_correction_rule),
    lineOrMissing('报价格式', report.price_rules?.form_requirements),
  ], pickEvidence(report, report.price_rules?.source_ref));
  appendParseSection(documentSections, 'document-submit', '投标文件递交方式', [
    lineOrMissing('递交方式', project.submission_method || project.submission_requirements),
    lineOrMissing('电子平台', project.electronic_platform),
    lineOrMissing('截止时间', project.bid_deadline),
    lineOrMissing('签章要求', project.signature_requirements),
  ], pickEvidence(report, project.submission_method, project.submission_requirements, project.electronic_platform));
  appendParseSection(documentSections, 'document-scheme', '方案要求', [
    toText(selectedTarget.target_title) ? `生成对象：${selectedTarget.target_title}` : MISSING_PARSE_TEXT,
    toText(selectedTarget.base_outline_strategy) ? `目录策略：${selectedTarget.base_outline_strategy}` : '',
    schemeOutline.map(item => requirementLine(item)).join('\n'),
    baseOutline.map(item => requirementLine(item)).join('\n'),
    asList(report.fixed_format_forms).map(item => `${item.name}：${item.fill_rules || item.fixed_text || item.source}`).join('\n'),
  ], pickEvidence(report, selectedTarget.source, ...asList(report.fixed_format_forms).map(item => item.source)));

  const processSections: TenderParseSection[] = [];
  appendParseSection(processSections, 'process-opening', '开标', [
    lineOrMissing('开标时间', project.opening_time || project.bid_deadline),
    lineOrMissing('开标方式/平台', project.electronic_platform || project.submission_method),
    ...collectRequirementLines(allRequirementItems, ['开标', '解密', '签到', '开标大厅'], 6),
  ], pickEvidence(report, project.electronic_platform, project.opening_time));
  appendParseSection(processSections, 'process-review', '评标', linesOrMissing(collectRequirementLines([...formalItems, ...responsivenessItems], ['评标', '评审', '澄清', '修正'], 8)), pickEvidence(report, ...formalItems.map(item => item.source), ...responsivenessItems.map(item => item.source)));
  appendParseSection(processSections, 'process-award', '定标', linesOrMissing(collectRequirementLines(allRequirementItems, ['定标', '中标', '推荐中标', '候选人'], 8)), pickEvidence(report, ...allRequirementItems.map(item => item.source)));
  appendParseSection(processSections, 'process-followup', '后续要求', linesOrMissing(collectRequirementLines(allRequirementItems, ['合同', '履约', '服务费', '通知书', '公示', '质疑'], 8)), pickEvidence(report, ...allRequirementItems.map(item => item.source)));

  const supplementSections: TenderParseSection[] = [];
  appendParseSection(supplementSections, 'supplement-tech-spec', '技术规格', [
    lineOrMissing('服务/技术范围', project.service_scope),
    lineOrMissing('质量要求', project.quality_requirements),
    ...collectRequirementLines([...toRecordItems(report.technical_scoring_items), ...schemeOutline], ['技术', '规格', '服务', '设计', '方案'], 6),
  ], pickEvidence(report, project.service_scope, project.quality_requirements));
  appendParseSection(supplementSections, 'supplement-contract-time', '合同时间', [lineOrMissing('服务期限/合同时间', project.service_period)], pickEvidence(report, project.service_period));
  appendParseSection(supplementSections, 'supplement-background', '项目背景', [
    lineOrMissing('项目名称', project.name),
    lineOrMissing('项目类型', project.project_type),
    lineOrMissing('资金来源', project.funding_source),
  ], pickEvidence(report, project.name, project.funding_source));
  appendParseSection(supplementSections, 'supplement-format', '方案与格式要求', [
    toText(selectedTarget.target_title) ? `生成对象：${selectedTarget.target_title}` : MISSING_PARSE_TEXT,
    ...schemeOutline.slice(0, 8).map(item => requirementLine(item)),
  ], pickEvidence(report, selectedTarget.source));
  appendParseSection(supplementSections, 'supplement-special', '其他特殊要求', [
    ...collectRequirementLines(allRequirementItems, ['特殊', '必须', '不得', '承诺', '偏离', '暗标'], 8),
    ...asList(report.generation_warnings).map(item => `${item.severity}：${item.warning}`),
  ], pickEvidence(report, ...allRequirementItems.map(item => item.source)));
  appendParseSection(supplementSections, 'supplement-sample', '样品要求', linesOrMissing(collectRequirementLines(allRequirementItems, ['样品', '样本', '演示'], 4)), pickEvidence(report, ...allRequirementItems.map(item => item.source)));
  appendParseSection(supplementSections, 'supplement-payment', '付款方式', linesOrMissing(collectRequirementLines(allRequirementItems, ['付款', '支付', '价款', '结算'], 4)), pickEvidence(report, ...allRequirementItems.map(item => item.source)));
  appendParseSection(supplementSections, 'supplement-share', '中标份额分配规则', linesOrMissing(collectRequirementLines(allRequirementItems, ['份额', '分配', '中标份额'], 4)), pickEvidence(report, ...allRequirementItems.map(item => item.source)));
  appendParseSection(supplementSections, 'supplement-count', '中标数量规则', linesOrMissing(collectRequirementLines(allRequirementItems, ['中标数量', '入围', '候选人数量', '标包数量'], 4)), pickEvidence(report, ...allRequirementItems.map(item => item.source)));

  const tabs: TenderParseTab[] = [
    { key: 'basic', label: '基础信息', sections: basicSections },
    { key: 'qualification', label: '资格审查', sections: [
      {
        id: 'qualification-review',
        title: '资格评审',
        content: [
          fixedRequirementBlock('资质条件', qualificationItems, ['资质', '资格条件', '资格']),
          fixedRequirementBlock('业绩要求', qualificationItems, ['业绩']),
          fixedRequirementBlock('财务要求', qualificationItems, ['财务', '审计']),
          fixedRequirementBlock('信誉要求', qualificationItems, ['信誉', '信用', '失信', '黑名单', '行贿']),
          fixedRequirementBlock('人员资格要求', qualificationItems, ['人员', '项目负责人', '资格证', '注册']),
          fixedRequirementBlock('联合体投标要求', qualificationItems, ['联合体', '分包']),
          fixedRequirementBlock('安全生产许可证要求', qualificationItems, ['安全生产许可证']),
          fixedRequirementBlock('投标资格评审否决项', riskItems, ['资格', '否决', '废标', '不得参加', '取消投标资格']),
        ],
        evidence: pickEvidence(report, ...qualificationItems.map(item => item.source)),
        count: qualificationItems.length,
      },
      {
        id: 'qualification-formal',
        title: '形式评审标准',
        content: formalItems.length ? formalItems.slice(0, 12).map(item => requirementLine(item)) : [MISSING_PARSE_TEXT],
        evidence: pickEvidence(report, ...formalItems.map(item => item.source)),
        count: formalItems.length,
      },
      {
        id: 'qualification-responsive',
        title: '响应性评审标准',
        content: responsivenessItems.length ? responsivenessItems.slice(0, 12).map(item => requirementLine(item)) : [MISSING_PARSE_TEXT],
        evidence: pickEvidence(report, ...responsivenessItems.map(item => item.source)),
        count: responsivenessItems.length,
      },
    ] },
    { key: 'technical', label: '技术评分', sections: technicalSections },
    { key: 'business', label: '商务评分', sections: buildItemSections(report, 'biz-score', toRecordItems(report.business_scoring_items), '商务评分') },
    { key: 'other', label: '其他评分', sections: [
      ...buildItemSections(report, 'price-score', toRecordItems(report.price_scoring_items), '价格评分'),
      ...buildItemSections(report, 'price-rule', report.price_rules ? [report.price_rules as unknown as Record<string, unknown>] : [], '报价规则'),
    ] },
    { key: 'risk', label: '无效标与废标项', sections: [
      ...buildItemSections(report, 'risk-reject', toRecordItems(report.rejection_risks), '废标风险'),
      ...buildItemSections(report, 'risk-clause', toRecordItems(report.mandatory_clauses), '实质性条款'),
    ] },
    { key: 'document', label: '投标文件要求', sections: documentSections },
    { key: 'process', label: '开评定标流程', sections: processSections },
    { key: 'supplement', label: '补充信息归纳', sections: supplementSections },
  ];

  return tabs.map(tab => ({
    ...tab,
    sections: tab.sections.length ? tab.sections : [{ id: `${tab.key}-empty`, title: '未识别到明确条目', content: ['当前解析报告未返回该类结构化内容，建议核对源文件或重新解析。'], evidence: [], count: 0 }],
  }));
};

const makeFallbackOutlineNode = (
  id: string,
  title: string,
  description: string,
  patch: Partial<OutlineItem> = {},
): OutlineItem => ({
  id,
  title,
  description,
  volume_id: patch.volume_id || 'V-TECH',
  chapter_type: patch.chapter_type || 'technical',
  source_type: patch.source_type || 'client_fallback',
  fixed_format_sensitive: Boolean(patch.fixed_format_sensitive),
  price_sensitive: Boolean(patch.price_sensitive),
  anonymity_sensitive: Boolean(patch.anonymity_sensitive),
  expected_word_count: patch.expected_word_count || 1200,
  expected_depth: patch.expected_depth || 'medium',
  expected_blocks: patch.expected_blocks || ['paragraph'],
  scoring_item_ids: patch.scoring_item_ids || [],
  requirement_ids: patch.requirement_ids || [],
  risk_ids: patch.risk_ids || [],
  material_ids: patch.material_ids || [],
  response_matrix_ids: patch.response_matrix_ids || [],
  children: patch.children,
});

const buildClientFallbackOutline = (
  report: AnalysisReport,
  bidMode: BidMode,
  referenceBidStyleProfile: Record<string, unknown>,
  documentBlocksPlan: Record<string, unknown>,
): OutlineData => {
  const bidDoc = (report as any).bid_document_requirements || {};
  const composition = Array.isArray(bidDoc.composition) ? bidDoc.composition : [];
  const selectedTarget = bidDoc.selected_generation_target || {};
  const targetTitle = cleanDisplayTitle(selectedTarget.target_title);
  const wrapperTitles = new Set(['服务方案', '技术方案', '设计方案', '实施方案', '施工组织设计', '供货方案', '售后服务方案']);
  const seenTargetTitles = new Set<string>();
  const rawTargetItems = [
    ...(Array.isArray(selectedTarget.base_outline_items) ? selectedTarget.base_outline_items : []),
    ...(Array.isArray(bidDoc.scheme_or_technical_outline_requirements) ? bidDoc.scheme_or_technical_outline_requirements : []),
  ];
  const hasMultiTargetItems = new Set(rawTargetItems.map((item: any) => cleanDisplayTitle(item?.title)).filter(Boolean)).size > 1;
  const targetItems = rawTargetItems.filter((item: any) => {
    const title = cleanDisplayTitle(item?.title);
    if (!title || seenTargetTitles.has(title)) return false;
    if (!hasMultiTargetItems && (title === targetTitle || wrapperTitles.has(title))) return false;
    seenTargetTitles.add(title);
    return true;
  });
  const technicalItems = (report.technical_scoring_items || []).filter(item => cleanDisplayTitle(item.name));
  const matrix = report.response_matrix;

  let outline: OutlineItem[] = [];
  if (bidMode === 'full_bid' && composition.length) {
    outline = composition.slice(0, 16).map((item: any, index: number) => {
      const isTech = /技术|服务|设计|方案|施工组织|供货/.test(item.title || '');
      const children = isTech && targetItems.length
        ? targetItems.slice(0, 12).map((target: any, childIndex: number) => makeFallbackOutlineNode(
          `${index + 1}.${childIndex + 1}`,
          cleanDisplayTitle(target.title) || `方案要求${childIndex + 1}`,
          '按招标文件方案纲要逐项响应，补齐评分项、材料和风险映射。',
          { volume_id: item.volume_id || 'V-TECH', scoring_item_ids: technicalItems.slice(0, 8).map(score => score.id) },
        ))
        : undefined;
      return makeFallbackOutlineNode(
        String(index + 1),
        cleanDisplayTitle(item.title) || `投标文件组成${index + 1}`,
        '按招标文件投标文件组成、固定格式、签章、附件和页码要求编制。',
        {
          volume_id: item.volume_id || (isTech ? 'V-TECH' : 'V-BIZ'),
          chapter_type: item.chapter_type || (isTech ? 'technical' : 'business'),
          fixed_format_sensitive: Boolean(item.fixed_format),
          price_sensitive: Boolean(item.price_related),
          children,
        },
      );
    });
  } else if (targetItems.length) {
    outline = targetItems.slice(0, 20).map((item: any, index: number) => makeFallbackOutlineNode(
      String(index + 1),
      cleanDisplayTitle(item.title) || `方案要求${index + 1}`,
      '按选中的技术/服务/设计方案生成对象逐项响应，避免混入商务、报价和资格卷正文。',
      {
        scoring_item_ids: technicalItems.slice(0, 8).map(score => score.id),
        response_matrix_ids: matrix?.items?.slice(0, 8).map(item => item.id) || [],
      },
    ));
  } else {
    outline = (technicalItems.length ? technicalItems : [{ id: 'T-01', name: '项目理解与实施方案' } as any])
      .slice(0, 12)
      .map((item, index) => makeFallbackOutlineNode(
        String(index + 1),
        cleanDisplayTitle(item.name) || `技术评分响应${index + 1}`,
        '按技术/服务评分项生成目录主线，后续正文需逐项覆盖评分标准。',
        { scoring_item_ids: item.id ? [item.id] : [] },
      ));
  }

  return {
    outline,
    project_name: cleanDisplayTitle(report.project?.name) || cleanDisplayTitle(report.project?.number) || '投标文件',
    response_matrix: matrix,
    coverage_summary: matrix?.coverage_summary || '模型返回不完整 JSON，已使用解析报告生成兜底目录。',
    reference_bid_style_profile: referenceBidStyleProfile,
    document_blocks_plan: documentBlocksPlan,
    bid_mode: bidMode,
  };
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

const flattenOutlineDraftRows = (items: OutlineItem[] = [], limit = 80): DraftOutlineRow[] => {
  const rows: DraftOutlineRow[] = [];
  const walk = (nodes: OutlineItem[], level = 0) => {
    for (const item of nodes) {
      if (rows.length >= limit) return;
      rows.push({ id: item.id, title: item.title, level, status: item.children?.length ? '已生成下级' : '叶子章节' });
      if (item.children?.length) walk(item.children, level + 1);
    }
  };
  walk(items);
  return rows;
};

const THIRD_LEVEL_TITLE_CATALOG: Array<[RegExp, string[]]> = [
  [/范围|内容|服务/, ['服务事项拆解', '工作边界与接口', '响应要求与交付口径']],
  [/背景|需求|理解/, ['招标需求识别', '项目特点分析', '响应重点说明']],
  [/质量|控制|保证/, ['质量目标分解', '过程控制措施', '验收与持续改进']],
  [/进度|期限|计划/, ['进度节点安排', '工期保障措施', '延期风险应对']],
  [/人员|团队|岗位/, ['组织架构与职责', '人员投入计划', '协同与考核机制']],
  [/设备|工具|软件|资源/, ['资源配置清单', '使用管理要求', '保障与维护措施']],
  [/流程|方法|实施|方案/, ['实施步骤安排', '关键流程控制', '异常处理机制']],
  [/风险|难点|应急/, ['风险识别', '预防控制措施', '应急处置方案']],
  [/沟通|协调|响应/, ['沟通机制', '响应时限要求', '服务承诺落实']],
];
const SECOND_LEVEL_TITLE_CATALOG: Array<[RegExp, string[]]> = [
  [/范围|内容|服务/, ['服务内容分解', '服务边界与接口', '服务成果与交付']],
  [/目标/, ['目标理解', '目标分解', '目标达成措施']],
  [/机构|岗位|职责/, ['组织架构设置', '岗位职责分工', '协同管理机制']],
  [/人员|团队/, ['人员配置计划', '专业能力保障', '人员管理与考核']],
  [/沟通|协调/, ['沟通机制设计', '信息反馈流程', '协调保障措施']],
  [/质量|承诺|措施/, ['质量目标承诺', '过程质量控制', '验收与改进措施']],
  [/方案|实施|方法/, ['总体实施思路', '关键实施流程', '保障与应急措施']],
];
const FALLBACK_SECOND_LEVEL_TITLES = ['需求理解与响应目标', '实施方法与保障措施', '成果交付与验收管理'];
const FALLBACK_THIRD_LEVEL_TITLES = ['响应要点拆解', '实施措施安排', '支撑材料与交付要求'];
const AUTO_SECOND_LEVEL_TITLES = new Set([
  ...SECOND_LEVEL_TITLE_CATALOG.flatMap(([, titles]) => titles),
  ...FALLBACK_SECOND_LEVEL_TITLES,
]);
const AUTO_THIRD_LEVEL_TITLES = new Set([
  ...THIRD_LEVEL_TITLE_CATALOG.flatMap(([, titles]) => titles),
  ...FALLBACK_THIRD_LEVEL_TITLES,
  '需求识别与边界确认',
  '重点难点分析',
  '响应思路与实施口径',
  '服务标准与响应要求',
  '交付成果与验收口径',
]);

type ThirdLevelPlan = { title: string; description: string };

type AutoOutlineBasis = {
  id: string;
  title: string;
  description: string;
  response_strategy?: string;
  source_refs?: string[];
  scoring_item_ids?: string[];
  requirement_ids?: string[];
  risk_ids?: string[];
  material_ids?: string[];
  response_matrix_ids?: string[];
};

const compactOutlineTitle = (value: unknown, fallback = '响应条目') => {
  const text = String(value || '').replace(/^.+?[:：]\s*/, '').replace(/\s+/g, ' ').trim();
  return (text || fallback).slice(0, 34);
};

const outlineMatchTokens = (value: string) =>
  String(value || '')
    .split(/[、，,；;。.\s（）()]+/)
    .map(part => part.trim())
    .filter(part => part.length >= 2 && !['服务', '方案', '内容', '措施', '要求', '响应', '章节'].includes(part));

const extractOutlinePhrases = (value: string) => {
  const cleaned = String(value || '')
    .replace(/【[^】]+】/g, ' ')
    .replace(/^[\d.、（()）\s]+/, '')
    .replace(/必须|应当|应|须|需要|围绕|结合|说明|明确|列明|响应/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const phrases = cleaned
    .split(/[；;。\n\r]/)
    .flatMap(part => part.split(/(?:包括|包含|覆盖|围绕|从|按|对|及|和|与)/))
    .flatMap(part => part.split(/[、，,]/))
    .map(part => part.replace(/^(本项目|本章节|当前章节|该章节|本项|该项|相关)/, '').trim())
    .map(part => part.replace(/(等|相关|方面|内容|要求|措施|方案|工作)$/g, '').trim())
    .filter(part => part.length >= 3 && part.length <= 18)
    .filter(part => !/^(招标文件|评分标准|响应矩阵|原文证据|按要求执行|以.*为准)$/.test(part));
  return uniqueTexts(phrases, 8);
};

const contextualThirdLevelPlans = (item: OutlineItem, basis: AutoOutlineBasis): ThirdLevelPlan[] => {
  const sourceText = [
    basis.description,
    basis.response_strategy,
    item.description,
    item.title,
  ].filter(Boolean).join('；');
  const titleTokens = outlineMatchTokens(item.title).slice(0, 4);
  const sourcePhrases = extractOutlinePhrases(sourceText);
  const matched = sourcePhrases.filter(phrase =>
    titleTokens.length === 0 || titleTokens.some(token => phrase.includes(token) || token.includes(phrase)),
  );
  const selected = uniqueTexts([...(matched.length ? matched : sourcePhrases), ...titleTokens], 4);
  return selected.slice(0, 4).map(title => ({
    title,
    description: [
      `围绕“${title}”展开本二级章节的具体写作内容。`,
      basis.description ? `对应要求：${basis.description}` : '',
      basis.response_strategy ? `响应策略：${basis.response_strategy}` : '',
    ].filter(Boolean).join('；'),
  }));
};

const outlineTextMatches = (item: OutlineItem, value: unknown) => {
  const candidate = String(value || '');
  if (!candidate) return false;
  const title = String(item.title || '');
  if (candidate.includes(title) || title.includes(candidate)) return true;
  const tokens = outlineMatchTokens(title);
  if (!tokens.length) return false;
  return tokens.some(token => candidate.includes(token));
};

const reportSourceItems = (report?: AnalysisReport | null): Array<Record<string, any>> => {
  if (!report) return [];
  return [
    ...(report.technical_scoring_items || []),
    ...(report.business_scoring_items || []),
    ...(report.price_scoring_items || []),
    ...(report.formal_review_items || []),
    ...(report.qualification_review_items || []),
    ...(report.responsiveness_review_items || []),
    ...(report.qualification_requirements || []),
    ...(report.formal_response_requirements || []),
    ...(report.mandatory_clauses || []),
    ...(report.rejection_risks || []),
    ...(report.required_materials || []),
    ...(report.missing_company_materials || []),
  ];
};

const sourceItemTitle = (source: Record<string, any>) =>
  compactOutlineTitle(source.name || source.title || source.clause || source.risk || source.summary || source.purpose || source.id);

const sourceItemDescription = (source: Record<string, any>) =>
  [
    source.standard,
    source.requirement,
    source.response_strategy,
    source.writing_focus,
    source.logic,
    source.mitigation,
    source.source,
  ].filter(Boolean).join('；').slice(0, 220);

const collectAutoOutlineBasis = (item: OutlineItem, report?: AnalysisReport | null): AutoOutlineBasis[] => {
  const matrixItems = report?.response_matrix?.items || [];
  const matrixIds = new Set(item.response_matrix_ids || []);
  const mappedIds = new Set([
    ...(item.scoring_item_ids || []),
    ...(item.requirement_ids || []),
    ...(item.risk_ids || []),
    ...(item.material_ids || []),
  ]);
  const bases: AutoOutlineBasis[] = [];
  const seen = new Set<string>();

  matrixItems.forEach((matrix) => {
    const matched = matrixIds.has(matrix.id)
      || (mappedIds.has(matrix.source_item_id) && outlineTextMatches(item, `${matrix.requirement_summary} ${matrix.response_strategy}`))
      || (matrix.target_chapter_ids || []).includes(item.id);
    if (!matched || seen.has(`matrix:${matrix.id}`)) return;
    seen.add(`matrix:${matrix.id}`);
    bases.push({
      id: matrix.id,
      title: compactOutlineTitle(matrix.requirement_summary || matrix.source_item_id, matrix.id),
      description: matrix.requirement_summary || '',
      response_strategy: matrix.response_strategy,
      source_refs: matrix.source_refs,
      risk_ids: matrix.risk_ids,
      material_ids: matrix.required_material_ids,
      response_matrix_ids: [matrix.id],
    });
  });

  const sources = reportSourceItems(report);
  sources.forEach((source) => {
    if (!mappedIds.has(source.id) || seen.has(`source:${source.id}`)) return;
    if (!outlineTextMatches(item, `${sourceItemTitle(source)} ${sourceItemDescription(source)}`)) return;
    seen.add(`source:${source.id}`);
    bases.push({
      id: source.id,
      title: sourceItemTitle(source),
      description: sourceItemDescription(source),
      scoring_item_ids: String(source.id).startsWith('T') || String(source.id).startsWith('B') || String(source.id).startsWith('P') ? [source.id] : [],
      requirement_ids: String(source.id).match(/^(Q|F|C|E)/) ? [source.id] : [],
      risk_ids: String(source.id).startsWith('R') ? [source.id] : [],
      material_ids: String(source.id).match(/^(M|X|EV|FF|SIG)/) ? [source.id] : [],
    });
  });

  return bases.slice(0, 8);
};

const effectiveScoringIds = (item: OutlineItem, report?: AnalysisReport | null) => {
  const fromBasis = collectAutoOutlineBasis(item, report).flatMap(basis => basis.scoring_item_ids || []);
  const ids = fromBasis.length ? fromBasis : (item.scoring_item_ids || []);
  return Array.from(new Set(ids));
};

const buildEvidenceThirdLevelChildren = (item: OutlineItem, basis: AutoOutlineBasis): OutlineItem[] => {
  const evidenceText = [
    basis.material_ids?.length ? `材料：${basis.material_ids.join('、')}` : '',
    basis.risk_ids?.length ? `风险：${basis.risk_ids.join('、')}` : '',
    basis.source_refs?.length ? `来源：${basis.source_refs.join('、')}` : '',
  ].filter(Boolean).join('；');
  const rows = contextualThirdLevelPlans(item, basis)
    .map((plan, index) => ({
      ...plan,
      description: index === 2 && evidenceText ? `${plan.description}；${evidenceText}` : plan.description,
    }));
  return rows.map((row, index) => ({
    ...item,
    id: `${item.id}.${index + 1}`,
    title: row.title,
    description: row.description,
    content: undefined,
    children: undefined,
  }));
};

const thirdLevelPattern = (item: OutlineItem) =>
  (item.children || []).map(child => child.title).join('|');

const hasContentInChildren = (item: OutlineItem) =>
  Boolean((item.children || []).some(child => child.content?.trim()));

const isRepeatedThirdLevelGroup = (item: OutlineItem, repeatedPatterns: Set<string>) =>
  Boolean(item.children?.length && !hasContentInChildren(item) && repeatedPatterns.has(thirdLevelPattern(item)));

const buildEvidenceSecondLevelChildren = (item: OutlineItem, report?: AnalysisReport | null): OutlineItem[] =>
  collectAutoOutlineBasis(item, report).slice(0, 6).map((basis, index) => {
    const child: OutlineItem = {
      ...item,
      id: `${item.id}.${index + 1}`,
      title: basis.title,
      description: basis.description || basis.response_strategy || item.description || '',
      response_matrix_ids: basis.response_matrix_ids || [],
      scoring_item_ids: basis.scoring_item_ids || item.scoring_item_ids || [],
      requirement_ids: basis.requirement_ids || item.requirement_ids || [],
      risk_ids: basis.risk_ids || item.risk_ids || [],
      material_ids: basis.material_ids || item.material_ids || [],
      content: undefined,
      children: undefined,
    };
    return child;
  });

const isPlaceholderOutlineChild = (item: OutlineItem) =>
  !item.content?.trim()
  && (item.source_type === 'manual' || item.title === '新章节')
  && /^新章节|待补充|请补充/.test(`${item.title}${item.description}`);

const isGeneratedSecondLevelGroup = (item: OutlineItem) =>
  Boolean(item.children?.length === 3 && item.children.every((child, index) =>
    child.id === `${item.id}.${index + 1}` &&
    !child.content?.trim() &&
    AUTO_SECOND_LEVEL_TITLES.has(child.title)
  ));

const isGeneratedThirdLevelGroup = (item: OutlineItem) =>
  Boolean(item.children?.length === 3 && item.children.every((child, index) =>
    child.id === `${item.id}.${index + 1}` &&
    !child.content?.trim() &&
    AUTO_THIRD_LEVEL_TITLES.has(child.title)
  ));

const ensureOutlineThirdLevel = (items: OutlineItem[], level = 1, report?: AnalysisReport | null): { items: OutlineItem[]; changed: boolean } => {
  let changed = false;
  const nextItems = items.map((item) => {
    let currentItem = item;
    if (level === 1 && item.children?.length) {
      const patternCounts = new Map<string, number>();
      item.children.forEach(child => {
        if (!child.children?.length || hasContentInChildren(child)) return;
        const pattern = thirdLevelPattern(child);
        if (!pattern) return;
        patternCounts.set(pattern, (patternCounts.get(pattern) || 0) + 1);
      });
      const repeatedPatterns = new Set(Array.from(patternCounts.entries()).filter(([, count]) => count > 1).map(([pattern]) => pattern));
      if (repeatedPatterns.size) {
        const repairedChildren = item.children.map(child => {
          if (!isRepeatedThirdLevelGroup(child, repeatedPatterns)) return child;
          return { ...child, children: undefined };
        });
        changed = true;
        currentItem = { ...item, children: repairedChildren };
      }
    }
    const hasOnlyPlaceholderChildren = Boolean(item.children?.length && item.children.every(isPlaceholderOutlineChild));
    if (level === 1 && (!currentItem.children?.length || isGeneratedSecondLevelGroup(currentItem) || hasOnlyPlaceholderChildren)) {
      const evidenceChildren = buildEvidenceSecondLevelChildren(currentItem, report);
      if (evidenceChildren.length) {
        changed = true;
        return { ...currentItem, children: evidenceChildren };
      }
      if (isGeneratedSecondLevelGroup(currentItem) || hasOnlyPlaceholderChildren) {
        changed = true;
        return { ...currentItem, children: undefined };
      }
    }
    if (level === 2 && isGeneratedThirdLevelGroup(currentItem)) {
      changed = true;
      return { ...currentItem, children: undefined };
    }
    if (currentItem.children?.length) {
      const result = ensureOutlineThirdLevel(currentItem.children, level + 1, report);
      if (result.changed) changed = true;
      return result.changed ? { ...currentItem, children: result.items } : currentItem;
    }
    return currentItem;
  });
  return { items: nextItems, changed };
};

export const useBidWorkspaceController = () => {
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
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState(state.uploadedFileName || '');
  const [referenceFileName, setReferenceFileName] = useState('');
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [legacyBusy, setLegacyBusy] = useState('');
  const [tasks, setTasks] = useState<Record<string, TaskState>>({});
  const [notice, setNotice] = useState<Notice | null>(null);
  const [streamText, setStreamText] = useState('');
  const [, setContentStreamText] = useState('');
  const [reviewReport, setReviewReport] = useState<ReviewReport | null>(null);
  const [consistencyReport, setConsistencyReport] = useState<ConsistencyRevisionReport | null>(null);
  const [referenceProfile, setReferenceProfile] = useState<Record<string, unknown>>({});
  const [matchedHistoryCase, setMatchedHistoryCase] = useState<Record<string, any> | null>(null);
  const [historyRequirementChecks, setHistoryRequirementChecks] = useState<Record<string, HistoryRequirementCheck>>({});
  const [historyRequirementSummary, setHistoryRequirementSummary] = useState<{ total: number; satisfied: number; not_found: number } | null>(null);
  const [checkingHistoryRequirements, setCheckingHistoryRequirements] = useState(false);
  const [documentBlocksPlan, setDocumentBlocksPlan] = useState<Record<string, unknown>>({});
  const [visualAssetResults, setVisualAssetResults] = useState<Record<string, VisualAssetResult>>({});
  const [activeReferenceSlotIndex, setActiveReferenceSlotIndex] = useState(0);
  const [verifyResult, setVerifyResult] = useState<ProviderVerifyResponse | null>(null);
  const [modelRuntime, setModelRuntime] = useState<ModelRuntimeResponse | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [localConfig, setLocalConfig] = useState<ConfigData>(state.config);
  const [selectedBidMode, setSelectedBidMode] = useState<BidMode>('full_bid');
  const [activeParseTabKey, setActiveParseTabKey] = useState<TenderParseTabKey>('basic');
  const [activeParseSectionId, setActiveParseSectionId] = useState('');
  const [activeSourceQuery, setActiveSourceQuery] = useState('');
  const [activeSourceLabel, setActiveSourceLabel] = useState('');
  const [sourceLocateRequestId, setSourceLocateRequestId] = useState(0);
  const [sourceLocateResult, setSourceLocateResult] = useState<SourceLocateResult>({ status: 'idle', label: '', snippet: '' });
  const [activeRenderedSourceBlock, setActiveRenderedSourceBlock] = useState<RenderedSourceBlockTarget | null>(null);
  const [activeDocxSourceNodeIndex, setActiveDocxSourceNodeIndex] = useState<number | null>(null);
  const [activeSourceLineHighlightIndex, setActiveSourceLineHighlightIndex] = useState<number | null>(null);
  const [analysisRevealPercent, setAnalysisRevealPercent] = useState(0);
  const [activeDocId, setActiveDocId] = useState('');
  const [outlineDraftRows, setOutlineDraftRows] = useState<DraftOutlineRow[]>([]);
  const [editingOutlineId, setEditingOutlineId] = useState('');
  const [outlineEditorForm, setOutlineEditorForm] = useState<OutlineEditorForm>({ id: '', title: '', description: '' });
  const [streamingChapterId, setStreamingChapterId] = useState('');
  const [analysisTaskId, setAnalysisTaskId] = useState('');
  const [analysisControl, setAnalysisControl] = useState<GenerationControlState>('idle');
  const [generationControl, setGenerationControl] = useState<GenerationControlState>('idle');
  const [generationProgress, setGenerationProgress] = useState<ProgressState | null>(null);
  const [exportDirectory, setExportDirectory] = useState('~/Downloads');
  const [manualReviewConfirmed, setManualReviewConfirmed] = useState(false);
  const [historyRecords, setHistoryRecords] = useState<DraftHistoryRecord[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [evidenceHighlighted, setEvidenceHighlighted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const referenceInputRef = useRef<HTMLInputElement>(null);
  const docPreviewRef = useRef<HTMLElement>(null);
  const docStageRef = useRef<HTMLDivElement>(null);
  const evidencePanelRef = useRef<HTMLDivElement>(null);
  const generationAbortRef = useRef<AbortController | null>(null);
  const generationPausedRef = useRef(false);
  const generationStoppedRef = useRef(false);
  const analysisStoppedRef = useRef(false);
  const batchOutlineRef = useRef<OutlineData | null>(null);
  const legacyBusyRef = useRef('');
  const uploadSessionRef = useRef(0);
  const lastDocxSourceScrollKeyRef = useRef('');
  const {
    advanceProgress,
    clampProgress,
    completeProgress,
    failProgress,
    progress,
    setProgress,
    startProgress,
    stopProgress,
    updateAnalysisStage,
  } = useProgressState(ANALYSIS_STEPS);

  const activeReport = state.analysisReport || state.outlineData?.analysis_report || null;
  const effectiveOutline = state.outlineData;
  const startTask = useCallback((id: string, detail = '') => {
    const normalizedId = normalizeTaskId(id || 'task');
    setTasks(prev => ({
      ...prev,
      [normalizedId]: {
        id: normalizedId,
        label: taskLabel(normalizedId),
        status: 'running',
        detail,
        dependsOn: taskDependencies(normalizedId),
        startedAt: Date.now(),
      },
    }));
  }, []);
  const finishTask = useCallback((id: string, status: Exclude<TaskStatus, 'idle' | 'blocked' | 'running'> = 'success', detail = '') => {
    if (!id) return;
    const normalizedId = normalizeTaskId(id);
    setTasks(prev => ({
      ...prev,
      [normalizedId]: {
        ...(prev[normalizedId] || {
          id: normalizedId,
          label: taskLabel(normalizedId),
          dependsOn: taskDependencies(normalizedId),
        }),
        status,
        detail: detail || prev[normalizedId]?.detail,
        error: status === 'error' ? detail || prev[normalizedId]?.error : prev[normalizedId]?.error,
        finishedAt: Date.now(),
      },
    }));
  }, []);
  const setBusy = useCallback((id: string) => {
    if (!id) {
      const previous = legacyBusyRef.current;
      if (previous) finishTask(previous, 'success');
      legacyBusyRef.current = '';
      setLegacyBusy('');
      return;
    }
    const previous = legacyBusyRef.current;
    if (previous && previous !== id) finishTask(previous, 'success');
    legacyBusyRef.current = id;
    setLegacyBusy(id);
    startTask(id);
  }, [finishTask, startTask]);
  const outlineReferenceProfile = profileRecord(effectiveOutline?.reference_bid_style_profile);
  const reportReferenceProfile = profileRecord(activeReport?.reference_bid_style_profile);
  const rawReferenceProfile = Object.keys(outlineReferenceProfile).length
    ? outlineReferenceProfile
    : Object.keys(reportReferenceProfile).length
      ? reportReferenceProfile
      : referenceProfile;
  const activeReferenceProfile = isUsableReferenceProfile(rawReferenceProfile) ? rawReferenceProfile : EMPTY_REFERENCE_PROFILE;
  const activeReferenceRecord = profileRecord(activeReferenceProfile);
  const referenceImageSlots = useMemo(
    () => (Array.isArray(activeReferenceRecord.image_slots) ? activeReferenceRecord.image_slots as Record<string, any>[] : []),
    [activeReferenceRecord],
  );
  const selectedReferenceSlot = referenceImageSlots[activeReferenceSlotIndex] || referenceImageSlots[0] || null;
  const referenceWordStyle = profileRecord(activeReferenceRecord.word_style_profile);
  const hasReferenceProfile = Object.keys(activeReferenceRecord).length > 0;
  const referenceProfileStats = [
    ['目录模板', `${listCount(activeReferenceRecord.outline_template)} 项`],
    ['章节骨架', `${listCount(activeReferenceRecord.chapter_blueprints)} 组`],
    ['表格模型', `${listCount(activeReferenceRecord.table_models)} 个`],
    ['图片/素材位', `${listCount(activeReferenceRecord.image_slots)} 个`],
  ];
  const wordPreviewStyle = useMemo(
    () => buildWordPreviewStyle(activeReferenceProfile as Record<string, unknown>),
    [activeReferenceProfile],
  );
  const activeDocumentBlocksPlan = effectiveOutline?.document_blocks_plan || activeReport?.document_blocks_plan || documentBlocksPlan;
  const displayDocumentBlocksPlan = useMemo(
    () => normalizeDocumentBlocksPlan(activeDocumentBlocksPlan as Record<string, unknown>, referenceImageSlots, effectiveOutline?.outline || []),
    [activeDocumentBlocksPlan, referenceImageSlots, effectiveOutline?.outline],
  );
  const plannedBlockGroups = useMemo<PlannedBlockGroup[]>(() => {
    const rawGroups = (displayDocumentBlocksPlan as any)?.document_blocks;
    if (!Array.isArray(rawGroups)) return [];
    return rawGroups.map((group: any) => ({
      chapter_id: String(group?.chapter_id || ''),
      chapter_title: String(group?.chapter_title || ''),
      blocks: Array.isArray(group?.blocks) ? group.blocks : [],
    })).filter(group => group.chapter_id || group.blocks.length);
  }, [displayDocumentBlocksPlan]);
  const plannedBlocksCount = plannedBlockGroups.reduce((sum, group) => sum + group.blocks.length, 0);
  const visualBlocksCount = plannedBlockGroups.reduce(
    (sum, group) => sum + group.blocks.filter(block => isVisualBlockType(block.block_type)).length,
    0,
  );
  const activeVisualAssets = useMemo(
    () => visualAssetsFromPlanGroups(plannedBlockGroups, visualAssetResults),
    [plannedBlockGroups, visualAssetResults],
  );
  const activeAssetLibrary = useMemo(
    () => ({ visual_assets: activeVisualAssets }),
    [activeVisualAssets],
  );
  const visualBlocksByChapter = useMemo(
    () => visualBlocksByChapterFromGroups(plannedBlockGroups, visualAssetResults),
    [plannedBlockGroups, visualAssetResults],
  );
  const generatedVisualCount = activeVisualAssets.length;
  const activeEnterpriseProfile = activeReport?.enterprise_material_profile || null;
  const activeResponseMatrix = effectiveOutline?.response_matrix || activeReport?.response_matrix || null;
  const responseMatrixItems = activeResponseMatrix?.items || [];
  const uncoveredMatrixCount = activeResponseMatrix?.uncovered_ids?.length || responseMatrixItems.filter(item => item.status !== 'covered').length;
  const tenderParseTabs = useMemo(() => buildTenderParseTabs(activeReport), [activeReport]);
  const activeParseTab = tenderParseTabs.find(tab => tab.key === activeParseTabKey) || tenderParseTabs[0];
  const activeParseSection = activeParseTab?.sections.find(section => section.id === activeParseSectionId) || activeParseTab?.sections[0];
  const sourceLines = useMemo(
    () => (state.fileContent || '').split(/\r?\n/).map(line => line.trimEnd()),
    [state.fileContent],
  );
  const sourcePreviewBlocks = useMemo<SourcePreviewBlock[]>(
    () => sourceLines.map((line, index) => buildSourcePreviewBlock(line, index)),
    [sourceLines],
  );
  const sourcePreviewPages = useMemo<SourcePreviewPage[]>(
    () => paginateSourcePreviewBlocks(sourcePreviewBlocks),
    [sourcePreviewBlocks],
  );
  const renderedSourcePages = useMemo(
    () => state.sourcePreviewPages || [],
    [state.sourcePreviewPages],
  );
  const hasSourcePreviewHtml = useMemo(
    () => Boolean(state.sourcePreviewHtml && stripPreviewInlineMarkup(state.sourcePreviewHtml).trim()),
    [state.sourcePreviewHtml],
  );
  const sourcePreviewHtmlWithLocateHighlight = useMemo(() => {
    const html = state.sourcePreviewHtml || '';
    if (!hasSourcePreviewHtml || activeDocxSourceNodeIndex === null) return html;
    if (typeof window === 'undefined' || typeof window.DOMParser === 'undefined') return html;

    const parser = new window.DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const nodes = Array.from(doc.querySelectorAll<HTMLElement>('.docx-source-preview p, .docx-source-preview h1, .docx-source-preview h2, .docx-source-preview h3, .docx-source-preview h4, .docx-source-preview td'));
    const target = nodes[activeDocxSourceNodeIndex];
    if (!target) return html;

    doc.querySelectorAll<HTMLElement>('.docx-source-node--active').forEach(node => {
      node.classList.remove('docx-source-node--active');
      node.removeAttribute('data-locate-label');
      node.removeAttribute('data-source-locate-active');
    });
    const locateLabel = activeSourceLabel || activeParseSection?.title || '';
    target.classList.add('docx-source-node--active');
    target.setAttribute('data-locate-label', locateLabel ? `${locateLabel}位置` : '原文位置');
    target.setAttribute('data-source-locate-active', 'true');
    return doc.body.innerHTML;
  }, [activeDocxSourceNodeIndex, activeParseSection?.title, activeSourceLabel, hasSourcePreviewHtml, state.sourcePreviewHtml]);
  const activeSourceLineIndex = useMemo(
    () => activeSourceQuery
      ? findSourceLineIndexByText(sourceLines, activeSourceQuery)
      : findSourceLineIndex(sourceLines, activeParseSection),
    [activeParseSection, activeSourceQuery, sourceLines],
  );
  const activeScoringRows = useMemo(
    () => activeReport && activeParseTab ? buildScoringRows(activeReport, activeParseTab.key) : [],
    [activeReport, activeParseTab],
  );
  const historyRequirementCheckList = useMemo(
    () => Object.values(historyRequirementChecks),
    [historyRequirementChecks],
  );
  const entries = useMemo(() => effectiveOutline ? collectEntries(effectiveOutline.outline) : [], [effectiveOutline]);
  const selectedEntry = entries.find(entry => entry.item.id === state.selectedChapter) || entries[0];
  const editingOutlineItem = useMemo(
    () => effectiveOutline && editingOutlineId ? findOutlineItem(effectiveOutline.outline, editingOutlineId) : null,
    [effectiveOutline, editingOutlineId],
  );
  const project = useMemo(
    () => buildProjectSummary(activeReport, state.projectOverview, state.techRequirements, state.fileContent, uploadedFileName || state.uploadedFileName),
    [activeReport, state.projectOverview, state.techRequirements, state.fileContent, uploadedFileName, state.uploadedFileName],
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
  const projectTitle = cleanDisplayTitle(project?.name)
    || cleanDisplayTitle(effectiveOutline?.project_name)
    || cleanDisplayTitle(uploadedFileName || state.uploadedFileName)
    || '待解析项目';
  const runtimeEvent = modelRuntime?.active_requests?.[0] || modelRuntime?.last_event || null;
  const runtimeStatus = runtimeEvent?.status || 'idle';
  const runtimeStatusText = modelRuntime?.active
    ? runtimeStatus === 'streaming'
      ? `模型返回中${runtimeEvent?.chunk_count ? ` · ${runtimeEvent.chunk_count}段` : ''}`
      : '模型连接中'
    : runtimeStatus === 'error'
      ? '模型调用失败'
      : runtimeStatus === 'success'
        ? '模型已返回'
        : '模型空闲';
  const sourcePanelStatusText = (() => {
    const label = sourceLocateResult.label || activeSourceLabel || activeParseSection?.title || '';
    if (sourceLocateResult.status === 'found') return `已定位：${label || '原文位置'}`;
    if (sourceLocateResult.status === 'locating') return `正在定位：${label || '原文位置'}`;
    if (sourceLocateResult.status === 'not-found') return `未精确命中：${label || '当前条目'}`;
    if (renderedSourcePages.length) return `Word 原文页图：${label || '上传文件'}`;
    if (hasSourcePreviewHtml) return `Word 原文：${label || '上传文件'}`;
    if (sourcePreviewPages.length) return `文本预览：${label || '上传文件'}`;
    return '等待上传文件';
  })();

  useEffect(() => setLocalConfig(state.config), [state.config]);

  useEffect(() => {
    setActiveReferenceSlotIndex(0);
  }, [referenceImageSlots.length]);

  useEffect(() => {
    if (state.uploadedFileName && state.uploadedFileName !== uploadedFileName) {
      setUploadedFileName(state.uploadedFileName);
    }
  }, [state.uploadedFileName, uploadedFileName]);

  useEffect(() => {
    if (!historyOpen) return;
    let cancelled = false;
    draftStorage.loadHistoryAsync().then((records) => {
      if (!cancelled) setHistoryRecords(records);
    });
    return () => {
      cancelled = true;
    };
  }, [historyOpen, state.fileContent, state.analysisReport, state.outlineData, state.selectedChapter]);

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
    let cancelled = false;
    const pollModelRuntime = () => {
      configApi.getModelRuntime()
        .then(response => {
          if (!cancelled) setModelRuntime(response.data);
        })
        .catch(() => {
          if (!cancelled) setModelRuntime(null);
        });
    };
    pollModelRuntime();
    const timer = window.setInterval(pollModelRuntime, modelRuntime?.active ? 2000 : 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [modelRuntime?.active]);

  useEffect(() => {
    if (!state.selectedChapter && entries[0]) updateSelectedChapter(entries[0].item.id);
  }, [entries, state.selectedChapter, updateSelectedChapter]);

  useEffect(() => {
    if (!activeDocId && selectedEntry?.item.id) setActiveDocId(selectedEntry.item.id);
  }, [activeDocId, selectedEntry?.item.id]);

  useEffect(() => {
    if (activeReport?.bid_mode_recommendation) setSelectedBidMode(normalizeBidMode(activeReport.bid_mode_recommendation));
  }, [activeReport?.bid_mode_recommendation]);

  useEffect(() => {
    if (!tenderParseTabs.length) return;
    const currentTab = tenderParseTabs.find(tab => tab.key === activeParseTabKey);
    if (!currentTab) {
      setActiveParseTabKey(tenderParseTabs[0].key);
      setActiveParseSectionId(tenderParseTabs[0].sections[0]?.id || '');
      return;
    }
    if (!currentTab.sections.some(section => section.id === activeParseSectionId)) {
      setActiveParseSectionId(currentTab.sections[0]?.id || '');
    }
  }, [activeParseSectionId, activeParseTabKey, tenderParseTabs]);

  useEffect(() => {
    if (activeNav !== 'analysis' || !activeReport) {
      setAnalysisRevealPercent(0);
      return;
    }

    setAnalysisRevealPercent(0);
    let nextPercent = 0;
    const timer = window.setInterval(() => {
      nextPercent = Math.min(100, nextPercent + 12);
      setAnalysisRevealPercent(nextPercent);
      if (nextPercent >= 100) window.clearInterval(timer);
    }, 90);

    return () => window.clearInterval(timer);
  }, [activeNav, activeReport]);

  useEffect(() => {
    if (!sourceLocateRequestId || activeNav !== 'analysis') return;
    window.requestAnimationFrame(() => {
      const locateLabel = activeSourceLabel || activeParseSection?.title || '';
      const panel = evidencePanelRef.current;
      panel?.querySelectorAll<HTMLElement>('.docx-source-node--active').forEach(node => {
        node.classList.remove('docx-source-node--active');
        node.removeAttribute('data-locate-label');
      });
      setActiveRenderedSourceBlock(null);
      setActiveDocxSourceNodeIndex(null);
      setActiveSourceLineHighlightIndex(null);
      if (renderedSourcePages.length) {
        const tokens = (activeSourceQuery
          ? sourceSearchTokensForLocate(activeSourceQuery, activeParseSection)
          : sourceSearchTokensForLocate('', activeParseSection))
          .map(normalizeSourceText)
          .filter(token => token.length >= 4);
        const rankedTargets = renderedSourcePages
          .flatMap(page => (page.text_blocks || []).map(block => ({
            page,
            block,
            score: scoreSourceNodeMatch(block.text || '', tokens),
          })))
          .filter(item => item.score > 0)
          .sort((left, right) => right.score - left.score);
        const target = rankedTargets[0];
        if (target) {
          setActiveRenderedSourceBlock({ pageNumber: target.page.page_number, blockId: target.block.id });
          window.requestAnimationFrame(() => {
            document.getElementById(`source-rendered-block-${target.page.page_number}-${target.block.id}`)?.scrollIntoView({
              behavior: 'smooth',
              block: 'center',
            });
          });
          setSourceLocateResult({
            status: 'found',
            label: locateLabel,
            snippet: stripPreviewInlineMarkup(target.block.text || '').slice(0, 120),
          });
          return;
        }
        setActiveRenderedSourceBlock(null);
        evidencePanelRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
        setSourceLocateResult({ status: 'not-found', label: locateLabel, snippet: '' });
        return;
      }
      if (hasSourcePreviewHtml) {
        const tokens = (activeSourceQuery
          ? sourceSearchTokensForLocate(activeSourceQuery, activeParseSection)
          : sourceSearchTokensForLocate('', activeParseSection))
          .map(normalizeSourceText)
          .filter(token => token.length >= 4);
        const nodes = Array.from(panel?.querySelectorAll<HTMLElement>('.docx-source-preview p, .docx-source-preview h1, .docx-source-preview h2, .docx-source-preview h3, .docx-source-preview h4, .docx-source-preview td') || []);
        const rankedTargets = nodes
          .map((node, index) => ({
            node,
            index,
            score: scoreSourceNodeMatch(node.innerText || node.textContent || '', tokens),
          }))
          .filter(item => item.score > 0)
          .sort((left, right) => right.score - left.score);
        const target = rankedTargets[0];
        if (target) {
          setActiveDocxSourceNodeIndex(target.index);
          setSourceLocateResult({
            status: 'found',
            label: locateLabel,
            snippet: stripPreviewInlineMarkup((target.node.innerText || target.node.textContent || '').replace(/\s+/g, ' ')).slice(0, 120),
          });
          return;
        }
        evidencePanelRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
        setSourceLocateResult({ status: 'not-found', label: locateLabel, snippet: '' });
        return;
      }
      if (activeSourceLineIndex >= 0) {
        setActiveSourceLineHighlightIndex(activeSourceLineIndex);
        document.getElementById(`source-line-${activeSourceLineIndex}`)?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
        setSourceLocateResult({
          status: 'found',
          label: locateLabel,
          snippet: stripPreviewInlineMarkup(sourceLines[activeSourceLineIndex] || '').slice(0, 120),
        });
        return;
      }
      evidencePanelRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      setSourceLocateResult({ status: 'not-found', label: locateLabel, snippet: '' });
    });
  }, [activeNav, activeParseSection, activeSourceLabel, activeSourceLineIndex, activeSourceQuery, hasSourcePreviewHtml, renderedSourcePages, sourceLines, sourceLocateRequestId, state.sourcePreviewHtml]);

  useEffect(() => {
    if (!hasSourcePreviewHtml || activeDocxSourceNodeIndex === null) return;
    const frame = window.requestAnimationFrame(() => {
      const panel = evidencePanelRef.current;
      const target = panel?.querySelector<HTMLElement>('.docx-source-node--active[data-source-locate-active="true"]');
      if (!target) return;
      const scrollKey = `${sourceLocateRequestId}:${activeDocxSourceNodeIndex}`;
      if (lastDocxSourceScrollKeyRef.current !== scrollKey) {
        lastDocxSourceScrollKeyRef.current = scrollKey;
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeDocxSourceNodeIndex, hasSourcePreviewHtml, sourceLocateRequestId, sourcePreviewHtmlWithLocateHighlight]);

  useEffect(() => {
    if (!state.outlineData?.outline?.length) return;
    const result = ensureOutlineThirdLevel(state.outlineData.outline, 1, activeReport);
    if (result.changed) {
      updateOutline({ ...state.outlineData, outline: result.items });
    }
  }, [activeReport, state.outlineData, updateOutline]);

  const setError = (text: string) => setNotice({ type: 'error', text });
  const setSuccess = (text: string) => setNotice({ type: 'success', text });
  const setInfo = (text: string) => setNotice({ type: 'info', text });
  const refreshHistory = () => {
    if (!historyOpen) return;
    draftStorage.loadHistoryAsync().then(setHistoryRecords);
  };

  const toggleHistoryPanel = () => {
    setHistoryOpen(prev => {
      const next = !prev;
      if (next) draftStorage.loadHistoryAsync().then(setHistoryRecords);
      return next;
    });
  };

  const selectParseSection = (sectionId: string) => {
    const section = activeParseTab?.sections.find(item => item.id === sectionId);
    const label = section?.title || '';
    setActiveParseSectionId(sectionId);
    setActiveSourceQuery('');
    setActiveSourceLabel(label);
    setSourceLocateResult({ status: 'locating', label, snippet: '' });
    setSourceLocateRequestId(value => value + 1);
    setEvidenceHighlighted(true);
    window.requestAnimationFrame(() => {
      evidencePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'end' });
    });
    window.setTimeout(() => setEvidenceHighlighted(false), 1100);
  };

  const locateSourceItem = (label: string, text: string) => {
    setActiveSourceQuery(text);
    setActiveSourceLabel(label);
    setSourceLocateResult({ status: 'locating', label, snippet: '' });
    setSourceLocateRequestId(value => value + 1);
    setEvidenceHighlighted(true);
    window.requestAnimationFrame(() => {
      evidencePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'end' });
    });
    window.setTimeout(() => setEvidenceHighlighted(false), 1100);
  };

  const openOutlineEditor = (item: OutlineItem) => {
    setEditingOutlineId(item.id);
    setOutlineEditorForm({
      id: item.id,
      title: item.title,
      description: item.description || '',
    });
    if (!item.children?.length) updateSelectedChapter(item.id);
  };

  const closeOutlineEditor = () => {
    setEditingOutlineId('');
    setOutlineEditorForm({ id: '', title: '', description: '' });
  };

  const saveOutlineEditor = () => {
    if (!effectiveOutline || !editingOutlineId) return;
    const title = outlineEditorForm.title.trim();
    if (!title) {
      setError('章节标题不能为空');
      return;
    }
    const nextOutline = {
      ...effectiveOutline,
      outline: updateOutlineItem(effectiveOutline.outline, editingOutlineId, {
        title,
        description: outlineEditorForm.description.trim(),
      }),
    };
    updateOutline(nextOutline);
    setManualReviewConfirmed(false);
    setOutlineDraftRows(flattenOutlineDraftRows(nextOutline.outline));
    setSuccess(`已更新目录节点 ${editingOutlineId}`);
  };

  const handleAddOutlineChild = (parent: OutlineItem) => {
    if (!effectiveOutline) return;
    const evidenceChildren = buildEvidenceSecondLevelChildren(parent, activeReport);
    if (evidenceChildren.length) {
      const existingIds = new Set((parent.children || []).map(child => child.id));
      const existingTitles = new Set((parent.children || []).map(child => child.title));
      const keptChildren = (parent.children || []).filter(child => !isPlaceholderOutlineChild(child));
      const missingChildren = evidenceChildren.filter(child => !existingIds.has(child.id) && !existingTitles.has(child.title));
      const nextChildren = keptChildren.length || missingChildren.length
        ? [...keptChildren, ...missingChildren]
        : evidenceChildren;
      const nextOutline = {
        ...effectiveOutline,
        outline: updateOutlineItem(effectiveOutline.outline, parent.id, { children: nextChildren }),
      };
      updateOutline(nextOutline);
      setManualReviewConfirmed(false);
      const selectedChild = missingChildren[0] || nextChildren[0];
      if (selectedChild) {
        updateSelectedChapter(selectedChild.id);
        setActiveDocId(selectedChild.id);
        openOutlineEditor(selectedChild);
      }
      setOutlineDraftRows(flattenOutlineDraftRows(nextOutline.outline));
      setSuccess(`已按响应矩阵补齐 ${nextChildren.length} 个子章节`);
      return;
    }
    setError('当前章节没有可用于生成子级的响应矩阵、评分项、审查项或材料映射；请先重新生成目录映射，避免创建无依据的“新章节”。');
  };

  const handleDeleteOutlineItem = (item: OutlineItem) => {
    if (!effectiveOutline) return;
    if (effectiveOutline.outline.length <= 1 && effectiveOutline.outline[0]?.id === item.id) {
      setError('至少需要保留一个顶层章节');
      return;
    }
    const hasContent = Boolean(item.content?.trim() || collectEntries(item.children || []).some(entry => entry.item.content?.trim()));
    const prompt = hasContent
      ? `确定删除“${item.id} ${item.title}”及其下级章节吗？已生成正文也会从当前草稿目录中移除。`
      : `确定删除“${item.id} ${item.title}”及其下级章节吗？`;
    if (!window.confirm(prompt)) return;
    const nextItems = deleteOutlineItem(effectiveOutline.outline, item.id);
    const nextOutline = { ...effectiveOutline, outline: nextItems };
    updateOutline(nextOutline);
    setManualReviewConfirmed(false);
    setOutlineDraftRows(flattenOutlineDraftRows(nextItems));
    const stillSelected = state.selectedChapter ? findOutlineItem(nextItems, state.selectedChapter) : null;
    if (!stillSelected) {
      const first = collectEntries(nextItems)[0];
      updateSelectedChapter(first?.item.id || '');
      setActiveDocId(first?.item.id || '');
    }
    if (editingOutlineId === item.id || !findOutlineItem(nextItems, editingOutlineId)) closeOutlineEditor();
    setSuccess(`已删除目录节点 ${item.id}`);
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

  const scrollDocumentStageTo = (itemId: string) => {
    window.requestAnimationFrame(() => {
      const target = document.getElementById(docSectionId(itemId));
      if (!target) return;
      const stage = docStageRef.current;
      if (!stage) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      const stageRect = stage.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const nextTop = Math.max(0, stage.scrollTop + targetRect.top - stageRect.top - 18);
      stage.scrollTo({ top: nextTop, behavior: 'smooth' });
    });
  };

  const scrollToDocumentNode = (item: OutlineItem) => {
    const firstLeaf = findFirstLeaf(item);
    setActiveDocId(item.id);
    updateSelectedChapter(firstLeaf.id);
    scrollDocumentStageTo(item.id);
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

  const restoreHistoryRecord = async (record: DraftHistoryRecord) => {
    const activated = await draftStorage.activateHistoryAsync(record.id);
    const draft = (activated || record).draft;
    restoreDraft(draft);
    setReviewReport(null);
    setManualReviewConfirmed(false);
    setActiveDocId(draft.selectedChapter || '');
    setUploadedFileName(draft.uploadedFileName || record.title);
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
    const normalizedMode = normalizeBidMode(mode);
    setSelectedBidMode(normalizedMode);
    if (effectiveOutline) updateOutline({ ...effectiveOutline, bid_mode: normalizedMode });
    setInfo(`已切换为${bidModeLabel(normalizedMode)}生成，后续目录、正文和审校会按该模式请求模型`);
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
    const uploadSession = uploadSessionRef.current + 1;
    uploadSessionRef.current = uploadSession;
    setBusy('upload');
    const taskVersion = startProgress('文件上传', ['读取文件', '后端解析文本'], '正在上传并读取招标文件', 12);
    setNotice(null);
    try {
      const response = await documentApi.uploadFileText(file);
      if (!response.data.success || !response.data.file_content) throw new Error(response.data.message || '上传失败');
      setUploadedFileName(file.name);
      setReviewReport(null);
      setManualReviewConfirmed(false);
      setConsistencyReport(null);
      setDocumentBlocksPlan({});
      setVisualAssetResults({});
      setHistoryRequirementChecks({});
      setHistoryRequirementSummary(null);
      setActiveDocId('');
      setOutlineDraftRows([]);
      setStreamingChapterId('');
      setContentStreamText('');
      setStreamText('');
      updateFileContent(
        response.data.file_content,
        file.name,
        response.data.parser_info,
        '',
        [],
      );
      completeProgress('文件已上传，文本读取完成', taskVersion);
      if (response.data.source_preview_id && response.data.source_preview_status === 'pending') {
        startTask('source_preview', '正在生成上传文档原文预览');
        void documentApi.getSourcePreview(response.data.source_preview_id)
          .then(previewResponse => {
            if (uploadSessionRef.current !== uploadSession) return;
            if (!previewResponse.data.success) {
              finishTask('source_preview', 'error', previewResponse.data.message || '原文预览生成失败');
              return;
            }
            restoreDraft({
              sourcePreviewHtml: previewResponse.data.source_preview_html || '',
              sourcePreviewPages: previewResponse.data.source_preview_pages || [],
              parserInfo: {
                ...(response.data.parser_info || {}),
                ...(previewResponse.data.parser_info || {}),
              },
            });
            finishTask(
              'source_preview',
              'success',
              previewResponse.data.source_preview_status === 'ready' ? '原文预览已生成' : '该文件暂无可用原文预览',
            );
          })
          .catch((previewError: any) => {
            if (uploadSessionRef.current !== uploadSession) return;
            finishTask('source_preview', 'error', previewError.response?.data?.detail || previewError.message || '原文预览生成失败');
          });
      } else {
        finishTask('source_preview', 'success', '该文件使用文本预览');
      }
    } catch (error: any) {
      failProgress(error.response?.data?.detail || error.message || '文件上传失败', 1, taskVersion);
      setError(error.response?.data?.detail || error.message || '文件上传失败');
    } finally {
      setBusy('');
    }
  };

  const clearReferenceProfileFromDraft = () => {
    setReferenceProfile({});
    setMatchedHistoryCase(null);
    if (state.analysisReport) {
      updateAnalysisResults(state.projectOverview, state.techRequirements, {
        ...state.analysisReport,
        reference_bid_style_profile: {},
      });
    }
    if (effectiveOutline) {
      updateOutline({ ...effectiveOutline, reference_bid_style_profile: {} });
    }
  };

  const handleReferenceSelect = (file: File) => {
    if (!file.name.toLowerCase().match(/\.(pdf|docx)$/)) {
      setError('样例文件仅支持 PDF 和 DOCX');
      return;
    }
    if (file.size > 500 * 1024 * 1024) {
      setError('样例文件大小不能超过 500MB');
      return;
    }
    setReferenceFile(file);
    setReferenceFileName(file.name);
    clearReferenceProfileFromDraft();
    setSuccess('成熟样例已选择，点击“去解析”后会调用文档解析器和模型解析');
  };

  const runReferenceAnalysis = async () => {
    if (!referenceFile) {
      setError('请先选择成熟样例文件');
      return;
    }
    setBusy('reference');
    const taskVersion = startProgress('样例解析', ['解析样例文本', '提取写作模板'], '正在解析成熟投标文件样例', 10);
    try {
      const response = await documentApi.uploadReferenceStyleFile(referenceFile);
      if (!response.data.success || !response.data.reference_bid_style_profile) {
        throw new Error(response.data.message || '样例解析失败');
      }
      const profile = response.data.reference_bid_style_profile;
      setReferenceFileName(referenceFile.name);
      setReferenceProfile(profile);
      if (state.analysisReport) {
        updateAnalysisResults(state.projectOverview, state.techRequirements, {
          ...state.analysisReport,
          reference_bid_style_profile: profile,
        });
      }
      if (effectiveOutline) {
        updateOutline({ ...effectiveOutline, reference_bid_style_profile: profile });
      }
      completeProgress('样例写作模板已生成', taskVersion);
      setSuccess('成熟样例已接入，后续响应矩阵、目录、正文和审校会复用其模板结构');
    } catch (error: any) {
      failProgress(error.response?.data?.detail || error.message || '样例解析失败', undefined, taskVersion);
      setError(error.response?.data?.detail || error.message || '样例解析失败');
    } finally {
      setBusy('');
    }
  };

  const runHistoryReferenceMatch = async () => {
    if (!state.fileContent?.trim()) {
      setError('请先上传并解析招标文件，再自动匹配历史案例库');
      return;
    }
    setBusy('reference-match');
    const taskVersion = startProgress(
      '历史案例匹配',
      ['召回历史案例', 'LLM 选择案例', '生成样例模板'],
      '正在从历史标书数据库匹配成熟案例',
      8,
    );
    try {
      const response = await documentApi.matchHistoryReference({
        file_content: state.fileContent,
        analysis_report: activeReport || {},
        limit: 8,
        use_llm: true,
      });
      if (!response.data.success || !response.data.reference_bid_style_profile) {
        throw new Error(response.data.message || '历史案例匹配失败');
      }
      const profile = response.data.reference_bid_style_profile;
      const matched = response.data.matched_case || null;
      setReferenceFile(null);
      setMatchedHistoryCase(matched);
      setReferenceFileName(matched?.project_title || '历史案例库自动匹配');
      setReferenceProfile(profile);
      if (state.analysisReport) {
        updateAnalysisResults(state.projectOverview, state.techRequirements, {
          ...state.analysisReport,
          reference_bid_style_profile: profile,
        });
      }
      if (effectiveOutline) {
        updateOutline({ ...effectiveOutline, reference_bid_style_profile: profile });
      }
      completeProgress('历史案例已匹配并生成样例模板', taskVersion);
      setSuccess(`已匹配历史案例：${matched?.project_title || '历史案例库'}`);
    } catch (error: any) {
      failProgress(error.response?.data?.detail || error.message || '历史案例匹配失败', undefined, taskVersion);
      setError(error.response?.data?.detail || error.message || '历史案例匹配失败');
    } finally {
      setBusy('');
    }
  };

  const runHistoryRequirementCheck = async (report: AnalysisReport | null = activeReport, silent = false) => {
    if (!report) {
      if (!silent) setError('请先完成标准解析，再进行历史库满足性检查');
      return;
    }
    setCheckingHistoryRequirements(true);
    if (!silent) setInfo('正在用历史数据库核对要求满足状态');
    try {
      const response = await documentApi.checkHistoryRequirements({
        analysis_report: report,
        limit_per_item: 3,
        use_llm: false,
      });
      if (!response.data.success) {
        throw new Error(response.data.message || '历史库满足性检查失败');
      }
      const nextChecks = response.data.checks.reduce<Record<string, HistoryRequirementCheck>>((acc, check) => {
        acc[check.item_id] = check;
        return acc;
      }, {});
      setHistoryRequirementChecks(nextChecks);
      setHistoryRequirementSummary(response.data.summary);
      if (!silent) {
        setSuccess(`要求匹配完成：${response.data.summary.satisfied}/${response.data.summary.total} 项满足`);
      }
    } catch (error: any) {
      if (!silent) setError(error.response?.data?.detail || error.message || '历史库满足性检查失败');
    } finally {
      setCheckingHistoryRequirements(false);
    }
  };

  const getRequirementCheckForItem = (id: string, label = '') => {
    const exact = historyRequirementChecks[id];
    if (exact) return exact;
    const normalizedId = normalizeSourceText(id);
    const normalizedLabel = normalizeSourceText(label);
    return historyRequirementCheckList.find(check => {
      const checkId = normalizeSourceText(check.item_id || '');
      const checkLabel = normalizeSourceText(check.label || '');
      if (checkId && (normalizedId === checkId || normalizedId.endsWith(checkId) || checkId.endsWith(normalizedId))) {
        return true;
      }
      return Boolean(normalizedLabel && checkLabel && (normalizedLabel === checkLabel || normalizedLabel.includes(checkLabel) || checkLabel.includes(normalizedLabel)));
    });
  };

  const renderRequirementMatchIcon = (
    check?: HistoryRequirementCheck,
    compact = false,
    titleOverride?: string,
    ariaOverride?: string,
    missingTitleOverride?: string,
  ) => {
    if (checkingHistoryRequirements && !check) {
      return <span className={`requirement-match requirement-match--pending ${compact ? 'requirement-match--compact' : ''}`} title="正在匹配数据库">…</span>;
    }
    if (!check) {
      if (historyRequirementSummary) {
        return (
          <span className={`requirement-match requirement-match--miss ${compact ? 'requirement-match--compact' : ''}`} title={missingTitleOverride || '数据库未匹配到满足证据'}>
            <XMarkIcon className="h-4 w-4" />
          </span>
        );
      }
      return <span className={`requirement-match requirement-match--idle ${compact ? 'requirement-match--compact' : ''}`} title="待匹配">待</span>;
    }
    return (
      <span
        className={`requirement-match ${check.satisfied ? 'requirement-match--ok' : 'requirement-match--miss'} ${compact ? 'requirement-match--compact' : ''}`}
        title={titleOverride || (check.satisfied ? '数据库匹配：满足要求' : '数据库匹配：不满足要求')}
        aria-label={ariaOverride || (check.satisfied ? '满足要求' : '不满足要求')}
      >
        {check.satisfied ? <CheckCircleIcon className="h-4 w-4" /> : <XMarkIcon className="h-4 w-4" />}
      </span>
    );
  };

  const controlAnalysisTask = async (action: 'pause' | 'resume' | 'stop') => {
    if (!analysisTaskId) {
      setError('解析任务尚未建立，请等待后端返回任务编号');
      return;
    }
    try {
      await documentApi.controlAnalysisTask(analysisTaskId, action);
      if (action === 'pause') {
        setAnalysisControl('paused');
        setProgress(prev => prev ? { ...prev, status: 'paused', detail: `已暂停：${prev.detail}` } : prev);
        setInfo('标准解析已暂停');
        return;
      }
      if (action === 'resume') {
        setAnalysisControl('running');
        setProgress(prev => prev ? { ...prev, status: 'running', detail: prev.detail.replace(/^已暂停：/, '') } : prev);
        setInfo('标准解析已继续');
        return;
      }
      analysisStoppedRef.current = true;
      setAnalysisControl('stopped');
      stopProgress('标准解析已停止，可重新开始解析');
      setBusy('');
      setInfo('标准解析已停止');
    } catch (error: any) {
      setError(apiErrorMessage(error, '解析任务控制失败'));
    }
  };

  const runAnalysis = async () => {
    if (!state.fileContent) {
      setError('请先上传招标文件');
      return;
    }
    if (!hasParsedDocumentText(state.fileContent)) {
      setError('请先重新上传招标文件，并等待文档解析完成后再进入标准解析。');
      return;
    }
    setBusy('analysis');
    const taskVersion = startProgress('标准解析', ANALYSIS_STEPS, '准备调用模型解析招标文件', 6);
    analysisStoppedRef.current = false;
    setAnalysisTaskId('');
    setAnalysisControl('running');
    setStreamText('');
    setReviewReport(null);
    setConsistencyReport(null);
    setManualReviewConfirmed(false);
    try {
      let reportRaw = '';
      const reportResponse = await documentApi.analyzeReportStream({
        file_content: state.fileContent,
        config: toLiteLLMConfig(localConfig),
      });
      await consumeSseStream(reportResponse, (payload) => {
        if (payload.task_id) {
          setAnalysisTaskId(String(payload.task_id));
        }
        if (payload.stopped) {
          analysisStoppedRef.current = true;
          setAnalysisControl('stopped');
          stopProgress(payload.detail || payload.message || '标准解析已停止', taskVersion);
          return;
        }
        if (payload.error) throw new Error(payload.message || '结构化解析失败');
        if (typeof payload.step_index === 'number' && payload.detail) {
          const status = ['running', 'success', 'error', 'paused', 'stopped'].includes(payload.status) ? payload.status : 'running';
          updateAnalysisStage(
            String(payload.detail),
            Number(payload.percent ?? 0),
            Number(payload.step_index),
            status as ProgressState['status'],
            payload.task_id ? String(payload.task_id) : undefined,
            taskVersion,
          );
        }
        if (typeof payload.chunk === 'string' && payload.chunk) {
          reportRaw += payload.chunk;
          setStreamText(reportRaw);
        }
      });
      if (analysisStoppedRef.current) {
        setStreamText('');
        return;
      }
      advanceProgress('正在校验并写入结构化解析结果', 96, 4, taskVersion);
      if (!reportRaw.trim()) {
        throw new Error('后端只返回了心跳，没有返回标准解析 JSON。通常表示模型调用长时间未完成、连接提前结束，或后端任务被中断；系统不会使用兜底报告。');
      }
      const report = parseJsonPayload<AnalysisReport>(reportRaw, '标准解析');
      const blockingWarning = getBlockingAnalysisReportWarning(report);
      if (blockingWarning) {
        throw new Error(`标准解析未完整完成：${blockingWarning}。请重新解析，目录阶段不会使用该报告。`);
      }
      report.bid_mode_recommendation = normalizeBidMode(report.bid_mode_recommendation);
      if (Object.keys(referenceProfile).length) {
        report.reference_bid_style_profile = referenceProfile;
      }
      const overview = summarizeAnalysisReport(report);
      const requirements = summarizeRequirementsFromReport(report);
      updateAnalysisResults(overview.trim(), requirements.trim(), report);
      setStreamText('');
      completeProgress('标准解析完成', taskVersion);
      setSuccess('标准解析完成，已生成项目、评分、风险和材料结构');
      void runHistoryRequirementCheck(report, true);
    } catch (error: any) {
      if (analysisStoppedRef.current || error?.name === 'AbortError') {
        stopProgress('标准解析已停止，可重新开始解析', taskVersion);
        setInfo('标准解析已停止');
        return;
      }
      failProgress(error.message || '标准解析失败', undefined, taskVersion);
      setError(error.message || '标准解析失败');
    } finally {
      setBusy('');
      setAnalysisTaskId('');
      if (!analysisStoppedRef.current) setAnalysisControl('idle');
    }
  };

  const runOutline = async () => {
    if (!state.projectOverview || !state.techRequirements || !state.analysisReport) {
      setError('请先完成标准解析');
      return;
    }
    const blockingWarning = getBlockingAnalysisReportWarning(state.analysisReport);
    if (blockingWarning) {
      setError(`标准解析未完整完成：${blockingWarning}。请先重新解析，目录阶段不会使用兜底报告。`);
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
        file_content: state.fileContent,
        analysis_report: state.analysisReport,
        bid_mode: normalizeBidMode(selectedBidMode),
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: displayDocumentBlocksPlan,
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '目录生成失败');
        if (payload.preview) {
          const preview = payload.preview as { message?: string; rows?: OutlineItem[] };
          const rows = flattenOutlineDraftRows(preview.rows || []);
          if (rows.length) setOutlineDraftRows(rows);
          return;
        }
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          const draftRows = parseOutlineDraftRows(raw);
          if (draftRows.length) setOutlineDraftRows(draftRows);
          advanceProgress('正在调用模型生成目录和映射关系', Math.min(92, 16 + Math.floor(raw.length / 220)), raw.length > 1000 ? 2 : 1, taskVersion);
        }
      });
      advanceProgress('正在写入目录结构和评分映射', 96, 2, taskVersion);
      let outline: OutlineData;
      try {
        outline = parseJsonPayload<OutlineData>(raw, '目录生成');
      } catch (parseError: any) {
        if (!CLIENT_GENERATION_FALLBACKS_ENABLED) {
          throw parseError;
        }
        outline = buildClientFallbackOutline(
          state.analysisReport as AnalysisReport,
          normalizeBidMode(selectedBidMode),
          activeReferenceProfile,
          displayDocumentBlocksPlan,
        );
        setInfo(parseError.message || '模型返回不完整 JSON，已使用解析报告生成兜底目录');
      }
      const nextOutline = {
        ...outline,
        project_name: cleanDisplayTitle(state.analysisReport.project?.name)
          || cleanDisplayTitle(uploadedFileName || state.uploadedFileName)
          || cleanDisplayTitle(state.analysisReport.project?.number)
          || '投标文件',
        project_overview: state.projectOverview,
        analysis_report: state.analysisReport,
        response_matrix: outline.response_matrix || state.analysisReport.response_matrix,
        coverage_summary: outline.coverage_summary || state.analysisReport.response_matrix?.coverage_summary,
        reference_bid_style_profile: outline.reference_bid_style_profile || activeReferenceProfile,
        document_blocks_plan: outline.document_blocks_plan || displayDocumentBlocksPlan,
        asset_library: outline.asset_library || effectiveOutline?.asset_library || { visual_assets: [] },
        bid_mode: normalizeBidMode(selectedBidMode),
      };
      if (nextOutline.document_blocks_plan) {
        setDocumentBlocksPlan(nextOutline.document_blocks_plan);
      }
      updateOutline(nextOutline);
      setManualReviewConfirmed(false);
      const first = collectEntries(nextOutline.outline)[0];
      if (first) updateSelectedChapter(first.item.id);
      setStreamText('');
      setOutlineDraftRows(flattenOutlineDraftRows(nextOutline.outline));
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
      bid_mode: normalizeBidMode(effectiveOutline.bid_mode || selectedBidMode),
      reference_bid_style_profile: activeReferenceProfile,
      document_blocks_plan: displayDocumentBlocksPlan,
      asset_library: activeAssetLibrary,
      generated_summaries: entries
        .filter(item => item.item.id !== entry.item.id && item.item.content?.trim())
        .slice(-12)
        .map(item => ({ chapter_id: item.item.id, summary: `${item.item.title}：${(item.item.content || '').slice(0, 260)}` })),
      enterprise_materials: (activeReport.required_materials || []).filter(item => item.status === 'provided'),
      enterprise_material_profile: activeEnterpriseProfile || undefined,
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
    setManualReviewConfirmed(false);
    setActiveDocId(entry.item.id);
    if (scroll) {
      scrollDocumentStageTo(entry.item.id);
    }
    return nextOutline;
  };

  const runCurrentChapter = async () => {
    if (!selectedEntry) return;
    setBusy(`chapter:${selectedEntry.item.id}`);
    setContentStreamText('');
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
        onContent: (partial) => {
          setContentStreamText(partial);
          saveGeneratedContent(selectedEntry, partial, false);
        },
        onProgress: (partial) => {
          const percent = Math.min(84, 18 + Math.floor(partial.length / 120));
          advanceProgress(`正在写入 ${selectedEntry.item.id} ${selectedEntry.item.title}`, percent, 1, taskVersion);
          syncGenerationProgress(`正在写入 ${selectedEntry.item.id} ${selectedEntry.item.title}`, percent, 1, '正文生成');
        },
      });
      advanceProgress('正在保存本章正文', 88, 2, taskVersion);
      saveGeneratedContent(selectedEntry, content);
      await draftStorage.flushPendingSave();
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
    setContentStreamText('');
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
      const concurrency = Math.min(contentConcurrencyLimit(), Math.max(1, pendingEntries.length));
      let completedCount = 0;
      let firstError: unknown = null;
      const runEntry = async (entry: ChapterEntry, index: number) => {
        await waitIfGenerationPaused();
        if (firstError) return;
        if (entry.item.content?.trim()) return;
        setStreamingChapterId(entry.item.id);
        setActiveDocId(entry.item.id);
        updateSelectedChapter(entry.item.id);
        const basePercent = Math.min(92, 8 + Math.round((index / Math.max(pendingEntries.length, 1)) * 82));
        advanceProgress(`正在生成 ${entry.item.id} ${entry.item.title}`, basePercent, 1, taskVersion);
        syncGenerationProgress(`正在生成 ${entry.item.id} ${entry.item.title}`, basePercent, 1, '批量生成');
        const content = await generateChapter(entry, {
          signal: controller.signal,
          onContent: (partial) => {
            setContentStreamText(`# ${entry.item.id} ${entry.item.title}\n\n${partial}`);
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
        completedCount += 1;
        const percent = Math.min(96, 8 + Math.round((completedCount / Math.max(pendingEntries.length, 1)) * 86));
        advanceProgress(`已完成 ${completedCount}/${pendingEntries.length} 个章节，并发 ${concurrency}`, percent, 1, taskVersion);
        syncGenerationProgress(`已完成 ${completedCount}/${pendingEntries.length} 个章节，并发 ${concurrency}`, percent, 1, '批量生成');
      };

      const workers = Array.from({ length: concurrency }, async (_, workerIndex) => {
        for (let index = workerIndex; index < pendingEntries.length; index += concurrency) {
          if (firstError) return;
          try {
            await runEntry(pendingEntries[index], index);
          } catch (error) {
            firstError = error;
            controller.abort();
            throw error;
          }
        }
      });
      await Promise.all(workers);
      await draftStorage.flushPendingSave();
      syncGenerationProgress('批量正文生成完成', 100, 2, '批量生成');
      setGenerationProgress(prev => prev ? { ...prev, status: 'success', percent: 100, detail: '批量正文生成完成' } : prev);
      completeProgress('批量正文生成完成', taskVersion);
      setSuccess('批量正文生成完成，正在执行一致性收口');
      await runConsistencyRevision(nextOutline, true);
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
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: displayDocumentBlocksPlan,
        bid_mode: normalizeBidMode(effectiveOutline.bid_mode || selectedBidMode),
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '合规审校失败');
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          advanceProgress('正在调用模型检查覆盖率、阻塞项和风险项', Math.min(92, 24 + Math.floor(raw.length / 220)), 1);
        }
      });
      advanceProgress('正在写入合规审校报告', 96, 2);
      const report = parseJsonPayload<ReviewReport>(raw, '合规审校');
      setReviewReport(report);
      setManualReviewConfirmed(false);
      completeProgress('合规审校完成', taskVersion);
      setSuccess(report.summary.ready_to_export ? '审校通过，可以导出 Word' : '审校完成，请处理阻塞项');
    } catch (error: any) {
      failProgress(error.message || '合规审校失败', undefined, taskVersion);
      setError(error.message || '合规审校失败');
    } finally {
      setBusy('');
    }
  };

  const runDocumentBlocksPlan = async () => {
    if (!effectiveOutline || !activeReport) {
      setError('请先完成标准解析并生成目录');
      return;
    }
    setBusy('blocks');
    const taskVersion = startProgress('图表素材规划', ['整理目录', '规划图表素材', '写入规划'], '正在生成图表、表格、图片和承诺书规划', 12);
    try {
      let raw = '';
      const response = await documentApi.generateDocumentBlocksPlanStream({
        outline: effectiveOutline.outline,
        analysis_report: activeReport,
        response_matrix: effectiveOutline.response_matrix || activeReport.response_matrix,
        reference_bid_style_profile: activeReferenceProfile,
        enterprise_materials: (activeReport.required_materials || []).filter(item => item.status === 'provided'),
        enterprise_material_profile: activeEnterpriseProfile || undefined,
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '图表素材规划失败');
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          advanceProgress('正在生成图表、表格、图片和承诺书规划', Math.min(92, 12 + Math.floor(raw.length / 180)), raw.length > 800 ? 1 : 0, taskVersion);
        }
      });
      const modelPlan = parseJsonPayload<Record<string, unknown>>(raw, '图表素材规划');
      const plan = normalizeDocumentBlocksPlan(modelPlan, referenceImageSlots, effectiveOutline.outline);
      setDocumentBlocksPlan(plan);
      setVisualAssetResults({});
      updateOutline({ ...effectiveOutline, document_blocks_plan: plan, asset_library: { visual_assets: [] }, reference_bid_style_profile: activeReferenceProfile });
      if (state.analysisReport) {
        updateAnalysisResults(state.projectOverview, state.techRequirements, {
          ...state.analysisReport,
          document_blocks_plan: plan,
          reference_bid_style_profile: activeReferenceProfile,
        });
      }
      completeProgress('图表素材规划完成', taskVersion);
      setSuccess('图表、表格、图片和承诺书规划已接入目录与导出链路');
    } catch (error: any) {
      failProgress(error.message || '图表素材规划失败', undefined, taskVersion);
      setError(error.message || '图表素材规划失败');
    } finally {
      setBusy('');
    }
  };

  const openAssetsWorkspace = () => {
    if (!effectiveOutline || !activeReport) {
      setError('请先完成标准解析并生成目录');
      return;
    }
    goToPage('assets');
  };

  const runVisualAssetGeneration = async (
    group: PlannedBlockGroup,
    groupIndex: number,
    block: PlannedBlock,
    blockIndex: number,
    assetKey: string,
  ) => {
    if (!effectiveOutline) {
      setError('请先生成目录');
      return;
    }
    setBusy(`asset:${assetKey}`);
    setVisualAssetResults(prev => ({
      ...prev,
      [assetKey]: { status: 'running' },
    }));
    try {
      const response = await documentApi.generateVisualAsset({
        chapter_id: group.chapter_id,
        chapter_title: group.chapter_title,
        project_name: effectiveOutline.project_name || project?.name || '',
        block,
        reference_bid_style_profile: activeReferenceProfile,
        size: '1536x1024',
      });
      const blockName = String(block.block_name || block.name || blockTypeLabel(block.block_type));
      const generatedAt = new Date().toISOString();
      const generatedAsset: GeneratedVisualAsset = {
        asset_key: assetKey,
        chapter_id: group.chapter_id,
        chapter_title: group.chapter_title,
        block_name: blockName,
        block_type: String(block.block_type || ''),
        image_url: response.data.image_url || '',
        b64_json: response.data.b64_json || '',
        prompt: response.data.prompt || '',
        caption: `图 ${group.chapter_id}-${blockIndex + 1} ${blockName}`,
        generated_at: generatedAt,
      };
      setVisualAssetResults(prev => ({
        ...prev,
        [assetKey]: {
          status: 'success',
          imageUrl: generatedAsset.image_url,
          b64Json: generatedAsset.b64_json,
          prompt: generatedAsset.prompt,
          caption: generatedAsset.caption,
          generatedAt,
        },
      }));
      const nextPlan = attachGeneratedAssetToPlan(displayDocumentBlocksPlan as Record<string, unknown>, groupIndex, blockIndex, generatedAsset, block);
      setDocumentBlocksPlan(nextPlan);
      updateOutline({
        ...effectiveOutline,
        document_blocks_plan: nextPlan,
        asset_library: { visual_assets: visualAssetsFromPlanGroups(plannedBlockGroups, { ...visualAssetResults, [assetKey]: {
          status: 'success',
          imageUrl: generatedAsset.image_url,
          b64Json: generatedAsset.b64_json,
          prompt: generatedAsset.prompt,
          caption: generatedAsset.caption,
          generatedAt,
        } }) },
      });
      setManualReviewConfirmed(false);
      setSuccess(`${block.block_name || blockTypeLabel(block.block_type)} 已生成`);
    } catch (error: any) {
      const message = apiErrorMessage(error, '图表素材生成失败');
      setVisualAssetResults(prev => ({
        ...prev,
        [assetKey]: { status: 'error', error: message },
      }));
      setError(message);
    } finally {
      setBusy('');
    }
  };

  const runConsistencyRevision = async (outlineOverride?: OutlineData, autoAfterBatch = false) => {
    const targetOutline = outlineOverride || effectiveOutline;
    if (!targetOutline || !activeReport) {
      setError('请先完成标准解析并生成目录');
      return;
    }
    setBusy('consistency');
    const taskVersion = startProgress('一致性修订', ['整理全文', '一致性检查', '生成修订报告'], '正在检查历史残留、承诺冲突和虚构风险', 12);
    try {
      const targetEntries = collectEntries(targetOutline.outline);
      const contentById = Object.fromEntries(targetEntries.map(entry => [entry.item.id, entry.item.content || '']));
      const fullBidDraft = buildExportOutline(targetOutline.outline, contentById);
      let raw = '';
      const response = await documentApi.generateConsistencyRevisionStream({
        full_bid_draft: fullBidDraft,
        analysis_report: activeReport,
        response_matrix: targetOutline.response_matrix || activeReport.response_matrix,
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: displayDocumentBlocksPlan,
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '全文一致性修订失败');
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          advanceProgress('正在检查历史残留、承诺冲突和虚构风险', Math.min(92, 12 + Math.floor(raw.length / 180)), raw.length > 800 ? 1 : 0, taskVersion);
        }
      });
      const report = parseJsonPayload<ConsistencyRevisionReport>(raw, '全文一致性修订');
      setConsistencyReport(report);
      completeProgress('一致性修订报告完成', taskVersion);
      setSuccess(report.ready_for_export
        ? (autoAfterBatch ? '批量生成完成，一致性收口通过' : '一致性检查通过')
        : `一致性检查完成，发现 ${report.issues?.length || 0} 项问题`);
    } catch (error: any) {
      failProgress(error.message || '全文一致性修订失败', undefined, taskVersion);
      setError(error.message || '全文一致性修订失败');
    } finally {
      setBusy('');
    }
  };

  const exportWord = async () => {
    if (!effectiveOutline) {
      setError('请先生成目录和正文');
      return;
    }
    if (!manualReviewConfirmed) {
      setError('导出前必须人工复核并勾选确认，模型生成结果可能存在误读、漏项、虚构和格式偏差。');
      return;
    }
    setBusy('export');
    const taskVersion = startProgress('导出 Word', ['整理章节', '写入复核清单', '生成文件'], '正在整理章节正文', 20);
    try {
      const contentById = Object.fromEntries(entries.map(entry => [entry.item.id, entry.item.content || '']));
      advanceProgress('正在生成 Word 文件', 70, 1);
      const targetExportDir = exportDirectory.trim();
      const response = await documentApi.exportWord({
        project_name: effectiveOutline.project_name || project?.name || '投标文件',
        project_overview: effectiveOutline.project_overview || state.projectOverview,
        outline: buildExportOutline(effectiveOutline.outline, contentById),
        analysis_report: activeReport,
        review_report: reviewReport,
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: displayDocumentBlocksPlan,
        asset_library: activeAssetLibrary,
        manual_review_confirmed: manualReviewConfirmed,
        export_dir: targetExportDir || undefined,
      });
      const filename = `${effectiveOutline.project_name || project?.name || '投标文件'}.docx`;
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        throw new Error(errorPayload?.detail || errorPayload?.message || '导出失败');
      }
      if (targetExportDir) {
        const payload = await response.json();
        completeProgress('Word 文件已生成', taskVersion);
        setSuccess(`Word 文件已保存：${payload.file_path || targetExportDir}`);
        return;
      }
      const blob = await response.blob();
      saveAs(blob, filename);
      completeProgress('Word 文件已生成', taskVersion);
      setSuccess(`Word 文件已生成：${filename}`);
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
      const nextConfig = toLiteLLMConfig(localConfig);
      const response = await configApi.verifyProvider(nextConfig);
      setVerifyResult(response.data);
      const modelCheck = response.data.checks.find(check => check.stage === 'models');
      if (modelCheck?.models?.length) setAvailableModels(modelCheck.models);
      if (response.data.success) {
        const saveResponse = await configApi.saveConfig(nextConfig);
        if (!saveResponse.data.success) {
          throw new Error(saveResponse.data.message || '端点验证成功，但配置保存失败');
        }
        setLocalConfig(nextConfig);
        updateConfig(nextConfig);
        setNotice({ type: 'success', text: `${response.data.message}，已保存为当前解析配置` });
        return;
      }
      setNotice({ type: 'error', text: response.data.message });
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

  const handleWorkflowAction = (item: typeof NAV_ITEMS[number]) => {
    goToPage(item.key);
  };

  const runningTaskIds = Object.values(tasks)
    .filter(task => task.status === 'running' || task.status === 'paused')
    .map(task => task.id);
  const busy = legacyBusy || runningTaskIds[0] || '';
  const isTaskRunning = (id: string) => {
    const normalizedId = normalizeTaskId(id);
    return tasks[normalizedId]?.status === 'running' || tasks[normalizedId]?.status === 'paused';
  };
  const taskCompleted = (id: string) => {
    const normalizedId = normalizeTaskId(id);
    if (tasks[normalizedId]?.status === 'success') return true;
    if (normalizedId === 'upload_text') return Boolean(state.fileContent);
    if (normalizedId === 'source_preview') return Boolean(hasSourcePreviewHtml || state.sourcePreviewPages?.length);
    if (normalizedId === 'history_match') return Boolean(hasReferenceProfile);
    if (normalizedId === 'analysis') return Boolean(activeReport);
    if (normalizedId === 'outline') return Boolean(effectiveOutline);
    if (normalizedId === 'document_blocks') return Boolean(Object.keys(documentBlocksPlan || {}).length);
    if (normalizedId === 'batch') return Boolean(effectiveOutline && entries.length > 0 && completedLeaves >= entries.length);
    if (normalizedId === 'review') return Boolean(reviewReport);
    if (normalizedId === 'consistency') return Boolean(consistencyReport);
    return false;
  };
  const taskDag = Object.entries(TASK_DAG).map(([id, dependsOn]) => ({
    id,
    label: taskLabel(id),
    dependsOn,
    status: tasks[id]?.status || (dependsOn.some(dep => !taskCompleted(dep)) ? 'blocked' : taskCompleted(id) ? 'success' : 'idle'),
    detail: tasks[id]?.detail || '',
    error: tasks[id]?.error || '',
  }));

  const workflowStatus = (key: NavKey) => {
    if (busy === 'upload' && key === 'project') return `${progress?.percent ?? 0}%`;
    if (busy === 'analysis' && key === 'analysis') return `${progress?.percent ?? 0}%`;
    if (busy === 'outline' && key === 'outline') return `${progress?.percent ?? 0}%`;
    if (busy === 'blocks' && key === 'assets') return `${progress?.percent ?? 0}%`;
    if (busy.startsWith('asset:') && key === 'assets') return '生成中';
    if (busy.startsWith('chapter') && key === 'content') return `${progress?.percent ?? 0}%`;
    if (busy === 'review' && key === 'review') return `${progress?.percent ?? 0}%`;
    if (key === 'project') return state.fileContent ? '已上传' : '选择';
    if (key === 'analysis') return state.analysisReport ? '已完成' : state.fileContent ? '可执行' : '待上传';
    if (key === 'outline') return effectiveOutline ? '已生成' : state.analysisReport ? '可执行' : '待解析';
    if (key === 'assets') return plannedBlocksCount ? `${generatedVisualCount}/${visualBlocksCount}` : effectiveOutline ? '可规划' : '待目录';
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
  const pageErrorText = notice?.type === 'error' ? notice.text : '';
  const outlineErrorText = progress?.label === '目录生成' && progress.status === 'error'
    ? (progress.error || pageErrorText || '目录生成失败')
    : currentPage === 'outline'
      ? pageErrorText
      : '';
  const analysisTaskProgressVisible = currentPage === 'analysis' && (busy === 'analysis' || progress?.label === '标准解析');
  const tenderRevealVisible = currentPage === 'analysis' && Boolean(activeReport) && !analysisTaskProgressVisible && analysisRevealPercent < 100;
  const tenderParseProgress: ProgressState | null = analysisTaskProgressVisible
    ? progress
    : tenderRevealVisible
      ? {
          label: '解析归纳',
          detail: '正在整理招标文件解析归纳',
          percent: analysisRevealPercent,
          stepIndex: Math.min(3, Math.floor(analysisRevealPercent / 34)),
          steps: ['读取解析结果', '组织评审页签', '整理原文证据', '生成归纳视图'],
          status: 'running',
        }
      : null;
  const tenderParseReady = Boolean(activeReport && activeParseTab && activeParseSection && !analysisTaskProgressVisible && !tenderRevealVisible);


  return {
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
    isTaskRunning,
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
    taskDag,
    tasks,
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
  } as const;
};

export type BidWorkspaceController = ReturnType<typeof useBidWorkspaceController>;
