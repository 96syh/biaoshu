/**
 * 步骤导航条组件
 */
import React from 'react';
import { CheckIcon } from '@heroicons/react/24/solid';

interface StepBarProps {
  steps: string[];
  currentStep: number;
}

const StepBar: React.FC<StepBarProps> = ({ steps, currentStep }) => {
  const stepDescriptions = ['上传与提取', '结构与目录', '成稿与导出'];

  return (
    <div className="w-full py-6">
      <nav aria-label="Progress">
        <ol className="grid gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <li
              key={step}
              className={`step-card ${
                index < currentStep ? 'step-card--completed' : index === currentStep ? 'step-card--active' : ''
              }`}
            >
              <div className="step-card__top">
                <div className="step-card__index" aria-current={index === currentStep ? 'step' : undefined}>
                  {index < currentStep ? (
                    <CheckIcon className="h-4 w-4 text-white" aria-hidden="true" />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>
                <span className="step-card__eyebrow">Step {index + 1}</span>
              </div>

              <div className="step-card__content">
                <span className="step-card__title">{step}</span>
                <p className="step-card__desc">{stepDescriptions[index] || '工作流节点'}</p>
              </div>
            </li>
          ))}
        </ol>
      </nav>
    </div>
  );
};

export default StepBar;
