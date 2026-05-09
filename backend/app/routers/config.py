"""配置相关API路由"""
from fastapi import APIRouter, HTTPException
from ..models.schemas import ConfigRequest, ConfigResponse, ModelListResponse, ProviderVerifyResponse
from ..services.openai_service import OpenAIService
from ..services.model_runtime_monitor import ModelRuntimeMonitor
from ..utils.config_manager import config_manager
from ..utils.provider_registry import (
    DEFAULT_PROVIDER,
    get_default_models,
    get_provider_auth_error,
    get_provider_api_mode,
    normalize_base_url,
    provider_requires_api_key,
)

router = APIRouter(prefix="/api/config", tags=["配置管理"])


def _litellm_config_payload(config: ConfigRequest) -> dict:
    """将所有模型配置统一收敛到 LiteLLM Proxy + OpenAI Chat Completions。"""
    return {
        "provider": DEFAULT_PROVIDER,
        "api_key": config.api_key,
        "base_url": normalize_base_url(DEFAULT_PROVIDER, config.base_url or ""),
        "model_name": config.model_name,
        "api_mode": get_provider_api_mode(DEFAULT_PROVIDER, "chat"),
    }


@router.post("/save", response_model=ConfigResponse)
async def save_config(config: ConfigRequest):
    """保存模型配置"""
    try:
        runtime_config = _litellm_config_payload(config)
        success = config_manager.save_config(
            provider=runtime_config["provider"],
            api_key=runtime_config["api_key"],
            base_url=runtime_config["base_url"],
            model_name=runtime_config["model_name"],
            api_mode=runtime_config["api_mode"],
        )
        
        if success:
            return ConfigResponse(success=True, message="配置保存成功")
        else:
            return ConfigResponse(success=False, message="配置保存失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置时发生错误: {str(e)}")


@router.get("/load", response_model=dict)
async def load_config():
    """加载保存的配置"""
    try:
        config = dict(config_manager.load_config())
        config["provider"] = DEFAULT_PROVIDER
        config["base_url"] = normalize_base_url(DEFAULT_PROVIDER, config.get("base_url") or "")
        config["api_mode"] = get_provider_api_mode(DEFAULT_PROVIDER, "chat")
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载配置时发生错误: {str(e)}")


@router.get("/model-runtime", response_model=dict)
async def get_model_runtime():
    """返回当前模型调用运行状态，用于前端和启动脚本监听。"""
    return {
        "success": True,
        **ModelRuntimeMonitor.snapshot(),
    }


@router.post("/models", response_model=ModelListResponse)
async def get_available_models(config: ConfigRequest):
    """获取可用的模型列表"""
    try:
        runtime_config = _litellm_config_payload(config)
        if provider_requires_api_key(runtime_config["provider"]) and not runtime_config["api_key"]:
            return ModelListResponse(
                models=[],
                success=False,
                message="当前供应商需要先输入 API Key"
            )

        openai_service = OpenAIService(config=runtime_config)
        
        # 获取模型列表
        models = await openai_service.get_available_models()
        
        return ModelListResponse(
            models=models,
            success=True,
            message=f"获取到 {len(models)} 个模型"
        )
        
    except Exception as e:
        fallback_models = get_default_models(DEFAULT_PROVIDER)
        if fallback_models:
            return ModelListResponse(
                models=fallback_models,
                success=True,
                message=f"未能拉取远端模型，已回退到推荐模型列表：{str(e)}"
            )
        return ModelListResponse(
            models=[],
            success=False,
            message=f"获取模型列表失败: {str(e)}"
        )


@router.post("/verify", response_model=ProviderVerifyResponse)
async def verify_provider(config: ConfigRequest):
    """验证当前供应商配置是否真的可连通、可取模型、可发起对话请求"""
    try:
        runtime_config = _litellm_config_payload(config)
        auth_error = get_provider_auth_error(runtime_config["provider"], runtime_config["api_key"])
        if auth_error:
            return ProviderVerifyResponse(
                success=False,
                message=auth_error,
                provider=runtime_config["provider"],
                normalized_base_url=runtime_config["base_url"],
                resolved_base_url="",
                base_url_candidates=[],
                model_name=runtime_config["model_name"],
                api_mode=runtime_config["api_mode"],
                checks=[],
            )

        openai_service = OpenAIService(config=runtime_config)
        result = await openai_service.verify_current_endpoint()
        result["success"] = any(
            check.get("stage") == "chat" and check.get("success")
            for check in result.get("checks", [])
        )
        return ProviderVerifyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证模型端点时发生错误: {str(e)}")
