"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ConfigRequest(BaseModel):
    """模型配置请求"""
    model_config = {"protected_namespaces": ()}
    
    provider: str = Field("litellm", description="模型供应商，当前固定为 LiteLLM Proxy")
    api_key: str = Field("", description="API密钥")
    base_url: Optional[str] = Field(None, description="Base URL")
    model_name: str = Field("", description="模型名称")
    api_mode: str = Field("chat", description="API协议模式，当前固定为 OpenAI Chat Completions")


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    message: str


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[str]
    success: bool
    message: str = ""


class ProviderCheckItem(BaseModel):
    """模型端点探测结果"""
    stage: str
    success: bool
    detail: str = ""
    url: Optional[str] = None
    http_status: Optional[int] = None
    model_name: Optional[str] = None
    models: Optional[List[str]] = None
    sample: Optional[str] = None


class ProviderVerifyResponse(BaseModel):
    """模型端点验证响应"""
    success: bool
    message: str
    provider: str
    normalized_base_url: str = ""
    resolved_base_url: str = ""
    base_url_candidates: List[str] = Field(default_factory=list)
    model_name: str = ""
    api_mode: str = "auto"
    checks: List[ProviderCheckItem] = Field(default_factory=list)
