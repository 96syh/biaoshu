"""Visual asset generation service for bid document figures."""
import json

import aiohttp
from fastapi import HTTPException

from ..config import settings
from ..models.schemas import VisualAssetGenerationRequest, VisualAssetGenerationResponse


def _json_excerpt(value, max_chars: int = 1800) -> str:
    try:
        text = json.dumps(value or {}, ensure_ascii=False, indent=2)
    except Exception:
        text = str(value or "")
    return text[:max_chars]


def _block_type_label(block_type: str) -> str:
    labels = {
        "org_chart": "项目组织架构图",
        "workflow_chart": "服务流程图",
        "image": "技术方案信息图",
        "material_attachment": "证明材料示意图",
    }
    return labels.get(block_type, "投标文件图表")


def build_visual_asset_prompt(request: VisualAssetGenerationRequest) -> str:
    """Build a bid-document visual prompt from the current block plan and mature sample profile."""
    block = request.block or {}
    block_type = str(block.get("block_type") or "image")
    block_name = str(block.get("block_name") or block.get("name") or _block_type_label(block_type))
    chart_schema = block.get("chart_schema") if isinstance(block.get("chart_schema"), dict) else {}
    table_schema = block.get("table_schema") if isinstance(block.get("table_schema"), dict) else {}
    reference_profile = request.reference_bid_style_profile or {}
    image_slots = reference_profile.get("image_slots") if isinstance(reference_profile, dict) else []
    table_models = reference_profile.get("table_models") if isinstance(reference_profile, dict) else []

    type_rules = {
        "org_chart": "采用经典组织架构图：上级在上、下级分层排列，用连线表达汇报关系，节点中只放岗位/职责短语。",
        "workflow_chart": "采用一页式流程图/阶段图：从左到右或自上而下展示阶段、关键动作、输入输出和责任主体，必要时使用判断菱形。",
        "image": "采用正式商务信息图：围绕方案结构、服务能力、技术路线或质量保障进行模块化展示。",
        "material_attachment": "采用材料清单/证据链示意图：展示材料来源、核验点、页码/附件位置和交付关系。",
    }
    rule = type_rules.get(block_type, type_rules["image"])

    return f"""生成一张可直接插入中文 Word 投标文件/技术标正文的正式图表图片。

图表类型：{_block_type_label(block_type)}
项目名称：{request.project_name or "投标项目"}
章节：{request.chapter_id} {request.chapter_title}
图表标题：{block_name}

内容依据：
- 当前图表规划块：
{_json_excerpt(block, 2600)}
- 当前图表结构 nodes/edges：
{_json_excerpt(chart_schema, 1800)}
- 表格/字段参考：
{_json_excerpt(table_schema, 1200)}
- 成熟样例中提取到的图片/素材位参考：
{_json_excerpt(image_slots, 1600)}
- 成熟样例中提取到的表格模型参考：
{_json_excerpt(table_models, 1200)}

版式要求：
1. {rule}
2. 白色背景，正式投标文件风格，扁平矢量图，不要照片质感，不要 3D，不要装饰性插画。
3. 主色使用深绿色、深灰、浅灰，少量蓝色作为辅助；整体克制、清晰、适合黑白打印。
4. 所有中文标签必须清晰可读，字体类似宋体/黑体，不要使用英文假字、乱码、无意义水印。
5. 图中只保留必要短语，避免长段落；如果内容多，用编号、阶段、层级和箭头表达。
6. 输出完整单张 PNG 构图，四周留白，适合放入 A4 纵向 Word 页面正文区域。
7. 不出现真实公司 Logo、印章、签名、人像、金额、日期、证书编号或无法确认的事实。
8. 不要生成封面、海报、宣传横幅或营销插画；必须是标书正文内部的图表素材。
"""


async def generate_visual_asset_response(request: VisualAssetGenerationRequest):
    """调用图片模型生成投标文件图表素材。"""
    api_url = settings.yibiao_image_api_url.strip()
    api_key = settings.yibiao_image_api_key.strip()
    model = settings.yibiao_image_model.strip() or "gpt-image-1"
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="图片生成未配置：请在后端环境变量 YIBIAO_IMAGE_API_KEY 中设置图片模型密钥。",
        )

    prompt = build_visual_asset_prompt(request)
    payload = {
        "model": model,
        "prompt": prompt,
        "size": request.size or "1536x1024",
        "n": 1,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=int(settings.yibiao_image_timeout_seconds))
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(api_url, headers=headers, json=payload) as response:
                response_text = await response.text()
                if response.status >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=f"图片模型调用失败，HTTP {response.status}: {response_text[:500]}",
                    )
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=502, detail="图片模型返回了非 JSON 响应")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"图片模型调用失败: {str(e)}")

    result_dict = result if isinstance(result, dict) else {}
    data_items = result_dict.get("data") if isinstance(result_dict.get("data"), list) else []
    first = data_items[0] if data_items else {}
    image_url = str(first.get("url") or result_dict.get("url") or "")
    b64_json = str(first.get("b64_json") or result_dict.get("b64_json") or "")
    if not image_url and not b64_json:
        raise HTTPException(status_code=502, detail="图片模型未返回 image url 或 b64_json")

    return VisualAssetGenerationResponse(
        success=True,
        message="图表素材已生成",
        prompt=prompt,
        image_url=image_url,
        b64_json=b64_json,
    )


