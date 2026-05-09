/** Visual asset and document-block data helpers. */
import type { OutlineItem } from '../types';

export type PlannedBlock = Record<string, any>;
export type PlannedBlockGroup = {
  chapter_id: string;
  chapter_title: string;
  blocks: PlannedBlock[];
};
export type VisualAssetResult = {
  status: 'idle' | 'generating' | 'running' | 'success' | 'error';
  imageUrl?: string;
  b64Json?: string;
  prompt?: string;
  caption?: string;
  generatedAt?: string;
  message?: string;
  error?: string;
};
export type GeneratedVisualAsset = {
  asset_key: string;
  chapter_id: string;
  chapter_title: string;
  block_name: string;
  block_type: string;
  image_url?: string;
  b64_json?: string;
  prompt?: string;
  caption?: string;
  generated_at?: string;
};

const collectOutlineEntries = (items: OutlineItem[], parents: OutlineItem[] = []): Array<{ item: OutlineItem; parents: OutlineItem[] }> =>
  items.flatMap((item) => {
    if (item.children?.length) {
      return collectOutlineEntries(item.children, [...parents, item]);
    }
    return [{ item, parents }];
  });

export const isVisualBlockType = (blockType?: string) =>
  ['org_chart', 'workflow_chart', 'image', 'material_attachment'].includes(blockType || '');

export const blockTypeLabel = (blockType?: string) => ({
  table: '表格',
  org_chart: '组织架构图',
  workflow_chart: '流程图',
  image: '图片/信息图',
  commitment_letter: '承诺书',
  material_attachment: '证明材料',
  page_break: '分页',
  paragraph: '段落',
}[blockType || ''] || blockType || '素材');

export const blockAssetKey = (chapterId: string, groupIndex: number, blockIndex: number, block: PlannedBlock) =>
  `${chapterId || 'chapter'}-${groupIndex}-${blockIndex}-${String(block.block_name || block.name || block.block_type || 'block').replace(/\s+/g, '-')}`;

export const generatedAssetFromBlock = (block: PlannedBlock): GeneratedVisualAsset | null => {
  const asset = block.generated_asset || block.visual_asset || block.asset;
  if (!asset || typeof asset !== 'object') return null;
  const imageUrl = String(asset.image_url || asset.url || asset.file_url || '');
  const b64Json = String(asset.b64_json || asset.base64 || asset.image_base64 || '');
  if (!imageUrl && !b64Json) return null;
  return {
    asset_key: String(asset.asset_key || asset.block_key || ''),
    chapter_id: String(asset.chapter_id || block.chapter_id || ''),
    chapter_title: String(asset.chapter_title || block.chapter_title || ''),
    block_name: String(asset.block_name || block.block_name || block.name || '图表素材'),
    block_type: String(asset.block_type || block.block_type || ''),
    image_url: imageUrl,
    b64_json: b64Json,
    prompt: String(asset.prompt || ''),
    caption: String(asset.caption || `图表 ${asset.block_name || block.block_name || block.name || ''}`).trim(),
    generated_at: String(asset.generated_at || ''),
  };
};

export const visualAssetImageSrc = (asset?: Pick<GeneratedVisualAsset, 'image_url' | 'b64_json'> | null) => {
  if (!asset) return '';
  if (asset.image_url) return asset.image_url;
  if (asset.b64_json) {
    return asset.b64_json.startsWith('data:image') ? asset.b64_json : `data:image/png;base64,${asset.b64_json}`;
  }
  return '';
};

export const visualAssetResultFromBlock = (block: PlannedBlock): VisualAssetResult | undefined => {
  const asset = generatedAssetFromBlock(block);
  if (!asset) return undefined;
  return {
    status: 'success',
    imageUrl: asset.image_url,
    b64Json: asset.b64_json,
    prompt: asset.prompt,
    caption: asset.caption,
    generatedAt: asset.generated_at,
  };
};

