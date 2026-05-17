export type TableWithHeader = {
  headerRow: string[];
  bodyRows: string[][];
};

const SERVICE_SCOPE_HEADERS = ['招标范围', '投标响应', '成果或配合事项', '备注'];
const QUALITY_HEADERS = ['成果或服务事项', '质量目标', '检查节点', '校审要求', '闭环方式'];

const EXACT_HEADER_CELLS = new Set([
  '序号',
  '编号',
  '阶段',
  '类别',
  '层级',
  '项目',
  '项目名称',
  '合同自编号',
  '本项目任职',
  '任职',
  '名称',
  '姓名',
  '项目负责人',
  '身份证号',
  '招标范围',
  '招标要求',
  '招标文件要求',
  '谈判文件条目号',
  '技术条款',
  '响应技术条款',
  '投标响应',
  '响应',
  '响应/偏离',
  '响应内容',
  '本章响应目标',
  '成果',
  '成果或配合事项',
  '成果或服务事项',
  '配合事项',
  '服务内容',
  '服务范围',
  '工作内容',
  '进度事项',
  '管控方式',
  '备注',
  '时限',
  '完成时限',
  '质量目标',
  '检查节点',
  '校审要求',
  '闭环方式',
  '人员',
  '岗位',
  '职责',
  '职称',
  '专业',
  '证书名称',
  '证明文件',
  '级别',
  '证号',
  '注册证书编号',
  '国家级注册资格',
  '社保月份',
  '同类工程设计经验年限',
  '文件',
  '资料',
  '页码',
  '条款',
  '要求',
  '目标',
  '方式',
  '节点',
  '说明',
]);

const compactCell = (value: string) => value.replace(/\s+/g, '').trim();
const ensureTableSuffix = (value: string) => value.endsWith('表') ? value : `${value}表`;

const isGenericColumnHeaderRow = (row: string[]) => {
  const cells = row.map(compactCell).filter(Boolean);
  return cells.length >= 2 && cells.every(cell => /^列\d+$/.test(cell));
};

const isBoilerplateResponseCell = (value: string) => {
  const cell = compactCell(value);
  if (!cell) return true;
  if (/^(?:全部|完全)响应[，,、；;]?无偏离$/.test(cell)) return true;
  return /^(?:全部响应|完全响应|无偏离|不偏离|无|\/|—|-|详见投标文件|按招标文件要求执行)$/.test(cell);
};

export const formatTableCaption = (tableIndex: number, title: string) => `表${tableIndex} ${ensureTableSuffix(title)}`;

const isHeaderCell = (value: string) => {
  const cell = compactCell(value);
  if (!cell || cell.length > 18) return false;
  if (EXACT_HEADER_CELLS.has(cell)) return true;
  return /(?:范围|响应|成果|事项|备注|阶段|时限|目标|方式|节点|要求|职责|人员|负责人|专业|工作|类型|项目|内容|名称|文件|条款|偏离|说明)$/.test(cell);
};

export const isLikelySemanticTableHeader = (row: string[]) => {
  const nonEmptyCells = row.map(compactCell).filter(Boolean);
  if (nonEmptyCells.length < 2) return false;

  const headerLikeCount = nonEmptyCells.filter(isHeaderCell).length;
  const threshold = Math.max(2, Math.ceil(nonEmptyCells.length * 0.6));
  return headerLikeCount === nonEmptyCells.length || headerLikeCount >= threshold;
};

const normalizeRows = (rows: string[][]) => {
  const columnCount = rows.reduce((max, row) => Math.max(max, row.length), 0);
  if (!columnCount) return { columnCount: 0, normalizedRows: [] as string[][] };
  return {
    columnCount,
    normalizedRows: rows.map(row => Array.from({ length: columnCount }, (_, index) => row[index] || '')),
  };
};

