"""多模型兼容服务（基于 OpenAI SDK 兼容层）"""
import openai
from typing import Dict, Any, List, AsyncGenerator
import json
import asyncio
import aiohttp
import re

from ..utils.outline_util import get_random_indexes, calculate_nodes_distribution, generate_one_outline_json_by_level1
from ..utils.json_util import check_json, extract_json_string
from ..utils.config_manager import config_manager
from ..utils.provider_registry import (
    DEFAULT_PROVIDER,
    get_base_url_candidates,
    get_default_base_url,
    get_default_models,
    normalize_base_url,
    provider_supports_model_listing,
    provider_uses_anthropic_api,
    provider_uses_responses_api,
    resolve_api_key,
)


class OpenAIService:
    """多模型服务类"""
    
    def __init__(self):
        """初始化模型服务，从 config_manager 读取配置"""
        # 从配置管理器加载配置
        config = config_manager.load_config()
        self.provider = config.get('provider', DEFAULT_PROVIDER)
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', '')
        self.model_name = config.get('model_name', 'gpt-4.1-mini')
        self.normalized_base_url = normalize_base_url(self.provider, self.base_url)
        self.base_url_candidates = get_base_url_candidates(self.provider, self.base_url)
        self.resolved_base_url = (
            self.base_url_candidates[0]
            if self.base_url_candidates
            else (self.normalized_base_url or get_default_base_url(self.provider))
        )
        self.uses_anthropic_api = provider_uses_anthropic_api(self.provider, self.model_name)
        self.uses_responses_api = provider_uses_responses_api(self.provider, self.model_name)

        # 统一走 OpenAI SDK，兼容 OpenAI / Claude / Gemini / DeepSeek / Ollama 等兼容端点
        self.client = self._create_client(self.resolved_base_url)

    def _create_client(self, base_url: str | None) -> openai.AsyncOpenAI:
        """按指定 Base URL 创建客户端实例"""
        return openai.AsyncOpenAI(
            api_key=resolve_api_key(self.provider, self.api_key),
            base_url=base_url if base_url else None
        )

    def _iter_base_urls(self) -> list[str | None]:
        """获取本次请求应尝试的 Base URL 列表"""
        if self.provider in {"custom", "anthropic"} and self.base_url_candidates:
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

    def _get_openai_http_headers(self) -> dict[str, str]:
        """构造 OpenAI 兼容协议所需请求头"""
        return {
            "Authorization": f"Bearer {resolve_api_key(self.provider, self.api_key)}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    @staticmethod
    def _extract_openai_content(payload: dict[str, Any]) -> str:
        """从 OpenAI 兼容响应中提取文本内容"""
        choices = payload.get("choices") or []
        if not choices:
            return ""

        choice = choices[0] or {}
        delta = choice.get("delta") or {}
        if delta.get("content"):
            return str(delta["content"])

        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            return "".join(text_parts)

        return ""

    async def _resolve_custom_model_name(self) -> str:
        """为 custom provider 自动纠正失效模型名，避免沿用陈旧配置"""
        if self.provider != "custom":
            return self.model_name

        try:
            available_models = await self._get_openai_compatible_models_http()
        except Exception:
            return self.model_name

        if not available_models or self.model_name in available_models:
            return self.model_name

        normalized_requested = (self.model_name or "").lower()
        family_tokens = [token for token in re.split(r"[-_/.:]", normalized_requested) if len(token) >= 3]

        fallback_model = next(
            (
                model
                for model in available_models
                if any(token in model.lower() for token in family_tokens)
            ),
            None,
        )
        if fallback_model is None:
            fallback_model = next((model for model in available_models if "sonnet" in model.lower()), None)
        if fallback_model is None:
            fallback_model = available_models[0]

        print(f"custom provider 检测到无效模型 {self.model_name}，自动切换为 {fallback_model}")
        self.model_name = fallback_model
        return self.model_name
    
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        if not provider_supports_model_listing(self.provider):
            return get_default_models(self.provider)

        if self.uses_anthropic_api:
            return await self._get_anthropic_models()

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            client = self._create_client(candidate)
            try:
                models = await client.models.list()
                self.client = client
                self.resolved_base_url = candidate or ""
                chat_models = []
                for model in models.data:
                    model_id = model.id.lower()
                    if any(keyword in model_id for keyword in [
                        'gpt', 'claude', 'chat', 'llama', 'qwen', 'deepseek',
                        'gemini', 'moonshot', 'kimi', 'glm', 'mistral', 'codex', 'gpt-5',
                    ]):
                        chat_models.append(model.id)
                normalized_models = sorted(list(set(chat_models)))
                if normalized_models:
                    return normalized_models

                fallback_models = get_default_models(self.provider)
                if fallback_models:
                    return fallback_models
                raise Exception("未找到可用的对话模型")
            except Exception as e:
                last_error = e

        if self.provider == "custom":
            try:
                return await self._get_openai_compatible_models_http()
            except Exception as http_error:
                last_error = http_error
            try:
                return await self._get_anthropic_models()
            except Exception as anthropic_error:
                last_error = anthropic_error
            raise Exception(
                "自定义端点没有返回可用模型列表。请确认 Base URL 指向兼容 OpenAI 的根路径（通常是 /v1），"
                "或该地址本身是 Claude 原生网关。"
            ) from last_error

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
        response_format: dict = None
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成请求 - 真正的异步实现"""
        if self.provider == "custom":
            await self._resolve_custom_model_name()

        if self.uses_anthropic_api:
            async for chunk in self._stream_anthropic_completion(
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            ):
                yield chunk
            return

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            client = self._create_client(candidate)
            try:
                self.client = client
                self.resolved_base_url = candidate or ""

                if self.uses_responses_api:
                    async for chunk in self._stream_responses_completion(
                        messages=messages,
                        temperature=temperature,
                        response_format=response_format,
                    ):
                        yield chunk
                    return

                stream = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    **({"response_format": response_format} if response_format is not None else {})
                )

                async for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                last_error = e

        if self.provider == "custom":
            try:
                async for chunk in self._stream_openai_compatible_completion(
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                ):
                    yield chunk
                return
            except Exception as http_error:
                last_error = http_error

            try:
                async for chunk in self._stream_anthropic_completion(
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                ):
                    yield chunk
                return
            except Exception as anthropic_error:
                last_error = anthropic_error
            raise Exception(
                "自定义端点调用失败，请确认它是 OpenAI 兼容根路径（通常是 /v1）或 Claude 原生 /v1/messages 网关，"
                "并检查模型名与 API Key 是否正确。"
                + (f" 原始错误: {str(last_error)}" if last_error else "")
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

    async def _get_openai_compatible_models_http(self) -> List[str]:
        """使用原生 HTTP 获取 OpenAI 兼容模型列表，兼容被 SDK 拦截的网关"""
        headers = self._get_openai_http_headers()
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
                            normalized_id = model_id.lower()
                            if any(keyword in normalized_id for keyword in [
                                "gpt", "claude", "chat", "llama", "qwen", "deepseek",
                                "gemini", "moonshot", "kimi", "glm", "mistral", "codex", "gpt-5",
                            ]):
                                models.append(model_id)

                        normalized_models = sorted(list(set(models)))
                        if normalized_models:
                            self.resolved_base_url = candidate or ""
                            return normalized_models

                        raise Exception("未找到可用的对话模型")
            except Exception as e:
                last_error = e

        raise Exception(f"HTTP 模型列表获取失败: {str(last_error)}") from last_error

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

    async def _stream_openai_compatible_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """使用原生 HTTP 调用 OpenAI 兼容聊天接口，兼容被 SDK 拦截的网关"""
        headers = self._get_openai_http_headers()
        body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if response_format is not None:
            body["response_format"] = response_format

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            endpoint = self._join_endpoint(candidate or "", "/chat/completions", force_v1=True)
            try:
                timeout = aiohttp.ClientTimeout(total=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(endpoint, headers=headers, json=body) as response:
                        payload = await response.text() if response.content_type == "application/json" else None
                        if response.status >= 400:
                            error_text = payload if payload is not None else await response.text()
                            raise Exception(error_text[:1000])

                        if payload is not None:
                            data = json.loads(payload)
                            content = self._extract_openai_content(data)
                            if not content:
                                raise Exception("OpenAI 兼容接口返回内容为空")
                            self.resolved_base_url = candidate or ""
                            yield content
                            return

                        async for raw_line in response.content:
                            line = raw_line.decode("utf-8", errors="ignore").strip()
                            if not line or not line.startswith("data: "):
                                continue

                            data_line = line[6:]
                            if data_line == "[DONE]":
                                self.resolved_base_url = candidate or ""
                                return

                            chunk_payload = json.loads(data_line)
                            content = self._extract_openai_content(chunk_payload)
                            if content:
                                yield content

                        self.resolved_base_url = candidate or ""
                        return
            except Exception as e:
                last_error = e

        raise Exception(f"OpenAI 兼容接口调用失败: {str(last_error)}") from last_error

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
    ) -> str:
        """收集流式返回的文本到一个完整字符串"""
        full_content = ""
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=temperature,
            response_format=response_format,
        ):
            full_content += chunk
        return full_content

    @staticmethod
    def _ensure_json_only_messages(messages: list) -> list:
        """为不支持 response_format 的模型补一层纯 JSON 输出约束"""
        json_rule = "输出要求：只返回合法 JSON，不要输出 ```json 代码块，不要输出任何解释、前言或结语。"
        normalized_messages = [dict(message) for message in messages]

        for index, message in enumerate(normalized_messages):
            if message.get("role") in {"system", "developer"}:
                content = str(message.get("content", "")).strip()
                normalized_messages[index]["content"] = f"{content}\n\n{json_rule}" if content else json_rule
                return normalized_messages

        return [{"role": "system", "content": json_rule}, *normalized_messages]

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
        active_messages = messages
        active_response_format = response_format
        response_format_fallback_used = False

        while True:
            try:
                full_content = await self._collect_stream_text(
                    active_messages,
                    temperature=temperature,
                    response_format=active_response_format,
                )
            except Exception as e:
                if active_response_format is not None and not response_format_fallback_used:
                    response_format_fallback_used = True
                    active_response_format = None
                    active_messages = self._ensure_json_only_messages(messages)
                    last_error_msg = str(e)
                    print(f"{log_prefix or 'JSON生成'} response_format 不兼容，回退到纯提示词 JSON 模式：{last_error_msg}")
                    continue
                raise

            normalized_content = extract_json_string(str(full_content))
            isok, error_msg = check_json(normalized_content, schema)
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

    async def generate_content_for_outline(self, outline: Dict[str, Any], project_overview: str = "") -> Dict[str, Any]:
        """为目录结构生成内容"""
        try:
            if not isinstance(outline, dict) or 'outline' not in outline:
                raise Exception("无效的outline数据格式")
            
            # 深拷贝outline数据
            import copy
            result_outline = copy.deepcopy(outline)
            
            # 递归处理目录
            await self._process_outline_recursive(result_outline['outline'], [], project_overview)
            
            return result_outline
            
        except Exception as e:
            raise Exception(f"处理过程中发生错误: {str(e)}")
    
    async def _process_outline_recursive(self, chapters: list, parent_chapters: list = None, project_overview: str = ""):
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
                    project_overview
                ):
                    content += chunk
                if content:
                    chapter['content'] = content
            else:
                # 递归处理子章节
                await self._process_outline_recursive(chapter['children'], current_parent_chapters, project_overview)
    
    async def _generate_chapter_content(self, chapter: dict, parent_chapters: list = None, sibling_chapters: list = None, project_overview: str = "") -> AsyncGenerator[str, None]:
        """
        为单个章节流式生成内容

        Args:
            chapter: 章节数据
            parent_chapters: 上级章节列表，每个元素包含章节id、标题和描述
            sibling_chapters: 同级章节列表，避免内容重复
            project_overview: 项目概述信息，提供项目背景和要求

        Yields:
            生成的内容流
        """
        try:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            chapter_description = chapter.get('description', '')

            # 构建提示词
            system_prompt = """你是一个专业的标书编写专家，负责为投标文件的技术标部分生成具体内容。

要求：
1. 内容要专业、准确，与章节标题和描述保持一致
2. 这是技术方案，不是宣传报告，注意朴实无华，不要假大空
3. 语言要正式、规范，符合标书写作要求，但不要使用奇怪的连接词，不要让人觉得内容像是AI生成的
4. 内容要详细具体，避免空泛的描述
5. 注意避免与同级章节内容重复，保持内容的独特性和互补性
6. 直接返回章节内容，不生成标题，不要任何额外说明或格式标记
"""

            # 构建上下文信息
            context_info = ""
            
            # 上级章节信息
            if parent_chapters:
                context_info += "上级章节信息：\n"
                for parent in parent_chapters:
                    context_info += f"- {parent['id']} {parent['title']}\n  {parent['description']}\n"
            
            # 同级章节信息（排除当前章节）
            if sibling_chapters:
                context_info += "同级章节信息（请避免内容重复）：\n"
                for sibling in sibling_chapters:
                    if sibling.get('id') != chapter_id:  # 排除当前章节
                        context_info += f"- {sibling.get('id', 'unknown')} {sibling.get('title', '未命名')}\n  {sibling.get('description', '')}\n"

            # 构建用户提示词
            project_info = ""
            if project_overview.strip():
                project_info = f"项目概述信息：\n{project_overview}\n\n"
            
            user_prompt = f"""请为以下标书章节生成具体内容：

{project_info}{context_info if context_info else ''}当前章节信息：
章节ID: {chapter_id}
章节标题: {chapter_title}
章节描述: {chapter_description}

请根据项目概述信息和上述章节层级关系，生成详细的专业内容，确保与上级章节的内容逻辑相承，同时避免与同级章节内容重复，突出本章节的独特性和技术方案的优势。"""

            # 调用AI流式生成内容
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 流式返回生成的文本
            async for chunk in self.stream_chat_completion(messages, temperature=0.7):
                yield chunk

        except Exception as e:
            print(f"生成章节内容时出错: {str(e)}")
            raise Exception(f"生成章节内容时出错: {str(e)}") from e

    def _preferred_json_response_format(self) -> dict[str, str] | None:
        """自定义网关优先使用纯提示词约束，减少对 response_format 的依赖"""
        if self.provider == "custom":
            return None
        return {"type": "json_object"}

    @staticmethod
    def _build_compact_chapter_schema(
        level1_title: str,
        level1_index: int,
        level2_count: int,
        level3_count: int,
    ) -> Dict[str, Any]:
        """构建轻量化单章目录骨架，降低单次生成复杂度"""
        chapter = {
            "id": str(level1_index),
            "title": level1_title,
            "description": "",
            "children": [],
        }

        for level2_index in range(1, level2_count + 1):
            section = {
                "id": f"{level1_index}.{level2_index}",
                "title": "",
                "description": "",
                "children": [],
            }
            for level3_index in range(1, level3_count + 1):
                section["children"].append({
                    "id": f"{level1_index}.{level2_index}.{level3_index}",
                    "title": "",
                    "description": "",
                })
            chapter["children"].append(section)

        return chapter

    async def _generate_compact_level1_titles(self, overview: str, requirements: str) -> list[dict[str, str]]:
        """使用短提示词生成一级目录，兼容稳定性较差的代理网关"""
        schema = [
            {
                "rating_item": "",
                "new_title": "",
            }
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是标书专家。只输出 JSON 数组。"
                    "每个元素必须包含 rating_item 和 new_title 两个字段。"
                    "根据评分要求，为每个评分点生成一个更专业的一级章节标题。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"overview:\n{overview}\n\n"
                    f"requirements:\n{requirements}\n\n"
                    "要求：标题数量与核心评分点对应；标题专业、简洁；不要输出任何解释。"
                ),
            },
        ]

        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=json.dumps(schema, ensure_ascii=False),
            max_retries=2,
            temperature=0.2,
            response_format=self._preferred_json_response_format(),
            log_prefix="一级目录",
            raise_on_fail=True,
        )

        level1_nodes = json.loads(full_content.strip())
        if not isinstance(level1_nodes, list) or not level1_nodes:
            raise Exception("一级目录生成结果为空")
        return level1_nodes

    async def _generate_compact_level1_outline(
        self,
        level1_index: int,
        level1_title: str,
        overview: str,
        requirements: str,
        other_titles: list[str],
    ) -> Dict[str, Any]:
        """逐章补全二三级目录，避免一次性生成整棵目录导致代理 502"""
        schema_variants = [
            self._build_compact_chapter_schema(level1_title, level1_index, 3 if level1_index <= 2 else 2, 2),
            self._build_compact_chapter_schema(level1_title, level1_index, 2, 2),
            self._build_compact_chapter_schema(level1_title, level1_index, 2, 1),
        ]
        other_outline = "\n".join(f"- {title}" for title in other_titles if title != level1_title) or "无"
        last_error: Exception | None = None

        for schema in schema_variants:
            schema_json = json.dumps(schema, ensure_ascii=False)
            messages = [
                {
                    "role": "system",
                    "content": "你是标书专家。只输出合法 JSON，不要代码块，不要解释。",
                },
                {
                    "role": "user",
                    "content": (
                        "请在给定 JSON 结构中补全空的 title 和 description，保持 id 和层级结构不变，"
                        "不要修改一级标题。二级标题要围绕一级标题展开，三级标题要细化二级标题，"
                        "并尽量避免与其他章节重复。\n\n"
                        f"overview:\n{overview}\n\n"
                        f"requirements:\n{requirements}\n\n"
                        f"other_titles:\n{other_outline}\n\n"
                        f"json:\n{schema_json}"
                    ),
                },
            ]

            try:
                full_content = await self._generate_with_json_check(
                    messages=messages,
                    schema=schema_json,
                    max_retries=2,
                    temperature=0.2,
                    response_format=self._preferred_json_response_format(),
                    log_prefix=f"第{level1_index}章目录",
                    raise_on_fail=True,
                )
                return json.loads(full_content.strip())
            except Exception as error:
                last_error = error

        raise Exception(f"第{level1_index}章目录生成失败: {str(last_error)}") from last_error

    async def generate_outline_compact(self, overview: str, requirements: str) -> Dict[str, Any]:
        """轻量化分步生成目录，优先保证跨模型/跨网关稳定性"""
        level1_nodes = await self._generate_compact_level1_titles(overview, requirements)
        normalized_titles = [
            (node.get("new_title") or node.get("rating_item") or f"第{index + 1}章").strip()
            for index, node in enumerate(level1_nodes)
        ]

        outline: list[dict[str, Any]] = []
        for index, title in enumerate(normalized_titles, start=1):
            outline.append(
                await self._generate_compact_level1_outline(
                    level1_index=index,
                    level1_title=title,
                    overview=overview,
                    requirements=requirements,
                    other_titles=normalized_titles,
                )
            )
            if self.provider == "custom":
                await asyncio.sleep(0.2)

        return {"outline": outline}

    async def generate_outline_v2(self, overview: str, requirements: str) -> Dict[str, Any]:
        return await self.generate_outline_compact(overview, requirements)
    
    async def process_level1_node(self, i, level1_node, nodes_distribution, level_l1, overview, requirements):
        """处理单个一级节点的函数"""

        # 生成json
        json_outline = generate_one_outline_json_by_level1(level1_node["new_title"], i + 1, nodes_distribution)
        print(f"正在处理第{i+1}章: {level1_node['new_title']}")
        
        # 其他标题
        other_outline = "\n".join([f"{j+1}. {node['new_title']}" 
                            for j, node in enumerate(level_l1) 
                            if j!= i])

        system_prompt = f"""
    ### 角色
    你是专业的标书编写专家，擅长根据项目需求编写标书。
    
    ### 任务
    1. 根据得到项目概述(overview)、评分要求(requirements)补全标书的提纲的二三级目录
    
    ### 说明
    1. 你将会得到一段json，这是提纲的其中一个章节，你需要再原结构上补全标题(title)和描述(description)
    2. 二级标题根据一级标题撰写,三级标题根据二级标题撰写
    3. 补全的内容要参考项目概述(overview)、评分要求(requirements)等项目信息
    4. 你还会收到其他章节的标题(other_outline)，你需要确保本章节的内容不会包含其他章节的内容
    
    ### 注意事项
    在原json上补全信息，禁止修改json结构，禁止修改一级标题

    ### Output Format in JSON
    {json_outline}

    """
        user_prompt = f"""
    ### 项目信息

    <overview>
    {overview}
    </overview>

    <requirements>
    {requirements}
    </requirements>
    
    <other_outline>
    {other_outline}
    </other_outline>


    直接返回json，不要任何额外说明或格式标记

    """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时不抛异常，保持原有“返回最后一次结果”的行为）
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=json_outline,
            max_retries=3,
            temperature=0.7,
            response_format={"type": "json_object"},
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )

        return json.loads(full_content.strip())
