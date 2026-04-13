/**
 * 主应用组件
 */
import React from 'react';
import { useAppState } from './hooks/useAppState';
import ConfigPanel from './components/ConfigPanel';
import StepBar from './components/StepBar';
import DocumentAnalysis from './pages/DocumentAnalysis';
import OutlineEdit from './pages/OutlineEdit';
import ContentEdit from './pages/ContentEdit';
import { getProviderPreset } from './constants/providers';

function App() {
  const {
    state,
    updateConfig,
    updateStep,
    updateFileContent,
    updateAnalysisResults,
    updateOutline,
    updateSelectedChapter,
    nextStep,
    prevStep,
  } = useAppState();

  const steps = ['标书解析', '目录编辑', '正文编辑'];
  const activeProvider = getProviderPreset(state.config.provider);

  const renderCurrentPage = () => {
    switch (state.currentStep) {
      case 0:
        return (
          <DocumentAnalysis
            fileContent={state.fileContent}
            projectOverview={state.projectOverview}
            techRequirements={state.techRequirements}
            onFileUpload={updateFileContent}
            onAnalysisComplete={updateAnalysisResults}
          />
        );
      case 1:
        return (
          <OutlineEdit
            projectOverview={state.projectOverview}
            techRequirements={state.techRequirements}
            outlineData={state.outlineData}
            onOutlineGenerated={updateOutline}
          />
        );
      case 2:
        return (
          <ContentEdit
            outlineData={state.outlineData}
            selectedChapter={state.selectedChapter}
            onChapterSelect={updateSelectedChapter}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      <div className="app-shell__glow app-shell__glow--one" />
      <div className="app-shell__glow app-shell__glow--two" />
      {/* 左侧配置面板 */}
      <ConfigPanel
        config={state.config}
        onConfigChange={updateConfig}
      />

      {/* 主内容区域 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 步骤导航 */}
        <div className="shell-header">
          <div className="shell-header__top">
            <div>
              <p className="shell-header__eyebrow">Proposal Operations Console</p>
              <h1 className="shell-header__title">多模型标书生成工作流</h1>
              <p className="shell-header__summary">
                上传资料、生成目录、批量输出正文。用一套控制台完成模型选择、招标解析与客户级展示。
              </p>
            </div>

            <div className="shell-header__meta">
              <div className="shell-chip">
                <span className="shell-chip__label">供应商</span>
                <span className="shell-chip__value">{activeProvider.label}</span>
              </div>
              <div className="shell-chip">
                <span className="shell-chip__label">模型</span>
                <span className="shell-chip__value">{state.config.model_name || '未设置'}</span>
              </div>
              <a
                href="/client-demo.html"
                target="_blank"
                rel="noopener noreferrer"
                className="secondary-button"
              >
                打开客户演示页
              </a>
            </div>
          </div>

          <StepBar steps={steps} currentStep={state.currentStep} />
        </div>

        {/* 页面内容 */}
        <div id="app-main-scroll" className="app-main-scroll">
          {renderCurrentPage()}
        </div>

        {/* 底部导航按钮 */}
        <div className="shell-footer">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => updateStep(0)}
                disabled={state.currentStep === 0}
                className="secondary-button"
              >
                首页
              </button>

              <button
                onClick={prevStep}
                disabled={state.currentStep === 0}
                className="secondary-button"
              >
                上一步
              </button>
            </div>

            <button
              onClick={nextStep}
              disabled={state.currentStep === steps.length - 1}
              className="primary-button"
            >
              下一步
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
