"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from .core import _json, _schema_contract, get_full_bid_rulebook
from .schemas import get_consistency_revision_schema, get_review_report_schema


def generate_compliance_review_prompt(
    analysis_report: Dict[str, Any],
    outline: List[Dict[str, Any]],
    project_overview: str = "",
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
    include_schema_in_prompt: bool = True,
) -> Tuple[str, str]:
    schema_json = _json(get_review_report_schema(), indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是投标文件导出前合规审校专家。目标是在 Word 导出前检查正文、表格、占位符、附件清单、图表素材和目录映射的导出风险。

输出契约：
1. 只输出合法 ReviewReport JSON，不输出 markdown。
2. 只能依据传入 AnalysisReport、ResponseMatrix、ReferenceBidStyleProfile、document_blocks_plan 和 outline_with_content 审校，不得新增招标要求。
3. revision_plan 必须给出可执行修订动作。

必须检查：
1. 项目名称、招标人、投标人、日期、服务期限/工期/交付期是否统一，是否残留历史项目或历史日期。
2. 输出范围是否正确：technical_only/service_plan 不得混入报价、保证金、投标函、资格审查资料正文；full_bid 不得遗漏 required 卷册。
3. AnalysisReport.bid_document_requirements、selected_generation_target、composition 顺序、base_outline_items、scheme_or_technical_outline_requirements 是否全覆盖。
4. ResponseMatrix 和 AnalysisReport 中的评分项、审查项、实质性条款、材料项、风险项是否覆盖。
5. 方案目录、承诺书、表格、证明材料、固定格式、签章、报价隔离、暗标规则是否满足。
6. 企业资料缺失是否保留明确占位，是否把缺失资料写成已具备。
7. 图表与素材规划中的必需表格、组织图、流程图、承诺书、图片/证书/截图占位是否存在。
8. 页码、附件索引、响应页码是否使用 〖页码待编排〗 或等待 Word 自动更新。

阻塞判定：
1. blocking=true 的废标风险、实质性条款、固定格式、签章、报价隔离、暗标身份泄露、企业资料虚构未处理时，summary.ready_to_export=false。
2. 历史日期、历史项目名称、历史招标人名称 severity=blocking 或 high。

{rulebook}

{_schema_contract("ReviewReport JSON", schema_json, include_schema_in_prompt)}
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
    include_schema_in_prompt: bool = True,
) -> Tuple[str, str]:
    schema_json = _json(get_consistency_revision_schema(), indent=2)
    system_prompt = f"""你是投标文件全文一致性修订专家。目标是在 Word 导出前检查全文一致性，只输出问题和修订建议，不直接改写全文。

输出契约：
1. 只输出合法 JSON。
2. 不直接改写全文，只输出问题、依据、严重度和修订建议。

检查范围：
1. 项目名称、招标人、投标人、日期、服务期限/工期/交付期、承诺周期。
2. 历史项目残留、行业错配、企业资料虚构、输出范围错误。
3. 缺少图表/承诺/素材块、评分项覆盖、投标文件格式章节和组成要求。

严重度：
1. 历史残留、日期/项目名称/招标人不一致，severity 至少为 high。
2. 服务期限/工期/交付期承诺与招标文件不一致，severity=blocking。
3. 企业资料虚构，severity=blocking。
4. 技术/服务方案中出现报价、保证金、投标函正文，severity=high 或 blocking。

{_schema_contract("ConsistencyRevisionReport JSON", schema_json, include_schema_in_prompt)}
"""
    user_prompt = f"""请输出全文一致性修订报告。

<analysis_report>{_json(analysis_report or {}, indent=2)}</analysis_report>
<response_matrix>{_json(response_matrix or (analysis_report or {}).get('response_matrix') or {}, indent=2)}</response_matrix>
<reference_bid_style_profile>{_json(reference_bid_style_profile or (analysis_report or {}).get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile>
<document_blocks_plan>{_json(document_blocks_plan or (analysis_report or {}).get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan>
<full_bid_draft>{_json(full_bid_draft or {}, indent=2)}</full_bid_draft>

直接返回 JSON。"""
    return system_prompt, user_prompt
