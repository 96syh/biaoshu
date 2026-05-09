import { useEffect, useState } from 'react';
import { CheckCircleIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import { AnalysisReport, OutlineItem } from '../../types';

interface OutlineRowsProps {
  item: OutlineItem;
  report?: AnalysisReport | null;
  selectedId?: string;
  editingId?: string;
  level?: number;
  onSelect: (id: string) => void;
  onEdit: (item: OutlineItem) => void;
  onAddChild: (item: OutlineItem) => void;
  onDelete: (item: OutlineItem) => void;
  getScoringIds: (item: OutlineItem, report?: AnalysisReport | null) => string[];
}

const containsOutlineItem = (item: OutlineItem, id?: string): boolean => {
  if (!id) return false;
  if (item.id === id) return true;
  return Boolean(item.children?.some(child => containsOutlineItem(child, id)));
};

const riskLevel = (item: OutlineItem) => {
  if (item.risk_ids?.length) return '高风险';
  if ((item.material_ids?.length || 0) > 1) return '中风险';
  return '低风险';
};

export const OutlineRows = ({
  item,
  report,
  selectedId,
  editingId,
  level = 0,
  onSelect,
  onEdit,
  onAddChild,
  onDelete,
  getScoringIds,
}: OutlineRowsProps) => {
  const hasChildren = Boolean(item.children?.length);
  const [expanded, setExpanded] = useState(level === 0);
  const active = containsOutlineItem(item, selectedId) || containsOutlineItem(item, editingId);
  const editing = item.id === editingId;
  const scoringIds = getScoringIds(item, report);
  const materialCount = item.material_ids?.length || 0;
  const expectsMaterial = Boolean(
    item.enterprise_required
    || item.asset_required
    || item.expected_blocks?.some(block => ['image', 'table', 'org_chart', 'workflow_chart', 'commitment_letter', 'material_attachment'].includes(block))
  );
  const materialLabel = materialCount > 0 ? `材料 ${materialCount}` : expectsMaterial ? '待材料' : '无需材料';
  const materialTone = materialCount > 0 ? 'chip--green' : expectsMaterial ? 'chip--amber' : '';
  const materialHelp = materialCount > 0
    ? `已绑定材料 ID：${item.material_ids?.join('、')}`
    : expectsMaterial
      ? '该章节需要企业资料、表格、图片或承诺书，但当前未映射到具体材料 ID。通常是招标文件未列出明确材料编号，或解析/目录映射未匹配到材料清单。'
      : '该章节当前不依赖单独证明材料，正文会直接按招标要求展开。';
  const itemRiskLevel = riskLevel(item);
  const handleRowAction = () => {
    if (hasChildren) {
      setExpanded(prev => !prev);
      return;
    }
    onSelect(item.id);
  };

  useEffect(() => {
    if (hasChildren && active) setExpanded(true);
  }, [active, hasChildren]);

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        className={`outline-row ${active ? 'outline-row--active' : ''} ${editing ? 'outline-row--editing' : ''}`}
        style={{ paddingLeft: 18 + level * 24 }}
        onClick={handleRowAction}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            handleRowAction();
          }
        }}
      >
        <span className="outline-name">
          {hasChildren ? <ChevronRightIcon className={`outline-chevron h-3.5 w-3.5 ${expanded ? 'outline-chevron--open' : ''}`} /> : <span className="tree-branch" />}
          <strong>{item.id}　{item.title}</strong>
        </span>
        <span className="outline-row-actions">
          <button type="button" onClick={(event) => { event.stopPropagation(); onEdit(item); }}>编辑</button>
          <button type="button" onClick={(event) => { event.stopPropagation(); onAddChild(item); }}>子级</button>
          <button type="button" className="danger-text-button" onClick={(event) => { event.stopPropagation(); onDelete(item); }}>删除</button>
        </span>
        <span className="chip chip--green">评分项 {scoringIds.length || '-'}</span>
        <span className={`chip ${itemRiskLevel === '高风险' ? 'chip--red' : itemRiskLevel === '中风险' ? 'chip--amber' : 'chip--green'}`}>{itemRiskLevel}</span>
        <span className={`chip ${materialTone}`} title={materialHelp}>{materialLabel}</span>
      </div>
      {active && (
        <div className="outline-row-detail" style={{ paddingLeft: 42 + level * 24 }}>
          <span>{item.description || '该节点用于承接招标文件对应要求。'}</span>
          <em>{materialHelp}</em>
        </div>
      )}
      {expanded && item.children?.map(child => (
        <OutlineRows
          key={child.id}
          item={child}
          report={report}
          selectedId={selectedId}
          editingId={editingId}
          level={level + 1}
          onSelect={onSelect}
          onEdit={onEdit}
          onAddChild={onAddChild}
          onDelete={onDelete}
          getScoringIds={getScoringIds}
        />
      ))}
    </>
  );
};
