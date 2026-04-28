
import json


def get_full_bid_rulebook():
  """从完整标书模板提炼出的通用风控规则，供多阶段提示词复用"""
  return """标书编制通用风控规则：
1. 以招标文件原文为最高优先级依据。不得用通用经验覆盖招标文件的具体要求。
2. 所有输出必须服务于投标文件编制、评分点覆盖、实质性响应、废标风险规避和后续 Word 导出。
3. 不得编造企业名称、资质、业绩、人员、财务、报价、税率、日期、证书编号、社保、发票、合同、信用查询结果或联系方式。
4. 未提供或无法核实的信息必须使用明确占位符：〖待补充：资料名称〗、〖待确认：事项〗、〖待提供扫描件：资料名称〗、〖以招标文件要求为准〗或〖页码待编排〗。
5. 招标文件、澄清/答疑/补遗、企业资料和历史案例冲突时，按“招标文件 > 澄清/答疑/补遗 > 企业已提供资料 > 企业历史材料 > 通用经验”处理。
6. 不得把“不满足、未提供、待确认”的事项写成“满足、已具备、已完成、已提供”。
7. 标注为“实质性格式”“固定格式”“不得修改格式”“必须按格式填写”的投标函、报价表、费用明细表、授权委托书、承诺函、偏离表、声明函、资格表、人员表、业绩表等，不得改变表头、列名、固定文字、行列结构和选择项。
8. 对“★”“*”“▲”“实质性要求”“不允许偏离”“投标无效”“废标”“否决投标”“资格审查不通过”等内容，必须单独识别、编号、响应和审校。
9. 对签字、签章、电子签章、骑缝章、法定代表人或授权代表签署、日期、附件扫描件等要求，必须建立检查项。
10. 对暗标、双盲评审、匿名技术标，如招标文件有要求，正文不得出现企业名称、人员姓名、业绩名称、联系方式、Logo、商标、可识别图片、页眉页脚异常、隐藏超链接等身份识别信息。
11. 报价文件必须严格服从招标文件规定的报价方式、币种、税率、含税/不含税口径、小数位、总价/单价、唯一报价、最高限价、分项报价、费用包含范围和算术修正规则。
12. 如招标文件要求价格文件单独成册或不得出现在技术/商务文件中，必须在目录、正文和审校中强制隔离。
13. 未提供报价信息时，不得生成具体金额，只能保留〖待补充：报价金额/分项报价〗。
14. 业绩证据链应区分合同关键页、中标通知书、验收证明、发票、税务查验截图、业主证明、框架协议、订单/任务书；仅有历史案例文字不得自动认定为有效证明材料。
15. 人员证据链应关注身份证、学历、职称/注册证、劳动合同、社保、退休返聘协议、人员业绩和证书有效期。
16. 信用与资质证据链应关注查询平台、查询对象、查询日期、截图页面、资质有效期、年检状态和承诺函。
17. 技术方案必须围绕评分细则逐条展开，说明响应措施、实施步骤、人员/资源、质量控制、进度控制、风险控制、交付成果和支撑材料。
18. 分值高、实质性强、容易失分的评分项，应获得更高目录层级、更长篇幅和更细颗粒度响应。
19. 不得重复生成同质化段落；同级章节必须分工明确。
20. 要求 JSON 时，只输出合法 JSON；要求正文时，只输出当前章节正文，不输出标题、提示语、AI 自述或解释过程。"""


