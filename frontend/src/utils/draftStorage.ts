/**
 * 项目草稿存储
 *
 * 主存储已迁移到后端 SQLite 项目数据库。浏览器 localStorage / IndexedDB
 * 只在启动时清理旧缓存，不再保存业务草稿。
 */

import type { AppState, OutlineItem } from '../types';
import { projectApi } from '../services/api';
import type { ProjectRecordResponse } from '../services/api';

const LEGACY_DRAFT_KEY = 'huazheng:draft:v1';
const LEGACY_CONTENT_BY_ID_KEY = 'huazheng:contentById:v1';
const LEGACY_HISTORY_KEY = 'huazheng:history:v1';
const LEGACY_ACTIVE_HISTORY_ID_KEY = 'huazheng:activeHistoryId:v1';
const LEGACY_INDEXED_DB_NAME = 'huazheng-workspace-drafts';

export type DraftState = Pick<
  AppState,
  | 'currentStep'
  | 'fileContent'
  | 'uploadedFileName'
  | 'parserInfo'
  | 'projectOverview'
  | 'techRequirements'
  | 'analysisReport'
  | 'outlineData'
  | 'selectedChapter'
>;

export type ContentById = Record<string, string>;
export type DraftHistoryRecord = {
  id: string;
  title: string;
  updatedAt: string;
  createdAt: string;
  completed: number;
  total: number;
  wordCount: number;
  draft: Partial<DraftState>;
};

let activeProjectId = '';
let activeDraft: Partial<DraftState> = {};
let saveQueue: Promise<unknown> = Promise.resolve();
let legacyCleaned = false;

const toDraft = (value: unknown): Partial<DraftState> => {
  if (!value || typeof value !== 'object') return {};
  return value as Partial<DraftState>;
};

const toHistoryRecord = (record: ProjectRecordResponse): DraftHistoryRecord => ({
  id: record.id,
  title: record.title,
  createdAt: record.createdAt,
  updatedAt: record.updatedAt,
  completed: record.completed,
  total: record.total,
  wordCount: record.wordCount,
  draft: toDraft(record.draft),
});

const createClientProjectId = () => `project-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

const clearLegacyBrowserCache = async () => {
  if (legacyCleaned || typeof window === 'undefined') return;
  legacyCleaned = true;

  try {
    window.localStorage.removeItem(LEGACY_DRAFT_KEY);
    window.localStorage.removeItem(LEGACY_CONTENT_BY_ID_KEY);
    window.localStorage.removeItem(LEGACY_HISTORY_KEY);
    window.localStorage.removeItem(LEGACY_ACTIVE_HISTORY_ID_KEY);
  } catch (error) {
    console.warn('清理旧 localStorage 缓存失败:', error);
  }

  try {
    if (window.indexedDB?.deleteDatabase) {
      window.indexedDB.deleteDatabase(LEGACY_INDEXED_DB_NAME);
    }
  } catch (error) {
    console.warn('清理旧 IndexedDB 缓存失败:', error);
  }
};

const saveActiveDraft = (draft: Partial<DraftState>) => {
  const projectId = activeProjectId || createClientProjectId();
  activeProjectId = projectId;
  saveQueue = saveQueue
    .catch(() => undefined)
    .then(async () => {
      try {
        const response = await projectApi.saveActiveProject(draft as Record<string, unknown>, projectId, true);
        const project = response.data.project;
        if (project) {
          activeProjectId = project.id;
          activeDraft = toDraft(project.draft);
        }
      } catch (error) {
        console.warn('保存项目草稿到后端数据库失败:', error);
      }
    });
};

const walkOutlineLeaves = (outline: OutlineItem[] = [], visit: (item: OutlineItem) => void) => {
  outline.forEach((item) => {
    if (item.children?.length) {
      walkOutlineLeaves(item.children, visit);
      return;
    }
    visit(item);
  });
};

const buildContentMapFromDraft = (draft: Partial<DraftState>): ContentById => {
  const map: ContentById = {};
  walkOutlineLeaves(draft.outlineData?.outline || [], (item) => {
    if (item.content) map[item.id] = item.content;
  });
  return map;
};

const updateOutlineContent = (
  outline: OutlineItem[] = [],
  contentById: ContentById,
): OutlineItem[] => outline.map(item => ({
  ...item,
  content: contentById[item.id] ?? item.content,
  children: item.children?.length ? updateOutlineContent(item.children, contentById) : item.children,
}));

export const draftStorage = {
  loadDraft(): Partial<DraftState> | null {
    return Object.keys(activeDraft).length ? activeDraft : null;
  },

  async loadDraftAsync(): Promise<Partial<DraftState> | null> {
    await clearLegacyBrowserCache();
    try {
      const response = await projectApi.getActiveProject();
      const project = response.data.project;
      if (!project) {
        activeProjectId = '';
        activeDraft = {};
        return null;
      }
      activeProjectId = project.id;
      activeDraft = toDraft(project.draft);
      return activeDraft;
    } catch (error) {
      console.warn('读取项目数据库草稿失败:', error);
      return null;
    }
  },

  saveDraft(partial: Partial<DraftState>) {
    activeDraft = { ...activeDraft, ...partial };
    saveActiveDraft(activeDraft);
  },

  startNewHistory() {
    activeProjectId = createClientProjectId();
    activeDraft = {};
    void clearLegacyBrowserCache();
    return activeProjectId;
  },

  loadHistory(): DraftHistoryRecord[] {
    return [];
  },

  async loadHistoryAsync(): Promise<DraftHistoryRecord[]> {
    await clearLegacyBrowserCache();
    try {
      const response = await projectApi.listProjects();
      return (response.data.projects || []).map(toHistoryRecord);
    } catch (error) {
      console.warn('读取项目列表失败:', error);
      return [];
    }
  },

  upsertHistory(draft: Partial<DraftState>) {
    activeDraft = { ...activeDraft, ...draft };
    saveActiveDraft(activeDraft);
  },

  activateHistory(id: string) {
    activeProjectId = id;
    return null;
  },

  async activateHistoryAsync(id: string) {
    await clearLegacyBrowserCache();
    try {
      const response = await projectApi.activateProject(id);
      const project = response.data.project;
      if (!project) return null;
      activeProjectId = project.id;
      activeDraft = toDraft(project.draft);
      return toHistoryRecord(project);
    } catch (error) {
      console.warn('切换项目失败:', error);
      return null;
    }
  },

  clearAll() {
    activeDraft = {};
    activeProjectId = '';
    void clearLegacyBrowserCache();
  },

  loadContentById(): ContentById {
    return buildContentMapFromDraft(activeDraft);
  },

  async loadContentByIdAsync(): Promise<ContentById> {
    return buildContentMapFromDraft(activeDraft);
  },

  saveContentById(contentById: ContentById) {
    if (!activeDraft.outlineData?.outline) return;
    const nextOutline = updateOutlineContent(activeDraft.outlineData.outline, contentById);
    activeDraft = {
      ...activeDraft,
      outlineData: {
        ...activeDraft.outlineData,
        outline: nextOutline,
      },
    };
    saveActiveDraft(activeDraft);
  },

  upsertChapterContent(chapterId: string, content: string) {
    const map = buildContentMapFromDraft(activeDraft);
    map[chapterId] = content;
    draftStorage.saveContentById(map);
  },

  filterContentByOutlineLeaves(outline: OutlineItem[]): ContentById {
    const source = buildContentMapFromDraft(activeDraft);
    const filtered: ContentById = {};
    walkOutlineLeaves(outline, (item) => {
      if (source[item.id]) filtered[item.id] = source[item.id];
    });
    return filtered;
  },
};
