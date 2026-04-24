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

export type BidMode = 'technical_only' | 'full_bid';

export interface AnalysisProjectInfo {
  name: string;
  number: string;
  package_name: string;
  purchaser: string;
  project_type: string;
  budget: string;
  service_scope: string;
  service_period: string;
  service_location: string;
  quality_requirements: string;
  bid_validity: string;
  bid_bond: string;
  performance_bond: string;
  bid_deadline: string;
  submission_requirements: string;
  signature_requirements: string;
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
}

export interface RejectionRisk {
  id: string;
  risk: string;
  source: string;
  mitigation: string;
}

export interface RequiredMaterial {
  id: string;
  name: string;
  purpose: string;
  source: string;
  status: string;
}

export interface BidStructureItem {
  id: string;
  parent_id: string;
  title: string;
  purpose: string;
  category: string;
  required: boolean;
  fixed_format: boolean;
  signature_required: boolean;
  attachment_required: boolean;
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
}

export interface PriceRule {
  quote_method: string;
  tax_requirement: string;
  decimal_places: string;
  uniqueness_requirement: string;
  form_requirements: string;
  arithmetic_correction_rule: string;
  missing_item_rule: string;
  prohibited_format_changes: string[];
}

export interface FixedFormatForm {
  id: string;
  name: string;
  source: string;
  required_columns: string[];
  fixed_text: string;
  fill_rules: string;
}

export interface SignatureRequirement {
  id: string;
  target: string;
  signer: string;
  seal: string;
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
}

export interface AnalysisReport {
  project: AnalysisProjectInfo;
  bid_mode_recommendation: BidMode;
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
}

export interface OutlineItem {
  id: string;
  title: string;
  description: string;
  scoring_item_ids?: string[];
  requirement_ids?: string[];
  risk_ids?: string[];
  material_ids?: string[];
  children?: OutlineItem[];
  content?: string;
}

export interface OutlineData {
  outline: OutlineItem[];
  project_name?: string;
  project_overview?: string;
  analysis_report?: AnalysisReport;
  bid_mode?: BidMode;
}

export interface GeneratedSummary {
  chapter_id: string;
  summary: string;
}

export interface ReviewCoverageItem {
  item_id: string;
  covered: boolean;
  chapter_ids: string[];
  issue: string;
}

export interface ReviewMissingMaterialItem {
  material_id: string;
  chapter_ids: string[];
  placeholder: string;
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
}

export interface ReviewContractIssue {
  item_id: string;
  chapter_ids: string[];
  issue: string;
  severity: string;
  blocking: boolean;
}

export interface ReviewSummary {
  ready_to_export: boolean;
  blocking_issues: number;
  warnings: number;
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
  summary: ReviewSummary;
}

export interface ComplianceReviewRequest {
  outline: OutlineItem[];
  project_overview?: string;
  analysis_report?: AnalysisReport;
  bid_mode?: BidMode;
}

export interface AppState {
  currentStep: number;
  config: ConfigData;
  fileContent: string;
  projectOverview: string;
  techRequirements: string;
  analysisReport?: AnalysisReport;
  outlineData: OutlineData | null;
  selectedChapter: string;
}
