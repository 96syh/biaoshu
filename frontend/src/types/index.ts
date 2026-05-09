/**
 * 类型定义
 */

export interface ConfigData {
  provider: string;
  api_key: string;
  base_url?: string;
  model_name: string;
  api_mode?: 'auto' | 'chat' | 'responses' | 'anthropic';
}

export type BidMode =
  | 'technical_only'
  | 'technical_service_plan'
  | 'service_plan'
  | 'full_bid'
  | 'business_technical'
  | 'business_volume'
  | 'qualification_volume'
  | 'price_volume'
  | 'construction_plan'
  | 'goods_supply_plan'
  | 'unknown';

export interface ParserInfo {
  parser?: string;
  preferred_parser?: string;
  fallback_used?: boolean;
  fallback_reason?: string;
  format?: string;
  file_kind?: string;
  device?: string;
  backend?: string;
  content_block_count?: number;
  file_size?: number;
  [key: string]: unknown;
}

export interface SourceRenderedTextBlock {
  id: string;
  text: string;
  bbox: [number, number, number, number];
}

export interface SourceRenderedPreviewPage {
  page_number: number;
  image_url: string;
  width: number;
  height: number;
  text_blocks: SourceRenderedTextBlock[];
}

export interface AnalysisProjectInfo {
  name: string;
  number: string;
  package_name: string;
  package_or_lot?: string;
  purchaser: string;
  agency?: string;
  procurement_method?: string;
  project_type: string;
  budget: string;
  maximum_price?: string;
  funding_source?: string;
  service_scope: string;
  service_period: string;
  service_location: string;
  quality_requirements: string;
  bid_validity: string;
  bid_bond: string;
  performance_bond: string;
  bid_deadline: string;
  opening_time?: string;
  submission_method?: string;
  electronic_platform?: string;
  submission_requirements: string;
  signature_requirements: string;
}

export interface SourceRef {
  id: string;
  location: string;
  excerpt: string;
  related_ids: string[];
}

export interface TechnicalScoringItem {
  id: string;
  name: string;
  score: string;
  standard: string;
  source: string;
  writing_focus: string;
  evidence_requirements: string[];
  easy_loss_points: string[];
}

export interface BusinessScoringItem {
  id: string;
  name: string;
  score: string;
  standard: string;
  source: string;
  evidence_requirements: string[];
  writing_focus: string;
  easy_loss_points: string[];
}

export interface PriceScoringItem {
  id: string;
  name: string;
  score: string;
  logic: string;
  source: string;
  risk: string;
}

export interface QualificationRequirement {
  id: string;
  name: string;
  requirement: string;
  source: string;
  required_materials: string[];
}

export interface FormalResponseRequirement {
  id: string;
  name: string;
  requirement: string;
  source: string;
  fixed_format: boolean;
  signature_required: boolean;
  attachment_required: boolean;
}

export interface MandatoryClause {
  id: string;
  clause: string;
  source: string;
  response_strategy: string;
  invalid_if_not_responded?: boolean;
}

export interface RejectionRisk {
  id: string;
  risk: string;
  trigger?: string;
  source: string;
  mitigation: string;
  blocking?: boolean;
}

export interface RequiredMaterial {
  id: string;
  name: string;
  purpose: string;
  source: string;
  status: string;
  used_by?: string[];
  volume_id?: string;
}

export interface BidStructureItem {
  id: string;
  parent_id: string;
  title: string;
  purpose: string;
  category: string;
  volume_id?: string;
  required: boolean;
  fixed_format: boolean;
  signature_required: boolean;
  attachment_required: boolean;
  seal_required?: boolean;
  price_related?: boolean;
  anonymity_sensitive?: boolean;
  source: string;
}

export interface ReviewRequirementItem {
  id: string;
  review_type: string;
  requirement: string;
  criterion: string;
  required_materials: string[];
  risk: string;
  target_chapters: string[];
  source: string;
  invalid_if_missing?: boolean;
}

export interface PriceRule {
  quote_method: string;
  currency?: string;
  maximum_price_rule?: string;
  abnormally_low_price_rule?: string;
  separate_price_volume_required?: boolean;
  price_forbidden_in_other_volumes?: boolean;
  tax_requirement: string;
  decimal_places: string;
  uniqueness_requirement: string;
  form_requirements: string;
  arithmetic_correction_rule: string;
  missing_item_rule: string;
  prohibited_format_changes: string[];
  source_ref?: string;
}

export interface BidVolumeRule {
  id: string;
  name: string;
  scope: string;
  separate_submission: boolean;
  price_allowed: boolean;
  anonymity_required: boolean;
  seal_signature_rule: string;
  source: string;
}

