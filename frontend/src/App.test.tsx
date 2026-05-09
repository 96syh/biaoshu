import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-markdown', () => {
  const React = require('react');
  return {
    __esModule: true,
    default: ({ children }: any) => React.createElement(React.Fragment, null, children),
  };
});

jest.mock('./services/api', () => {
  const config = {
    provider: 'litellm',
    api_key: '',
    base_url: 'http://localhost:4000/v1',
    model_name: '',
    api_mode: 'chat',
  };
  const emptyProjectResponse = { data: { success: true, message: 'ok', project: null, projects: [] } };
  return {
    __esModule: true,
    configApi: {
      loadConfig: () => Promise.resolve({ data: config }),
      saveConfig: () => Promise.resolve({ data: { success: true, message: 'ok' } }),
      getModels: () => Promise.resolve({ data: { success: true, models: [], message: 'ok' } }),
      verifyProvider: () => Promise.resolve({ data: { success: false, message: '', checks: [] } }),
      getModelRuntime: () => Promise.resolve({ data: { success: true, active: false, active_count: 0, active_requests: [], last_event: {} } }),
    },
    projectApi: {
      listProjects: () => Promise.resolve(emptyProjectResponse),
      getActiveProject: () => Promise.resolve(emptyProjectResponse),
      createProject: () => Promise.resolve(emptyProjectResponse),
      saveActiveProject: () => Promise.resolve(emptyProjectResponse),
      activateProject: () => Promise.resolve(emptyProjectResponse),
      deleteProject: () => Promise.resolve({ data: { success: true, message: 'ok' } }),
    },
    documentApi: {
      uploadFile: () => Promise.reject(new Error('not mocked')),
      uploadReferenceFile: () => Promise.reject(new Error('not mocked')),
      exportDocument: () => Promise.reject(new Error('not mocked')),
    },
    outlineApi: {
      generateOutlineStream: () => Promise.reject(new Error('not mocked')),
    },
    contentApi: {
      generateChapterContentStream: () => Promise.reject(new Error('not mocked')),
    },
  };
});

const App = require('./App').default;

test('renders the local workspace shell', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByText('本地工作台')).toBeInTheDocument();
    expect(screen.getByText('待上传文件')).toBeInTheDocument();
  });
});
