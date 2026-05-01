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
  GeneratedSummary,
  MissingCompanyMaterial,
  OutlineData,
  OutlineItem,
  RequiredMaterial,
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
  old_outline?: string;
  parser_info?: Record<string, unknown>;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
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

export interface AnalysisRequest {
  file_content: string;
  analysis_type: 'overview' | 'requirements';
}

export interface AnalysisReportRequest {
  file_content: string;
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
