"""文档处理相关API路由"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..models.schemas import (
    AnalysisReportRequest,
    AnalysisTaskControlRequest,
    AnalysisTaskControlResponse,
    AnalysisRequest,
    AnalysisType,
    ComplianceReviewRequest,
    ConsistencyRevisionRequest,
    DocumentBlocksPlanRequest,
    FileUploadResponse,
    VisualAssetGenerationRequest,
    VisualAssetGenerationResponse,
    WordExportRequest,
)
from ..services.file_service import FileService
from ..services.openai_service import OpenAIService
from ..services.visual_asset_service import generate_visual_asset_response
from ..services.word_export_service import create_word_export_response
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..utils.sse import sse_response
import json
import asyncio
import time
import uuid

router = APIRouter(prefix="/api/document", tags=["文档处理"])


class AnalysisTaskState:
    """Keep server-side control state for one standard-analysis SSE task."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.cancelled = False
        self.status = "running"
        self.current_step = 0


ANALYSIS_TASKS: dict[str, AnalysisTaskState] = {}


def _analysis_metric_count(report: dict, keys: tuple[str, ...]) -> int:
    return sum(len(report.get(key) or []) for key in keys)


def _analysis_stream_payload(
    task_state: AnalysisTaskState,
    step_index: int,
    detail: str,
    percent: int,
    status: str = "running",
    **extra,
) -> str:
    task_state.current_step = step_index
    task_state.status = status
    payload = {
        "chunk": "",
        "task_id": task_state.task_id,
        "step_index": step_index,
        "detail": detail,
        "percent": max(0, min(100, int(percent))),
        "status": status,
        **extra,
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

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
        parse_result = await FileService.process_uploaded_file_with_metadata(file)
        file_content = parse_result.get("file_content", "")
        parser_info = parse_result.get("parser_info", {})
        source_preview_html = parse_result.get("source_preview_html") or ""
        parser_name = parser_info.get("parser") or "unknown"
        fallback_note = "（已降级到内置解析器）" if parser_info.get("fallback_used") else ""
        
        return FileUploadResponse(
            success=True,
            message=f"文件 {file.filename} 上传成功，解析器：{parser_name}{fallback_note}，已在上传阶段转换为 {parser_info.get('format') or '文本'}",
            file_content=file_content,
            source_preview_html=source_preview_html,
            parser_info=parser_info,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return FileUploadResponse(
            success=False,
            message=f"文件处理失败: {str(e)}"
        )


@router.post("/analyze-stream")
async def analyze_document_stream(request: AnalysisRequest):
    """流式分析文档内容"""
    try:
        # 加载配置
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        # 创建OpenAI服务实例
        openai_service = OpenAIService()
        
        async def generate():
            try:
                if openai_service._force_local_fallback():
                    fallback_text = (
                        OpenAIService.fallback_overview(request.file_content)
                        if request.analysis_type == AnalysisType.OVERVIEW
                        else OpenAIService.fallback_requirements(request.file_content)
                    )
                    yield f"data: {json.dumps({'chunk': fallback_text}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                # 构建分析提示词
                if request.analysis_type == AnalysisType.OVERVIEW:
                    system_prompt = """你是一个专业的标书撰写专家。请分析用户发来的招标文件，提取并总结项目概述信息。
            
请重点关注以下方面：
1. 项目名称和基本信息
2. 项目背景和目的
3. 项目规模和预算
4. 项目时间安排
5. 项目要实施的具体内容
6. 主要技术特点
7. 其他关键要求

工作要求：
1. 保持提取信息的全面性和准确性，尽量使用原文内容，不要自己编写
2. 只关注与项目实施有关的内容，不提取商务信息
3. 直接返回整理好的项目概述，除此之外不返回任何其他内容
"""
                else:  # requirements
                    system_prompt = """你是一名专业的招标文件分析师，擅长从复杂的招标文档中高效提取“技术评分项”相关内容。请严格按照以下步骤和规则执行任务：
### 1. 目标定位
- 重点识别文档中与“技术评分”、“评标方法”、“评分标准”、“技术参数”、“技术要求”、“技术方案”、“技术部分”或“评审要素”相关的章节（如“第X章 评标方法”或“附件X：技术评分表”）。
- 一定不要提取商务、价格、资质等于技术类评分项无关的条目。
### 2. 提取内容要求
对每一项技术评分项，按以下结构化格式输出（若信息缺失，标注“未提及”），如果评分项不够明确，你需要根据上下文分析并也整理成如下格式：
【评分项名称】：<原文描述，保留专业术语>
【权重/分值】：<具体分值或占比，如“30分”或“40%”>
【评分标准】：<详细规则，如“≥95%得满分，每低1%扣0.5分”>
【数据来源】：<文档中的位置，如“第5.2.3条”或“附件3-表2”>

### 3. 处理规则
- **模糊表述**：有些招标文件格式不是很标准，没有明确的“技术评分表”，但一定都会有“技术评分”相关内容，请根据上下文判断评分项。
- **表格处理**：若评分项以表格形式呈现，按行提取，并标注“[表格数据]”。
- **分层结构**：若存在二级评分项（如“技术方案→子项1、子项2”），用缩进或编号体现层级关系。
- **单位统一**：将所有分值统一为“分”或“%”，并注明原文单位（如原文为“20点”则标注“[原文：20点]”）。

### 4. 输出示例
【评分项名称】：系统可用性 
【权重/分值】：25分 
【评分标准】：年平均故障时间≤1小时得满分；每增加1小时扣2分，最高扣10分。 
【数据来源】：附件4-技术评分细则（第3页） 

【评分项名称】：响应时间
【权重/分分】：15分 [原文：15%]
【评分标准】：≤50ms得满分；每增加10ms扣1分。
【数据来源】：第6.1.2条

### 5. 验证步骤
提取完成后，执行以下自检：
- [ ] 所有技术评分项是否覆盖（无遗漏）？
- [ ] 是否错误提取商务、价格、资质等于技术类评分项无关的条目？
- [ ] 权重总和是否与文档声明的技术分总分一致（如“技术部分共60分”）？

直接返回提取结果，除此之外不输出任何其他内容
"""
                
                analysis_type_cn = "项目概述" if request.analysis_type == AnalysisType.OVERVIEW else "技术评分要求"
                user_prompt = f"请分析以下招标文件内容，提取{analysis_type_cn}信息：\n\n{request.file_content}"
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # 流式返回分析结果
                try:
                    async for chunk in openai_service.stream_chat_completion(messages, temperature=0.3):
                        yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    if not openai_service._generation_fallbacks_enabled():
                        raise openai_service._fallback_disabled_error("文档分析", str(e)) from e
                    fallback_text = (
                        OpenAIService.fallback_overview(request.file_content)
                        if request.analysis_type == AnalysisType.OVERVIEW
                        else OpenAIService.fallback_requirements(request.file_content)
                    )
                    print(f"文档分析模型输出不可用，启用文本兜底分析：{str(e)}")
                    yield f"data: {json.dumps({'chunk': fallback_text}, ensure_ascii=False)}\n\n"
            except Exception as e:
                payload = {
                    "error": True,
                    "message": f"文档分析失败: {str(e)}",
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"
        
        return sse_response(generate())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档分析失败: {str(e)}")


@router.post("/analyze-report-stream")
async def analyze_report_stream(request: AnalysisReportRequest):
    """流式生成结构化标准解析报告"""
    try:
        request_id = uuid.uuid4().hex[:8]
        started_at = time.monotonic()
        task_state = AnalysisTaskState(request_id)
        ANALYSIS_TASKS[request_id] = task_state
        config = (
            request.config.model_dump(mode="json", exclude_none=True)
            if request.config
            else config_manager.load_config()
        )
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        openai_service = OpenAIService(config=config)
        print(
            f"标准解析报告[{request_id}] 开始："
            f"model={config.get('model_name')} base_url={config.get('base_url')} "
            f"file_chars={len(request.file_content or '')}",
            flush=True,
        )

        async def generate():
            compute_task = None
            final_report = None

            async def wait_if_paused() -> None:
                while not task_state.pause_event.is_set():
                    task_state.status = "paused"
                    if task_state.cancelled:
                        raise asyncio.CancelledError()
                    await asyncio.sleep(0.25)
                if task_state.cancelled:
                    raise asyncio.CancelledError()
                task_state.status = "running"

            try:
                yield _analysis_stream_payload(
                    task_state,
                    0,
                    "文件解析完成：MinerU Markdown 已进入标准解析队列",
                    12,
                )
                await wait_if_paused()
                yield _analysis_stream_payload(
                    task_state,
                    1,
                    "条款识别中：正在抽取项目基础信息和投标文件组成",
                    20,
                )
                compute_task = asyncio.create_task(
                    openai_service.generate_analysis_report(request.file_content)
                )
                heartbeat_count = 0

                while not compute_task.done():
                    await wait_if_paused()
                    yield _analysis_stream_payload(
                        task_state,
                        1,
                        "条款识别中：正在抽取项目基础信息和投标文件组成",
                        20,
                    )
                    heartbeat_count += 1
                    if heartbeat_count % 30 == 0:
                        print(
                            f"标准解析报告[{request_id}] 仍在生成："
                            f"{int(time.monotonic() - started_at)} 秒，心跳 {heartbeat_count} 次",
                            flush=True,
                        )
                    await asyncio.sleep(1)

                await wait_if_paused()
                final_report = await compute_task
                yield _analysis_stream_payload(
                    task_state,
                    1,
                    "条款识别完成：项目基础信息、投标文件组成和关键出处已抽取",
                    38,
                )
                await wait_if_paused()

                scoring_count = _analysis_metric_count(
                    final_report,
                    ("technical_scoring_items", "business_scoring_items", "price_scoring_items"),
                )
                yield _analysis_stream_payload(
                    task_state,
                    2,
                    f"评分项提取完成：识别 {scoring_count} 项技术、商务或报价评分规则",
                    58,
                )
                await wait_if_paused()

                compliance_count = _analysis_metric_count(
                    final_report,
                    (
                        "qualification_requirements",
                        "formal_response_requirements",
                        "mandatory_clauses",
                        "rejection_risks",
                        "required_materials",
                        "fixed_format_forms",
                        "signature_requirements",
                    ),
                )
                yield _analysis_stream_payload(
                    task_state,
                    3,
                    f"合规要求提取完成：识别 {compliance_count} 项资格、格式、签章、材料或废标风险",
                    78,
                )
                await wait_if_paused()

                yield _analysis_stream_payload(
                    task_state,
                    4,
                    "结果校验中：正在校验 JSON、响应矩阵和企业资料画像",
                    92,
                )
                report_json = json.dumps(final_report, ensure_ascii=False)
                print(
                    f"标准解析报告[{request_id}] 完成："
                    f"{int(time.monotonic() - started_at)} 秒，输出 {len(report_json)} 字符",
                    flush=True,
                )
                chunk_size = 256
                for index in range(0, len(report_json), chunk_size):
                    await wait_if_paused()
                    piece = report_json[index:index + chunk_size]
                    yield f"data: {json.dumps({'chunk': piece, 'task_id': request_id, 'step_index': 4, 'percent': 96, 'status': 'running'}, ensure_ascii=False)}\n\n"
                yield _analysis_stream_payload(
                    task_state,
                    4,
                    "标准解析完成：已写入项目、评分、风险和材料结构",
                    100,
                    "success",
                )
            except asyncio.CancelledError:
                if compute_task and not compute_task.done():
                    compute_task.cancel()
                if task_state.cancelled:
                    print(f"标准解析报告[{request_id}] 已停止", flush=True)
                    yield _analysis_stream_payload(
                        task_state,
                        task_state.current_step,
                        "标准解析已停止，可重新开始解析",
                        max(0, min(100, 0)),
                        "stopped",
                        stopped=True,
                    )
                else:
                    print(f"标准解析报告[{request_id}] SSE 连接被取消", flush=True)
                    raise
            except Exception as e:
                print(f"标准解析报告[{request_id}] 失败：{str(e)}", flush=True)
                payload = {
                    "chunk": "",
                    "task_id": request_id,
                    "step_index": task_state.current_step,
                    "percent": 100,
                    "status": "error",
                    "error": True,
                    "message": f"结构化解析报告生成失败: {str(e)}",
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            finally:
                ANALYSIS_TASKS.pop(request_id, None)

            yield "data: [DONE]\n\n"

        return sse_response(generate())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"结构化解析报告生成失败: {str(e)}")


@router.post("/analysis-task/{task_id}/control", response_model=AnalysisTaskControlResponse)
async def control_analysis_task(task_id: str, request: AnalysisTaskControlRequest):
    """Pause, resume, or stop a running standard-analysis task."""
    task_state = ANALYSIS_TASKS.get(task_id)
    if not task_state:
        raise HTTPException(status_code=404, detail="解析任务不存在或已结束")

    action = (request.action or "").strip().lower()
    if action == "pause":
        task_state.pause_event.clear()
        task_state.status = "paused"
        return AnalysisTaskControlResponse(success=True, message="标准解析已暂停", task_id=task_id, status=task_state.status)
    if action in {"resume", "continue"}:
        task_state.pause_event.set()
        task_state.status = "running"
        return AnalysisTaskControlResponse(success=True, message="标准解析已继续", task_id=task_id, status=task_state.status)
    if action == "stop":
        task_state.cancelled = True
        task_state.pause_event.set()
        task_state.status = "stopped"
        return AnalysisTaskControlResponse(success=True, message="标准解析已停止", task_id=task_id, status=task_state.status)

    raise HTTPException(status_code=400, detail="不支持的解析任务控制动作")


@router.post("/reference-style-upload")
async def reference_style_upload(file: UploadFile = File(...)):
    """上传成熟投标文件样例并生成可复用风格剖面"""
    try:
        file_kind = FileService.detect_upload_file_kind(file)
        if file_kind in (None, "doc"):
            return FileUploadResponse(success=False, message=FileService.get_upload_validation_message(file))

        parse_result = await FileService.process_uploaded_file_with_metadata(file)
        file_content = parse_result.get("file_content", "")
        parser_info = parse_result.get("parser_info", {})
        if (
            str(parser_info.get("parser") or "").lower() != "mineru"
            or str(parser_info.get("format") or "").lower() != "markdown"
        ):
            return FileUploadResponse(
                success=False,
                message="成熟样例必须先通过 MinerU 转换为 Markdown 后再生成模板剖面；请检查 MinerU 配置或将 YIBIAO_DOCUMENT_PARSER 设置为 mineru_strict。",
                parser_info=parser_info,
            )

        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        profile = await OpenAIService().generate_reference_bid_style_profile(file_content)
        image_assets = parser_info.get("image_assets") if isinstance(parser_info, dict) else []
        image_slots = profile.get("image_slots") if isinstance(profile, dict) else []
        if isinstance(image_assets, list) and isinstance(image_slots, list):
            for index, slot in enumerate(image_slots):
                if not isinstance(slot, dict) or index >= len(image_assets):
                    continue
                asset = image_assets[index] if isinstance(image_assets[index], dict) else {}
                if asset.get("url") and not slot.get("image_url"):
                    slot["image_url"] = asset.get("url")
                if asset.get("alt") and not slot.get("image_alt"):
                    slot["image_alt"] = asset.get("alt")
                if asset.get("source_path") and not slot.get("source_ref"):
                    slot["source_ref"] = asset.get("source_path")
        return FileUploadResponse(
            success=True,
            message=f"样例文件 {file.filename} 已通过 MinerU Markdown 解析，并生成写作模板剖面",
            file_content=file_content,
            parser_info=parser_info,
            reference_bid_style_profile=profile,
        )
    except HTTPException as e:
        return FileUploadResponse(success=False, message=e.detail)
    except Exception as e:
        return FileUploadResponse(success=False, message=f"样例解析失败: {str(e)}")


@router.post("/generate-visual-asset", response_model=VisualAssetGenerationResponse)
async def generate_visual_asset(request: VisualAssetGenerationRequest):
    """调用图片模型生成投标文件图表素材。"""
    return await generate_visual_asset_response(request)


@router.post("/document-blocks-plan-stream")
async def document_blocks_plan_stream(request: DocumentBlocksPlanRequest):
    """生成图表、表格、图片、承诺书和附件规划"""
    try:
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        async def generate():
            try:
                service = OpenAIService()
                compute_task = asyncio.create_task(service.generate_document_blocks_plan(
                    outline=[item.model_dump(mode="json") for item in request.outline],
                    analysis_report=request.analysis_report.model_dump(mode="json") if request.analysis_report else None,
                    response_matrix=request.response_matrix.model_dump(mode="json") if request.response_matrix else None,
                    reference_bid_style_profile=request.reference_bid_style_profile,
                    enterprise_materials=[item.model_dump(mode="json") for item in request.enterprise_materials],
                    asset_library=request.asset_library,
                ))
                while not compute_task.done():
                    yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)
                result_json = json.dumps(await compute_task, ensure_ascii=False)
                for index in range(0, len(result_json), 256):
                    yield f"data: {json.dumps({'chunk': result_json[index:index + 256]}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'chunk': '', 'error': True, 'message': f'图表素材规划失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return sse_response(generate())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图表素材规划失败: {str(e)}")


@router.post("/consistency-revision-stream")
async def consistency_revision_stream(request: ConsistencyRevisionRequest):
    """生成全文一致性修订报告"""
    try:
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        async def generate():
            try:
                service = OpenAIService()
                compute_task = asyncio.create_task(service.generate_consistency_revision_report(
                    full_bid_draft=[item.model_dump(mode="json") for item in request.full_bid_draft],
                    analysis_report=request.analysis_report.model_dump(mode="json") if request.analysis_report else None,
                    response_matrix=request.response_matrix.model_dump(mode="json") if request.response_matrix else None,
                    reference_bid_style_profile=request.reference_bid_style_profile,
                    document_blocks_plan=request.document_blocks_plan,
                ))
                while not compute_task.done():
                    yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)
                result_json = json.dumps(await compute_task, ensure_ascii=False)
                for index in range(0, len(result_json), 256):
                    yield f"data: {json.dumps({'chunk': result_json[index:index + 256]}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'chunk': '', 'error': True, 'message': f'全文一致性修订失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return sse_response(generate())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全文一致性修订失败: {str(e)}")


