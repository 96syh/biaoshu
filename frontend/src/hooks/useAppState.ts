/**
 * 应用状态管理Hook
 */
import { useState, useCallback, useEffect } from 'react';
import { AnalysisReport, AppState, ConfigData, OutlineData, ParserInfo } from '../types';
import { draftStorage } from '../utils/draftStorage';
import { DEFAULT_PROVIDER_ID } from '../constants/providers';

const initialState: AppState = {
  currentStep: 0,
  config: {
    provider: DEFAULT_PROVIDER_ID,
    api_key: '',
    base_url: 'http://localhost:4000/v1',
    model_name: '',
    api_mode: 'chat',
  },
  fileContent: '',
  uploadedFileName: '',
  parserInfo: undefined,
  projectOverview: '',
  techRequirements: '',
  analysisReport: undefined,
  outlineData: null,
  selectedChapter: '',
};

export const useAppState = () => {
  const [state, setState] = useState<AppState>(() => {
    const draft = draftStorage.loadDraft();
    return { ...initialState, ...draft };
  });

  useEffect(() => {
    let cancelled = false;
    draftStorage.loadDraftAsync().then((draft) => {
      if (cancelled || !draft) return;
      setState(prev => ({ ...prev, ...draft }));
    });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const updateFileContent = useCallback((fileContent: string, uploadedFileName = '', parserInfo?: ParserInfo) => {
    setState(prev => {
      draftStorage.startNewHistory();
      const next = {
        ...prev,
        currentStep: 0,
        fileContent,
        uploadedFileName,
        parserInfo,
        projectOverview: '',
        techRequirements: '',
        analysisReport: undefined,
        outlineData: null,
        selectedChapter: '',
      };
      draftStorage.saveDraft({
        currentStep: 0,
        fileContent,
        uploadedFileName,
        parserInfo,
        projectOverview: '',
        techRequirements: '',
        analysisReport: undefined,
        outlineData: null,
        selectedChapter: '',
      });
      return next;
    });
  }, []);

  const updateAnalysisResults = useCallback((
    overview: string,
    requirements: string,
    analysisReport?: AnalysisReport,
  ) => {
    setState(prev => {
      const next = {
        ...prev,
        projectOverview: overview,
        techRequirements: requirements,
        analysisReport,
      };
      draftStorage.saveDraft({
        projectOverview: overview,
        techRequirements: requirements,
        analysisReport,
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

  const restoreDraft = useCallback((draft: Partial<Pick<
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
  >>) => {
    setState(prev => {
      const next = { ...prev, ...draft };
      draftStorage.saveDraft(draft);
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
    restoreDraft,
    nextStep,
    prevStep,
  };
};
