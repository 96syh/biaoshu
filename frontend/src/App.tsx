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
  ConsistencyRevisionReport,
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
  status: 'running' | 'success' | 'error' | 'paused' | 'stopped';
  taskId?: string;
  error?: string;
};
type GenerationControlState = 'idle' | 'running' | 'paused' | 'stopped';
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

const normalizeBidMode = (mode?: unknown): BidMode => (mode === 'full_bid' ? 'full_bid' : 'technical_only');
const bidModeLabel = (mode?: unknown) => (normalizeBidMode(mode) === 'full_bid' ? '完整标' : '技术标');

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
const ANALYSIS_STEPS = ['文件解析', '条款识别', '评分项提取', '合规要求提取', '结果校验'];
const BLOCKING_REPORT_WARNING_PATTERN = /兜底|未完整返回|模型输出未完整|解析失败|超时/;
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
    throw new Error(`${label}没有返回可解析的 JSON，请重试或检查模型输出。`);
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

const parserStatus = (parserInfo?: Record<string, unknown>) => {
  const parser = String(parserInfo?.parser || '');
  const preferred = String(parserInfo?.preferred_parser || '');
  const fallbackUsed = Boolean(parserInfo?.fallback_used);
  const isMinerU = parser.toLowerCase() === 'mineru';
  if (isMinerU) {
    const detail = [
      parserInfo?.device ? `设备 ${parserInfo.device}` : '',
      parserInfo?.backend ? `后端 ${parserInfo.backend}` : '',
      parserInfo?.content_block_count ? `${parserInfo.content_block_count} 块` : '',
    ].filter(Boolean).join(' · ');
    return {
      label: 'MinerU 已使用',
      tone: 'success',
      detail: detail || '已使用 MinerU 解析为 Markdown',
    };
  }
  if (fallbackUsed && preferred === 'mineru') {
    return {
      label: 'MinerU 已降级',
      tone: 'warning',
      detail: `${parser || '内置解析器'} 已接管。${parserInfo?.fallback_reason ? `原因：${String(parserInfo.fallback_reason).slice(0, 120)}` : ''}`,
    };
  }
  if (parser) {
    return {
      label: '未使用 MinerU',
      tone: 'neutral',
      detail: `当前使用 ${parser}（${parserInfo?.format || 'plain_text'}）`,
    };
  }
  return {
    label: '解析器待确认',
    tone: 'neutral',
    detail: '上传文件后显示 MinerU 或降级解析器状态',
  };
};

const hasMinerUMarkdown = (parserInfo?: Record<string, unknown>) =>
  String(parserInfo?.parser || '').toLowerCase() === 'mineru'
  && String(parserInfo?.format || '').toLowerCase() === 'markdown'
  && !parserInfo?.fallback_used;

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

