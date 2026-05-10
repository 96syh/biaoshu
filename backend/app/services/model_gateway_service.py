"""Low-level model gateway built on OpenAI-compatible APIs."""
import asyncio
import json
import os
import re
from typing import Any, AsyncGenerator, Dict, List

import aiohttp
import openai

from ..utils.config_manager import config_manager
from ..utils.json_util import extract_json_string
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
from .model_runtime_monitor import ModelRuntimeMonitor


class ModelGatewayService:
    """Provider configuration, endpoint verification and raw model streaming."""

    _model_semaphore: asyncio.Semaphore | None = None
    _model_semaphore_size: int | None = None

    @classmethod
    def _model_concurrency_limit(cls) -> int:
        try:
            limit = int(os.getenv("YIBIAO_MODEL_CONCURRENCY", "2"))
        except (TypeError, ValueError):
            return 2
        return max(1, limit)

    @classmethod
    def _get_model_semaphore(cls) -> asyncio.Semaphore:
        limit = cls._model_concurrency_limit()
        if cls._model_semaphore is None or cls._model_semaphore_size != limit:
            cls._model_semaphore = asyncio.Semaphore(limit)
            cls._model_semaphore_size = limit
        return cls._model_semaphore

    def __init__(self, config: Dict[str, Any] | None = None):
        """Initialize the model gateway, allowing runtime config overrides."""
        runtime_config = dict(config or config_manager.load_config())
        # 模型接入统一收敛到 LiteLLM Proxy，由 LiteLLM 负责把各厂商协议转换成 OpenAI 格式。
        self.provider = DEFAULT_PROVIDER
        self.api_key = runtime_config.get("api_key", "")
        self.base_url = runtime_config.get("base_url", "")
        self.model_name = runtime_config.get("model_name", "gpt-4.1-mini")
        self.api_mode = get_provider_api_mode(self.provider, runtime_config.get("api_mode", "auto"))
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
        """Create a client for a specific base URL."""
        return openai.AsyncOpenAI(
            api_key=resolve_api_key(self.provider, self.api_key),
            base_url=base_url if base_url else None,
            default_headers={
                "Accept": "application/json",
                "User-Agent": "curl/8.7.1",
            },
        )

    def _iter_base_urls(self) -> list[str | None]:
        """Return base URLs to attempt for this request."""
        if self.provider in {"custom", "anthropic", "litellm"} and self.base_url_candidates:
            return list(self.base_url_candidates)
        return [self.resolved_base_url]

    @staticmethod
    def _join_endpoint(base_url: str, path: str, force_v1: bool = False) -> str:
        """Join endpoint paths while handling root URLs and /v1 roots."""
        normalized_base = (base_url or "").rstrip("/")
        normalized_path = path if path.startswith("/") else f"/{path}"
        if force_v1 and not normalized_base.endswith("/v1"):
            normalized_base = f"{normalized_base}/v1"
        return f"{normalized_base}{normalized_path}"

    @staticmethod
    def _response_format_requires_json_guard(response_format: dict | None) -> bool:
        """Whether the response format needs an extra JSON-only prompt guard."""
        if not response_format:
            return False
        return response_format.get("type") in {"json_object", "json_schema"}

    @staticmethod
    def _response_format_name(name: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(name or "structured_output")).strip("_")
        return normalized[:64] or "structured_output"

    @classmethod
    def _json_schema_response_format(cls, name: str, schema: Any, *, strict: bool = False) -> dict:
        """Build a Chat Completions compatible json_schema response_format."""
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
        """Convert existing example payloads into loose JSON Schema."""
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
        """Append JSON-only constraints for compatible endpoints that ignore response_format."""
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
        """Extract plain JSON text from common fenced model responses."""
        if not isinstance(full_content, str):
            return full_content
        return extract_json_string(full_content)

    @staticmethod
    def _raise_if_gateway_error(payload: Any) -> None:
        """Detect business errors wrapped in 200 responses by compatible gateways."""
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
        """Whether a compatible API error indicates an unavailable model name."""
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
        """Fetch available model ids from the configured endpoint."""
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
                        "gpt", "claude", "chat", "llama", "qwen", "deepseek",
                        "gemini", "moonshot", "kimi", "glm", "mistral", "codex", "gpt-5",
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
        """Stream a chat completion from the configured model gateway."""
        async with self._get_model_semaphore():
            last_error: Exception | None = None
            monitor_id = ModelRuntimeMonitor.start(
                provider=self.provider,
                model_name=self.model_name,
                api_mode=self.api_mode,
                base_url=self.resolved_base_url or "",
            )
            for candidate in self._iter_base_urls():
                client = self._create_client(candidate)
                try:
                    self.client = client
                    self.resolved_base_url = candidate or ""
                    ModelRuntimeMonitor.mark_attempt(monitor_id, base_url=self.resolved_base_url)

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
                            ModelRuntimeMonitor.mark_streaming(monitor_id)
                            yield chunk.choices[0].delta.content
                    if not received_content:
                        raise Exception("模型返回空流式内容，请确认 Base URL 指向真实 API 路径而不是管理后台页面")
                    ModelRuntimeMonitor.finish(monitor_id)
                    return
                except Exception as e:
                    last_error = e

            if self._is_model_selection_error(last_error):
                final_error = Exception(
                    "LiteLLM Proxy 已响应，但当前模型名不可用。请先同步模型列表并选择 LiteLLM 返回的模型 ID，"
                    f"或确认 LiteLLM 配置中的 model_name。原始错误: {str(last_error)}"
                )
                ModelRuntimeMonitor.fail(monitor_id, final_error)
                raise final_error from last_error

            final_error = Exception(f"模型调用失败: {str(last_error)}")
            ModelRuntimeMonitor.fail(monitor_id, final_error)
            raise final_error from last_error

    async def _get_anthropic_models(self) -> List[str]:
        """Fetch models through Anthropic's native API."""
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
        """Call Anthropic Messages API in single-response mode for compatibility."""
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
        """Map Chat Completions response_format to Responses API text.format."""
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
        """Stream text output through the Responses API."""
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
        """Collect streaming chunks into a full string."""
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
        """Verify model listing and a sample chat request for the current endpoint."""
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
