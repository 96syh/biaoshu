"""配置相关API路由"""
from fastapi import APIRouter, HTTPException
from ..models.schemas import ConfigRequest, ConfigResponse, ModelListResponse, ProviderVerifyResponse
from ..services.openai_service import OpenAIService
from ..utils.config_manager import config_manager
from ..utils.provider_registry import (
    get_default_models,
    get_provider_auth_error,
    get_provider_api_mode,
    normalize_base_url,
    provider_requires_api_key,
)

router = APIRouter(prefix="/api/config", tags=["配置管理"])


@router.post("/save", response_model=ConfigResponse)
async def save_config(config: ConfigRequest):
    """保存模型配置"""
    try:
        normalized_base_url = normalize_base_url(config.provider, config.base_url or "")
        success = config_manager.save_config(
            provider=config.provider,
            api_key=config.api_key,
            base_url=normalized_base_url,
            model_name=config.model_name,
            api_mode=get_provider_api_mode(config.provider, config.api_mode),
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
        config = config_manager.load_config()
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载配置时发生错误: {str(e)}")


@router.post("/models", response_model=ModelListResponse)
async def get_available_models(config: ConfigRequest):
    """获取可用的模型列表"""
    try:
        if provider_requires_api_key(config.provider) and not config.api_key:
            return ModelListResponse(
                models=[],
                success=False,
                message="当前供应商需要先输入 API Key"
            )

        normalized_base_url = normalize_base_url(config.provider, config.base_url or "")

        # 临时保存配置以供OpenAI服务使用
        temp_saved = config_manager.save_config(
            provider=config.provider,
            api_key=config.api_key,
            base_url=normalized_base_url,
            model_name=config.model_name,
            api_mode=get_provider_api_mode(config.provider, config.api_mode),
        )

        if not temp_saved:
            return ModelListResponse(
                models=[],
                success=False,
                message="保存临时配置失败"
            )

        # 创建OpenAI服务实例
        openai_service = OpenAIService()
        
        # 获取模型列表
        models = await openai_service.get_available_models()
        
        return ModelListResponse(
            models=models,
            success=True,
            message=f"获取到 {len(models)} 个模型"
        )
        
    except Exception as e:
        if config.provider == "custom":
            return ModelListResponse(
                models=[],
                success=False,
                message=f"未能从自定义端点同步模型列表：{str(e)}"
            )
        fallback_models = get_default_models(config.provider)
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
        auth_error = get_provider_auth_error(config.provider, config.api_key)
        if auth_error:
            return ProviderVerifyResponse(
                success=False,
                message=auth_error,
                provider=config.provider,
                normalized_base_url=normalize_base_url(config.provider, config.base_url or ""),
                resolved_base_url="",
                base_url_candidates=[],
                model_name=config.model_name,
                api_mode=get_provider_api_mode(config.provider, config.api_mode),
                checks=[],
            )

        normalized_base_url = normalize_base_url(config.provider, config.base_url or "")
        runtime_config = {
            "provider": config.provider,
            "api_key": config.api_key,
            "base_url": normalized_base_url,
            "model_name": config.model_name,
            "api_mode": get_provider_api_mode(config.provider, config.api_mode),
        }

        openai_service = OpenAIService(config=runtime_config)
        result = await openai_service.verify_current_endpoint()
        result["success"] = any(
            check.get("stage") == "chat" and check.get("success")
            for check in result.get("checks", [])
        )
        return ProviderVerifyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证模型端点时发生错误: {str(e)}")
