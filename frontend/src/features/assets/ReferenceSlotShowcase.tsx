import { referenceSlotImageSrc, referenceSlotTitle, referenceSlotTypeLabel } from '../../utils/visualAssets';
import { ReferenceSlotGraphic } from './ReferenceSlotGraphic';

export const ReferenceSlotShowcase = ({ slot }: { slot: Record<string, any> }) => {
  const title = referenceSlotTitle(slot);
  const assetType = String(slot.asset_type || 'other');
  return (
    <div className="asset-reference-showcase">
      <div className="asset-reference-showcase__copy">
        <span>样例图预览</span>
        <strong>{title}</strong>
        <p>{slot.fallback_placeholder || slot.description || slot.position || '根据成熟样例图片位生成的图表预览，正式生成后会写回正文和 Word 导出。'}</p>
      </div>
      <ReferenceSlotGraphic slot={slot} />
      <div className="asset-reference-showcase__meta">
        <span>{referenceSlotTypeLabel(assetType)}</span>
        <span>{referenceSlotImageSrc(slot) ? '样例原图' : '结构预览'}</span>
      </div>
    </div>
  );
};
