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
from ..utils import generation_policy
from ..utils.json_util import check_json, extract_json_string
from ..utils.config_manager import config_manager
from ..models.schemas import AnalysisReport, ResponseMatrix, ReviewReport
from .enterprise_material_service import EnterpriseMaterialService
from .fallback_generation import FallbackGenerationMixin
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


class OpenAIService(FallbackGenerationMixin):
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
    def _generation_fallbacks_enabled() -> bool:
        """是否允许生成链路在模型失败时返回兜底结果，默认关闭。"""
        return generation_policy.generation_fallbacks_enabled()

    @classmethod
    def _force_local_fallback(cls) -> bool:
        """端到端本地验证开关；只有显式允许兜底时才生效。"""
        return generation_policy.force_local_fallback()

    @classmethod
    def _fallback_disabled_error(cls, stage: str, reason: str) -> Exception:
        """生成链路兜底关闭时统一返回可操作错误。"""
        return generation_policy.fallback_disabled_error(stage, reason, cls._compact_text)

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        """读取正整数环境变量；非法值回退到默认值。"""
        try:
            value = int(os.getenv(name, str(default)))
            return value if value >= 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() not in {"0", "false", "no", "off"}

    def _include_schema_in_prompt(self) -> bool:
        """兼容会忽略 response_format 的 OpenAI 兼容网关，默认保留 prompt 侧 schema。"""
        return self._bool_env("YIBIAO_INCLUDE_SCHEMA_IN_PROMPT", True)

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

    @staticmethod
    def _response_format_name(name: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(name or "structured_output")).strip("_")
        return normalized[:64] or "structured_output"

    @classmethod
    def _json_schema_response_format(cls, name: str, schema: Any, *, strict: bool = False) -> dict:
        """构造 Chat Completions 兼容的 json_schema response_format。"""
        if isinstance(schema, str):
            schema = json.loads(schema)
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls._response_format_name(name),
                "schema": schema,
                "strict": strict,
            },
        }

    @classmethod
    def _pydantic_response_format(cls, name: str, model_cls: type, *, strict: bool = False) -> dict:
        return cls._json_schema_response_format(name, model_cls.model_json_schema(), strict=strict)

    @classmethod
    def _example_to_json_schema(cls, example: Any) -> dict:
        """把项目现有的示例结构转换成宽松 JSON Schema，供 response_format 使用。"""
        if isinstance(example, str):
            try:
                example = json.loads(example)
            except json.JSONDecodeError:
                return {"type": "string"}
        if isinstance(example, dict):
            return {
                "type": "object",
                "properties": {str(key): cls._example_to_json_schema(value) for key, value in example.items()},
                "additionalProperties": True,
            }
        if isinstance(example, list):
            return {
                "type": "array",
                "items": cls._example_to_json_schema(example[0]) if example else {},
            }
        if isinstance(example, bool):
            return {"type": "boolean"}
        if isinstance(example, int) and not isinstance(example, bool):
            return {"type": "integer"}
        if isinstance(example, float):
            return {"type": "number"}
        if example is None:
            return {}
        return {"type": "string"}

    @classmethod
    def _example_response_format(cls, name: str, example: Any, *, strict: bool = False) -> dict:
        return cls._json_schema_response_format(name, cls._example_to_json_schema(example), strict=strict)

    @staticmethod
    def _schema_from_response_format(response_format: dict | None) -> dict | None:
        if not response_format or response_format.get("type") != "json_schema":
            return None
        json_schema = response_format.get("json_schema")
        if isinstance(json_schema, dict) and isinstance(json_schema.get("schema"), dict):
            return json_schema["schema"]
        schema = response_format.get("schema")
        return schema if isinstance(schema, dict) else None

    @classmethod
    def _response_format_schema_hint(cls, response_format: dict | None) -> str:
        schema = cls._schema_from_response_format(response_format)
        if not schema:
            return ""
        return "输出必须符合以下 JSON Schema：\n" + json.dumps(schema, ensure_ascii=False)

    def _augment_messages_for_json_output(self, messages: list, response_format: dict | None) -> list:
        """为不支持 response_format 的本地兼容端点追加 JSON 纯输出约束"""
        if not self._response_format_requires_json_guard(response_format):
            return messages

        json_guard = (
            "你必须只输出合法 JSON，不要输出 markdown 代码块，不要输出解释性文字，"
            "不要在 JSON 前后添加任何多余内容。"
        )
        schema_hint = self._response_format_schema_hint(response_format)
        if schema_hint:
            json_guard = f"{json_guard}\n\n{schema_hint}"

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
        return extract_json_string(full_content)

    @staticmethod
    def _repair_unescaped_inner_quotes(json_text: str) -> str:
        """修复模型在字符串内部偶发输出的未转义英文双引号。"""
        repaired: list[str] = []
        in_string = False
        escaped = False
        text = str(json_text or "")

        for index, char in enumerate(text):
            if not in_string:
                repaired.append(char)
                if char == '"':
                    in_string = True
                continue

            if escaped:
                repaired.append(char)
                escaped = False
                continue

            if char == "\\":
                repaired.append(char)
                escaped = True
                continue

            if char == '"':
                lookahead = index + 1
                while lookahead < len(text) and text[lookahead].isspace():
                    lookahead += 1
                next_char = text[lookahead] if lookahead < len(text) else ""
                if next_char in {":", ",", "}", "]", ""}:
                    repaired.append(char)
                    in_string = False
                else:
                    repaired.append('\\"')
                continue

            repaired.append(char)

        return "".join(repaired)

    @classmethod
    def _loads_json_loose(cls, json_text: str) -> Any:
        """解析模型 JSON；失败时尝试修复字符串内部未转义引号。"""
        payload = cls._extract_json_payload(str(json_text or ""))
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return json.loads(cls._repair_unescaped_inner_quotes(payload))

    @staticmethod
    def _stringify_requirement(value: Any, limit: int = 260) -> str:
        if isinstance(value, list):
            return "；".join(OpenAIService._stringify_requirement(item, limit) for item in value)[:limit]
        if isinstance(value, dict):
            parts = []
            for key, item in value.items():
                if item in (None, "", [], {}):
                    continue
                parts.append(f"{key}: {OpenAIService._stringify_requirement(item, 120)}")
            return "；".join(parts)[:limit]
        return OpenAIService._compact_text(str(value or ""), limit)

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
            return [f"{key}: {OpenAIService._stringify_requirement(item, 120)}" for key, item in value.items() if item not in (None, "", {}, [])]
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

                request_messages = (
                    self._augment_messages_for_json_output(messages, response_format)
                    if self._response_format_requires_json_guard(response_format)
                    else messages
                )

                try:
                    stream = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=request_messages,
                        temperature=temperature,
                        stream=True,
                        **request_kwargs,
                    )
                except Exception:
                    if response_format is None:
                        raise
                    stream = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=request_messages,
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
            json_guard = "你必须只输出合法 JSON，不要输出 markdown 代码块，不要附加解释。"
            schema_hint = self._response_format_schema_hint(response_format)
            system_parts.append(f"{json_guard}\n\n{schema_hint}" if schema_hint else json_guard)

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
            nested = response_format.get("json_schema")
            if isinstance(nested, dict):
                format_config = {"type": "json_schema"}
                for key in ("name", "schema", "strict", "description"):
                    if key in nested:
                        format_config[key] = nested[key]
                return {"format": format_config}

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
        max_tokens: int | None = None,
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
                max_tokens=max_tokens,
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
                            "请重新读取本轮对话上方提供的招标文件文本，并重新输出标准解析结果。"
                            "上一轮输出未通过系统 JSON 校验。你现在只输出一个合法 JSON 对象，"
                            "不要解释、不要道歉、不要说无法看到上次内容、不要使用 markdown 代码块。"
                            "为避免截断，每个数组最多保留最关键 8 项，长文本压缩到 80 字以内，"
                            "必须闭合所有对象和数组，字段缺失时使用空字符串、空数组或默认布尔值。"
                            "所有 schema 中声明为数组的字段必须输出数组；即使只有一项也使用数组。"
                            f"校验错误：{last_error_msg}"
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
                if model_cls is AnalysisReport:
                    try:
                        compatible_payload = self._loads_json_loose(str(normalized_content))
                        coerced_report = self._coerce_analysis_report_payload(compatible_payload)
                        if coerced_report:
                            parsed = AnalysisReport.model_validate(coerced_report)
                            print(
                                f"{log_prefix} 已将模型兼容解析结构归一化为 AnalysisReport",
                                flush=True,
                            )
                            return parsed.model_dump(mode="json")
                    except Exception:
                        pass
                parsed = model_cls.model_validate_json(str(normalized_content))
                return parsed.model_dump(mode="json")
            except Exception as e:
                if model_cls is AnalysisReport:
                    try:
                        compatible_payload = self._loads_json_loose(str(normalized_content))
                        coerced_report = self._coerce_analysis_report_payload(compatible_payload)
                        if coerced_report:
                            parsed = AnalysisReport.model_validate(coerced_report)
                            print(
                                f"{log_prefix} 已将模型兼容解析结构归一化为 AnalysisReport",
                                flush=True,
                            )
                            return parsed.model_dump(mode="json")
                    except Exception as normalize_error:
                        last_error_msg = f"{str(e)}；兼容结构归一化失败: {normalize_error}"
                    else:
                        last_error_msg = str(e)
                else:
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
        max_input_chars = self._int_env("YIBIAO_ANALYSIS_INPUT_MAX_CHARS", 70000)
        analysis_input = self._prepare_analysis_input(file_content, max_input_chars)
        if len(analysis_input) < len(str(file_content or "")):
            print(
                "标准解析报告 输入过长，已按关键词窗口压缩："
                f"{len(str(file_content or ''))} -> {len(analysis_input)} 字符",
                flush=True,
            )
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

    @staticmethod
    def _prepare_reference_bid_style_input(reference_bid_text: str, max_chars: int = 42000) -> str:
        """把成熟样例 Markdown 压缩成模板证据包，降低模型超时概率。"""
        text = str(reference_bid_text or "").strip()
        if len(text) <= max_chars:
            return text

        lines = [line.rstrip() for line in text.splitlines()]
        head = text[:5000]
        toc_and_headings: list[str] = []
        tables: list[str] = []
        assets: list[str] = []
        writing_samples: list[str] = []

        heading_pattern = re.compile(
            r"^\s*(#{1,4}\s+.+|(?:第?[一二三四五六七八九十百]+[章节]?|\d+(?:\.\d+){0,3}|[（(]\d+[）)])\s*[、.．:：)]\s*.{2,90})\s*$"
        )
        structure_keywords = re.compile(r"目录|技术|服务|方案|组织|质量|安全|进度|人员|设备|业绩|承诺|保障|措施|表|图|附件|签字|盖章")

        for index, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue
            if heading_pattern.match(line):
                toc_and_headings.append(line)
                for sample in lines[index + 1:index + 5]:
                    sample_text = sample.strip()
                    if 20 <= len(sample_text) <= 180 and not sample_text.startswith("|"):
                        writing_samples.append(sample_text)
                        break
            if line.startswith("|") and line.count("|") >= 2:
                tables.append(line)
            if re.search(r"!\[|<img|图片|照片|组织机构图|流程图|效果图|截图|证书|资质|业绩", line):
                assets.append(line)
            if structure_keywords.search(line) and 28 <= len(line) <= 180 and not line.startswith("|"):
                writing_samples.append(line)

        def unique(values: list[str], limit: int) -> list[str]:
            seen: set[str] = set()
            result: list[str] = []
            for value in values:
                normalized = re.sub(r"\s+", " ", value).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                result.append(normalized)
                if len(result) >= limit:
                    break
            return result

        evidence = "\n".join([
            "# 样例封面和开头",
            head,
            "\n# 目录和标题层级证据",
            "\n".join(unique(toc_and_headings, 220)),
            "\n# 表格列名证据",
            "\n".join(unique(tables, 80)),
            "\n# 图片/附件/素材位证据",
            "\n".join(unique(assets, 80)),
            "\n# 段落写作风格样本",
            "\n".join(unique(writing_samples, 180)),
        ]).strip()
        return evidence[:max_chars]

    @staticmethod
    def _reference_profile_check_schema() -> Dict[str, Any]:
        """样例模板先只校验 JSON 对象；核心字段在归一化后用业务规则校验。"""
        return {}

    @staticmethod
    def _merge_reference_profile_defaults(profile: Dict[str, Any]) -> Dict[str, Any]:
        """补齐可安全默认的样例模板字段，避免非核心字段缺失阻断解析。"""
        defaults = prompt_manager.get_reference_bid_style_profile_schema()
        result = json.loads(json.dumps(defaults, ensure_ascii=False))

        def merge(base: Any, incoming: Any) -> Any:
            if isinstance(base, dict) and isinstance(incoming, dict):
                merged = dict(base)
                for key, value in incoming.items():
                    merged[key] = merge(merged.get(key), value) if key in merged else value
                return merged
            return incoming if incoming not in (None, "") else base

        normalized = merge(result, profile)
        normalized["profile_name"] = normalized.get("profile_name") or "成熟样例写作模板"
        normalized["document_scope"] = normalized.get("document_scope") or "unknown"
        normalized["recommended_use_case"] = normalized.get("recommended_use_case") or "作为后续目录和正文生成的参考模板"
        return normalized

    @classmethod
    def _normalize_reference_profile_payload(cls, content: str) -> Dict[str, Any]:
        """兼容模型返回包裹结构或别名字段的 ReferenceBidStyleProfile。"""
        try:
            payload = json.loads(extract_json_string(content))
        except json.JSONDecodeError as e:
            raise Exception(f"样例模板 JSON 解析失败: {str(e)}") from e

        if isinstance(payload, list):
            payload = payload[0] if payload and isinstance(payload[0], dict) else {}
        if not isinstance(payload, dict):
            raise Exception("样例模板 JSON 顶层必须是对象")

        for key in ("reference_bid_style_profile", "ReferenceBidStyleProfile", "profile", "data", "result"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                payload = nested
                break

        if "outline_template" not in payload and isinstance(payload.get("outline"), list):
            payload["outline_template"] = payload["outline"]
        if "chapter_blueprints" not in payload:
            for key in ("chapters", "chapter_templates", "section_blueprints"):
                if isinstance(payload.get(key), list):
                    payload["chapter_blueprints"] = payload[key]
                    break

        return cls._merge_reference_profile_defaults(payload)

    @staticmethod
    def _validate_reference_profile(profile: Dict[str, Any]) -> None:
        outline = profile.get("outline_template")
        blueprints = profile.get("chapter_blueprints")
        style = profile.get("word_style_profile") or {}
        if not isinstance(outline, list) or not outline:
            raise Exception("模型未解析出 outline_template，样例不能作为目录模板使用")
        if not isinstance(blueprints, list) or not blueprints:
            raise Exception("模型未解析出 chapter_blueprints，样例不能作为正文写作模板使用")
        for key in ("body_font_family", "body_font_size", "heading_font_family", "heading_1_size"):
            if not style.get(key):
                raise Exception(f"模型未解析出 Word 样式字段 word_style_profile.{key}")

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
        clean_title = OpenAIService._clean_outline_requirement_title(title)
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
            OpenAIService._clean_outline_requirement_title(part)
            for part in normalized.split("|")
            if OpenAIService._clean_outline_requirement_title(part)
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
        split_titles = OpenAIService._extract_split_secondary_titles(title)
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
            children.append(OpenAIService._build_secondary_seed_node(
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
        title = OpenAIService._clean_outline_requirement_title(
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
            if OpenAIService._outline_title_related(title, score_text):
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
            children.append(OpenAIService._build_secondary_seed_node(
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
        split_children = OpenAIService._seed_secondary_children_from_title(level1_node)
        if split_children:
            return split_children
        return OpenAIService._seed_secondary_children_from_scoring(level1_node, analysis_report)

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

    async def generate_reference_bid_style_profile(self, reference_bid_text: str) -> Dict[str, Any]:
        """解析成熟投标文件样例，生成可复用的风格剖面。"""
        if self._force_local_fallback():
            raise Exception("成熟样例解析需要真实模型；当前 YIBIAO_FORCE_LOCAL_FALLBACK=1，不能生成真实写作模板。")

        timeout_seconds = self._int_env("YIBIAO_REFERENCE_STYLE_TIMEOUT_SECONDS", 360)
        max_tokens = self._int_env("YIBIAO_REFERENCE_STYLE_MAX_TOKENS", 10000)
        max_input_chars = self._int_env("YIBIAO_REFERENCE_STYLE_INPUT_MAX_CHARS", 42000)
        reference_input = self._prepare_reference_bid_style_input(reference_bid_text, max_input_chars)
        if len(reference_input) < len(str(reference_bid_text or "")):
            print(
                "样例风格剖面 输入过长，已压缩为模板证据包："
                f"{len(str(reference_bid_text or ''))} -> {len(reference_input)} 字符",
                flush=True,
            )

        system_prompt, user_prompt = prompt_manager.generate_reference_bid_style_profile_prompt(
            reference_input,
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        check_schema = self._reference_profile_check_schema()
        response_schema = prompt_manager.get_reference_bid_style_profile_schema()
        try:
            content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema=check_schema,
                    max_retries=2,
                    temperature=0.1,
                    response_format=self._example_response_format("reference_bid_style_profile", response_schema),
                    max_tokens=max_tokens,
                    log_prefix="样例风格剖面",
                    raise_on_fail=True,
                ),
                timeout=timeout_seconds,
            )
            profile = self._normalize_reference_profile_payload(content)
            self._validate_reference_profile(profile)
            return profile
        except asyncio.TimeoutError as e:
            raise Exception(
                f"成熟样例模板解析超时：模型超过 {timeout_seconds} 秒仍未返回合法模板 JSON。"
                f"已将输入压缩为 {len(reference_input)} 字符模板证据包；请换用更快模型、提高 "
                "YIBIAO_REFERENCE_STYLE_TIMEOUT_SECONDS，或上传更短的成熟样例。"
            ) from e
        except Exception as e:
            raise Exception(f"成熟样例模板解析失败，未生成可用模板：{self._compact_text(str(e), 220)}") from e

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
                    max_retries=1,
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
                if not self._generation_fallbacks_enabled():
                    raise self._fallback_disabled_error("章节正文生成", str(e)) from e
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
            include_schema_in_prompt=self._include_schema_in_prompt(),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            full_content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema=[{}],
                    max_retries=1,
                    temperature=0.22,
                    response_format=self._example_response_format("level1_outline", schema_json),
                    log_prefix="一级提纲",
                    raise_on_fail=True,
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

        parsed = json.loads(full_content.strip())
        level_l1 = parsed.get("outline") if isinstance(parsed, dict) else parsed
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
            include_schema_in_prompt=self._include_schema_in_prompt(),
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
            response_format=self._example_response_format(f"level23_outline_{i + 1}", json_outline),
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )
        generated_node = json.loads(full_content.strip())
        if secondary_seeds:
            generated_node = self._merge_secondary_seed_children(generated_node, secondary_seeds)
        return self._strip_outline_below_second_level(
            self._normalize_outline_node(generated_node, str(i + 1), title, bid_mode)
        )
