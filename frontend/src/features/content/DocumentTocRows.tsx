import { CheckCircleIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import { OutlineItem } from '../../types';

interface DocumentTocRowsProps {
  item: OutlineItem;
  activeId?: string;
  level?: number;
  onSelect: (item: OutlineItem) => void;
}

export const DocumentTocRows = ({ item, activeId, level = 0, onSelect }: DocumentTocRowsProps) => {
  const hasChildren = Boolean(item.children?.length);
  const active = item.id === activeId;
  const generated = Boolean(item.content?.trim());

  return (
    <div className="word-toc-node">
      <button
        type="button"
        className={`word-toc-row ${active ? 'word-toc-row--active' : ''}`}
        style={{ paddingLeft: 10 + level * 18 }}
        onClick={() => onSelect(item)}
      >
        {hasChildren ? <ChevronRightIcon className="h-3.5 w-3.5" /> : <span className="tree-branch" />}
        <span className="word-toc-row__title">{item.id} {item.title}</span>
        {generated && <CheckCircleIcon className="h-3.5 w-3.5 text-emerald-600" />}
      </button>
      {item.children?.map(child => (
        <DocumentTocRows
          key={child.id}
          item={child}
          activeId={activeId}
          level={level + 1}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
};
