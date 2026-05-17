"""历史标书案例库 API。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..services.openai_service import OpenAIService
from ..services.history_case_service import HistoryCaseService
from ..services.generation_cache_service import GenerationCacheService
from ..utils.config_manager import config_manager
from ..utils.json_util import extract_json_string
from ..utils.provider_registry import get_provider_auth_error
from ..utils import prompt_manager


class HistoryCaseSearchRequest(BaseModel):
    query: str = Field(..., description="检索关键词")
    limit: int = Field(10, ge=1, le=50, description="最大返回条数")


class ReferenceMatchRequest(BaseModel):
    file_content: str = Field(..., description="当前上传招标文件解析文本")
    analysis_report: Dict[str, Any] = Field(default_factory=dict, description="可选：结构化标准解析报告")
    limit: int = Field(8, ge=3, le=15, description="候选数量")
    use_llm: bool = Field(True, description="是否使用 LLM 在候选案例中择优")


class RequirementCheckRequest(BaseModel):
    analysis_report: Dict[str, Any] = Field(..., description="结构化标准解析报告")
    limit_per_item: int = Field(3, ge=1, le=5, description="每个要求项最多返回的历史证据数量")
    use_llm: bool = Field(True, description="是否使用 LLM 对检索证据做二次判断")


class HistoryCaseController:
    """历史案例统计、检索、要求核对和样例匹配控制器。"""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/history-cases", tags=["历史标书案例库"])
        self.router.get("/summary")(self.get_summary)
        self.router.get("/projects")(self.list_projects)
        self.router.get("/domains")(self.list_domains)
        self.router.post("/search")(self.search)
        self.router.post("/check-requirements")(self.check_requirements)
        self.router.post("/match-reference")(self.match_reference)

    async def get_summary(self):
        """返回历史标书案例库统计。"""
        return HistoryCaseService.summary()

    async def list_projects(
        self,
        limit: int = Query(100, ge=1, le=500),
        year: str = Query("", description="按年份过滤，如 2025"),
        subject: str = Query("", description="按投标主体/标签模糊过滤"),
        result: str = Query("", description="按结果过滤，如 中标、未中、流标"),
        domain: str = Query("", description="按领域过滤，如 石油、燃气、化工"),
    ):
        """列出已入库的历史项目。"""
        return {
            "success": True,
            "projects": HistoryCaseService.list_projects(
                limit=limit,
                year=year,
                subject=subject,
                result=result,
                domain=domain,
            ),
        }

    async def list_domains(self):
        """列出历史项目领域分类统计。"""
        return {
            "success": True,
            "domains": HistoryCaseService.list_domains(),
        }

    async def search(self, request: HistoryCaseSearchRequest):
        """全文检索历史标书内容，并返回来源文档和 PageIndex 树路径。"""
        return {
            "success": True,
            "results": HistoryCaseService.search(query=request.query, limit=request.limit),
        }

    async def check_requirements(self, request: RequirementCheckRequest):
        """用历史中标案例库核对标准解析中的评分项、资质项是否已有满足证据。"""
        result = HistoryCaseService.check_requirements(
            analysis_report=request.analysis_report,
            limit_per_item=request.limit_per_item,
        )
        llm_reason = ""
        if request.use_llm and result["checks"]:
            llm_reason = await self._apply_requirement_llm_judgment(result)

        return {
            "success": True,
            "message": "历史案例库要求项校验完成",
            "summary": result["summary"],
            "checks": result["checks"],
            "llm_reason": llm_reason,
        }

    async def match_reference(self, request: ReferenceMatchRequest):
        """根据当前招标文件自动匹配历史成熟案例，并生成可复用样例风格剖面。"""
        cache_key = GenerationCacheService.build_key(
            "history_reference_match",
            str(config_manager.load_config().get("model_name", "")),
            {"workflow": "pageindex_history_v2", **request.model_dump(mode="json")},
        )
        cached = GenerationCacheService.get("history_reference_match", cache_key)
        if isinstance(cached, dict):
            return cached

        candidates = HistoryCaseService.match_candidates(
            tender_text=request.file_content,
            analysis_report=request.analysis_report,
            limit=request.limit,
        )
        if not candidates:
            return {
                "success": False,
                "message": "历史案例库未匹配到可用候选",
                "candidates": [],
            }

        selected, llm_reason = await self._select_candidate(request, candidates)
        pageindex_context = HistoryCaseService.load_pageindex_context_for_candidate(selected)
        profile_source = pageindex_context or HistoryCaseService.load_markdown(str(selected.get("markdown_path") or ""))
        if not profile_source:
            return {
                "success": False,
                "message": "已匹配候选，但无法读取历史案例 PageIndex/Markdown 文本",
                "matched_case": selected,
                "candidates": candidates,
            }

        profile, llm_reason = await self._build_reference_profile(profile_source, selected, llm_reason)
        result = {
            "success": True,
            "message": f"已自动匹配历史案例：{selected.get('project_title')}",
            "matched_case": selected,
            "candidates": candidates,
            "llm_reason": llm_reason,
            "reference_bid_style_profile": profile,
        }
        GenerationCacheService.set("history_reference_match", cache_key, result)
        return result

    @staticmethod
    def _refresh_requirement_summary(result: dict) -> None:
        result["summary"]["satisfied"] = sum(1 for check in result["checks"] if check.get("satisfied"))
        result["summary"]["not_found"] = result["summary"]["total"] - result["summary"]["satisfied"]

    async def _apply_requirement_llm_judgment(self, result: dict) -> str:
        try:
            judged, llm_reason = await _judge_requirement_checks_with_llm(result["checks"])
            if judged:
                judge_map = {str(item.get("item_id")): item for item in judged}
                for check in result["checks"]:
                    judgment = judge_map.get(str(check.get("item_id")))
                    if not judgment:
                        continue
                    check["satisfied"] = bool(judgment.get("satisfied")) and bool(check.get("evidence"))
                    check["confidence"] = max(
                        float(check.get("confidence") or 0),
                        min(0.98, max(0.0, float(judgment.get("confidence") or 0))),
                    )
                    if judgment.get("reason"):
                        check["reason"] = str(judgment.get("reason"))
                self._refresh_requirement_summary(result)
            return llm_reason
        except Exception as exc:
            return f"LLM 判定失败，已使用历史库检索规则结果：{str(exc)}"

    async def _select_candidate(self, request: ReferenceMatchRequest, candidates: list[dict]) -> tuple[dict, str]:
        selected = candidates[0]
        llm_reason = ""
        if not request.use_llm:
            return selected, llm_reason

        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            return selected, f"LLM 选择跳过，已使用规则得分最高候选：{auth_error}"

        try:
            selected_id, llm_reason = await _select_reference_candidate_with_llm(
                request.file_content,
                request.analysis_report,
                candidates,
            )
            selected = next((item for item in candidates if item.get("project_id") == selected_id), selected)
            guarded_selected, guard_reason = HistoryCaseService.validate_reference_selection(
                selected,
                candidates,
                request.file_content,
                request.analysis_report,
            )
            if guard_reason:
                selected = guarded_selected
                llm_reason = f"{llm_reason}；{guard_reason}" if llm_reason else guard_reason
        except Exception as exc:
            llm_reason = f"LLM 选择失败，已使用规则得分最高候选：{str(exc)}"
        return selected, llm_reason

    @staticmethod
    async def _build_reference_profile(profile_source: str, selected: dict, llm_reason: str) -> tuple[dict, str]:
        try:
            profile = await OpenAIService().generate_reference_bid_style_profile(profile_source)
        except Exception as exc:
            profile = _build_rule_based_reference_profile(profile_source, selected, str(exc))
            warning = f"成熟样例剖面模型生成失败，已使用规则模板：{str(exc)}"
            llm_reason = f"{llm_reason}；{warning}" if llm_reason else warning

        profile.setdefault("source_history_case", {
            "project_id": selected.get("project_id"),
            "project_title": selected.get("project_title"),
            "document_id": selected.get("best_document_id"),
            "file_name": selected.get("best_file_name"),
            "document_category": selected.get("best_document_category"),
            "document_category_basis": selected.get("best_document_category_basis"),
            "primary_domain": selected.get("primary_domain"),
            "pageindex_tree_path": selected.get("pageindex_tree_path"),
            "pageindex_node_id": selected.get("best_pageindex_node_id"),
            "node_title": selected.get("best_node_title"),
            "node_path": selected.get("best_node_path"),
            "profile_source": "pageindex_nodes",
        })
        return profile, llm_reason


controller = HistoryCaseController()
router = controller.router


def _build_rule_based_reference_profile(markdown: str, selected: Dict[str, Any], failure_reason: str = "") -> Dict[str, Any]:
    """Build a minimal usable profile when the model cannot parse the matched case."""
    profile = json.loads(json.dumps(prompt_manager.get_reference_bid_style_profile_schema(), ensure_ascii=False))
    headings: list[dict[str, Any]] = []
    for raw in str(markdown or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        markdown_heading = re.match(r"^(#{1,3})\s+(.{2,80})$", line)
        numbered_heading = re.match(
            r"^((?:第[一二三四五六七八九十百\d]+[章节篇部分])|(?:[一二三四五六七八九十]+[、.．])|(?:\d+(?:\.\d+){0,2}[、.．]))\s*(.{2,70})$",
            line,
        )
        if markdown_heading:
            level = len(markdown_heading.group(1))
            title = markdown_heading.group(2).strip()
        elif numbered_heading:
            level = 1 if numbered_heading.group(1).startswith("第") else 2
            title = re.sub(r"^\d+(?:\.\d+){0,2}[、.．]\s*", "", line).strip()
            title = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", title).strip()
        else:
            continue
        if title and not any(item["title"] == title for item in headings):
            headings.append({"title": title, "level": max(1, min(3, level))})
        if len(headings) >= 12:
            break

    if not headings:
        headings = [{"title": str(selected.get("project_title") or "历史案例写作模板"), "level": 1}]

    profile["profile_name"] = "历史案例库规则匹配模板"
    profile["document_scope"] = "technical_service_plan"
    profile["recommended_use_case"] = "模型模板解析不可用时，作为目录结构和正文风格的保守参考"
    profile["template_intent"] = {
        "how_to_use": "仅迁移历史案例的目录层级、章节功能和版式习惯；所有事实必须重新映射到当前招标文件和企业资料。",
        "reuse_boundaries": ["不得照抄历史项目名称、人员、业绩、日期、金额和承诺时限"],
        "must_map_from_tender": ["项目名称", "服务范围", "服务期限", "评分标准", "投标文件格式"],
        "must_map_from_enterprise": ["企业资质", "人员", "业绩", "证书", "图片/附件"],
        "must_keep_as_placeholder": ["缺失企业资料", "缺失图片素材", "最终页码"],
    }
    profile["outline_template"] = [
        {
            "id": str(index),
            "title": item["title"],
            "level": item["level"],
            "children": [],
            "source_type": "profile_expansion",
            "scoring_purpose": "参考历史案例章节功能，当前项目需按招标文件重新映射",
            "expected_depth": "medium",
            "tables_required": [],
            "image_slots": [],
            "enterprise_required": False,
            "asset_required": False,
        }
        for index, item in enumerate(headings[:10], 1)
    ]
    profile["chapter_blueprints"] = [
        {
            "chapter_title": item["title"],
            "applies_when": ["当前招标文件存在同类技术/服务方案要求时使用"],
            "writing_function": "响应招标要求",
            "recommended_structure": ["目标与依据", "实施措施", "质量/进度/风险控制", "成果与承诺"],
            "paragraph_blueprint": [
                {
                    "purpose": "说明本节如何响应当前招标文件要求",
                    "opening_pattern": "围绕{{项目名称}}和{{服务范围}}，说明我公司的响应目标和实施原则。",
                    "content_slots": ["{{招标要求}}", "{{评分项}}", "{{企业资料或占位}}"],
                    "closing_rule": "缺失事实使用占位符，不继承历史案例具体值。",
                }
            ],
            "tender_fact_slots": ["项目名称", "服务范围", "服务期限", "质量要求", "评分标准"],
            "enterprise_fact_slots": ["企业资质", "人员配置", "同类业绩", "证书/附件"],
            "tables_to_insert": [],
            "assets_to_insert": [],
            "do_not_copy": ["历史项目名称", "历史投标人", "历史人员", "历史业绩", "历史日期", "历史金额"],
        }
        for item in headings[:6]
    ]
    profile["quality_risks"] = [
        {
            "risk": "规则兜底模板未经过模型深度反向建模",
            "location": str(selected.get("project_title") or ""),
            "fix_rule": "生成目录和正文时只参考章节结构，必须以当前招标文件解析结果为最高依据。",
        }
    ]
    if failure_reason:
        profile["quality_risks"].append({
            "risk": "模型样例剖面生成失败",
            "location": "history-case-match",
            "fix_rule": failure_reason[:300],
        })
    return profile


async def _select_reference_candidate_with_llm(
    tender_text: str,
    analysis_report: Dict[str, Any],
    candidates: list[dict],
) -> tuple[str, str]:
    candidate_pack = [
        {
            "project_id": item.get("project_id"),
            "rank": item.get("rank"),
            "score": item.get("score"),
            "project_title": item.get("project_title"),
            "year": item.get("year"),
            "batch": item.get("batch"),
            "result": item.get("result"),
            "subject": item.get("subject"),
            "primary_domain": item.get("primary_domain"),
            "primary_subdomain": item.get("primary_subdomain"),
            "file_name": item.get("best_file_name"),
            "document_category": item.get("best_document_category"),
            "pageindex_node_id": item.get("best_pageindex_node_id"),
            "node_title": item.get("best_node_title"),
            "node_path": item.get("best_node_path"),
            "snippet": item.get("snippet"),
            "match_reasons": item.get("match_reasons", []),
        }
        for item in candidates
    ]
    system_prompt = """你是标书历史案例匹配专家。请从候选历史标书中选择最适合作为当前招标文件成熟样例的一个案例。
