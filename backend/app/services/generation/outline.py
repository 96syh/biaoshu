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


class OutlineGenerationMixin:
    @staticmethod
    def _outline_title_related(title: str, *values: Any) -> bool:
        text = " ".join(str(value or "") for value in values)
        if title and (title in text or text in title):
            return True
        parts = re.split(r"[、，,；;。.\s（）()]+", str(title or ""))
        tokens = [
            part
            for part in parts
            if len(part) >= 2 and part not in {"服务", "方案", "内容", "措施", "要求", "响应", "章节"}
        ]
        return any(token in text for token in tokens)

    @staticmethod
    def _build_secondary_seed_node(
        parent_id: str,
        index: int,
        title: str,
        description: str,
        *,
        volume_id: str,
        chapter_type: str,
        source_type: str,
        expected_blocks: list[str] | None = None,
        scoring_item_ids: list[str] | None = None,
        requirement_ids: list[str] | None = None,
        risk_ids: list[str] | None = None,
        material_ids: list[str] | None = None,
        response_matrix_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """构造二级标题种子节点，供模型在此基础上补全。"""
        blocks = expected_blocks or ["paragraph"]
        return {
            "id": f"{parent_id}.{index}",
            "title": title,
            "description": description,
            "volume_id": volume_id,
            "chapter_type": chapter_type,
            "source_type": source_type,
            "fixed_format_sensitive": False,
            "price_sensitive": False,
            "anonymity_sensitive": False,
            "expected_word_count": 800,
            "expected_depth": "medium",
            "expected_blocks": blocks,
            "enterprise_required": bool(material_ids),
            "asset_required": any(block in {"image", "org_chart", "workflow_chart"} for block in blocks),
            "scoring_item_ids": scoring_item_ids or [],
            "requirement_ids": requirement_ids or [],
            "risk_ids": risk_ids or [],
            "material_ids": material_ids or [],
            "response_matrix_ids": response_matrix_ids or [],
            "children": [],
        }

    @staticmethod
    def _extract_split_secondary_titles(title: str) -> list[str]:
        """从一级标题中抽取可直接拆分的并列元素，并转换为专业二级标题。"""
        clean_title = FallbackGenerationMixin._clean_outline_requirement_title(title)
        if not clean_title:
            return []

        special_cases: list[tuple[str, list[str]]] = [
            (r"服务范围.*服务内容|服务内容.*服务范围", ["服务范围", "服务内容"]),
            (r"服务机构设置.*岗位职责|岗位职责.*服务机构设置|机构设置.*岗位职责", ["项目管理机构图", "岗位职责、工作范围及其相互关系"]),
            (r"质量承诺.*措施|措施.*质量承诺", ["质量承诺", "质量控制与保障措施"]),
            (r"沟通技巧.*方法|沟通.*方法|方法.*沟通", ["沟通协调机制", "沟通方法与响应方式"]),
        ]
        for pattern, titles in special_cases:
            if re.search(pattern, clean_title):
                return titles

        if not re.search(r"及其|以及|及|和|与|或|包括|、|，|,|（|）|\(|\)", clean_title):
            return []

        normalized = clean_title.replace("（", "(").replace("）", ")")
        normalized = re.sub(r"\(([^)]*)\)", lambda match: f"{match.group(1)}" if match.group(1).strip() else "", normalized)
        for marker in ("以及", "及其", "包括", "及", "和", "与", "或"):
            normalized = normalized.replace(marker, "|")
        normalized = re.sub(r"[、，,]+", "|", normalized)
        segments = [
            FallbackGenerationMixin._clean_outline_requirement_title(part)
            for part in normalized.split("|")
            if FallbackGenerationMixin._clean_outline_requirement_title(part)
        ]
        if len(segments) < 2:
            return []

        result: list[str] = []
        for segment in segments:
            candidate = segment.strip()
            if re.search(r"框图|组织架构|组织机构|机构设置", candidate):
                candidate = "项目管理机构图"
            elif re.search(r"岗位职责|工作范围|相互关系", candidate):
                candidate = "岗位职责、工作范围及其相互关系" if any(
                    keyword in clean_title for keyword in ("工作范围", "相互关系")
                ) else "岗位职责与协同关系"
            elif re.search(r"服务范围|范围", candidate) and "服务范围" in clean_title:
                candidate = "服务范围"
            elif re.search(r"服务内容|工作内容|内容", candidate) and "服务内容" in clean_title:
                candidate = "服务内容"
            elif re.search(r"质量承诺", candidate):
                candidate = "质量承诺"
            elif candidate in {"措施", "保障措施"} and "质量" in clean_title:
                candidate = "质量控制与保障措施"
            elif candidate in {"方法", "技巧"} and "沟通" in clean_title:
                candidate = "沟通方法与响应方式"
            elif "沟通" in candidate and not re.search(r"方法|技巧|响应", candidate):
                candidate = "沟通协调机制"

            if candidate and candidate not in result:
                result.append(candidate)
        return result if len(result) >= 2 else []

    @staticmethod
    def _seed_secondary_children_from_title(level1_node: Dict[str, Any]) -> list[dict[str, Any]]:
        """优先按照一级标题中的并列元素生成二级标题种子。"""
        title = level1_node.get("title") or level1_node.get("new_title") or level1_node.get("rating_item") or ""
        split_titles = OutlineGenerationMixin._extract_split_secondary_titles(title)
        if not split_titles:
            return []

        parent_id = str(level1_node.get("id") or "1")
        volume_id = str(level1_node.get("volume_id") or "V-TECH")
        chapter_type = str(level1_node.get("chapter_type") or "technical")
        children: list[dict[str, Any]] = []
        for index, child_title in enumerate(split_titles, start=1):
            blocks = ["paragraph"]
            if re.search(r"机构图|组织架构", child_title):
                blocks = ["org_chart"]
            elif re.search(r"流程", child_title):
                blocks = ["workflow_chart"]
            elif re.search(r"人员|岗位|职责", child_title):
                blocks = ["table"]
            children.append(OutlineGenerationMixin._build_secondary_seed_node(
                parent_id,
                index,
                child_title,
                "根据一级标题中的并列要素拆分得到，应优先围绕该要素展开写作。",
                volume_id=volume_id,
                chapter_type=chapter_type,
                source_type="tender_direct_response",
                expected_blocks=blocks,
            ))
        return children

    @staticmethod
    def _seed_secondary_children_from_scoring(
        level1_node: Dict[str, Any],
        analysis_report: Dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """当一级标题无法直接拆分时，优先按评分项提炼二级标题种子。"""
        report = analysis_report or {}
        title = FallbackGenerationMixin._clean_outline_requirement_title(
            level1_node.get("title") or level1_node.get("new_title") or level1_node.get("rating_item") or ""
        )
        if not title:
            return []

        score_items = []
        score_items.extend(report.get("technical_scoring_items") or [])
        score_items.extend(report.get("business_scoring_items") or [])
        score_items.extend(report.get("price_scoring_items") or [])

        title_is_personnel = bool(re.search(r"人员|团队|项目负责人|岗位|机构", title))
        title_is_goal = bool(re.search(r"目标", title))
        title_is_generic_plan = bool(re.search(r"实施|方案|服务", title)) and not bool(
            re.search(r"范围|内容|人员|机构|岗位|职责|沟通|质量|进度|目标", title)
        )

        relevant_items: list[dict[str, Any]] = []
        for item in score_items:
            score_text = " ".join(
                str(item.get(key) or "")
                for key in ("name", "standard", "writing_focus", "source", "logic", "risk")
            )
            if OutlineGenerationMixin._outline_title_related(title, score_text):
                relevant_items.append(item)
                continue
            if title_is_personnel and re.search(r"项目负责人|项目组|团队|人员|注册|职称|资格|证书|业绩|经验", score_text):
                relevant_items.append(item)
                continue
            if title_is_goal and re.search(r"目标|质量|进度|响应|交付|成果|服务标准|时限", score_text):
                relevant_items.append(item)
                continue
            if title_is_generic_plan and re.search(r"流程|进度|节点|质量|风险|应急|资源|组织|协同|重点|难点|实施", score_text):
                relevant_items.append(item)

        if not relevant_items:
            return []

        parent_id = str(level1_node.get("id") or "1")
        volume_id = str(level1_node.get("volume_id") or "V-TECH")
        chapter_type = str(level1_node.get("chapter_type") or "technical")
        children: list[dict[str, Any]] = []

        if title_is_personnel:
            specs = [
                ("项目负责人", r"项目负责人|设计负责人|负责人|项目经理", ["table"]),
                ("项目组成人员详情", r"项目组|项目组成人员|团队|专业人员|服务人员|人员配置", ["table"]),
                ("人员资格与证书配置", r"注册|职称|资格|证书", ["table"]),
                ("人员业绩与项目经验", r"业绩|经验|类似项目", ["table"]),
            ]
        elif title_is_goal:
            specs = [
                ("总体目标", r"总体|整体|服务目标|总目标|目标", ["paragraph"]),
                ("质量目标", r"质量|质控|质保|验收|检查|复核", ["table"]),
                ("进度目标", r"进度|节点|时限|周期|工期|安排", ["table"]),
                ("成果与响应目标", r"交付|成果|响应|服务标准|时限", ["paragraph"]),
            ]
        else:
            specs = [
                ("总体实施思路", r"总体|整体|思路|方案|理解|重点|难点", ["paragraph"]),
                ("服务实施流程", r"流程|步骤|程序|实施流程|工作流程|服务流程", ["workflow_chart"]),
                ("阶段任务与进度安排", r"进度|节点|时限|周期|工期|安排", ["table"]),
                ("资源配置与协同机制", r"资源|配置|协同|组织|投入|配合|衔接", ["table"]),
                ("质量控制与保障措施", r"质量|质控|质保|验收|检查|复核", ["table"]),
                ("风险应对与应急处理", r"风险|应急|预案|处置|控制", ["paragraph"]),
            ]

        def matched_ids(pattern: str) -> list[str]:
            return [
                item.get("id")
                for item in relevant_items
                if item.get("id") and re.search(
                    pattern,
                    " ".join(
                        str(item.get(key) or "")
                        for key in ("name", "standard", "writing_focus", "source", "logic", "risk")
                    ),
                )
            ]

        for child_title, pattern, blocks in specs:
            score_ids = list(dict.fromkeys(matched_ids(pattern)))
            allow_generic_plan_support = title_is_generic_plan and child_title in {"总体实施思路", "资源配置与协同机制"}
            allow_goal_support = title_is_goal and child_title == "总体目标"
            if not score_ids and not allow_generic_plan_support and not allow_goal_support:
                continue
            children.append(OutlineGenerationMixin._build_secondary_seed_node(
                parent_id,
                len(children) + 1,
                child_title,
                "根据评分项中的明确得分对象和关键关注点提炼，应优先覆盖对应评分要求。",
                volume_id=volume_id,
                chapter_type=chapter_type,
                source_type="scoring_response",
                expected_blocks=blocks,
                scoring_item_ids=score_ids,
            ))

        if title_is_personnel and len(children) >= 2:
            core_titles = {"项目负责人", "项目组成人员详情"}
            core_children = [child for child in children if child.get("title") in core_titles]
            return core_children or children[:2]
        return children

    @staticmethod
    def _seed_secondary_outline_children(
        level1_node: Dict[str, Any],
        analysis_report: Dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """二级标题种子优先级：一级标题可拆分元素 > 评分项。"""
        split_children = OutlineGenerationMixin._seed_secondary_children_from_title(level1_node)
        if split_children:
            return split_children
        return OutlineGenerationMixin._seed_secondary_children_from_scoring(level1_node, analysis_report)

    @staticmethod
    def _merge_secondary_seed_children(
        generated_node: Dict[str, Any],
        secondary_seeds: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        """用确定性的二级标题种子覆盖模型标题，保留模型补充的描述和映射。"""
        if not secondary_seeds:
            return generated_node

        node = dict(generated_node or {})
        generated_children = list(node.get("children") or [])
        merged_children: list[dict[str, Any]] = []

        for index, seed in enumerate(secondary_seeds):
            generated_child = dict(generated_children[index]) if index < len(generated_children) else {}
            merged_child = {
                **seed,
                **generated_child,
                "id": seed.get("id") or generated_child.get("id"),
                "title": seed.get("title") or generated_child.get("title"),
                "description": generated_child.get("description") or seed.get("description") or "",
                "volume_id": seed.get("volume_id") or generated_child.get("volume_id") or node.get("volume_id", ""),
                "chapter_type": seed.get("chapter_type") or generated_child.get("chapter_type") or node.get("chapter_type", ""),
                "source_type": seed.get("source_type") or generated_child.get("source_type") or "scoring_response",
                "expected_blocks": generated_child.get("expected_blocks") or seed.get("expected_blocks") or ["paragraph"],
                "children": [],
            }
            for list_key in ("scoring_item_ids", "requirement_ids", "risk_ids", "material_ids", "response_matrix_ids"):
                seed_values = list(seed.get(list_key) or [])
                generated_values = list(generated_child.get(list_key) or [])
                merged_child[list_key] = list(dict.fromkeys(seed_values + generated_values))
            merged_children.append(merged_child)

        node["children"] = merged_children
        return node

    @staticmethod
    def _strip_outline_below_second_level(level1_node: Dict[str, Any]) -> Dict[str, Any]:
        """只保留一级节点及其二级子节点，裁掉更深层级目录。"""
        node = dict(level1_node or {})
        cleaned_children: list[dict[str, Any]] = []
        for child in (node.get("children") or []):
            child_node = dict(child or {})
            child_node["children"] = []
            cleaned_children.append(child_node)
        node["children"] = cleaned_children
        return node

    @classmethod
    def _normalize_outline_node(
        cls,
        node: Any,
        fallback_id: str,
        fallback_title: str,
        bid_mode: str | None = None,
    ) -> Dict[str, Any]:
        """补齐模型常漏的目录节点元数据，保持后续正文/审校合同稳定。"""
        if not isinstance(node, dict):
            node = {}
        normalized = dict(node)
        title = str(
            normalized.get("title")
            or normalized.get("new_title")
            or normalized.get("rating_item")
            or fallback_title
            or fallback_id
        )
        normalized["id"] = str(normalized.get("id") or fallback_id)
        normalized["title"] = title
        normalized.setdefault("description", "按招标文件要求编写。")
        normalized.setdefault("volume_id", "V-TECH")
        normalized.setdefault("chapter_type", "service_plan" if bid_mode in {"technical_service_plan", "service_plan"} else "technical")
        normalized.setdefault("source_type", "tender_direct_response")
        normalized.setdefault("fixed_format_sensitive", False)
        normalized.setdefault("price_sensitive", False)
        normalized.setdefault("anonymity_sensitive", False)
        normalized.setdefault("expected_word_count", 1200)
        normalized.setdefault("expected_depth", "medium")
        normalized.setdefault("expected_blocks", ["paragraph"])
        normalized.setdefault("enterprise_required", False)
        normalized.setdefault("asset_required", False)
        for key in ("scoring_item_ids", "requirement_ids", "risk_ids", "material_ids", "response_matrix_ids"):
            value = normalized.get(key)
            normalized[key] = value if isinstance(value, list) else []

        children = normalized.get("children")
        if isinstance(children, list) and children:
            normalized["children"] = [
                cls._normalize_outline_node(
                    child,
                    f"{normalized['id']}.{index}",
                    f"{title}-{index}",
                    bid_mode,
                )
                for index, child in enumerate(children, start=1)
            ]
        else:
            normalized["children"] = []
        return normalized

    @classmethod
    def _coerce_level1_outline_payload(cls, payload: Any) -> list[dict[str, Any]]:
        """适配目录一级输出：压缩包提示词允许顶层对象或数组。"""
        candidate = payload
        if isinstance(candidate, dict):
            for key in ("outline", "level1_outline", "chapters", "nodes", "items", "data", "result", "children"):
                nested = candidate.get(key)
                if isinstance(nested, (list, dict)):
                    candidate = nested
                    break

        if isinstance(candidate, dict):
            candidate = [candidate] if (candidate.get("title") or candidate.get("children")) else []

        if not isinstance(candidate, list):
            return []

        return [item for item in candidate if isinstance(item, dict)]

    @classmethod
    def _coerce_level23_outline_payload(
        cls,
        payload: Any,
        base_node: Dict[str, Any],
        bid_mode: str | None = None,
    ) -> Dict[str, Any]:
        """把模型返回的完整节点、children 包裹对象或数组适配为当前一级节点。"""
        candidate = payload
        if isinstance(candidate, dict):
            for key in ("current_level1_node", "level1_node", "node", "chapter", "outline", "data", "result"):
                nested = candidate.get(key)
                if isinstance(nested, (dict, list)):
                    candidate = nested
                    break

        if isinstance(candidate, list):
            generated_children = candidate
            candidate_node: Dict[str, Any] = {}
        elif isinstance(candidate, dict):
            candidate_node = dict(candidate)
            generated_children = candidate_node.get("children")
            if not isinstance(generated_children, list):
                for key in ("subsections", "sections", "nodes", "items", "chapters", "outline"):
                    nested = candidate_node.get(key)
                    if isinstance(nested, list):
                        generated_children = nested
                        break
        else:
            raise ValueError("模型返回的二级目录不是 JSON 对象或数组")

        if not isinstance(generated_children, list):
            generated_children = []

        coerced_children: list[dict[str, Any]] = []
        for index, child in enumerate(generated_children, start=1):
            if isinstance(child, dict):
                child_node = dict(child)
            elif str(child or "").strip():
                child_node = {"title": str(child).strip()}
            else:
                continue
            child_node["children"] = []
            coerced_children.append(child_node)

        merged = {
            **dict(base_node or {}),
            **candidate_node,
            "id": str((base_node or {}).get("id") or candidate_node.get("id") or ""),
            "title": str((base_node or {}).get("title") or candidate_node.get("title") or ""),
            "volume_id": (base_node or {}).get("volume_id", candidate_node.get("volume_id", "")),
            "chapter_type": (base_node or {}).get("chapter_type", candidate_node.get("chapter_type", "")),
            "children": coerced_children,
        }
        return cls._normalize_outline_node(
            merged,
            str((base_node or {}).get("id") or ""),
            str((base_node or {}).get("title") or ""),
            bid_mode,
        )

    async def generate_outline_v2(
        self,
        overview: str,
        requirements: str,
        file_content: str | None = None,
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """生成目录。模型优先；只有显式打开兜底开关时才允许通用兜底目录。"""
        report = dict(analysis_report or {})
        if report and not self._force_local_fallback() and self._analysis_report_has_blocking_generation_warning(report):
            raise Exception(
                "当前标准解析报告来自旧兜底或未完整模型输出，目录生成已停止。"
                "请先重新执行标准解析，得到完整结构化解析报告后再生成目录。"
            )
        if file_content and len(self._collect_scheme_outline_items(report)) < 2:
            fallback_bid_doc = self._extract_bid_document_requirements(file_content, allow_generic_defaults=False)
            fallback_report = {"bid_document_requirements": fallback_bid_doc}
            fallback_items = self._collect_scheme_outline_items(fallback_report)
            if len(fallback_items) >= 2:
                bid_doc = dict(report.get("bid_document_requirements") or {})
                bid_doc["scheme_or_technical_outline_requirements"] = fallback_bid_doc.get("scheme_or_technical_outline_requirements") or []
                selected_target = dict(bid_doc.get("selected_generation_target") or {})
                fallback_target = fallback_bid_doc.get("selected_generation_target") or {}
                selected_target.setdefault("target_id", fallback_target.get("target_id", ""))
                selected_target.setdefault("target_title", fallback_target.get("target_title", ""))
                selected_target.setdefault("parent_composition_id", fallback_target.get("parent_composition_id", ""))
                selected_target.setdefault("target_source", fallback_target.get("target_source", ""))
                selected_target.setdefault("target_source_type", fallback_target.get("target_source_type", "composition_item"))
                selected_target["generation_scope"] = selected_target.get("generation_scope") or fallback_target.get("generation_scope", "scheme_section_only")
                selected_target["use_as_outline_basis"] = True
                selected_target["base_outline_strategy"] = "scheme_outline"
                selected_target["base_outline_items"] = fallback_target.get("base_outline_items") or fallback_items
                selected_target["confidence"] = "high"
                bid_doc["selected_generation_target"] = selected_target
                if not bid_doc.get("composition"):
                    bid_doc["composition"] = fallback_bid_doc.get("composition") or []
                report["bid_document_requirements"] = bid_doc
        style_profile = reference_bid_style_profile or report.get("reference_bid_style_profile") or {}
        blocks_plan = document_blocks_plan or report.get("document_blocks_plan") or {}
        effective_bid_mode = bid_mode or report.get("bid_mode_recommendation") or "technical_only"

        if self._force_local_fallback():
            fallback = self._fallback_outline(report, effective_bid_mode)
            fallback.setdefault("document_blocks_plan", blocks_plan or {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []})
            fallback.setdefault("reference_bid_style_profile", style_profile)
            return fallback

        schema_json = json.dumps([
            {
                "id": "1",
                "volume_id": "V-TECH",
                "title": "正式一级目录标题",
                "chapter_type": "technical/business/qualification/price/form/material/review/service_plan/supply/construction",
                "source_type": "tender_direct_response/scoring_response/profile_expansion/enterprise_showcase/fixed_form/material_attachment",
                "description": "本章响应什么要求、覆盖哪些评分/审查/材料/风险，需要什么表格/承诺/图片",
                "fixed_format_sensitive": False,
                "price_sensitive": False,
                "anonymity_sensitive": False,
                "enterprise_required": False,
                "asset_required": False,
                "expected_depth": "medium",
                "expected_word_count": 1200,
                "expected_blocks": ["paragraph"],
                "scoring_item_ids": [],
                "requirement_ids": [],
                "risk_ids": [],
                "material_ids": [],
                "response_matrix_ids": [],
                "children": [],
            }
        ], ensure_ascii=False)
        system_prompt, user_prompt = prompt_manager.generate_level1_outline_prompt(
            overview=overview,
            requirements=requirements,
            analysis_report=report,
            bid_mode=effective_bid_mode,
            schema_json=schema_json,
            reference_bid_style_profile=style_profile,
            document_blocks_plan=blocks_plan,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            full_content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema={},
                    max_retries=0,
                    temperature=0.22,
                    response_format={"type": "json_object"},
                    log_prefix="一级提纲",
                    raise_on_fail=False,
                ),
                timeout=120,
            )
        except Exception as e:
            if not self._generation_fallbacks_enabled():
                raise self._fallback_disabled_error("一级提纲生成", str(e)) from e
            print(f"一级提纲模型输出不可用，启用通用兜底目录：{str(e)}")
            fallback = self._fallback_outline(report, effective_bid_mode)
            fallback.setdefault("document_blocks_plan", blocks_plan or {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []})
            fallback.setdefault("reference_bid_style_profile", style_profile)
            return fallback

        if not str(full_content or "").strip():
            raise self._fallback_disabled_error("一级提纲生成", "模型没有返回目录 JSON")
        try:
            parsed = self._loads_json_loose(full_content)
        except json.JSONDecodeError as e:
            raise self._fallback_disabled_error("一级提纲生成", f"模型返回的一级目录不是合法 JSON：{str(e)}") from e
        level_l1 = self._coerce_level1_outline_payload(parsed)
        if not isinstance(level_l1, list) or not level_l1:
            if not self._generation_fallbacks_enabled():
                raise self._fallback_disabled_error("一级提纲生成", "模型返回的 outline 为空或格式不正确")
            fallback = self._fallback_outline(report, effective_bid_mode)
            fallback.setdefault("document_blocks_plan", blocks_plan or {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []})
            fallback.setdefault("reference_bid_style_profile", style_profile)
            return fallback
        level_l1 = [
            self._normalize_outline_node(
                node,
                str(index),
                f"第{index}章",
                effective_bid_mode,
            )
            for index, node in enumerate(level_l1, start=1)
        ]

        # 技术/服务分册下，“服务方案/设计方案”只是生成对象；如果解析到了
        # “应包括”的子项，必须把这些子项作为一级目录，避免模型只返回包装标题。
        if effective_bid_mode != "full_bid":
            scheme_nodes = self._build_scheme_outline_nodes(report, report.get("response_matrix"))
            if len(scheme_nodes) >= 2:
                level_l1 = scheme_nodes
                if progress_callback:
                    await progress_callback({
                        "stage": "outline_guard",
                        "message": "已按招标文件服务纲要子项重建一级目录",
                        "outline": level_l1,
                    })

        nodes_distribution = self._build_nodes_distribution(level_l1, report, effective_bid_mode)
        outline_concurrency = max(1, self._int_env("YIBIAO_OUTLINE_CONCURRENCY", 2))
        semaphore = asyncio.Semaphore(outline_concurrency)

        async def process_with_limit(i: int, level1_node: Dict[str, Any]):
            async with semaphore:
                return await self.process_level1_node(
                    i,
                    level1_node,
                    nodes_distribution,
                    level_l1,
                    overview,
                    requirements,
                    analysis_report=report,
                    bid_mode=effective_bid_mode,
                    response_matrix=report.get("response_matrix"),
                    reference_bid_style_profile=style_profile,
                    document_blocks_plan=blocks_plan,
                )

        outline = await asyncio.gather(*[
            process_with_limit(i, level1_node)
            for i, level1_node in enumerate(level_l1)
        ])

        if not blocks_plan and self._bool_env("YIBIAO_AUTO_DOCUMENT_BLOCKS_PLAN", False):
            try:
                blocks_plan = await self.generate_document_blocks_plan(
                    outline=outline,
                    analysis_report=report,
                    response_matrix=report.get("response_matrix"),
                    reference_bid_style_profile=style_profile,
                )
            except Exception as e:
                print(f"目录生成已完成，但图表素材规划失败，先返回空规划：{self._compact_text(str(e), 180)}")
                blocks_plan = {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []}
        elif not blocks_plan:
            blocks_plan = {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []}
        return {
            "outline": outline,
            "response_matrix": report.get("response_matrix"),
            "coverage_summary": (report.get("response_matrix") or {}).get("coverage_summary", ""),
            "reference_bid_style_profile": style_profile,
            "document_blocks_plan": blocks_plan,
        }

    async def process_level1_node(
        self,
        i,
        level1_node,
        nodes_distribution,
        level_l1,
        overview,
        requirements,
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        response_matrix: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ):
        """处理单个一级节点：优先保留成熟样例 children，缺失时再调用模型补全。"""
        title = level1_node.get("title") or level1_node.get("new_title") or level1_node.get("rating_item") or f"第{i + 1}章"
        if level1_node.get("children"):
            return self._strip_outline_below_second_level(
                self._normalize_outline_node(level1_node, str(i + 1), title, bid_mode)
            )

        json_outline = generate_one_outline_json_by_level1(title, i + 1, nodes_distribution)
        json_outline["volume_id"] = level1_node.get("volume_id", "")
        json_outline["chapter_type"] = level1_node.get("chapter_type", "")
        json_outline["source_type"] = level1_node.get("source_type", "")
        for key in ("scoring_item_ids", "requirement_ids", "risk_ids", "material_ids", "response_matrix_ids", "expected_blocks"):
            json_outline[key] = level1_node.get(key, [])
        for bool_key in ("fixed_format_sensitive", "price_sensitive", "anonymity_sensitive", "enterprise_required", "asset_required"):
            json_outline[bool_key] = bool(level1_node.get(bool_key, False))
        json_outline["expected_word_count"] = int(level1_node.get("expected_word_count") or 0)
        json_outline["expected_depth"] = level1_node.get("expected_depth", "medium")
        secondary_seeds = self._seed_secondary_outline_children(level1_node, analysis_report)
        if secondary_seeds:
            json_outline["children"] = secondary_seeds
        print(f"正在处理第{i+1}章: {title}")

        other_outline = "\n".join([
            f"{j+1}. {node.get('title') or node.get('new_title') or node.get('rating_item') or ''}"
            for j, node in enumerate(level_l1)
            if j != i
        ])
        system_prompt, user_prompt = prompt_manager.generate_level23_outline_prompt(
            current_outline_json=json_outline,
            other_outline=other_outline,
            overview=overview,
            requirements=requirements,
            analysis_report=analysis_report,
            bid_mode=bid_mode,
            response_matrix=response_matrix or (analysis_report or {}).get("response_matrix", {}),
            reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile", {}),
            document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan", {}),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema={},
            max_retries=0,
            temperature=0.25,
            response_format={"type": "json_object"},
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )
        if not str(full_content or "").strip():
            raise self._fallback_disabled_error(f"第{i+1}章二级目录生成", "模型没有返回章节目录 JSON")
        try:
            payload = self._loads_json_loose(full_content)
            generated_node = self._coerce_level23_outline_payload(payload, json_outline, bid_mode)
        except json.JSONDecodeError as e:
            raise self._fallback_disabled_error(f"第{i+1}章二级目录生成", f"模型返回的章节目录不是合法 JSON：{str(e)}") from e
        except ValueError as e:
            raise self._fallback_disabled_error(f"第{i+1}章二级目录生成", str(e)) from e
        if secondary_seeds:
            generated_node = self._merge_secondary_seed_children(generated_node, secondary_seeds)
        isok, error_msg = check_json(json.dumps(generated_node, ensure_ascii=False), json_outline)
        if not isok:
            raise self._fallback_disabled_error(f"第{i+1}章二级目录生成", f"模型目录适配后仍不符合 schema：{error_msg}")
        return self._strip_outline_below_second_level(
            self._normalize_outline_node(generated_node, str(i + 1), title, bid_mode)
        )