export const attachGeneratedAssetToPlan = (
  plan: Record<string, unknown> | undefined,
  groupIndex: number,
  blockIndex: number,
  generatedAsset: GeneratedVisualAsset,
  sourceBlock?: PlannedBlock,
) => {
  const nextPlan = JSON.parse(JSON.stringify(plan || {})) as Record<string, any>;
  const groups = Array.isArray(nextPlan.document_blocks) ? nextPlan.document_blocks : [];
  if (!groups[groupIndex]) {
    groups[groupIndex] = {
      chapter_id: generatedAsset.chapter_id,
      chapter_title: generatedAsset.chapter_title,
      blocks: [],
    };
  }
  const group = groups[groupIndex];
  if (!Array.isArray(group.blocks)) group.blocks = [];
  const currentBlock = group.blocks[blockIndex] || sourceBlock || {
    block_type: generatedAsset.block_type,
    block_name: generatedAsset.block_name,
  };
  group.blocks[blockIndex] = {
    ...currentBlock,
    asset_key: generatedAsset.asset_key,
    generated_asset: generatedAsset,
  };
  return { ...nextPlan, document_blocks: groups };
};

export const hasPlannedBlockGroups = (plan: unknown) => {
  const groups = (plan as any)?.document_blocks;
  if (!Array.isArray(groups)) return false;
  return groups.some((group: any) => Array.isArray(group?.blocks) ? group.blocks.length > 0 : Boolean(group?.block_type || group?.block_name));
};

export const normalizeDocumentBlocksPlan = (
  plan: Record<string, unknown> | undefined,
  referenceSlots: Record<string, any>[],
  outline: OutlineItem[] = [],
) => {
  if (hasPlannedBlockGroups(plan)) return plan || {};
  return buildReferenceSlotPlan(referenceSlots, outline);
};

export const visualAssetsFromPlanGroups = (
  groups: PlannedBlockGroup[],
  results: Record<string, VisualAssetResult> = {},
) => {
  const assets: GeneratedVisualAsset[] = [];
  groups.forEach((group, groupIndex) => {
    group.blocks.forEach((block, blockIndex) => {
      const assetKey = blockAssetKey(group.chapter_id, groupIndex, blockIndex, block);
      const blockAsset = generatedAssetFromBlock(block);
      if (blockAsset) {
        assets.push({ ...blockAsset, asset_key: blockAsset.asset_key || assetKey });
        return;
      }
      const result = results[assetKey];
      if (result?.status === 'success' && (result.imageUrl || result.b64Json)) {
        const blockName = String(block.block_name || block.name || blockTypeLabel(block.block_type));
        assets.push({
          asset_key: assetKey,
          chapter_id: group.chapter_id,
          chapter_title: group.chapter_title,
          block_name: blockName,
          block_type: String(block.block_type || ''),
          image_url: result.imageUrl,
          b64_json: result.b64Json,
          prompt: result.prompt,
          caption: result.caption || `图 ${group.chapter_id}-${blockIndex + 1} ${blockName}`,
          generated_at: result.generatedAt || '',
        });
      }
    });
  });
  return assets;
};

export const visualBlocksByChapterFromGroups = (
  groups: PlannedBlockGroup[],
  results: Record<string, VisualAssetResult> = {},
) => {
  const byChapter: Record<string, PlannedBlock[]> = {};
  groups.forEach((group, groupIndex) => {
    group.blocks.forEach((block, blockIndex) => {
      if (!isVisualBlockType(block.block_type)) return;
      const assetKey = blockAssetKey(group.chapter_id, groupIndex, blockIndex, block);
      const existingAsset = generatedAssetFromBlock(block);
      const result = results[assetKey];
      if (!existingAsset && !(result?.status === 'success' && (result.imageUrl || result.b64Json))) return;
      const blockName = String(block.block_name || block.name || blockTypeLabel(block.block_type));
      const generated_asset = existingAsset || {
        asset_key: assetKey,
        chapter_id: group.chapter_id,
        chapter_title: group.chapter_title,
        block_name: blockName,
        block_type: String(block.block_type || ''),
        image_url: result?.imageUrl,
        b64_json: result?.b64Json,
        prompt: result?.prompt,
        caption: result?.caption || `图 ${group.chapter_id}-${blockIndex + 1} ${blockName}`,
        generated_at: result?.generatedAt || '',
      };
      byChapter[group.chapter_id] = [
        ...(byChapter[group.chapter_id] || []),
        { ...block, generated_asset },
      ];
    });
  });
  return byChapter;
};

