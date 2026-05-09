"""历史标书案例库 API。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..services.openai_service import OpenAIService
from ..services.history_case_service import HistoryCaseService
from ..utils.config_manager import config_manager
from ..utils.json_util import extract_json_string
from ..utils.provider_registry import get_provider_auth_error


router = APIRouter(prefix="/api/history-cases", tags=["历史标书案例库"])


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


@router.get("/summary")
async def get_history_case_summary():
    """返回历史标书案例库统计。"""
    return HistoryCaseService.summary()


@router.get("/projects")
async def list_history_case_projects(
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


@router.get("/domains")
async def list_history_case_domains():
    """列出历史项目领域分类统计。"""
    return {
        "success": True,
        "domains": HistoryCaseService.list_domains(),
    }


@router.post("/search")
async def search_history_cases(request: HistoryCaseSearchRequest):
    """全文检索历史标书内容，并返回来源文档和 PageIndex 树路径。"""
    return {
        "success": True,
        "results": HistoryCaseService.search(query=request.query, limit=request.limit),
    }


@router.post("/check-requirements")
async def check_history_case_requirements(request: RequirementCheckRequest):
    """用历史中标案例库核对标准解析中的评分项、资质项是否已有满足证据。"""
    result = HistoryCaseService.check_requirements(
        analysis_report=request.analysis_report,
        limit_per_item=request.limit_per_item,
    )
    llm_reason = ""
    if request.use_llm and result["checks"]:
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
                result["summary"]["satisfied"] = sum(1 for check in result["checks"] if check.get("satisfied"))
                result["summary"]["not_found"] = result["summary"]["total"] - result["summary"]["satisfied"]
        except Exception as exc:
            llm_reason = f"LLM 判定失败，已使用历史库检索规则结果：{str(exc)}"

    return {
        "success": True,
        "message": "历史案例库要求项校验完成",
        "summary": result["summary"],
        "checks": result["checks"],
        "llm_reason": llm_reason,
    }


@router.post("/match-reference")
async def match_reference_case(request: ReferenceMatchRequest):
    """根据当前招标文件自动匹配历史成熟案例，并生成可复用样例风格剖面。"""
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

    selected = candidates[0]
    llm_reason = ""
    if request.use_llm:
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            return {
                "success": False,
                "message": auth_error,
                "candidates": candidates,
            }
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

    markdown = HistoryCaseService.load_markdown(str(selected.get("markdown_path") or ""))
    if not markdown:
        return {
            "success": False,
            "message": "已匹配候选，但无法读取历史案例 Markdown 文本",
            "matched_case": selected,
            "candidates": candidates,
        }

    try:
        profile = await OpenAIService().generate_reference_bid_style_profile(markdown)
    except Exception as exc:
        return {
            "success": False,
            "message": f"已匹配历史案例，但生成成熟样例剖面失败：{str(exc)}",
            "matched_case": selected,
            "candidates": candidates,
            "llm_reason": llm_reason,
        }

    profile.setdefault("source_history_case", {
        "project_id": selected.get("project_id"),
        "project_title": selected.get("project_title"),
        "document_id": selected.get("best_document_id"),
        "file_name": selected.get("best_file_name"),
        "primary_domain": selected.get("primary_domain"),
        "pageindex_tree_path": selected.get("pageindex_tree_path"),
    })

    return {
        "success": True,
        "message": f"已自动匹配历史案例：{selected.get('project_title')}",
        "matched_case": selected,
        "candidates": candidates,
        "llm_reason": llm_reason,
        "reference_bid_style_profile": profile,
    }


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
