/**
 * 工作台草稿存储
 *
 * 当前按演示需求处理：页面刷新后必须回到全新工作台，
 * 因此禁用自动恢复与持续写入，只保留显式清理旧键的能力。
 */

import type { AppState, OutlineItem } from '../types';

const DRAFT_KEY = 'huazheng:draft:v1';
const CONTENT_BY_ID_KEY = 'huazheng:contentById:v1';
const WORKSPACE_DRAFT_ENABLED = false;

export type DraftState = Pick<
  AppState,
  'currentStep' | 'fileContent' | 'projectOverview' | 'techRequirements' | 'outlineData' | 'selectedChapter'
>;

export type ContentById = Record<string, string>; // 章节id -> content

const safeJsonParse = <T,>(raw: string | null): T | null => {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
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
    } catch (e) {
      console.warn('保存草稿失败（可能是 localStorage 空间不足）:', e);
    }
  },

  clearAll() {
    // 仅清理当前应用自己的草稿键，避免误删同域下其他数据
    try {
      localStorage.removeItem(DRAFT_KEY);
      localStorage.removeItem(CONTENT_BY_ID_KEY);
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
