/**
 * 工作台草稿存储
 *
 * 保存工作台草稿和历史记录，避免长流程生成中断后丢失进度。
 */

import type { AppState, OutlineItem } from '../types';

const DRAFT_KEY = 'huazheng:draft:v1';
const CONTENT_BY_ID_KEY = 'huazheng:contentById:v1';
const HISTORY_KEY = 'huazheng:history:v1';
const ACTIVE_HISTORY_ID_KEY = 'huazheng:activeHistoryId:v1';
const WORKSPACE_DRAFT_ENABLED = true;
const MAX_HISTORY = 12;

export type DraftState = Pick<
  AppState,
  | 'currentStep'
  | 'fileContent'
  | 'uploadedFileName'
  | 'projectOverview'
  | 'techRequirements'
  | 'analysisReport'
  | 'outlineData'
  | 'selectedChapter'
>;

export type ContentById = Record<string, string>; // 章节id -> content
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

const safeJsonParse = <T,>(raw: string | null): T | null => {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
};

const isGeneratedMediaTitle = (value?: string) =>
  /-{2,}\s*media\/image\d+\.(png|jpg|jpeg|gif|webp)\s*-{2,}/i.test((value || '').trim());

const cleanTitle = (value?: string) => {
  const title = (value || '').trim();
  if (!title || isGeneratedMediaTitle(title)) return '';
  return title;
};

const draftTitle = (draft: Partial<DraftState>) =>
  cleanTitle(draft.outlineData?.project_name)
  || cleanTitle(draft.analysisReport?.project?.name)
  || cleanTitle(draft.uploadedFileName)
  || cleanTitle(draft.analysisReport?.project?.number)
  || '未命名标书';

const draftStats = (draft: Partial<DraftState>) => {
  const outline = draft.outlineData?.outline || [];
  let completed = 0;
  let total = 0;
  let wordCount = 0;
  const walk = (items: OutlineItem[]) => {
    items.forEach((item) => {
      if (item.children?.length) {
        walk(item.children);
        return;
      }
      total += 1;
      if (item.content?.trim()) completed += 1;
      wordCount += item.content?.length || 0;
    });
  };
  walk(outline);
  return { completed, total, wordCount };
};

const createId = () => `draft-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

const getActiveHistoryId = () => {
  let id = localStorage.getItem(ACTIVE_HISTORY_ID_KEY);
  if (!id) {
    id = createId();
    localStorage.setItem(ACTIVE_HISTORY_ID_KEY, id);
  }
  return id;
};

export const draftStorage = {
  loadDraft(): Partial<DraftState> | null {
    if (!WORKSPACE_DRAFT_ENABLED) {
      return null;
    }
    return safeJsonParse<Partial<DraftState>>(localStorage.getItem(DRAFT_KEY));
  },

  saveDraft(partial: Partial<DraftState>) {
    if (!WORKSPACE_DRAFT_ENABLED) {
      return;
    }
    try {
      const prev = safeJsonParse<Partial<DraftState>>(localStorage.getItem(DRAFT_KEY)) || {};
      const next = { ...prev, ...partial };
      localStorage.setItem(DRAFT_KEY, JSON.stringify(next));
      draftStorage.upsertHistory(next);
    } catch (e) {
      console.warn('保存草稿失败（可能是 localStorage 空间不足）:', e);
    }
  },

  startNewHistory() {
    try {
      const id = createId();
      localStorage.setItem(ACTIVE_HISTORY_ID_KEY, id);
      localStorage.removeItem(DRAFT_KEY);
      localStorage.removeItem(CONTENT_BY_ID_KEY);
      return id;
    } catch {
      return createId();
    }
  },

  loadHistory(): DraftHistoryRecord[] {
    return safeJsonParse<DraftHistoryRecord[]>(localStorage.getItem(HISTORY_KEY)) || [];
  },

  upsertHistory(draft: Partial<DraftState>) {
    if (!WORKSPACE_DRAFT_ENABLED || !draft) return;
    try {
      const id = getActiveHistoryId();
      const history = draftStorage.loadHistory();
      const existing = history.find(item => item.id === id);
      const now = new Date().toISOString();
      const stats = draftStats(draft);
      const record: DraftHistoryRecord = {
        id,
        title: draftTitle(draft),
        createdAt: existing?.createdAt || now,
        updatedAt: now,
        completed: stats.completed,
        total: stats.total,
        wordCount: stats.wordCount,
        draft,
      };
      const nextHistory = [record, ...history.filter(item => item.id !== id)]
        .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
        .slice(0, MAX_HISTORY);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(nextHistory));
    } catch (e) {
      console.warn('保存历史记录失败:', e);
    }
  },

  activateHistory(id: string) {
    try {
      localStorage.setItem(ACTIVE_HISTORY_ID_KEY, id);
      const record = draftStorage.loadHistory().find(item => item.id === id);
      if (record) {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(record.draft));
      }
      return record || null;
    } catch {
      return null;
    }
  },

  clearAll() {
    // 仅清理当前应用自己的草稿键，避免误删同域下其他数据
    try {
      localStorage.removeItem(DRAFT_KEY);
      localStorage.removeItem(CONTENT_BY_ID_KEY);
      localStorage.removeItem(ACTIVE_HISTORY_ID_KEY);
    } catch (e) {
      console.warn('清空 localStorage 失败:', e);
    }
  },

  loadContentById(): ContentById {
    if (!WORKSPACE_DRAFT_ENABLED) {
      return {};
    }
    return safeJsonParse<ContentById>(localStorage.getItem(CONTENT_BY_ID_KEY)) || {};
  },

  saveContentById(contentById: ContentById) {
    if (!WORKSPACE_DRAFT_ENABLED) {
      return;
    }
    try {
      localStorage.setItem(CONTENT_BY_ID_KEY, JSON.stringify(contentById));
    } catch (e) {
      console.warn('保存正文内容失败（可能是 localStorage 空间不足）:', e);
    }
  },

  upsertChapterContent(chapterId: string, content: string) {
    if (!WORKSPACE_DRAFT_ENABLED) {
      return;
    }
    try {
      const map = draftStorage.loadContentById();
      map[chapterId] = content;
      draftStorage.saveContentById(map);
    } catch (e) {
      console.warn('保存章节内容失败:', e);
    }
  },

  /**
   * 按当前 outline 的叶子节点过滤 contentById，避免目录变更后错误回填。
   */
  filterContentByOutlineLeaves(outline: OutlineItem[]): ContentById {
    if (!WORKSPACE_DRAFT_ENABLED) {
      return {};
    }
    const map = draftStorage.loadContentById();
    const leafIds = new Set<string>();
    const walk = (items: OutlineItem[]) => {
      items.forEach((it) => {
        if (!it.children || it.children.length === 0) {
          leafIds.add(it.id);
          return;
        }
        walk(it.children);
      });
    };
    walk(outline);

    const filtered: ContentById = {};
    Object.keys(map).forEach((id) => {
      if (leafIds.has(id)) filtered[id] = map[id];
    });
    return filtered;
  },
};