def get_analysis_report_schema():
  """结构化标准解析报告 JSON 模板"""
  return {
    "project": {
      "name": "",
      "number": "",
      "package_name": "",
      "package_or_lot": "",
      "purchaser": "",
      "agency": "",
      "procurement_method": "",
      "project_type": "",
      "budget": "",
      "maximum_price": "",
      "funding_source": "",
      "service_scope": "",
      "service_period": "",
      "service_location": "",
      "quality_requirements": "",
      "bid_validity": "",
      "bid_bond": "",
      "performance_bond": "",
      "bid_deadline": "",
      "opening_time": "",
      "submission_method": "",
      "electronic_platform": "",
      "submission_requirements": "",
      "signature_requirements": ""
    },
    "bid_mode_recommendation": "technical_only",
    "source_refs": [
      {
        "id": "SRC-01",
        "location": "招标文件章节/页码/表格",
        "excerpt": "不超过120字的原文短摘录",
        "related_ids": ["T-01", "C-01"]
      }
    ],
    "volume_rules": [
      {
        "id": "V-TECH",
        "name": "技术标",
        "scope": "",
        "separate_submission": False,
        "price_allowed": False,
        "anonymity_required": False,
        "seal_signature_rule": "",
        "source": ""
      }
    ],
    "anonymity_rules": {
      "enabled": False,
      "scope": "",
      "forbidden_identifiers": [],
      "formatting_rules": [],
      "source": ""
    },
    "bid_structure": [
      {
        "id": "S-01",
        "parent_id": "",
        "title": "",
        "purpose": "",
        "category": "资格/商务/技术/报价/承诺/附件",
        "volume_id": "V-TECH",
        "required": True,
        "fixed_format": False,
        "signature_required": False,
        "attachment_required": False,
        "seal_required": False,
        "price_related": False,
        "anonymity_sensitive": False,
        "source": ""
      }
    ],
    "formal_review_items": [
      {
        "id": "E-01",
        "review_type": "形式评审",
        "requirement": "",
        "criterion": "",
        "required_materials": ["M-01"],
        "risk": "",
        "target_chapters": ["S-01"],
        "source": "",
        "invalid_if_missing": False
      }
    ],
    "qualification_review_items": [
      {
        "id": "E-02",
        "review_type": "资格评审",
        "requirement": "",
        "criterion": "",
        "required_materials": ["M-01"],
        "risk": "",
        "target_chapters": ["S-01"],
        "source": "",
        "invalid_if_missing": False
      }
    ],
    "responsiveness_review_items": [
      {
        "id": "E-03",
        "review_type": "响应性评审",
        "requirement": "",
        "criterion": "",
        "required_materials": ["M-01"],
        "risk": "",
        "target_chapters": ["S-01"],
        "source": "",
        "invalid_if_missing": False
      }
    ],
    "business_scoring_items": [
      {
        "id": "B-01",
        "name": "",
        "score": "",
        "standard": "",
        "source": "",
        "evidence_requirements": ["合同关键页", "发票", "查验截图"],
        "writing_focus": "",
        "easy_loss_points": []
      }
    ],
    "technical_scoring_items": [
      {
        "id": "T-01",
        "name": "",
        "score": "",
        "standard": "",
        "source": "",
        "writing_focus": "",
        "evidence_requirements": [],
        "easy_loss_points": []
      }
    ],
    "price_scoring_items": [
      {
        "id": "P-01",
        "name": "",
        "score": "",
        "logic": "",
        "source": "",
        "risk": ""
      }
    ],
    "price_rules": {
      "quote_method": "",
      "currency": "",
      "maximum_price_rule": "",
      "abnormally_low_price_rule": "",
      "separate_price_volume_required": False,
      "price_forbidden_in_other_volumes": False,
      "tax_requirement": "",
      "decimal_places": "",
      "uniqueness_requirement": "",
      "form_requirements": "",
      "arithmetic_correction_rule": "",
      "missing_item_rule": "",
      "prohibited_format_changes": [],
      "source_ref": ""
    },
    "qualification_requirements": [
      {
        "id": "Q-01",
        "name": "",
        "requirement": "",
        "source": "",
        "required_materials": ["M-01"]
      }
    ],
    "formal_response_requirements": [
      {
        "id": "F-01",
        "name": "",
        "requirement": "",
        "source": "",
        "fixed_format": False,
        "signature_required": False,
        "attachment_required": False
      }
    ],
    "mandatory_clauses": [
      {
        "id": "C-01",
        "clause": "",
        "source": "",
        "response_strategy": "",
        "invalid_if_not_responded": True
      }
    ],
    "rejection_risks": [
      {
        "id": "R-01",
        "risk": "",
        "trigger": "",
        "source": "",
        "mitigation": "",
        "blocking": True
      }
    ],
    "fixed_format_forms": [
      {
        "id": "FF-01",
        "name": "",
        "volume_id": "",
        "source": "",
        "required_columns": [],
        "must_keep_columns": [],
        "must_keep_text": [],
        "fillable_fields": [],
        "fixed_text": "",
        "fill_rules": "",
        "seal_required": False
      }
    ],
    "signature_requirements": [
      {
        "id": "SIG-01",
        "target": "",
        "signer": "",
        "seal": "",
        "date_required": False,
        "electronic_signature_required": False,
        "source": "",
        "risk": ""
      }
    ],
    "evidence_chain_requirements": [
      {
        "id": "EV-01",
        "target": "企业业绩/项目负责人/社保/信用/发票",
        "required_evidence": [],
        "validation_rule": "",
        "source": "",
        "risk": ""
      }
    ],
    "required_materials": [
      {
        "id": "M-01",
        "name": "",
        "purpose": "",
        "source": "",
        "status": "missing",
        "used_by": ["Q-01"],
        "volume_id": ""
      }
    ],
    "missing_company_materials": [
      {
        "id": "X-01",
        "name": "",
        "used_by": ["Q-01", "T-01"],
        "placeholder": "〖待补充：具体资料名称〗",
        "blocking": False
      }
    ],
    "generation_warnings": [
      {
        "id": "W-01",
        "warning": "",
        "severity": "warning",
        "related_ids": []
      }
    ],
    "response_matrix": get_response_matrix_schema()
  }


