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


class GenerationCoreMixin:
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
            return "；".join(GenerationCoreMixin._stringify_requirement(item, limit) for item in value)[:limit]
        if isinstance(value, dict):
            parts = []
            for key, item in value.items():
                if item in (None, "", [], {}):
                    continue
                parts.append(f"{key}: {GenerationCoreMixin._stringify_requirement(item, 120)}")
            return "；".join(parts)[:limit]
        return FallbackGenerationMixin._compact_text(str(value or ""), limit)

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