export const referenceSlotImageSrc = (slot: Record<string, any> | null | undefined) => {
  if (!slot) return '';
  return String(slot.image_url || slot.preview_url || slot.url || slot.file_url || slot.source_url || '').trim();
};

export const referenceSlotTitle = (slot: Record<string, any> | null | undefined, index = 0) =>
  String(slot?.name || slot?.slot_name || slot?.image_alt || `样例图片位 ${index + 1}`).trim();

export const referenceSlotTypeLabel = (assetType?: string) => ({
  org_chart: '组织架构图',
  workflow_chart: '流程图',
  software_screenshot: '软件截图',
  product_image: '产品图片',
  project_rendering: '效果图',
  certificate_image: '证书扫描件',
  other: '图片素材',
}[assetType || ''] || '图片素材');

export const blockTypeFromReferenceAssetType = (assetType?: string) => {
  if (assetType === 'org_chart') return 'org_chart';
  if (assetType === 'workflow_chart') return 'workflow_chart';
  if (assetType === 'certificate_image') return 'material_attachment';
  return 'image';
};

export const buildReferenceSlotChartSchema = (slot: Record<string, any>) => {
  const title = referenceSlotTitle(slot);
  const assetType = String(slot.asset_type || '');
  if (assetType === 'org_chart') {
    return {
      nodes: ['项目负责人', '技术负责人', '质量负责人', '进度负责人', '资料负责人'],
      edges: [['项目负责人', '技术负责人'], ['项目负责人', '质量负责人'], ['项目负责人', '进度负责人'], ['项目负责人', '资料负责人']],
    };
  }
  if (assetType === 'workflow_chart') {
    return {
      nodes: ['任务接收', '方案编制', '内部校审', '成果提交', '归档复盘'],
      edges: [['任务接收', '方案编制'], ['方案编制', '内部校审'], ['内部校审', '成果提交'], ['成果提交', '归档复盘']],
    };
  }
  return {
    nodes: [title, '资料来源', '核验要点', '正文插入位置'],
    edges: [['资料来源', title], ['核验要点', title], [title, '正文插入位置']],
  };
};

export const buildReferenceSlotPlan = (
  slots: Record<string, any>[],
  outline: OutlineItem[] = [],
): Record<string, unknown> => {
  if (!slots.length) return { document_blocks: [], missing_assets: [], missing_enterprise_data: [] };
  const entries = collectOutlineEntries(outline);
  const groups = new Map<string, PlannedBlockGroup>();

  const matchEntry = (slot: Record<string, any>, index: number) => {
    const chapterTitle = String(slot.chapter_title || '').trim();
    const slotTitle = referenceSlotTitle(slot, index);
    const matched = entries.find(entry => {
      const title = `${entry.item.id} ${entry.item.title}`;
      const chapterMatches = Boolean(chapterTitle && (title.includes(chapterTitle) || chapterTitle.includes(entry.item.title)));
      const slotMatches = Boolean(slotTitle && (title.includes(slotTitle) || slotTitle.includes(entry.item.title)));
      return chapterMatches || slotMatches;
    });
    return matched || entries[index % Math.max(entries.length, 1)];
  };

  slots.forEach((slot, index) => {
    const entry = matchEntry(slot, index);
    const chapterId = entry?.item.id || `sample-${index + 1}`;
    const chapterTitle = entry?.item.title || String(slot.chapter_title || '成熟样例图表');
    if (!groups.has(chapterId)) {
      groups.set(chapterId, { chapter_id: chapterId, chapter_title: chapterTitle, blocks: [] });
    }
    groups.get(chapterId)?.blocks.push({
      block_type: blockTypeFromReferenceAssetType(String(slot.asset_type || '')),
      block_name: referenceSlotTitle(slot, index),
      placeholder: slot.fallback_placeholder || slot.description || '根据成熟样例图位生成正式图表素材。',
      data_source: 'reference_bid_style_profile.image_slots',
      required: slot.asset_required !== false,
      reference_slot: slot,
      chart_schema: buildReferenceSlotChartSchema(slot),
    });
  });

  return {
    document_blocks: Array.from(groups.values()),
    missing_assets: [],
    missing_enterprise_data: [],
    source: 'reference_bid_style_profile.image_slots',
  };
};
