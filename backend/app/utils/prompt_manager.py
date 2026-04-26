
import json


def get_full_bid_rulebook():
  """从完整标书模板提炼出的通用风控规则，供多阶段提示词复用"""
  return """标书编制通用风控规则：
1. 以招标文件原文为唯一准绳；否决项、无效投标项、实质性条款、格式强制项、签字盖章项、资格条件、时间条件必须单独识别。
2. 不得编造企业名称、资质、业绩、人员、财务、报价、税率、日期、证书编号、社保、发票、合同、信用查询结果或联系方式。
3. 未提供或无法核实的信息必须标记为【待补充】、【待确认】、【待补证】、【待提供扫描件】或【待提供查询截图】。
4. 招标人给定的投标函、报价表、费用明细表、承诺函、偏离表等固定格式，不得擅自改表头、列名、固定文字、行列数量。
5. 对同一要求多处表述不一致时，采用最完整且最严格版本，并登记为风险或冲突提示。
6. 业绩证据链必须区分框架协议、子合同/任务书、合同关键页、发票、税务查验截图、业主证明；仅有框架协议不得直接判定为有效业绩。
7. 人员材料必须关注身份证、职称/注册证、社保、劳动关系、退休返聘、人员业绩和社保时间窗口。
8. 信誉材料必须关注查询平台、查询对象、查询口径、截图页面和对应承诺函。
9. 报价规则必须关注报价方式、税率、小数位、唯一报价、算术修正、缺漏项处理和禁止改动格式。
10. 页码未最终排版前，响应页码/投标文件页码统一使用【页码待编排】。
11. 技术方案必须紧贴评分办法逐项响应，包含组织结构、岗位分工、流程、时限、节点、控制措施、成果形式，避免空泛套话。
12. 当企业资料与招标要求不匹配时，应登记差异和风险，不得把不满足项写成满足。"""


def get_analysis_report_schema():
  """结构化标准解析报告 JSON 模板"""
  return {
    "project": {
      "name": "",
      "number": "",
      "package_name": "",
      "purchaser": "",
      "project_type": "",
      "budget": "",
      "service_scope": "",
      "service_period": "",
      "service_location": "",
      "quality_requirements": "",
      "bid_validity": "",
      "bid_bond": "",
      "performance_bond": "",
      "bid_deadline": "",
      "submission_requirements": "",
      "signature_requirements": ""
    },
    "bid_mode_recommendation": "technical_only",
    "bid_structure": [
      {
        "id": "S-01",
        "parent_id": "",
        "title": "",
        "purpose": "",
        "category": "资格/商务/技术/报价/承诺/附件",
        "required": True,
        "fixed_format": False,
        "signature_required": False,
        "attachment_required": False,
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
        "source": ""
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
        "source": ""
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
        "source": ""
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
      "tax_requirement": "",
      "decimal_places": "",
      "uniqueness_requirement": "",
      "form_requirements": "",
      "arithmetic_correction_rule": "",
      "missing_item_rule": "",
      "prohibited_format_changes": []
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
        "response_strategy": ""
      }
    ],
    "rejection_risks": [
      {
        "id": "R-01",
        "risk": "",
        "source": "",
        "mitigation": ""
      }
    ],
    "fixed_format_forms": [
      {
        "id": "FF-01",
        "name": "",
        "source": "",
        "required_columns": [],
        "fixed_text": "",
        "fill_rules": ""
      }
    ],
    "signature_requirements": [
      {
        "id": "SIG-01",
        "target": "",
        "signer": "",
        "seal": "",
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
        "status": "missing"
      }
    ],
    "missing_company_materials": [
      {
        "id": "X-01",
        "name": "",
        "used_by": ["Q-01", "T-01"],
        "placeholder": "【待补充：具体资料名称】"
      }
    ]
  }


