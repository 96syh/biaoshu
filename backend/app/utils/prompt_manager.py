"""Prompt 管理器：通用标书生成流水线提示词。

本文件可直接替换 backend/app/utils/prompt_manager.py。

设计目标：
1. 适配完整投标文件、技术标/服务方案分册、商务卷、资格卷、报价卷等多种模式；
2. 不绑定任何单一行业；
3. 支持成熟投标文件样例反向建模、响应矩阵、目录生成、正文生成、图表素材规划、全文一致性审校；
4. 所有正文生成均以招标文件、响应矩阵和企业资料为事实源，企业材料缺失时只保留占位。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


def _json(data: Any, *, indent: int | None = None) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))


def get_full_bid_rulebook() -> str:
    """跨行业标书风控规则，供所有阶段复用。"""
    return """标书生成通用规则：

一、事实源与禁止虚构
1. 以招标文件原文为最高优先级依据。不得用通用经验、历史模板或样例文件覆盖招标文件的具体要求。
2. 招标文件、澄清/答疑/补遗、企业资料、历史案例之间冲突时，按“招标文件 > 澄清/答疑/补遗 > 企业已提供资料 > 企业知识库/历史材料 > 通用行业经验”处理。
3. 不得编造企业名称、资质、业绩、人员、金额、日期、证书编号、合同编号、发票信息、社保记录、信用查询结果、联系方式、报价、税率、服务期限、交付期限或承诺事项。
4. 未在招标文件或企业资料中出现的信息，必须使用：〖待补充：资料名称〗、〖待确认：事项〗、〖待提供扫描件：资料名称〗、〖待提供查询截图：事项〗、〖以招标文件要求为准〗、〖页码待编排〗。
5. 不得把“不满足、未提供、待确认”的事项写成“满足、已具备、已完成、已提供”。

二、投标文件编制要求、生成对象定位与格式硬约束
1. 招标文件中的“投标文件”“投标文件格式”“投标文件的组成”“投标文件的编制”“投标文件格式要求”“技术/服务/施工/供货/设计方案应包括”等章节，是目录生成、正文生成和导出审校的硬约束，优先级高于历史样例、通用模板和模型自由发挥。
2. 必须先做“生成对象定位”：从投标文件组成和投标文件格式中找出本次真正需要写正文的方案类组成项，例如“服务方案”“设计方案”“技术方案”“实施方案”“施工组织设计”“供货方案”“售后服务方案”等；不要把整章“投标文件格式”或整本投标文件误认为都要写。
3. 必须单独解析投标文件应包括哪些卷册、章节、表格、承诺函、证明材料和附件；同时必须写出 selected_generation_target，说明本次目录应基于哪个组成项生成，以及哪些完整投标文件组成项只做排除/审校提示。
4. 如果招标文件中有多个位置描述同一目标，例如“3.1.1（7）设计方案”和“第六章 六、设计方案”，应合并理解：前者用于确认生成对象，后者用于提取详细目录要求；如果第六章没有详细子项，则用第三章技术评分项作为目录基础。
5. 若用户目标是 full_bid，目录必须按招标文件“投标文件/投标文件格式”列明的顺序完整生成，不得遗漏投标函、授权/身份证明、联合体协议、保证金、报价、资格审查资料、技术/服务/设计方案、其他资料、偏差表等必需项；不适用章节应保留“不适用/本项目不适用”处理规则或按招标文件要求处理。
6. 若用户目标是 technical_only、technical_service_plan、service_plan 或未明确但存在 selected_generation_target，只生成 selected_generation_target 对应的方案分册/方案章节，不得混入投标函、报价、保证金、资格审查资料等完整投标文件正文。
7. 对招标文件明确给出的固定表格和固定格式，必须保留表头、列名、固定文字、顺序、签章栏、日期栏和附件说明；只允许填写空白项或使用占位符，不得擅自改写格式含义。
8. 对标注“以上内容仅供参考模板，可以根据投标人情况自行拟定”的方案类内容，可以扩展和优化，但必须覆盖其列明的全部要点，且不得与评分办法、实质性条款和卷册隔离规则冲突。

三、格式、签章与实质性响应
1. 对“★”“*”“▲”“实质性要求”“不允许偏离”“投标无效”“废标”“否决投标”“资格审查不通过”“必须”“不得”“应当”等内容，必须单独识别、编号、响应和审校。
2. 标注为“实质性格式”“固定格式”“不得修改格式”“必须按格式填写”的投标函、报价表、费用明细表、授权委托书、承诺函、偏离表、声明函、资格表、人员表、业绩表等，不得改变表头、列名、固定文字、行列结构和选择项。
3. 对签字、签章、电子签章、骑缝章、法定代表人或授权代表签署、日期、附件扫描件等要求，必须建立检查项。
4. 对暗标、双盲、匿名技术标，如招标文件有要求，正文不得出现企业名称、人员姓名、业绩名称、联系方式、Logo、商标、可识别图片、页眉页脚异常、隐藏超链接等身份识别信息。

四、报价与卷册隔离
1. 报价文件必须严格服从招标文件规定的报价方式、币种、税率、含税/不含税口径、小数位、总价/单价、唯一报价、最高限价、分项报价、费用包含范围和算术修正规则。
2. 如招标文件要求价格文件单独成册，或不得出现在技术/商务/暗标文件中，必须在目录、正文和审校中强制隔离。
3. 未提供报价信息时，不得生成具体金额，只能保留 〖待补充：报价金额/分项报价〗。

五、证据链
1. 业绩证据链应区分：合同关键页、中标通知书、验收证明、发票、税务查验截图、业主证明、框架协议、订单/任务书；仅有历史案例文字不得自动认定为有效证明材料。
2. 人员证据链应关注：身份证、学历、职称/注册证、劳动合同、社保、退休返聘协议、人员业绩、证书有效期。
3. 信用与资质证据链应关注：查询平台、查询对象、查询日期、截图页面、资质有效期、年检状态和承诺函。
4. 货物类项目应关注：厂家授权、检测报告、合格证、参数证明、供货能力、售后网点、备品备件、质保承诺。
5. 工程类项目应关注：施工资质、安全生产许可证、项目经理证书、施工组织、机械设备、质量安全文明施工、进度计划。
6. 服务类项目应关注：服务团队、服务流程、响应时限、质量保障、沟通机制、应急预案、成果交付和保密承诺。

六、评分点写作
1. 技术/服务/实施方案必须围绕评分细则逐条展开，不能只做空泛宣传。
2. 每个评分点至少形成一个明确的响应章节或段落，并说明：响应措施、实施步骤、人员/资源、质量控制、进度控制、风险控制、交付成果、支撑材料。
3. 分值高、实质性强、容易失分的评分项，应获得更高目录层级、更长篇幅和更细颗粒度响应。
4. 同级章节必须分工明确；不得重复生成同质化段落。

