import ReactMarkdown from 'react-markdown';
import { OutlineItem } from '../../types';
import { PlannedBlock, blockTypeLabel, generatedAssetFromBlock, visualAssetImageSrc } from '../../utils/visualAssets';

export const docSectionId = (id: string) => `doc-section-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;

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
            <ReactMarkdown>{item.content}</ReactMarkdown>
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
