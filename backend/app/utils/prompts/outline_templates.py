"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, List


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