七、输出约束
1. 要求 JSON 时，只输出合法 JSON，不输出 markdown 代码块、解释语、前后缀。
2. 要求正文时，只输出当前章节正文，不输出标题、提示语、AI 自述、解释过程。
3. 页码、附件页码、响应页码在最终 Word 排版前统一使用 〖页码待编排〗。
"""


def _node(
    id_: str,
    title: str,
    desc: str,
    children: List[Dict[str, Any]] | None = None,
    *,
    chapter_type: str = "technical",
    expected_depth: str = "medium",
    scoring: List[str] | None = None,
    req: List[str] | None = None,
    material: List[str] | None = None,
    blocks: List[str] | None = None,
    source_type: str = "template_expansion",
) -> Dict[str, Any]:
    blocks = blocks or ["paragraph"]
    return {
        "id": id_,
        "volume_id": "V-TECH",
        "title": title,
        "description": desc,
        "chapter_type": chapter_type,
        "source_type": source_type,
        "fixed_format_sensitive": False,
        "price_sensitive": False,
        "anonymity_sensitive": False,
        "enterprise_required": bool(material),
        "asset_required": any(b in {"image", "org_chart", "workflow_chart"} for b in blocks),
        "expected_depth": expected_depth,
        "expected_word_count": {"short": 500, "medium": 1200, "long": 2400, "very_long": 3800}.get(expected_depth, 1200),
        "expected_blocks": blocks,
        "scoring_item_ids": scoring or [],
        "requirement_ids": req or [],
        "risk_ids": [],
        "material_ids": material or [],
        "response_matrix_ids": [],
        "children": children or [],
    }


def get_generic_service_plan_outline_template() -> List[Dict[str, Any]]:
    """服务/技术方案分册的跨行业保底目录。具体目录应优先由模型按招标文件生成。"""
    return [
        _node("1", "项目理解与服务范围", "准确响应招标范围、服务/实施内容、服务地点、服务期限、交付成果和边界条件。", [
            _node("1.1", "项目背景与需求理解", "结合招标文件说明项目背景、采购目标、需求边界和响应重点。", expected_depth="short", source_type="tender_direct_response"),
            _node("1.2", "服务范围与服务内容", "逐项响应招标文件规定的服务、供货、施工、运维、咨询或设计内容。", source_type="tender_direct_response"),
            _node("1.3", "成果交付与服务标准", "说明交付物、验收口径、服务标准、质量要求和时限要求。", source_type="tender_direct_response"),
        ], source_type="tender_direct_response"),
        _node("2", "工作目标与响应承诺", "从质量、进度、服务、安全、合规、成本或交付目标等维度作出可核验响应。", [
            _node("2.1", "质量目标", "明确成果质量、验收一次通过、缺陷控制和持续改进目标。"),
            _node("2.2", "进度目标", "响应招标文件的期限、节点、响应时限或交付周期。"),
            _node("2.3", "服务目标", "说明满意度、响应机制、问题闭环和协同目标。"),
        ]),
        _node("3", "组织机构与岗位职责", "说明项目组织机构、岗位职责、接口关系、管理机制和资源调配方式。", [
            _node("3.1", "项目组织机构", "输出组织机构图占位或结构化组织层级。", expected_depth="short", material=["M-人员组织"], blocks=["org_chart"]),
            _node("3.2", "岗位职责与协同关系", "逐项说明项目负责人、质量、进度、文档、专业人员或实施人员职责。", material=["M-人员组织"]),
        ], material=["M-人员组织"], blocks=["org_chart"]),
        _node("4", "实施方案", "技术/服务方案核心章节，覆盖总体思路、依据原则、实施方法、流程、资源、进度、质量、安全、风险和重点难点。", [
            _node("4.1", "总体思路", "概述项目策划、资源投入、组织协同、进度质量控制和成果交付。"),
            _node("4.2", "编制依据与实施原则", "结合招标文件、法律法规、行业规范、技术标准和企业管理体系。"),
            _node("4.3", "工作方法", "写清实施步骤、输入输出、过程控制、评审确认和变更控制。", expected_depth="long"),
            _node("4.4", "工作流程", "输出流程图占位或流程表，覆盖启动、执行、检查、交付、验收、归档。", blocks=["workflow_chart"]),
            _node("4.5", "资源投入计划", "输出人员、设备、软件、车辆、备品备件或服务工具等资源投入表；资料缺失时占位。", material=["M-资源投入"], blocks=["table"]),
            _node("4.6", "文档与资料管理", "说明资料接收、传递、版本、受控、归档、保密和页码索引。"),
            _node("4.7", "变更与风险管理", "说明需求变更、范围变更、进度变更、质量风险、安全风险的识别、审批和闭环。"),
            _node("4.8", "进度计划与保障措施", "响应招标文件节点要求，输出进度计划表、纠偏机制和必要承诺。", blocks=["table"]),
            _node("4.9", "重点难点分析及对策", "识别本项目关键难点、易失分点、履约风险并提出针对性措施。", expected_depth="long"),
        ], expected_depth="very_long"),
        _node("5", "拟投入人员、设备及支撑能力", "说明团队、人员、设备、软件、工具、场地、售后或运维能力。", [
            _node("5.1", "人员投入计划", "说明人员配置原则、专业分工、替换机制、社保/劳动关系等核验要求。", material=["M-人员表"]),
            _node("5.2", "拟投入人员表", "输出人员汇总表；缺少人员库时使用待补占位。", material=["M-人员表"], blocks=["table"]),
            _node("5.3", "设备、工具及软件投入", "输出设备、工具、车辆、软件、检测仪器、平台系统或备品备件清单。", material=["M-设备软件"], blocks=["table"]),
        ], material=["M-人员表", "M-设备软件"], blocks=["table"]),
        _node("6", "沟通协调与服务响应", "写组织协调、招标人沟通、内部沟通、会议管理、接口管理、响应时限和闭环机制。", [
            _node("6.1", "沟通协调机制", "写定期沟通、即时沟通、书面沟通、会议纪要、事项跟踪和闭环管理。"),
            _node("6.2", "服务响应机制", "写响应渠道、响应时限、升级机制、应急联系人和问题解决流程；联系方式缺失时占位。", material=["M-联系人"]),
            _node("6.3", "沟通与服务承诺", "输出沟通或服务承诺书，按招标文件和企业资料填写。", blocks=["commitment_letter"]),
        ], expected_depth="long"),
        _node("7", "质量保证及履约承诺", "覆盖质量目标、过程质量控制、验收控制、文件资料控制、内审/检查、持续改进、质量承诺和违约责任。", [
            _node("7.1", "质量保证体系", "说明质量管理组织、制度、程序、标准和责任分工。"),
            _node("7.2", "过程质量控制措施", "写输入、执行、检查、验证、确认、更改、验收全过程控制。", expected_depth="long"),
            _node("7.3", "成果验收与持续改进", "写验收标准、问题整改、复盘改进和客户满意度管理。"),
            _node("7.4", "服务质量承诺", "输出服务质量承诺书，包含质量、期限、安全、保密和交付深度等。", blocks=["commitment_letter"]),
            _node("7.5", "违约责任承诺", "如招标文件或评分项要求，输出违约责任承诺书。", blocks=["commitment_letter"]),
        ], expected_depth="very_long"),
        _node("8", "其他技术支撑与增值服务", "根据招标文件、评分项或样例风格展示管理制度、信息化工具、数字化能力、培训、售后、应急或可视化成果。", [
            _node("8.1", "企业管理制度", "如评分项要求，覆盖业务管理、行政、财务、人事、档案、职业道德、企业文化等制度。", material=["M-企业制度"]),
            _node("8.2", "信息化或数字化支撑", "如项目适用，写平台、软件、数据管理、数字化交付、远程协同等能力；资料缺失时占位。", material=["M-数字化能力"], blocks=["image", "table"]),
            _node("8.3", "成果展示或案例素材", "如评分项或样例要求插入图片、效果图、系统截图、证书或案例素材，缺失时只输出占位。", material=["M-图片素材"], blocks=["image"]),
        ], material=["M-企业制度", "M-图片素材"], blocks=["image"]),
    ]


def get_design_service_outline_template() -> List[Dict[str, Any]]:
    """兼容旧调用。现在返回通用服务/技术方案模板，而非单一行业专项模板。"""
    return get_generic_service_plan_outline_template()


def get_reference_bid_style_profile_schema() -> Dict[str, Any]:
    return {
        "profile_name": "",
        "document_scope": "full_bid | technical_only | technical_service_plan | service_plan | business_volume | qualification_volume | price_volume | unknown",
        "recommended_use_case": "",
        "cover_profile": {
            "has_cover": True,
            "title_pattern": "",
            "project_name_position": "",
            "bidder_name_position": "",
            "signature_seal_position": "",
            "date_format": "YYYY年MM月DD日",
        },
        "toc_profile": {
            "has_toc": True,
            "toc_depth": 2,
            "page_number_required": True,
            "toc_should_be_generated_by_word": True,
        },
        "outline_template": [
            {
                "id": "1",
                "title": "",
                "level": 1,
                "children": [],
                "source_type": "tender_mapped | scoring_response | enterprise_showcase | profile_expansion | fixed_form | material_attachment",
                "scoring_purpose": "",
                "expected_depth": "short | medium | long | very_long",
                "tables_required": [],
                "image_slots": [],
                "enterprise_required": False,
                "asset_required": False,
            }
        ],
        "writing_style": {
            "voice": "第一人称公司主体，如“我公司”",
            "tone": "正式、承诺式、专业投标文件语气",
            "paragraph_style": "条理化分点",
            "common_patterns": [],
            "forbidden_patterns": ["AI自述", "泛泛宣传", "历史项目残留"],
        },
        "section_generation_rules": [
            {
                "chapter_title": "",
                "content_source_priority": ["tender_analysis", "enterprise_profile", "template_library", "asset_library"],
                "must_include": [],
                "must_not_include": [],
                "table_or_asset_policy": "",
            }
        ],
        "table_models": [
            {
                "chapter_title": "",
                "table_name": "",
                "columns": [],
                "rows_policy": "",
                "enterprise_required": False,
            }
        ],
        "image_slots": [
            {
                "chapter_title": "",
                "slot_name": "",
                "asset_type": "org_chart | workflow_chart | software_screenshot | product_image | project_rendering | certificate_image | other",
                "asset_required": True,
                "fallback_placeholder": "〖插入图片：图片名称〗",
            }
        ],
        "enterprise_data_requirements": [
            {"name": "", "used_by_chapters": [], "required": True, "fallback": "〖待补充：资料名称〗"}
        ],
        "quality_risks": [{"risk": "", "location": "", "fix_rule": ""}],
    }



def get_bid_document_requirements_schema() -> Dict[str, Any]:
    """招标文件中“投标文件/投标文件格式/投标文件组成/编制要求”的专门解析模板。"""
    return {
        "source_chapters": [
            {
                "id": "BD-SRC-01",
                "chapter_title": "",
                "location": "章节/页码/条款/表格",
                "excerpt": "不超过120字原文摘录",
            }
        ],
        "document_scope_required": "full_bid | technical_volume | service_plan_volume | business_volume | qualification_volume | price_volume | unknown",
        "composition": [
            {
                "id": "BD-01",
                "order": 1,
                "title": "",
                "required": True,
                "applicability": "required | optional | not_applicable | conditional",
                "volume_id": "",
                "chapter_type": "cover | toc | form | authorization | bond | price | qualification | business | technical | service_plan | construction_plan | goods_supply | design_plan | deviation_table | commitment | other",
                "fixed_format": False,
                "allow_self_drafting": False,
                "signature_required": False,
                "seal_required": False,
                "attachment_required": False,
                "price_related": False,
                "anonymity_sensitive": False,
                "source_ref": "BD-SRC-01",
                "must_keep_text": [],
                "must_keep_columns": [],
                "fillable_fields": [],
                "children": [],
            }
        ],
        "scheme_or_technical_outline_requirements": [
            {
                "id": "BD-SP-01",
                "parent_title": "服务方案/设计方案/技术方案/施工组织设计/供货方案/实施方案",
                "order": 1,
                "title": "",
                "required": True,
                "allow_expand": True,
                "source_ref": "BD-SRC-01",
                "target_chapter_hint": "",
            }
        ],
        "selected_generation_target": {
            "target_id": "BD-07",
            "target_title": "服务方案/设计方案/技术方案/施工组织设计/供货方案/实施方案",
            "parent_composition_id": "BD-07",
            "target_source": "3.1.1(7)设计方案 / 第六章七服务方案 / 第六章六设计方案 等",
            "target_source_type": "composition_item | format_section | scoring_section | user_selected | inferred",
            "generation_scope": "scheme_section_only | full_bid | volume_only | unknown",
            "use_as_outline_basis": True,
            "base_outline_strategy": "scheme_outline | format_section_children | technical_scoring_items | reference_profile_fallback | generic_fallback",
            "base_outline_items": [
                {
                    "id": "BD-SP-01",
                    "order": 1,
                    "title": "招标文件列明的方案子项或评分项标题",
                    "source_ref": "BD-SRC-01",
                    "derived_from": "scheme_or_technical_outline_requirements | technical_scoring_items | reference_profile",
                    "must_preserve_title": True,
                }
            ],
            "excluded_composition_item_ids": [],
            "excluded_composition_titles": [],
            "selection_reason": "",
            "confidence": "high | medium | low",
        },
        "fixed_forms": [
            {
                "id": "BD-FF-01",
                "form_name": "",
                "belongs_to": "BD-01",
                "must_keep_columns": [],
                "must_keep_text": [],
                "fillable_fields": [],
                "signature_required": False,
                "seal_required": False,
                "date_required": False,
                "source_ref": "BD-SRC-01",
            }
        ],
        "formatting_and_submission_rules": {
            "language": "",
            "toc_required": False,
            "page_number_required": False,
            "binding_or_upload_rules": "",
            "electronic_signature_rules": "",
            "encryption_or_platform_rules": "",
            "source_ref": "",
        },
        "excluded_when_generating_technical_only": [],
        "priority_rule": "先定位本次要生成的方案类组成项，再生成该组成项下的目录；投标文件编制要求优先于样例风格。",
    }


def get_analysis_report_schema() -> Dict[str, Any]:
    """结构化标准解析报告 JSON 模板。字段兼容 models.schemas.AnalysisReport。"""
    return {
        "project": {
            "name": "", "number": "", "package_name": "", "package_or_lot": "", "purchaser": "", "agency": "",
            "procurement_method": "", "project_type": "", "budget": "", "maximum_price": "", "funding_source": "",
            "service_scope": "", "service_period": "", "service_location": "", "quality_requirements": "",
            "bid_validity": "", "bid_bond": "", "performance_bond": "", "bid_deadline": "", "opening_time": "",
            "submission_method": "", "electronic_platform": "", "submission_requirements": "", "signature_requirements": "",
        },
        "bid_mode_recommendation": "technical_only",
        "source_refs": [{"id": "SRC-01", "location": "章节/页码/表格/条款", "excerpt": "不超过120字原文摘录", "related_ids": ["T-01"]}],
        "bid_document_requirements": get_bid_document_requirements_schema(),
        "volume_rules": [{"id": "V-TECH", "name": "技术标/服务方案", "scope": "", "separate_submission": False, "price_allowed": False, "anonymity_required": False, "seal_signature_rule": "", "source": ""}],
        "anonymity_rules": {"enabled": False, "scope": "", "forbidden_identifiers": [], "formatting_rules": [], "source": ""},
        "bid_structure": [{"id": "S-01", "parent_id": "", "title": "", "purpose": "", "category": "资格/商务/技术/报价/承诺/附件/服务方案/实施方案", "volume_id": "V-TECH", "required": True, "fixed_format": False, "signature_required": False, "attachment_required": False, "seal_required": False, "price_related": False, "anonymity_sensitive": False, "source": ""}],
        "formal_review_items": [{"id": "E-01", "review_type": "形式评审", "requirement": "", "criterion": "", "required_materials": [], "risk": "", "target_chapters": [], "source": "", "invalid_if_missing": False}],
        "qualification_review_items": [{"id": "E-02", "review_type": "资格评审", "requirement": "", "criterion": "", "required_materials": [], "risk": "", "target_chapters": [], "source": "", "invalid_if_missing": False}],
        "responsiveness_review_items": [{"id": "E-03", "review_type": "响应性评审", "requirement": "", "criterion": "", "required_materials": [], "risk": "", "target_chapters": [], "source": "", "invalid_if_missing": False}],
        "business_scoring_items": [{"id": "B-01", "name": "", "score": "", "standard": "", "source": "", "evidence_requirements": [], "writing_focus": "", "easy_loss_points": []}],
        "technical_scoring_items": [{"id": "T-01", "name": "", "score": "", "standard": "", "source": "", "writing_focus": "", "evidence_requirements": [], "easy_loss_points": []}],
        "price_scoring_items": [{"id": "P-01", "name": "", "score": "", "logic": "", "source": "", "risk": ""}],
        "price_rules": {"quote_method": "", "currency": "", "maximum_price_rule": "", "abnormally_low_price_rule": "", "separate_price_volume_required": False, "price_forbidden_in_other_volumes": False, "tax_requirement": "", "decimal_places": "", "uniqueness_requirement": "", "form_requirements": "", "arithmetic_correction_rule": "", "missing_item_rule": "", "prohibited_format_changes": [], "source_ref": ""},
        "qualification_requirements": [{"id": "Q-01", "name": "", "requirement": "", "source": "", "required_materials": []}],
        "formal_response_requirements": [{"id": "F-01", "name": "", "requirement": "", "source": "", "fixed_format": False, "signature_required": False, "attachment_required": False}],
        "mandatory_clauses": [{"id": "C-01", "clause": "", "source": "", "response_strategy": "", "invalid_if_not_responded": False}],
        "rejection_risks": [{"id": "R-01", "risk": "", "trigger": "", "source": "", "mitigation": "", "blocking": True}],
        "fixed_format_forms": [{"id": "FF-01", "name": "", "volume_id": "", "source": "", "required_columns": [], "must_keep_columns": [], "must_keep_text": [], "fillable_fields": [], "fixed_text": "", "fill_rules": "", "seal_required": False}],
        "signature_requirements": [{"id": "SIG-01", "target": "", "signer": "", "seal": "", "date_required": False, "electronic_signature_required": False, "source": "", "risk": ""}],
        "evidence_chain_requirements": [{"id": "EV-01", "target": "企业业绩/人员/资质/信用/发票/产品参数/检测报告/其他", "required_evidence": [], "validation_rule": "", "source": "", "risk": ""}],
        "required_materials": [{"id": "M-01", "name": "", "purpose": "", "source": "", "status": "missing", "used_by": [], "volume_id": ""}],
        "missing_company_materials": [{"id": "X-01", "name": "", "used_by": [], "placeholder": "〖待补充：具体资料名称〗", "blocking": False}],
        "generation_warnings": [{"id": "W-01", "warning": "", "severity": "warning", "related_ids": []}],
        "response_matrix": get_response_matrix_schema(),
        "reference_bid_style_profile": {},
        "document_blocks_plan": {},
    }


def get_response_matrix_schema() -> Dict[str, Any]:
    return {
        "items": [
            {
                "id": "RM-01",
                "source_item_id": "T-01",
                "source_type": "scoring/review/mandatory/risk/material/format/signature/evidence/price/selected_generation_target/selected_outline_item/excluded_full_bid_section/profile_expansion",
                "requirement_summary": "",
                "response_strategy": "",
                "target_chapter_ids": [],
                "required_material_ids": [],
                "risk_ids": [],
                "source_refs": [],
                "priority": "high",
                "status": "pending",
                "blocking": False,
            }
        ],
        "uncovered_ids": [],
        "high_risk_ids": [],
        "coverage_summary": "",
    }


def get_document_blocks_schema() -> Dict[str, Any]:
    return {
        "document_blocks": [
            {
                "chapter_id": "",
                "chapter_title": "",
                "blocks": [
                    {
                        "block_type": "paragraph | table | org_chart | workflow_chart | image | commitment_letter | material_attachment | page_break",
                        "block_name": "",
                        "data_source": "tender | enterprise_profile | staff_roster | equipment_library | asset_library | generated | manual",
                        "required": True,
                        "asset_id": "",
                        "placeholder": "",
                        "table_schema": {"columns": [], "row_policy": ""},
                        "chart_schema": {"nodes": [], "edges": []},
                        "commitment_schema": {"to": "", "items": [], "signer": "{bidder_name}", "date": "{bid_date}"},
                    }
                ],
            }
        ],
        "missing_assets": [{"chapter_id": "", "asset_name": "", "fallback_placeholder": ""}],
        "missing_enterprise_data": [{"chapter_id": "", "data_name": "", "fallback_placeholder": ""}],
    }


def get_review_report_schema() -> Dict[str, Any]:
    return {
        "coverage": [{"item_id": "T-01", "target_type": "scoring", "covered": True, "chapter_ids": [], "issue": "", "evidence": "", "fix_suggestion": ""}],
        "missing_materials": [{"material_id": "M-01", "material_name": "", "used_by": [], "chapter_ids": [], "placeholder": "〖待补充：资料名称〗", "placeholder_found": True, "fix_suggestion": ""}],
        "rejection_risks": [{"risk_id": "R-01", "handled": False, "issue": ""}],
        "duplication_issues": [{"chapter_ids": [], "issue": ""}],
        "fabrication_risks": [{"chapter_id": "", "text": "", "reason": "", "fix_suggestion": ""}],
        "fixed_format_issues": [],
        "signature_issues": [],
        "price_rule_issues": [],
        "evidence_chain_issues": [],
        "page_reference_issues": [],
        "anonymity_issues": [],
        "blocking_issues": [],
        "warnings": [],
        "revision_plan": {"actions": [{"id": "RP-01", "target_chapter_ids": [], "action_type": "补写/替换/删减/补材料/人工确认", "instruction": "", "priority": "high", "related_issue_ids": [], "blocking": True}], "summary": ""},
        "summary": {"ready_to_export": False, "blocking_issues": 0, "warnings": 0, "blocking_issues_count": 0, "warnings_count": 0, "coverage_rate": 0, "blocking_summary": "", "next_actions": []},
    }


def get_consistency_revision_schema() -> Dict[str, Any]:
    return {
        "ready_for_export": False,
        "issues": [
            {"id": "ISS-01", "severity": "blocking | high | medium | low", "issue_type": "project_name | tenderer_name | bidder_name | date | service_period | schedule_commitment | historical_residue | hallucination | scope_error | missing_block | scoring_coverage | other", "chapter_id": "", "original_text": "", "problem": "", "fix_suggestion": ""}
        ],
        "coverage_check": [{"requirement_or_scoring_id": "", "covered": True, "chapter_ids": [], "comment": ""}],
        "missing_blocks": [{"chapter_id": "", "block_name": "", "fix_suggestion": ""}],
        "summary": {"blocking_count": 0, "high_count": 0, "can_export_after_auto_fix": False, "manual_data_needed": []},
    }


def generate_reference_bid_style_profile_prompt(reference_bid_text: str) -> Tuple[str, str]:
    schema_json = _json(get_reference_bid_style_profile_schema(), indent=2)
    system_prompt = f"""你是投标文件样例反向建模专家。你的任务不是总结内容，而是从成熟投标文件样例中提取可复用的生成规则。

