from typing import Dict, Any, List, AsyncGenerator
import asyncio
import json
import os
import re

from ...utils.outline_util import generate_one_outline_json_by_level1
from ...utils import prompt_manager
from ...utils import generation_policy
from ...utils.json_util import check_json, extract_json_string
from ...models.schemas import AnalysisReport, ResponseMatrix, ReviewReport
from ..enterprise_material_service import EnterpriseMaterialService
from ..fallback_generation import FallbackGenerationMixin


class ReviewGenerationMixin:
    async def generate_consistency_revision_report(
        self,
        full_bid_draft: Dict[str, Any] | List[Dict[str, Any]],
        analysis_report: Dict[str, Any] | None = None,
        response_matrix: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """生成全文一致性修订报告。"""
        report = analysis_report or {}
        if self._force_local_fallback():
            return {"ready_for_export": False, "issues": [], "coverage_check": [], "missing_blocks": [], "summary": {"blocking_count": 0, "high_count": 0, "can_export_after_auto_fix": False, "manual_data_needed": []}}
        system_prompt, user_prompt = prompt_manager.generate_consistency_revision_prompt(
            analysis_report=report,
            full_bid_draft=full_bid_draft,
            response_matrix=response_matrix or report.get("response_matrix") or {},
            reference_bid_style_profile=reference_bid_style_profile or report.get("reference_bid_style_profile") or {},
            document_blocks_plan=document_blocks_plan or report.get("document_blocks_plan") or {},
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        schema = prompt_manager.get_consistency_revision_schema()
        try:
            content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema=schema,
                    max_retries=1,
                    temperature=0.1,
                    response_format=self._example_response_format("consistency_revision_report", schema),
                    log_prefix="一致性修订",
                    raise_on_fail=True,
                ),
                timeout=120,
            )
            return json.loads(content.strip())
        except Exception as e:
            if not self._generation_fallbacks_enabled():
                raise self._fallback_disabled_error("一致性修订", str(e)) from e
            print(f"一致性修订模型输出不可用，返回兜底报告：{str(e)}")
            return {
                "ready_for_export": False,
                "issues": [{"id": "ISS-01", "severity": "high", "issue_type": "other", "chapter_id": "", "original_text": "", "problem": "一致性修订模型不可用", "fix_suggestion": "导出前人工核对项目名称、日期、期限、材料和历史残留。"}],
                "coverage_check": [],
                "missing_blocks": [],
                "summary": {"blocking_count": 0, "high_count": 1, "can_export_after_auto_fix": False, "manual_data_needed": []},
            }

    async def generate_response_matrix(
        self,
        analysis_report: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """基于标准解析报告生成响应矩阵。可选吸收成熟样例风格，但不新增强制招标要求。"""
        report = analysis_report or {}
        style_profile = reference_bid_style_profile or report.get("reference_bid_style_profile") or {}
        if self._force_local_fallback():
            return self._fallback_response_matrix(report)

        system_prompt, user_prompt = prompt_manager.generate_response_matrix_prompt(
            report,
            style_profile,
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return await asyncio.wait_for(
                self._generate_pydantic_json(
                    messages=messages,
                    model_cls=ResponseMatrix,
                    max_retries=1,
                    temperature=0.1,
                    response_format=self._pydantic_response_format("response_matrix", ResponseMatrix),
                    max_tokens=4096,
                    log_prefix="响应矩阵",
                ),
                timeout=90,
            )
        except Exception as e:
            if not self._generation_fallbacks_enabled():
                raise self._fallback_disabled_error("响应矩阵", str(e)) from e
            print(f"响应矩阵模型输出不可用，启用兜底矩阵：{str(e)}")
            return self._fallback_response_matrix(report)

    async def generate_compliance_review(
        self,
        outline: list,
        analysis_report: Dict[str, Any] | None = None,
        project_overview: str = "",
        response_matrix: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """生成导出前合规审校报告"""
        if self._force_local_fallback():
            return self._fallback_compliance_review(outline, analysis_report)

        system_prompt, user_prompt = prompt_manager.generate_compliance_review_prompt(
            analysis_report=analysis_report,
            outline=outline,
            project_overview=project_overview,
            response_matrix=response_matrix or (analysis_report or {}).get("response_matrix"),
            reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
            document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return await asyncio.wait_for(
                self._generate_pydantic_json(
                    messages=messages,
                    model_cls=ReviewReport,
                    max_retries=1,
                    temperature=0.2,
                    response_format=self._pydantic_response_format("review_report", ReviewReport),
                    log_prefix="合规审校",
                ),
                timeout=120,
            )
        except Exception as e:
            if not self._generation_fallbacks_enabled():
                raise self._fallback_disabled_error("合规审校", str(e)) from e
            print(f"合规审校模型输出不可用，启用文本兜底审校：{str(e)}")
            return self._fallback_compliance_review(outline, analysis_report)
