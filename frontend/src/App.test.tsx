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
const { parseDocumentPreviewBlocks, normalizeWordHtmlTables } = require('./features/content/DocumentPreviewNode');

test('renders the local workspace shell', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByText('本地工作台')).toBeInTheDocument();
    expect(screen.getByText('待上传文件')).toBeInTheDocument();
  });
});

test('parses generated markdown tables without gfm dependency', () => {
  const blocks = parseDocumentPreviewBlocks([
    '服务范围响应表',
    '',
    '| 序号 | 招标要求 | 响应范围 |',
    '| 1 | 服务范围 | 完全响应 |',
    '| 2 | 服务期限 | 按招标文件执行 |',
  ].join('\n'));

  expect(blocks).toEqual([
    { type: 'markdown', content: '服务范围响应表' },
    {
      type: 'table',
      rows: [
        ['序号', '招标要求', '响应范围'],
        ['1', '服务范围', '完全响应'],
        ['2', '服务期限', '按招标文件执行'],
      ],
    },
  ]);
});

test('parses inline markdown tables split from generated text', () => {
  const blocks = parseDocumentPreviewBlocks(
    '进度目标响应表 | 序号 | 进度事项 | 招标文件要求 | 本章响应目标 | 管控方式 | | 1 | 服务期限 | 自合同签订之日起至2026年12月31日 | 在服务期限内组织设计服务 | 建立任务台账 | | 2 | 初步设计 | 不超过5日 | 5日内完成 | 节点预警 |'
  );

  expect(blocks).toEqual([
    { type: 'markdown', content: '进度目标响应表' },
    {
      type: 'table',
      rows: [
        ['序号', '进度事项', '招标文件要求', '本章响应目标', '管控方式'],
        ['1', '服务期限', '自合同签订之日起至2026年12月31日', '在服务期限内组织设计服务', '建立任务台账'],
        ['2', '初步设计', '不超过5日', '5日内完成', '节点预警'],
      ],
    },
  ]);
});

test('normalizes saved html paragraphs that contain inline markdown tables', () => {
  const html = normalizeWordHtmlTables(
    '<p data-history-block-id="patch-1">进度目标响应表 | 序号 | 进度事项 | 招标文件要求 | | 1 | 服务期限 | 至2026年12月31日 |</p>'
  );

  expect(html).toContain('<p data-history-block-id="patch-1">进度目标响应表</p>');
  expect(html).toContain('<table data-history-block-id="patch-1">');
  expect(html).toContain('<th>序号</th>');
  expect(html).toContain('<td>服务期限</td>');
  expect(html).not.toContain('| 序号 |');
});