必须识别：文件范围、封面规则、目录层级、章节结构、正文风格、表格样式、承诺书样式、图文素材位置、企业资料依赖、图片素材依赖、质量风险。

硬性要求：
1. 只输出合法 JSON，不输出 markdown。
2. 不要照抄样例正文，不要改写样例正文。
3. 必须保留原始目录层级和特殊块类型。
4. 对“应由企业资料提供”的内容标记 enterprise_required=true。
5. 对“应由图片/附件素材库提供”的内容标记 asset_required=true。
6. 如果样例中存在历史项目残留、日期不一致、投标人名称不一致、错别字、行业错配内容，写入 quality_risks，后续生成时应修正而不是照抄。
7. 不得把样例所在行业固化为所有项目的默认行业；只提取风格与结构。

JSON schema：
{schema_json}
"""
    user_prompt = f"""请解析以下目标投标文件样例，生成 ReferenceBidStyleProfile JSON。

<reference_bid_text>
{reference_bid_text}
</reference_bid_text>

直接返回 JSON。"""
    return system_prompt, user_prompt


def generate_analysis_report_prompt(file_content: str) -> Tuple[str, str]:
    schema_json = _json(get_analysis_report_schema(), indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是资深招标文件解析专家。你的任务是把招标文件解析为可供后续目录生成、正文生成、图表素材规划和合规审校复用的 AnalysisReport JSON。

硬性要求：
1. 只输出合法 JSON，不输出 markdown。
2. 不得编造招标文件未出现的信息；缺失信息填空字符串、空数组或 null。
3. 所有关键条目必须尽量填写 source 或 source_ref，写明章节名、条款号、页码、表格名或短原文。
4. 对“★、*、▲、实质性要求、不允许偏离、废标、投标无效、否决投标、资格不通过、必须、不得、应当”等高风险内容必须单独提取。
5. 对固定格式表单、签字盖章、报价文件、偏离表、承诺函、授权委托书、资格证明材料、暗标要求必须单独提取。
6. 必须定位并解析招标文件中名称类似“投标文件”“投标文件格式”“投标文件的组成”“投标文件的编制”“投标文件格式要求”“技术方案/服务方案/设计方案/施工组织设计/供货方案应包括”的章节；解析结果写入 bid_document_requirements，不能只写入普通说明。
7. bid_document_requirements.composition 必须反映投标文件要求的章节顺序、必交/不适用/可选状态、固定格式、签字盖章、附件、报价相关、暗标敏感等属性。
8. 必须生成 bid_document_requirements.selected_generation_target：
   - 如果“投标文件组成”中有“服务方案/设计方案/技术方案/实施方案/施工组织设计/供货方案”等方案类项，且用户未明确要求 full_bid，应把该方案类项选为本次目录生成对象；
   - 如果同时存在“3.1.1（7）设计方案”和“第六章 六、设计方案”，应把二者合并为同一 target，3.1.1 用于确认它是投标文件组成项，第六章用于提取详细格式或提纲；
   - 如果第六章只列出“设计方案/服务方案”但没有子项，则 selected_generation_target.base_outline_strategy="technical_scoring_items"，后续目录按技术评分项展开；
   - 如果第六章或格式章节写明“设计方案应包括/服务方案应包括”，必须将这些子项写入 base_outline_items，后续目录优先逐项采用这些标题。
9. 如果方案类章节写有“应包括但不限于”或“服务纲要应包括”，必须逐项写入 bid_document_requirements.scheme_or_technical_outline_requirements，并作为后续技术/服务分册目录硬约束。
10. 必须识别推荐输出范围 bid_mode_recommendation，可用值：full_bid、technical_only、technical_service_plan、service_plan、business_volume、qualification_volume、price_volume。默认情况下，只要存在 selected_generation_target 且用户没有要求完整标书，bid_mode_recommendation 应推荐 technical_only/technical_service_plan/service_plan，而不是 full_bid。
11. 完整投标文件格式要求、技术/服务/设计方案要求、商务/资格/报价要求要分卷册识别；如果目标只是方案分册，不要把商务、报价、资格强行放入技术目录，但要保留为 selected_generation_target.excluded_composition_titles、excluded_when_generating_technical_only、volume_rules 或审校信息。
12. 评分项按 technical_scoring_items、business_scoring_items、price_scoring_items 分类；资格/形式/响应性评审单独分类。
   - 技术评分、商务评分、其他/价格评分必须按原评分表逐行提取，不得合并成一个总条目。
   - 每个评分项必须填写 name、score、standard/source；standard 内必须保留该行的全部子项、扣分规则、满分条件、最低分规则和证明材料要求。
   - 如果同一评分项下有多个子项或分档规则，standard 用换行、序号或分号拆开，保证前端能显示为“评分项 / 分值 / 得分要求”三列表格。
   - 不允许只写“按招标文件执行”“详见评分办法”；必须摘录该评分行的实际得分要求。
   - 其他评分、信用扣分、失信行为扣分、报价公式、价格分、经营场所、管理制度等不属于技术/商务主观评分的条目，统一放入 price_scoring_items，用 name 标明原评分项名称。
13. 报价规则、报价隔离、暗标、证据链、签章、固定格式、投标文件格式章节是高风险项，不得合并丢失。
14. 为避免 JSON 截断，普通数组最多输出最关键 10 项；但 technical_scoring_items、business_scoring_items、price_scoring_items 和 bid_document_requirements.composition 不受 10 项限制，应尽量完整保留原表行，最多 40 项。
15. 必须同步生成 response_matrix 初稿；如果条目很多，可覆盖高分值、高风险、阻塞项和投标文件格式硬约束。
16. 解析粒度要支撑前端按“基础信息、资格审查、技术评分、商务评分、其他评分、无效标与废标项、投标文件要求、开评定标流程、补充信息归纳”九类页签展示；不要把这些内容合并成一段概述。
17. 必须优先定位“服务纲要/技术规格/评分办法/合同服务范围/资格要求/响应性条款”等关键章节，再分片抽取；同一要求如果同时出现在投标文件组成和具体格式章节，应在 source 或 source_ref 中同时体现。
18. 每个评分项、资格项、响应性条款、废标项、格式/签章/材料要求都要带可核验原文证据，source 不得只写“招标文件”这类泛称，至少包含章节名、条款号、表格名、页码或短原文之一。
19. 参考以下文件解析视角进行归纳，但输出仍必须符合 AnalysisReport JSON schema：
   - 基础信息固定子项：招标人/代理信息、项目信息、关键时间/内容、保证金相关、其他信息。缺失字段用空字符串，不得臆测。
   - 资格审查固定子项：资格评审、形式评审标准、响应性评审标准；其中资格评审内部必须尽量覆盖资质条件、业绩要求、财务要求、信誉要求、人员资格要求、联合体投标要求、安全生产许可证要求、投标资格评审否决项、营业执照要求、认证体系要求、企业荣誉要求、企业信用要求、人员业绩要求、其他资料要求。
   - 技术评分/商务评分/其他评分：必须输出三列表格所需字段，即评分项、分值、得分要求；每个评分项的得分要求要包含子项、材料、满分/扣分/最低分规则。技术评分放 technical_scoring_items；商务评分放 business_scoring_items；失信扣分、报价公式、价格分、其他扣分规则等放 price_scoring_items。
   - 无效标与废标项：专项提取所有“无效、否决、废标、不予受理、不得分、扣分、不接受、必须、须、不得、未响应、实质性偏离”等条款，并写触发条件和后果。
   - 投标文件要求固定子项：投标文件组成、投标报价要求、投标文件递交方式、方案要求；签章盖章、附件模板、固定格式、格式不得修改要求要归入对应子项或 fixed_format/signature/material 字段。
   - 开评定标流程固定子项：开标、评标、定标、后续要求，按流程顺序提取；涉及澄清、修正、异议、公示、合同签订、履约等放入对应流程。
   - 补充信息归纳固定子项：技术规格、合同时间、项目背景、方案与格式要求、其他特殊要求、样品要求、付款方式、中标份额分配规则、中标数量规则。没有扫描到的内容保持空值，不要编造。

{rulebook}

JSON schema：
{schema_json}
"""
    user_prompt = f"""请解析以下招标文件内容，输出 AnalysisReport JSON。

<tender_file_content>
{file_content}
</tender_file_content>

直接返回 JSON。"""
    return system_prompt, user_prompt


