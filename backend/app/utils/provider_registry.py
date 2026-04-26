"""模型供应商预设与默认配置"""
from typing import Dict, Any
from urllib.parse import urlparse, urlunparse


DEFAULT_PROVIDER = "litellm"

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "litellm": {
        "label": "LiteLLM Proxy",
        "base_url": "http://localhost:4000/v1",
        "models": [],
        "requires_api_key": False,
        "supports_model_listing": True,
        "api_mode": "chat",
    },
}


def get_provider_preset(provider: str | None) -> Dict[str, Any]:
    """获取 provider 预设，不存在时回退到 OpenAI"""
    provider_id = (provider or DEFAULT_PROVIDER).lower()
    return PROVIDER_PRESETS.get(provider_id, PROVIDER_PRESETS[DEFAULT_PROVIDER])


def get_default_base_url(provider: str | None) -> str:
    """获取 provider 对应的默认 base_url"""
    return get_provider_preset(provider).get("base_url", "")


def get_default_models(provider: str | None) -> list[str]:
    """获取 provider 对应的推荐模型列表"""
    return list(get_provider_preset(provider).get("models", []))


def provider_requires_api_key(provider: str | None) -> bool:
    """判断 provider 是否默认要求 API Key"""
    return bool(get_provider_preset(provider).get("requires_api_key", True))


def get_provider_auth_error(provider: str | None, api_key: str | None) -> str | None:
    """根据 provider 规则返回鉴权错误信息"""
    if provider_requires_api_key(provider) and not api_key:
        provider_label = get_provider_preset(provider).get("label", "当前供应商")
        return f"{provider_label} 需要先配置 API Key"
    return None


def provider_supports_model_listing(provider: str | None) -> bool:
    """判断 provider 是否适合直接拉取远端模型列表"""
    return bool(get_provider_preset(provider).get("supports_model_listing", False))


def normalize_api_mode(api_mode: str | None) -> str:
    """规范化 API 协议模式"""
    normalized = (api_mode or "auto").strip().lower()
    return normalized if normalized in {"auto", "chat", "responses", "anthropic"} else "auto"


def get_provider_api_mode(provider: str | None, api_mode: str | None = None) -> str:
    """解析供应商最终 API 协议模式"""
    if (provider or DEFAULT_PROVIDER).lower() == "litellm":
        return "chat"

    explicit_mode = normalize_api_mode(api_mode)
    if explicit_mode != "auto":
        return explicit_mode

    preset_mode = get_provider_preset(provider).get("api_mode")
    if preset_mode in {"chat", "responses", "anthropic"}:
        return preset_mode
    return "auto"


def provider_uses_responses_api(
    provider: str | None,
    model_name: str | None,
    api_mode: str | None = None,
) -> bool:
    """判断当前 provider / model 是否应该走 Responses API"""
    resolved_mode = get_provider_api_mode(provider, api_mode)
    if (provider or DEFAULT_PROVIDER).lower() == "litellm":
        return False
    if resolved_mode == "responses":
        return True
    if resolved_mode in {"chat", "anthropic"}:
        return False

    normalized_model = (model_name or "").lower()
    return "codex" in normalized_model


def provider_uses_anthropic_api(
    provider: str | None,
    model_name: str | None,
    api_mode: str | None = None,
) -> bool:
    """判断当前 provider 是否应直接走 Anthropic 原生接口"""
    if (provider or DEFAULT_PROVIDER).lower() == "litellm":
        return False
    return get_provider_api_mode(provider, api_mode) == "anthropic"


def normalize_base_url(provider: str | None, base_url: str | None) -> str:
    """规范化用户输入的 Base URL，尽量修正为兼容 OpenAI SDK 的根路径"""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return ""

    provider_id = (provider or "").lower()
    if provider_id == "anthropic":
        parsed = urlparse(normalized)
        if not parsed.scheme or not parsed.netloc:
            return normalized

        path = parsed.path.rstrip("/")
        for suffix in ("/messages", "/models"):
            if path.endswith(suffix):
                path = path[: -len(suffix)]
                break
        if path.endswith("/v1"):
            path = path[: -len("/v1")]

        cleaned = parsed._replace(
            path=path.rstrip("/"),
            params="",
            query="",
            fragment="",
        )
        return urlunparse(cleaned).rstrip("/")

    if provider_id not in {"custom", "litellm"}:
        return normalized

    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return normalized

    path = parsed.path.rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/responses", "/messages", "/models"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break

    cleaned = parsed._replace(
        path=path.rstrip("/"),
        params="",
        query="",
        fragment="",
    )
    return urlunparse(cleaned).rstrip("/")


def get_base_url_candidates(provider: str | None, base_url: str | None) -> list[str]:
    """为自定义兼容端点生成候选 Base URL，覆盖常见的 /v1 差异"""
    normalized = normalize_base_url(provider, base_url)
    if not normalized:
        default_url = get_default_base_url(provider)
        return [default_url] if default_url else []

    candidates = [normalized]
    provider_id = (provider or "").lower()
    if provider_id not in {"custom", "anthropic", "litellm"}:
        return candidates

    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return candidates

    path = parsed.path.rstrip("/")
    has_version_path = path.endswith("/v1") or "/v1/" in path or path.endswith("/v1beta/openai")
    if not has_version_path:
        v1_path = f"{path}/v1" if path else "/v1"
        v1_url = urlunparse(parsed._replace(path=v1_path, params="", query="", fragment="")).rstrip("/")
        if v1_url not in candidates:
            candidates.append(v1_url)

    return candidates


def resolve_api_key(provider: str | None, api_key: str | None) -> str:
    """为不要求 API Key 的兼容端点提供占位值"""
    if api_key:
        return api_key
    if not provider_requires_api_key(provider):
        return "local-proxy"
    return ""
