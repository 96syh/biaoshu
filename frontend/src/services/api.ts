/**
 * API服务
 */
import axios from 'axios';
import type {
  AnalysisReport,
  BidMode,
  ComplianceReviewRequest,
  ConsistencyRevisionRequest,
  DocumentBlocksPlanRequest,
  EnterpriseMaterialProfile,
  GeneratedSummary,
  MissingCompanyMaterial,
  OutlineData,
  OutlineItem,
  RequiredMaterial,
  VisualAssetGenerationRequest,
  VisualAssetGenerationResponse,
} from '../types';

export type {
  AnalysisReport,
  BidMode,
  ComplianceReviewRequest,
  GeneratedSummary,
  MissingCompanyMaterial,
  ReviewReport,
} from '../types';

const getDefaultApiBaseUrl = () => {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }

  if (typeof window !== 'undefined' && window.location.origin) {
    const isLocalDevHost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
    if (isLocalDevHost && ['3000', '3001'].includes(window.location.port)) {
      return 'http://127.0.0.1:8000';
    }

    if (isLocalDevHost && window.location.port === '3010') {
      return 'http://127.0.0.1:8010';
    }

    return window.location.origin;
  }

  return 'http://localhost:8000';
};

const API_BASE_URL = getDefaultApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 调整为60秒
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API请求错误:', error);
    return Promise.reject(error);
  }
);

export interface ConfigData {
  provider: string;
  api_key: string;
  base_url?: string;
  model_name: string;
  api_mode?: 'auto' | 'chat' | 'responses' | 'anthropic';
}

export interface FileUploadResponse {
  success: boolean;
  message: string;
  file_content?: string;
  source_preview_html?: string;
  old_outline?: string;
  parser_info?: Record<string, unknown>;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
}

export interface HistoryReferenceMatchRequest {
  file_content: string;
  analysis_report?: AnalysisReport | Record<string, unknown>;
  limit?: number;
  use_llm?: boolean;
}

export interface HistoryReferenceMatchResponse {
  success: boolean;
  message: string;
  matched_case?: Record<string, any>;
  candidates?: Record<string, any>[];
  llm_reason?: string;
  reference_bid_style_profile?: Record<string, unknown>;
}

export interface HistoryRequirementEvidence {
  project_id?: string;
  project_title?: string;
  result?: string;
  primary_domain?: string;
  primary_subdomain?: string;
  document_id?: string;
  file_name?: string;
  document_path?: string;
  pageindex_tree_path?: string;
  snippet?: string;
  matched_term?: string;
  is_winning_case?: boolean;
}

export interface HistoryRequirementCheck {
  item_id: string;
  category: 'qualification' | 'scoring' | string;
  category_label: string;
  label: string;
  score?: string;
  requirement?: string;
  search_terms?: string[];
  satisfied: boolean;
  confidence: number;
  reason: string;
  evidence: HistoryRequirementEvidence[];
}

export interface HistoryRequirementCheckRequest {
  analysis_report: AnalysisReport | Record<string, unknown>;
  limit_per_item?: number;
  use_llm?: boolean;
}

export interface HistoryRequirementCheckResponse {
  success: boolean;
  message: string;
  summary: {
    total: number;
    satisfied: number;
    not_found: number;
  };
  checks: HistoryRequirementCheck[];
  llm_reason?: string;
}

export interface ProviderCheckItem {
  stage: string;
  success: boolean;
  detail: string;
  url?: string;
  http_status?: number;
  model_name?: string;
  models?: string[];
  sample?: string;
}

export interface ProviderVerifyResponse {
  success: boolean;
  message: string;
  provider: string;
  normalized_base_url: string;
  resolved_base_url: string;
  base_url_candidates: string[];
  model_name: string;
  api_mode: 'auto' | 'chat' | 'responses' | 'anthropic';
  checks: ProviderCheckItem[];
}

export interface ProjectRecordResponse {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  completed: number;
  total: number;
  wordCount: number;
  draft: Record<string, unknown>;
}

export interface ProjectResponse {
  success: boolean;
  message: string;
  project?: ProjectRecordResponse | null;
  projects?: ProjectRecordResponse[];
}

export interface AnalysisRequest {
  file_content: string;
  analysis_type: 'overview' | 'requirements';
}

export interface AnalysisReportRequest {
  file_content: string;
  config?: ConfigData;
}

export type AnalysisTaskAction = 'pause' | 'resume' | 'stop';

export interface AnalysisTaskControlResponse {
  success: boolean;
  message: string;
  task_id: string;
  status: 'running' | 'paused' | 'stopped' | string;
}

export interface OutlineRequest {
  overview: string;
  requirements: string;
  file_content?: string;
  uploaded_expand?: boolean;
  old_outline?: string;
  old_document?: string;
  analysis_report?: AnalysisReport;
  bid_mode?: BidMode;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
}

export interface ContentGenerationRequest {
  outline: OutlineData;
  project_overview: string;
}