def generate_response_matrix_prompt(analysis_report: Dict[str, Any], reference_bid_style_profile: Dict[str, Any] | None = None) -> Tuple[str, str]:
    schema_json = _json(get_response_matrix_schema(), indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是投标响应矩阵规划专家。你的任务是把 AnalysisReport 转换为 ResponseMatrix JSON，并在有样例风格时吸收其结构习惯。

目标：
1. 确保每个评分项、资格项、形式项、响应性条款、实质性条款、废标风险、固定格式、签章要求、报价规则、证明材料都有对应响应策略。
2. 必须把 AnalysisReport.bid_document_requirements.composition、scheme_or_technical_outline_requirements、selected_generation_target 纳入矩阵；这些条目是目录和正文生成的硬约束。
3. 如果 selected_generation_target.generation_scope="scheme_section_only"，矩阵必须把选中的方案类组成项和 base_outline_items 作为正文生成主线；其他投标函、保证金、报价、资格资料等完整标书组成项只能作为 excluded 或 material/human_confirm，不得映射成技术目录正文。
4. 识别哪些内容可以生成正文，哪些必须填表，哪些必须附材料，哪些必须人工确认，哪些只允许出现在报价卷。
5. 为后续目录、正文、图表块和审校提供强映射关系。

硬性要求：
1. 只输出合法 JSON。
2. 不得新增 AnalysisReport 中不存在的强制条款 ID。
3. 对 blocking=true 的风险必须给出响应章节建议和处理策略。
4. 评分项 source_item_id 引用 T/B/P；评审/资格/形式/实质性条款引用 E/Q/F/C；风险引用 R；固定格式/签章/证据链/材料引用 FF/SIG/EV/M/X。
5. 报价、金额、税率缺失时不得生成具体数值。
6. 可根据 ReferenceBidStyleProfile 增加 profile_expansion 类型条目，但必须说明它是样例扩展，不得伪装为招标文件强制要求。
7. 如果用户目标为 full_bid，composition 中 required=true 且 applicability != not_applicable 的项目必须有矩阵条目；如果用户目标为技术/服务/方案分册，selected_generation_target.base_outline_items 和 scheme_or_technical_outline_requirements 中 required=true 的项目必须有矩阵条目。
8. 固定格式表单、签章、盖章、日期、附件、偏差表、报价表等格式项必须标记 response_method 为 fill_form/material_attachment/human_confirm 或在 response_strategy 中明确不得自由改写。

{rulebook}

JSON schema：
{schema_json}
"""
    user_prompt = f"""请基于以下 AnalysisReport 和 ReferenceBidStyleProfile 生成 ResponseMatrix。

<analysis_report_json>
{_json(analysis_report or {}, indent=2)}
</analysis_report_json>

<reference_bid_style_profile_json>
{_json(reference_bid_style_profile or {}, indent=2)}
</reference_bid_style_profile_json>

直接返回 JSON。"""
    return system_prompt, user_prompt


def generate_level1_outline_prompt(
    overview: str,
    requirements: str,
    analysis_report: Dict[str, Any] | None,
    bid_mode: str | None,
    schema_json: str,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    report = analysis_report or {}
    response_matrix = report.get("response_matrix") or {}
    rulebook = get_full_bid_rulebook()
    service_template = _json(get_generic_service_plan_outline_template(), indent=2)
    system_prompt = f"""你是资深投标文件目录规划专家。你的任务是根据 AnalysisReport、ResponseMatrix、用户目标和可选样例风格，生成一级目录 JSON。

硬性要求：
1. 只输出合法 JSON，不输出 markdown。
2. 不得重新解析招标文件；只能使用传入的 AnalysisReport 和 ResponseMatrix。
3. 目录必须服从 bid_document_requirements、selected_generation_target、volume_rules、bid_structure、报价隔离、暗标/匿名和固定格式要求；其中 selected_generation_target 和 bid_document_requirements 的优先级最高。
4. 目录生成前必须先判断本次输出范围：
   - full_bid：按 bid_document_requirements.composition 的顺序生成整本投标文件目录；
   - technical_only/technical_service_plan/service_plan 或未明确但 selected_generation_target.use_as_outline_basis=true：只生成 selected_generation_target 对应的方案分册/方案章节目录；
   - price_volume/qualification_volume/business_volume：只生成对应卷册。
5. 当只生成方案分册时，不得生成完整投标文件中的投标函、报价、保证金、资格审查资料、偏差表等正文卷册；这些应进入 selected_generation_target.excluded_composition_titles、描述或 coverage_summary。
6. 方案分册目录的标题依据优先级：
   A. selected_generation_target.base_outline_items 中 must_preserve_title=true 的标题；
   B. bid_document_requirements.scheme_or_technical_outline_requirements；
   C. 技术/服务详细评分项 technical_scoring_items；
   D. ReferenceBidStyleProfile 的同类目录风格；
   E. 通用服务/技术方案保底目录。
7. 如果招标文件只在“3.1.1（7）设计方案”列出生成对象，又在第六章“六、设计方案”列出“应包括”的十项内容，应以这十项内容作为目录一级或主要二级标题。
8. 如果第六章没有列出方案子项，则用第三章详细技术评分项作为目录主线，例如“进度管理及保证措施、质量管理及保证措施、内部审查程序、文档管理计划与控制措施”等。
9. 如果有 ReferenceBidStyleProfile，只能吸收其目录层级、标题风格、表格/承诺/图片位置；不得机械照抄行业特定内容、历史项目残留，也不得覆盖招标文件确定的 selected_generation_target。
10. 每个一级节点必须包含：id、volume_id、title、chapter_type、description、fixed_format_sensitive、price_sensitive、anonymity_sensitive、expected_word_count、scoring_item_ids、requirement_ids、risk_ids、material_ids、response_matrix_ids、children。
11. scoring_item_ids 只能放 T/B/P；requirement_ids 放 E/Q/F/C；risk_ids 放 R；material_ids 放 M/X/EV/FF/SIG。
12. 分值高、阻塞风险高、证据链复杂的章节应有更高 expected_word_count 和更细 children。
13. 目录标题应优先采用招标文件“投标文件/投标文件格式”中的章节名称；只有在招标文件允许自拟或仅给出参考纲要时，才可按样例风格优化标题。
14. 不生成正文。

通用服务/技术方案保底目录参考，仅在招标文件适合服务/技术方案分册且无更明确格式时参考：
{service_template}

{rulebook}

输出 JSON schema：
{schema_json}
"""
    user_prompt = f"""请生成一级目录 JSON。允许每个一级目录直接携带 children；如果有成熟样例目录，请在符合招标文件的前提下吸收其结构。

<overview>{overview}</overview>
<requirements>{requirements}</requirements>
<bid_mode>{bid_mode or report.get('bid_mode_recommendation') or ''}</bid_mode>
<analysis_report_json>{_json(report, indent=2)}</analysis_report_json>
<response_matrix_json>{_json(response_matrix, indent=2)}</response_matrix_json>
<reference_bid_style_profile_json>{_json(reference_bid_style_profile or report.get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile_json>
<document_blocks_plan_json>{_json(document_blocks_plan or report.get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan_json>

直接返回 JSON 对象或 JSON 数组。"""
    return system_prompt, user_prompt


def generate_level23_outline_prompt(
    current_outline_json: Dict[str, Any],
    other_outline: str,
    overview: str,
    requirements: str,
    analysis_report: Dict[str, Any] | None,
    bid_mode: str | None,
    response_matrix: Dict[str, Any] | None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    schema_json = _json(current_outline_json, indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是标书二三级目录设计专家。当前阶段只补全当前一级章节的 children、description、映射字段和预期内容块，不生成正文。

硬性要求：
1. 禁止修改当前一级章节 id、title、volume_id、chapter_type。
2. 不得新增 AnalysisReport 和 ResponseMatrix 中不存在的强制条款 ID。
3. 如果当前一级章节在 selected_generation_target.base_outline_items、bid_document_requirements.composition 或 scheme_or_technical_outline_requirements 中有对应要求，二三级目录必须覆盖这些要求；不得因为样例目录不同而漏项。
4. 如果当前一级章节已有成熟样例 children，应优先保留其合理结构；但必须修正行业错配、历史项目残留和与招标文件冲突的内容。
5. 价格敏感内容只能出现在允许价格的卷册；暗标章节不得设计暴露投标人身份的标题或素材位。
6. 证明材料类章节应设计“材料清单、证明用途、核验要点、页码索引”。
7. 技术/服务/实施方案类章节应按评分标准拆成“理解、方法、流程、组织、进度、质量、安全、风险、成果、保障”中最合适的结构。
8. 固定格式表单类章节只能设计填报项和核验项，不得改动表头、列名和固定文字。
9. 对招标文件写明“应包括但不限于”的方案纲要，必须逐项拆出二级或三级节点，或在 description 中说明由哪个节点覆盖；如果 selected_generation_target.base_outline_items 已经提供标题，必须保留标题语义和顺序。
10. description 要写清本节点要写什么、响应哪些评分项、需要哪些表格/承诺/图片/企业资料。

{rulebook}

输出 JSON schema：
{schema_json}
"""
    user_prompt = f"""请补全当前一级章节的二级、三级目录。

<current_level1_node>{_json(current_outline_json, indent=2)}</current_level1_node>
<other_outline>{other_outline}</other_outline>
<overview>{overview}</overview>
<requirements>{requirements}</requirements>
<bid_mode>{bid_mode or ''}</bid_mode>
<analysis_report_json>{_json(analysis_report or {}, indent=2)}</analysis_report_json>
<response_matrix_json>{_json(response_matrix or {}, indent=2)}</response_matrix_json>
<reference_bid_style_profile_json>{_json(reference_bid_style_profile or (analysis_report or {}).get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile_json>
<document_blocks_plan_json>{_json(document_blocks_plan or (analysis_report or {}).get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan_json>

直接返回 JSON。"""
    return system_prompt, user_prompt


def generate_document_blocks_prompt(
    analysis_report: Dict[str, Any] | None,
    outline: List[Dict[str, Any]] | Dict[str, Any],
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    enterprise_materials: List[Dict[str, Any]] | None = None,
    asset_library: List[Dict[str, Any]] | Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    schema_json = _json(get_document_blocks_schema(), indent=2)
    system_prompt = f"""你是技术标图表与素材规划专家。你的任务是根据目录、响应矩阵和样例风格，规划每个章节应插入的表格、流程图、组织架构图、图片、承诺书、证明材料或页码占位。

硬性要求：
1. 只输出合法 JSON。
2. 不得编造图片、证书、截图、人员、设备、软件或案例；没有素材时输出 placeholder。
3. 如素材库有匹配图片或附件，输出 asset_id；没有则输出 fallback placeholder。
4. 表格必须给出表名、列名、行生成规则和数据来源。
5. 承诺书必须给出致函对象、承诺事项、署名变量、日期变量。
6. 组织机构图、流程图可以输出结构化 nodes/edges，由后端渲染或人工替换。
7. Word 目录页码不得由模型生成，应由 Word 自动更新。

JSON schema：
{schema_json}
"""
    user_prompt = f"""请输出图表与素材规划 JSON。

<analysis_report_json>{_json(analysis_report or {}, indent=2)}</analysis_report_json>
<response_matrix_json>{_json(response_matrix or (analysis_report or {}).get('response_matrix') or {}, indent=2)}</response_matrix_json>
<reference_bid_style_profile_json>{_json(reference_bid_style_profile or (analysis_report or {}).get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile_json>
<outline_json>{_json(outline or [], indent=2)}</outline_json>
<enterprise_materials_json>{_json(enterprise_materials or [], indent=2)}</enterprise_materials_json>
<asset_library_json>{_json(asset_library or [], indent=2)}</asset_library_json>

直接返回 JSON。"""
    return system_prompt, user_prompt


def generate_chapter_content_prompt(
    chapter: Dict[str, Any],
    parent_chapters: List[Dict[str, Any]] | None,
    sibling_chapters: List[Dict[str, Any]] | None,
    project_overview: str,
    analysis_report: Dict[str, Any] | None = None,
    bid_mode: str | None = None,
    generated_summaries: List[Dict[str, Any]] | None = None,
    enterprise_materials: List[Dict[str, Any]] | None = None,
    missing_materials: List[Dict[str, Any]] | None = None,
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
    bidder_name: str = "{bidder_name}",
    bid_date: str = "{bid_date}",
) -> Tuple[str, str]:
    report = analysis_report or {}
    project = report.get("project") or {}
    response_matrix = response_matrix or report.get("response_matrix") or {}
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是资深投标文件编制专家。你的任务是为当前叶子章节生成可直接放入投标文件的正文。

硬性规则：
1. 只输出当前章节正文，不输出章节标题。
2. 不输出 markdown 代码块，不输出 AI 自述，不解释生成过程。
3. 不得重新解析招标文件；只能使用传入的 AnalysisReport、ResponseMatrix、目录节点、样例风格、图表规划和企业资料。
4. 不得编造企业资质、人员姓名、证书编号、电话号码、软件清单、设备数量、项目业绩、图片、日期、金额、报价或税率。
5. 凡企业资料缺失，必须使用：〖待补充：资料名称〗、〖待确认：事项〗、〖待提供扫描件：资料名称〗、〖插入图片：图片名称〗。
6. 正式投标文件语气，主体称谓默认使用“我公司”；如暗标要求禁止身份识别，则不得出现投标人名称、人员姓名、联系方式、Logo、商标、可识别案例名。
7. 当前项目必须围绕 AnalysisReport.project.name 展开，不得写成其他项目；历史项目名称、历史日期不得残留。
8. 涉及服务范围、供货范围、施工范围、交付内容、服务期限、工期、质量要求、响应时限时，必须准确引用 AnalysisReport 中的招标要求；没有明确要求时写 〖以招标文件要求为准〗。
9. 涉及进度、工期、交付周期、响应时限时，只能使用 AnalysisReport 中提取的期限或当前章节映射的 C/SCH/RM 条目；不得套用历史样例中的天数。
10. 涉及质量承诺时，应覆盖法律法规、行业标准、招标人要求、过程质量控制、验收整改、违约责任；如招标文件没有违约责任要求，应写为按合同约定承担责任。
11. 涉及沟通协调时，可写定期沟通、即时沟通、书面沟通、会议纪要、问题闭环、响应升级；具体联系人和电话缺失时必须占位。
12. 涉及组织机构时，输出组织架构图占位或结构化职责说明；人员姓名、证书、履历缺失时占位。
13. 涉及设备、软件、产品、备品备件、仪器、车辆、平台时，必须依据企业资料或资源库；缺失时用表格占位，不得虚构品牌、数量、型号。
14. 涉及图片、证书、截图、效果图、系统截图、案例展示时，先写展示目的和插入位置，再输出图片占位；不得假装已有图片。
15. 当前章节如对应 selected_generation_target.base_outline_items、bid_document_requirements.composition 或 fixed_forms，必须严格按该要求写作；固定格式表单、承诺函、偏离表、报价表等章节不得改表头、列名、固定文字和行列结构。
16. 当前章节如属于技术/服务/设计/实施方案，应逐项覆盖 selected_generation_target.base_outline_items 和 bid_document_requirements.scheme_or_technical_outline_requirements 中映射到本章节的要点；不得只按历史样例自由扩写。
17. 如果本次输出范围是方案分册，正文不得出现投标函、报价、投标保证金、资格审查资料等非 selected_generation_target 的完整标书正文内容；必要时只可写“该内容按招标文件对应格式另行提供”。
18. 当前章节如未被招标文件“投标文件/投标文件格式”要求，但来自样例 profile_expansion，必须确保不与招标文件目录、评分项、卷册隔离和固定格式冲突。
19. 正文中不得写死页码。
20. 与同级章节不得重复；同级已覆盖的内容，本节只深化、引用或建立索引。

写作风格：
1. 使用“目标—措施—流程—保障—承诺”的结构。
2. 多用 1）、2）、3）；a）、b）、c）分点结构。
3. 内容要具体，避免只写口号。
4. 高分章节、阻塞风险章节、证据链章节写得更细；低风险说明性章节简洁准确。

{rulebook}
"""
    user_prompt = f"""请生成当前章节正文。

<project_variables>
{_json({
    "project_name": project.get("name") or "{project_name}",
    "tenderer_name": project.get("purchaser") or "{tenderer_name}",
    "bidder_name": bidder_name,
    "bid_date": bid_date,
    "service_scope": project.get("service_scope", ""),
    "service_period": project.get("service_period", ""),
    "service_location": project.get("service_location", ""),
    "quality_requirements": project.get("quality_requirements", ""),
}, indent=2)}
</project_variables>
<bid_mode>{bid_mode or report.get('bid_mode_recommendation') or ''}</bid_mode>
<current_chapter>{_json(chapter or {}, indent=2)}</current_chapter>
<parent_chapters>{_json(parent_chapters or [], indent=2)}</parent_chapters>
<sibling_chapters>{_json(sibling_chapters or [], indent=2)}</sibling_chapters>
<generated_summaries>{_json(generated_summaries or [], indent=2)}</generated_summaries>
<project_overview>{project_overview}</project_overview>
<analysis_report>{_json(report, indent=2)}</analysis_report>
<response_matrix>{_json(response_matrix, indent=2)}</response_matrix>
<reference_bid_style_profile>{_json(reference_bid_style_profile or report.get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile>
<document_blocks_plan>{_json(document_blocks_plan or report.get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan>
<enterprise_materials>{_json(enterprise_materials or [], indent=2)}</enterprise_materials>
<missing_materials>{_json(missing_materials or report.get('missing_company_materials') or [], indent=2)}</missing_materials>

直接输出当前章节正文，不要输出标题。"""
    return system_prompt, user_prompt


def generate_compliance_review_prompt(
    analysis_report: Dict[str, Any],
    outline: List[Dict[str, Any]],
    project_overview: str = "",
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    schema_json = _json(get_review_report_schema(), indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是投标文件导出前合规审校专家。你的任务是在 Word 导出前，对完整正文、表格、占位符、附件清单、图表素材、目录映射进行覆盖、格式、材料、报价隔离、暗标、日期一致性、历史残留和虚构风险检查。

必须检查：
1. 项目名称、招标人、投标人、日期、服务期限/工期/交付期是否统一；不得出现历史项目名称、历史招标人或历史日期。
2. 输出范围是否正确：technical_only/service_plan 不得混入报价、保证金、投标函、资格审查资料正文；full_bid 则不得遗漏招标文件要求的完整卷册。
3. 是否严格遵守 AnalysisReport.bid_document_requirements 和 selected_generation_target：full_bid 要检查 composition 顺序与必备章节；技术/服务/设计方案分册要检查 selected_generation_target.base_outline_items 和 scheme_or_technical_outline_requirements 全覆盖；固定格式要检查表头、固定文字、签章栏和附件要求。
4. ResponseMatrix 和 AnalysisReport 中的评分项、审查项、实质性条款、材料项、风险项是否覆盖.
4. 招标文件要求的方案目录、承诺书、表格、证明材料、固定格式、签章、报价隔离、暗标规则是否满足；如果输出范围是方案分册，是否误把被排除的投标函、保证金、报价、资格资料写入正文。
5. 企业资料缺失是否保留明确占位；是否把缺失资料写成已具备。
6. 图表与素材规划中的必需表格、组织图、流程图、承诺书、图片/证书/截图占位是否存在。
7. 页码、附件索引、响应页码是否使用 〖页码待编排〗 或等待 Word 自动更新。

硬性要求：
1. 只输出合法 ReviewReport JSON，不输出 markdown。
2. 只能依据传入 AnalysisReport、ResponseMatrix、ReferenceBidStyleProfile、document_blocks_plan 和 outline_with_content 审校，不得新增招标要求。
3. blocking=true 的废标风险、实质性条款、固定格式、签章、报价隔离、暗标身份泄露、企业资料虚构未处理时，summary.ready_to_export=false。
4. 发现历史残留日期、项目名称、招标人名称，severity=blocking 或 high，并写入 blocking_issues 或 warnings。
5. revision_plan 必须给出可执行修订动作。

{rulebook}

JSON schema：
{schema_json}
"""
    user_prompt = f"""请对以下标书内容进行导出前合规审校。

<project_overview>{project_overview or ''}</project_overview>
<analysis_report>{_json(analysis_report or {}, indent=2)}</analysis_report>
<response_matrix>{_json(response_matrix or (analysis_report or {}).get('response_matrix') or {}, indent=2)}</response_matrix>
<reference_bid_style_profile>{_json(reference_bid_style_profile or (analysis_report or {}).get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile>
<document_blocks_plan>{_json(document_blocks_plan or (analysis_report or {}).get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan>
<outline_with_content>{_json(outline or [], indent=2)}</outline_with_content>

直接返回 ReviewReport JSON。"""
    return system_prompt, user_prompt


def generate_consistency_revision_prompt(
    analysis_report: Dict[str, Any] | None,
    full_bid_draft: Dict[str, Any] | List[Dict[str, Any]],
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    schema_json = _json(get_consistency_revision_schema(), indent=2)
    system_prompt = f"""你是投标文件全文一致性修订专家。你的任务是在 Word 导出前检查全文一致性，只输出问题和修订建议，不直接改写全文。

检查范围：项目名称、招标人、投标人、日期、服务期限/工期/交付期、承诺周期、历史项目残留、行业错配、企业资料虚构、输出范围错误、缺少图表/承诺/素材块、评分项覆盖、投标文件格式章节/组成要求是否被遵守。

硬性要求：
1. 只输出合法 JSON。
2. 不要直接改写全文，只输出问题和修订建议。
3. 发现历史残留内容，severity 至少为 high。
4. 发现日期、项目名称、招标人不一致，severity 至少为 high。
5. 发现服务期限/工期/交付期承诺与招标文件不一致，severity=blocking。
6. 发现企业资料虚构，severity=blocking。
7. 发现输出范围是技术/服务方案却出现报价、保证金、投标函正文，severity=high 或 blocking。

JSON schema：
{schema_json}
"""
    user_prompt = f"""请输出全文一致性修订报告。

<analysis_report>{_json(analysis_report or {}, indent=2)}</analysis_report>
<response_matrix>{_json(response_matrix or (analysis_report or {}).get('response_matrix') or {}, indent=2)}</response_matrix>
<reference_bid_style_profile>{_json(reference_bid_style_profile or (analysis_report or {}).get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile>
<document_blocks_plan>{_json(document_blocks_plan or (analysis_report or {}).get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan>
<full_bid_draft>{_json(full_bid_draft or {}, indent=2)}</full_bid_draft>

直接返回 JSON。"""
    return system_prompt, user_prompt


def read_expand_outline_prompt() -> str:
    template = _json(get_generic_service_plan_outline_template(), indent=2)
    return f"""你是投标文件样例反向建模专家。当前任务是从用户提交的简版技术方案、历史投标文件或样例文件中提取并重建目录结构。

当前阶段只允许输出目录 JSON，不生成正文，不输出解析过程。
如果文本存在明确章节名称，优先保留；如果没有明确章节名称，提炼专业、规范、可用于正式投标文件的章节名称。
对表格类、函件类、承诺类、证明材料类、图片展示类章节必须建立目录节点。
不得把样例行业固化为所有项目默认行业；只抽取目录结构和风格。若文本中包含“投标文件/投标文件格式/投标文件组成/编制要求”，必须优先抽取这些硬约束章节。

通用服务/技术方案目录参考：
{template}

返回 JSON：{{"outline": [...]}}，不要 markdown。"""


def generate_outline_prompt(overview: str, requirements: str) -> Tuple[str, str]:
    schema = {"outline": get_generic_service_plan_outline_template()}
    system_prompt = f"""你是通用投标文件目录生成专家。当前只生成目录 JSON，不生成正文。
根据输入判断是完整投标文件、技术标、服务方案、施工组织设计、供货方案、资格卷还是报价卷；如果输入包含投标文件格式/组成要求，目录必须优先遵守；不得强行套用某个行业模板。
JSON 格式参考：{_json(schema)}"""
    user_prompt = f"""请基于以下项目信息生成标书目录结构：
项目概述：{overview}
技术/服务/评分要求：{requirements}
请直接输出目录 JSON。"""
    return system_prompt, user_prompt


def generate_outline_with_old_prompt(overview: str, requirements: str, old_outline: str) -> Tuple[str, str]:
    system_prompt = """你是通用投标文件目录校正专家。当前只生成目录 JSON，不生成正文。
你需要充分吸收用户已有目录，补齐评分项、审查项、证明材料、表格、承诺书和图表素材节点；不得强行套用某个行业模板。"""
    user_prompt = f"""用户已有目录：{old_outline}
项目概述：{overview}
技术/服务/评分要求：{requirements}
请结合用户目录输出最终目录 JSON。"""
    return system_prompt, user_prompt