判断优先级：
1. 行业/领域最接近；
2. 项目对象最接近，例如油库、加油站、LNG、管道、化工装置、电力新能源等；
3. 服务类型最接近，例如设计、勘察、可研、初设、消防专篇、框架服务；
4. 优先选择中标案例，但不要为了中标牺牲领域匹配；
5. 如果当前项目是油库/加油站/销售公司工程设计服务，不要选择只有油管、管道、管线迁改对象的案例，除非候选同时覆盖油库/加油站；
6. 只从候选中选择，禁止编造。

只返回 JSON：{"selected_project_id":"...","reason":"...","confidence":0.0}"""
    user_prompt = f"""当前招标文件摘要：
{tender_text[:5000]}

结构化解析报告：
{json.dumps(analysis_report or {}, ensure_ascii=False)[:5000]}

候选历史案例：
{json.dumps(candidate_pack, ensure_ascii=False, indent=2)}
"""
    service = OpenAIService()
    chunks = []
    async for chunk in service.stream_chat_completion(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1,
        response_format={"type": "json_object"},
        max_tokens=800,
    ):
        chunks.append(chunk)
    payload = json.loads(extract_json_string("".join(chunks)))
    selected_id = str(payload.get("selected_project_id") or "")
    if not selected_id:
        raise ValueError("模型未返回 selected_project_id")
    if not any(item.get("project_id") == selected_id for item in candidates):
        raise ValueError("模型选择的项目不在候选列表中")
    return selected_id, str(payload.get("reason") or "")


async def _judge_requirement_checks_with_llm(checks: list[dict]) -> tuple[list[dict], str]:
    config = config_manager.load_config()
    auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
    if auth_error:
        return [], auth_error

    compact_checks = []
    for check in checks[:60]:
        compact_checks.append({
            "item_id": check.get("item_id"),
            "category": check.get("category_label"),
            "label": check.get("label"),
            "score": check.get("score"),
            "requirement": str(check.get("requirement") or "")[:500],
            "rule_satisfied": check.get("satisfied"),
            "evidence": [
                {
                    "project_title": item.get("project_title"),
                    "result": item.get("result"),
                    "file_name": item.get("file_name"),
                    "document_category": item.get("document_category"),
                    "pageindex_node_id": item.get("pageindex_node_id"),
                    "node_title": item.get("node_title"),
                    "node_path": item.get("node_path"),
                    "snippet": str(item.get("snippet") or "")[:300],
                }
                for item in (check.get("evidence") or [])[:3]
            ],
        })

    system_prompt = """你是标书资质和评分项核验专家。请基于历史中标案例库检索证据，判断每个招标要求是否已有可复用的满足证据。
规则：
1. 只能根据 evidence 中的历史案例片段判断，禁止编造企业能力；
2. evidence 为空必须判定 satisfied=false；
3. 优先认可 result 含“中标”的案例；
4. 资质/业绩/人员/证书类要求需要证据片段与要求主题一致才可打勾；
5. 技术/商务评分项如果历史案例片段可支撑类似响应内容，可判定满足；
6. 返回 JSON，结构为 {"checks":[{"item_id":"...","satisfied":true,"confidence":0.0,"reason":"..."}],"reason":"..."}。"""
    user_prompt = f"""待核验要求项：
{json.dumps(compact_checks, ensure_ascii=False, indent=2)}
"""

    chunks = []
    async for chunk in OpenAIService().stream_chat_completion(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1,
        response_format={"type": "json_object"},
        max_tokens=3000,
    ):
        chunks.append(chunk)
    payload = json.loads(extract_json_string("".join(chunks)))
    judged = payload.get("checks")
    if not isinstance(judged, list):
        raise ValueError("模型未返回 checks 数组")
    return judged, str(payload.get("reason") or "")
