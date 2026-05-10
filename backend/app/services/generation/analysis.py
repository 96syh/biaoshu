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
from ..generation_cache_service import GenerationCacheService
from .core import GenerationCoreMixin


class AnalysisGenerationMixin:
    @staticmethod
    def _analysis_report_has_blocking_generation_warning(report: Dict[str, Any] | None) -> bool:
        """识别旧版本生成的标准解析兜底报告，避免目录阶段继续消费。"""
        if not isinstance(report, dict):
            return False
        warning_texts = []
        for item in report.get("generation_warnings") or []:
            if isinstance(item, dict):
                warning_texts.append(f"{item.get('severity', '')} {item.get('warning', '')}")
            else:
                warning_texts.append(str(item))
        for item in report.get("rejection_risks") or []:
            if isinstance(item, dict) and item.get("source") == "系统解析状态":
                warning_texts.append(str(item.get("risk", "")))
        combined = "\n".join(warning_texts)
        return bool(re.search(r"兜底|未完整返回|模型输出未完整|解析失败|超时", combined))

    @classmethod
    def _normalize_analysis_report_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """归一化接近 AnalysisReport 但类型不严格的模型输出。

        Claude 和部分 OpenAI 兼容网关经常把 list 字段返回成按类别分组的 object，
        例如 qualification_requirements={"registration":"..."}。这里在 Pydantic
        校验前收敛为内部 schema，避免可修复输出触发整次标准解析失败。
        """
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)

        def as_record_list(value: Any, field: str, prefix: str) -> list[dict[str, Any]]:
            if value in (None, "", {}, []):
                return []
            if isinstance(value, dict):
                raw_items = []
                for key, item in value.items():
                    if item in (None, "", {}, []):
                        continue
                    if isinstance(item, dict):
                        record = dict(item)
                        record.setdefault("name", str(key))
                    else:
                        record = {"name": str(key), "requirement": cls._stringify_requirement(item, 500)}
                    raw_items.append(record)
            elif isinstance(value, list):
                raw_items = []
                for index, item in enumerate(value, start=1):
                    if item in (None, "", {}, []):
                        continue
                    if isinstance(item, dict):
                        raw_items.append(dict(item))
                    else:
                        raw_items.append({"name": f"{prefix}-{index:02d}", "requirement": cls._stringify_requirement(item, 500)})
            else:
                raw_items = [{"name": field, "requirement": cls._stringify_requirement(value, 500)}]

            result: list[dict[str, Any]] = []
            for index, item in enumerate(raw_items, start=1):
                record = dict(item)
                record["id"] = str(record.get("id") or f"{prefix}-{index:02d}")
                generic_text = cls._stringify_requirement(record, 500)

                if field in {"technical_scoring_items", "business_scoring_items"}:
                    record["name"] = str(record.get("name") or record.get("item") or record.get("title") or record.get("category") or f"评分项{index}")
                    record["score"] = str(record.get("score") or record.get("weight") or record.get("points") or "")
                    record["standard"] = cls._stringify_requirement(
                        record.get("standard") or record.get("requirement") or record.get("criterion") or record.get("logic") or record.get("details") or generic_text,
                        700,
                    )
                    record["source"] = str(record.get("source") or record.get("source_ref") or "模型解析的评分标准")
                    record["evidence_requirements"] = cls._ensure_string_list(record.get("evidence_requirements"))
                    record["easy_loss_points"] = cls._ensure_string_list(record.get("easy_loss_points"))
                elif field == "price_scoring_items":
                    record["name"] = str(record.get("name") or record.get("item") or record.get("title") or "报价评分")
                    record["score"] = str(record.get("score") or record.get("weight") or record.get("points") or "")
                    record["logic"] = cls._stringify_requirement(
                        record.get("logic") or record.get("standard") or record.get("requirement") or generic_text,
                        700,
                    )
                    record["source"] = str(record.get("source") or "模型解析的报价评分")
                    record["risk"] = str(record.get("risk") or "")
                elif field in {"qualification_requirements", "formal_response_requirements"}:
                    record["name"] = str(record.get("name") or record.get("title") or record.get("review_type") or record.get("category") or f"要求{index}")
                    record["requirement"] = cls._stringify_requirement(
                        record.get("requirement") or record.get("standard") or record.get("criterion") or record.get("details") or generic_text,
                        700,
                    )
                    record["source"] = str(record.get("source") or record.get("source_ref") or "模型解析的审查要求")
                    record["required_materials"] = cls._ensure_string_list(record.get("required_materials"))
                    if field == "formal_response_requirements":
                        record["fixed_format"] = bool(record.get("fixed_format", False))
                        record["signature_required"] = bool(record.get("signature_required", False))
                        record["attachment_required"] = bool(record.get("attachment_required", False))
                elif field in {"formal_review_items", "qualification_review_items", "responsiveness_review_items"}:
                    record["review_type"] = str(record.get("review_type") or record.get("name") or record.get("category") or "评审项")
                    record["requirement"] = cls._stringify_requirement(
                        record.get("requirement") or record.get("standard") or record.get("criterion") or record.get("details") or generic_text,
                        700,
                    )
                    record["criterion"] = str(record.get("criterion") or record.get("logic") or "")
                    record["required_materials"] = cls._ensure_string_list(record.get("required_materials"))
                    record["target_chapters"] = cls._ensure_string_list(record.get("target_chapters"))
                    record["source"] = str(record.get("source") or "模型解析的评审标准")
                    record["invalid_if_missing"] = bool(record.get("invalid_if_missing", False))
                elif field == "mandatory_clauses":
                    record["clause"] = cls._stringify_requirement(record.get("clause") or record.get("requirement") or generic_text, 700)
                    record["source"] = str(record.get("source") or "模型解析的实质性条款")
                    record["response_strategy"] = str(record.get("response_strategy") or "逐条响应并人工复核。")
                    record["invalid_if_not_responded"] = bool(record.get("invalid_if_not_responded", True))
                elif field == "rejection_risks":
                    record["risk"] = cls._stringify_requirement(record.get("risk") or record.get("requirement") or generic_text, 700)
                    record["trigger"] = str(record.get("trigger") or "")
                    record["source"] = str(record.get("source") or "模型解析的废标风险")
                    record["mitigation"] = str(record.get("mitigation") or "按招标文件要求逐项响应。")
                    record["blocking"] = bool(record.get("blocking", True))
                elif field == "required_materials":
                    record["name"] = str(record.get("name") or record.get("title") or f"证明材料{index}")
                    record["purpose"] = str(record.get("purpose") or record.get("requirement") or record.get("name") or "")
                    record["source"] = str(record.get("source") or "模型解析的材料要求")
                    record["status"] = str(record.get("status") or "missing")
                    record["used_by"] = cls._ensure_string_list(record.get("used_by"))
                    record["volume_id"] = str(record.get("volume_id") or "")
                else:
                    record.setdefault("source", record.get("source_ref") or "模型解析")
                result.append(record)
            return result

        list_field_prefixes = {
            "source_refs": "SRC",
            "volume_rules": "V",
            "bid_structure": "S",
            "formal_review_items": "E",
            "qualification_review_items": "QREV",
            "responsiveness_review_items": "RESP",
            "business_scoring_items": "B",
            "technical_scoring_items": "T",
            "price_scoring_items": "P",
            "qualification_requirements": "Q",
            "formal_response_requirements": "F",
            "mandatory_clauses": "C",
            "rejection_risks": "R",
            "fixed_format_forms": "FF",
            "signature_requirements": "SIG",
            "evidence_chain_requirements": "EV",
            "required_materials": "M",
            "missing_company_materials": "X",
            "generation_warnings": "W",
        }
        for field, prefix in list_field_prefixes.items():
            if field in normalized:
                normalized[field] = as_record_list(normalized.get(field), field, prefix)

        price_rules = normalized.get("price_rules")
        if isinstance(price_rules, list):
            normalized["price_rules"] = price_rules[0] if price_rules and isinstance(price_rules[0], dict) else {}
        elif not isinstance(price_rules, dict):
            normalized["price_rules"] = {"quote_method": cls._stringify_requirement(price_rules, 500)} if price_rules else {}

        if not isinstance(normalized.get("project"), dict):
            normalized["project"] = {"name": cls._stringify_requirement(normalized.get("project"), 200)}

        if not normalized.get("source_refs"):
            normalized["source_refs"] = [{
                "id": "SRC-01",
                "location": "模型解析的招标文件",
                "excerpt": cls._stringify_requirement(normalized.get("project", {}).get("name"), 160),
                "related_ids": [],
            }]
        else:
            for index, source in enumerate(normalized["source_refs"], start=1):
                source["id"] = str(source.get("id") or f"SRC-{index:02d}")
                source["location"] = str(source.get("location") or source.get("name") or "模型解析的招标文件")
                source["excerpt"] = cls._stringify_requirement(source.get("excerpt") or source.get("requirement") or source, 300)
                source["related_ids"] = cls._ensure_string_list(source.get("related_ids"))

        enterprise_profile = normalized.get("enterprise_material_profile")
        if not isinstance(enterprise_profile, dict):
            normalized["enterprise_material_profile"] = {}

        return normalized

    @staticmethod
    def _ensure_string_list(value: Any) -> list[str]:
        if value in (None, "", {}, []):
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "", {}, [])]
        if isinstance(value, dict):
            return [f"{key}: {GenerationCoreMixin._stringify_requirement(item, 120)}" for key, item in value.items() if item not in (None, "", {}, [])]
        return [str(value)]

    @classmethod
    def _analysis_report_quality_issues(cls, report: Dict[str, Any] | None, source_text: str) -> list[str]:
        """检查模型返回的是不是“合法但空”的 AnalysisReport。

        这是模型无关门禁：Claude/GPT/DeepSeek 都可以输出 JSON，但只要招标原文里
        明确存在项目、资格、评分、投标文件组成等内容，报告就必须抽出来。
        """
        if not isinstance(report, dict):
            return ["模型输出不是 JSON 对象"]

        source = str(source_text or "")
        issues: list[str] = []
        project = report.get("project") if isinstance(report.get("project"), dict) else {}
        project_values = " ".join(str(project.get(key) or "") for key in ("name", "number", "purchaser", "service_scope"))
        if not project_values.strip() and re.search(r"项目|工程|采购|招标编号|招标人|采购人", source):
            issues.append("项目基础信息为空")

        scoring_count = sum(
            len(report.get(key) or [])
            for key in ("technical_scoring_items", "business_scoring_items", "price_scoring_items")
            if isinstance(report.get(key), list)
        )
        if scoring_count == 0 and re.search(r"评分标准|详细评审|评审项目|分值|得分|评标办法前附表", source):
            issues.append("原文存在评分办法但评分项为空")

        qualification_count = sum(
            len(report.get(key) or [])
            for key in ("qualification_requirements", "qualification_review_items")
            if isinstance(report.get(key), list)
        )
        if qualification_count == 0 and re.search(r"投标人资格要求|资格要求|资质要求|业绩要求|信誉要求|资格评审", source):
            issues.append("原文存在资格/资质要求但资格项为空")

        bid_doc = report.get("bid_document_requirements") if isinstance(report.get("bid_document_requirements"), dict) else {}
        composition = bid_doc.get("composition") if isinstance(bid_doc, dict) else []
        if (not isinstance(composition, list) or len(composition) == 0) and re.search(r"投标文件应包括|投标文件的组成|投标文件格式|投标文件编制", source):
            issues.append("原文存在投标文件组成/格式要求但组成项为空")

        source_refs = report.get("source_refs")
        if not isinstance(source_refs, list) or len(source_refs) == 0:
            issues.append("source_refs 为空，无法追溯原文出处")

        return issues

    @classmethod
    def _supplement_analysis_report_from_source(cls, report: Dict[str, Any], source_text: str) -> Dict[str, Any]:
        """用原文中可直接抽取的结构化条款补齐模型漏填字段。

        这一步只补“模型返回为空、但原文可追溯抽取”的评分/资格/投标文件组成项，
        不生成通用默认报告，也不覆盖模型已经解析出的内容。
        """
        if not isinstance(report, dict):
            return report

        enriched = dict(report)
        added_ids: list[str] = []

        project = dict(enriched.get("project") or {}) if isinstance(enriched.get("project"), dict) else {}
        project_extractors = {
            "name": lambda text: cls._extract_project_name(text),
            "number": lambda text: cls._extract_project_number(text),
            "purchaser": lambda text: cls._extract_labeled_value(text, ["招标人", "采购人", "建设单位"], 100),
            "agency": lambda text: cls._extract_labeled_value(text, ["招标代理机构", "采购代理机构", "代理机构"], 100),
            "procurement_method": lambda text: cls._extract_labeled_value(text, ["采购方式", "招标方式"], 80),
            "project_type": lambda text: cls._extract_labeled_value(text, ["项目类型", "采购类型"], 80),
            "budget": lambda text: cls._extract_labeled_value(text, ["预算金额", "项目预算", "采购预算"], 120),
            "maximum_price": lambda text: cls._extract_labeled_value(text, ["最高限价", "最高投标限价", "招标控制价"], 120),
            "funding_source": lambda text: cls._extract_labeled_value(text, ["资金来源"], 120),
            "service_scope": lambda text: cls._extract_labeled_value(text, ["服务范围", "采购内容", "招标范围", "项目概况"], 180),
            "service_period": lambda text: cls._extract_labeled_value(text, ["服务期限", "工期", "合同履行期限", "履约期限"], 120),
            "service_location": lambda text: cls._extract_labeled_value(text, ["服务地点", "项目地点", "建设地点", "履约地点"], 120),
            "quality_requirements": lambda text: cls._extract_labeled_value(text, ["质量要求", "服务质量"], 120),
            "bid_validity": lambda text: cls._extract_labeled_value(text, ["投标有效期"], 120),
            "bid_bond": lambda text: cls._extract_labeled_value(text, ["投标保证金"], 160),
            "performance_bond": lambda text: cls._extract_labeled_value(text, ["履约担保", "履约保证金"], 160),
            "bid_deadline": lambda text: cls._extract_labeled_value(text, ["投标截止时间", "递交截止时间"], 120),
            "opening_time": lambda text: cls._extract_labeled_value(text, ["开标时间"], 120),
            "submission_method": lambda text: cls._extract_labeled_value(text, ["递交方式", "投标文件递交"], 160),
            "electronic_platform": lambda text: cls._extract_labeled_value(text, ["电子交易平台", "电子招投标平台", "交易平台"], 160),
            "submission_requirements": lambda text: cls._extract_labeled_value(text, ["递交要求", "投标文件递交", "电子投标"], 180),
        }
        project_filled = False
        for key, extractor in project_extractors.items():
            if project.get(key):
                continue
            value = extractor(source_text)
            if value:
                project[key] = value
                project_filled = True
        if project_filled:
            enriched["project"] = project
            added_ids.append("PROJECT-INFO")

        technical_items, business_items, price_items = cls._extract_scoring_items_from_text(source_text)
        scoring_sources = (
            ("technical_scoring_items", technical_items),
            ("business_scoring_items", business_items),
            ("price_scoring_items", price_items),
        )
        for key, extracted_items in scoring_sources:
            existing_items = enriched.get(key)
            if isinstance(existing_items, list) and existing_items:
                continue
            if extracted_items:
                enriched[key] = extracted_items
                added_ids.extend(str(item.get("id") or "") for item in extracted_items if item.get("id"))

        qualification_count = sum(
            len(enriched.get(key) or [])
            for key in ("qualification_requirements", "qualification_review_items")
            if isinstance(enriched.get(key), list)
        )
        if qualification_count == 0:
            qualification_items = cls._extract_qualification_items_from_text(source_text)
            if qualification_items:
                enriched["qualification_requirements"] = qualification_items
                added_ids.extend(str(item.get("id") or "") for item in qualification_items if item.get("id"))

        bid_doc = enriched.get("bid_document_requirements") if isinstance(enriched.get("bid_document_requirements"), dict) else {}
        composition = bid_doc.get("composition") if isinstance(bid_doc, dict) else []
        if not isinstance(composition, list) or not composition:
            parsed_bid_doc = cls._extract_bid_document_requirements(source_text, allow_generic_defaults=False)
            parsed_composition = parsed_bid_doc.get("composition") if isinstance(parsed_bid_doc, dict) else []
            if isinstance(parsed_composition, list) and parsed_composition:
                merged_bid_doc = dict(bid_doc)
                for field, value in parsed_bid_doc.items():
                    if value not in (None, "", [], {}) and not merged_bid_doc.get(field):
                        merged_bid_doc[field] = value
                enriched["bid_document_requirements"] = merged_bid_doc
                added_ids.extend(str(item.get("id") or "") for item in parsed_composition if isinstance(item, dict) and item.get("id"))

        if added_ids:
            source_refs = enriched.get("source_refs") if isinstance(enriched.get("source_refs"), list) else []
            existing_source_ids = {str(ref.get("id") or "") for ref in source_refs if isinstance(ref, dict)}
            if "SRC-SYSTEM-EXTRACT-01" not in existing_source_ids:
                source_refs.append({
                    "id": "SRC-SYSTEM-EXTRACT-01",
                    "location": "招标文件原文结构化抽取",
                    "excerpt": "模型漏填字段由系统从评分办法、资格要求或投标文件组成原文中补齐。",
                    "related_ids": list(dict.fromkeys(added_ids))[:30],
                })
                enriched["source_refs"] = source_refs

            warnings = enriched.get("generation_warnings") if isinstance(enriched.get("generation_warnings"), list) else []
            warnings.append({
                "id": "W-SOURCE-SUPPLEMENT-01",
                "warning": "模型返回的结构化报告存在空字段，系统仅用招标文件原文可追溯条款补齐评分/资格/组成项；请人工复核。",
                "severity": "warning",
                "related_ids": list(dict.fromkeys(added_ids))[:30],
            })
            enriched["generation_warnings"] = warnings

            matrix = enriched.get("response_matrix") if isinstance(enriched.get("response_matrix"), dict) else {}
            matrix_items = matrix.get("items") if isinstance(matrix.get("items"), list) else []
            existing_matrix_source_ids = {str(item.get("source_item_id") or "") for item in matrix_items if isinstance(item, dict)}
            supplement_items = []
            source_items = [
                *enriched.get("technical_scoring_items", []),
                *enriched.get("business_scoring_items", []),
                *enriched.get("price_scoring_items", []),
                *enriched.get("qualification_requirements", []),
            ]
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("id") or "")
                if not source_id or source_id in existing_matrix_source_ids:
                    continue
                supplement_items.append({
                    "id": f"RM-SUP-{len(matrix_items) + len(supplement_items) + 1:02d}",
                    "source_item_id": source_id,
                    "source_type": "price" if source_id.startswith("P-") else ("scoring" if source_id.startswith(("T-", "B-")) else "review"),
                    "requirement_summary": item.get("name") or item.get("standard") or item.get("requirement") or item.get("logic") or "",
                    "response_strategy": "按招标文件原文条款逐项响应，并关联证明材料。",
                    "target_chapter_ids": [],
                    "required_material_ids": item.get("required_materials") or item.get("evidence_requirements") or [],
                    "risk_ids": [],
                    "source_refs": ["SRC-SYSTEM-EXTRACT-01"],
                    "priority": "high" if source_id.startswith(("T-", "Q-", "P-")) else "normal",
                    "status": "pending",
                    "blocking": source_id.startswith("Q-"),
                })
            if supplement_items:
                matrix["items"] = [*matrix_items, *supplement_items]
                matrix["uncovered_ids"] = list(dict.fromkeys([
                    *(matrix.get("uncovered_ids") if isinstance(matrix.get("uncovered_ids"), list) else []),
                    *(item["source_item_id"] for item in supplement_items),
                ]))
                matrix["high_risk_ids"] = list(dict.fromkeys([
                    *(matrix.get("high_risk_ids") if isinstance(matrix.get("high_risk_ids"), list) else []),
                    *(item["id"] for item in supplement_items if item.get("blocking")),
                ]))
                matrix["coverage_summary"] = matrix.get("coverage_summary") or "模型解析结果已补充原文抽取的关键响应项。"
                enriched["response_matrix"] = matrix

        return AnalysisReport.model_validate(enriched).model_dump(mode="json")

    @classmethod
    def _analysis_repair_evidence_pack(cls, source_text: str, max_chars: int = 18000) -> str:
        """为质量重试提取原文证据包，不生成结论，只提供模型重建 JSON 的依据。"""
        source = str(source_text or "")
        keywords = [
            "招标编号", "项目名称", "招标人", "采购人", "服务期限", "服务范围",
            "投标人资格要求", "资格要求", "资质要求", "业绩要求", "信誉要求",
            "投标文件应包括", "投标文件的组成", "投标文件格式",
            "评标办法前附表", "详细评审", "评分标准", "商务部分", "服务部分",
            "投标报价", "废标", "否决", "实质性响应",
        ]
        windows: list[str] = []
        seen_ranges: list[tuple[int, int]] = []
        for keyword in keywords:
            start = source.find(keyword)
            if start < 0:
                continue
            left = max(0, start - 900)
            right = min(len(source), start + 2600)
            if any(abs(left - old_left) < 400 for old_left, _ in seen_ranges):
                continue
            seen_ranges.append((left, right))
            windows.append(f"【{keyword}】\n{source[left:right]}")
        if not windows:
            windows.append(source[:max_chars])
        return "\n\n---\n\n".join(windows)[:max_chars]

    @classmethod
    def _coerce_analysis_report_payload(cls, payload: Any) -> Dict[str, Any] | None:
        """把兼容模型常见的自定义招标解析 JSON 映射为内部 AnalysisReport。"""
        if not isinstance(payload, dict):
            return None
        analysis_report_keys = {
            "project",
            "source_refs",
            "bid_document_requirements",
            "formal_review_items",
            "qualification_review_items",
            "responsiveness_review_items",
            "business_scoring_items",
            "technical_scoring_items",
            "price_scoring_items",
            "price_rules",
            "qualification_requirements",
            "formal_response_requirements",
            "mandatory_clauses",
            "rejection_risks",
            "required_materials",
            "response_matrix",
        }
        if any(key in payload for key in analysis_report_keys):
            return cls._normalize_analysis_report_payload(payload)

        has_compatible_keys = any(
            key in payload
            for key in (
                "projectName",
                "tenderCode",
                "tenderer",
                "evaluationCriteria",
                "qualificationRequirements",
                "bidSubmission",
            )
        )
        if not has_compatible_keys:
            return None

        budget = payload.get("budget") if isinstance(payload.get("budget"), dict) else {}
        lots = budget.get("lots") if isinstance(budget, dict) else []
        budget_text = ""
        if isinstance(lots, list) and lots:
            budget_text = "；".join(
                f"{item.get('lotNumber') or ''}{item.get('lotName') or ''}: {item.get('budgetAmount') or item.get('budgetAmountExcludingTax') or ''}"
                for item in lots
                if isinstance(item, dict)
            )
        elif isinstance(budget, dict):
            budget_text = cls._stringify_requirement(budget)

        bid_submission = payload.get("bidSubmission") if isinstance(payload.get("bidSubmission"), dict) else {}
        bid_opening = payload.get("bidOpening") if isinstance(payload.get("bidOpening"), dict) else {}
        bid_bond = payload.get("bidBond") if isinstance(payload.get("bidBond"), dict) else {}

        project = {
            "name": str(payload.get("projectName") or ""),
            "number": str(payload.get("tenderCode") or ""),
            "purchaser": str(payload.get("tenderer") or ""),
            "agency": str(payload.get("tenderAgent") or ""),
            "procurement_method": "公开招标",
            "project_type": "勘察设计服务",
            "budget": budget_text,
            "maximum_price": budget_text,
            "service_scope": str(payload.get("scope") or ""),
            "service_period": str(payload.get("servicePeriod") or ""),
            "service_location": str(payload.get("serviceLocation") or ""),
            "bid_deadline": str(bid_submission.get("deadline") or ""),
            "opening_time": str(bid_opening.get("time") or bid_submission.get("deadline") or ""),
            "submission_method": str(bid_submission.get("method") or ""),
            "electronic_platform": str(bid_submission.get("location") or ""),
            "submission_requirements": str(bid_submission.get("format") or ""),
            "bid_bond": cls._stringify_requirement(bid_bond),
        }

        evaluation = payload.get("evaluationCriteria") if isinstance(payload.get("evaluationCriteria"), dict) else {}

        def scoring_items(group_key: str, prefix: str) -> list[dict[str, Any]]:
            group = evaluation.get(group_key) if isinstance(evaluation, dict) else {}
            raw_items = group.get("items") if isinstance(group, dict) else []
            result = []
            for index, item in enumerate(raw_items or [], start=1):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("item") or item.get("name") or f"{group_key}-{index}")
                score = item.get("score") or item.get("weight") or ""
                result.append({
                    "id": f"{prefix}-{index:02d}",
                    "name": name,
                    "score": f"{score}分" if isinstance(score, (int, float)) else str(score),
                    "standard": cls._stringify_requirement(item.get("standard") or item.get("requirements") or item),
                    "source": "模型解析的评审办法/评分标准",
                    "writing_focus": name,
                    "evidence_requirements": [],
                    "easy_loss_points": [],
                })
            return result

        technical_items = scoring_items("technical", "T")
        business_items = scoring_items("commercial", "B")
        price_group = evaluation.get("price") if isinstance(evaluation, dict) else {}
        price_items = []
        if isinstance(price_group, dict) and price_group:
            price_items.append({
                "id": "P-01",
                "name": "报价评分",
                "score": f"{price_group.get('weight')}分" if price_group.get("weight") else "",
                "logic": cls._stringify_requirement(price_group),
                "source": "模型解析的评审办法/报价评分",
                "risk": "",
            })

        qualification = payload.get("qualificationRequirements") if isinstance(payload.get("qualificationRequirements"), dict) else {}
        qualification_items: list[dict[str, Any]] = []
        required_materials: list[dict[str, Any]] = []
        for index, (key, value) in enumerate(qualification.items(), start=1):
            if value in (None, "", [], {}):
                continue
            req_id = f"Q-{index:02d}"
            name = {
                "eligibility": "主体资格",
                "qualifications": "资质要求",
                "financial": "财务要求",
                "performance": "业绩要求",
                "reputation": "信誉要求",
                "personnel": "人员要求",
                "jointVenture": "联合体要求",
            }.get(str(key), str(key))
            qualification_items.append({
                "id": req_id,
                "name": name,
                "requirement": cls._stringify_requirement(value, 500),
                "source": "模型解析的资格要求",
                "required_materials": [f"M-{index:02d}"],
            })
            required_materials.append({
                "id": f"M-{index:02d}",
                "name": f"{name}证明材料",
                "purpose": name,
                "source": "模型解析的资格要求",
                "status": "missing",
                "used_by": [req_id],
                "volume_id": "V-QUAL",
            })

        special = payload.get("specialProvisions") if isinstance(payload.get("specialProvisions"), list) else []
        mandatory_clauses = [
            {
                "id": f"C-{index:02d}",
                "clause": cls._stringify_requirement(item, 220),
                "source": "模型解析的特别规定",
                "response_strategy": "正文或商务响应中明确承诺，并由人工复核。",
                "invalid_if_not_responded": True,
            }
            for index, item in enumerate(special[:12], start=1)
        ]

        scheme_requirements = [
            {
                "id": f"BD-SP-{index:02d}",
                "parent_title": "技术/服务方案",
                "order": index,
                "title": item.get("name") or item.get("item") or f"方案要点{index}",
                "required": True,
                "allow_expand": True,
                "source_ref": "BD-SRC-01",
                "target_chapter_hint": item.get("name") or item.get("item") or "",
            }
            for index, item in enumerate(technical_items or [{"name": "服务实施方案"}], start=1)
        ]
        composition = [
            {
                "id": "BD-01",
                "order": 1,
                "title": "技术/服务方案",
                "required": True,
                "applicability": "required",
                "volume_id": "V-TECH",
                "chapter_type": "service_plan",
                "fixed_format": False,
                "allow_self_drafting": True,
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
            },
            {
                "id": "BD-02",
                "order": 2,
                "title": "资格审查资料",
                "required": True,
                "applicability": "required",
                "volume_id": "V-QUAL",
                "chapter_type": "qualification",
                "fixed_format": False,
                "allow_self_drafting": False,
                "signature_required": True,
                "seal_required": True,
                "attachment_required": True,
                "price_related": False,
                "anonymity_sensitive": False,
                "source_ref": "BD-SRC-01",
                "must_keep_text": [],
                "must_keep_columns": [],
                "fillable_fields": [],
                "children": [],
            },
            {
                "id": "BD-03",
                "order": 3,
                "title": "报价文件",
                "required": True,
                "applicability": "required",
                "volume_id": "V-PRICE",
                "chapter_type": "price",
                "fixed_format": True,
                "allow_self_drafting": False,
                "signature_required": True,
                "seal_required": True,
                "attachment_required": False,
                "price_related": True,
                "anonymity_sensitive": False,
                "source_ref": "BD-SRC-01",
                "must_keep_text": [],
                "must_keep_columns": [],
                "fillable_fields": [],
                "children": [],
            },
        ]
        response_items = []
        for index, item in enumerate([*technical_items, *business_items, *qualification_items], start=1):
            source_id = item.get("id") or f"REQ-{index:02d}"
            response_items.append({
                "id": f"RM-{index:02d}",
                "source_item_id": source_id,
                "source_type": "scoring" if str(source_id).startswith(("T-", "B-")) else "review",
                "requirement_summary": item.get("name") or item.get("requirement") or "",
                "response_strategy": "在对应章节中逐项响应，并保留人工复核占位。",
                "target_chapter_ids": [],
                "required_material_ids": item.get("required_materials") or [],
                "risk_ids": [],
                "source_refs": [],
                "priority": "high" if str(source_id).startswith(("T-", "Q-")) else "normal",
                "status": "pending",
                "blocking": str(source_id).startswith("Q-"),
            })

        return {
            "project": project,
            "bid_mode_recommendation": "technical_only",
            "source_refs": [{"id": "SRC-01", "location": "模型解析的招标文件关键信息", "excerpt": project.get("name", ""), "related_ids": []}],
            "bid_document_requirements": {
                "source_chapters": [{"id": "BD-SRC-01", "chapter_title": "投标文件/评审办法", "location": "模型兼容解析", "excerpt": "模型返回兼容结构后由系统归一化"}],
                "document_scope_required": "unknown",
                "composition": composition,
                "scheme_or_technical_outline_requirements": scheme_requirements,
                "selected_generation_target": {
                    "target_id": "BD-01",
                    "target_title": "技术/服务方案",
                    "parent_composition_id": "BD-01",
                    "target_source": "模型解析的技术评分项",
                    "target_source_type": "scoring_section",
                    "generation_scope": "scheme_section_only",
                    "use_as_outline_basis": True,
                    "base_outline_strategy": "technical_scoring_items",
                    "base_outline_items": [
                        {"order": item["order"], "title": item["title"], "source_ref": item["source_ref"], "must_preserve_title": False}
                        for item in scheme_requirements
                    ],
                    "excluded_composition_item_ids": ["BD-02", "BD-03"],
                    "excluded_composition_titles": ["资格审查资料", "报价文件"],
                    "selection_reason": "模型返回了评分项结构，系统按技术/服务方案分册生成。",
                    "confidence": "medium",
                },
                "fixed_forms": [],
                "formatting_and_submission_rules": {
                    "language": "",
                    "toc_required": True,
                    "page_number_required": True,
                    "binding_or_upload_rules": project.get("submission_requirements", ""),
                    "electronic_signature_rules": "",
                    "encryption_or_platform_rules": project.get("electronic_platform", ""),
                    "source_ref": "BD-SRC-01",
                },
                "excluded_when_generating_technical_only": ["资格审查资料", "报价文件"],
                "priority_rule": "投标文件编制要求优先于样例风格。",
            },
            "volume_rules": [],
            "anonymity_rules": {"enabled": False, "scope": "", "forbidden_identifiers": [], "formatting_rules": [], "source": ""},
            "bid_structure": [],
            "formal_review_items": [],
            "qualification_review_items": [],
            "responsiveness_review_items": [],
            "business_scoring_items": business_items,
            "technical_scoring_items": technical_items,
            "price_scoring_items": price_items,
            "price_rules": {
                "quote_method": "固定综合服务下浮率报价" if "下浮" in cls._stringify_requirement(payload) else "",
                "currency": "CNY",
                "maximum_price_rule": budget_text,
                "abnormally_low_price_rule": "",
                "separate_price_volume_required": True,
                "price_forbidden_in_other_volumes": True,
                "tax_requirement": "",
                "decimal_places": "",
                "uniqueness_requirement": "",
                "form_requirements": "",
                "arithmetic_correction_rule": "",
                "missing_item_rule": "",
                "prohibited_format_changes": [],
                "source_ref": "SRC-01",
            },
            "qualification_requirements": qualification_items,
            "formal_response_requirements": [],
            "mandatory_clauses": mandatory_clauses,
            "rejection_risks": [],
            "fixed_format_forms": [],
            "signature_requirements": [],
            "evidence_chain_requirements": [],
            "required_materials": required_materials,
            "missing_company_materials": [],
            "enterprise_material_profile": EnterpriseMaterialService.build_profile(
                required_materials=required_materials,
                missing_company_materials=[],
                evidence_chain_requirements=[],
            ),
            "generation_warnings": [{
                "id": "W-STRUCTURE-01",
                "warning": "模型返回了兼容招标解析结构，系统已归一化为 AnalysisReport；请人工复核字段覆盖。",
                "severity": "warning",
                "related_ids": [],
            }],
            "response_matrix": {
                "items": response_items,
                "uncovered_ids": [item.get("source_item_id", "") for item in response_items],
                "high_risk_ids": [item.get("id", "") for item in response_items if item.get("blocking")],
                "coverage_summary": "由兼容解析结构归一化生成的初始响应矩阵。",
            },
            "reference_bid_style_profile": {},
            "document_blocks_plan": {},
        }

    async def generate_analysis_report(self, file_content: str) -> Dict[str, Any]:
        """从招标文件全文生成结构化标准解析报告"""
        if self._force_local_fallback():
            return self._fallback_analysis_report(file_content, "本地安全验证模式")

        timeout_seconds = self._int_env("YIBIAO_ANALYSIS_REPORT_TIMEOUT_SECONDS", 1800)
        max_tokens = self._int_env("YIBIAO_ANALYSIS_REPORT_MAX_TOKENS", 12000)
        max_input_chars = self._int_env("YIBIAO_ANALYSIS_INPUT_MAX_CHARS", 70000)
        analysis_input = self._prepare_analysis_input(file_content, max_input_chars)
        if len(analysis_input) < len(str(file_content or "")):
            print(
                "标准解析报告 输入过长，已按关键词窗口压缩："
                f"{len(str(file_content or ''))} -> {len(analysis_input)} 字符",
                flush=True,
            )
        cache_key = GenerationCacheService.build_key(
            "analysis_report",
            self.model_name,
            {
                "analysis_input": analysis_input,
                "max_tokens": max_tokens,
                "include_schema": self._include_schema_in_prompt(),
            },
        )
        cached_report = GenerationCacheService.get("analysis_report", cache_key)
        if isinstance(cached_report, dict):
            return AnalysisReport.model_validate(cached_report).model_dump(mode="json")
        system_prompt, user_prompt = prompt_manager.generate_analysis_report_prompt(
            analysis_input,
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        generation_task = self._generate_pydantic_json(
            messages=messages,
            model_cls=AnalysisReport,
            max_retries=1,
            temperature=0.1,
            response_format=self._pydantic_response_format("analysis_report", AnalysisReport),
            max_tokens=max_tokens,
            log_prefix="标准解析报告",
        )
        try:
            if timeout_seconds > 0:
                report = await asyncio.wait_for(generation_task, timeout=timeout_seconds)
            else:
                report = await generation_task
            report = self._supplement_analysis_report_from_source(report, analysis_input)
            quality_issues = self._analysis_report_quality_issues(report, analysis_input)
            if quality_issues:
                print(
                    "标准解析报告 内容质量未达标，进行模型重建："
                    f"{'；'.join(quality_issues)}",
                    flush=True,
                )
                evidence_pack = self._analysis_repair_evidence_pack(analysis_input)
                repair_messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "上一轮返回的 JSON 语法合法，但关键字段为空或缺失，不能作为标准解析结果。"
                            "请仅依据下面的招标文件原文证据包，重建完整 AnalysisReport JSON。"
                            "这不是兜底生成，必须从证据包中抽取真实条款；没有出现的信息保持空字符串或空数组。"
                            "必须重点补齐 project、qualification_requirements、qualification_review_items、"
                            "technical_scoring_items、business_scoring_items、price_scoring_items、"
                            "bid_document_requirements.composition、source_refs。"
                            "所有数组字段必须输出数组，所有条目必须带 id 和 source/source_ref。\n\n"
                            f"质量问题：{'；'.join(quality_issues)}\n\n"
                            f"<tender_evidence_pack>\n{evidence_pack}\n</tender_evidence_pack>\n\n"
                            "只返回合法 JSON。"
                        ),
                    },
                ]
                repair_task = self._generate_pydantic_json(
                    messages=repair_messages,
                    model_cls=AnalysisReport,
                    max_retries=1,
                    temperature=0.05,
                    response_format=self._pydantic_response_format("analysis_report_repaired", AnalysisReport),
                    max_tokens=max_tokens,
                    log_prefix="标准解析报告修复",
                )
                report = await asyncio.wait_for(repair_task, timeout=timeout_seconds) if timeout_seconds > 0 else await repair_task
                report = self._supplement_analysis_report_from_source(report, analysis_input)
                quality_issues = self._analysis_report_quality_issues(report, analysis_input)
                if quality_issues:
                    raise Exception(
                        "模型返回的 JSON 已能解析为标准结构，但关键内容仍为空："
                        f"{'；'.join(quality_issues)}。请换用更强模型或检查模型网关是否截断输出；系统不会使用兜底报告。"
                    )
            report = self._repair_bid_document_requirements(report, file_content)
            if not report.get("response_matrix"):
                report["response_matrix"] = await self.generate_response_matrix(report)
            enterprise_profile = report.get("enterprise_material_profile") or {}
            if not enterprise_profile.get("requirements"):
                report["enterprise_material_profile"] = EnterpriseMaterialService.build_profile(
                    required_materials=report.get("required_materials") or [],
                    missing_company_materials=report.get("missing_company_materials") or [],
                    evidence_chain_requirements=report.get("evidence_chain_requirements") or [],
                )
            validated = AnalysisReport.model_validate(report).model_dump(mode="json")
            GenerationCacheService.set("analysis_report", cache_key, validated)
            return validated
        except asyncio.TimeoutError as e:
            raise Exception(
                f"模型解析超时：标准解析超过 {timeout_seconds} 秒仍未完成。"
                "系统已停止后续目录生成，未启用兜底报告；请换用更快模型、调高 "
                "YIBIAO_ANALYSIS_REPORT_TIMEOUT_SECONDS，或缩短输入后重新解析。"
            ) from e
        except Exception as e:
            raise Exception(
                "结构化标准解析报告生成失败，系统已停止后续目录生成，未启用兜底报告。"
                f"原因：{self._compact_text(str(e), 180)}"
            ) from e