def get_review_report_schema():
  """导出前合规审校 JSON 模板"""
  return {
    "coverage": [
      {
        "item_id": "T-01",
        "covered": True,
        "chapter_ids": ["1.1.1"],
        "issue": ""
      }
    ],
    "missing_materials": [
      {
        "material_id": "M-01",
        "chapter_ids": ["2.1.1"],
        "placeholder": "【待补充：具体资料名称】"
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
        "reason": ""
      }
    ],
    "fixed_format_issues": [
      {
        "item_id": "FF-01",
        "chapter_ids": ["2.1.1"],
        "issue": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "signature_issues": [
      {
        "item_id": "SIG-01",
        "chapter_ids": ["2.1.1"],
        "issue": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "price_rule_issues": [
      {
        "item_id": "P-01",
        "chapter_ids": ["3.1.1"],
        "issue": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "evidence_chain_issues": [
      {
        "item_id": "EV-01",
        "chapter_ids": ["4.1.1"],
        "issue": "",
        "severity": "blocking",
        "blocking": True
      }
    ],
    "page_reference_issues": [
      {
        "item_id": "PAGE-01",
        "chapter_ids": ["1.1.1"],
        "issue": "",
        "severity": "warning",
        "blocking": False
      }
    ],
    "summary": {
      "ready_to_export": False,
      "blocking_issues": 0,
      "warnings": 0
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
9. 必须同时提取形式评审、资格评审、响应性评审、商务评分、技术评分、价格规则、固定格式、签字盖章、页码占位和证据链要求；若招标文件没有对应内容则输出空数组或空字符串。
10. 如果文档明显只要求技术标，bid_mode_recommendation 输出 technical_only；如果出现完整资格/商务/报价/承诺/附件组卷要求，输出 full_bid。
11. 为避免 JSON 被截断，每个数组最多输出最关键 8 项；单个字段内容尽量压缩到 80 字以内；不得为了完整复述原文而输出长段落。
12. 若同类要求很多，优先保留否决项、实质性条款、评分项、签章/格式要求和材料要求，其余合并概括到 risk、writing_focus 或 source。

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


def generate_compliance_review_prompt(analysis_report, outline, project_overview=""):
  """生成导出前合规审校提示词"""
  schema_json = json.dumps(get_review_report_schema(), ensure_ascii=False, indent=2)
  analysis_report_json = json.dumps(analysis_report or {}, ensure_ascii=False, indent=2)
  outline_json = json.dumps(outline or [], ensure_ascii=False, indent=2)
  rulebook = get_full_bid_rulebook()
  system_prompt = f"""你是专业投标文件合规审校专家。你的任务是在 Word 导出前检查标书内容是否覆盖评分项、审查项和风险点。

要求：
1. 只输出合法 ReviewReport JSON，不输出 markdown 代码块，不输出解释文字。
2. coverage 检查 AnalysisReport 中 bid_structure、formal_review_items、qualification_review_items、responsiveness_review_items、business_scoring_items、technical_scoring_items、price_scoring_items、qualification_requirements、formal_response_requirements、mandatory_clauses 是否被正文或目录覆盖。
3. missing_materials 检查 required_materials 和 missing_company_materials 是否在相关章节中保留了明确占位或材料清单。
4. rejection_risks 检查 rejection_risks 是否已有响应或规避说明。
5. duplication_issues 检查明显重复章节或重复正文。
6. fabrication_risks 检查疑似虚构企业名称、金额、日期、证书编号、业绩、人员、合同、发票、联系方式等风险。
7. fixed_format_issues 检查固定格式表头、列名、固定文字、行列数量是否被改动或缺失。
8. signature_issues 检查签字盖章位置、签署主体、盖章要求是否遗漏。
9. price_rule_issues 检查报价方式、税率、小数位、唯一报价、算术修正、缺漏项处理、费用明细表格式要求。
10. evidence_chain_issues 检查业绩、人员、社保、发票、税务查验、信用截图、保证金凭证等证据链是否完整。
11. page_reference_issues 检查索引表和响应页码；未最终排版时应使用【页码待编排】。
12. 若存在未覆盖评分项/评审项、未处理废标风险、固定格式被破坏、签章遗漏、报价规则不满足、证据链缺失或缺失证明材料未标注，summary.ready_to_export 必须为 false。
13. 所有阻塞项 severity 使用 blocking 且 blocking=true；提示项 severity 使用 warning。

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

<outline_with_content>
{outline_json}
</outline_with_content>

直接返回 ReviewReport JSON，不要任何额外说明或格式标记。"""
  return system_prompt, user_prompt


def read_expand_outline_prompt():
  '''从简版技术方案中提取目录的提示词'''
  system_prompt = """你是一个专业的标书解析与编制专家，当前任务是从用户提交的简版技术方案中提取并重建目录结构。

  你必须严格按照以下工作流在内部执行，但当前阶段只允许输出目录 JSON：
  第一步：先做《标准解析报告》
  - 提取项目名称、项目编号、标段、招标人、服务范围、服务地点、服务工期、服务质量、投标有效期、投标保证金等基础信息
  - 提取否决投标条款、实质性响应条款、资格审查要求、资质要求、财务要求、业绩要求、信誉要求、人员要求、联合体要求、其他要求
  - 提取商务评分项、技术评分项、正式投标文件结构要求、表格类文件、函件类文件、承诺类文件、证明材料类文件
  - 提取待补充的企业资料清单，以及高风险废标点、易漏项、易错项
  第二步：再依据解析报告生成目录
  第三步：只有当用户明确下达“开始生成标书”指令时，才进入正文生成阶段

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

  你必须严格按照以下顺序在内部执行，但当前阶段只允许输出目录 JSON：
  第一步：先做《标准解析报告》
  - 提取项目基础信息、项目目标、采购范围、服务范围、实施边界
  - 提取否决投标条款、实质性条款、资格审查项、资质项、财务项、业绩项、信誉项、人员项、联合体要求、其他要求
  - 提取商务评分项、技术评分项、各评分项对应的证明材料和写作重点
  - 识别正式投标文件结构、固定格式表单、承诺函、偏离表、证明材料章节、需企业补充资料清单和高风险废标点
  第二步：依据解析报告生成目录
  第三步：等企业资料补齐后，只有在用户明确说“开始生成标书”时，才进入正文生成阶段

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

  先在内部完成《标准解析报告》，再输出目录 JSON。
  当前只到“先做标准解析报告；然后生成目录”这个阶段，不要开始生成标书正文。"""
  return system_prompt, user_prompt


  
def generate_outline_with_old_prompt(overview, requirements, old_outline):
  system_prompt = """你是一个专业的标书解析与编制专家，尤其适配本地 DeepSeek 类大模型。根据提供的项目概述、评分要求和用户已有目录，生成投标文件目录结构。
  用户会提供一个自己编写的目录，你要在充分吸收该目录的基础上，校正缺漏，确保最终目录满足评分要求和正式投标文件要求。

  你必须严格按照以下顺序在内部执行，但当前阶段只允许输出目录 JSON：
  第一步：先做《标准解析报告》
  - 提取项目基础信息、采购范围、服务范围、实施边界
  - 提取否决投标条款、资格审查项、评分项、固定格式文件、证明材料要求和高风险废标点
  - 判断用户已有目录哪些可以保留、哪些需要补充、哪些需要改写
  - 提取需企业补充的资料清单，为后续“开始生成标书”做准备
  第二步：依据解析报告和用户已有目录生成最终目录
  第三步：等企业资料补齐后，只有在用户明确说“开始生成标书”时，才进入正文生成阶段

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

  先在内部完成《标准解析报告》，再结合用户目录输出最终目录 JSON。
  当前只到“先做标准解析报告；然后生成目录”这个阶段，不要开始生成标书正文。"""
  return system_prompt, user_prompt
