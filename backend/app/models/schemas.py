"""数据模型定义"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ConfigRequest(BaseModel):
    """模型配置请求"""
    model_config = {"protected_namespaces": ()}
    
    provider: str = Field("litellm", description="模型供应商，当前固定为 LiteLLM Proxy")
    api_key: str = Field("", description="API密钥")
    base_url: Optional[str] = Field(None, description="Base URL")
    model_name: str = Field("", description="模型名称")
    api_mode: str = Field("chat", description="API协议模式，当前固定为 OpenAI Chat Completions")


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    message: str


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[str]
    success: bool
    message: str = ""


class ProviderCheckItem(BaseModel):
    """模型端点探测结果"""
    stage: str
    success: bool
    detail: str = ""
    url: Optional[str] = None
    http_status: Optional[int] = None
    model_name: Optional[str] = None
    models: Optional[List[str]] = None
    sample: Optional[str] = None


class ProviderVerifyResponse(BaseModel):
    """模型端点验证响应"""
    success: bool
    message: str
    provider: str
    normalized_base_url: str = ""
    resolved_base_url: str = ""
    base_url_candidates: List[str] = Field(default_factory=list)
    model_name: str = ""
    api_mode: str = "auto"
    checks: List[ProviderCheckItem] = Field(default_factory=list)


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    message: str
    file_content: Optional[str] = None
    old_outline: Optional[str] = None
    parser_info: Dict[str, Any] = Field(default_factory=dict, description="文档解析器、输出格式和降级信息")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="样例投标文件风格剖面")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")


class ProjectDraftRequest(BaseModel):
    """项目草稿保存请求"""
    project_id: Optional[str] = Field(None, description="项目 ID；为空时使用当前激活项目或新建")
    draft: Dict[str, Any] = Field(default_factory=dict, description="完整项目草稿 JSON")
    activate: bool = Field(True, description="保存后是否设为当前项目")


class ProjectCreateRequest(BaseModel):
    """新建项目请求"""
    draft: Dict[str, Any] = Field(default_factory=dict, description="可选初始草稿")


class ProjectRecord(BaseModel):
    """项目数据库记录"""
    id: str
    title: str
    createdAt: str
    updatedAt: str
    completed: int = 0
    total: int = 0
    wordCount: int = 0
    draft: Dict[str, Any] = Field(default_factory=dict)


class ProjectResponse(BaseModel):
    """项目 API 响应"""
    success: bool
    message: str = ""
    project: Optional[ProjectRecord] = None
    projects: List[ProjectRecord] = Field(default_factory=list)


class AnalysisType(str, Enum):
    """分析类型"""
    OVERVIEW = "overview"
    REQUIREMENTS = "requirements"


class BidMode(str, Enum):
    """标书生成模式。

    保持向后兼容，同时扩展为通用投标文件范围：完整标书、技术标、服务方案、
    商务卷、资格卷、报价卷、施工组织设计、供货方案等。
    """
    TECHNICAL_ONLY = "technical_only"
    TECHNICAL_SERVICE_PLAN = "technical_service_plan"
    SERVICE_PLAN = "service_plan"
    FULL_BID = "full_bid"
    BUSINESS_TECHNICAL = "business_technical"
    BUSINESS_VOLUME = "business_volume"
    QUALIFICATION_VOLUME = "qualification_volume"
    PRICE_VOLUME = "price_volume"
    CONSTRUCTION_PLAN = "construction_plan"
    GOODS_SUPPLY_PLAN = "goods_supply_plan"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value):
        normalized = str(value or "").strip()
        aliases = {
            "technical_volume": cls.TECHNICAL_ONLY,
            "service_plan_volume": cls.SERVICE_PLAN,
            "technical_service_volume": cls.TECHNICAL_SERVICE_PLAN,
            "business": cls.BUSINESS_VOLUME,
            "qualification": cls.QUALIFICATION_VOLUME,
            "price": cls.PRICE_VOLUME,
            "full": cls.FULL_BID,
            "完整标书": cls.FULL_BID,
            "完整标": cls.FULL_BID,
            "技术标": cls.TECHNICAL_ONLY,
            "服务方案": cls.SERVICE_PLAN,
            "商务卷": cls.BUSINESS_VOLUME,
            "资格卷": cls.QUALIFICATION_VOLUME,
            "报价卷": cls.PRICE_VOLUME,
            "施工方案": cls.CONSTRUCTION_PLAN,
            "供货方案": cls.GOODS_SUPPLY_PLAN,
        }
        return aliases.get(normalized, cls.UNKNOWN)


class AnalysisRequest(BaseModel):
    """文档分析请求"""
    file_content: str = Field(..., description="文档内容")
    analysis_type: AnalysisType = Field(..., description="分析类型")


class AnalysisProjectInfo(BaseModel):
    """结构化解析报告中的项目基础信息"""
    name: str = Field("", description="项目名称")
    number: str = Field("", description="项目编号")
    package_name: str = Field("", description="标段/包号")
    package_or_lot: str = Field("", description="标段/包件信息")
    purchaser: str = Field("", description="采购人/招标人")
    agency: str = Field("", description="采购代理机构")
    procurement_method: str = Field("", description="采购/招标方式")
    project_type: str = Field("", description="项目类型")
    budget: str = Field("", description="项目预算")
    maximum_price: str = Field("", description="最高限价/控制价")
    funding_source: str = Field("", description="资金来源")
    service_scope: str = Field("", description="服务范围")
    service_period: str = Field("", description="服务期限")
    service_location: str = Field("", description="服务地点")
    quality_requirements: str = Field("", description="质量要求")
    bid_validity: str = Field("", description="投标有效期")
    bid_bond: str = Field("", description="投标保证金要求")
    performance_bond: str = Field("", description="履约担保要求")
    bid_deadline: str = Field("", description="投标截止/开标时间")
    opening_time: str = Field("", description="开标时间")
    submission_method: str = Field("", description="递交方式")
    electronic_platform: str = Field("", description="电子交易平台")
    submission_requirements: str = Field("", description="电子标/纸质标递交要求")
    signature_requirements: str = Field("", description="整体签字盖章要求")


class SourceRef(BaseModel):
    """招标文件出处索引"""
    id: str = Field(..., description="出处ID，如 SRC-01")
    location: str = Field("", description="章节、页码、表格或条款位置")
    excerpt: str = Field("", description="短摘录，不超过120字")
    related_ids: List[str] = Field(default_factory=list, description="关联解析项ID")


class BidDocumentSourceChapter(BaseModel):
    """招标文件中投标文件编制要求的出处"""
    id: str = Field(..., description="出处ID，如 BD-SRC-01")
    chapter_title: str = Field("", description="章节名称，如 投标文件/投标文件格式/投标文件的组成")
    location: str = Field("", description="章节、页码、条款或表格位置")
    excerpt: str = Field("", description="短摘录，不超过120字")


class BidDocumentCompositionItem(BaseModel):
    """投标文件应包含的卷册、章节、表单或附件要求"""
    id: str = Field(..., description="组成项ID，如 BD-01")
    order: int = Field(0, description="招标文件列明的顺序")
    title: str = Field("", description="章节、表单、附件或卷册名称")
    required: bool = Field(True, description="是否必备")
    applicability: str = Field("required", description="required/optional/not_applicable/conditional")
    volume_id: str = Field("", description="所属卷册ID，如 V-BIZ/V-TECH/V-PRICE")
    chapter_type: str = Field("", description="cover/toc/form/authorization/bond/price/qualification/business/technical/service_plan/deviation_table/commitment/other")
    fixed_format: bool = Field(False, description="是否固定格式")
    allow_self_drafting: bool = Field(False, description="是否允许自拟或参考模板扩展")
    signature_required: bool = Field(False, description="是否需要签字")
    seal_required: bool = Field(False, description="是否需要盖章")
    attachment_required: bool = Field(False, description="是否需要附件或证明材料")
    price_related: bool = Field(False, description="是否报价相关")
    anonymity_sensitive: bool = Field(False, description="是否受暗标/匿名约束")
    source_ref: str = Field("", description="出处ID")
    must_keep_text: List[str] = Field(default_factory=list, description="不得修改的固定文字")
    must_keep_columns: List[str] = Field(default_factory=list, description="不得修改的表头/列名")
    fillable_fields: List[str] = Field(default_factory=list, description="允许填写的字段")
    children: List[Dict[str, Any]] = Field(default_factory=list, description="子项，避免递归模型带来的兼容问题")


class SchemeOutlineRequirement(BaseModel):
    """技术/服务/施工/供货方案应包含的提纲要求"""
    id: str = Field(..., description="提纲要求ID，如 BD-SP-01")
    parent_title: str = Field("", description="所属方案名称，如 服务方案/技术方案/施工组织设计")
    order: int = Field(0, description="顺序")
    title: str = Field("", description="招标文件列明的方案子项")
    required: bool = Field(True, description="是否必须覆盖")
    allow_expand: bool = Field(True, description="是否允许结合投标人情况扩展")
    source_ref: str = Field("", description="出处ID")
    target_chapter_hint: str = Field("", description="建议映射章节")


class SelectedGenerationTarget(BaseModel):
    """本次目录与正文生成应聚焦的投标文件组成项。用于解决“只生成服务方案/设计方案”而非整本投标文件的问题。"""
    target_id: str = Field("", description="选中的组成项ID，如 BD-07 或 BD-SP-01")
    target_title: str = Field("", description="选中的生成对象标题，如 服务方案/设计方案/技术方案")
    parent_composition_id: str = Field("", description="所属投标文件组成项ID")
    target_source: str = Field("", description="来源章节、页码或条款，如 第六章七服务方案 / 3.1.1(7)设计方案")
    target_source_type: str = Field("", description="composition_item/format_section/scoring_section/user_selected/inferred")
    generation_scope: str = Field("scheme_section_only", description="scheme_section_only/full_bid/volume_only/unknown")
    use_as_outline_basis: bool = Field(True, description="是否作为目录硬依据")
    base_outline_strategy: str = Field("", description="scheme_outline/format_section_children/technical_scoring_items/reference_profile_fallback/generic_fallback")
    base_outline_items: List[Dict[str, Any]] = Field(default_factory=list, description="目录基础项，含 order/title/source_ref/derived_from 等")
    excluded_composition_item_ids: List[str] = Field(default_factory=list, description="生成技术/方案分册时应排除的完整投标文件组成项ID")
    excluded_composition_titles: List[str] = Field(default_factory=list, description="生成技术/方案分册时应排除的完整投标文件组成项标题")
    selection_reason: str = Field("", description="为什么选中该章节作为生成对象")
    confidence: str = Field("medium", description="high/medium/low")


class BidDocumentFixedForm(BaseModel):
    """投标文件格式中的固定表单或固定函件"""
    id: str = Field(..., description="固定格式ID，如 BD-FF-01")
    form_name: str = Field("", description="表单或函件名称")
    belongs_to: str = Field("", description="所属组成项ID")
    must_keep_columns: List[str] = Field(default_factory=list, description="必须保留的列名")
    must_keep_text: List[str] = Field(default_factory=list, description="必须保留的固定文字")
    fillable_fields: List[str] = Field(default_factory=list, description="允许填写的字段")
    signature_required: bool = Field(False, description="是否要求签字")
    seal_required: bool = Field(False, description="是否要求盖章")
    date_required: bool = Field(False, description="是否要求日期")
    source_ref: str = Field("", description="出处ID")


class BidDocumentFormattingRules(BaseModel):
    """投标文件格式、递交和排版要求"""
    language: str = Field("", description="语言文字要求")
    toc_required: bool = Field(False, description="是否要求目录")
    page_number_required: bool = Field(False, description="是否要求页码或响应页码")
    binding_or_upload_rules: str = Field("", description="装订、上传、加密、密封或递交规则")
    electronic_signature_rules: str = Field("", description="电子签章规则")
    encryption_or_platform_rules: str = Field("", description="平台、加密、验签或上传规则")
    source_ref: str = Field("", description="出处ID")


class BidDocumentRequirements(BaseModel):
    """招标文件中“投标文件/投标文件格式/投标文件组成/编制要求”的硬约束"""
    source_chapters: List[BidDocumentSourceChapter] = Field(default_factory=list, description="投标文件编制要求出处")
    document_scope_required: str = Field("unknown", description="full_bid/technical_volume/service_plan_volume/business_volume/qualification_volume/price_volume/unknown")
    composition: List[BidDocumentCompositionItem] = Field(default_factory=list, description="投标文件组成、顺序和格式要求")
    scheme_or_technical_outline_requirements: List[SchemeOutlineRequirement] = Field(default_factory=list, description="方案类章节应包括的提纲")
    selected_generation_target: SelectedGenerationTarget = Field(default_factory=SelectedGenerationTarget, description="本次目录与正文生成应聚焦的投标文件组成项")
    fixed_forms: List[BidDocumentFixedForm] = Field(default_factory=list, description="固定格式表单或函件")
    formatting_and_submission_rules: BidDocumentFormattingRules = Field(default_factory=BidDocumentFormattingRules, description="投标文件格式、递交和平台要求")
    excluded_when_generating_technical_only: List[str] = Field(default_factory=list, description="生成技术/服务分册时应排除的完整投标文件章节")
    priority_rule: str = Field("投标文件编制要求优先于样例风格。", description="优先级说明")


class TechnicalScoringItem(BaseModel):
    """技术评分项"""
    id: str = Field(..., description="评分项ID，如 T-01")
    name: str = Field("", description="评分项名称")
    score: str = Field("", description="分值或权重")
    standard: str = Field("", description="评分标准")
    source: str = Field("", description="招标文件出处")
    writing_focus: str = Field("", description="后续正文写作重点")
    evidence_requirements: List[str] = Field(default_factory=list, description="证据/材料要求")
    easy_loss_points: List[str] = Field(default_factory=list, description="易失分点")


class BusinessScoringItem(BaseModel):
    """商务评分项"""
    id: str = Field(..., description="商务评分项ID，如 B-01")
    name: str = Field("", description="评分项名称")
    score: str = Field("", description="分值或权重")
    standard: str = Field("", description="评分标准")
    source: str = Field("", description="招标文件出处")
    evidence_requirements: List[str] = Field(default_factory=list, description="证据/材料要求")
    writing_focus: str = Field("", description="后续正文写作重点")
    easy_loss_points: List[str] = Field(default_factory=list, description="易失分点")


class PriceScoringItem(BaseModel):
    """价格评分项"""
    id: str = Field(..., description="价格评分项ID，如 P-01")
    name: str = Field("", description="评分项名称")
    score: str = Field("", description="分值或权重")
    logic: str = Field("", description="价格分计算或评分逻辑")
    source: str = Field("", description="招标文件出处")
    risk: str = Field("", description="报价风险提示")


class QualificationRequirement(BaseModel):
    """资格审查或资质要求"""
    id: str = Field(..., description="资格要求ID，如 Q-01")
    name: str = Field("", description="要求名称")
    requirement: str = Field("", description="具体要求")
    source: str = Field("", description="招标文件出处")
    required_materials: List[str] = Field(default_factory=list, description="关联材料ID列表")


class FormalResponseRequirement(BaseModel):
    """投标文件格式、表单、承诺等响应要求"""
    id: str = Field(..., description="响应要求ID，如 F-01")
    name: str = Field("", description="要求名称")
    requirement: str = Field("", description="具体要求")
    source: str = Field("", description="招标文件出处")
    fixed_format: bool = Field(False, description="是否固定格式")
    signature_required: bool = Field(False, description="是否需要签字盖章")
    attachment_required: bool = Field(False, description="是否需要附件证明")


class MandatoryClause(BaseModel):
    """实质性条款或必须响应条款"""
    id: str = Field(..., description="条款ID，如 C-01")
    clause: str = Field("", description="条款内容")
    source: str = Field("", description="招标文件出处")
    response_strategy: str = Field("", description="响应策略")
    invalid_if_not_responded: bool = Field(False, description="未响应是否可能导致否决")


class RejectionRisk(BaseModel):
    """废标或高风险项"""
    id: str = Field(..., description="风险ID，如 R-01")
    risk: str = Field("", description="风险描述")
    trigger: str = Field("", description="触发条件")
    source: str = Field("", description="招标文件出处")
    mitigation: str = Field("", description="规避或响应建议")
    blocking: bool = Field(True, description="是否阻塞导出")


class RequiredMaterial(BaseModel):
    """投标所需证明材料"""
    id: str = Field(..., description="材料ID，如 M-01")
    name: str = Field("", description="材料名称")
    purpose: str = Field("", description="材料用途")
    source: str = Field("", description="招标文件出处")
    status: str = Field("missing", description="材料状态，如 missing/provided/unknown")
    used_by: List[str] = Field(default_factory=list, description="被哪些评分项/审查项引用")
    volume_id: str = Field("", description="所属卷册ID")


class BidStructureItem(BaseModel):
    """投标文件结构节点"""
    id: str = Field(..., description="结构节点ID，如 S-01")
    parent_id: str = Field("", description="父节点ID")
    title: str = Field("", description="章节或表格名称")
    purpose: str = Field("", description="章节用途")
    category: str = Field("", description="资格/商务/技术/报价/承诺/附件等类别")
    volume_id: str = Field("", description="卷册ID，如 V-TECH/V-BIZ/V-PRICE")
    required: bool = Field(True, description="是否必备")
    fixed_format: bool = Field(False, description="是否固定格式")
    signature_required: bool = Field(False, description="是否需要签字盖章")
    attachment_required: bool = Field(False, description="是否需要附件证明")
    seal_required: bool = Field(False, description="是否需要盖章")
    price_related: bool = Field(False, description="是否与报价相关")
    anonymity_sensitive: bool = Field(False, description="是否受暗标/匿名要求约束")
    source: str = Field("", description="招标文件出处")


class ReviewRequirementItem(BaseModel):
    """初步评审要求"""
    id: str = Field(..., description="评审项ID，如 E-01")
    review_type: str = Field("", description="形式评审/资格评审/响应性评审")
    requirement: str = Field("", description="招标要求")
    criterion: str = Field("", description="判断标准")
    required_materials: List[str] = Field(default_factory=list, description="所需材料ID列表")
    risk: str = Field("", description="常见失分或废标风险")
    target_chapters: List[str] = Field(default_factory=list, description="建议对应章节")
    source: str = Field("", description="招标文件出处")
    invalid_if_missing: bool = Field(False, description="缺失是否可能导致否决")


class PriceRule(BaseModel):
    """报价与计价规则"""
    quote_method: str = Field("", description="报价方式")
    currency: str = Field("", description="币种")
    maximum_price_rule: str = Field("", description="最高限价规则")
    abnormally_low_price_rule: str = Field("", description="异常低价/低于成本规则")
    separate_price_volume_required: bool = Field(False, description="报价文件是否必须单独成册")
    price_forbidden_in_other_volumes: bool = Field(False, description="技术/商务卷是否禁止出现价格")
    tax_requirement: str = Field("", description="含税/不含税及税率要求")
    decimal_places: str = Field("", description="小数位数要求")
    uniqueness_requirement: str = Field("", description="报价唯一性要求")
    form_requirements: str = Field("", description="开标一览表/费用明细表要求")
    arithmetic_correction_rule: str = Field("", description="算术错误修正规则")
    missing_item_rule: str = Field("", description="缺漏项处理规则")
    prohibited_format_changes: List[str] = Field(default_factory=list, description="禁止改动的格式要求")
    source_ref: str = Field("", description="出处ID或条款位置")


class BidVolumeRule(BaseModel):
    """卷册隔离和组卷规则"""
    id: str = Field(..., description="卷册ID，如 V-TECH")
    name: str = Field("", description="卷册名称")
    scope: str = Field("", description="卷册范围")
    separate_submission: bool = Field(False, description="是否单独递交")
    price_allowed: bool = Field(True, description="本卷是否允许出现报价")
    anonymity_required: bool = Field(False, description="本卷是否要求匿名/暗标")
    seal_signature_rule: str = Field("", description="签章规则")
    source: str = Field("", description="招标文件出处")


class AnonymityRules(BaseModel):
    """暗标、双盲或匿名技术标规则"""
    enabled: bool = Field(False, description="是否存在匿名/暗标要求")
    scope: str = Field("", description="适用范围")
    forbidden_identifiers: List[str] = Field(default_factory=list, description="禁止出现的身份识别信息")
    formatting_rules: List[str] = Field(default_factory=list, description="字体、页眉页脚、图片等格式规则")
    source: str = Field("", description="招标文件出处")


class GenerationWarning(BaseModel):
    """生成链路警告"""
    id: str = Field(..., description="警告ID，如 W-01")
    warning: str = Field("", description="警告内容")
    severity: str = Field("warning", description="warning/blocking")
    related_ids: List[str] = Field(default_factory=list, description="关联解析项ID")


class FixedFormatForm(BaseModel):
    """固定格式表单或模板"""
    id: str = Field(..., description="固定格式ID，如 FF-01")
    name: str = Field("", description="表单或模板名称")
    volume_id: str = Field("", description="所属卷册ID")
    source: str = Field("", description="招标文件出处")
    required_columns: List[str] = Field(default_factory=list, description="不得修改的表头/列名")
    must_keep_columns: List[str] = Field(default_factory=list, description="必须保留的列")
    must_keep_text: List[str] = Field(default_factory=list, description="必须保留的固定文字")
    fillable_fields: List[str] = Field(default_factory=list, description="允许填写的字段")
    fixed_text: str = Field("", description="不得修改的固定文字")
    fill_rules: str = Field("", description="填写规则")
    seal_required: bool = Field(False, description="是否需要盖章")


class SignatureRequirement(BaseModel):
    """签字盖章要求"""
    id: str = Field(..., description="签章要求ID，如 SIG-01")
    target: str = Field("", description="对应章节/表单/附件")
    signer: str = Field("", description="签署主体或人员")
    seal: str = Field("", description="盖章要求")
    date_required: bool = Field(False, description="是否要求签署日期")
    electronic_signature_required: bool = Field(False, description="是否要求电子签章")
    source: str = Field("", description="招标文件出处")
    risk: str = Field("", description="遗漏风险")


class EvidenceChainRequirement(BaseModel):
    """证据链要求"""
    id: str = Field(..., description="证据链ID，如 EV-01")
    target: str = Field("", description="适用对象，如企业业绩/项目负责人/社保")
    required_evidence: List[str] = Field(default_factory=list, description="合同关键页、发票、截图等证据")
    validation_rule: str = Field("", description="核验口径")
    source: str = Field("", description="招标文件出处")
    risk: str = Field("", description="风险提示")


class MissingCompanyMaterial(BaseModel):
    """企业需补充资料"""
    id: str = Field(..., description="待补资料ID，如 X-01")
    name: str = Field("", description="资料名称")
    used_by: List[str] = Field(default_factory=list, description="被哪些评分项/要求引用")
    placeholder: str = Field("", description="正文中使用的待补充占位文本")
    blocking: bool = Field(False, description="是否阻塞导出")


class EnterpriseProvidedMaterial(BaseModel):
    """已识别的企业资料。"""
    id: str = Field(..., description="企业资料ID，如 EM-P-01")
    name: str = Field("", description="资料名称")
    material_type: str = Field("", description="资质/业绩/人员/设备/证书/图片/承诺/报价/其他")
    source: str = Field("", description="资料来源，如用户上传、企业资料库、历史样例或招标文件要求")
    used_by: List[str] = Field(default_factory=list, description="被哪些评分项/审查项/章节引用")
    confidence: str = Field("unknown", description="high/medium/low/unknown")
    verification_status: str = Field("unverified", description="unverified/verified/rejected/expired")


class EnterpriseMaterialRequirement(BaseModel):
    """企业资料需求项，独立于正文材料占位。"""
    id: str = Field(..., description="需求ID，如 EM-R-01")
    name: str = Field("", description="所需资料名称")
    material_type: str = Field("", description="资质/业绩/人员/设备/证书/图片/承诺/报价/其他")
    required_by: List[str] = Field(default_factory=list, description="来源评分项/评审项/章节ID")
    source: str = Field("", description="招标文件出处")
    required: bool = Field(True, description="是否必需")
    blocking: bool = Field(False, description="缺失是否阻塞导出或需人工确认")
    placeholder: str = Field("", description="正文或附件索引中的占位文本")
    status: str = Field("missing", description="missing/provided/unknown/not_applicable")
    validation_rule: str = Field("", description="人工复核口径")


class EnterpriseMaterialProfile(BaseModel):
    """企业资料独立解析画像。"""
    requirements: List[EnterpriseMaterialRequirement] = Field(default_factory=list, description="企业资料需求")
    provided_materials: List[EnterpriseProvidedMaterial] = Field(default_factory=list, description="已识别企业资料")
    missing_materials: List[EnterpriseMaterialRequirement] = Field(default_factory=list, description="仍需补齐资料")
    verification_tasks: List[str] = Field(default_factory=list, description="人工复核任务")
    summary: str = Field("", description="企业资料准备状态摘要")


class ResponseMatrixItem(BaseModel):
    """响应矩阵条目"""
    id: str = Field(..., description="矩阵ID，如 RM-01")
    source_item_id: str = Field("", description="来源解析项ID")
    source_type: str = Field("", description="scoring/review/mandatory/risk/material/format/signature/evidence/price")
    requirement_summary: str = Field("", description="需要响应的要求摘要")
    response_strategy: str = Field("", description="正文响应策略")
    target_chapter_ids: List[str] = Field(default_factory=list, description="建议目录章节ID")
    required_material_ids: List[str] = Field(default_factory=list, description="材料ID")
    risk_ids: List[str] = Field(default_factory=list, description="风险ID")
    source_refs: List[str] = Field(default_factory=list, description="出处ID或条款位置")
    priority: str = Field("normal", description="high/normal/low")
    status: str = Field("pending", description="pending/covered/missing")
    blocking: bool = Field(False, description="未覆盖是否阻塞导出")


class ResponseMatrix(BaseModel):
    """招标要求到目录、正文和材料的响应矩阵"""
    items: List[ResponseMatrixItem] = Field(default_factory=list, description="响应矩阵条目")
    uncovered_ids: List[str] = Field(default_factory=list, description="尚未覆盖的来源项ID")
    high_risk_ids: List[str] = Field(default_factory=list, description="高风险矩阵条目ID")
    coverage_summary: str = Field("", description="覆盖摘要")


class AnalysisReport(BaseModel):
    """招标文件标准解析报告，供目录、正文和审校阶段复用"""
    project: AnalysisProjectInfo = Field(default_factory=AnalysisProjectInfo, description="项目基础信息")
    bid_mode_recommendation: BidMode = Field(BidMode.TECHNICAL_ONLY, description="推荐生成模式")
    source_refs: List[SourceRef] = Field(default_factory=list, description="出处索引")
    bid_document_requirements: BidDocumentRequirements = Field(default_factory=BidDocumentRequirements, description="投标文件/投标文件格式/组成/编制要求硬约束")
    volume_rules: List[BidVolumeRule] = Field(default_factory=list, description="卷册隔离规则")
    anonymity_rules: AnonymityRules = Field(default_factory=AnonymityRules, description="暗标/匿名规则")
    bid_structure: List[BidStructureItem] = Field(default_factory=list, description="投标文件结构树")
    formal_review_items: List[ReviewRequirementItem] = Field(default_factory=list, description="形式评审项")
    qualification_review_items: List[ReviewRequirementItem] = Field(default_factory=list, description="资格评审项")
    responsiveness_review_items: List[ReviewRequirementItem] = Field(default_factory=list, description="响应性评审项")
    business_scoring_items: List[BusinessScoringItem] = Field(default_factory=list, description="商务评分项")
    technical_scoring_items: List[TechnicalScoringItem] = Field(default_factory=list, description="技术评分项")
    price_scoring_items: List[PriceScoringItem] = Field(default_factory=list, description="价格评分项")
    price_rules: PriceRule = Field(default_factory=PriceRule, description="报价与计价规则")
    qualification_requirements: List[QualificationRequirement] = Field(default_factory=list, description="资格审查要求")
    formal_response_requirements: List[FormalResponseRequirement] = Field(default_factory=list, description="正式响应格式要求")
    mandatory_clauses: List[MandatoryClause] = Field(default_factory=list, description="实质性/必须响应条款")
    rejection_risks: List[RejectionRisk] = Field(default_factory=list, description="废标或高风险项")
    fixed_format_forms: List[FixedFormatForm] = Field(default_factory=list, description="固定格式表单")
    signature_requirements: List[SignatureRequirement] = Field(default_factory=list, description="签字盖章要求")
    evidence_chain_requirements: List[EvidenceChainRequirement] = Field(default_factory=list, description="证据链要求")
    required_materials: List[RequiredMaterial] = Field(default_factory=list, description="所需证明材料")
    missing_company_materials: List[MissingCompanyMaterial] = Field(default_factory=list, description="待补企业资料")
    enterprise_material_profile: EnterpriseMaterialProfile = Field(default_factory=EnterpriseMaterialProfile, description="独立企业资料解析画像")
    generation_warnings: List[GenerationWarning] = Field(default_factory=list, description="生成链路警告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")


class OutlineItem(BaseModel):
    """目录项"""
    id: str
    title: str
    description: str
    volume_id: str = Field("", description="所属卷册ID")
    chapter_type: str = Field("", description="章节类型，如 technical/business/price/form/material/review/service_plan/supply/construction")
    source_type: str = Field("", description="章节来源类型，如 tender_direct_response/scoring_response/profile_expansion/enterprise_showcase")
    fixed_format_sensitive: bool = Field(False, description="是否涉及固定格式")
    price_sensitive: bool = Field(False, description="是否涉及报价")
    anonymity_sensitive: bool = Field(False, description="是否受暗标/匿名要求约束")
    expected_word_count: int = Field(0, description="建议篇幅")
    expected_depth: str = Field("medium", description="建议深度 short/medium/long/very_long")
    expected_blocks: List[str] = Field(default_factory=list, description="预期内容块 paragraph/table/image/org_chart/workflow_chart/commitment_letter/material_attachment")
    enterprise_required: bool = Field(False, description="是否依赖企业资料")
    asset_required: bool = Field(False, description="是否依赖图片、证书、截图或其他素材")
    scoring_item_ids: List[str] = Field(default_factory=list, description="关联技术/商务/价格评分项ID列表")
    requirement_ids: List[str] = Field(default_factory=list, description="关联资格/响应要求ID列表")
    risk_ids: List[str] = Field(default_factory=list, description="关联风险ID列表")
    material_ids: List[str] = Field(default_factory=list, description="关联材料ID列表")
    response_matrix_ids: List[str] = Field(default_factory=list, description="关联响应矩阵ID列表")
    children: Optional[List['OutlineItem']] = None
    content: Optional[str] = None


# 解决循环引用
OutlineItem.model_rebuild()


class OutlineResponse(BaseModel):
    """目录响应"""
    outline: List[OutlineItem]
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
    coverage_summary: str = Field("", description="目录映射覆盖摘要")


class OutlineRequest(BaseModel):
    """目录生成请求"""
    overview: str = Field(..., description="项目概述")
    requirements: str = Field(..., description="技术评分要求")
    file_content: Optional[str] = Field(None, description="招标文件全文，用于目录阶段补齐方案纲要子项")
    uploaded_expand: Optional[bool] = Field(False, description="是否已上传方案扩写文件")
    old_outline: Optional[str] = Field(None, description="上传的方案扩写文件解析出的旧目录JSON")
    old_document: Optional[str] = Field(None, description="上传的方案扩写文件解析出的旧文档")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    bid_mode: Optional[BidMode] = Field(None, description="标书生成模式")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="可选：成熟投标文件样例风格剖面")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="可选：图表与素材规划")

class ContentGenerationRequest(BaseModel):
    """内容生成请求"""
    outline: Dict[str, Any] = Field(..., description="目录结构")
    project_overview: str = Field("", description="项目概述")


class GeneratedSummary(BaseModel):
    """已生成章节摘要"""
    chapter_id: str = Field(..., description="章节ID")
    summary: str = Field("", description="章节摘要")


class ChapterContentRequest(BaseModel):
    """单章节内容生成请求"""
    chapter: Dict[str, Any] = Field(..., description="章节信息")
    parent_chapters: Optional[List[Dict[str, Any]]] = Field(None, description="上级章节列表")
    sibling_chapters: Optional[List[Dict[str, Any]]] = Field(None, description="同级章节列表")
    project_overview: str = Field("", description="项目概述")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    bid_mode: Optional[BidMode] = Field(None, description="标书生成模式")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="可选：样例风格剖面")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="可选：图表与素材规划")
    generated_summaries: List[GeneratedSummary] = Field(default_factory=list, description="已生成章节摘要")
    enterprise_materials: List[RequiredMaterial] = Field(default_factory=list, description="已提供企业材料")
    enterprise_material_profile: EnterpriseMaterialProfile = Field(default_factory=EnterpriseMaterialProfile, description="独立企业资料解析画像")
    missing_materials: List[MissingCompanyMaterial] = Field(default_factory=list, description="待补企业资料")
    asset_library: Dict[str, Any] = Field(default_factory=dict, description="可选：图片、证书、截图、效果图等素材库")


class AnalysisReportRequest(BaseModel):
    """结构化解析报告生成请求"""
    file_content: str = Field(..., description="招标文件内容")
    config: Optional[ConfigRequest] = Field(None, description="可选：本次解析使用的运行时模型配置")


class AnalysisTaskControlRequest(BaseModel):
    """标准解析任务控制请求"""
    action: str = Field(..., description="pause/resume/stop")


class AnalysisTaskControlResponse(BaseModel):
    """标准解析任务控制响应"""
    success: bool
    message: str
    task_id: str = ""
    status: str = ""


class ReviewCoverageItem(BaseModel):
    """评分项覆盖检查结果"""
    item_id: str = Field("", description="评分项或要求ID")
    target_type: str = Field("", description="检查对象类型")
    covered: bool = Field(False, description="是否已覆盖")
    chapter_ids: List[str] = Field(default_factory=list, description="覆盖该项的章节ID")
    issue: str = Field("", description="问题说明")
    evidence: str = Field("", description="覆盖证据")
    fix_suggestion: str = Field("", description="修复建议")


class ReviewMissingMaterialItem(BaseModel):
    """缺失材料检查结果"""
    material_id: str = Field("", description="材料ID")
    material_name: str = Field("", description="材料名称")
    used_by: List[str] = Field(default_factory=list, description="被哪些要求引用")
    chapter_ids: List[str] = Field(default_factory=list, description="相关章节ID")
    placeholder: str = Field("", description="建议占位文本")
    placeholder_found: bool = Field(False, description="正文是否已有占位")
    fix_suggestion: str = Field("", description="修复建议")


class ReviewRiskItem(BaseModel):
    """废标风险检查结果"""
    risk_id: str = Field("", description="风险ID")
    handled: bool = Field(False, description="是否已处理")
    issue: str = Field("", description="问题说明")


class ReviewDuplicationIssue(BaseModel):
    """重复内容检查结果"""
    chapter_ids: List[str] = Field(default_factory=list, description="重复章节ID")
    issue: str = Field("", description="问题说明")


class ReviewFabricationRisk(BaseModel):
    """疑似虚构风险检查结果"""
    chapter_id: str = Field("", description="章节ID")
    text: str = Field("", description="疑似风险文本")
    reason: str = Field("", description="判断原因")
    fix_suggestion: str = Field("", description="修复建议")


class ReviewContractIssue(BaseModel):
    """导出前审校通用问题"""
    item_id: str = Field("", description="关联项ID")
    chapter_ids: List[str] = Field(default_factory=list, description="相关章节ID")
    issue: str = Field("", description="问题说明")
    evidence: str = Field("", description="审校证据")
    fix_suggestion: str = Field("", description="修复建议")
    severity: str = Field("warning", description="问题等级，如 blocking/warning")
    blocking: bool = Field(False, description="是否阻塞导出")


class RevisionPlanAction(BaseModel):
    """修订计划动作"""
    id: str = Field(..., description="动作ID，如 RP-01")
    target_chapter_ids: List[str] = Field(default_factory=list, description="目标章节")
    action_type: str = Field("", description="补写/替换/删减/补材料/人工确认")
    instruction: str = Field("", description="修订指令")
    priority: str = Field("normal", description="high/normal/low")
    related_issue_ids: List[str] = Field(default_factory=list, description="关联问题ID")
    blocking: bool = Field(False, description="是否处理后才能导出")


class RevisionPlan(BaseModel):
    """审校后的修订计划"""
    actions: List[RevisionPlanAction] = Field(default_factory=list, description="修订动作")
    summary: str = Field("", description="修订摘要")


class ReviewSummary(BaseModel):
    """审校汇总"""
    ready_to_export: bool = Field(False, description="是否可导出")
    blocking_issues: int = Field(0, description="阻塞问题数量")
    warnings: int = Field(0, description="警告数量")
    blocking_issues_count: int = Field(0, description="阻塞问题数量")
    warnings_count: int = Field(0, description="警告数量")
    coverage_rate: float = Field(0, description="覆盖率")
    blocking_summary: str = Field("", description="阻塞摘要")
    next_actions: List[str] = Field(default_factory=list, description="下一步处理建议")


class ReviewReport(BaseModel):
    """导出前合规审校报告"""
    coverage: List[ReviewCoverageItem] = Field(default_factory=list, description="评分项/要求覆盖检查")
    missing_materials: List[ReviewMissingMaterialItem] = Field(default_factory=list, description="缺失材料检查")
    rejection_risks: List[ReviewRiskItem] = Field(default_factory=list, description="废标风险检查")
    duplication_issues: List[ReviewDuplicationIssue] = Field(default_factory=list, description="重复内容检查")
    fabrication_risks: List[ReviewFabricationRisk] = Field(default_factory=list, description="虚构风险检查")
    fixed_format_issues: List[ReviewContractIssue] = Field(default_factory=list, description="固定格式问题")
    signature_issues: List[ReviewContractIssue] = Field(default_factory=list, description="签字盖章问题")
    price_rule_issues: List[ReviewContractIssue] = Field(default_factory=list, description="报价规则问题")
    evidence_chain_issues: List[ReviewContractIssue] = Field(default_factory=list, description="证据链问题")
    page_reference_issues: List[ReviewContractIssue] = Field(default_factory=list, description="页码/索引问题")
    anonymity_issues: List[ReviewContractIssue] = Field(default_factory=list, description="暗标/匿名问题")
    blocking_issues: List[ReviewContractIssue] = Field(default_factory=list, description="阻塞项清单")
    warnings: List[ReviewContractIssue] = Field(default_factory=list, description="警告项清单")
    revision_plan: Optional[RevisionPlan] = Field(None, description="修订计划")
    summary: ReviewSummary = Field(default_factory=ReviewSummary, description="审校汇总")


class ComplianceReviewRequest(BaseModel):
    """导出前合规审校请求"""
    outline: List[OutlineItem] = Field(..., description="包含正文内容的目录结构")
    project_overview: Optional[str] = Field("", description="项目概述")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
    bid_mode: Optional[BidMode] = Field(None, description="标书生成模式")


class DocumentBlocksPlanRequest(BaseModel):
    """图表与素材规划请求"""
    outline: List[OutlineItem] = Field(..., description="目录结构")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    enterprise_materials: List[RequiredMaterial] = Field(default_factory=list, description="企业资料")
    enterprise_material_profile: EnterpriseMaterialProfile = Field(default_factory=EnterpriseMaterialProfile, description="独立企业资料解析画像")
    asset_library: Dict[str, Any] = Field(default_factory=dict, description="素材库")


class ConsistencyRevisionRequest(BaseModel):
    """全文一致性修订请求"""
    full_bid_draft: List[OutlineItem] = Field(..., description="包含正文内容的目录结构")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None


class WordExportRequest(BaseModel):
    """Word导出请求"""
    project_name: Optional[str] = Field(None, description="项目名称")
    project_overview: Optional[str] = Field(None, description="项目概述")
    outline: List[OutlineItem] = Field(..., description="目录结构，包含内容")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    review_report: Optional[ReviewReport] = Field(None, description="导出前审校报告")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟样例写作模板和 Word 样式")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
    manual_review_confirmed: bool = Field(False, description="是否已完成人工复核确认")
    export_dir: Optional[str] = Field(None, description="可选：由本地后端直接保存 Word 的目录")
