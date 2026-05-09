import { SparklesIcon } from '@heroicons/react/24/outline';

export type DraftOutlineRow = { id: string; title: string; level: number; status: string };

export const OutlineDraftPreview = ({ rows }: { rows: DraftOutlineRow[] }) => (
  <div className="outline-draft">
    <div className="outline-draft__head">
      <SparklesIcon className="h-4 w-4" />
      <strong>正在生成目录和映射关系</strong>
      <span>{rows.length ? `已出现 ${rows.length} 个章节` : '等待模型返回章节'}</span>
    </div>
    <div className="outline-draft__list">
      {rows.length ? rows.map((row, index) => (
        <div key={`${row.id}-${index}`} className="outline-draft-row" style={{ paddingLeft: 14 + row.level * 22 }}>
          <span>{row.id}</span>
          <strong>{row.title}</strong>
          <em>{row.status}</em>
        </div>
      )) : (
        Array.from({ length: 5 }).map((_, index) => <div key={index} className="outline-draft-skeleton" />)
      )}
    </div>
  </div>
);
