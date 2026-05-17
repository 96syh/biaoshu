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
const { DocumentPreviewNode, parseDocumentPreviewBlocks, normalizeWordHtmlTables } = require('./features/content/DocumentPreviewNode');
const { buildTableWithHeader } = require('./utils/tableHeaders');

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
    {
      type: 'table',
      captionTitle: '服务范围响应表',
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
    {
      type: 'table',
      captionTitle: '进度目标响应表',
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

  expect(html).toContain('<p class="word-table-caption">表1 进度目标响应表</p>');
  expect(html).toContain('<table data-history-block-id="patch-1">');
  expect(html).toContain('<th>序号</th>');
  expect(html).toContain('<td>服务期限</td>');
  expect(html).not.toContain('| 序号 |');
});

test('adds semantic headers when a generated table starts with body rows', () => {
  const table = buildTableWithHeader([
    ['设计服务费用小于20万元的油库项目设计服务', '完全响应，按招标人委托开展相应设计工作', '初步设计、施工图设计及相关设计成果', '服务地点为辽宁省行政区域范围内相关油库所在地'],
    ['竣工验收等后续配合', '完全响应，配合完成竣工验收阶段技术服务', '竣工验收配合、设计问题解释', '服务期限内按委托要求执行'],
  ]);

  expect(table.headerRow).toEqual(['招标范围', '投标响应', '成果或配合事项', '备注']);
  expect(table.bodyRows[0][0]).toBe('设计服务费用小于20万元的油库项目设计服务');
});

test('normalizes saved html tables so every table has a header', () => {
  const html = normalizeWordHtmlTables(
    '<table><tbody><tr><td>设计服务费用小于20万元的油库项目设计服务</td><td>完全响应，按招标人委托开展相应设计工作</td><td>初步设计、施工图设计及相关设计成果</td><td>服务地点为辽宁省行政区域范围内相关油库所在地</td></tr></tbody></table>'
  );

  expect(html).toContain('<p class="word-table-caption">表1 服务范围响应情况表</p>');
  expect(html).toContain('<thead><tr><th>招标范围</th><th>投标响应</th><th>成果或配合事项</th><th>备注</th></tr></thead>');
  expect(html).toContain('<td>设计服务费用小于20万元的油库项目设计服务</td>');
  expect(html).not.toContain('<th>设计服务费用小于20万元的油库项目设计服务</th>');
});

test('keeps only the project situation table for project personnel sections', () => {
  const blocks = parseDocumentPreviewBlocks([
    '表1 项目负责人情况表',
    '| 项目 | 目标 | 节点 | 要求 | 备注 |',
    '| --- | --- | --- | --- | --- |',
    '| 1 | 姓名 | [待补充：项目负责人姓名] | 身份证明 | [页码待编排] |',
    '',
    '表2 项目负责人业绩证明索引表',
    '| 列1 | 列2 | 列3 | 列4 | 列5 | 列6 | 列7 |',
    '| --- | --- | --- | --- | --- | --- | --- |',
    '| 1 | [待补充：项目负责人业绩项目名称] | 油库/加油站/类似项目 | 合同或委托证明日期 | 合同或委托证明 | 负责人姓名或岗位所在页及标注说明 | [页码待编排] |',
    '',
    '表3 响应情况表',
    '| 序号 | 本项目任职 | 姓名 | 职称 | 专业 | 证书名称 | 级别 | 证号 | 备注 |',
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    '| 1 | 项目负责人 | 孙艺萌 | 高级工程师 | 建筑学 | 职称证 | 高级 | 00352558 | |',
  ].join('\n'));

  const tables = blocks.filter((block: any) => block.type === 'table');
  expect(tables).toHaveLength(1);
  expect(tables[0].captionTitle).toBe('项目情况表');
  expect(tables[0].rows[1][2]).toBe('孙艺萌');
});

test('removes empty response-only tables from generated preview blocks', () => {
  const blocks = parseDocumentPreviewBlocks([
    '表1 响应情况表',
    '| 列1 | 列2 | 列3 | 列4 | 列5 | 列6 | 列7 |',
    '| --- | --- | --- | --- | --- | --- | --- |',
    '| 序号 | 货物名称 | 谈判文件 条目号 | 技术条款 | 响应技术条款 | 响应/偏离 | 说明 |',
    '| | | | | | | 全部响应，无偏离 |',
  ].join('\n'));

  expect(blocks).toEqual([]);
});

test('converts repeated single project leader table into text', () => {
  const blocks = parseDocumentPreviewBlocks([
    '表2 响应情况表',
    '| 序号 | 合同自编号 | 项目名称 | 项目负责人 | 证明文件 |',
    '| --- | --- | --- | --- | --- |',
    '| 1 | LNHZ25020 | 中石化广东东莞市南丰等3座充电站单项工程 | 孙艺萌 | 框架+单项任务书+发票 |',
    '| 2 | LNHZ25069 | 河源大兴等10座站充电桩建设项目 | 孙艺萌 | 框架+单项任务书+发票 |',
  ].join('\n'));

  expect(blocks).toHaveLength(1);
  expect(blocks[0]).toEqual({
    type: 'markdown',
    content: expect.stringContaining('拟派项目负责人为孙艺萌'),
  });
});

test('numbers preview tables continuously across child sections', () => {
  const outline = {
    id: '1',
    title: '服务方案',
    description: '',
    children: [
      {
        id: '1.1',
        title: '服务范围',
        description: '',
        content: [
          '表1 服务范围响应情况表',
          '| 招标范围 | 投标响应 | 成果或配合事项 | 备注 |',
          '| --- | --- | --- | --- |',
          '| 服务范围 | 完全响应 | 设计成果 | 按招标文件执行 |',
        ].join('\n'),
      },
      {
        id: '1.2',
        title: '进度安排',
        description: '',
        content: [
          '表1 进度目标响应表',
          '| 项目 | 目标 | 节点 | 要求 | 备注 |',
          '| --- | --- | --- | --- | --- |',
          '| 服务期限 | 按期完成 | 阶段检查 | 建立台账 | 无 |',
        ].join('\n'),
      },
    ],
  };

  render(<DocumentPreviewNode item={outline} level={1} onSelect={() => undefined} />);

  expect(screen.getByText('表1 服务范围响应情况表')).toBeInTheDocument();
  expect(screen.getByText('表2 进度目标响应表')).toBeInTheDocument();
});
