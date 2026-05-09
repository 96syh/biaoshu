import { useRef, useState } from 'react';

export type ProgressState = {
  label: string;
  detail: string;
  percent: number;
  stepIndex: number;
  steps: string[];
  status: 'running' | 'success' | 'error' | 'paused' | 'stopped';
  taskId?: string;
  error?: string;
};

export const useProgressState = (analysisSteps: string[]) => {
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const progressVersionRef = useRef(0);

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
        steps: analysisSteps,
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

  return {
    advanceProgress,
    clampProgress,
    completeProgress,
    failProgress,
    progress,
    setProgress,
    startProgress,
    stopProgress,
    updateAnalysisStage,
  };
};