const containsOutlineItem = (item: OutlineItem, id?: string): boolean => {
  if (!id) return false;
  if (item.id === id) return true;
  return Boolean(item.children?.some(child => containsOutlineItem(child, id)));
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

const riskLevel = (item: OutlineItem) => {
  if (item.risk_ids?.length) return '高风险';
  if ((item.material_ids?.length || 0) > 1) return '中风险';
  return '低风险';
};

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
    ...raw,
    ...matchedRefs.map(ref => `${ref.location}：${ref.excerpt}`),
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
    return { ...child, children: buildEvidenceThirdLevelChildren(child, basis) };
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
          const basis = collectAutoOutlineBasis(child, report)[0];
          return basis
            ? { ...child, children: buildEvidenceThirdLevelChildren(child, basis) }
            : { ...child, children: undefined };
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
      const basis = collectAutoOutlineBasis(currentItem, report)[0];
      if (basis) {
        changed = true;
        return { ...currentItem, children: buildEvidenceThirdLevelChildren(currentItem, basis) };
      }
      changed = true;
      return { ...currentItem, children: undefined };
    }
    if (currentItem.children?.length) {
      const result = ensureOutlineThirdLevel(currentItem.children, level + 1, report);
      if (result.changed) changed = true;
      return result.changed ? { ...currentItem, children: result.items } : currentItem;
    }
    if (level !== 2) return currentItem;
    const basis = collectAutoOutlineBasis(currentItem, report)[0];
    if (!basis) return currentItem;
    changed = true;
    return { ...currentItem, children: buildEvidenceThirdLevelChildren(currentItem, basis) };
  });
  return { items: nextItems, changed };
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
  const [uploadedFileName, setUploadedFileName] = useState(state.uploadedFileName || '');
  const [referenceFileName, setReferenceFileName] = useState('');
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [busy, setBusy] = useState('');
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [streamText, setStreamText] = useState('');
  const [outlineLiveText, setOutlineLiveText] = useState('');
  const [contentStreamText, setContentStreamText] = useState('');
  const [reviewReport, setReviewReport] = useState<ReviewReport | null>(null);
  const [consistencyReport, setConsistencyReport] = useState<ConsistencyRevisionReport | null>(null);
  const [referenceProfile, setReferenceProfile] = useState<Record<string, unknown>>({});
  const [documentBlocksPlan, setDocumentBlocksPlan] = useState<Record<string, unknown>>({});
  const [verifyResult, setVerifyResult] = useState<ProviderVerifyResponse | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [localConfig, setLocalConfig] = useState<ConfigData>(state.config);
  const [selectedBidMode, setSelectedBidMode] = useState<BidMode>('full_bid');
  const [matrixExpanded, setMatrixExpanded] = useState(false);
  const [activeParseTabKey, setActiveParseTabKey] = useState<TenderParseTabKey>('basic');
  const [activeParseSectionId, setActiveParseSectionId] = useState('');
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const referenceInputRef = useRef<HTMLInputElement>(null);
  const docPreviewRef = useRef<HTMLElement>(null);
  const progressVersionRef = useRef(0);
  const generationAbortRef = useRef<AbortController | null>(null);
  const generationPausedRef = useRef(false);
  const generationStoppedRef = useRef(false);
  const analysisStoppedRef = useRef(false);
  const batchOutlineRef = useRef<OutlineData | null>(null);

  const activeReport = state.analysisReport || state.outlineData?.analysis_report || null;
  const effectiveOutline = state.outlineData;
  const outlineReferenceProfile = profileRecord(effectiveOutline?.reference_bid_style_profile);
  const reportReferenceProfile = profileRecord(activeReport?.reference_bid_style_profile);
  const rawReferenceProfile = Object.keys(outlineReferenceProfile).length
    ? outlineReferenceProfile
    : Object.keys(reportReferenceProfile).length
      ? reportReferenceProfile
      : referenceProfile;
  const activeReferenceProfile = isUsableReferenceProfile(rawReferenceProfile) ? rawReferenceProfile : EMPTY_REFERENCE_PROFILE;
  const activeReferenceRecord = profileRecord(activeReferenceProfile);
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
  const activeEnterpriseProfile = activeReport?.enterprise_material_profile || null;
  const activeResponseMatrix = effectiveOutline?.response_matrix || activeReport?.response_matrix || null;
  const responseMatrixItems = activeResponseMatrix?.items || [];
  const visibleMatrixItems = matrixExpanded ? responseMatrixItems : responseMatrixItems.slice(0, 5);
  const highRiskMatrixCount = responseMatrixItems.filter(item => item.priority === 'high' || item.blocking).length;
  const uncoveredMatrixCount = activeResponseMatrix?.uncovered_ids?.length || responseMatrixItems.filter(item => item.status !== 'covered').length;
  const tenderParseTabs = useMemo(() => buildTenderParseTabs(activeReport), [activeReport]);
  const activeParseTab = tenderParseTabs.find(tab => tab.key === activeParseTabKey) || tenderParseTabs[0];
  const activeParseSection = activeParseTab?.sections.find(section => section.id === activeParseSectionId) || activeParseTab?.sections[0];
  const activeScoringRows = useMemo(
    () => activeReport && activeParseTab ? buildScoringRows(activeReport, activeParseTab.key) : [],
    [activeReport, activeParseTab],
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
  const currentParserStatus = parserStatus(state.parserInfo);

  useEffect(() => setLocalConfig(state.config), [state.config]);

  useEffect(() => {
    if (state.uploadedFileName && state.uploadedFileName !== uploadedFileName) {
      setUploadedFileName(state.uploadedFileName);
    }
  }, [state.uploadedFileName, uploadedFileName]);

  useEffect(() => {
    let cancelled = false;
    draftStorage.loadHistoryAsync().then((records) => {
      if (!cancelled) setHistoryRecords(records);
    });
    return () => {
      cancelled = true;
    };
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
    draftStorage.loadHistoryAsync().then(setHistoryRecords);
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

  const updateAnalysisStage = (
    detail: string,
    percent: number,
    stepIndex?: number,
    status: ProgressState['status'] = 'running',
    taskId?: string,
    taskVersion = progressVersionRef.current,
  ) => {
    if (taskVersion !== progressVersionRef.current) return;
    setProgress(prev => prev
      ? {
        ...prev,
        detail,
        percent: clampProgress(percent),
        stepIndex: stepIndex ?? prev.stepIndex,
        status,
        taskId: taskId || prev.taskId,
        error: status === 'error' ? prev.error : undefined,
      }
      : {
        label: '标准解析',
        detail,
        percent: clampProgress(percent),
        stepIndex: stepIndex ?? 0,
        steps: ANALYSIS_STEPS,
        status,
        taskId,
      });
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

  const stopProgress = (detail: string, taskVersion = progressVersionRef.current) => {
    if (taskVersion !== progressVersionRef.current) return;
    progressVersionRef.current += 1;
    setProgress(prev => prev ? {
      ...prev,
      detail,
      status: 'stopped',
      error: undefined,
    } : prev);
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
    setInfo(normalizedMode === 'technical_only' ? '已切换为技术标生成，后续目录、正文和审校会按技术标模式请求模型' : '已切换为完整标生成');
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
      setReviewReport(null);
      setManualReviewConfirmed(false);
      setConsistencyReport(null);
      setDocumentBlocksPlan({});
      setActiveDocId('');
      setOutlineDraftRows([]);
      setStreamingChapterId('');
      setOutlineLiveText('');
      setContentStreamText('');
      setStreamText('');
      updateFileContent(response.data.file_content, file.name, response.data.parser_info);
      completeProgress('文件已上传，文本读取完成', taskVersion);
      setSuccess('招标文件已上传，开始进行标准解析');
    } catch (error: any) {
      failProgress(error.response?.data?.detail || error.message || '文件上传失败', 1, taskVersion);
      setError(error.response?.data?.detail || error.message || '文件上传失败');
    } finally {
      setBusy('');
    }
  };

  const clearReferenceProfileFromDraft = () => {
    setReferenceProfile({});
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
    setSuccess('成熟样例已选择，点击“去解析”后才会调用 MinerU 和模型解析');
  };

  const runReferenceAnalysis = async () => {
    if (!referenceFile) {
      setError('请先选择成熟样例文件');
      return;
    }
    setBusy('reference');
    const taskVersion = startProgress('样例解析', ['MinerU 转 Markdown', '提取写作模板'], '正在解析成熟投标文件样例', 10);
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
      setSuccess('成熟样例已通过 MinerU Markdown 接入，后续响应矩阵、目录、正文和审校会复用其模板结构');
    } catch (error: any) {
      failProgress(error.response?.data?.detail || error.message || '样例解析失败', undefined, taskVersion);
      setError(error.response?.data?.detail || error.message || '样例解析失败');
    } finally {
      setBusy('');
    }
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
    if (!hasMinerUMarkdown(state.parserInfo)) {
      setError('请先重新上传招标文件，并等待 MinerU 在上传阶段完成 Markdown 解析；旧草稿或降级解析结果不能进入标准解析。');
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
    setOutlineLiveText('准备生成目录：正在整理项目概况、评分项、风险项和材料清单。');
    setOutlineDraftRows((state.analysisReport?.bid_structure || []).slice(0, 8).map((item, index) => ({
      id: item.id || `${index + 1}`,
      title: item.title || item.purpose || `候选章节 ${index + 1}`,
      level: item.parent_id ? 1 : 0,
      status: '待模型确认',
    })));
    try {
      let raw = '';
      let lastFinalNoticeLength = 0;
      advanceProgress('正在调用模型生成目录和映射关系', 16, 1, taskVersion);
      const response = await outlineApi.generateOutlineStream({
        overview: state.projectOverview,
        requirements: state.techRequirements,
        file_content: state.fileContent,
        analysis_report: state.analysisReport,
        bid_mode: normalizeBidMode(selectedBidMode),
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: activeDocumentBlocksPlan,
      });
      await consumeSseStream(response, (payload) => {
        if (payload.error) throw new Error(payload.message || '目录生成失败');
        if (payload.preview) {
          const preview = payload.preview as { message?: string; rows?: OutlineItem[] };
          const rows = flattenOutlineDraftRows(preview.rows || []);
          setOutlineLiveText(prev => [
            prev,
            preview.message,
            rows.length ? rows.slice(0, 12).map(row => `${'  '.repeat(row.level)}${row.id} ${row.title}`).join('\n') : '',
          ].filter(Boolean).join('\n'));
          if (rows.length) setOutlineDraftRows(rows);
          return;
        }
        if (typeof payload.chunk === 'string') {
          raw += payload.chunk;
          setStreamText(raw);
          const draftRows = parseOutlineDraftRows(raw);
          if (draftRows.length) setOutlineDraftRows(draftRows);
          if (payload.chunk && raw.length - lastFinalNoticeLength >= 1024) {
            lastFinalNoticeLength = raw.length;
            setOutlineLiveText(prev => `${prev}\n正在接收最终目录 JSON：${raw.length.toLocaleString()} 字符`);
          }
          advanceProgress('正在调用模型生成目录和映射关系', Math.min(92, 16 + Math.floor(raw.length / 220)), raw.length > 1000 ? 2 : 1, taskVersion);
        }
      });
      advanceProgress('正在写入目录结构和评分映射', 96, 2, taskVersion);
      let outline: OutlineData;
      try {
        outline = parseJsonPayload<OutlineData>(raw, '目录生成');
      } catch (parseError: any) {
        outline = buildClientFallbackOutline(
          state.analysisReport as AnalysisReport,
          normalizeBidMode(selectedBidMode),
          activeReferenceProfile,
          activeDocumentBlocksPlan,
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
        document_blocks_plan: outline.document_blocks_plan || activeDocumentBlocksPlan,
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
      setOutlineLiveText(prev => `${prev}\n目录生成完成：已写入 ${countNodes(nextOutline.outline)} 个节点，可点击父级展开查看三级标题。`);
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
      document_blocks_plan: activeDocumentBlocksPlan,
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
      window.requestAnimationFrame(() => {
        document.getElementById(docSectionId(entry.item.id))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
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
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: activeDocumentBlocksPlan,
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
      const plan = parseJsonPayload<Record<string, unknown>>(raw, '图表素材规划');
      setDocumentBlocksPlan(plan);
      updateOutline({ ...effectiveOutline, document_blocks_plan: plan, reference_bid_style_profile: activeReferenceProfile });
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

  const runConsistencyRevision = async () => {
    if (!effectiveOutline || !activeReport) {
      setError('请先完成标准解析并生成目录');
      return;
    }
    setBusy('consistency');
    const taskVersion = startProgress('一致性修订', ['整理全文', '一致性检查', '生成修订报告'], '正在检查历史残留、承诺冲突和虚构风险', 12);
    try {
      const contentById = Object.fromEntries(entries.map(entry => [entry.item.id, entry.item.content || '']));
      const fullBidDraft = buildExportOutline(effectiveOutline.outline, contentById);
      let raw = '';
      const response = await documentApi.generateConsistencyRevisionStream({
        full_bid_draft: fullBidDraft,
        analysis_report: activeReport,
        response_matrix: effectiveOutline.response_matrix || activeReport.response_matrix,
        reference_bid_style_profile: activeReferenceProfile,
        document_blocks_plan: activeDocumentBlocksPlan,
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
      setSuccess(report.ready_for_export ? '一致性检查通过' : `一致性检查完成，发现 ${report.issues?.length || 0} 项问题`);
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
        document_blocks_plan: activeDocumentBlocksPlan,
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
    if (progress?.label === '标准解析' && progress.status === 'stopped') {
      if (index < progress.stepIndex) return '已完成';
      if (index === progress.stepIndex) return '已停止';
      return '待执行';
    }
    if (progress?.label === '标准解析' && progress.status === 'paused') {
      if (index < progress.stepIndex) return '已完成';
      if (index === progress.stepIndex) return '已暂停';
      return '待执行';
    }
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
            <strong>项目数据库</strong>
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
              <div className="history-empty">项目会保存到后端数据库</div>
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
              {BID_MODE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={selectedBidMode === option.value ? 'active' : ''}
                  onClick={() => handleModeChange(option.value)}
                >
                  {option.label}
                </button>
              ))}
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

                <div className="ops-panel">
                  <h2>上传成熟样例</h2>
                  <button type="button" className="upload-zone" onClick={() => referenceInputRef.current?.click()}>
                    <DocumentArrowUpIcon className="h-8 w-8" />
                    <strong>选择 PDF 或 DOCX 样例标书</strong>
                    <span>先选择文件，点击“去解析”后再用 MinerU 转 Markdown，并抽取目录、段落骨架、表格、承诺书和素材位。</span>
                  </button>
                  <input
                    ref={referenceInputRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) handleReferenceSelect(file);
                      event.target.value = '';
                    }}
                  />
                  <div className="file-pill">
                    <DocumentTextIcon className="h-5 w-5 text-sky-600" />
                    <div>
                      <strong>{referenceFileName || '未接入写作模板'}</strong>
                      <span>
                        {busy === 'reference'
                          ? '样例解析中'
                          : hasReferenceProfile
                            ? '样例写作模板已生成'
                            : referenceFile
                              ? '已选择，待解析'
                              : '可选，建议上传成熟目标文件'}
                      </span>
                    </div>
                    {hasReferenceProfile ? <CheckCircleIcon className="h-5 w-5 text-emerald-600" /> : null}
                  </div>
                  <div className="page-action-row">
                    <button type="button" className="solid-button" onClick={runReferenceAnalysis} disabled={!referenceFile || busy === 'reference'}>
                      {busy === 'reference' ? '解析中' : hasReferenceProfile ? '重新解析' : '去解析'}
                    </button>
                    <button type="button" onClick={() => referenceInputRef.current?.click()} disabled={busy === 'reference'}>重新选择</button>
                  </div>
                </div>

                <div className="ops-panel reference-profile-panel">
                  <div className="ops-panel__head">
                    <h2>成熟样例模板</h2>
                    <span className="text-link">{busy === 'reference' ? '解析中' : hasReferenceProfile ? '已生成' : '未接入'}</span>
                  </div>
                  {!hasReferenceProfile ? (
                    <div className="empty-state empty-state--compact">
                      <strong>{busy === 'reference' ? '正在解析成熟样例' : referenceFile ? '已选择样例，待解析' : '上传成熟样例后生成'}</strong>
                      <span>{referenceFile ? '点击左侧“去解析”后，这里会填充样例的目录层级、章节骨架、Word 字号字体、表格和素材位。' : '这里会展示样例的目录层级、章节骨架、Word 字号字体、表格和素材位，不再显示招标项目占位字段。'}</span>
                    </div>
                  ) : (
                    <>
                      <div className="reference-profile-summary">
                        <strong>{String(activeReferenceRecord.profile_name || referenceFileName || '成熟样例写作模板')}</strong>
                        <span>{String(activeReferenceRecord.recommended_use_case || '用于后续目录、正文、表格和审校模板复用。')}</span>
                      </div>
                      <div className="info-row"><span>样例范围</span><strong>{String(activeReferenceRecord.document_scope || 'unknown')}</strong></div>
                      {referenceProfileStats.map(([label, value]) => (
                        <div key={label} className="info-row"><span>{label}</span><strong>{value}</strong></div>
                      ))}
                      <div className="reference-style-grid">
                        <span>正文 {String(referenceWordStyle.body_font_family || DEFAULT_WORD_STYLE_PROFILE.body_font_family)} / {String(referenceWordStyle.body_font_size || DEFAULT_WORD_STYLE_PROFILE.body_font_size)}</span>
                        <span>标题 {String(referenceWordStyle.heading_font_family || DEFAULT_WORD_STYLE_PROFILE.heading_font_family)} / {String(referenceWordStyle.heading_1_size || DEFAULT_WORD_STYLE_PROFILE.heading_1_size)}</span>
                        <span>页边距 {String(referenceWordStyle.margin_top || DEFAULT_WORD_STYLE_PROFILE.margin_top)} · {String(referenceWordStyle.margin_left || DEFAULT_WORD_STYLE_PROFILE.margin_left)}</span>
                        <span>表格 {String(referenceWordStyle.table_font_size || DEFAULT_WORD_STYLE_PROFILE.table_font_size)}</span>
                      </div>
                    </>
                  )}
                </div>

                <div className="ops-panel">
                  <div className="ops-panel__head">
                    <h2>企业资料画像</h2>
                    <span>{activeReport ? `待补 ${(activeEnterpriseProfile?.missing_materials || activeReport.missing_company_materials || []).length} 项` : '待解析'}</span>
                  </div>
                  {activeReport ? (
                    (activeEnterpriseProfile?.missing_materials || activeReport.missing_company_materials || []).length ? (
                      <>
                        {activeEnterpriseProfile?.summary ? <div className="field-hint">{activeEnterpriseProfile.summary}</div> : null}
                        {(activeEnterpriseProfile?.missing_materials || activeReport.missing_company_materials || []).slice(0, 8).map(item => (
                        <div key={item.id} className="warning-row">
                          <ExclamationTriangleIcon className="h-4 w-4 text-amber-500" />
                          <span>{item.name}</span>
                          <strong>待补充</strong>
                        </div>
                        ))}
                      </>
                    ) : (
                      <div className="empty-state empty-state--compact">
                        <strong>未识别出缺失材料</strong>
                        <span>企业资料已独立成画像，仍需在审校阶段核验证据链和原件一致性。</span>
                      </div>
                    )
                  ) : (
                    <div className="empty-state empty-state--compact">
                      <strong>完成标准解析后显示</strong>
                      <span>企业资料画像会独立归纳已提供、待补和人工核验任务。</span>
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
                  <div className={`parser-status parser-status--${currentParserStatus.tone}`}>
                    <strong>{currentParserStatus.label}</strong>
                    <span>{currentParserStatus.detail}</span>
                  </div>
                  {ANALYSIS_STEPS.map((item, index) => {
                    const status = analysisStepStatus(index);
                    return (
                      <div key={item} className={`check-row check-row--${status === '失败' || status === '已停止' ? 'error' : status === '进行中' || status === '已暂停' ? 'active' : status === '已完成' ? 'done' : 'idle'}`}>
                        <CheckCircleIcon className={`h-4 w-4 ${status === '已完成' ? 'text-emerald-600' : status === '失败' || status === '已停止' ? 'text-rose-600' : status === '进行中' || status === '已暂停' ? 'text-amber-500' : 'text-slate-300'}`} />
                        <span>{item}</span>
                        <strong>
                          {(status === '进行中' || status === '已暂停') && <i className="status-pulse" />}
                          {status}
                        </strong>
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
                    <span>{activeReport ? (project?.__fallback ? '已补全关键字段' : bidModeLabel(selectedBidMode)) : '待解析'}</span>
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

                <div className="ops-panel tender-parse-panel">
                  <div className="ops-panel__head">
                    <h2>招标文件解析归纳</h2>
                    <span>{activeReport ? '按评审页签组织' : '待解析'}</span>
                  </div>
                  {activeReport && activeParseTab && activeParseSection ? (
                    <>
                      <div className="tender-parse-tabs">
                        {tenderParseTabs.map(tab => (
                          <button
                            key={tab.key}
                            type="button"
                            className={tab.key === activeParseTab.key ? 'active' : ''}
                            onClick={() => {
                              setActiveParseTabKey(tab.key);
                              setActiveParseSectionId(tab.sections[0]?.id || '');
                            }}
                          >
                            <CheckCircleIcon className="h-4 w-4" />
                            <span>{tab.label}</span>
                            <em>{tab.sections.reduce((sum, section) => sum + section.count, 0)}</em>
                          </button>
                        ))}
                      </div>
                      {isScoringParseTab(activeParseTab.key) ? (
                        <div className="tender-score-table-wrap">
                          <table className="tender-score-table">
                            <thead>
                              <tr>
                                <th>评分项</th>
                                <th>分值</th>
                                <th>得分要求</th>
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
                                        <p key={`${row.id}-subitem-${index}`}>{subitem}</p>
                                      ))}
                                      {row.evidence.length > 0 && (
                                        <div className="score-evidence">
                                          {row.evidence.slice(0, 2).map((line, index) => (
                                            <span key={`${row.id}-evidence-${index}`}>{line}</span>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              )) : (
                                <tr>
                                  <td colSpan={3}>当前解析报告未返回该类评分表，建议重新解析或人工核对评分办法章节。</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="tender-parse-workbench">
                          <nav className="tender-parse-sections" aria-label="解析章节">
                            {activeParseTab.sections.map(section => (
                              <button
                                key={section.id}
                                type="button"
                                className={section.id === activeParseSection.id ? 'active' : ''}
                                onClick={() => setActiveParseSectionId(section.id)}
                              >
                                <span>{section.title}</span>
                                <em>{section.count ? `${section.count} 项` : '待核对'}</em>
                              </button>
                            ))}
                          </nav>
                          <article className="tender-parse-detail">
                            <div className="tender-parse-detail__head">
                              <strong>{activeParseSection.title}</strong>
                              <span>{activeParseTab.label}</span>
                            </div>
                            <div className="tender-parse-content">
                              {activeParseSection.content.map((line, index) => (
                                <p key={`${activeParseSection.id}-content-${index}`}>{line}</p>
                              ))}
                            </div>
                            <div className="tender-parse-evidence">
                              <strong>原文证据</strong>
                              {activeParseSection.evidence.length ? (
                                activeParseSection.evidence.map((line, index) => (
                                  <span key={`${activeParseSection.id}-evidence-${index}`}>{line}</span>
                                ))
                              ) : (
                                <span>当前条目未返回可定位原文，建议重新解析或人工核对源文件。</span>
                              )}
                            </div>
                          </article>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="empty-state empty-state--compact">
                      <strong>等待标准解析</strong>
                      <span>完成后会按基础信息、资格审查、技术评分、废标项、投标文件要求等页签展示，并保留每项原文证据。</span>
                    </div>
                  )}
                </div>

                <div className="ops-panel response-matrix-panel">
                  <div className="ops-panel__head">
                    <h2>响应矩阵</h2>
                    <div className="panel-head-actions">
                      <span>{activeResponseMatrix ? `${responseMatrixItems.length} 项` : '待生成'}</span>
                      {activeResponseMatrix && responseMatrixItems.length > 5 && (
                        <button type="button" className="text-link" onClick={() => setMatrixExpanded(prev => !prev)}>
                          {matrixExpanded ? '收起' : '展开全部'}
                        </button>
                      )}
                    </div>
                  </div>
                  {activeResponseMatrix ? (
                    <>
                      <div className="review-metrics review-metrics--compact">
                        <Metric label="矩阵项" value={`${responseMatrixItems.length}`} tone="green" />
                        <Metric label="高风险" value={`${highRiskMatrixCount}`} tone="red" />
                        <Metric label="待覆盖" value={`${uncoveredMatrixCount}`} tone="amber" />
                      </div>
                      <div className="matrix-mini-list">
                        {visibleMatrixItems.map(item => (
                          <div key={item.id} className="matrix-mini-row">
                            <strong>{item.id}</strong>
                            <span>{item.requirement_summary || item.source_item_id}</span>
                            <em>{item.priority === 'high' || item.blocking ? '高优先级' : item.source_type}</em>
                            {matrixExpanded && (
                              <div className="matrix-mini-detail">
                                <span>策略：{item.response_strategy || '待目录阶段映射'}</span>
                                <span>目标章节：{item.target_chapter_ids?.length ? item.target_chapter_ids.join('、') : '待生成目录后确定'}</span>
                                <span>材料：{item.required_material_ids?.length ? item.required_material_ids.join('、') : '无明确材料'}</span>
                                <span>风险：{item.risk_ids?.length ? item.risk_ids.join('、') : '无关联风险'}</span>
                              </div>
                            )}
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
                      <button type="button" onClick={runDocumentBlocksPlan} disabled={!effectiveOutline || !state.analysisReport || busy === 'blocks'}>
                        {busy === 'blocks' ? '规划中' : '图表素材规划'}
                      </button>
                      <button type="button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>智能建议</button>
                      <button type="button" onClick={runOutline} disabled={!state.analysisReport || busy === 'outline'}>{effectiveOutline ? '重新生成' : '生成目录'}</button>
                    </div>
                  </div>
                  {Object.keys(activeDocumentBlocksPlan || {}).length ? (
                    <div className="field-hint">
                      文档块规划已接入：{((activeDocumentBlocksPlan as any).document_blocks || []).length || 0} 个表格/图片/承诺书块，
                      导出 Word 时会生成可替换占位。
                    </div>
                  ) : (
                    <div className="field-hint">目录生成后可单独执行图表素材规划，补齐表格、流程图、组织架构图、图片和承诺书位置。</div>
                  )}
                  {busy === 'outline' && <TaskProgress progress={progress} />}
                  {(busy === 'outline' || outlineLiveText) && (
                    <LiveStreamPanel title="目录生成过程" text={outlineLiveText || streamText} />
                  )}
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
                        />
                      ))}
                    </div>
                  ) : (
                    busy === 'outline' ? (
                      <OutlineDraftPreview rows={outlineDraftRows} raw={outlineLiveText || streamText} />
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
                  {(busy.startsWith('chapter') || busy === 'batch' || contentStreamText) && (
                    <div className="content-progress-strip">
                      <LiveStreamPanel title="正文实时生成" text={contentStreamText || '等待模型返回正文内容...'} />
                    </div>
                  )}
                  <div className="word-document-stage">
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
            )}

            {currentPage === 'review' && (
              <div className="review-panel review-panel--page">
                <div className="ops-panel__head">
                  <h2>合规审校</h2>
                  <div className="outline-actions">
                    <button type="button" className="text-link" onClick={runConsistencyRevision} disabled={!effectiveOutline || busy === 'consistency'}>
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
  report?: AnalysisReport | null;
  selectedId?: string;
  editingId?: string;
  level?: number;
  onSelect: (id: string) => void;
  onEdit: (item: OutlineItem) => void;
  onAddChild: (item: OutlineItem) => void;
  onDelete: (item: OutlineItem) => void;
}

const OutlineRows = ({ item, report, selectedId, editingId, level = 0, onSelect, onEdit, onAddChild, onDelete }: OutlineRowsProps) => {
  const hasChildren = Boolean(item.children?.length);
  const [expanded, setExpanded] = useState(level === 0);
  const active = containsOutlineItem(item, selectedId) || containsOutlineItem(item, editingId);
  const editing = item.id === editingId;
  const scoringIds = effectiveScoringIds(item, report);
  const materialCount = item.material_ids?.length || 0;
  const expectsMaterial = Boolean(
    item.enterprise_required
    || item.asset_required
    || item.expected_blocks?.some(block => ['image', 'table', 'org_chart', 'workflow_chart', 'commitment_letter', 'material_attachment'].includes(block))
  );
  const materialLabel = materialCount > 0 ? `材料 ${materialCount}` : expectsMaterial ? '待材料' : '无需材料';
  const materialTone = materialCount > 0 ? 'chip--green' : expectsMaterial ? 'chip--amber' : '';
  const materialHelp = materialCount > 0
    ? `已绑定材料 ID：${item.material_ids?.join('、')}`
    : expectsMaterial
      ? '该章节需要企业资料、表格、图片或承诺书，但当前未映射到具体材料 ID。通常是招标文件未列出明确材料编号，或解析/目录映射未匹配到材料清单。'
      : '该章节当前不依赖单独证明材料，正文会直接按招标要求展开。';
  const handleRowAction = () => {
    if (hasChildren) {
      setExpanded(prev => !prev);
      return;
    }
    onSelect(item.id);
  };
  useEffect(() => {
    if (hasChildren && active) setExpanded(true);
  }, [active, hasChildren]);
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        className={`outline-row ${active ? 'outline-row--active' : ''} ${editing ? 'outline-row--editing' : ''}`}
        style={{ paddingLeft: 18 + level * 24 }}
        onClick={handleRowAction}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            handleRowAction();
          }
        }}
      >
        <span className="outline-name">
          {hasChildren ? <ChevronRightIcon className={`outline-chevron h-3.5 w-3.5 ${expanded ? 'outline-chevron--open' : ''}`} /> : <span className="tree-branch" />}
          <strong>{item.id}　{item.title}</strong>
        </span>
        <span className="outline-row-actions">
          <button type="button" onClick={(event) => { event.stopPropagation(); onEdit(item); }}>编辑</button>
          <button type="button" onClick={(event) => { event.stopPropagation(); onAddChild(item); }}>子级</button>
          <button type="button" className="danger-text-button" onClick={(event) => { event.stopPropagation(); onDelete(item); }}>删除</button>
        </span>
        <span className="chip chip--green">评分项 {scoringIds.length || '-'}</span>
        <span className={`chip ${riskLevel(item) === '高风险' ? 'chip--red' : riskLevel(item) === '中风险' ? 'chip--amber' : 'chip--green'}`}>{riskLevel(item)}</span>
        <span className={`chip ${materialTone}`} title={materialHelp}>{materialLabel}</span>
      </div>
      {active && (
        <div className="outline-row-detail" style={{ paddingLeft: 42 + level * 24 }}>
          <span>{item.description || '该节点用于承接招标文件对应要求。'}</span>
          <em>{materialHelp}</em>
        </div>
      )}
      {expanded && item.children?.map(child => (
        <OutlineRows
          key={child.id}
          item={child}
          report={report}
          selectedId={selectedId}
          editingId={editingId}
          level={level + 1}
          onSelect={onSelect}
          onEdit={onEdit}
          onAddChild={onAddChild}
          onDelete={onDelete}
        />
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
    {raw && <pre className="stream-box">{raw}</pre>}
  </div>
);

const LiveStreamPanel = ({ title, text }: { title: string; text: string }) => (
  <div className="live-stream-panel">
    <div className="live-stream-panel__head">
      <SparklesIcon className="h-4 w-4" />
      <strong>{title}</strong>
      <span>{text.length.toLocaleString()} 字符</span>
    </div>
    <pre>{text}</pre>
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
      </button>
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
      {progress.status === 'stopped' && (
        <div className="task-progress__error">
          <strong>标准解析已停止，当前结果不会写入项目。</strong>
          {onRetry && <button type="button" onClick={onRetry}>重新解析</button>}
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
