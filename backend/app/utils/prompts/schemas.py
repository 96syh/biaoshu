"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict


def get_reference_bid_style_profile_schema() -> Dict[str, Any]:
    return {
        "profile_name": "",
        "document_scope": "full_bid | technical_only | technical_service_plan | service_plan | business_volume | qualification_volume | price_volume | unknown",
        "recommended_use_case": "",
        "template_intent": {
            "how_to_use": "",
            "reuse_boundaries": [],
            "must_map_from_tender": [],
            "must_map_from_enterprise": [],
            "must_keep_as_placeholder": [],
        },
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
        "word_style_profile": {
            "page_size": "A4",
            "orientation": "portrait",
            "margin_top": "2.2cm",
            "margin_bottom": "2.2cm",
            "margin_left": "2.7cm",
            "margin_right": "2.2cm",
            "body_font_family": "宋体",
            "body_font_size": "10.5pt",
            "body_line_height": "1.5",
            "body_first_line_indent": "2em",
            "heading_font_family": "黑体",
            "heading_1_size": "16pt",
            "heading_2_size": "14pt",
            "heading_3_size": "12pt",
            "table_font_size": "9pt",
            "table_border_style": "single",
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
        "chapter_blueprints": [
            {
                "chapter_title": "",
                "applies_when": [],
                "writing_function": "响应招标要求 | 回应评分项 | 展示企业能力 | 承诺履约结果 | 固定格式填报 | 素材展示",
                "recommended_structure": [],
                "paragraph_blueprint": [
                    {
                        "purpose": "",
                        "opening_pattern": "",
                        "content_slots": [],
                        "closing_rule": "",
                    }
                ],
                "tender_fact_slots": [],
                "enterprise_fact_slots": [],
                "tables_to_insert": [],
                "assets_to_insert": [],
                "do_not_copy": [],
            }
        ],
        "writing_style": {
            "voice": "第一人称公司主体，如“我公司”",
            "tone": "正式、承诺式、专业投标文件语气",
            "paragraph_style": "条理化分点",
            "common_patterns": [],
            "forbidden_patterns": ["AI自述", "泛泛宣传", "历史项目残留"],
            "sentence_blueprints": [
                {
                    "scene": "",
                    "pattern": "",
                    "required_variables": [],
                    "avoid": "",
                }
            ],
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
                "image_url": "",
                "image_alt": "",
                "source_ref": "",
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
        "enterprise_material_profile": {
            "requirements": [{
                "id": "EM-R-01",
                "name": "",
                "material_type": "资质/业绩/人员/设备/证书/图片/承诺/报价/其他",
                "required_by": [],
                "source": "",
                "required": True,
                "blocking": False,
                "placeholder": "〖待补充：具体资料名称〗",
                "status": "missing",
                "validation_rule": "人工核对原件、有效期、主体名称、页码和招标文件要求是否一致",
            }],
            "provided_materials": [{
                "id": "EM-P-01",
                "name": "",
                "material_type": "",
                "source": "",
                "used_by": [],
                "confidence": "unknown",
                "verification_status": "unverified",
            }],
            "missing_materials": [{
                "id": "EM-R-01",
                "name": "",
                "material_type": "",
                "required_by": [],
                "source": "",
                "required": True,
                "blocking": False,
                "placeholder": "〖待补充：具体资料名称〗",
                "status": "missing",
                "validation_rule": "",
            }],
            "verification_tasks": [],
            "summary": "",
        },
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