@router.post("/review-compliance-stream")
async def review_compliance_stream(request: ComplianceReviewRequest):
    """导出前执行覆盖性、缺料、废标风险和虚构风险审校"""
    try:
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        openai_service = OpenAIService()

        async def generate():
            try:
                compute_task = asyncio.create_task(
                    openai_service.generate_compliance_review(
                        outline=[item.model_dump(mode="json") for item in request.outline],
                        analysis_report=(
                            request.analysis_report.model_dump(mode="json")
                            if request.analysis_report else None
                        ),
                        response_matrix=(
                            request.response_matrix.model_dump(mode="json")
                            if request.response_matrix else None
                        ),
                        project_overview=request.project_overview or "",
                        reference_bid_style_profile=request.reference_bid_style_profile,
                        document_blocks_plan=request.document_blocks_plan,
                    )
                )

                while not compute_task.done():
                    yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)

                review_json = json.dumps(await compute_task, ensure_ascii=False)
                chunk_size = 256
                for index in range(0, len(review_json), chunk_size):
                    piece = review_json[index:index + chunk_size]
                    yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
            except Exception as e:
                payload = {
                    "chunk": "",
                    "error": True,
                    "message": f"导出前合规审校失败: {str(e)}",
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        return sse_response(generate())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出前合规审校失败: {str(e)}")


@router.post("/export-word")
async def export_word(request: WordExportRequest):
    """根据目录数据导出Word文档"""
    return await create_word_export_response(request)
