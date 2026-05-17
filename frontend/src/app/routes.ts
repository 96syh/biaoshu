import type { ComponentType } from 'react';
import type { BidWorkspaceController } from '../features/app/useBidWorkspaceController';
import { AnalysisPage } from '../features/app/pages/AnalysisPage';
import { AssetsPage } from '../features/app/pages/AssetsPage';
import { ContentPage } from '../features/app/pages/ContentPage';
import { OutlinePage } from '../features/app/pages/OutlinePage';
import { ProjectPage } from '../features/app/pages/ProjectPage';
import { ReviewPage } from '../features/app/pages/ReviewPage';

export type WorkspaceRouteKey = 'project' | 'analysis' | 'outline' | 'assets' | 'content' | 'review';

export type WorkspacePage = ComponentType<{
  controller: BidWorkspaceController;
}>;

export interface WorkspaceRoute {
  key: WorkspaceRouteKey;
  label: string;
  description: string;
  page: WorkspacePage;
}

export const workspaceRoutes: WorkspaceRoute[] = [
  { key: 'project', label: '上传文件', description: '选择招标文件', page: ProjectPage },
  { key: 'analysis', label: '标准解析', description: '评审要点识别', page: AnalysisPage },
  { key: 'outline', label: '目录规划', description: '评分响应映射', page: OutlinePage },
  { key: 'assets', label: '图表素材', description: '样例与图片规划', page: AssetsPage },
  { key: 'content', label: '响应正文', description: '章节内容编制', page: ContentPage },
  { key: 'review', label: '审校导出', description: '合规审校与 Word 导出', page: ReviewPage },
];

export const fallbackRoute = workspaceRoutes[0];
