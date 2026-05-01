"""多模型兼容服务（基于 OpenAI SDK 兼容层）"""
import openai
from typing import Dict, Any, List, AsyncGenerator
import json
import asyncio
import re
import aiohttp
import os

from ..utils.outline_util import generate_one_outline_json_by_level1
from ..utils import prompt_manager
from ..utils.json_util import check_json
from ..utils.config_manager import config_manager
from ..models.schemas import AnalysisReport, ResponseMatrix, ReviewReport
from ..utils.provider_registry import (
    DEFAULT_PROVIDER,
    get_base_url_candidates,
    get_default_base_url,
    get_default_models,
    get_provider_api_mode,
    normalize_base_url,
    provider_supports_model_listing,
    resolve_api_key,
)


class OpenAIService:
    """多模型服务类"""
    
    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化模型服务，支持传入运行时配置覆盖已保存配置"""
        runtime_config = dict(config or config_manager.load_config())
        # 模型接入统一收敛到 LiteLLM Proxy，由 LiteLLM 负责把各厂商协议转换成 OpenAI 格式。
        self.provider = DEFAULT_PROVIDER
        self.api_key = runtime_config.get('api_key', '')
        self.base_url = runtime_config.get('base_url', '')
        self.model_name = runtime_config.get('model_name', 'gpt-4.1-mini')
        self.api_mode = get_provider_api_mode(self.provider, runtime_config.get('api_mode', 'auto'))
        self.normalized_base_url = normalize_base_url(self.provider, self.base_url)
        self.base_url_candidates = get_base_url_candidates(self.provider, self.base_url)
        self.resolved_base_url = (
            self.base_url_candidates[0]
            if self.base_url_candidates
            else (self.normalized_base_url or get_default_base_url(self.provider))
        )
        self.uses_anthropic_api = False
        self.uses_responses_api = False

        # 统一走 LiteLLM Proxy 暴露的 OpenAI Chat Completions 兼容接口。
        self.client = self._create_client(self.resolved_base_url)

    def _create_client(self, base_url: str | None) -> openai.AsyncOpenAI:
        """按指定 Base URL 创建客户端实例"""
        return openai.AsyncOpenAI(
            api_key=resolve_api_key(self.provider, self.api_key),
            base_url=base_url if base_url else None,
            default_headers={
                "Accept": "application/json",
                "User-Agent": "curl/8.7.1",
            },
        )

    @staticmethod
    def _force_local_fallback() -> bool:
        """端到端本地验证开关，避免测试时把用户招标文件外传到第三方模型。"""
        return os.getenv("YIBIAO_FORCE_LOCAL_FALLBACK") == "1"

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        """读取正整数环境变量；非法值回退到默认值。"""
        try:
            value = int(os.getenv(name, str(default)))
            return value if value >= 0 else default
        except (TypeError, ValueError):
            return default

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

    def _iter_base_urls(self) -> list[str | None]:
        """获取本次请求应尝试的 Base URL 列表"""
        if self.provider in {"custom", "anthropic", "litellm"} and self.base_url_candidates:
            return list(self.base_url_candidates)
        return [self.resolved_base_url]

    @staticmethod
    def _join_endpoint(base_url: str, path: str, force_v1: bool = False) -> str:
        """拼接 API 端点路径，兼容根地址和 /v1 根地址"""
        normalized_base = (base_url or "").rstrip("/")
        normalized_path = path if path.startswith("/") else f"/{path}"
        if force_v1 and not normalized_base.endswith("/v1"):
            normalized_base = f"{normalized_base}/v1"
        return f"{normalized_base}{normalized_path}"

    @staticmethod
    def _response_format_requires_json_guard(response_format: dict | None) -> bool:
        """判断当前响应格式是否需要额外的 JSON 输出约束"""
        if not response_format:
            return False
        return response_format.get("type") in {"json_object", "json_schema"}

    def _augment_messages_for_json_output(self, messages: list, response_format: dict | None) -> list:
        """为不支持 response_format 的本地兼容端点追加 JSON 纯输出约束"""
        if not self._response_format_requires_json_guard(response_format):
            return messages

        json_guard = (
            "你必须只输出合法 JSON，不要输出 markdown 代码块，不要输出解释性文字，"
            "不要在 JSON 前后添加任何多余内容。"
        )

        augmented_messages: list[dict[str, Any]] = []
        appended_to_system = False
        for message in messages:
            cloned = dict(message)
            if not appended_to_system and cloned.get("role") == "system":
                original_content = str(cloned.get("content", "")).strip()
                cloned["content"] = f"{original_content}\n\n{json_guard}" if original_content else json_guard
                appended_to_system = True
            augmented_messages.append(cloned)

        if not appended_to_system:
            augmented_messages.insert(0, {"role": "system", "content": json_guard})

        return augmented_messages

    @staticmethod
    def _extract_json_payload(full_content: str) -> str:
        """尽量从模型返回中提取纯 JSON 文本，兼容本地模型常见的代码块包裹"""
        if not isinstance(full_content, str):
            return full_content

        candidate = full_content.strip()
        if not candidate:
            return candidate

        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)
            candidate = candidate.strip()

        first_positions = [pos for pos in (candidate.find("{"), candidate.find("[")) if pos != -1]
        if first_positions:
            start = min(first_positions)
            opening = candidate[start]
            closing = "}" if opening == "{" else "]"
            end = candidate.rfind(closing)
            if end != -1 and end > start:
                sliced = candidate[start:end + 1].strip()
                if sliced:
                    return sliced

        return candidate

    @staticmethod
    def _compact_text(text: str, limit: int = 120) -> str:
        """压缩模型/文本抽取内容，避免兜底报告继续制造超长 JSON。"""
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        return normalized[:limit]

    @staticmethod
    def _clean_extracted_value(value: str, limit: int = 80) -> str:
        """清洗从段落或表格中抽出的字段值。"""
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" |:：\t")
        if "||" in cleaned:
            cleaned = cleaned.split("||", 1)[0].strip()
        if "|" in cleaned:
            cleaned = cleaned.split("|", 1)[0].strip()
        return cleaned[:limit]

    @staticmethod
    def _extract_table_value(text: str, labels: list[str], limit: int = 80) -> str:
        """从 file_service 扁平化后的 Word 表格行中抽取字段。"""
        for raw_line in str(text or "").splitlines():
            if "||" not in raw_line and "|" not in raw_line:
                continue
            cells = [cell.strip() for cell in re.split(r"\s*\|\|?\s*", raw_line) if cell.strip()]
            for index, cell in enumerate(cells[:-1]):
                normalized_cell = re.sub(r"^\d+(?:\.\d+)*\s*", "", cell).strip()
                for label in labels:
                    colon_match = re.match(rf"^{re.escape(label)}\s*[：:]\s*(.+)$", normalized_cell)
                    if colon_match:
                        return OpenAIService._clean_extracted_value(colon_match.group(1), limit)
                if any(label == normalized_cell for label in labels):
                    for candidate in cells[index + 1:]:
                        if candidate and candidate not in {"编列内容", "要求", "评审标准"}:
                            return OpenAIService._clean_extracted_value(candidate, limit)
        return ""

    @staticmethod
    def _extract_labeled_value(text: str, labels: list[str], limit: int = 80) -> str:
        """从招标文本中按常见标签抽取一行字段。"""
        table_value = OpenAIService._extract_table_value(text, labels, limit)
        if table_value:
            return table_value
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[：:]\s*([^\n\r。；;]{{1,120}})"
            match = re.search(pattern, text)
            if match:
                return OpenAIService._clean_extracted_value(match.group(1), limit)
        return ""

    @staticmethod
    def _extract_project_name(text: str) -> str:
        """优先从封面、公告标题或须知表抽取项目名称。"""
        table_value = OpenAIService._extract_table_value(text, ["招标项目名称", "项目名称", "采购项目名称"], 100)
        if table_value and not table_value.startswith("见"):
            return table_value
        cover_match = re.search(r"([^|\n\r]{4,100}?(?:服务框架|项目|工程|采购))\s*\|\s*招标文件", str(text or ""))
        if cover_match:
            return OpenAIService._clean_extracted_value(cover_match.group(1), 100)
        for raw_line in str(text or "").splitlines()[:40]:
            line = raw_line.strip()
            if not line or line in {"招标文件", "采购文件"}:
                continue
            if "招标文件" in line:
                candidate = line.replace("招标文件", "").strip()
                if candidate:
                    return OpenAIService._clean_extracted_value(candidate, 100)
            if re.search(r"服务框架|项目|工程|采购", line) and len(line) <= 80:
                return OpenAIService._clean_extracted_value(line, 100)
        match = re.search(r"本招标项目\s*([^\n\r，。]{4,100}?)(?:已|，|。)", text)
        if match:
            return OpenAIService._clean_extracted_value(match.group(1), 100)
        return table_value

    @staticmethod
    def _extract_project_number(text: str) -> str:
        """抽取招标/采购编号，避免表格残片误识别。"""
        match = re.search(r"(?:招标编号|项目编号|采购编号)\s*[：:]\s*([A-Za-z0-9_\-]+)", str(text or ""))
        if match:
            return OpenAIService._clean_extracted_value(match.group(1), 80)
        return OpenAIService._extract_labeled_value(text, ["项目编号", "招标编号", "采购编号"])

    @staticmethod
    def _keyword_source(text: str, keyword: str) -> str:
        """为兜底条目生成可追溯的粗粒度出处。"""
        index = text.find(keyword)
        if index == -1:
            return ""
        prefix = text[max(0, index - 80):index]
        chapter_match = re.findall(r"(第[一二三四五六七八九十\d]+章[^。\n\r]{0,30}|[一二三四五六七八九十\d]+[\.、][^。\n\r]{0,30})", prefix)
        return OpenAIService._compact_text(chapter_match[-1] if chapter_match else "招标文件相关条款", 60)

    @staticmethod
    def _extract_bid_document_requirements(text: str) -> Dict[str, Any]:
        """从招标文件中粗抽“投标文件/投标文件格式/组成/编制要求”。

        这是模型失败时的兜底抽取；模型正常时由 prompt 产出更完整的结构。
        """
        raw = str(text or "")
        compact = re.sub(r"[ \t]+", " ", raw)
        source_chapters: list[dict[str, Any]] = []
        for kw in ("投标文件格式", "投标文件的组成", "投标文件的编制", "投标文件"):
            idx = compact.find(kw)
            if idx >= 0:
                source_chapters.append({
                    "id": f"BD-SRC-{len(source_chapters)+1:02d}",
                    "chapter_title": kw,
                    "location": OpenAIService._keyword_source(raw, kw) or "招标文件相关章节",
                    "excerpt": OpenAIService._compact_text(compact[max(0, idx): idx + 160], 120),
                })
        if not source_chapters:
            source_chapters.append({"id": "BD-SRC-01", "chapter_title": "", "location": "", "excerpt": ""})

        # 1) 先抽“投标文件应包括下列内容”后的（1）（2）列表。
        comp_titles: list[str] = []
        include_match = re.search(r"投标文件应包括下列内容[：:\s]*(.*?)(?:投标人在评标过程中|3\.1\.2|3\.2\s|投标报价|$)", raw, flags=re.S)
        if include_match:
            segment = include_match.group(1)[:2000]
            for m in re.finditer(r"[（(]\s*\d+\s*[）)]\s*([^；;\n\r]+)", segment):
                title = OpenAIService._compact_text(m.group(1), 60).strip("；;，,。 ")
                if title and title not in comp_titles:
                    comp_titles.append(title)
        # 2) 再抽“投标文件格式/目录”附近的一、二、三列表。
        if not comp_titles:
            idx = max(raw.find("投标文件格式"), raw.find("投标文件"))
            if idx >= 0:
                segment = raw[idx: idx + 4000]
                for m in re.finditer(r"(?:^|[\n\r])\s*([一二三四五六七八九十]+)[、.．]\s*([^\n\r]{2,80})", segment):
                    title = OpenAIService._compact_text(m.group(2), 60).strip("；;，,。 ")
                    if title and not re.search(r"总则|招标文件|评标|合同授予|纪律|投诉", title) and title not in comp_titles:
                        comp_titles.append(title)
                    if len(comp_titles) >= 12:
                        break
        if not comp_titles:
            for title in ["投标函及投标函附录", "法定代表人身份证明或授权委托书", "投标保证金", "投标报价", "资格审查资料", "技术/服务/实施方案", "其他资料"]:
                if title not in comp_titles:
                    comp_titles.append(title)

        def classify(title: str) -> tuple[str, str, bool, bool, bool, bool]:
            t = title or ""
            if re.search(r"报价|价格|费用|开标一览", t):
                return "V-PRICE", "price", True, True, True, True
            if re.search(r"资格|资质|业绩|财务|信誉|人员|基本情况|证明", t):
                return "V-QUAL", "qualification", False, True, True, False
            if re.search(r"保证金|保函", t):
                return "V-BIZ", "bond", True, True, True, False
            if re.search(r"投标函|授权|身份证明|联合体|承诺", t):
                return "V-BIZ", "form", True, True, False, False
            if re.search(r"偏差|偏离", t):
                return "V-BIZ", "deviation_table", True, True, False, False
            if re.search(r"方案|施工组织|服务|技术|实施|供货|设计", t):
                return "V-TECH", "service_plan", False, False, False, False
            return "V-BIZ", "other", False, False, False, False

        composition: list[dict[str, Any]] = []
        for i, title in enumerate(comp_titles[:16], start=1):
            volume, ctype, fixed, sig, attachment, price_related = classify(title)
            not_applicable = bool(re.search(r"本项目不适用|不适用", title))
            composition.append({
                "id": f"BD-{i:02d}",
                "order": i,
                "title": title,
                "required": not not_applicable,
                "applicability": "not_applicable" if not_applicable else "required",
                "volume_id": volume,
                "chapter_type": ctype,
                "fixed_format": fixed,
                "allow_self_drafting": bool(re.search(r"方案|其他资料|承诺", title)),
                "signature_required": sig,
                "seal_required": sig or bool(re.search(r"盖章|单位章|公章", raw)),
                "attachment_required": attachment,
                "price_related": price_related,
                "anonymity_sensitive": bool(re.search(r"暗标|双盲|匿名", raw) and volume == "V-TECH"),
                "source_ref": source_chapters[0]["id"],
                "must_keep_text": [],
                "must_keep_columns": [],
                "fillable_fields": [],
                "children": [],
            })

        # 抽方案“应包括但不限于”的子项，兼容服务方案/技术方案/施工组织设计/供货方案/设计方案。
        scheme_items: list[dict[str, Any]] = []
        scheme_match = re.search(
            r"(?:服务纲要|服务方案|技术方案|设计方案|实施方案|施工组织设计|供货方案|售后服务方案)"
            r"[\s\S]{0,220}?应\s*包\s*括"
            r"(?:\s*[（(]?\s*但\s*不\s*限\s*于\s*[）)]?)?"
            r"[^：:]{0,120}[：:]\s*([\s\S]*?)"
            r"(?=\n\s*(?:[一二三四五六七八九十]+[、.．]\s*(?:其他资料|偏差表|投标报价|资格审查)|八、其他|七、其他|其他资料|注[:：]|以上内容)|$)",
            raw,
            flags=re.S,
        )
        if scheme_match:
            segment = scheme_match.group(1)[:2000]
            item_pattern = r"(?:^|[\n\r])\s*(?:[（(]?\s*(?:[一二三四五六七八九十]+|\d{1,2})\s*[）)]?[、.．])\s*([^；;。\n\r]+)"
            for m in re.finditer(item_pattern, segment):
                title = OpenAIService._compact_text(m.group(1), 80).strip("；;，,。 ")
                if title:
                    scheme_items.append({
                        "id": f"BD-SP-{len(scheme_items)+1:02d}",
                        "parent_title": "服务方案/设计方案/技术方案/实施方案",
                        "order": len(scheme_items)+1,
                        "title": title,
                        "required": True,
                        "allow_expand": True,
                        "source_ref": source_chapters[0]["id"],
                        "target_chapter_hint": "",
                    })
        canonical_scheme_items = OpenAIService._infer_canonical_design_service_outline(raw)
        if canonical_scheme_items and (
            not scheme_items
            or len(scheme_items) <= 2
            or not any("服务范围" in str(item.get("title") or "") for item in scheme_items)
        ):
            scheme_items = canonical_scheme_items
        # 如果没抽到，按 composition 中的方案章节做一个总约束。
        if not scheme_items:
            for item in composition:
                if item.get("volume_id") == "V-TECH" and item.get("chapter_type") in {"service_plan", "technical"}:
                    scheme_items.append({
                        "id": "BD-SP-01",
                        "parent_title": item.get("title") or "技术/服务方案",
                        "order": 1,
                        "title": item.get("title") or "技术/服务方案",
                        "required": True,
                        "allow_expand": True,
                        "source_ref": item.get("source_ref") or source_chapters[0]["id"],
                        "target_chapter_hint": "",
                    })
                    break

        fixed_forms = []
        for item in composition:
            if item.get("fixed_format"):
                fixed_forms.append({
                    "id": f"BD-FF-{len(fixed_forms)+1:02d}",
                    "form_name": item.get("title") or "固定格式",
                    "belongs_to": item.get("id"),
                    "must_keep_columns": [],
                    "must_keep_text": [],
                    "fillable_fields": [],
                    "signature_required": bool(item.get("signature_required")),
                    "seal_required": bool(item.get("seal_required")),
                    "date_required": bool(re.search(r"年\s*月\s*日|日期", raw)),
                    "source_ref": item.get("source_ref") or source_chapters[0]["id"],
                })

        selected_item = None
        for item in composition:
            title = str(item.get("title") or "")
            if item.get("volume_id") == "V-TECH" or re.search(r"服务方案|设计方案|技术方案|实施方案|施工组织设计|供货方案|售后方案|运维方案", title):
                selected_item = item
                break
        base_outline_items = []
        for req_item in scheme_items[:20]:
            title = str(req_item.get("title") or "").strip()
            if not title:
                continue
            # 如果只抽到一个“设计方案/服务方案”总项，不把它当作子目录；后续用评分项兜底。
            if len(scheme_items) == 1 and selected_item and title == str(selected_item.get("title") or ""):
                continue
            base_outline_items.append({
                "id": req_item.get("id") or f"BD-SP-{len(base_outline_items)+1:02d}",
                "order": int(req_item.get("order") or len(base_outline_items)+1),
                "title": title,
                "source_ref": req_item.get("source_ref") or source_chapters[0]["id"],
                "derived_from": "scheme_or_technical_outline_requirements",
                "must_preserve_title": True,
            })
        excluded_items = [item for item in composition if selected_item and item.get("id") != selected_item.get("id")]
        excluded = [item.get("title") for item in excluded_items if item.get("volume_id") in {"V-BIZ", "V-QUAL", "V-PRICE"} or item.get("id") != (selected_item or {}).get("id")]
        selected_generation_target = {
            "target_id": (selected_item or {}).get("id", ""),
            "target_title": (selected_item or {}).get("title", "技术/服务/实施方案"),
            "parent_composition_id": (selected_item or {}).get("id", ""),
            "target_source": (selected_item or {}).get("source_ref", source_chapters[0]["id"]),
            "target_source_type": "composition_item" if selected_item else "inferred",
            "generation_scope": "scheme_section_only" if selected_item else "unknown",
            "use_as_outline_basis": bool(selected_item),
            "base_outline_strategy": "scheme_outline" if base_outline_items else "technical_scoring_items",
            "base_outline_items": base_outline_items,
            "excluded_composition_item_ids": [item.get("id") for item in excluded_items if item.get("id")],
            "excluded_composition_titles": [title for title in excluded if title],
            "selection_reason": "从投标文件组成中识别到方案类章节；本系统默认生成该方案章节目录和正文，而不是整本投标文件。" if selected_item else "未明确识别方案类组成项，后续按技术评分项或通用技术方案生成。",
            "confidence": "high" if selected_item and base_outline_items else ("medium" if selected_item else "low"),
        }
        return {
            "source_chapters": source_chapters[:6],
            "document_scope_required": "full_bid" if len(composition) >= 5 else "unknown",
            "composition": composition,
            "scheme_or_technical_outline_requirements": scheme_items[:12],
            "selected_generation_target": selected_generation_target,
            "fixed_forms": fixed_forms[:12],
            "formatting_and_submission_rules": {
                "language": "中文" if "中文" in raw else "",
                "toc_required": bool(re.search(r"目录", raw)),
                "page_number_required": bool(re.search(r"页码|目录", raw)),
                "binding_or_upload_rules": OpenAIService._extract_labeled_value(raw, ["投标文件递交", "递交方式", "上传", "密封", "加密"], 160),
                "electronic_signature_rules": "按招标文件要求签字盖章/电子签章" if re.search(r"电子签章|电子印章|签字|盖章", raw) else "",
                "encryption_or_platform_rules": OpenAIService._extract_labeled_value(raw, ["电子招标投标平台", "交易平台", "加密", "验签"], 160),
                "source_ref": source_chapters[0]["id"],
            },
            "excluded_when_generating_technical_only": [x for x in excluded if x],
            "priority_rule": "投标文件编制要求优先于样例风格；样例只用于扩写深度和版式，不得覆盖招标文件格式。",
        }

    @staticmethod
    def _fallback_analysis_report(file_content: str, reason: str = "") -> Dict[str, Any]:
        """模型结构化输出失败时的保底 AnalysisReport。

        该兜底只使用招标文件原文可见信息，不虚构企业材料，目标是让后续目录、
        正文、审校、导出流程继续可执行，并在 UI 上暴露待补与风险。
        """
        text = str(file_content or "")
        project_name = OpenAIService._extract_project_name(text)
        project_number = OpenAIService._extract_project_number(text)
        purchaser = OpenAIService._extract_labeled_value(text, ["招标人", "采购人", "建设单位"])
        budget = OpenAIService._extract_labeled_value(text, ["预算金额", "最高限价", "招标控制价", "最高投标限价"])
        service_period = OpenAIService._extract_labeled_value(text, ["服务期限", "工期", "合同履行期限"])
        deadline = OpenAIService._extract_labeled_value(text, ["投标截止时间", "递交截止时间", "开标时间"])
        signature_req = "按招标文件格式完成法定代表人/授权代表签字或盖章并加盖公章" if re.search(r"签字|盖章|公章|法定代表人", text) else ""
        bid_document_requirements = OpenAIService._extract_bid_document_requirements(text)

        score_blocks = re.findall(
            r"【评分项名称】[：:]\s*(.*?)\s*【权重/分值】[：:]\s*(.*?)\s*【评分标准】[：:]\s*(.*?)(?=【评分项名称】|【数据来源】|$)",
            text,
            flags=re.S,
        )
        if not score_blocks:
            score_blocks = re.findall(
                r"([^\n\r。；;]{2,30})\s*([0-9]+(?:\.[0-9]+)?\s*分)\s*([^\n\r]{20,240})",
                text,
            )

        technical_items = []
        business_items = []
        required_materials = []
        missing_materials = []
        evidence_requirements = []
        for index, block in enumerate(score_blocks[:8], start=1):
            name, score, standard = (OpenAIService._compact_text(part, 80) for part in block[:3])
            material_id = f"M-{index:02d}"
            evidence = []
            for keyword in ["证书", "合同", "业绩", "社保", "发票", "截图", "承诺函", "名单"]:
                if keyword in standard:
                    evidence.append(keyword)
            if evidence:
                required_materials.append({
                    "id": material_id,
                    "name": f"{name}证明材料",
                    "purpose": name,
                    "source": OpenAIService._keyword_source(text, name),
                    "status": "unknown",
                })
                missing_materials.append({
                    "id": f"X-{index:02d}",
                    "name": f"{name}相关企业材料",
                    "used_by": [f"T-{index:02d}"],
                    "placeholder": f"〖待补充：{name}相关证明材料〗",
                })
                evidence_requirements.append({
                    "id": f"EV-{index:02d}",
                    "target": name,
                    "required_evidence": evidence[:4],
                    "validation_rule": "按招标文件评分标准逐项核验",
                    "source": OpenAIService._keyword_source(text, name),
                    "risk": "证明材料缺失或专业不匹配会影响得分",
                })

            item = {
                "id": f"T-{index:02d}",
                "name": name or f"技术评分项{index}",
                "score": score,
                "standard": OpenAIService._compact_text(standard, 140),
                "source": OpenAIService._keyword_source(text, name) or "评分办法",
                "writing_focus": "正文需逐条响应评分标准并引用证明材料",
                "evidence_requirements": evidence[:4],
                "easy_loss_points": ["未按评分标准逐项响应", "证明材料缺失或不一致"],
            }
            if re.search(r"报价|价格|商务|业绩|资信|信誉", name):
                business_items.append({**item, "id": f"B-{len(business_items) + 1:02d}"})
            else:
                technical_items.append(item)

        if not technical_items:
            technical_items.append({
                "id": "T-01",
                "name": "技术/服务/实施方案",
                "score": "",
                "standard": "按招标文件技术、服务或实施方案评审要求响应",
                "source": OpenAIService._keyword_source(text, "技术") or OpenAIService._keyword_source(text, "服务") or "评分办法/技术要求",
                "writing_focus": "围绕项目理解、实施方案、质量安全、进度保障、人员资源和服务响应逐项展开",
                "evidence_requirements": [],
                "easy_loss_points": ["响应不完整", "缺少针对性", "未对应评分标准"],
            })

        bid_structure = []
        for index, item in enumerate((bid_document_requirements.get("composition") or [])[:12], start=1):
            bid_structure.append({
                "id": f"S-{index:02d}",
                "parent_id": "",
                "title": item.get("title") or f"投标文件组成{index}",
                "purpose": "按招标文件投标文件格式/组成要求编制",
                "category": item.get("chapter_type") or "",
                "volume_id": item.get("volume_id") or "",
                "required": bool(item.get("required", True)),
                "fixed_format": bool(item.get("fixed_format")),
                "signature_required": bool(item.get("signature_required")),
                "attachment_required": bool(item.get("attachment_required")),
                "seal_required": bool(item.get("seal_required")),
                "price_related": bool(item.get("price_related")),
                "anonymity_sensitive": bool(item.get("anonymity_sensitive")),
                "source": item.get("source_ref") or OpenAIService._keyword_source(text, item.get("title") or "投标文件"),
            })
        if not bid_structure:
            bid_structure = [
                {"id": "S-01", "parent_id": "", "title": "投标函及投标函附录", "purpose": "正式响应招标要求", "category": "承诺", "required": True, "fixed_format": True, "signature_required": True, "attachment_required": False, "source": OpenAIService._keyword_source(text, "投标函")},
                {"id": "S-02", "parent_id": "", "title": "资格审查资料", "purpose": "证明投标资格", "category": "资格", "required": True, "fixed_format": False, "signature_required": True, "attachment_required": True, "source": OpenAIService._keyword_source(text, "资格")},
                {"id": "S-03", "parent_id": "", "title": "技术/服务/实施方案", "purpose": "响应技术、服务或实施方案评分项", "category": "技术/服务", "required": True, "fixed_format": False, "signature_required": False, "attachment_required": False, "source": OpenAIService._keyword_source(text, "技术") or OpenAIService._keyword_source(text, "服务")},
                {"id": "S-04", "parent_id": "", "title": "商务响应与报价文件", "purpose": "响应商务和报价要求", "category": "商务/报价", "required": True, "fixed_format": True, "signature_required": True, "attachment_required": True, "source": OpenAIService._keyword_source(text, "报价")},
            ]

        formal_review = [{
            "id": "E-01",
            "review_type": "形式评审",
            "requirement": "投标文件格式、签字盖章、递交方式需符合招标文件要求",
            "criterion": "格式完整且签章齐全",
            "required_materials": [],
            "risk": "格式或签章缺失可能导致否决",
            "target_chapters": ["投标函及投标函附录"],
            "source": OpenAIService._keyword_source(text, "形式评审"),
        }]
        qualification_review = [{
            "id": "E-02",
            "review_type": "资格评审",
            "requirement": "按招标文件提交企业资质、业绩、人员等资格证明",
            "criterion": "资格证明真实、有效、覆盖要求",
            "required_materials": [item["id"] for item in required_materials[:4]],
            "risk": "资格证明缺失或过期可能导致否决",
            "target_chapters": ["资格审查资料"],
            "source": OpenAIService._keyword_source(text, "资格评审"),
        }]
        responsiveness_review = [{
            "id": "E-03",
            "review_type": "响应性评审",
            "requirement": "服务期限、质量、报价、实质性条款需无偏离响应",
            "criterion": "未出现重大偏离",
            "required_materials": [],
            "risk": "实质性条款未响应可能导致否决",
            "target_chapters": ["技术/服务/实施方案", "商务响应与报价文件"],
            "source": OpenAIService._keyword_source(text, "响应性评审"),
        }]

        if not required_materials:
            required_materials.append({
                "id": "M-01",
                "name": "企业资格与评分证明材料",
                "purpose": "资格审查和评分佐证",
                "source": OpenAIService._keyword_source(text, "证明材料"),
                "status": "unknown",
            })
            missing_materials.append({
                "id": "X-01",
                "name": "企业资格与评分证明材料",
                "used_by": ["Q-01", "T-01"],
                "placeholder": "〖待补充：企业资质、业绩、人员、承诺等证明材料〗",
            })

        report = {
            "project": {
                "name": project_name,
                "number": project_number,
                "package_name": "",
                "package_or_lot": "",
                "purchaser": purchaser,
                "agency": OpenAIService._extract_labeled_value(text, ["代理机构", "招标代理"]),
                "procurement_method": OpenAIService._extract_labeled_value(text, ["采购方式", "招标方式"]),
                "project_type": "",
                "budget": budget,
                "maximum_price": budget,
                "funding_source": OpenAIService._extract_labeled_value(text, ["资金来源"]),
                "service_scope": OpenAIService._extract_labeled_value(text, ["服务范围", "采购内容", "招标范围"], 100),
                "service_period": service_period,
                "service_location": OpenAIService._extract_labeled_value(text, ["服务地点", "项目地点", "建设地点"]),
                "quality_requirements": OpenAIService._extract_labeled_value(text, ["质量要求", "服务质量"]),
                "bid_validity": OpenAIService._extract_labeled_value(text, ["投标有效期"]),
                "bid_bond": OpenAIService._extract_labeled_value(text, ["投标保证金"]),
                "performance_bond": OpenAIService._extract_labeled_value(text, ["履约担保", "履约保证金"]),
                "bid_deadline": deadline,
                "opening_time": OpenAIService._extract_labeled_value(text, ["开标时间"]),
                "submission_method": OpenAIService._extract_labeled_value(text, ["递交方式"]),
                "electronic_platform": OpenAIService._extract_labeled_value(text, ["电子交易平台", "电子招投标平台"]),
                "submission_requirements": OpenAIService._extract_labeled_value(text, ["递交要求", "投标文件递交", "电子投标"]),
                "signature_requirements": signature_req,
            },
            "bid_mode_recommendation": (
                "technical_service_plan"
                if (bid_document_requirements.get("selected_generation_target") or {}).get("target_title") and re.search(r"设计服务|工程设计|勘察设计|初步设计|施工图|设计成果|设计周期", text)
                else (
                    "service_plan"
                    if (bid_document_requirements.get("selected_generation_target") or {}).get("target_title") and re.search(r"服务方案|服务纲要|运维方案|咨询方案|服务承诺|响应时限|服务目标", text)
                    else (
                        "technical_only"
                        if (bid_document_requirements.get("selected_generation_target") or {}).get("target_title")
                        else "full_bid" if re.search(r"投标函|授权委托书|投标保证金|资格审查资料|报价文件|开标一览表", text) else "technical_only"
                    )
                )
            ),
            "source_refs": [
                {
                    "id": "SRC-01",
                    "location": "招标文件关键条款",
                    "excerpt": OpenAIService._compact_text(text[:240], 120),
                    "related_ids": ["S-01", "T-01", "E-01"],
                }
            ],
            "bid_document_requirements": bid_document_requirements,
            "volume_rules": [
                {
                    "id": "V-TECH",
                    "name": "技术标",
                    "scope": "技术、服务或实施方案与评分响应",
                    "separate_submission": bool(re.search(r"技术标.*单独|暗标|双盲", text)),
                    "price_allowed": not bool(re.search(r"技术.*不得.*报价|暗标|双盲", text)),
                    "anonymity_required": bool(re.search(r"暗标|双盲|匿名", text)),
                    "seal_signature_rule": signature_req,
                    "source": OpenAIService._keyword_source(text, "技术标"),
                },
                {
                    "id": "V-PRICE",
                    "name": "报价文件",
                    "scope": "报价表、费用明细和价格响应",
                    "separate_submission": bool(re.search(r"报价.*单独|价格.*单独", text)),
                    "price_allowed": True,
                    "anonymity_required": False,
                    "seal_signature_rule": signature_req,
                    "source": OpenAIService._keyword_source(text, "报价"),
                },
            ],
            "anonymity_rules": {
                "enabled": bool(re.search(r"暗标|双盲|匿名", text)),
                "scope": OpenAIService._extract_labeled_value(text, ["暗标", "双盲", "匿名"], 100),
                "forbidden_identifiers": ["企业名称", "人员姓名", "联系方式", "Logo", "商标"] if re.search(r"暗标|双盲|匿名", text) else [],
                "formatting_rules": [],
                "source": OpenAIService._keyword_source(text, "暗标") or OpenAIService._keyword_source(text, "双盲"),
            },
            "bid_structure": bid_structure,
            "formal_review_items": formal_review,
            "qualification_review_items": qualification_review,
            "responsiveness_review_items": responsiveness_review,
            "business_scoring_items": business_items[:8],
            "technical_scoring_items": technical_items[:8],
            "price_scoring_items": [{
                "id": "P-01",
                "name": "报价评分",
                "score": "",
                "logic": "按招标文件价格评分办法执行",
                "source": OpenAIService._keyword_source(text, "报价"),
                "risk": "报价口径、税费或格式错误会影响评审",
            }] if "报价" in text or "价格" in text else [],
            "price_rules": {
                "quote_method": OpenAIService._extract_labeled_value(text, ["报价方式", "报价要求"]),
                "currency": "人民币" if "人民币" in text else "",
                "maximum_price_rule": budget,
                "abnormally_low_price_rule": OpenAIService._extract_labeled_value(text, ["异常低价", "低于成本"]),
                "separate_price_volume_required": bool(re.search(r"报价.*单独|价格.*单独", text)),
                "price_forbidden_in_other_volumes": bool(re.search(r"技术.*不得.*报价|商务.*不得.*报价|价格.*不得.*技术", text)),
                "tax_requirement": "按招标文件要求含税/不含税报价" if re.search(r"含税|税率|不含税", text) else "",
                "decimal_places": OpenAIService._extract_labeled_value(text, ["小数位", "精确到"]),
                "uniqueness_requirement": "投标报价应唯一" if "唯一" in text and "报价" in text else "",
                "form_requirements": "按开标一览表或报价表格式填写" if re.search(r"开标一览表|报价表", text) else "",
                "arithmetic_correction_rule": OpenAIService._extract_labeled_value(text, ["算术错误", "修正"]),
                "missing_item_rule": OpenAIService._extract_labeled_value(text, ["缺漏项", "漏项"]),
                "prohibited_format_changes": ["不得擅自修改固定格式"] if re.search(r"不得.*修改|格式.*不得", text) else [],
                "source_ref": "SRC-01",
            },
            "qualification_requirements": [{
                "id": "Q-01",
                "name": "投标人资格要求",
                "requirement": "满足招标文件资格审查要求并提供有效证明",
                "source": OpenAIService._keyword_source(text, "资格"),
                "required_materials": [item["id"] for item in required_materials[:4]],
            }],
            "formal_response_requirements": [{
                "id": "F-01",
                "name": "投标文件格式与签章",
                "requirement": "使用招标文件规定格式，按要求签字盖章",
                "source": OpenAIService._keyword_source(text, "签字"),
                "fixed_format": True,
                "signature_required": bool(signature_req),
                "attachment_required": False,
            }],
            "mandatory_clauses": [{
                "id": "C-01",
                "clause": "服务期限、质量、报价、资格及实质性条款需逐项响应",
                "source": OpenAIService._keyword_source(text, "实质性"),
                "response_strategy": "在目录和正文中设置专门响应章节并避免负偏离",
            }],
            "rejection_risks": [{
                "id": "R-01",
                "risk": "签字盖章、资格证明、实质性响应或报价格式缺失可能导致否决",
                "source": OpenAIService._keyword_source(text, "否决") or OpenAIService._keyword_source(text, "废标"),
                "mitigation": "生成正文后执行合规审校，逐项补齐材料和格式",
            }],
            "fixed_format_forms": [{
                "id": "FF-01",
                "name": "投标函/报价表等固定格式",
                "source": OpenAIService._keyword_source(text, "格式"),
                "required_columns": [],
                "fixed_text": "",
                "fill_rules": "按招标文件模板填写，不擅自改动格式",
            }],
            "signature_requirements": [{
                "id": "SIG-01",
                "target": "投标函、授权委托书、报价表及承诺文件",
                "signer": "法定代表人或授权代表",
                "seal": "按格式要求加盖投标人公章",
                "source": OpenAIService._keyword_source(text, "盖章"),
                "risk": "漏签漏盖可能导致形式评审不通过",
            }],
            "evidence_chain_requirements": evidence_requirements[:8],
            "required_materials": required_materials[:8],
            "missing_company_materials": missing_materials[:8],
            "generation_warnings": [],
        }
        if reason:
            report["rejection_risks"].append({
                "id": "R-02",
                "risk": f"结构化模型输出未完整返回，已启用文本兜底解析：{OpenAIService._compact_text(reason, 80)}",
                "source": "系统解析状态",
                "mitigation": "可换用更快模型后重跑标准解析以获得更完整映射",
            })
            report["generation_warnings"].append({
                "id": "W-01",
                "warning": f"结构化模型输出未完整返回，已启用文本兜底解析：{OpenAIService._compact_text(reason, 80)}",
                "severity": "warning",
                "related_ids": ["R-02"],
            })
        report["response_matrix"] = OpenAIService._fallback_response_matrix(report)
        return AnalysisReport.model_validate(report).model_dump(mode="json")

    @staticmethod
    def _fallback_response_matrix(analysis_report: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """基于 AnalysisReport 稳定生成响应矩阵兜底结果。"""
        report = analysis_report or {}
        items: list[dict[str, Any]] = []

        def append_item(source_type: str, source_id: str, summary: str, materials=None, risks=None, blocking=False, priority="normal", source_refs=None):
            if not source_id:
                return
            matrix_id = f"RM-{len(items) + 1:02d}"
            items.append({
                "id": matrix_id,
                "source_item_id": source_id,
                "source_type": source_type,
                "requirement_summary": OpenAIService._compact_text(summary, 80),
                "response_strategy": "在目录和正文中设置对应章节，逐项响应并保留材料/页码占位",
                "target_chapter_ids": [],
                "required_material_ids": list(materials or []),
                "risk_ids": list(risks or []),
                "source_refs": list(source_refs or []),
                "priority": priority,
                "status": "pending",
                "blocking": blocking,
            })

        bid_doc = report.get("bid_document_requirements") or {}
        selected_target = bid_doc.get("selected_generation_target") or {}
        selected_id = selected_target.get("parent_composition_id") or selected_target.get("target_id")
        scheme_only = selected_target.get("generation_scope") == "scheme_section_only" and selected_id
        for item in (bid_doc.get("composition") or [])[:16]:
            is_selected_composition = bool(selected_id and item.get("id") == selected_id)
            is_required_full_bid_item = bool(item.get("required", True)) and item.get("applicability") != "not_applicable"
            source_type = "selected_generation_target" if is_selected_composition else ("excluded_full_bid_section" if scheme_only else "bid_document_composition")
            append_item(
                source_type,
                item.get("id"),
                f"投标文件组成要求：{item.get('title') or ''}",
                [],
                [],
                is_required_full_bid_item if not scheme_only else is_selected_composition,
                "high" if is_selected_composition or (is_required_full_bid_item and not scheme_only) else "low",
                [item.get("source_ref")] if item.get("source_ref") else [],
            )
        for target_item in (selected_target.get("base_outline_items") or [])[:20]:
            append_item(
                "selected_outline_item",
                target_item.get("id") or f"BD-TARGET-{len(items)+1:02d}",
                f"选中生成对象目录项：{target_item.get('title') or ''}",
                [],
                [],
                True,
                "high",
                [target_item.get("source_ref")] if target_item.get("source_ref") else [],
            )
        for item in (bid_doc.get("scheme_or_technical_outline_requirements") or [])[:16]:
            append_item(
                "bid_scheme_outline",
                item.get("id"),
                f"方案纲要要求：{item.get('title') or ''}",
                [],
                [],
                bool(item.get("required", True)),
                "high",
                [item.get("source_ref")] if item.get("source_ref") else [],
            )
        for item in (bid_doc.get("fixed_forms") or [])[:12]:
            append_item(
                "bid_fixed_form",
                item.get("id"),
                f"固定格式要求：{item.get('form_name') or ''}",
                [],
                [],
                True,
                "high",
                [item.get("source_ref")] if item.get("source_ref") else [],
            )

        for key, source_type in (
            ("technical_scoring_items", "scoring"),
            ("business_scoring_items", "scoring"),
            ("price_scoring_items", "price"),
        ):
            for item in (report.get(key) or [])[:8]:
                append_item(
                    source_type,
                    item.get("id"),
                    item.get("standard") or item.get("logic") or item.get("name") or "",
                    item.get("evidence_requirements") or [],
                    [],
                    source_type == "price",
                    "high" if source_type == "price" or item.get("score") else "normal",
                    [item.get("source")] if item.get("source") else [],
                )

        for key in ("formal_review_items", "qualification_review_items", "responsiveness_review_items"):
            for item in (report.get(key) or [])[:8]:
                append_item(
                    "review",
                    item.get("id"),
                    item.get("requirement") or item.get("criterion") or "",
                    item.get("required_materials") or [],
                    [],
                    bool(item.get("invalid_if_missing")),
                    "high" if item.get("invalid_if_missing") else "normal",
                    [item.get("source")] if item.get("source") else [],
                )

        for item in (report.get("mandatory_clauses") or [])[:8]:
            append_item("mandatory", item.get("id"), item.get("clause") or "", [], [], True, "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("rejection_risks") or [])[:8]:
            append_item("risk", item.get("id"), item.get("risk") or "", [], [item.get("id")], bool(item.get("blocking", True)), "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("required_materials") or [])[:8]:
            append_item("material", item.get("id"), item.get("name") or item.get("purpose") or "", [item.get("id")], [], item.get("status") == "missing", "high" if item.get("status") == "missing" else "normal", [item.get("source")] if item.get("source") else [])
        for item in (report.get("fixed_format_forms") or [])[:8]:
            append_item("format", item.get("id"), item.get("name") or item.get("fill_rules") or "", [], [], True, "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("signature_requirements") or [])[:8]:
            append_item("signature", item.get("id"), item.get("target") or item.get("seal") or "", [], [], True, "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("evidence_chain_requirements") or [])[:8]:
            append_item("evidence", item.get("id"), item.get("target") or item.get("validation_rule") or "", [], [], False, "normal", [item.get("source")] if item.get("source") else [])

        high_risk_ids = [item["id"] for item in items if item.get("priority") == "high" or item.get("blocking")]
        return ResponseMatrix.model_validate({
            "items": items,
            "uncovered_ids": [item.get("source_item_id") for item in items if item.get("source_item_id")],
            "high_risk_ids": high_risk_ids,
            "coverage_summary": f"已建立 {len(items)} 条响应矩阵，待目录和正文阶段逐项覆盖。",
        }).model_dump(mode="json")

    @staticmethod
    def fallback_overview(file_content: str) -> str:
        """本地提取项目概述，用于安全 smoke 或模型异常兜底。"""
        report = OpenAIService._fallback_analysis_report(file_content)
        project = report.get("project", {})
        lines = [
            f"项目名称：{project.get('name') or '待模型解析'}",
            f"项目编号：{project.get('number') or '待模型解析'}",
            f"招标/采购人：{project.get('purchaser') or '待模型解析'}",
            f"预算/限价：{project.get('budget') or '以招标文件为准'}",
            f"服务期限：{project.get('service_period') or '以招标文件为准'}",
            f"递交截止：{project.get('bid_deadline') or '以招标文件为准'}",
            "项目概述：本项目需按招标文件要求完成资格、商务、报价和技术响应，正文应围绕评分项、实质性条款、材料清单和签字盖章要求逐项展开。",
        ]
        return "\n".join(lines)

    @staticmethod
    def fallback_requirements(file_content: str) -> str:
        """本地提取技术评分要求，用于安全 smoke 或模型异常兜底。"""
        report = OpenAIService._fallback_analysis_report(file_content)
        items = report.get("technical_scoring_items") or []
        if not items:
            return "【评分项名称】：技术服务方案\n【权重/分值】：以招标文件为准\n【评分标准】：围绕项目理解、实施方案、质量安全、进度保障、人员组织和服务响应逐项编写。\n【数据来源】：技术评审条款"
        blocks = []
        for item in items[:8]:
            blocks.append(
                "\n".join([
                    f"【评分项名称】：{item.get('name') or '技术评分项'}",
                    f"【权重/分值】：{item.get('score') or '以招标文件为准'}",
                    f"【评分标准】：{item.get('standard') or '按招标文件评分标准响应'}",
                    f"【数据来源】：{item.get('source') or '评分办法'}",
                ])
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _clean_outline_requirement_title(title: Any) -> str:
        """清理招标文件方案纲要标题，去掉编号和末尾标点。"""
        text = OpenAIService._compact_text(str(title or ""), 80)
        text = re.sub(r"^[（(]?\s*(?:[一二三四五六七八九十]+|\d{1,2})\s*[）)]?[、.．]\s*", "", text)
        return text.strip("；;，,。 .")

    @staticmethod
    def _canonical_design_service_outline_items() -> list[dict[str, Any]]:
        """工程设计服务项目常见的服务纲要七项。"""
        titles = [
            "服务范围、服务内容",
            "服务工作目标",
            "服务机构设置（框图）、岗位职责",
            "服务方案",
            "拟投入的服务人员",
            "沟通技巧和方法",
            "质量承诺及措施",
        ]
        return [
            {
                "id": f"BD-SP-{index:02d}",
                "parent_title": "服务方案",
                "order": index,
                "title": title,
                "required": True,
                "allow_expand": True,
                "source_ref": "服务纲要",
                "target_chapter_hint": "",
            }
            for index, title in enumerate(titles, start=1)
        ]

    @staticmethod
    def _infer_canonical_design_service_outline(text: str) -> list[dict[str, Any]]:
        """当 Word 提取破坏换行/编号时，用关键词组合识别服务纲要七项。"""
        compact = re.sub(r"\s+", "", str(text or ""))
        if not re.search(r"服务纲要|服务方案", compact):
            return []
        required_keywords = [
            "服务范围",
            "服务内容",
            "服务工作目标",
            "服务机构设置",
            "岗位职责",
            "拟投入",
            "服务人员",
            "沟通技巧",
            "质量承诺",
            "措施",
        ]
        hit_count = sum(1 for keyword in required_keywords if keyword in compact)
        if hit_count >= 7:
            return OpenAIService._canonical_design_service_outline_items()
        design_service_signal = bool(re.search(r"工程设计|设计服务|初步设计|施工图设计|安全消防|效果图", compact))
        if design_service_signal and hit_count >= 5:
            return OpenAIService._canonical_design_service_outline_items()
        return []

    @staticmethod
    def _collect_scheme_outline_items(report: Dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """返回真正应展开为一级目录的方案纲要子项，不包含“服务方案”这类包装标题。"""
        report = report or {}
        bid_doc = report.get("bid_document_requirements") or {}
        selected_target = bid_doc.get("selected_generation_target") or {}
        target_title = OpenAIService._clean_outline_requirement_title(selected_target.get("target_title"))
        raw_items = list(selected_target.get("base_outline_items") or [])
        raw_items.extend(list(bid_doc.get("scheme_or_technical_outline_requirements") or []))
        raw_titles = [
            OpenAIService._clean_outline_requirement_title((raw_item or {}).get("title"))
            for raw_item in raw_items
        ]
        has_multi_outline_items = len({title for title in raw_titles if title}) > 1

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        wrapper_titles = {"服务方案", "技术方案", "设计方案", "实施方案", "施工组织设计", "供货方案", "售后服务方案"}
        for raw_item in raw_items:
            title = OpenAIService._clean_outline_requirement_title((raw_item or {}).get("title"))
            if not title:
                continue
            if not has_multi_outline_items and target_title and title == target_title:
                continue
            if not has_multi_outline_items and title in wrapper_titles:
                continue
            if title in seen:
                continue
            item = dict(raw_item or {})
            item["title"] = title
            item.setdefault("id", f"BD-SP-{len(items) + 1:02d}")
            item.setdefault("order", len(items) + 1)
            items.append(item)
            seen.add(title)
        return items

    @staticmethod
    def _build_scheme_outline_nodes(
        report: Dict[str, Any] | None = None,
        response_matrix: Dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """把服务/技术方案的“应包括”条目确定性转换为一级目录。"""
        report = report or {}
        response_matrix = response_matrix or report.get("response_matrix") or {}
        technical_ids = [item.get("id") for item in report.get("technical_scoring_items", []) if item.get("id")]
        requirement_ids: list[str] = []
        for key in ("formal_review_items", "qualification_review_items", "responsiveness_review_items", "qualification_requirements", "formal_response_requirements", "mandatory_clauses"):
            requirement_ids.extend([item.get("id") for item in report.get(key, []) if item.get("id")])
        material_ids = [item.get("id") for item in report.get("required_materials", []) if item.get("id")]
        material_ids.extend([item.get("id") for item in report.get("missing_company_materials", []) if item.get("id")])
        risk_ids = [item.get("id") for item in report.get("rejection_risks", []) if item.get("id")]
        matrix_ids = [item.get("id") for item in (response_matrix.get("items") or []) if item.get("id")]

        nodes: list[dict[str, Any]] = []
        for index, item in enumerate(OpenAIService._collect_scheme_outline_items(report)[:20], start=1):
            title = item.get("title") or f"方案要求{index}"
            blocks = ["paragraph"]
            if re.search(r"机构|组织|框图|岗位|职责", title):
                blocks = ["org_chart", "table"]
            elif re.search(r"人员|团队|拟投入", title):
                blocks = ["table"]
            elif re.search(r"承诺|质量", title):
                blocks = ["commitment_letter", "table"]
            elif re.search(r"计划|清单|表", title):
                blocks = ["table"]
            nodes.append({
                "id": str(index),
                "title": title,
                "description": "按招标文件服务纲要/方案要求原文逐项响应；该条目是本次方案分册的一级目录，不得被“服务方案”包装标题替代。",
                "volume_id": "V-TECH",
                "chapter_type": "service_plan",
                "source_type": "selected_outline_item",
                "fixed_format_sensitive": False,
                "price_sensitive": False,
                "anonymity_sensitive": False,
                "enterprise_required": bool(re.search(r"人员|机构|岗位|职责|材料|资质|业绩|证明", title)),
                "asset_required": any(block in {"org_chart", "workflow_chart", "image"} for block in blocks),
                "expected_depth": "medium",
                "expected_word_count": 1200,
                "expected_blocks": blocks,
                "scoring_item_ids": technical_ids[:8],
                "requirement_ids": requirement_ids[:8],
                "risk_ids": risk_ids[:4],
                "material_ids": material_ids[:8] if re.search(r"人员|机构|岗位|职责|资质|业绩|证明", title) else [],
                "response_matrix_ids": matrix_ids[:8],
                "children": [],
            })
        return nodes

    @staticmethod
    def _fallback_outline(
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
    ) -> Dict[str, Any]:
        """目录生成失败时的保底目录，保持跨行业通用，不再强行套用单一行业模板。"""
        report = analysis_report or {}
        mode = str(bid_mode or report.get("bid_mode_recommendation") or "").strip()
        blob = json.dumps(report, ensure_ascii=False) + "\n" + mode
        is_full_bid = mode == "full_bid"
        is_price_only = mode == "price_volume"
        is_qualification_only = mode == "qualification_volume"
        is_business_volume = mode in {"business_volume", "business_technical"}
        is_service_or_technical = mode in {"technical_only", "technical_service_plan", "service_plan", "construction_plan", "goods_supply_plan", ""}

        response_matrix = report.get("response_matrix") or OpenAIService._fallback_response_matrix(report)
        technical_ids = [item.get("id") for item in report.get("technical_scoring_items", []) if item.get("id")]
        business_ids = [item.get("id") for item in report.get("business_scoring_items", []) if item.get("id")]
        price_ids = [item.get("id") for item in report.get("price_scoring_items", []) if item.get("id")]
        material_ids = [item.get("id") for item in report.get("required_materials", []) if item.get("id")]
        material_ids.extend([item.get("id") for item in report.get("missing_company_materials", []) if item.get("id")])
        material_ids.extend([item.get("id") for item in report.get("evidence_chain_requirements", []) if item.get("id")])
        risk_ids = [item.get("id") for item in report.get("rejection_risks", []) if item.get("id")]
        requirement_ids: list[str] = []
        for key in ("formal_review_items", "qualification_review_items", "responsiveness_review_items", "qualification_requirements", "formal_response_requirements", "mandatory_clauses"):
            requirement_ids.extend([item.get("id") for item in report.get(key, []) if item.get("id")])

        bid_doc = report.get("bid_document_requirements") or {}
        bid_composition = [item for item in (bid_doc.get("composition") or []) if item.get("title")]
        scheme_requirements = [item for item in (bid_doc.get("scheme_or_technical_outline_requirements") or []) if item.get("title")]
        selected_target = bid_doc.get("selected_generation_target") or {}
        scheme_outline_items = OpenAIService._collect_scheme_outline_items(report)
        selected_base_items = scheme_outline_items

        def node(id_, title, desc, *, volume="V-TECH", ctype="technical", fixed=False, price=False, children=None, scoring=None, req=None, mats=None, blocks=None):
            return {
                "id": id_,
                "title": title,
                "description": desc,
                "volume_id": volume,
                "chapter_type": ctype,
                "source_type": "fallback",
                "fixed_format_sensitive": fixed,
                "price_sensitive": price,
                "anonymity_sensitive": False,
                "expected_depth": "medium",
                "expected_word_count": 1200,
                "expected_blocks": blocks or ["paragraph"],
                "enterprise_required": bool(mats),
                "asset_required": any(b in {"image", "org_chart", "workflow_chart"} for b in (blocks or [])),
                "scoring_item_ids": scoring or [],
                "requirement_ids": req or [],
                "risk_ids": risk_ids[:4],
                "material_ids": mats or [],
                "response_matrix_ids": [],
                "children": children or [],
            }

        if is_full_bid and bid_composition:
            outline = []
            for idx, item in enumerate(bid_composition[:16], start=1):
                ctype = item.get("chapter_type") or "other"
                volume = item.get("volume_id") or ("V-TECH" if ctype in {"technical", "service_plan", "construction_plan", "goods_supply"} else "V-BIZ")
                children = []
                if volume == "V-TECH" and scheme_outline_items:
                    for j, req_item in enumerate(scheme_outline_items[:12], start=1):
                        children.append(node(
                            f"{idx}.{j}",
                            req_item.get("title") or f"方案要求{j}",
                            "按招标文件投标文件格式中的方案纲要逐项响应；可结合评分项和样例风格扩展，但不得漏项。",
                            volume=volume,
                            ctype="technical",
                            scoring=technical_ids[:8],
                            req=requirement_ids[:8],
                        ))
                outline.append(node(
                    str(idx),
                    item.get("title") or f"投标文件组成{idx}",
                    "按招标文件“投标文件/投标文件格式/投标文件组成”要求编制；固定格式、签章、附件和页码要求不得擅自修改。",
                    volume=volume,
                    ctype=ctype,
                    fixed=bool(item.get("fixed_format")),
                    price=bool(item.get("price_related")),
                    children=children,
                    scoring=(price_ids if item.get("price_related") else (business_ids if volume in {"V-BIZ", "V-QUAL"} else technical_ids))[:8],
                    req=requirement_ids[:10],
                    mats=material_ids[:10] if bool(item.get("attachment_required")) or volume == "V-QUAL" else [],
                    blocks=["table"] if bool(item.get("fixed_format")) else ["paragraph"],
                ))
            return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": "已按招标文件投标文件格式/组成要求生成完整投标文件目录。"}

        if is_price_only:
            outline = [node("1", "报价文件", "按招标文件报价方式、固定格式、费用口径和签字盖章要求填写；未提供报价时保留待补占位。", volume="V-PRICE", ctype="price", fixed=True, price=True, scoring=price_ids, req=requirement_ids[:8], mats=material_ids[:8], children=[
                node("1.1", "报价规则响应", "说明报价口径、税费、小数位、唯一报价、最高限价和缺漏项规则。", volume="V-PRICE", ctype="price", price=True),
                node("1.2", "报价表及费用明细", "保留招标文件固定表格结构，使用待补占位，不生成具体金额。", volume="V-PRICE", ctype="price", fixed=True, price=True, blocks=["table"]),
            ])]
            return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": response_matrix.get("coverage_summary", "")}

        if is_qualification_only:
            outline = [node("1", "资格审查资料", "按资格评审、资质、业绩、人员、信誉、财务和证据链要求组卷。", volume="V-QUAL", ctype="qualification", fixed=True, mats=material_ids[:10], req=requirement_ids[:10], children=[
                node("1.1", "资格证明材料清单", "列明营业执照、资质证书、业绩、人员、财务、信誉等证明材料及页码占位。", volume="V-QUAL", ctype="material", mats=material_ids[:10], blocks=["table"]),
                node("1.2", "资格响应与承诺", "对资格硬条件和禁止投标情形逐项响应。", volume="V-QUAL", ctype="qualification"),
            ])]
            return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": response_matrix.get("coverage_summary", "")}

        if is_service_or_technical and not is_full_bid and not is_business_volume:
            scheme_nodes = OpenAIService._build_scheme_outline_nodes(report, response_matrix)
            if scheme_nodes:
                outline = scheme_nodes
                return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": "已按 selected_generation_target/方案纲要生成方案分册目录，商务、报价、资格等完整投标文件章节仅作为审校排除项。"}

            if technical_ids and report.get("technical_scoring_items"):
                outline = []
                for idx, score_item in enumerate((report.get("technical_scoring_items") or [])[:12], start=1):
                    title = score_item.get("name") or f"技术评分响应{idx}"
                    outline.append(node(
                        str(idx),
                        title,
                        "招标文件未给出更细的方案子目录，按第三章技术/服务详细评分项生成目录主线。",
                        volume="V-TECH",
                        ctype="technical",
                        scoring=[score_item.get("id")] if score_item.get("id") else technical_ids[:8],
                        req=requirement_ids[:8],
                        blocks=["paragraph", "table"] if re.search(r"进度|计划|文档|管理", title) else ["paragraph"],
                    ))
                return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": "招标文件未给出明确方案子项，已按技术/服务评分项生成方案目录。"}

            outline = prompt_manager.get_generic_service_plan_outline_template()
            # 尝试把解析出的 ID 挂到通用模板上，便于后续正文和审校追踪。
            for item in outline:
                item.setdefault("scoring_item_ids", [])
                item.setdefault("requirement_ids", [])
                item.setdefault("risk_ids", [])
                item.setdefault("material_ids", [])
            if outline:
                outline[0]["requirement_ids"] = requirement_ids[:8]
                if len(outline) > 3:
                    outline[3]["scoring_item_ids"] = technical_ids[:8]
                    outline[3]["risk_ids"] = risk_ids[:4]
                if len(outline) > 4:
                    outline[4]["material_ids"] = material_ids[:8]
                if len(outline) > 6:
                    outline[6]["scoring_item_ids"] = technical_ids[:8]
            return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": response_matrix.get("coverage_summary", "")}

        outline = [
            node("1", "投标函及商务资格响应", "按招标文件格式完成投标函、授权、承诺、资格审查、商务响应和签字盖章。", volume="V-BIZ", ctype="business", fixed=True, scoring=business_ids[:8], req=requirement_ids[:10], mats=material_ids[:10], children=[
                node("1.1", "投标函及承诺文件", "保留固定格式、签字盖章、投标有效期、服务期限/工期等关键字段。", volume="V-BIZ", ctype="form", fixed=True),
                node("1.2", "资格审查资料", "列明企业资质、业绩、人员、财务、信誉和证据链材料。", volume="V-BIZ", ctype="qualification", mats=material_ids[:10], blocks=["table"]),
            ]),
            node("2", "技术/服务/实施方案", "围绕项目理解、实施方法、组织安排、进度质量、安全风险、交付成果和服务保障展开。", volume="V-TECH", ctype="technical", scoring=technical_ids[:10], req=requirement_ids[:8], mats=material_ids[:6], children=[
                node("2.1", "项目理解与需求分析", "结合招标范围和评分标准说明项目目标、边界、重难点和响应策略。", volume="V-TECH", ctype="technical"),
                node("2.2", "总体实施方案", "描述组织架构、工作流程、进度计划、质量安全、风险控制和成果交付。", volume="V-TECH", ctype="technical"),
                node("2.3", "评分项逐项响应", "按照评分项逐条写明响应措施、支撑材料和易失分控制。", volume="V-TECH", ctype="review", scoring=technical_ids[:10]),
            ]),
            node("3", "材料索引与导出前自检", "汇总待补材料、证据链、页码占位、签章、固定格式、报价隔离和暗标风险。", volume="V-CHECK", ctype="review", req=requirement_ids[:10], mats=material_ids[:10], children=[
                node("3.1", "证明材料与页码索引", "汇总材料清单、证明用途、核验要点和页码占位。", volume="V-CHECK", ctype="material", mats=material_ids[:10], blocks=["table"]),
                node("3.2", "合规自检", "检查覆盖率、缺失材料、签字盖章、固定格式、报价隔离和暗标规则。", volume="V-CHECK", ctype="review"),
            ]),
        ]
        if is_full_bid or report.get("price_rules", {}).get("quote_method") or price_ids:
            outline.append(node("4", "报价文件", "按报价规则、固定表格和费用口径填写报价文件；没有报价数据时保留待补占位。", volume="V-PRICE", ctype="price", fixed=True, price=True, scoring=price_ids[:5], children=[
                node("4.1", "报价规则响应", "说明报价口径、税费、小数位、唯一报价和费用范围。", volume="V-PRICE", ctype="price", price=True),
                node("4.2", "报价表及费用明细", "保留固定表格结构并使用待补占位。", volume="V-PRICE", ctype="price", fixed=True, price=True, blocks=["table"]),
            ]))
        return {"outline": outline, "response_matrix": response_matrix, "coverage_summary": response_matrix.get("coverage_summary", "")}

    @staticmethod
    def _count_analysis_items(analysis_report: Dict[str, Any] | None) -> int:
        """按已解析出的评分、审查、风险和材料数量估算目录颗粒度。"""
        report = analysis_report or {}
        keys = (
            "technical_scoring_items",
            "business_scoring_items",
            "price_scoring_items",
            "formal_review_items",
            "qualification_review_items",
            "responsiveness_review_items",
            "qualification_requirements",
            "formal_response_requirements",
            "mandatory_clauses",
            "rejection_risks",
            "required_materials",
            "missing_company_materials",
        )
        return sum(len(report.get(key) or []) for key in keys)

    @staticmethod
    def _allocate_leaf_distribution(total_leaf_nodes: int, weights: list[int]) -> list[int]:
        """按确定性权重分配叶子节点，避免随机重点章节导致生成结果漂移。"""
        if not weights:
            return []

        total_weight = max(sum(weights), 1)
        allocated = [max(2, round(total_leaf_nodes * weight / total_weight)) for weight in weights]
        diff = total_leaf_nodes - sum(allocated)
        cursor = 0
        while diff != 0 and allocated:
            index = cursor % len(allocated)
            if diff > 0:
                allocated[index] += 1
                diff -= 1
            elif allocated[index] > 2:
                allocated[index] -= 1
                diff += 1
            cursor += 1
            if cursor > len(allocated) * 20:
                break
        return allocated

    @staticmethod
    def _split_leaf_count(leaf_count: int, level2_count: int) -> list[int]:
        """把一级章节叶子节点稳定分摊给二级章节。"""
        level2_count = max(1, level2_count)
        base = leaf_count // level2_count
        extra = leaf_count % level2_count
        return [base + (1 if index < extra else 0) for index in range(level2_count)]

    @staticmethod
    def _build_nodes_distribution(
        level_l1: list[dict],
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
    ) -> dict:
        """基于评分项/审查项/风险项确定目录规模，不再使用固定十万字和随机重点章节。"""
        level1_count = len(level_l1)
        if level1_count <= 0:
            return {"level2_nodes": [], "leaf_nodes": [], "leaf_per_level2": []}

        item_count = OpenAIService._count_analysis_items(analysis_report)
        full_bid = bid_mode == "full_bid" or (analysis_report or {}).get("bid_mode_recommendation") == "full_bid"
        base_leaf_nodes = 30 if full_bid else 18
        total_leaf_nodes = max(base_leaf_nodes, level1_count * 3, item_count * 2)
        total_leaf_nodes = min(total_leaf_nodes, 72 if full_bid else 48)

        weights: list[int] = []
        for node in level_l1:
            title = str(node.get("new_title") or node.get("title") or "")
            mapped_count = (
                len(node.get("scoring_item_ids") or []) * 3
                + len(node.get("requirement_ids") or []) * 2
                + len(node.get("risk_ids") or []) * 2
                + len(node.get("material_ids") or [])
            )
            keyword_weight = 0
            if full_bid and any(keyword in title for keyword in ("资格", "商务", "报价", "投标函", "承诺", "附件", "自检")):
                keyword_weight += 2
            if any(keyword in title for keyword in ("技术", "方案", "实施", "服务", "评分", "响应")):
                keyword_weight += 2
            weights.append(max(1, mapped_count + keyword_weight + 1))

        leaf_nodes = OpenAIService._allocate_leaf_distribution(total_leaf_nodes, weights)
        level2_nodes: list[int] = []
        leaf_per_level2: list[list[int]] = []
        for leaf_count in leaf_nodes:
            level2_count = min(6, max(2, round(leaf_count / 3)))
            level2_nodes.append(level2_count)
            leaf_per_level2.append(OpenAIService._split_leaf_count(leaf_count, level2_count))

        return {
            "level2_nodes": level2_nodes,
            "leaf_nodes": leaf_nodes,
            "leaf_per_level2": leaf_per_level2,
        }

    @staticmethod
    def _fallback_chapter_content(
        chapter: dict,
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        missing_materials: list | None = None,
    ) -> str:
        """正文生成失败时的保底章节内容，跨行业通用，不套用固定行业或固定周期。"""
        title = chapter.get("title") or "当前章节"
        description = chapter.get("description") or "按招标文件要求编写。"
        project = (analysis_report or {}).get("project", {})
        project_name = project.get("name") or "以招标文件为准"
        tenderer = project.get("purchaser") or "招标人"
        scope = project.get("service_scope") or "〖以招标文件要求为准〗"
        period = project.get("service_period") or "〖以招标文件要求为准〗"
        location = project.get("service_location") or "〖以招标文件要求为准〗"
        quality = project.get("quality_requirements") or "〖以招标文件要求为准〗"
        missing = missing_materials or (analysis_report or {}).get("missing_company_materials", [])
        missing_lines = "\n".join(
            f"- {item.get('placeholder') or ('〖待补充：' + (item.get('name') or '相关证明材料') + '〗')}"
            for item in missing[:8]
        ) or "- 〖待确认：企业资质、业绩、人员、设备、软件、图片、证书、签章等材料是否已提供〗"

        schedule_texts: list[str] = []
        for key in ("mandatory_clauses", "responsiveness_review_items"):
            for item in (analysis_report or {}).get(key, []) or []:
                raw = " ".join(str(item.get(k, "")) for k in ("clause", "requirement", "criterion", "response_strategy"))
                if any(word in raw for word in ("期限", "工期", "进度", "交付", "完成", "响应", "周期", "日", "天")):
                    schedule_texts.append(OpenAIService._compact_text(raw, 160))
        schedule_text = "；".join(dict.fromkeys([x for x in schedule_texts if x])) or "按招标文件规定的进度、工期、交付周期或服务响应时限执行。"

        if any(keyword in title for keyword in ("范围", "内容", "需求理解", "项目理解")):
            return (
                f"本节围绕{project_name}的招标要求进行响应。项目范围、服务/供货/施工/实施内容以招标文件为准，当前识别范围为：{scope}。"
                f"项目实施地点为{location}，服务期限或履约期限为{period}。\n\n"
                "我公司将以招标文件、合同条款、技术标准、服务标准和招标人管理要求为依据，明确工作边界、交付成果、验收口径和协同接口，确保投标响应不遗漏、不偏离、不夸大。"
            )
        if any(keyword in title for keyword in ("进度", "工期", "交付周期", "响应时限")):
            return (
                f"我公司承诺严格满足招标文件关于进度、工期、交付周期和响应时限的要求：{schedule_text}\n\n"
                "表 进度计划与控制要点\n"
                "| 序号 | 阶段/事项 | 主要工作内容 | 时间要求 | 控制措施 |\n|---|---|---|---|---|\n"
                "| 1 | 启动准备 | 接收任务、确认需求、配置人员和资源 | 〖以招标文件要求为准〗 | 建立任务台账和责任分工 |\n"
                "| 2 | 过程实施 | 按工作计划完成服务、供货、施工或技术实施 | 〖以招标文件要求为准〗 | 周期检查、偏差预警、资源调配 |\n"
                "| 3 | 成果交付 | 提交成果文件、货物、服务报告或验收资料 | 〖以招标文件要求为准〗 | 内部复核后提交招标人确认 |\n"
                "| 4 | 整改闭环 | 根据审查、验收或反馈意见完成整改 | 〖以招标文件要求为准〗 | 建立问题清单并闭环销项 |\n\n"
                f"承诺书\n致：{tenderer}\n我公司郑重承诺严格执行招标文件规定的进度、工期、交付周期和服务响应要求，并接受招标文件及合同约定的考核。\n\n投标人：〖待补充：投标人名称〗\n日期：{{bid_date}}"
            )
        if any(keyword in title for keyword in ("组织", "机构", "岗位", "职责")):
            return (
                "〖插入图片：项目组织机构图〗\n\n"
                "我公司将根据项目特点设置项目负责人、质量管理、进度管理、资料管理、专业实施或服务人员等岗位，形成职责清晰、接口明确、协同高效的项目组织体系。各岗位人员信息、证书、社保、劳动合同等证明材料如未提供，应在组卷前补齐：\n"
                f"{missing_lines}"
            )
        if any(keyword in title for keyword in ("质量", "验收", "违约", "保障")):
            return (
                f"我公司承诺本项目成果和服务满足国家法律法规、行业标准、招标文件、合同条款及招标人要求，当前识别的质量要求为：{quality}。\n\n"
                "质量控制将覆盖需求确认、方案编制、过程实施、内部检查、成果复核、交付验收、问题整改和资料归档全过程。对发现的问题建立整改台账，明确责任人、完成时限和复核要求，确保问题闭环处理。若因我公司原因造成质量、交付或服务不满足招标文件及合同要求，我公司愿按合同约定承担相应责任。"
            )
        if any(keyword in title for keyword in ("沟通", "协调", "响应")):
            return (
                "我公司将建立定期沟通、即时沟通和书面沟通相结合的协调机制。对例会、需求变更、问题反馈、审查意见和验收意见形成会议纪要或书面记录，明确责任人、完成时限和闭环状态。\n\n"
                "如招标人要求专属联系人、服务热线或驻场人员，应按企业资料填写；资料缺失时使用占位：〖待补充：联系人、联系方式、驻场人员或服务响应渠道〗。"
            )
        if any(keyword in title for keyword in ("设备", "软件", "工具", "资源", "人员", "产品", "供货")):
            return (
                f"本节根据招标文件和评分要求说明资源投入。相关人员、设备、软件、产品、车辆、检测仪器、备品备件或服务工具应以企业资料为准，不得虚构。\n\n"
                "表 资源投入计划表\n"
                "| 序号 | 资源类别 | 名称/岗位 | 数量/配置 | 用途 | 证明材料 |\n|---|---|---|---|---|---|\n"
                "| 1 | 人员 | 〖待补充：人员或岗位〗 | 〖待补充〗 | 〖待确认：用途〗 | 〖待提供扫描件：证书/社保/劳动合同〗 |\n"
                "| 2 | 设备/工具/软件 | 〖待补充：资源名称〗 | 〖待补充〗 | 〖待确认：用途〗 | 〖待提供扫描件或截图：购置/授权/清单〗 |\n\n"
                f"应补充或核验资料：\n{missing_lines}"
            )
        if any(keyword in title for keyword in ("图片", "展示", "数字化", "信息化", "案例", "效果图", "截图", "证书")):
            return (
                f"{description}\n\n"
                "本节相关图片、证书、系统截图、案例素材或可视化成果必须来源于企业素材库或项目实际资料。未提供素材时，不得虚构图片内容，应保留以下占位：\n\n"
                f"〖插入图片：{title}素材〗\n\n"
                f"应补充或核验资料：\n{missing_lines}"
            )
        return (
            f"本节围绕“{title}”进行响应。{description}\n\n"
            f"项目名称：{project_name}。\n"
            "响应原则：以招标文件、评分办法和标准解析报告为准，逐项覆盖当前章节关联的评分项、审查要求、风险点和材料要求。\n\n"
            "实施与响应要点：\n"
            "1. 准确响应招标文件中与本节相关的范围、期限、质量、交付、服务、格式和材料要求。\n"
            "2. 对评分项设置专门措施，说明工作方法、组织安排、质量控制、进度控制、风险防控和交付成果。\n"
            "3. 对企业资料缺失项保留明确占位，不擅自虚构。\n\n"
            "应附材料及核验要点：\n"
            f"{missing_lines}\n"
        )

    @staticmethod
    def _fallback_compliance_review(
        outline: list,
        analysis_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """合规审校失败时的保底审校结果。"""
        report = analysis_report or {}
        scoring_ids = [item.get("id") for item in report.get("technical_scoring_items", []) if item.get("id")]
        material_ids = [item.get("id") for item in report.get("required_materials", []) if item.get("id")]
        risk_ids = [item.get("id") for item in report.get("rejection_risks", []) if item.get("id")]
        coverage = [
            {
                "item_id": item_id,
                "target_type": "scoring",
                "covered": False,
                "chapter_ids": [],
                "issue": "需确认正文是否逐项覆盖评分标准",
                "evidence": "",
                "fix_suggestion": "在对应章节补写评分标准响应措施和支撑材料",
            }
            for item_id in scoring_ids[:8]
        ]
        missing = [
            {
                "material_id": item_id,
                "material_name": item_id,
                "used_by": [],
                "chapter_ids": [],
                "placeholder": "〖待补充或核验证明材料〗",
                "placeholder_found": False,
                "fix_suggestion": "补齐材料或在正文中保留明确待补占位",
            }
            for item_id in material_ids[:8]
        ]
        risks = [
            {"risk_id": item_id, "handled": False, "issue": "需在导出前核验签字盖章、格式、材料和实质性响应"}
            for item_id in risk_ids[:8]
        ]
        warnings = len(coverage) + len(missing) + len(risks)
        blocking_issue = {
            "item_id": "CHECK-01",
            "chapter_ids": [],
            "issue": "兜底审校无法确认完整覆盖，需要人工复核响应矩阵、材料和签章",
            "evidence": "模型审校不可用，系统返回兜底结果",
            "fix_suggestion": "重新执行合规审校或逐项检查覆盖矩阵",
            "severity": "blocking",
            "blocking": True,
        }
        return ReviewReport.model_validate({
            "coverage": coverage,
            "missing_materials": missing,
            "rejection_risks": risks,
            "duplication_issues": [],
            "fabrication_risks": [],
            "fixed_format_issues": [],
            "signature_issues": [{
                "item_id": "SIG-01",
                "chapter_ids": [],
                "issue": "签字盖章需在最终 Word 组卷后人工核验",
                "severity": "warning",
                "blocking": False,
            }],
            "price_rule_issues": [],
            "evidence_chain_issues": [],
            "page_reference_issues": [{
                "item_id": "PAGE-01",
                "chapter_ids": [],
                "issue": "最终排版前页码索引仍为待编排状态",
                "evidence": "正文导出前尚未完成 Word 页码编排",
                "fix_suggestion": "导出后更新目录、索引和页码引用",
                "severity": "warning",
                "blocking": False,
            }],
            "anonymity_issues": [],
            "blocking_issues": [blocking_issue],
            "warnings": [],
            "revision_plan": {
                "actions": [{
                    "id": "RP-01",
                    "target_chapter_ids": [],
                    "action_type": "人工确认",
                    "instruction": "逐项核验评分项、审查项、材料、签章、固定格式和报价隔离要求。",
                    "priority": "high",
                    "related_issue_ids": ["CHECK-01"],
                    "blocking": True,
                }],
                "summary": "兜底审校无法替代正式模型审校，导出前需人工复核。",
            },
            "summary": {
                "ready_to_export": False,
                "blocking_issues": 1,
                "warnings": warnings + 2,
                "blocking_issues_count": 1,
                "warnings_count": warnings + 2,
                "coverage_rate": 0,
                "blocking_summary": "需要人工复核完整响应矩阵和材料链",
                "next_actions": ["重新执行合规审校", "补齐缺失材料", "核验签章与固定格式"],
            },
        }).model_dump(mode="json")

    @staticmethod
    def _raise_if_gateway_error(payload: Any) -> None:
        """识别 OpenAI 兼容网关用 200 响应包裹的业务错误"""
        if not hasattr(payload, "model_dump"):
            return

        data = payload.model_dump()
        base_resp = data.get("base_resp")
        if not isinstance(base_resp, dict):
            return

        status_code = base_resp.get("status_code")
        status_msg = base_resp.get("status_msg") or base_resp.get("message") or "unknown error"
        if status_code not in (None, 0, "0"):
            raise Exception(f"模型网关返回错误: {status_msg} ({status_code})")

    @staticmethod
    def _is_model_selection_error(error: Exception | None) -> bool:
        """判断 OpenAI 兼容调用失败是否由模型名不匹配导致。

        这种情况下继续尝试 Claude 原生协议会掩盖真正的错误。
        """
        message = str(error or "").lower()
        return any(marker in message for marker in (
            "model",
            "not found",
            "not_found",
            "available models",
            "does not exist",
            "invalid model",
        ))
    
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        if not provider_supports_model_listing(self.provider):
            return get_default_models(self.provider)

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            client = self._create_client(candidate)
            try:
                models = await client.models.list()
                self.client = client
                self.resolved_base_url = candidate or ""
                model_ids = []
                for model in models.data:
                    if not getattr(model, "id", None):
                        continue
                    if self.provider in {"custom", "litellm"}:
                        model_ids.append(model.id)
                        continue
                    model_id = model.id.lower()
                    if any(keyword in model_id for keyword in [
                        'gpt', 'claude', 'chat', 'llama', 'qwen', 'deepseek',
                        'gemini', 'moonshot', 'kimi', 'glm', 'mistral', 'codex', 'gpt-5',
                    ]):
                        model_ids.append(model.id)
                normalized_models = sorted(list(set(model_ids)))
                if normalized_models:
                    return normalized_models

                fallback_models = get_default_models(self.provider)
                if fallback_models:
                    return fallback_models
                raise Exception("未找到可用的对话模型")
            except Exception as e:
                last_error = e

        try:
            fallback_models = get_default_models(self.provider)
            if fallback_models:
                return fallback_models
            raise Exception("未找到可用的对话模型")
        except Exception as e:
            fallback_models = get_default_models(self.provider)
            if fallback_models:
                return fallback_models
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    async def stream_chat_completion(
        self, 
        messages: list, 
        temperature: float = 0.7,
        response_format: dict = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成请求 - 真正的异步实现"""
        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            client = self._create_client(candidate)
            try:
                self.client = client
                self.resolved_base_url = candidate or ""

                request_kwargs: Dict[str, Any] = {}
                if response_format is not None:
                    request_kwargs["response_format"] = response_format
                if max_tokens is not None:
                    request_kwargs["max_tokens"] = max_tokens

                try:
                    stream = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        stream=True,
                        **request_kwargs,
                    )
                except Exception:
                    if response_format is None:
                        raise
                    fallback_messages = self._augment_messages_for_json_output(messages, response_format)
                    stream = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=fallback_messages,
                        temperature=temperature,
                        stream=True,
                        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
                    )

                received_content = False
                async for chunk in stream:
                    self._raise_if_gateway_error(chunk)
                    if not chunk.choices:
                        continue
                    if chunk.choices[0].delta.content is not None:
                        received_content = True
                        yield chunk.choices[0].delta.content
                if not received_content:
                    raise Exception("模型返回空流式内容，请确认 Base URL 指向真实 API 路径而不是管理后台页面")
                return
            except Exception as e:
                last_error = e

        if self._is_model_selection_error(last_error):
            raise Exception(
                "LiteLLM Proxy 已响应，但当前模型名不可用。请先同步模型列表并选择 LiteLLM 返回的模型 ID，"
                f"或确认 LiteLLM 配置中的 model_name。原始错误: {str(last_error)}"
            ) from last_error

        raise Exception(f"模型调用失败: {str(last_error)}") from last_error

    async def _get_anthropic_models(self) -> List[str]:
        """获取 Anthropic / Claude 原生接口的模型列表"""
        headers = {
            "x-api-key": resolve_api_key(self.provider, self.api_key),
            "anthropic-version": "2023-06-01",
        }
        last_error: Exception | None = None

        for candidate in self._iter_base_urls():
            endpoint = self._join_endpoint(candidate or "", "/models", force_v1=True)
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(endpoint, headers=headers) as response:
                        payload = await response.text()
                        if response.status >= 400:
                            raise Exception(payload[:500])

                        data = json.loads(payload)
                        models = []
                        for item in data.get("data", []):
                            model_id = item.get("id", "")
                            if "claude" in model_id.lower():
                                models.append(model_id)

                        if models:
                            self.resolved_base_url = candidate or ""
                            return sorted(list(set(models)))

                        raise Exception("未找到可用的 Claude 模型")
            except Exception as e:
                last_error = e

        raise Exception(f"获取 Claude 模型列表失败: {str(last_error)}") from last_error

    async def _stream_anthropic_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """调用 Anthropic 原生 Messages API，先以单次响应方式兼容现有流程"""
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role in {"system", "developer"}:
                system_parts.append(str(content))
                continue

            anthropic_role = "assistant" if role == "assistant" else "user"
            anthropic_messages.append({
                "role": anthropic_role,
                "content": str(content),
            })

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": ""})

        if response_format and response_format.get("type") in {"json_object", "json_schema"}:
            system_parts.append("你必须只输出合法 JSON，不要输出 markdown 代码块，不要附加解释。")

        headers = {
            "x-api-key": resolve_api_key(self.provider, self.api_key),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model_name,
            "max_tokens": 8192,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            endpoint = self._join_endpoint(candidate or "", "/messages", force_v1=True)
            try:
                timeout = aiohttp.ClientTimeout(total=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(endpoint, headers=headers, json=body) as response:
                        payload = await response.text()
                        if response.status >= 400:
                            raise Exception(payload[:1000])

                        data = json.loads(payload)
                        text_chunks = []
                        for block in data.get("content", []):
                            if block.get("type") == "text" and block.get("text"):
                                text_chunks.append(block["text"])

                        if not text_chunks:
                            raise Exception("Claude 返回内容为空")

                        self.resolved_base_url = candidate or ""
                        yield "".join(text_chunks)
                        return
            except Exception as e:
                last_error = e

        raise Exception(f"Claude 接口调用失败: {str(last_error)}") from last_error

    @staticmethod
    def _build_responses_text_config(response_format: dict | None) -> dict | None:
        """将 Chat Completions 的 response_format 映射为 Responses API 的 text.format"""
        if not response_format:
            return None

        response_type = response_format.get("type")
        if response_type in {"text", "json_object"}:
            return {"format": {"type": response_type}}

        if response_type == "json_schema":
            format_config = {"type": "json_schema"}
            for key in ("name", "schema", "strict", "description"):
                if key in response_format:
                    format_config[key] = response_format[key]
            return {"format": format_config}

        return None

    async def _stream_responses_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """针对 Codex / Responses API 的流式文本输出"""
        request_params: Dict[str, Any] = {
            "model": self.model_name,
            "input": messages,
            "temperature": temperature,
        }

        text_config = self._build_responses_text_config(response_format)
        if text_config is not None:
            request_params["text"] = text_config

        received_text = False
        async with self.client.responses.stream(**request_params) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    received_text = True
                    yield event.delta

            if not received_text:
                final_response = await stream.get_final_response()
                if final_response.output_text:
                    yield final_response.output_text

    async def _collect_stream_text(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """收集流式返回的文本到一个完整字符串"""
        full_content = ""
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=temperature,
            response_format=response_format,
            max_tokens=max_tokens,
        ):
            full_content += chunk
        return full_content

    async def verify_current_endpoint(self) -> Dict[str, Any]:
        """验证当前供应商配置是否可列模型并可发起一次对话"""
        checks: list[dict[str, Any]] = []
        visible_candidates = [candidate for candidate in self.base_url_candidates if candidate]
        models_ok = False
        chat_ok = False
        models_error = ""
        chat_error = ""

        try:
            models = await self.get_available_models()
            models_ok = True
            checks.append({
                "stage": "models",
                "success": True,
                "detail": f"获取到 {len(models)} 个模型",
                "url": self.resolved_base_url or self.normalized_base_url or "",
                "model_name": self.model_name,
                "models": models[:20],
            })
        except Exception as exc:
            models = []
            models_error = str(exc)
            checks.append({
                "stage": "models",
                "success": False,
                "detail": models_error,
                "url": self.resolved_base_url or self.normalized_base_url or "",
                "model_name": self.model_name,
            })

        if models_ok and models and self.provider in {"custom", "litellm"} and self.model_name not in models:
            chat_error = (
                f"模型名 '{self.model_name}' 不在当前端点返回的模型列表中。"
                f"可用模型: {', '.join(models[:20])}"
            )
            checks.append({
                "stage": "chat",
                "success": False,
                "detail": chat_error,
                "url": self.resolved_base_url or self.normalized_base_url or "",
                "model_name": self.model_name,
                "models": models[:20],
            })
        else:
            try:
                sample = await self._collect_stream_text(
                    messages=[{"role": "user", "content": "请只回复 OK"}],
                    temperature=0,
                )
                if not sample.strip():
                    raise Exception("模型返回空内容，请确认 Base URL、模型名和 API Key 是否正确")
                chat_ok = True
                checks.append({
                    "stage": "chat",
                    "success": True,
                    "detail": "对话请求成功",
                    "url": self.resolved_base_url or self.normalized_base_url or "",
                    "model_name": self.model_name,
                    "sample": sample.strip()[:200],
                })
            except Exception as exc:
                chat_error = str(exc)
                checks.append({
                    "stage": "chat",
                    "success": False,
                    "detail": chat_error,
                    "url": self.resolved_base_url or self.normalized_base_url or "",
                    "model_name": self.model_name,
                })

        if models_ok and chat_ok:
            message = "端点验证成功"
        elif chat_ok:
            message = f"模型列表验证失败，但对话请求成功: {models_error}"
        elif models_ok:
            message = f"对话请求验证失败: {chat_error}"
        else:
            message = f"模型列表与对话请求均失败: {chat_error or models_error}"

        return {
            "success": chat_ok,
            "message": message,
            "provider": self.provider,
            "normalized_base_url": self.normalized_base_url or "",
            "resolved_base_url": self.resolved_base_url or "",
            "base_url_candidates": visible_candidates,
            "model_name": self.model_name,
            "api_mode": self.api_mode,
            "checks": checks,
        }

    async def _generate_with_json_check(
        self,
        messages: list,
        schema: str | Dict[str, Any],
        max_retries: int = 3,
        temperature: float = 0.7,
        response_format: dict | None = None,
        log_prefix: str = "",
        raise_on_fail: bool = True,
    ) -> str:
        """
        通用的带 JSON 结构校验与重试的生成函数。

        返回：通过校验的 full_content；如果 raise_on_fail=False，则在多次失败后返回最后一次内容。
        """
        attempt = 0
        last_error_msg = ""

        while True:
            full_content = await self._collect_stream_text(
                messages,
                temperature=temperature,
                response_format=response_format,
            )

            normalized_content = self._extract_json_payload(str(full_content))
            isok, error_msg = check_json(str(normalized_content), schema)
            if isok:
                return normalized_content

            last_error_msg = error_msg
            prefix = f"{log_prefix} " if log_prefix else ""

            if attempt >= max_retries:
                print(f"{prefix}check_json 校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                if raise_on_fail:
                    raise Exception(f"{prefix}check_json 校验失败: {last_error_msg}")
                # 不抛异常，返回最后一次内容（保持原有行为）
                return normalized_content

            attempt += 1
            print(f"{prefix}check_json 校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
            await asyncio.sleep(0.5)

    async def _generate_pydantic_json(
        self,
        messages: list,
        model_cls: type,
        max_retries: int = 3,
        temperature: float = 0.3,
        response_format: dict | None = None,
        max_tokens: int | None = None,
        log_prefix: str = "",
    ) -> Dict[str, Any]:
        """生成 JSON 并使用 Pydantic 模型校验，适合允许空数组的结构化结果"""
        attempt = 0
        last_error_msg = ""

        while True:
            request_messages = messages
            if attempt > 0:
                request_messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "上一次输出不是可解析的完整 JSON，常见原因是输出过长被截断。"
                            "请重新输出一个更精简但字段完整的合法 JSON：每个数组最多保留最关键 8 项，"
                            "长文本压缩到 80 字以内，必须闭合所有对象和数组。"
                            f"上次错误：{last_error_msg}"
                        ),
                    },
                ]

            full_content = await self._collect_stream_text(
                request_messages,
                temperature=temperature,
                response_format=response_format,
                max_tokens=max_tokens,
            )
            normalized_content = self._extract_json_payload(str(full_content))

            try:
                parsed = model_cls.model_validate_json(str(normalized_content))
                return parsed.model_dump(mode="json")
            except Exception as e:
                last_error_msg = str(e)
                prefix = f"{log_prefix} " if log_prefix else ""

                if attempt >= max_retries:
                    print(f"{prefix}Pydantic JSON 校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                    raise Exception(f"{prefix}Pydantic JSON 校验失败: {last_error_msg}") from e

                attempt += 1
                print(f"{prefix}Pydantic JSON 校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
                await asyncio.sleep(0.5)

    async def generate_analysis_report(self, file_content: str) -> Dict[str, Any]:
        """从招标文件全文生成结构化标准解析报告"""
        if self._force_local_fallback():
            return self._fallback_analysis_report(file_content, "本地安全验证模式")

        timeout_seconds = self._int_env("YIBIAO_ANALYSIS_REPORT_TIMEOUT_SECONDS", 1800)
        max_tokens = self._int_env("YIBIAO_ANALYSIS_REPORT_MAX_TOKENS", 12000)
        system_prompt, user_prompt = prompt_manager.generate_analysis_report_prompt(file_content)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        generation_task = self._generate_pydantic_json(
            messages=messages,
            model_cls=AnalysisReport,
            max_retries=1,
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            log_prefix="标准解析报告",
        )
        try:
            if timeout_seconds > 0:
                report = await asyncio.wait_for(generation_task, timeout=timeout_seconds)
            else:
                report = await generation_task
            if not report.get("response_matrix"):
                report["response_matrix"] = await self.generate_response_matrix(report)
            return AnalysisReport.model_validate(report).model_dump(mode="json")
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

    async def generate_reference_bid_style_profile(self, reference_bid_text: str) -> Dict[str, Any]:
        """解析成熟投标文件样例，生成可复用的风格剖面。"""
        if self._force_local_fallback():
            return {
                "profile_name": "本地兜底样例风格",
                "document_scope": "unknown",
                "recommended_use_case": "用于目录层级、表格、承诺书和素材位置参考，不绑定具体行业。",
                "outline_template": [],
                "writing_style": {"voice": "我公司", "tone": "正式投标文件语气", "paragraph_style": "条理化分点"},
                "quality_risks": [],
            }
        system_prompt, user_prompt = prompt_manager.generate_reference_bid_style_profile_prompt(reference_bid_text)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        schema = prompt_manager.get_reference_bid_style_profile_schema()
        try:
            content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema=schema,
                    max_retries=1,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    log_prefix="样例风格剖面",
                    raise_on_fail=True,
                ),
                timeout=120,
            )
            return json.loads(content.strip())
        except Exception as e:
            print(f"样例风格剖面模型输出不可用，返回兜底剖面：{str(e)}")
            return {
                "profile_name": "样例解析失败兜底剖面",
                "document_scope": "unknown",
                "recommended_use_case": "样例解析失败，后续仅按招标文件和通用规则生成。",
                "outline_template": [],
                "writing_style": {"voice": "我公司", "tone": "正式投标文件语气", "paragraph_style": "条理化分点"},
                "quality_risks": [{"risk": "样例风格解析失败", "location": "系统", "fix_rule": str(e)[:120]}],
            }

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
        if self._force_local_fallback():
            return {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []}
        system_prompt, user_prompt = prompt_manager.generate_document_blocks_prompt(
            analysis_report=report,
            outline=outline,
            response_matrix=matrix,
            reference_bid_style_profile=style_profile,
            enterprise_materials=enterprise_materials or [],
            asset_library=asset_library or [],
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        schema = prompt_manager.get_document_blocks_schema()
        try:
            content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema=schema,
                    max_retries=1,
                    temperature=0.15,
                    response_format={"type": "json_object"},
                    log_prefix="图表素材规划",
                    raise_on_fail=True,
                ),
                timeout=90,
            )
            return json.loads(content.strip())
        except Exception as e:
            print(f"图表素材规划模型输出不可用，返回空规划：{str(e)}")
            return {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []}

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
                    response_format={"type": "json_object"},
                    log_prefix="一致性修订",
                    raise_on_fail=True,
                ),
                timeout=120,
            )
            return json.loads(content.strip())
        except Exception as e:
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

        system_prompt, user_prompt = prompt_manager.generate_response_matrix_prompt(report, style_profile)
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
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                    log_prefix="响应矩阵",
                ),
                timeout=90,
            )
        except Exception as e:
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
                    response_format={"type": "json_object"},
                    log_prefix="合规审校",
                ),
                timeout=120,
            )
        except Exception as e:
            print(f"合规审校模型输出不可用，启用文本兜底审校：{str(e)}")
            return self._fallback_compliance_review(outline, analysis_report)

    async def generate_content_for_outline(
        self,
        outline: Dict[str, Any],
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """为目录结构生成内容"""
        try:
            if not isinstance(outline, dict) or 'outline' not in outline:
                raise Exception("无效的outline数据格式")
            
            # 深拷贝outline数据
            import copy
            result_outline = copy.deepcopy(outline)
            
            # 递归处理目录
            await self._process_outline_recursive(
                result_outline['outline'],
                [],
                project_overview,
                analysis_report=analysis_report,
                bid_mode=bid_mode,
                reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
            )
            
            return result_outline
            
        except Exception as e:
            raise Exception(f"处理过程中发生错误: {str(e)}")
    
    async def _process_outline_recursive(
        self,
        chapters: list,
        parent_chapters: list = None,
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ):
        """递归处理章节列表"""
        for chapter in chapters:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            
            # 检查是否为叶子节点
            is_leaf = 'children' not in chapter or not chapter.get('children', [])
            
            # 准备当前章节信息
            current_chapter_info = {
                'id': chapter_id,
                'title': chapter_title,
                'description': chapter.get('description', '')
            }
            
            # 构建完整的上级章节列表
            current_parent_chapters = []
            if parent_chapters:
                current_parent_chapters.extend(parent_chapters)
            current_parent_chapters.append(current_chapter_info)
            
            if is_leaf:
                # 为叶子节点生成内容，传递同级章节信息
                content = ""
                async for chunk in self._generate_chapter_content(
                    chapter, 
                    current_parent_chapters[:-1],  # 上级章节列表（排除当前章节）
                    chapters,  # 同级章节列表
                    project_overview,
                    analysis_report=analysis_report,
                    bid_mode=bid_mode,
                    reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                    document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
                ):
                    content += chunk
                if content:
                    chapter['content'] = content
            else:
                # 递归处理子章节
                await self._process_outline_recursive(
                    chapter['children'],
                    current_parent_chapters,
                    project_overview,
                    analysis_report=analysis_report,
                    bid_mode=bid_mode,
                    reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                    document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
                )
    
    async def _generate_chapter_content(
        self,
        chapter: dict,
        parent_chapters: list = None,
        sibling_chapters: list = None,
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        generated_summaries: list | None = None,
        enterprise_materials: list | None = None,
        missing_materials: list | None = None,
        response_matrix: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """为单个章节流式生成内容。"""
        try:
            if self._force_local_fallback():
                yield self._fallback_chapter_content(
                    chapter,
                    project_overview=project_overview,
                    analysis_report=analysis_report,
                    missing_materials=missing_materials,
                )
                return

            effective_response_matrix = response_matrix or (analysis_report or {}).get("response_matrix") or {}
            system_prompt, user_prompt = prompt_manager.generate_chapter_content_prompt(
                chapter=chapter,
                parent_chapters=parent_chapters or [],
                sibling_chapters=sibling_chapters or [],
                project_overview=project_overview,
                analysis_report=analysis_report,
                bid_mode=bid_mode,
                generated_summaries=generated_summaries or [],
                enterprise_materials=enterprise_materials or [],
                missing_materials=missing_materials or (analysis_report or {}).get("missing_company_materials", []),
                response_matrix=effective_response_matrix,
                reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            try:
                async for chunk in self.stream_chat_completion(messages, temperature=0.35):
                    yield chunk
            except Exception as e:
                print(f"章节模型输出不可用，启用文本兜底正文：{str(e)}")
                yield self._fallback_chapter_content(
                    chapter,
                    project_overview=project_overview,
                    analysis_report=analysis_report,
                    missing_materials=missing_materials,
                )
        except Exception as e:
            print(f"生成章节内容时出错: {str(e)}")
            raise Exception(f"生成章节内容时出错: {str(e)}") from e

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
        """生成目录。模型优先；只有模型不可用或本地验证模式才启用通用兜底目录。"""
        report = dict(analysis_report or {})
        if report and not self._force_local_fallback() and self._analysis_report_has_blocking_generation_warning(report):
            raise Exception(
                "当前标准解析报告来自旧兜底或未完整模型输出，目录生成已停止。"
                "请先重新执行标准解析，得到完整结构化解析报告后再生成目录。"
            )
        if file_content and len(self._collect_scheme_outline_items(report)) < 2:
            fallback_bid_doc = self._extract_bid_document_requirements(file_content)
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
                    schema=schema_json,
                    max_retries=1,
                    temperature=0.22,
                    response_format={"type": "json_object"},
                    log_prefix="一级提纲",
                    raise_on_fail=True,
                ),
                timeout=120,
            )
        except Exception as e:
            print(f"一级提纲模型输出不可用，启用通用兜底目录：{str(e)}")
            fallback = self._fallback_outline(report, effective_bid_mode)
            fallback.setdefault("document_blocks_plan", blocks_plan or {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []})
            fallback.setdefault("reference_bid_style_profile", style_profile)
            return fallback

        parsed = json.loads(full_content.strip())
        level_l1 = parsed.get("outline") if isinstance(parsed, dict) else parsed
        if not isinstance(level_l1, list) or not level_l1:
            fallback = self._fallback_outline(report, effective_bid_mode)
            fallback.setdefault("document_blocks_plan", blocks_plan or {"document_blocks": [], "missing_assets": [], "missing_enterprise_data": []})
            fallback.setdefault("reference_bid_style_profile", style_profile)
            return fallback

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
        tasks = [
            self.process_level1_node(
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
            for i, level1_node in enumerate(level_l1)
        ]
        outline = await asyncio.gather(*tasks)

        if not blocks_plan:
            blocks_plan = await self.generate_document_blocks_plan(
                outline=outline,
                analysis_report=report,
                response_matrix=report.get("response_matrix"),
                reference_bid_style_profile=style_profile,
            )
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
            node = dict(level1_node)
            node.setdefault("id", str(i + 1))
            node.setdefault("title", title)
            node.setdefault("description", "按招标文件要求编写。")
            node.setdefault("volume_id", "V-TECH")
            node.setdefault("chapter_type", "service_plan" if bid_mode in {"technical_service_plan", "service_plan"} else "technical")
            node.setdefault("source_type", "profile_or_model")
            node.setdefault("enterprise_required", False)
            node.setdefault("asset_required", False)
            node.setdefault("expected_depth", "medium")
            node.setdefault("expected_blocks", ["paragraph"])
            node.setdefault("fixed_format_sensitive", False)
            node.setdefault("price_sensitive", False)
            node.setdefault("anonymity_sensitive", False)
            node.setdefault("expected_word_count", 1200)
            for key in ("scoring_item_ids", "requirement_ids", "risk_ids", "material_ids", "response_matrix_ids"):
                node.setdefault(key, [])
            return node

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
            schema=json_outline,
            max_retries=3,
            temperature=0.25,
            response_format={"type": "json_object"},
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )
        return json.loads(full_content.strip())
