from fastapi import APIRouter, UploadFile, File, HTTPException
from ..models.schemas import FileUploadResponse
from ..services.file_service import FileService
from ..utils import prompt_manager
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..services.openai_service import OpenAIService

router = APIRouter(prefix="/api/expand", tags=["标书扩写"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传文档文件并提取文本内容"""
    try:
        file_kind = FileService.detect_upload_file_kind(file)
        if file_kind in (None, "doc"):
            return FileUploadResponse(
                success=False,
                message=FileService.get_upload_validation_message(file)
            )
        
        # 处理文件并提取文本
        file_content = await FileService.process_uploaded_file(file)

        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)
        
        # 提取目录
        openai_service = OpenAIService()
        messages = [
            {"role": "system", "content": prompt_manager.read_expand_outline_prompt()},
            {"role": "user", "content": file_content}
        ]
        full_content = ""
        async for chunk in openai_service.stream_chat_completion(messages, temperature=0.7, response_format={"type": "json_object"}):
            full_content += chunk
        return FileUploadResponse(
            success=True,
            message=f"文件 {file.filename} 上传成功",
            file_content=file_content,
            old_outline=full_content
        )
        
    except HTTPException as e:
        return FileUploadResponse(
            success=False,
            message=e.detail
        )
    except Exception as e:
        return FileUploadResponse(
            success=False,
            message=f"文件处理失败: {str(e)}"
        )
