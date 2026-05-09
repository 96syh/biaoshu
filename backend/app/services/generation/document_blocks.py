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


class DocumentBlocksGenerationMixin:
    @classmethod
    def _normalize_document_blocks_payload(cls, content: str) -> Dict[str, Any]:
        """兼容图表素材规划返回数组、包裹对象或缺省顶层键。"""
        payload = cls._loads_json_loose(content)
        if isinstance(payload, list):
            payload = {"document_blocks": payload}
        if not isinstance(payload, dict):
            payload = {}

        for key in ("document_blocks_plan", "blocks_plan", "plan", "data", "result"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                payload = nested
                break
            if isinstance(nested, list):
                payload = {"document_blocks": nested}
                break

        if "document_blocks" not in payload:
            for key in ("blocks", "chapters", "items"):
                if isinstance(payload.get(key), list):
                    payload["document_blocks"] = payload[key]
                    break
        payload.setdefault("document_blocks", [])
        payload.setdefault("missing_assets", [])
        payload.setdefault("missing_enterprise_data", [])
        if not isinstance(payload["document_blocks"], list):
            payload["document_blocks"] = []
        if not isinstance(payload["missing_assets"], list):
            payload["missing_assets"] = []
        if not isinstance(payload["missing_enterprise_data"], list):
            payload["missing_enterprise_data"] = []
        return payload

    async def generate_document_blocks_plan(
        self,
        outline: List[Dict[str, Any]] | Dict[str, Any],
        analysis_report: Dict[str, Any] | None = None,
        response_matrix: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        enterprise_materials: List[Dict[str, Any]] | None = None,
        asset_library: List[Dict[str, Any]] | Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """生成图表、表格、承诺书、图片、证明材料等文档块规划。"""
        report = analysis_report or {}
        style_profile = reference_bid_style_profile or report.get("reference_bid_style_profile") or {}
        matrix = response_matrix or report.get("response_matrix") or {}
        timeout_seconds = self._int_env("YIBIAO_DOCUMENT_BLOCKS_TIMEOUT_SECONDS", 240)
        if self._force_local_fallback():
            return {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []}
        system_prompt, user_prompt = prompt_manager.generate_document_blocks_prompt(
            analysis_report=report,
            outline=outline,
            response_matrix=matrix,
            reference_bid_style_profile=style_profile,
            enterprise_materials=enterprise_materials or [],
            asset_library=asset_library or [],
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        schema = prompt_manager.get_document_blocks_schema()
        try:
            content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema={},
                    max_retries=0,
                    temperature=0.15,
                    response_format=self._example_response_format("document_blocks_plan", schema),
                    log_prefix="图表素材规划",
                    raise_on_fail=True,
                ),
                timeout=timeout_seconds,
            )
            return self._normalize_document_blocks_payload(content)
        except Exception as e:
            if not self._generation_fallbacks_enabled():
                raise self._fallback_disabled_error("图表素材规划", str(e)) from e
            print(f"图表素材规划模型输出不可用，返回空规划：{str(e)}")
            return {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []}
