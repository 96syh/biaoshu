"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, Tuple
from .core import _json, _schema_contract
from .schemas import get_reference_bid_style_profile_schema


def generate_reference_bid_style_profile_prompt(reference_bid_text: str, *, include_schema_in_prompt: bool = True) -> Tuple[str, str]:
    schema_json = _json(get_reference_bid_style_profile_schema(), indent=2)
    system_prompt = f"""你是投标文件样例模板工程师。目标不是总结样例内容，而是把成熟投标文件反向建模成可迁移的 ReferenceBidStyleProfile JSON。

输出契约：
1. 只输出合法 JSON，不输出 markdown，不输出长段正文。
2. 字符串保持高信号，尽量 80 字以内；outline_template 保留 6-12 项，chapter_blueprints 保留 4-8 项。
3. 证据不足时采用保守模板策略，并在 quality_risks 标记“证据不足/需人工复核”。

抽取对象：
1. reusable_template：目录层级、标题习惯、段落组织、表格模型、图片/承诺/素材位置、封面/目录顺序。
2. project_facts：项目名称、招标人、日期、期限、地点、金额、行业对象，只能进入 tender_fact_slots 或 quality_risks。
3. enterprise_facts：投标人、人员、证书、软件设备、体系文件、业绩图片，只能进入 enterprise_fact_slots、enterprise_data_requirements 或 image_slots。
4. word_style_profile：页面尺寸、方向、页边距、字体、字号、行距、首行缩进、表格边框；无法精确判断时给常用 Word 值并标记人工复核。

迁移规则：
1. chapter_blueprints 要写适用场景、写作功能、段落骨架、招标事实槽、企业事实槽、表格/图片/承诺插入规则、禁止照抄项。
2. 不得照抄或改写样例正文；句式只能输出含变量的骨架，例如 {{项目名称}}、{{服务范围}}、{{质量标准}}、{{响应时限}}。
3. 应由招标文件决定的内容写入 tender_fact_slots 或 template_intent.must_map_from_tender；应由企业资料提供的内容标记 enterprise_required=true。
4. 图片标记 `![...](...)` 中括号内 URL 必须原样写入 image_slots.image_url，alt/title 写入 image_alt 或 source_ref。
5. 历史项目残留、日期不一致、投标人不一致、错别字、行业错配、不可泛化承诺、人员/证书/业绩敏感内容写入 quality_risks。
6. 不得把样例行业固化为所有项目默认行业，不得编造样例中没有的版式、事实、表格、图片、承诺时限或企业能力。

{_schema_contract("ReferenceBidStyleProfile JSON", schema_json, include_schema_in_prompt)}
"""
    user_prompt = f"""请解析以下成熟投标文件样例，生成可作为写作模板使用的 ReferenceBidStyleProfile JSON。

<reference_bid_text>
{reference_bid_text}
</reference_bid_text>

直接返回 JSON。"""
    return system_prompt, user_prompt
