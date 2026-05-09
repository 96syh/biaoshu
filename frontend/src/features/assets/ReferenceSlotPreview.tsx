import { referenceSlotTitle, referenceSlotTypeLabel } from '../../utils/visualAssets';
import { ReferenceSlotGraphic } from './ReferenceSlotGraphic';

export const ReferenceSlotPreview = ({ slot }: { slot: Record<string, any> }) => {
  const title = referenceSlotTitle(slot);
  const assetType = String(slot.asset_type || 'other');
  const typeLabel = referenceSlotTypeLabel(assetType);

  return (
    <div className="asset-reference-preview">
      <div className="asset-reference-preview__head">
        <strong>{title}</strong>
        <span>{typeLabel}</span>
      </div>
      <ReferenceSlotGraphic slot={slot} compact />
      <p>{slot.fallback_placeholder || slot.source_ref || '点击左侧图片位查看对应样例图；重新上传样例后，解析器提取到的原图会优先显示。'}</p>
    </div>
  );
};
