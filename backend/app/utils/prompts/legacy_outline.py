"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Tuple
from .core import _json
from .outline_templates import get_generic_service_plan_outline_template


def read_expand_outline_prompt() -> str:
    template = _json(get_generic_service_plan_outline_template(), indent=2)
    return f"""你是投标文件样例反向建模专家。目标是从简版技术方案、历史投标文件或样例文件中提取可迁移目录结构。

输出契约：只输出目录 JSON，不生成正文，不输出解析过程。
规则：明确章节名优先保留；无明确章节名时提炼正式投标文件标题；表格、函件、承诺、证明材料、图片展示都应建立目录节点；只抽取结构和风格，不固化样例行业。
如果文本包含“投标文件/投标文件格式/投标文件组成/编制要求”，优先抽取这些硬约束章节。

通用服务/技术方案目录参考：
{template}

返回 JSON：{{"outline": [...]}}，不要 markdown。"""


def generate_outline_prompt(overview: str, requirements: str) -> Tuple[str, str]:
    schema = {"outline": get_generic_service_plan_outline_template()}
    system_prompt = f"""你是通用投标文件目录生成专家。目标是按输入范围生成目录 JSON，不生成正文。
先判断范围：完整投标文件、技术标、服务方案、施工组织设计、供货方案、资格卷或报价卷。若输入含投标文件格式/组成要求，优先遵守；不得强行套行业模板。
JSON 格式参考：{_json(schema)}"""
    user_prompt = f"""请基于以下项目信息生成标书目录结构：
项目概述：{overview}
技术/服务/评分要求：{requirements}
请直接输出目录 JSON。"""
    return system_prompt, user_prompt


def generate_outline_with_old_prompt(overview: str, requirements: str, old_outline: str) -> Tuple[str, str]:
    system_prompt = """你是通用投标文件目录校正专家。目标是吸收用户已有目录并补齐缺口，只生成目录 JSON，不生成正文。
必须补齐评分项、审查项、证明材料、表格、承诺书和图表素材节点；不得强行套用某个行业模板。"""
    user_prompt = f"""用户已有目录：{old_outline}
项目概述：{overview}
技术/服务/评分要求：{requirements}
请结合用户目录输出最终目录 JSON。"""
    return system_prompt, user_prompt
