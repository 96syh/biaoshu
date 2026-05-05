"""项目数据库 API。"""
from fastapi import APIRouter, HTTPException

from ..models.schemas import ProjectCreateRequest, ProjectDraftRequest, ProjectResponse
from ..services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["项目数据库"])


@router.get("", response_model=ProjectResponse)
async def list_projects():
    """列出最近项目。"""
    projects = ProjectService.list_projects()
    return ProjectResponse(success=True, projects=projects)


@router.get("/active", response_model=ProjectResponse)
async def get_active_project():
    """读取当前激活项目。"""
    project = ProjectService.get_active_project()
    return ProjectResponse(success=True, project=project)


@router.post("", response_model=ProjectResponse)
async def create_project(request: ProjectCreateRequest):
    """新建项目并设为当前项目。"""
    project = ProjectService.create_project(request.draft)
    return ProjectResponse(success=True, message="项目已创建", project=project)


@router.put("/active", response_model=ProjectResponse)
async def save_active_project(request: ProjectDraftRequest):
    """保存当前项目草稿。"""
    project = ProjectService.upsert_project(
        draft=request.draft,
        project_id=request.project_id,
        activate=request.activate,
    )
    return ProjectResponse(success=True, message="项目草稿已保存", project=project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """读取指定项目。"""
    project = ProjectService.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectResponse(success=True, project=project)


@router.post("/{project_id}/activate", response_model=ProjectResponse)
async def activate_project(project_id: str):
    """切换当前项目。"""
    project = ProjectService.activate_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectResponse(success=True, message="项目已切换", project=project)


@router.delete("/{project_id}", response_model=ProjectResponse)
async def delete_project(project_id: str):
    """删除指定项目。"""
    deleted = ProjectService.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectResponse(success=True, message="项目已删除")