export interface AnonymityRules {
  enabled: boolean;
  scope: string;
  forbidden_identifiers: string[];
  formatting_rules: string[];
  source: string;
}

export interface GenerationWarning {
  id: string;
  warning: string;
  severity: string;
  related_ids: string[];
}

export interface FixedFormatForm {
  id: string;
  name: string;
  volume_id?: string;
  source: string;
  required_columns: string[];
  must_keep_columns?: string[];
  must_keep_text?: string[];
  fillable_fields?: string[];
  fixed_text: string;
  fill_rules: string;
  seal_required?: boolean;
}

export interface SignatureRequirement {
  id: string;
  target: string;
  signer: string;
  seal: string;
  date_required?: boolean;
  electronic_signature_required?: boolean;
  source: string;
  risk: string;
}

export interface EvidenceChainRequirement {
  id: string;
  target: string;
  required_evidence: string[];
  validation_rule: string;
  source: string;
  risk: string;
}

export interface MissingCompanyMaterial {
  id: string;
  name: string;
  used_by: string[];
  placeholder: string;
  blocking?: boolean;
}

export interface EnterpriseProvidedMaterial {
  id: string;
  name: string;
  material_type: string;
  source: string;
  used_by: string[];
  confidence: string;
  verification_status: string;
}

export interface EnterpriseMaterialRequirement {
  id: string;
  name: string;
  material_type: string;
  required_by: string[];
  source: string;
  required: boolean;
  blocking?: boolean;
  placeholder: string;
  status: 'missing' | 'provided' | 'unknown' | 'not_applicable' | string;
  validation_rule?: string;
}

export interface EnterpriseMaterialProfile {
  requirements: EnterpriseMaterialRequirement[];
  provided_materials: EnterpriseProvidedMaterial[];
  missing_materials: EnterpriseMaterialRequirement[];
  verification_tasks: string[];
  summary: string;
}

export interface ResponseMatrixItem {
  id: string;
  source_item_id: string;
  source_type: string;
  requirement_summary: string;
  response_strategy: string;
  target_chapter_ids: string[];
  required_material_ids: string[];
  risk_ids: string[];
  source_refs: string[];
  priority: string;
  status: string;
  blocking: boolean;
}

export interface ResponseMatrix {
  items: ResponseMatrixItem[];
  uncovered_ids: string[];
  high_risk_ids: string[];
  coverage_summary: string;
}

export interface AnalysisReport {
  project: AnalysisProjectInfo;
  bid_mode_recommendation: BidMode;
  source_refs?: SourceRef[];
  volume_rules?: BidVolumeRule[];
  anonymity_rules?: AnonymityRules;
  bid_structure: BidStructureItem[];
  formal_review_items: ReviewRequirementItem[];
  qualification_review_items: ReviewRequirementItem[];
  responsiveness_review_items: ReviewRequirementItem[];
  business_scoring_items: BusinessScoringItem[];
  technical_scoring_items: TechnicalScoringItem[];
  price_scoring_items: PriceScoringItem[];
  price_rules: PriceRule;
  qualification_requirements: QualificationRequirement[];
  formal_response_requirements: FormalResponseRequirement[];
  mandatory_clauses: MandatoryClause[];
  rejection_risks: RejectionRisk[];
  fixed_format_forms: FixedFormatForm[];
  signature_requirements: SignatureRequirement[];
  evidence_chain_requirements: EvidenceChainRequirement[];
  required_materials: RequiredMaterial[];
  missing_company_materials: MissingCompanyMaterial[];
  enterprise_material_profile?: EnterpriseMaterialProfile;
  generation_warnings?: GenerationWarning[];
  response_matrix?: ResponseMatrix;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
}

export interface OutlineItem {
  id: string;
  title: string;
  description: string;
  volume_id?: string;
  chapter_type?: string;
  fixed_format_sensitive?: boolean;
  price_sensitive?: boolean;
  anonymity_sensitive?: boolean;
  expected_word_count?: number;
  scoring_item_ids?: string[];
  requirement_ids?: string[];
  risk_ids?: string[];
  material_ids?: string[];
  response_matrix_ids?: string[];
  source_type?: string;
  expected_depth?: string;
  expected_blocks?: string[];
  enterprise_required?: boolean;
  asset_required?: boolean;
  children?: OutlineItem[];
  content?: string;
}

export interface OutlineData {
  outline: OutlineItem[];
  project_name?: string;
  project_overview?: string;
  analysis_report?: AnalysisReport;
  response_matrix?: ResponseMatrix;
  coverage_summary?: string;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
  asset_library?: Record<string, unknown>;
  bid_mode?: BidMode;
}

export interface GeneratedSummary {
  chapter_id: string;
  summary: string;
}