def get_response_matrix_schema():
  """响应矩阵 JSON 模板"""
  return {
    "items": [
      {
        "id": "RM-01",
        "source_item_id": "T-01",
        "source_type": "scoring/review/mandatory/risk/material/format/signature/evidence/price",
        "requirement_summary": "",
        "response_strategy": "",
        "target_chapter_ids": ["1.1"],
        "required_material_ids": ["M-01"],
        "risk_ids": ["R-01"],
        "source_refs": ["SRC-01"],
        "priority": "high",
        "status": "pending",
        "blocking": False
      }
    ],
    "uncovered_ids": ["T-01"],
    "high_risk_ids": ["RM-01"],
    "coverage_summary": ""
  }


def get_review_report_schema():
  """导出前合规审校 JSON 模板"""
  return {
    "coverage": [
      {
        "item_id": "T-01",
        "target_type": "scoring",
        "covered": True,
        "chapter_ids": ["1.1.1"],
        "issue": "",
        "evidence": "",
        "fix_suggestion": ""
      }
    ],
    "missing_materials": [
      {
        "material_id": "M-01",
        "material_name": "",
        "used_by": ["T-01"],
        "chapter_ids": ["2.1.1"],
        "placeholder": "〖待补充：具体资料名称〗",
        "placeholder_found": True,
        "fix_suggestion": ""
      }
    ],
    "rejection_risks": [
      {
        "risk_id": "R-01",
        "handled": False,
        "issue": ""
      }
    ],
    "duplication_issues": [
      {
        "chapter_ids": ["1.2.1", "1.3.1"],
        "issue": ""
      }
    ],
    "fabrication_risks": [
      {
        "chapter_id": "3.1.1",
        "text": "",
        "reason": "",
        "fix_suggestion": ""
      }
    ],
    "fixed_format_issues": [
      {
        "item_id": "FF-01",
        "chapter_ids": ["2.1.1"],
        "issue": "",
        "evidence": "",
        "fix_suggestion": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "signature_issues": [
      {
        "item_id": "SIG-01",
        "chapter_ids": ["2.1.1"],
        "issue": "",
        "evidence": "",
        "fix_suggestion": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "price_rule_issues": [
      {
        "item_id": "P-01",
        "chapter_ids": ["3.1.1"],
        "issue": "",
        "evidence": "",
        "fix_suggestion": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "evidence_chain_issues": [
      {
        "item_id": "EV-01",
        "chapter_ids": ["4.1.1"],
        "issue": "",
        "evidence": "",
        "fix_suggestion": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "page_reference_issues": [
      {
        "item_id": "PAGE-01",
        "chapter_ids": ["1.1.1"],
        "issue": "",
        "evidence": "",
        "fix_suggestion": "",
        "severity": "warning",
        "blocking": False
      }
    ],
    "anonymity_issues": [],
    "blocking_issues": [],
    "warnings": [],
    "revision_plan": {
      "actions": [
        {
          "id": "RP-01",
          "target_chapter_ids": ["1.1.1"],
          "action_type": "补写/替换/删减/补材料/人工确认",
          "instruction": "",
          "priority": "high",
          "related_issue_ids": ["T-01"],
          "blocking": True
        }
      ],
      "summary": ""
    },
    "summary": {
      "ready_to_export": False,
      "blocking_issues": 0,
      "warnings": 0,
      "blocking_issues_count": 0,
      "warnings_count": 0,
      "coverage_rate": 0,
      "blocking_summary": "",
      "next_actions": []
    }
  }


def generate_analysis_report_prompt(file_content):
  """生成结构化标准解析报告的提示词"""
  schema_json = json.dumps(get_analysis_report_schema(), ensure_ascii=False, separators=(",", ":"))
  rulebook = get_full_bid_rulebook()
  system_prompt = f"""你是专业招标文件解析专家。你的任务是把招标文件解析为可供后续目录生成、正文生成和合规检查复用的 AnalysisReport JSON。

要求：
1. 只输出合法 JSON，不输出 markdown 代码块，不输出解释文字。
2. 所有条目必须尽量标注 source，source 写招标文件中的章节、页码、表格或条款位置；确实无法定位时填空字符串。
3. 未提及的信息填空字符串或空数组，不得猜测。
4. 企业资料缺失时只登记 missing_company_materials，不得虚构企业名称、资质、业绩、人员、金额、日期、证书编号、合同、发票或联系方式。
5. 根据输入内容判断 bid_mode_recommendation，只能是 technical_only 或 full_bid。
6. 技术评分项使用 T-01、T-02 编号；资格要求使用 Q-01 编号；正式响应要求使用 F-01 编号；实质性条款使用 C-01 编号；废标风险使用 R-01 编号；材料使用 M-01 编号；待补资料使用 X-01 编号。
7. 投标结构使用 S-01 编号；评审项使用 E-01 编号；商务评分项使用 B-01 编号；价格评分项使用 P-01 编号；固定格式使用 FF-01 编号；签章要求使用 SIG-01 编号；证据链要求使用 EV-01 编号。
8. required_materials.status 只能使用 missing、provided 或 unknown。
9. 必须同时提取形式评审、资格评审、响应性评审、商务评分、技术评分、价格规则、固定格式、签字盖章、页码占位、证据链要求、报价隔离要求、卷册规则和暗标/匿名要求；若招标文件没有对应内容则输出空数组或空字符串。
10. 如果文档明显只要求技术标，bid_mode_recommendation 输出 technical_only；如果出现完整资格/商务/报价/承诺/附件组卷要求，输出 full_bid。
11. bid_structure 必须体现卷册隔离思路：资格、商务、技术、报价、承诺、附件等应按招标文件要求拆分；价格文件单独递交或不得进入技术/商务文件时，必须在对应节点 purpose 或 source 中写明。
12. 对暗标、双盲、匿名技术标要求，必须在 mandatory_clauses、formal_response_requirements 或 rejection_risks 中单独编号。
13. 高风险内容不得合并：否决项、实质性条款、固定格式、签章、报价、暗标、资格硬条件必须分别输出。
14. 为避免 JSON 被截断，每个数组最多输出最关键 8 项；单个字段内容尽量压缩到 80 字以内；不得为了完整复述原文而输出长段落。
15. 若同类要求很多，优先保留否决项、实质性条款、评分项、签章/格式要求和材料要求，其余合并概括到 risk、writing_focus 或 source。
16. 必须生成 response_matrix：把评分项、审查项、实质性条款、废标风险、材料、固定格式、签章、报价和暗标要求逐项映射到后续目录/正文响应策略；不得把 response_matrix 留空。
17. source_refs 只记录最关键出处，每个 excerpt 不超过 120 字；volume_rules 必须体现技术/商务/报价/资格/附件是否隔离、是否允许报价、是否暗标。

{rulebook}

JSON 格式模板：
{schema_json}
"""

  user_prompt = f"""请解析以下招标文件内容，输出 AnalysisReport JSON：

<tender_document>
{file_content}
</tender_document>

直接返回 JSON，不要任何额外说明或格式标记。"""
  return system_prompt, user_prompt


def generate_response_matrix_prompt(analysis_report):
  """基于 AnalysisReport 生成独立响应矩阵的提示词"""
  schema_json = json.dumps(get_response_matrix_schema(), ensure_ascii=False, separators=(",", ":"))
  analysis_report_json = json.dumps(analysis_report or {}, ensure_ascii=False, separators=(",", ":"))
  rulebook = get_full_bid_rulebook()
  system_prompt = f"""你是专业投标响应矩阵设计专家。你的任务是把已解析的 AnalysisReport 转换为 ResponseMatrix JSON。

要求：
1. 只输出合法 JSON，不输出 markdown 代码块，不输出解释文字。
2. 只能使用传入的 AnalysisReport，不得重新解析、不得新增招标文件中不存在的评分项、审查项、材料项或风险项。
3. 每个技术/商务/价格评分项、形式/资格/响应性评审项、实质性条款、废标风险、固定格式、签章、证据链、材料和报价隔离要求，都应至少形成一条矩阵或被合并说明。
4. source_item_id 必须引用 AnalysisReport 中已有 ID；target_chapter_ids 可先引用建议章节或结构节点 ID，后续目录生成会再细化。
5. priority=high 用于高分值、否决项、固定格式、签章、报价、暗标、资格硬条件和证据链要求；blocking=true 用于未覆盖会影响导出或可能否决投标的项目。
6. uncovered_ids 初始包含尚未绑定具体正文的来源 ID；目录生成完成后可逐步缩减。
7. 每条 requirement_summary 和 response_strategy 控制在 80 字以内。

{rulebook}

JSON 格式模板：
{schema_json}
"""
  user_prompt = f"""请基于以下 AnalysisReport 生成 ResponseMatrix：

<analysis_report>
{analysis_report_json}
</analysis_report>

直接返回 JSON，不要任何额外说明或格式标记。"""
  return system_prompt, user_prompt


def generate_compliance_review_prompt(analysis_report, outline, project_overview="", response_matrix=None):
  """生成导出前合规审校提示词"""
  schema_json = json.dumps(get_review_report_schema(), ensure_ascii=False, indent=2)
  analysis_report_json = json.dumps(analysis_report or {}, ensure_ascii=False, indent=2)
  response_matrix_json = json.dumps(response_matrix or {}, ensure_ascii=False, indent=2)
  outline_json = json.dumps(outline or [], ensure_ascii=False, indent=2)
  rulebook = get_full_bid_rulebook()
  system_prompt = f"""你是专业投标文件合规审校专家。你的任务是在 Word 导出前检查完整标书正文、表格内容、占位符、附件清单和目录映射是否覆盖评分项、审查项和风险点。

要求：
1. 只输出合法 ReviewReport JSON，不输出 markdown 代码块，不输出解释文字。
2. 只能依据传入的 AnalysisReport、ResponseMatrix 和 outline_with_content 审校，不得另行推断新的评分项、审查项或材料项。
3. coverage 检查 ResponseMatrix 和 AnalysisReport 中 bid_structure、formal_review_items、qualification_review_items、responsiveness_review_items、business_scoring_items、technical_scoring_items、price_scoring_items、qualification_requirements、formal_response_requirements、mandatory_clauses 是否被正文或目录覆盖。
4. missing_materials 检查 required_materials 和 missing_company_materials 是否在相关章节中保留了明确占位或材料清单。
5. rejection_risks 检查 rejection_risks 是否已有响应或规避说明。
6. duplication_issues 检查明显重复章节或重复正文。
7. fabrication_risks 检查疑似虚构企业名称、金额、日期、证书编号、业绩、人员、合同、发票、联系方式等风险。
8. fixed_format_issues 检查固定格式表头、列名、固定文字、行列数量是否被改动或缺失。
9. signature_issues 检查签字盖章位置、签署主体、盖章要求是否遗漏。
10. price_rule_issues 检查报价方式、税率、小数位、唯一报价、算术修正、缺漏项处理、费用明细表格式要求；若价格文件要求单独成册或不得混入技术/商务文件，必须检查目录和正文是否隔离。
11. evidence_chain_issues 检查业绩、人员、社保、发票、税务查验、信用截图、保证金凭证等证据链是否完整。
12. page_reference_issues 检查索引表和响应页码；未最终排版时应使用〖页码待编排〗。
13. 如 AnalysisReport 包含暗标、双盲或匿名要求，必须检查正文是否出现企业名称、人员姓名、业绩名称、联系方式、Logo、商标等身份识别信息。
14. 若存在未覆盖评分项/评审项、未处理废标风险、固定格式被破坏、签章遗漏、报价规则不满足、价格文件未隔离、暗标身份泄露、证据链缺失或缺失证明材料未标注，summary.ready_to_export 必须为 false。
15. 所有阻塞项 severity 使用 blocking 且 blocking=true；提示项 severity 使用 warning。
16. 必须输出 blocking_issues、warnings 和 revision_plan。revision_plan 要把每个阻塞项转成可执行修订动作，写明目标章节、动作类型和修订指令。
17. summary.blocking_issues、summary.blocking_issues_count、summary.warnings、summary.warnings_count 必须与问题列表数量保持一致；summary.coverage_rate 输出 0 到 100 的数字。

{rulebook}

JSON 格式模板：
{schema_json}
"""

  user_prompt = f"""请对以下标书内容进行导出前合规审校：

<project_overview>
{project_overview or ""}
</project_overview>

<analysis_report>
{analysis_report_json}
</analysis_report>

<response_matrix>
{response_matrix_json}
</response_matrix>

<outline_with_content>
{outline_json}
</outline_with_content>

直接返回 ReviewReport JSON，不要任何额外说明或格式标记。"""
  return system_prompt, user_prompt


def read_expand_outline_prompt():
  '''从简版技术方案中提取目录的提示词'''
  system_prompt = """你是一个专业的标书解析与编制专家，当前任务是从用户提交的简版技术方案中提取并重建目录结构。

  当前阶段只允许从用户提交的简版技术方案中提取或重建目录 JSON。
  如上游已生成标准解析报告，目录必须复用该报告，不得在本阶段重新解释出新的评分项、审查项、材料项或风险项。
  只有当用户明确下达“开始生成标书”指令时，才进入正文生成阶段。

  当前任务只做“目录提取/目录重建”，不要生成正文，不要输出解析报告。

  要求：
  1. 目录结构要全面覆盖原技术方案已经体现出的全部必要章节，允许输出多级目录
  2. 如果技术方案中已经存在明确章节名称，优先保留原章节名称
  3. 如果技术方案中没有明确章节名称，则结合全文内容，提炼出专业、规范、可用于正式投标文件的章节名称
  4. 目录应服务于后续正式标书生成，因此 description 不能空泛，要写清“本章节要写什么、解决什么问题、需插入什么材料或证明”
  5. 如果原文明显只包含技术标内容，则输出技术标目录；如果原文明显包含商务、资格、技术混合结构，则按实际结构重建完整目录
  6. 对表格类、函件类、承诺类、证明材料类章节，也必须建立相应目录节点，不能只保留方案型章节
  7. 返回标准 JSON 格式，包含章节编号、标题、描述和子章节，编号必须连贯
  8. 除了 JSON 结果外，不要输出任何其他内容，不要输出 markdown 代码块，不要输出解析过程

  JSON格式要求：
  {
    "outline": [
      {
        "id": "1",
        "title": "",
        "description": "",
        "children": [
          {
            "id": "1.1",
            "title": "",
            "description": "",
            "children":[
                {
                  "id": "1.1.1",
                  "title": "",
                  "description": ""
                }
            ]
          }
        ]
      }
    ]
  }
  """
  return system_prompt
  
def generate_outline_prompt(overview, requirements):
  system_prompt = """你是一个专业的标书解析与编制专家，尤其适配本地 DeepSeek 类大模型。根据提供的项目概述和评分要求，生成投标文件目录结构。

  当前阶段只允许输出目录 JSON。
  如上游已生成标准解析报告，目录必须复用该报告，不得在本阶段重新解释出新的评分项、审查项、材料项或风险项。
  等企业资料补齐后，只有在用户明确说“开始生成标书”时，才进入正文生成阶段。

  当前任务只执行到“生成目录”，绝对不能提前生成正文。

  要求：
  1. 目录结构要全面覆盖当前输入能够支持的全部必要章节
  2. 若当前输入仅体现技术评分要求，则生成技术标目录；若输入已明显包含商务、资格、报价、形式评审或完整招标结构要求，则生成完整投标文件目录
  3. 章节名称要专业、准确，符合正式投标文件规范，不得口语化
  4. 一级目录应优先对应评分要求或招标文件明确要求；如评分要求只有内容没有标题，应转写成正式目录标题
  5. 一共包括三级目录
  6. 每个 description 要写明该章节的核心写作内容、对应评分点/审查点、拟附证明材料或支撑内容
  7. 目录应能支撑后续“开始生成标书”后的正式章节内容生成，不能只写空泛题目
  8. 返回标准 JSON 格式，包含章节编号、标题、描述和子章节
  9. 除了 JSON 结果外，不要输出任何其他内容，不要输出 markdown 代码块，不要输出解析报告

  JSON格式要求：
  {
    "outline": [
      {
        "id": "1",
        "title": "",
        "description": "",
        "children": [
          {
            "id": "1.1",
            "title": "",
            "description": "",
            "children":[
                {
                  "id": "1.1.1",
                  "title": "",
                  "description": ""
                }
            ]
          }
        ]
      }
    ]
  }
  """
              
  user_prompt = f"""请基于以下项目信息生成标书目录结构：

  项目概述：
  {overview}

  技术评分要求：
  {requirements}

  请直接输出目录 JSON。
  当前只到“生成目录”这个阶段，不要开始生成标书正文。"""
  return system_prompt, user_prompt


  
def generate_outline_with_old_prompt(overview, requirements, old_outline):
  system_prompt = """你是一个专业的标书解析与编制专家，尤其适配本地 DeepSeek 类大模型。根据提供的项目概述、评分要求和用户已有目录，生成投标文件目录结构。
  用户会提供一个自己编写的目录，你要在充分吸收该目录的基础上，校正缺漏，确保最终目录满足评分要求和正式投标文件要求。

  当前阶段只允许输出目录 JSON。
  如上游已生成标准解析报告，目录必须复用该报告，不得在本阶段重新解释出新的评分项、审查项、材料项或风险项。
  等企业资料补齐后，只有在用户明确说“开始生成标书”时，才进入正文生成阶段。

  当前任务只执行到“生成目录”，不要生成正文。

  要求：
  1. 尽量保留用户已有目录中合理、专业、可复用的章节名称和层级结构
  2. 对缺失的评分点、审查点、证明材料章节必须补齐
  3. 若当前输入仅体现技术评分要求，则生成技术标目录；若输入已明显包含商务、资格、报价、形式评审或完整招标结构要求，则生成完整投标文件目录
  4. 章节名称要专业、准确，符合投标文件规范
  5. 一共包括三级目录
  6. 每个 description 要写清章节用途、对应审查点/评分点、拟附材料或写作重点
  7. 返回标准 JSON 格式，包含章节编号、标题、描述和子章节
  8. 除了 JSON 结果外，不要输出任何其他内容，不要输出 markdown 代码块，不要输出解析报告

  JSON格式要求：
  {
    "outline": [
      {
        "id": "1",
        "title": "",
        "description": "",
        "children": [
          {
            "id": "1.1",
            "title": "",
            "description": "",
            "children":[
                {
                  "id": "1.1.1",
                  "title": "",
                  "description": ""
                }
            ]
          }
        ]
      }
    ]
  }
  """
              
  user_prompt = f"""请基于以下项目信息生成标书目录结构：
  用户自己编写的目录：
  {old_outline}

  项目概述：
  {overview}

  技术评分要求：
  {requirements}

  请结合用户目录输出最终目录 JSON。
  当前只到“生成目录”这个阶段，不要开始生成标书正文。"""
  return system_prompt, user_prompt
