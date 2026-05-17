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

export const TaskProgress = ({ progress, onRetry }: { progress: ProgressState | null; onRetry?: () => void }) => {
  if (!progress) return null;
  const safePercent = Math.max(0, Math.min(100, Math.round(progress.percent || 0)));
  const visualPercent = progress.status === 'success' ? 100 : safePercent;
  return (
    <div className={`task-progress task-progress--${progress.status}`}>
      <div className="task-progress__head">
        <strong>{progress.detail}</strong>
        <span>{visualPercent}%</span>
      </div>
      <div className="task-progress__motion" aria-hidden="true">
        <span
          className="task-progress__dog"
          style={{ left: `${visualPercent}%` }}
        >
          🐕
        </span>
      </div>
      <div className="task-progress__bar">
        <span style={{ width: `${visualPercent}%` }} />
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