export interface ReviewCoverageItem {
  item_id: string;
  target_type?: string;
  covered: boolean;
  chapter_ids: string[];
  issue: string;
  evidence?: string;
  fix_suggestion?: string;
}

export interface ReviewMissingMaterialItem {
  material_id: string;
  material_name?: string;
  used_by?: string[];
  chapter_ids: string[];
  placeholder: string;
  placeholder_found?: boolean;
  fix_suggestion?: string;
}

export interface ReviewRiskItem {
  risk_id: string;
  handled: boolean;
  issue: string;
}

export interface ReviewDuplicationIssue {
  chapter_ids: string[];
  issue: string;
}

export interface ReviewFabricationRisk {
  chapter_id: string;
  text: string;
  reason: string;
  fix_suggestion?: string;
}

export interface ReviewContractIssue {
  item_id: string;
  chapter_ids: string[];
  issue: string;
  evidence?: string;
  fix_suggestion?: string;
  severity: string;
  blocking: boolean;
}

export interface RevisionPlanAction {
  id: string;
  target_chapter_ids: string[];
  action_type: string;
  instruction: string;
  priority: string;
  related_issue_ids: string[];
  blocking: boolean;
}

export interface RevisionPlan {
  actions: RevisionPlanAction[];
  summary: string;
}

export interface ReviewSummary {
  ready_to_export: boolean;
  blocking_issues: number;
  warnings: number;
  blocking_issues_count?: number;
  warnings_count?: number;
  coverage_rate?: number;
  blocking_summary?: string;
  next_actions?: string[];
}

export interface ReviewReport {
  coverage: ReviewCoverageItem[];
  missing_materials: ReviewMissingMaterialItem[];
  rejection_risks: ReviewRiskItem[];
  duplication_issues: ReviewDuplicationIssue[];
  fabrication_risks: ReviewFabricationRisk[];
  fixed_format_issues: ReviewContractIssue[];
  signature_issues: ReviewContractIssue[];
  price_rule_issues: ReviewContractIssue[];
  evidence_chain_issues: ReviewContractIssue[];
  page_reference_issues: ReviewContractIssue[];
  anonymity_issues?: ReviewContractIssue[];
  blocking_issues?: ReviewContractIssue[];
  warnings?: ReviewContractIssue[];
  revision_plan?: RevisionPlan | null;
  summary: ReviewSummary;
}

export interface ComplianceReviewRequest {
  outline: OutlineItem[];
  project_overview?: string;
  analysis_report?: AnalysisReport;
  response_matrix?: ResponseMatrix;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
  bid_mode?: BidMode;
}

export interface DocumentBlocksPlanRequest {
  outline: OutlineItem[];
  analysis_report?: AnalysisReport;
  response_matrix?: ResponseMatrix;
  reference_bid_style_profile?: Record<string, unknown>;
  enterprise_materials?: RequiredMaterial[];
  enterprise_material_profile?: EnterpriseMaterialProfile;
  asset_library?: Record<string, unknown>;
}

export interface VisualAssetGenerationRequest {
  chapter_id?: string;
  chapter_title?: string;
  project_name?: string;
  block: Record<string, unknown>;
  reference_bid_style_profile?: Record<string, unknown>;
  size?: string;
}

export interface VisualAssetGenerationResponse {
  success: boolean;
  message: string;
  prompt: string;
  image_url?: string;
  b64_json?: string;
}

export interface ConsistencyRevisionRequest {
  full_bid_draft: OutlineItem[];
  analysis_report?: AnalysisReport;
  response_matrix?: ResponseMatrix;
  reference_bid_style_profile?: Record<string, unknown>;
  document_blocks_plan?: Record<string, unknown>;
}

export interface ConsistencyRevisionReport {
  ready_for_export: boolean;
  issues: Array<{
    id: string;
    severity: string;
    issue_type: string;
    chapter_id: string;
    original_text: string;
    problem: string;
    fix_suggestion: string;
  }>;
  coverage_check: Array<Record<string, unknown>>;
  missing_blocks: Array<Record<string, unknown>>;
  summary: {
    blocking_count: number;
    high_count: number;
    can_export_after_auto_fix: boolean;
    manual_data_needed: string[];
  };
}

export interface AppState {
  currentStep: number;
  config: ConfigData;
  fileContent: string;
  uploadedFileName?: string;
  sourcePreviewHtml?: string;
  sourcePreviewPages?: SourceRenderedPreviewPage[];
  parserInfo?: ParserInfo;
  projectOverview: string;
  techRequirements: string;
  analysisReport?: AnalysisReport;
  outlineData: OutlineData | null;
  selectedChapter: string;
}
