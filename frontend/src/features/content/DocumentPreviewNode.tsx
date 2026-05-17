import ReactMarkdown from 'react-markdown';
import { OutlineItem } from '../../types';
import {
  buildTableWithHeader,
  formatTableCaption,
  inferTableCaptionTitle,
  isEmptyResponseOnlyTable,
  isProjectPersonnelSupplementTable,
  isProjectSituationTable,
  isLikelySemanticTableHeader,
  isStandaloneTableCaptionSource,
  singleRepeatedProjectLeaderSummary,
  tableCaptionTitleFromText,
} from '../../utils/tableHeaders';
import { PlannedBlock, blockTypeLabel, generatedAssetFromBlock, visualAssetImageSrc } from '../../utils/visualAssets';

export const docSectionId = (id: string) => `doc-section-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;

type PreviewMarkdownBlock =
  | { type: 'markdown'; content: string }
  | { type: 'table'; rows: string[][]; captionTitle?: string };

export type TableNumberingState = {
  current: number;
};

const tableDividerPattern = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
const tableHeaderStartPattern = /\|\s*(?:序号|编号|阶段|类别|层级|项目|名称|成果|进度|招标范围|招标要求|投标响应|成果或配合事项|响应内容|备注)\s*\|/;
const tableRowPattern = /^\s*\|.*\|\s*$/;

const removeBlankLinesInsideMarkdownTables = (content: string): string[] => {
  const lines = content.split(/\r?\n/);
  const normalized: string[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) {
      let previousIndex = normalized.length - 1;
      while (previousIndex >= 0 && !normalized[previousIndex].trim()) previousIndex -= 1;
      let nextIndex = index + 1;
      while (nextIndex < lines.length && !lines[nextIndex].trim()) nextIndex += 1;
      const previousIsTable = previousIndex >= 0 && tableRowPattern.test(normalized[previousIndex].trim());
      const nextIsTable = nextIndex < lines.length && tableRowPattern.test(lines[nextIndex].trim());
      if (previousIsTable && nextIsTable) continue;
    }
    normalized.push(line);
  }
  return normalized;
};

const normalizePotentialInlineTableRows = (content: string): string[] =>
  removeBlankLinesInsideMarkdownTables(content).flatMap(line => {
    const pipeCount = (line.match(/\|/g) || []).length;
    if (pipeCount < 4) return [line];
    const chunks: string[] = [];
    let tableLine = line;
    const headerMatch = tableLine.match(tableHeaderStartPattern);
    if (headerMatch?.index && headerMatch.index > 0 && !tableLine.trimStart().startsWith('|')) {
      const leadText = tableLine.slice(0, headerMatch.index).trim();
      if (leadText) chunks.push(leadText);
      tableLine = tableLine.slice(headerMatch.index);
    }
    const expanded = tableLine
      .replace(/(\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?)/g, '\n$1\n')
      .replace(/\|\s*\|\s*(?=(?:\d+|[一二三四五六七八九十]+)\s*\|)/g, '|\n| ')
      .replace(/\s+(\|\s*(?:\d+|[一二三四五六七八九十]+)\s*\|)/g, '\n$1');
    return [...chunks, ...expanded.split('\n').filter(part => part.trim())];
  });

const parseMarkdownTableRow = (line: string): string[] | null => {
  const trimmed = line.trim();
  if (!trimmed.includes('|') || tableDividerPattern.test(trimmed)) return null;
  const normalized = trimmed.replace(/^\|/, '').replace(/\|$/, '');
  const cells = normalized.split('|').map(cell => cell.trim());
  const meaningfulCells = cells.filter(Boolean);
  if (meaningfulCells.length < 2 && cells.length < 4) return null;
  return cells;
};

export const parseDocumentPreviewBlocks = (content: string): PreviewMarkdownBlock[] => {
  const blocks: PreviewMarkdownBlock[] = [];
  let markdownLines: string[] = [];
  let tableRows: string[][] = [];

  const flushMarkdown = () => {
    const markdown = markdownLines.join('\n').trim();
    if (markdown) blocks.push({ type: 'markdown', content: markdown });
    markdownLines = [];
  };

  const flushTable = () => {
    if (tableRows.length) {
      const table = buildTableWithHeader(tableRows);
      if (table.bodyRows.length) {
        const previousBlock = blocks[blocks.length - 1];
        const previousText = previousBlock?.type === 'markdown' ? previousBlock.content : '';
        const captionTitle = previousText ? tableCaptionTitleFromText(previousText) || undefined : undefined;
        if (isEmptyResponseOnlyTable(tableRows)) {
          if (captionTitle && isStandaloneTableCaptionSource(previousText)) blocks.pop();
          tableRows = [];
          return;
        }
        const leaderSummary = singleRepeatedProjectLeaderSummary(tableRows);
        if (leaderSummary) {
          if (captionTitle && isStandaloneTableCaptionSource(previousText)) blocks.pop();
          blocks.push({ type: 'markdown', content: leaderSummary });
          tableRows = [];
          return;
        }
        if (captionTitle && isStandaloneTableCaptionSource(previousText)) blocks.pop();
        blocks.push({ type: 'table', rows: tableRows, captionTitle });
      }
    }
    tableRows = [];
  };

  normalizePotentialInlineTableRows(content).forEach(line => {
    if (tableDividerPattern.test(line.trim())) return;
    const tableRow = parseMarkdownTableRow(line);
    if (tableRow) {
      flushMarkdown();
      tableRows.push(tableRow);
      return;
    }
    flushTable();
    markdownLines.push(line);
  });

  flushTable();
  flushMarkdown();
  return collapseProjectSituationTables(blocks);
};

const collapseProjectSituationTables = (blocks: PreviewMarkdownBlock[]): PreviewMarkdownBlock[] => {
  const situationIndex = blocks.findIndex(block => block.type === 'table' && isProjectSituationTable(block.rows));
  if (situationIndex < 0) return blocks;

  const nextBlocks: PreviewMarkdownBlock[] = [];
  blocks.forEach((block, index) => {
    if (block.type !== 'table') {
      nextBlocks.push(block);
      return;
    }
    if (index === situationIndex) {
      nextBlocks.push({ ...block, captionTitle: '项目情况表' });
      return;
    }
    if (!isProjectPersonnelSupplementTable(block.rows)) nextBlocks.push(block);
  });
  return nextBlocks;
};

const countMarkdownTables = (content?: string) =>
  parseDocumentPreviewBlocks(content || '').filter(block => block.type === 'table').length;

const countHtmlTables = (html?: string) => {
  if (!html?.trim()) return 0;
  const tableNumbering = { current: 0 };
  normalizeWordHtmlTables(html, tableNumbering);
  return tableNumbering.current;
};

const countRenderedTables = (item: OutlineItem) => {
  if (item.children?.length) return 0;
  if (item.content_html?.trim()) return countHtmlTables(item.content_html);
  return countMarkdownTables(item.content);
};

export const buildDocumentTableNumbering = (items: OutlineItem[]) => {
  const numbering: Record<string, number> = {};
  let tableIndex = 0;
  const visit = (item: OutlineItem) => {
    numbering[item.id] = tableIndex;
    if (item.children?.length) {
      item.children.forEach(visit);
      return;
    }
    tableIndex += countRenderedTables(item);
  };
  items.forEach(visit);
  return numbering;
};

const MarkdownTable = ({ rows }: { rows: string[][] }) => {
  const { headerRow, bodyRows } = buildTableWithHeader(rows);
  if (!headerRow.length || !bodyRows.length) return null;
  return (
    <div className="word-markdown-table-wrap">
      <table className="word-markdown-table">
        <thead>
          <tr>
            {headerRow.map((cell, index) => <th key={`head-${index}`}>{cell}</th>)}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`}>
              {row.map((cell, cellIndex) => <td key={`cell-${rowIndex}-${cellIndex}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const WordMarkdownContent = ({ content, initialTableIndex }: { content: string; initialTableIndex: number }) => {
  const blocks = parseDocumentPreviewBlocks(content);
  let tableIndex = initialTableIndex;
  return (
    <>
      {blocks.map((block, index) => {
        if (block.type === 'table') {
          tableIndex += 1;
          const caption = formatTableCaption(tableIndex, block.captionTitle || inferTableCaptionTitle(block.rows));
          return (
            <div key={`table-${index}`} className="word-table-block">
              <p className="word-table-caption">{caption}</p>
              <MarkdownTable rows={block.rows} />
            </div>
          );
        }
        return <ReactMarkdown key={`markdown-${index}`}>{block.content}</ReactMarkdown>;
      })}
    </>
  );
};

const appendTextParagraph = (documentRef: Document, fragment: DocumentFragment, text: string, blockId: string | null) => {
  const paragraph = documentRef.createElement('p');
  if (blockId) paragraph.setAttribute('data-history-block-id', blockId);
  paragraph.textContent = text;
  fragment.appendChild(paragraph);
};

const appendTable = (documentRef: Document, fragment: DocumentFragment, rows: string[][], blockId: string | null) => {
  if (isEmptyResponseOnlyTable(rows)) return;
  const leaderSummary = singleRepeatedProjectLeaderSummary(rows);
  if (leaderSummary) {
    appendTextParagraph(documentRef, fragment, leaderSummary, blockId);
    return;
  }
  const { headerRow, bodyRows } = buildTableWithHeader(rows);
  if (!headerRow.length || !bodyRows.length) return;
  const table = documentRef.createElement('table');
  if (blockId) table.setAttribute('data-history-block-id', blockId);
  const thead = documentRef.createElement('thead');
  const headTr = documentRef.createElement('tr');
  headerRow.forEach(cell => {
    const th = documentRef.createElement('th');
    th.textContent = cell;
    headTr.appendChild(th);
  });
  thead.appendChild(headTr);
  table.appendChild(thead);
  const tbody = documentRef.createElement('tbody');
  bodyRows.forEach(row => {
    const tr = documentRef.createElement('tr');
    row.forEach(cell => {
      const td = documentRef.createElement('td');
      td.textContent = cell;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  fragment.appendChild(table);
};

const rowCells = (row: HTMLTableRowElement): string[] =>
  Array.from(row.children).map(cell => (cell.textContent || '').trim());

const createTableHead = (documentRef: Document, headerRow: string[]) => {
  const thead = documentRef.createElement('thead');
  const headTr = documentRef.createElement('tr');
  headerRow.forEach(cell => {
    const th = documentRef.createElement('th');
    th.textContent = cell;
    headTr.appendChild(th);
  });
  thead.appendChild(headTr);
  return thead;
};

const ensureHtmlTableHeader = (documentRef: Document, table: HTMLTableElement) => {
  const existingHeads = Array.from(table.querySelectorAll('thead'));
  const hasUsableHead = existingHeads.some(thead =>
    Array.from(thead.querySelectorAll('tr')).some(row => rowCells(row as HTMLTableRowElement).some(Boolean))
  );
  if (hasUsableHead) return;
  existingHeads.forEach(thead => thead.remove());

  const tableRows = Array.from(table.querySelectorAll('tr')) as HTMLTableRowElement[];
  const rawRows = tableRows.map(rowCells).filter(row => row.length > 0);
  if (!rawRows.length) return;
  if (rawRows.length === 1 && isLikelySemanticTableHeader(rawRows[0])) {
    table.remove();
    return;
  }

  const firstRowIsHeader = isLikelySemanticTableHeader(rawRows[0]);
  const { headerRow } = buildTableWithHeader(rawRows);
  if (!headerRow.length) return;
  if (firstRowIsHeader) tableRows[0].remove();
  table.insertBefore(createTableHead(documentRef, headerRow), table.firstChild);
};

const ensureHtmlTableCaptions = (documentRef: Document, container: Element, tableNumbering?: TableNumberingState) => {
  let tableIndex = tableNumbering?.current || 0;
  Array.from(container.querySelectorAll('table')).forEach(tableElement => {
    const table = tableElement as HTMLTableElement;
    if (!table.isConnected) return;
    const rows = (Array.from(table.querySelectorAll('tr')) as HTMLTableRowElement[]).map(rowCells).filter(row => row.length > 0);
    const tableWithHeader = buildTableWithHeader(rows);
    if (!tableWithHeader.bodyRows.length) {
      table.remove();
      return;
    }
    if (isEmptyResponseOnlyTable(rows)) {
      const previousElement = table.previousElementSibling;
      if (previousElement?.classList.contains('word-table-caption')) previousElement.remove();
      table.remove();
      return;
    }
    const leaderSummary = singleRepeatedProjectLeaderSummary(rows);
    if (leaderSummary) {
      const previousElement = table.previousElementSibling;
      if (previousElement?.classList.contains('word-table-caption') || (previousElement?.tagName.toLowerCase() === 'p' && isStandaloneTableCaptionSource(previousElement.textContent || ''))) {
        previousElement.textContent = leaderSummary;
        previousElement.classList.remove('word-table-caption');
      } else {
        const paragraph = documentRef.createElement('p');
        paragraph.textContent = leaderSummary;
        table.parentNode?.insertBefore(paragraph, table);
      }
      table.remove();
      return;
    }

    tableIndex += 1;
    const previousElement = table.previousElementSibling;
    const previousText = previousElement?.tagName.toLowerCase() === 'p' ? previousElement.textContent || '' : '';
    const captionTitle = tableCaptionTitleFromText(previousText) || inferTableCaptionTitle(rows);
    const captionText = formatTableCaption(tableIndex, captionTitle);

    if (previousElement?.classList.contains('word-table-caption')) {
      previousElement.textContent = captionText;
      return;
    }

    if (previousElement?.tagName.toLowerCase() === 'p' && isStandaloneTableCaptionSource(previousText)) {
      previousElement.textContent = captionText;
      previousElement.classList.add('word-table-caption');
      return;
    }

    const caption = documentRef.createElement('p');
    caption.className = 'word-table-caption';
    caption.textContent = captionText;
    table.parentNode?.insertBefore(caption, table);
  });
  if (tableNumbering) tableNumbering.current = tableIndex;
};

const collapseProjectSituationHtmlTables = (container: Element) => {
  const tables = Array.from(container.querySelectorAll('table')) as HTMLTableElement[];
  const tableRows = tables.map(table =>
    (Array.from(table.querySelectorAll('tr')) as HTMLTableRowElement[]).map(rowCells).filter(row => row.length > 0)
  );
  const situationIndex = tableRows.findIndex(rows => isProjectSituationTable(rows));
  if (situationIndex < 0) return;

  tables.forEach((table, index) => {
    if (index === situationIndex || !isProjectPersonnelSupplementTable(tableRows[index])) return;
    const previousElement = table.previousElementSibling;
    if (previousElement?.classList.contains('word-table-caption')) previousElement.remove();
    table.remove();
  });
};

export const normalizeWordHtmlTables = (html: string, tableNumbering?: TableNumberingState): string => {
  if ((!html.includes('|') && !html.toLowerCase().includes('<table')) || typeof DOMParser === 'undefined') return html;
  const parser = new DOMParser();
  const documentRef = parser.parseFromString(`<div>${html}</div>`, 'text/html');
  const container = documentRef.body.firstElementChild;
  if (!container) return html;

  Array.from(container.querySelectorAll('p')).forEach(paragraph => {
    const text = paragraph.textContent || '';
    if (tableDividerPattern.test(text.trim())) {
      paragraph.remove();
      return;
    }
    const blocks = parseDocumentPreviewBlocks(text);
    if (!blocks.some(block => block.type === 'table')) return;
    const fragment = documentRef.createDocumentFragment();
    const blockId = paragraph.getAttribute('data-history-block-id');
    blocks.forEach(block => {
      if (block.type === 'table') {
        appendTable(documentRef, fragment, block.rows, blockId);
      } else {
        appendTextParagraph(documentRef, fragment, block.content, blockId);
      }
    });
    paragraph.replaceWith(fragment);
  });

  Array.from(container.querySelectorAll('p')).forEach(paragraph => {
    const row = parseMarkdownTableRow(paragraph.textContent || '');
    const nextElement = paragraph.nextElementSibling;
    if (!row || !nextElement || nextElement.tagName.toLowerCase() !== 'table') return;

    const table = nextElement as HTMLTableElement;
    const existingHead = table.querySelector('thead');
    const rowLooksLikeHeader = isLikelySemanticTableHeader(row);
    if (!rowLooksLikeHeader) return;

    const firstBodyRow = table.querySelector('tbody tr, tr');
    const columnCount = Math.max(row.length, firstBodyRow?.children.length || 0);
    const normalizedHeader = Array.from({ length: columnCount }, (_, index) => row[index] || '');
    const thead = existingHead || documentRef.createElement('thead');
    thead.innerHTML = '';
    const headTr = documentRef.createElement('tr');
    normalizedHeader.forEach(cell => {
      const th = documentRef.createElement('th');
      th.textContent = cell;
      headTr.appendChild(th);
    });
    thead.appendChild(headTr);
    if (!existingHead) table.insertBefore(thead, table.firstChild);
    paragraph.remove();
  });

  Array.from(container.querySelectorAll('table')).forEach(table => {
    ensureHtmlTableHeader(documentRef, table as HTMLTableElement);
  });
  collapseProjectSituationHtmlTables(container);
  ensureHtmlTableCaptions(documentRef, container, tableNumbering);

  return container.innerHTML;
};

const WordHtmlContent = ({ html, initialTableIndex }: { html: string; initialTableIndex: number }) => {
  const tableNumbering = { current: initialTableIndex };
  return <div className="word-html-fragment" dangerouslySetInnerHTML={{ __html: normalizeWordHtmlTables(html, tableNumbering) }} />;
};

interface DocumentPreviewNodeProps {
  item: OutlineItem;
  level: number;
  activeId?: string;
  streamingId?: string;
  onSelect: (item: OutlineItem) => void;
  visualBlocksByChapter?: Record<string, PlannedBlock[]>;
  tableNumberingByItemId?: Record<string, number>;
}

const WordAssetFigures = ({ blocks }: { blocks: PlannedBlock[] }) => {
  if (!blocks.length) return null;
  return (
    <div className="word-asset-figures">
      {blocks.map((block, index) => {
        const asset = generatedAssetFromBlock(block);
        const src = visualAssetImageSrc(asset);
        if (!src) return null;
        const caption = asset?.caption || `图表 ${index + 1} ${block.block_name || block.name || blockTypeLabel(block.block_type)}`;
        return (
          <figure key={`${asset?.asset_key || block.block_name || index}`} className="word-asset-figure">
            <img src={src} alt={caption} />
            <figcaption>{caption}</figcaption>
          </figure>
        );
      })}
    </div>
  );
};

export const DocumentPreviewNode = ({ item, level, activeId, streamingId, onSelect, visualBlocksByChapter = {}, tableNumberingByItemId }: DocumentPreviewNodeProps) => {
  const activeTableNumberingByItemId = tableNumberingByItemId || buildDocumentTableNumbering([item]);
  const initialTableIndex = activeTableNumberingByItemId[item.id] || 0;
  const hasChildren = Boolean(item.children?.length);
  const active = item.id === activeId;
  const streaming = item.id === streamingId;
  const headingLevel = Math.min(level, 4);
  const headingClass = `word-heading word-heading--${headingLevel}`;
  const visualBlocks = visualBlocksByChapter[item.id] || [];

  return (
    <section
      id={docSectionId(item.id)}
      className={`word-section ${active ? 'word-section--active' : ''}`}
    >
      <button type="button" className={headingClass} onClick={() => onSelect(item)}>
        <span>{item.id} {item.title}</span>
      </button>
      {!hasChildren && (
        item.content?.trim() ? (
          <div className={`word-section__content ${streaming ? 'word-section__content--streaming' : ''}`}>
            {item.content_html?.trim()
              ? <WordHtmlContent html={item.content_html} initialTableIndex={initialTableIndex} />
              : <WordMarkdownContent content={item.content} initialTableIndex={initialTableIndex} />}
          </div>
        ) : (
          <div className={`word-section__placeholder ${streaming ? 'word-section__placeholder--streaming' : ''}`}>请输入或智能编写...</div>
        )
      )}
      <WordAssetFigures blocks={visualBlocks} />
      {item.children?.map(child => (
        <DocumentPreviewNode
          key={child.id}
          item={child}
          level={level + 1}
          activeId={activeId}
          streamingId={streamingId}
          onSelect={onSelect}
          visualBlocksByChapter={visualBlocksByChapter}
          tableNumberingByItemId={activeTableNumberingByItemId}
        />
      ))}
    </section>
  );
};
