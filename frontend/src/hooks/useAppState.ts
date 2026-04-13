/**
 * 应用状态管理Hook
 */
import { useState, useCallback } from 'react';
import { AppState, ConfigData, OutlineData } from '../types';
import { draftStorage } from '../utils/draftStorage';
import { DEFAULT_PROVIDER_ID } from '../constants/providers';

const initialState: AppState = {
  currentStep: 0,
  config: {
    provider: DEFAULT_PROVIDER_ID,
    api_key: '',
    base_url: '',
    model_name: 'gpt-4.1-mini',
  },
  fileContent: '',
  projectOverview: '',
  techRequirements: '',
  outlineData: null,
  selectedChapter: '',
};

export const useAppState = () => {
  const [state, setState] = useState<AppState>(() => {
    // 按当前需求：页面刷新后回到全新工作台，不自动恢复旧草稿
    draftStorage.clearAll();
    return { ...initialState };
  });

  const updateConfig = useCallback((config: ConfigData) => {
    setState(prev => ({ ...prev, config }));
  }, []);

  const updateStep = useCallback((step: number) => {
    setState(prev => {
      const next = { ...prev, currentStep: step };
      draftStorage.saveDraft({ currentStep: step });
      return next;
    });
  }, []);

  const updateFileContent = useCallback((fileContent: string) => {
    setState(prev => {
      const next = { ...prev, fileContent };
      draftStorage.saveDraft({ fileContent });
      return next;
    });
  }, []);

  const updateAnalysisResults = useCallback((overview: string, requirements: string) => {
    setState(prev => {
      const next = {
        ...prev,
        projectOverview: overview,
        techRequirements: requirements,
      };
      draftStorage.saveDraft({
        projectOverview: overview,
        techRequirements: requirements,
      });
      return next;
    });
  }, []);

  const updateOutline = useCallback((outlineData: OutlineData) => {
    setState(prev => {
      const next = { ...prev, outlineData };
      draftStorage.saveDraft({ outlineData });
      return next;
    });
  }, []);

  const updateSelectedChapter = useCallback((chapterId: string) => {
    setState(prev => {
      const next = { ...prev, selectedChapter: chapterId };
      draftStorage.saveDraft({ selectedChapter: chapterId });
      return next;
    });
  }, []);

  const nextStep = useCallback(() => {
    setState(prev => {
      const nextStepValue = Math.min(prev.currentStep + 1, 2);
      const next = { ...prev, currentStep: nextStepValue };
      draftStorage.saveDraft({ currentStep: nextStepValue });
      return next;
    });
  }, []);

  const prevStep = useCallback(() => {
    setState(prev => {
      const prevStepValue = Math.max(prev.currentStep - 1, 0);
      const next = { ...prev, currentStep: prevStepValue };
      draftStorage.saveDraft({ currentStep: prevStepValue });
      return next;
    });
  }, []);

  return {
    state,
    updateConfig,
    updateStep,
    updateFileContent,
    updateAnalysisResults,
    updateOutline,
    updateSelectedChapter,
    nextStep,
    prevStep,
  };
};
