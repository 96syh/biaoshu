import ReactMarkdown from 'react-markdown';
import { OutlineItem } from '../../types';
import { PlannedBlock, blockTypeLabel, generatedAssetFromBlock, visualAssetImageSrc } from '../../utils/visualAssets';

export const docSectionId = (id: string) => `doc-section-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;

type PreviewMarkdownBlock =
  | { type: 'markdown'; content: string }
  | { type: 'table'; rows: string[][] };

const tableDividerPattern = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
const tableHeaderStartPattern = /\|\s*(?:序号|编号|阶段|类别|层级|项目|名称|成果|进度|招标要求|响应内容)\s*\|/;

const normalizePotentialInlineTableRows = (content: string): string[] =>
  content.split(/\r?\n/).flatMap(line => {
    const pipeCount = (line.match(/\|/g) || []).length;
    if (pipeCount < 6) return [line];
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
    return [...chunks, ...expanded.split('\n')];
  });

const parseMarkdownTableRow = (line: string): string[] | null => {
  const trimmed = line.trim();
  if (!trimmed.includes('|') || tableDividerPattern.test(trimmed)) return null;
  const normalized = trimmed.replace(/^\|/, '').replace(/\|$/, '');
  const cells = normalized.split('|').map(cell => cell.trim());
  const meaningfulCells = cells.filter(Boolean);
  if (meaningfulCells.length < 2) return null;
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
    if (tableRows.length >= 2) {
      blocks.push({ type: 'table', rows: tableRows });
    } else if (tableRows.length === 1) {
      markdownLines.push(`| ${tableRows[0].join(' | ')} |`);
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
  return blocks;
};

const MarkdownTable = ({ rows }: { rows: string[][] }) => {
  const columnCount = Math.max(...rows.map(row => row.length));
  const normalizeRow = (row: string[]) => Array.from({ length: columnCount }, (_, index) => row[index] || '');
  const [headerRow, ...bodyRows] = rows.map(normalizeRow);
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

const WordMarkdownContent = ({ content }: { content: string }) => {
  const blocks = parseDocumentPreviewBlocks(content);
  return (
    <>
      {blocks.map((block, index) => (
        block.type === 'table'
          ? <MarkdownTable key={`table-${index}`} rows={block.rows} />
          : <ReactMarkdown key={`markdown-${index}`}>{block.content}</ReactMarkdown>
      ))}
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
  const columnCount = Math.max(...rows.map(row => row.length));
  const normalizeRow = (row: string[]) => Array.from({ length: columnCount }, (_, index) => row[index] || '');
  const [headerRow, ...bodyRows] = rows.map(normalizeRow);
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

export const normalizeWordHtmlTables = (html: string): string => {
  if (!html.includes('|') || typeof DOMParser === 'undefined') return html;
  const parser = new DOMParser();
  const documentRef = parser.parseFromString(`<div>${html}</div>`, 'text/html');
  const container = documentRef.body.firstElementChild;
  if (!container) return html;

  Array.from(container.querySelectorAll('p')).forEach(paragraph => {
    const text = paragraph.textContent || '';
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

  return container.innerHTML;
};

const WordHtmlContent = ({ html }: { html: string }) => (
  <div className="word-html-fragment" dangerouslySetInnerHTML={{ __html: normalizeWordHtmlTables(html) }} />
);

interface DocumentPreviewNodeProps {
  item: OutlineItem;
  level: number;
  activeId?: string;
  streamingId?: string;
  onSelect: (item: OutlineItem) => void;
  visualBlocksByChapter?: Record<string, PlannedBlock[]>;
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

export const DocumentPreviewNode = ({ item, level, activeId, streamingId, onSelect, visualBlocksByChapter = {} }: DocumentPreviewNodeProps) => {
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
              ? <WordHtmlContent html={item.content_html} />
              : <WordMarkdownContent content={item.content} />}
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
        />
      ))}
    </section>
  );
};
