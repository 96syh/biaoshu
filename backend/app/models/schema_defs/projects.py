"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ProjectDraftRequest(BaseModel):
    """项目草稿保存请求"""
    project_id: Optional[str] = Field(None, description="项目 ID；为空时使用当前激活项目或新建")
    draft: Dict[str, Any] = Field(default_factory=dict, description="完整项目草稿 JSON")
    activate: bool = Field(True, description="保存后是否设为当前项目")


class ProjectCreateRequest(BaseModel):
    """新建项目请求"""
    draft: Dict[str, Any] = Field(default_factory=dict, description="可选初始草稿")


class ProjectRecord(BaseModel):
    """项目数据库记录"""
    id: str
    title: str
    createdAt: str
    updatedAt: str
    completed: int = 0
    total: int = 0
    wordCount: int = 0
    draft: Dict[str, Any] = Field(default_factory=dict)


class ProjectResponse(BaseModel):
    """项目 API 响应"""
    success: bool
    message: str = ""
    project: Optional[ProjectRecord] = None
    projects: List[ProjectRecord] = Field(default_factory=list)
