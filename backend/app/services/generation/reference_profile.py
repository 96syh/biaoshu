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


class ReferenceProfileGenerationMixin:
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