const inferHeaderRow = (rows: string[][], columnCount: number) => {
  const combined = compactCell(rows.flat().join(''));
  if (
    columnCount === 4
    && /(?:完全响应|招标人|设计服务|服务地点|初步设计|施工图设计|竣工验收|油库|加油站|新能源)/.test(combined)
  ) {
    return SERVICE_SCOPE_HEADERS;
  }
  if (columnCount === 5 && /(?:质量目标|检查节点|校审|闭环|质量|初步设计|施工图设计)/.test(combined)) {
    return QUALITY_HEADERS;
  }

  if (columnCount === 2) return ['项目', '内容'];
  if (columnCount === 3) return ['项目', '响应内容', '备注'];
  if (columnCount === 4) return ['项目', '响应内容', '成果或配合事项', '备注'];
  if (columnCount === 5) return ['项目', '目标', '节点', '要求', '备注'];
  return Array.from({ length: columnCount }, (_, index) => `列${index + 1}`);
};

export const tableCaptionTitleFromText = (value: string): string | null => {
  const text = value.replace(/\s+/g, '').trim();
  if (!text) return null;

  const numbered = text.match(/^表\d+[\s、:：.-]*(.{2,40})$/);
  if (numbered?.[1]) return ensureTableSuffix(numbered[1].replace(/[。；;，,：:].*$/, ''));

  const beforeTable = text.match(/(.{2,40}?)(?:详?见下表|如下表|见表)/);
  if (beforeTable?.[1]) {
    const cleaned = beforeTable[1]
      .replace(/^(本项目|本次服务|本次|本章|下列|以下|上述)/, '')
      .replace(/(?:情况|内容|如下|为)$/, '');
    return cleaned ? ensureTableSuffix(cleaned) : null;
  }

  if (text.length <= 32 && text.endsWith('表') && !/[。；;，,]/.test(text)) {
    return text;
  }

  return null;
};

export const isStandaloneTableCaptionSource = (value: string) => {
  const text = value.replace(/\s+/g, '').trim();
  return Boolean(
    text
    && text.length <= 36
    && !/[。；;，,]/.test(text)
    && (/^表\d+/.test(text) || text.endsWith('表'))
  );
};

export const buildTableWithHeader = (rows: string[][]): TableWithHeader => {
  const { columnCount, normalizedRows } = normalizeRows(rows);
  if (!columnCount || !normalizedRows.length) return { headerRow: [], bodyRows: [] };

  if (
    normalizedRows.length >= 2
    && isGenericColumnHeaderRow(normalizedRows[0])
    && isLikelySemanticTableHeader(normalizedRows[1])
  ) {
    return {
      headerRow: normalizedRows[1],
      bodyRows: normalizedRows.slice(2),
    };
  }

  if (isLikelySemanticTableHeader(normalizedRows[0])) {
    return {
      headerRow: normalizedRows[0],
      bodyRows: normalizedRows.slice(1),
    };
  }

  return {
    headerRow: inferHeaderRow(normalizedRows, columnCount),
    bodyRows: normalizedRows,
  };
};

export const inferTableCaptionTitle = (rows: string[][]) => {
  const { headerRow } = buildTableWithHeader(rows);
  const combinedText = [...headerRow, ...rows.flat()].join('|');
  if (/本项目任职/.test(combinedText) && /姓名/.test(combinedText) && /职称/.test(combinedText) && /专业/.test(combinedText)) {
    return '项目情况表';
  }
  const headerText = headerRow.join('|');
  if (/招标范围/.test(headerText) && /投标响应/.test(headerText)) return '服务范围响应情况表';
  if (/进度事项|完成时限|管控方式/.test(headerText)) return '进度目标响应表';
  if (/质量目标|检查节点|校审要求|闭环方式/.test(headerText)) return '质量控制响应表';
  if (/人员|岗位|职责|专业/.test(headerText)) return '人员配置表';
  if (/设备|软件|工具/.test(headerText)) return '设备配置表';
  if (/资料|文件|页码|附件/.test(headerText)) return '资料清单表';
  return '响应情况表';
};

export const isProjectSituationTable = (rows: string[][]) => {
  const combined = compactCell(rows.flat().join(''));
  return /本项目任职/.test(combined)
    && /姓名/.test(combined)
    && /职称/.test(combined)
    && /专业/.test(combined)
    && /(?:证书名称|证号|执业|职业资格|注册)/.test(combined);
};