export interface ChapterContentRequest {
  chapter: OutlineItem;
  parent_chapters?: OutlineItem[];
  sibling_chapters?: OutlineItem[];
  project_overview: string;
  analysis_report?: AnalysisReport;
  response_matrix?: AnalysisReport['response_matrix'];
  bid_mode?: BidMode;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
  asset_library?: Record<string, unknown>;
  generated_summaries?: GeneratedSummary[];
  enterprise_materials?: RequiredMaterial[];
  enterprise_material_profile?: EnterpriseMaterialProfile;
  missing_materials?: MissingCompanyMaterial[];
}

// 配置相关API
export const configApi = {
  // 保存配置
  saveConfig: (config: ConfigData) =>
    api.post('/api/config/save', config),

  // 加载配置
  loadConfig: () =>
    api.get('/api/config/load'),

  // 获取可用模型
  getModels: (config: ConfigData) =>
    api.post('/api/config/models', config),

  // 验证当前模型端点
  verifyProvider: (config: ConfigData) =>
    api.post<ProviderVerifyResponse>('/api/config/verify', config),
};

// 项目数据库 API
export const projectApi = {
  listProjects: () =>
    api.get<ProjectResponse>('/api/projects'),

  getActiveProject: () =>
    api.get<ProjectResponse>('/api/projects/active'),

  createProject: (draft: Record<string, unknown> = {}) =>
    api.post<ProjectResponse>('/api/projects', { draft }),

  saveActiveProject: (draft: Record<string, unknown>, projectId?: string, activate = true) =>
    api.put<ProjectResponse>('/api/projects/active', {
      project_id: projectId,
      draft,
      activate,
    }),

  activateProject: (projectId: string) =>
    api.post<ProjectResponse>(`/api/projects/${projectId}/activate`),

  deleteProject: (projectId: string) =>
    api.delete<ProjectResponse>(`/api/projects/${projectId}`),
};

// 文档相关API
export const documentApi = {
  // 上传文件
  uploadFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/document/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  // 上传成熟投标文件样例并生成风格剖面
  uploadReferenceStyleFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/document/reference-style-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000,
    });
  },

  // 根据当前招标文件自动匹配历史案例库，并生成成熟样例剖面
  matchHistoryReference: (data: HistoryReferenceMatchRequest) =>
    api.post<HistoryReferenceMatchResponse>('/api/history-cases/match-reference', data, {
      timeout: 420000,
    }),

  // 用历史中标案例库核对标准解析中的评分项和资质项
  checkHistoryRequirements: (data: HistoryRequirementCheckRequest) =>
    api.post<HistoryRequirementCheckResponse>('/api/history-cases/check-requirements', data, {
      timeout: 420000,
    }),


  // 流式分析文档
  analyzeDocumentStream: (data: AnalysisRequest) =>
    fetch(`${API_BASE_URL}/api/document/analyze-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 流式生成结构化标准解析报告
  analyzeReportStream: (data: AnalysisReportRequest) =>
    fetch(`${API_BASE_URL}/api/document/analyze-report-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 控制结构化标准解析任务
  controlAnalysisTask: (taskId: string, action: AnalysisTaskAction) =>
    api.post<AnalysisTaskControlResponse>(`/api/document/analysis-task/${taskId}/control`, { action }),

  // 流式执行导出前合规审校
  reviewComplianceStream: (data: ComplianceReviewRequest) =>
    fetch(`${API_BASE_URL}/api/document/review-compliance-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 流式生成图表与素材规划
  generateDocumentBlocksPlanStream: (data: DocumentBlocksPlanRequest) =>
    fetch(`${API_BASE_URL}/api/document/document-blocks-plan-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 生成单个图表素材图片
  generateVisualAsset: (data: VisualAssetGenerationRequest) =>
    api.post<VisualAssetGenerationResponse>('/api/document/generate-visual-asset', data, {
      timeout: 240000,
    }),

  // 流式生成全文一致性修订报告
  generateConsistencyRevisionStream: (data: ConsistencyRevisionRequest) =>
    fetch(`${API_BASE_URL}/api/document/consistency-revision-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 导出Word文档
  exportWord: (data: any) =>
    fetch(`${API_BASE_URL}/api/document/export-word`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),
};

// 目录相关API
export const outlineApi = {
  // 生成目录
  generateOutline: (data: OutlineRequest) =>
    api.post('/api/outline/generate', data),

  // 流式生成目录
  generateOutlineStream: (data: OutlineRequest) =>
    fetch(`${API_BASE_URL}/api/outline/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

};

// 内容相关API
export const contentApi = {
  // 生成单章节内容
  generateChapterContent: (data: ChapterContentRequest) =>
    api.post('/api/content/generate-chapter', data),

  // 流式生成单章节内容
  generateChapterContentStream: (data: ChapterContentRequest, signal?: AbortSignal) =>
    fetch(`${API_BASE_URL}/api/content/generate-chapter-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
      signal,
    }),
};

// 方案扩写相关API
export const expandApi = {
  // 上传方案扩写文件
  uploadExpandFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/expand/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 文件上传专用超时设置：5分钟
    });
  },
};

export default api;
