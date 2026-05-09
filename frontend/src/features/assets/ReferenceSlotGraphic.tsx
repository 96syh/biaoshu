import { referenceSlotImageSrc, referenceSlotTitle } from '../../utils/visualAssets';

export const ReferenceSlotGraphic = ({ slot, compact = false }: { slot: Record<string, any>; compact?: boolean }) => {
  const src = referenceSlotImageSrc(slot);
  const title = referenceSlotTitle(slot);
  const assetType = String(slot.asset_type || 'other');
  if (src) {
    return <img className={compact ? 'asset-slot-image asset-slot-image--compact' : 'asset-slot-image'} src={src} alt={title} />;
  }
  if (assetType === 'org_chart') {
    return (
      <div className={`asset-slot-graphic asset-slot-graphic--org ${compact ? 'asset-slot-graphic--compact' : ''}`}>
        <strong>{title}</strong>
        <div><span>项目负责人</span></div>
        <div><span>技术负责人</span><span>质量负责人</span><span>资料负责人</span></div>
        <div><span>设计专业组</span><span>校审组</span><span>交付组</span></div>
      </div>
    );
  }
  if (assetType === 'workflow_chart') {
    return (
      <div className={`asset-slot-graphic asset-slot-graphic--flow ${compact ? 'asset-slot-graphic--compact' : ''}`}>
        <strong>{title}</strong>
        {['任务接收', '方案编制', '内部校审', '成果提交', '归档复盘'].map(step => <span key={step}>{step}</span>)}
      </div>
    );
  }
  if (assetType === 'software_screenshot') {
    return (
      <div className={`asset-slot-graphic asset-slot-graphic--screen ${compact ? 'asset-slot-graphic--compact' : ''}`}>
        <strong>{title}</strong>
        <section><i /><i /><i /><i /></section>
      </div>
    );
  }
  if (assetType === 'certificate_image') {
    return (
      <div className={`asset-slot-graphic asset-slot-graphic--cert ${compact ? 'asset-slot-graphic--compact' : ''}`}>
        <strong>{title}</strong>
        <section><span>证书</span><i /><i /><i /></section>
      </div>
    );
  }
  if (assetType === 'project_rendering') {
    return (
      <div className={`asset-slot-graphic asset-slot-graphic--render ${compact ? 'asset-slot-graphic--compact' : ''}`}>
        <strong>{title}</strong>
        <section><i /><i /><i /></section>
      </div>
    );
  }
  return (
    <div className={`asset-slot-graphic asset-slot-graphic--image ${compact ? 'asset-slot-graphic--compact' : ''}`}>
      <strong>{title}</strong>
      <section><span>图片素材</span><i /><i /></section>
    </div>
  );
};