export const isProjectPersonnelSupplementTable = (rows: string[][]) => {
  if (isProjectSituationTable(rows)) return false;
  const combined = compactCell(rows.flat().join(''));
  const table = buildTableWithHeader(rows);
  const headerText = compactCell(table.headerRow.join(''));
  const hasProjectPersonSignal = /(?:项目负责人|业绩项目|同类工程|社保月份|身份证号|注册证书编号)/.test(combined);
  const hasPlaceholderSignal = /(?:待补充|页码待编排|合同或委托证明|扫描件|证明索引)/.test(combined);
  const genericResponseTable = /项目.*目标.*节点.*要求.*备注/.test(headerText);
  return hasProjectPersonSignal && (hasPlaceholderSignal || genericResponseTable);
};

export const isEmptyResponseOnlyTable = (rows: string[][]) => {
  const table = buildTableWithHeader(rows);
  const headerText = compactCell(table.headerRow.join(''));
  if (!/(?:响应|偏离|技术条款|商务条款|说明)/.test(headerText)) return false;
  if (!table.bodyRows.length) return true;

  const meaningfulRows = table.bodyRows
    .map(row => row.map(compactCell).filter(Boolean))
    .filter(cells => cells.length > 0);
  if (!meaningfulRows.length) return true;

  return meaningfulRows.every(cells => cells.every(isBoilerplateResponseCell));
};

const valueByHeader = (headerRow: string[], row: string[], patterns: RegExp[]) => {
  const index = headerRow.findIndex(header => patterns.some(pattern => pattern.test(compactCell(header))));
  return index >= 0 ? (row[index] || '').trim() : '';
};

export const singleRepeatedProjectLeaderSummary = (rows: string[][]): string | null => {
  const table = buildTableWithHeader(rows);
  const headerText = compactCell(table.headerRow.join(''));
  if (!/项目负责人/.test(headerText) || !table.bodyRows.length) return null;

  const leaderNames = table.bodyRows
    .map(row => valueByHeader(table.headerRow, row, [/项目负责人/, /^姓名$/]))
    .map(value => value.trim())
    .filter(Boolean);
  const uniqueNames = Array.from(new Set(leaderNames));
  if (uniqueNames.length !== 1) return null;

  const leaderName = uniqueNames[0];
  const firstRow = table.bodyRows.find(row => row.includes(leaderName)) || table.bodyRows[0];
  const title = valueByHeader(table.headerRow, firstRow, [/职称/, /职务/, /岗位/]);
  const education = valueByHeader(table.headerRow, firstRow, [/学历/]);
  const certificate = valueByHeader(table.headerRow, firstRow, [/证书/, /证明文件/, /注册资格/]);
  const projectNames = table.bodyRows
    .map(row => valueByHeader(table.headerRow, row, [/项目名称/, /业绩项目/]))
    .filter(Boolean);

  const attributes = [title, education, certificate].filter(Boolean).join('，');
  const projectPart = projectNames.length
    ? `，相关项目经历包括${projectNames.slice(0, 3).join('、')}${projectNames.length > 3 ? '等项目' : ''}`
    : '';
  return `拟派项目负责人为${leaderName}${attributes ? `，${attributes}` : ''}${projectPart}。`;
};

export const markdownLinesFromRowsWithHeader = (rows: string[][]) => {
  if (isEmptyResponseOnlyTable(rows)) return [];
  const leaderSummary = singleRepeatedProjectLeaderSummary(rows);
  if (leaderSummary) return [leaderSummary];
  const { headerRow, bodyRows } = buildTableWithHeader(rows);
  if (!headerRow.length || !bodyRows.length) return [];
  return [
    `| ${headerRow.join(' | ')} |`,
    `| ${Array(headerRow.length).fill('---').join(' | ')} |`,
    ...bodyRows.map(row => `| ${row.join(' | ')} |`),
  ];
};
