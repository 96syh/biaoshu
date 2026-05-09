"""兼容 re-export：实际提示词实现已拆分到 app.utils.prompts。"""
from .prompts.core import _json, _schema_contract, get_full_bid_rulebook
from .prompts.outline_templates import _node, get_generic_service_plan_outline_template, get_design_service_outline_template
from .prompts.schemas import get_reference_bid_style_profile_schema, get_bid_document_requirements_schema, get_analysis_report_schema, get_response_matrix_schema, get_document_blocks_schema, get_review_report_schema, get_consistency_revision_schema
from .prompts.reference_profile import generate_reference_bid_style_profile_prompt
from .prompts.analysis import generate_analysis_report_prompt, generate_response_matrix_prompt
from .prompts.outline import generate_level1_outline_prompt, generate_level23_outline_prompt
from .prompts.document_blocks import generate_document_blocks_prompt
from .prompts.content import generate_chapter_content_prompt
from .prompts.review import generate_compliance_review_prompt, generate_consistency_revision_prompt
from .prompts.legacy_outline import read_expand_outline_prompt, generate_outline_prompt, generate_outline_with_old_prompt

__all__ = [
    "_json",
    "_schema_contract",
    "get_full_bid_rulebook",
    "_node",
    "get_generic_service_plan_outline_template",
    "get_design_service_outline_template",
    "get_reference_bid_style_profile_schema",
    "get_bid_document_requirements_schema",
    "get_analysis_report_schema",
    "get_response_matrix_schema",
    "get_document_blocks_schema",
    "get_review_report_schema",
    "get_consistency_revision_schema",
    "generate_reference_bid_style_profile_prompt",
    "generate_analysis_report_prompt",
    "generate_response_matrix_prompt",
    "generate_level1_outline_prompt",
    "generate_level23_outline_prompt",
    "generate_document_blocks_prompt",
    "generate_chapter_content_prompt",
    "generate_compliance_review_prompt",
    "generate_consistency_revision_prompt",
    "read_expand_outline_prompt",
    "generate_outline_prompt",
    "generate_outline_with_old_prompt",
]
