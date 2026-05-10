from typing import Dict, Any, List, AsyncGenerator
import asyncio
import html
import json
import os
import re

from ...utils.outline_util import generate_one_outline_json_by_level1
from ...utils import prompt_manager
from ...utils import generation_policy
from ...utils.json_util import check_json, extract_json_string
from ...models.schemas import AnalysisReport, ResponseMatrix, ReviewReport
from ..enterprise_material_service import EnterpriseMaterialService
from ..fallback_generation import FallbackGenerationMixin
from ..history_case_service import HistoryCaseService


class ContentGenerationMixin:
    async def generate_content_for_outline(
        self,
        outline: Dict[str, Any],
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """为目录结构生成内容"""
        try:
            if not isinstance(outline, dict) or 'outline' not in outline:
                raise Exception("无效的outline数据格式")
            
            # 深拷贝outline数据
            import copy
            result_outline = copy.deepcopy(outline)
            
            # 递归处理目录
            await self._process_outline_recursive(
                result_outline['outline'],
                [],
                project_overview,
                analysis_report=analysis_report,
                bid_mode=bid_mode,
                reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
            )
            
            return result_outline
            
        except Exception as e:
            raise Exception(f"处理过程中发生错误: {str(e)}")

    async def _process_outline_recursive(
        self,
        chapters: list,
        parent_chapters: list = None,
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
    ):
        """递归处理章节列表"""
        for chapter in chapters:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            
            # 检查是否为叶子节点
            is_leaf = 'children' not in chapter or not chapter.get('children', [])
            
            # 准备当前章节信息
            current_chapter_info = {
                'id': chapter_id,
                'title': chapter_title,
                'description': chapter.get('description', '')
            }
            
            # 构建完整的上级章节列表
            current_parent_chapters = []
            if parent_chapters:
                current_parent_chapters.extend(parent_chapters)
            current_parent_chapters.append(current_chapter_info)
            
            if is_leaf:
                # 为叶子节点生成内容，传递同级章节信息
                content = ""
                async for chunk in self._generate_chapter_content(
                    chapter, 
                    current_parent_chapters[:-1],  # 上级章节列表（排除当前章节）
                    chapters,  # 同级章节列表
                    project_overview,
                    analysis_report=analysis_report,
                    bid_mode=bid_mode,
                    reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                    document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
                ):
                    content += chunk
                if content:
                    chapter['content'] = content
            else:
                # 递归处理子章节
                await self._process_outline_recursive(
                    chapter['children'],
                    current_parent_chapters,
                    project_overview,
                    analysis_report=analysis_report,
                    bid_mode=bid_mode,
                    reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                    document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
                )

    async def _generate_chapter_content(
        self,
        chapter: dict,
        parent_chapters: list = None,
        sibling_chapters: list = None,
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        generated_summaries: list | None = None,
        enterprise_materials: list | None = None,
        missing_materials: list | None = None,
        response_matrix: Dict[str, Any] | None = None,
        reference_bid_style_profile: Dict[str, Any] | None = None,
        document_blocks_plan: Dict[str, Any] | None = None,
        history_reference_drafts: list | None = None,
    ) -> AsyncGenerator[str, None]:
        """为单个章节流式生成内容。"""
        try:
            if self._force_local_fallback():
                yield self._fallback_chapter_content(
                    chapter,
                    project_overview=project_overview,
                    analysis_report=analysis_report,
                    missing_materials=missing_materials,
                )
                return

            effective_response_matrix = response_matrix or (analysis_report or {}).get("response_matrix") or {}
            effective_history_reference_drafts = history_reference_drafts or []
            if not effective_history_reference_drafts:
                try:
                    effective_history_reference_drafts = HistoryCaseService.find_chapter_reference_drafts(
                        chapter=chapter,
                        parent_chapters=parent_chapters or [],
                        sibling_chapters=sibling_chapters or [],
                        analysis_report=analysis_report or {},
                        response_matrix=effective_response_matrix,
                        limit=3,
                    )
                except Exception as exc:
                    print(f"历史章节参考检索失败，继续直接生成正文：{exc}")
                    effective_history_reference_drafts = []
            primary_history_draft = self._select_primary_history_draft(effective_history_reference_drafts)
            if primary_history_draft:
                try:
                    markdown, html_content, operations = await self._generate_patch_based_chapter_content(
                        chapter=chapter,
                        parent_chapters=parent_chapters or [],
                        project_overview=project_overview,
                        analysis_report=analysis_report or {},
                        response_matrix=effective_response_matrix,
                        history_reference_draft=primary_history_draft,
                        generated_summaries=generated_summaries or [],
                    )
                    self._last_chapter_render = {
                        "content_html": html_content,
                        "patch_operations": operations,
                        "history_reference": self._compact_history_reference(primary_history_draft),
                    }
                    yield markdown
                    return
                except Exception as exc:
                    print(f"历史 Word patch 生成失败，回退为正文生成：{exc}")
                    self._last_chapter_render = {}
            system_prompt, user_prompt = prompt_manager.generate_chapter_content_prompt(
                chapter=chapter,
                parent_chapters=parent_chapters or [],
                sibling_chapters=sibling_chapters or [],
                project_overview=project_overview,
                analysis_report=analysis_report,
                bid_mode=bid_mode,
                generated_summaries=generated_summaries or [],
                enterprise_materials=enterprise_materials or [],
                missing_materials=missing_materials or (analysis_report or {}).get("missing_company_materials", []),
                response_matrix=effective_response_matrix,
                reference_bid_style_profile=reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile"),
                document_blocks_plan=document_blocks_plan or (analysis_report or {}).get("document_blocks_plan"),
                history_reference_drafts=effective_history_reference_drafts,
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            try:
                async for chunk in self.stream_chat_completion(messages, temperature=0.35):
                    yield chunk
            except Exception as e:
                if not self._generation_fallbacks_enabled():
                    raise self._fallback_disabled_error("章节正文生成", str(e)) from e
                print(f"章节模型输出不可用，启用文本兜底正文：{str(e)}")
                yield self._fallback_chapter_content(
                    chapter,
                    project_overview=project_overview,
                    analysis_report=analysis_report,
                    missing_materials=missing_materials,
                )
        except Exception as e:
            print(f"生成章节内容时出错: {str(e)}")
            raise Exception(f"生成章节内容时出错: {str(e)}") from e

    @staticmethod
    def _select_primary_history_draft(drafts: list | None) -> Dict[str, Any] | None:
        for draft in drafts or []:
            matched_blocks = draft.get("matched_blocks") if isinstance(draft, dict) else None
            if (
                isinstance(draft, dict)
                and draft.get("match_level") in {"high", "medium"}
                and isinstance(matched_blocks, list)
                and bool(matched_blocks)
            ):
                return draft
        return None

    async def _generate_patch_based_chapter_content(
        self,
        chapter: dict,
        parent_chapters: list,
        project_overview: str,
        analysis_report: Dict[str, Any],
        response_matrix: Dict[str, Any],
        history_reference_draft: Dict[str, Any],
        generated_summaries: list,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        source_markdown = str(
            history_reference_draft.get("markdown_text")
            or history_reference_draft.get("reference_text")
            or ""
        ).strip()
        source_html = str(history_reference_draft.get("html_fragment") or "").strip()
        system_prompt, user_prompt = prompt_manager.generate_chapter_patch_prompt(
            chapter=chapter,
            parent_chapters=parent_chapters,
            project_overview=project_overview,
            analysis_report=analysis_report,
            response_matrix=response_matrix,
            history_reference_draft=history_reference_draft,
            generated_summaries=generated_summaries,
        )
        raw_patch = await self._collect_stream_text(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.18,
            response_format={"type": "json_object"},
        )
        payload = self._loads_json_loose(raw_patch)
        operations = payload.get("operations") if isinstance(payload, dict) else []
        if not isinstance(operations, list):
            operations = []
        matched_blocks = history_reference_draft.get("matched_blocks")
        if isinstance(matched_blocks, list) and matched_blocks:
            patched_blocks = self._apply_history_patch_to_blocks(matched_blocks, operations)
            markdown = HistoryCaseService._blocks_to_markdown(patched_blocks)
            html_content = HistoryCaseService._blocks_to_html(patched_blocks)
        else:
            markdown = self._apply_history_patch_operations(source_markdown, operations, html_mode=False)
            html_content = source_html or self._history_markdown_to_basic_html(source_markdown)
            html_content = self._apply_history_patch_operations(html_content, operations, html_mode=True)
        return markdown or source_markdown, html_content, [op for op in operations if isinstance(op, dict)]

    @classmethod
    def _apply_history_patch_to_blocks(cls, blocks: list, operations: list) -> list[dict[str, Any]]:
        patched = json.loads(json.dumps([block for block in blocks if isinstance(block, dict)], ensure_ascii=False))
        if not patched:
            return []

        for raw_op in operations or []:
            op = cls._normalize_history_patch_operation(raw_op)
            kind = op.get("op")
            if not kind:
                continue
            if kind == "move_block_after":
                cls._move_history_block(patched, op.get("block_id"), op.get("after_block_id"))
                continue
            if kind in {"insert_after", "append_text"}:
                cls._insert_history_text_block(patched, op)
                continue

            indexes = cls._target_history_block_indexes(patched, op)
            for index in indexes:
                block = patched[index]
                if kind == "replace_text":
                    cls._replace_in_history_block(block, op.get("from"), op.get("to"))
                elif kind == "delete_text":
                    cls._replace_in_history_block(block, op.get("from"), "")
                elif kind == "update_caption":
                    cls._update_history_caption(block, op)
        return patched

    @staticmethod
    def _normalize_history_patch_operation(operation: Any) -> dict[str, Any]:
        if not isinstance(operation, dict):
            return {}
        kind = str(operation.get("op") or "").strip()
        aliases = {
            "insert_after_text": "insert_after",
            "insert_after_block": "insert_after",
            "move_image_after": "move_block_after",
            "move_after": "move_block_after",
        }
        kind = aliases.get(kind, kind)
        return {
            "op": kind,
            "block_id": str(operation.get("block_id") or "").strip(),
            "after_block_id": str(operation.get("after_block_id") or operation.get("after") or "").strip(),
            "from": str(operation.get("from") or operation.get("target_text") or "").strip(),
            "to": str(operation.get("to") or operation.get("replacement") or operation.get("caption") or ""),
            "text": str(operation.get("text") or ""),
            "caption": str(operation.get("caption") or operation.get("to") or operation.get("replacement") or ""),
            "reason": str(operation.get("reason") or ""),
        }

    @staticmethod
    def _target_history_block_indexes(blocks: list[dict[str, Any]], op: dict[str, Any]) -> list[int]:
        block_id = op.get("block_id")
        if block_id:
            return [index for index, block in enumerate(blocks) if str(block.get("id") or "") == block_id]
        target = str(op.get("from") or "")
        if target:
            matches = [
                index for index, block in enumerate(blocks)
                if target in str(block.get("text") or "") or target in str(block.get("markdown") or "")
            ]
            if matches:
                return matches[:1]
        return []

    @classmethod
    def _replace_in_history_block(cls, block: dict[str, Any], old: str | None, new: str | None) -> None:
        if not old:
            return
        replacement = "" if new is None else str(new)
        for key in ("text", "markdown"):
            value = str(block.get(key) or "")
            if old in value:
                block[key] = value.replace(old, replacement, 1)
        html_value = str(block.get("html") or "")
        escaped_old = html.escape(old)
        if escaped_old in html_value:
            block["html"] = html_value.replace(escaped_old, html.escape(replacement), 1)
        xml_value = str(block.get("docx_xml") or "")
        if xml_value:
            escaped_xml_old = html.escape(old, quote=False)
            escaped_xml_replacement = html.escape(replacement, quote=False)
            if escaped_xml_old in xml_value:
                block["docx_xml"] = xml_value.replace(escaped_xml_old, escaped_xml_replacement, 1)
            elif old in xml_value:
                block["docx_xml"] = xml_value.replace(old, replacement, 1)

    @classmethod
    def _insert_history_text_block(cls, blocks: list[dict[str, Any]], op: dict[str, Any]) -> None:
        text = str(op.get("text") or "").strip()
        if not text:
            return
        after_id = str(op.get("after_block_id") or op.get("block_id") or "").strip()
        insert_at = len(blocks)
        if after_id:
            for index, block in enumerate(blocks):
                if str(block.get("id") or "") == after_id:
                    insert_at = index + 1
                    break
        elif op.get("from"):
            for index, block in enumerate(blocks):
                if str(op.get("from")) in str(block.get("text") or ""):
                    insert_at = index + 1
                    break
        new_id = f"patch-{len([block for block in blocks if str(block.get('id') or '').startswith('patch-')]) + 1}"
        blocks.insert(insert_at, {
            "id": new_id,
            "type": "paragraph",
            "level": 0,
            "text": text,
            "markdown": text,
            "html": cls._history_markdown_to_basic_html(text, wrap=False, block_id=new_id),
            "asset_ids": [],
        })

    @staticmethod
    def _move_history_block(blocks: list[dict[str, Any]], block_id: str | None, after_block_id: str | None) -> None:
        if not block_id or not after_block_id or block_id == after_block_id:
            return
        source_index = next((index for index, block in enumerate(blocks) if str(block.get("id") or "") == block_id), -1)
        if source_index < 0:
            return
        block = blocks.pop(source_index)
        target_index = next((index for index, item in enumerate(blocks) if str(item.get("id") or "") == after_block_id), -1)
        if target_index < 0:
            blocks.insert(source_index, block)
            return
        blocks.insert(target_index + 1, block)

    @classmethod
    def _update_history_caption(cls, block: dict[str, Any], op: dict[str, Any]) -> None:
        caption = str(op.get("caption") or op.get("to") or "").strip()
        if not caption:
            return
        target = str(op.get("from") or "")
        if target:
            cls._replace_in_history_block(block, target, caption)
            return
        markdown = str(block.get("markdown") or "")
        if re.search(r"!\[[^\]]*\]\([^)]+\)", markdown):
            block["markdown"] = f"{markdown.rstrip()}\n\n{caption}"
        html_value = str(block.get("html") or "")
        if "<figure" in html_value and "<figcaption" not in html_value:
            block["html"] = html_value.replace("</figure>", f"<figcaption>{html.escape(caption)}</figcaption></figure>", 1)
        elif html_value:
            block["html"] = f"{html_value}<p>{html.escape(caption)}</p>"
        block["text"] = f"{str(block.get('text') or '').rstrip()}\n{caption}".strip()
        block["caption_text"] = caption

    @staticmethod
    def _apply_history_patch_operations(content: str, operations: list, html_mode: bool = False) -> str:
        next_content = str(content or "")
        for raw_op in operations or []:
            op = ContentGenerationMixin._normalize_history_patch_operation(raw_op)
            if not op:
                continue
            kind = str(op.get("op") or "").strip()
            target = str(op.get("from") or "").strip()
            replacement = str(op.get("to") or "")
            text = str(op.get("text") or "")
            if html_mode:
                target = html.escape(target)
                replacement = html.escape(replacement)
                text = html.escape(text)
            if kind in {"replace_text", "update_caption"} and target and target in next_content:
                next_content = next_content.replace(target, replacement, 1)
            elif kind == "delete_text" and target:
                next_content = next_content.replace(target, "", 1)
            elif kind == "insert_after_text" and target and text:
                index = next_content.find(target)
                if index >= 0:
                    insert_at = index + len(target)
                    separator = "" if html_mode else "\n"
                    next_content = f"{next_content[:insert_at]}{separator}{text}{next_content[insert_at:]}"
            elif kind == "append_text" and text:
                next_content = f"{next_content.rstrip()}{'<p>' if html_mode else chr(10)}{text}{'</p>' if html_mode else ''}"
        return next_content

    @staticmethod
    def _history_markdown_to_basic_html(markdown: str, wrap: bool = True, block_id: str = "") -> str:
        parts = ['<div class="history-word-preview">'] if wrap else []
        table_rows: list[list[str]] = []

        def is_divider(line: str) -> bool:
            return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line or ""))

        def parse_table_row(line: str) -> list[str] | None:
            stripped = line.strip()
            if "|" not in stripped or is_divider(stripped):
                return None
            normalized = stripped.strip("|")
            cells = [cell.strip() for cell in normalized.split("|")]
            if len([cell for cell in cells if cell]) < 2:
                return None
            return cells

        def normalize_inline_table_lines(text: str) -> list[str]:
            normalized_lines: list[str] = []
            header_pattern = re.compile(r"\|\s*(?:序号|编号|阶段|类别|层级|项目|名称|成果|进度|招标要求|响应内容)\s*\|")
            for raw_line in str(text or "").splitlines():
                line = raw_line.rstrip()
                if line.count("|") < 6:
                    normalized_lines.append(line)
                    continue
                match = header_pattern.search(line)
                if match and match.start() > 0 and not line.lstrip().startswith("|"):
                    lead = line[:match.start()].strip()
                    if lead:
                        normalized_lines.append(lead)
                    line = line[match.start():]
                line = re.sub(r"\|\s*\|\s*(?=(?:\d+|[一二三四五六七八九十]+)\s*\|)", "|\n| ", line)
                line = re.sub(r"\s+(\|\s*(?:\d+|[一二三四五六七八九十]+)\s*\|)", r"\n\1", line)
                normalized_lines.extend(line.splitlines())
            return normalized_lines

        def flush_table() -> None:
            nonlocal table_rows
            if len(table_rows) >= 2:
                column_count = max(len(row) for row in table_rows)
                normalized = [row + [""] * (column_count - len(row)) for row in table_rows]
                header, body = normalized[0], normalized[1:]
                attrs = f' data-history-block-id="{html.escape(block_id)}"' if block_id else ""
                parts.append(f"<table{attrs}><thead><tr>")
                parts.extend(f"<th>{html.escape(cell)}</th>" for cell in header)
                parts.append("</tr></thead><tbody>")
                for row in body:
                    parts.append("<tr>")
                    parts.extend(f"<td>{html.escape(cell)}</td>" for cell in row)
                    parts.append("</tr>")
                parts.append("</tbody></table>")
            elif table_rows:
                attrs = f' data-history-block-id="{html.escape(block_id)}"' if block_id else ""
                parts.append(f"<p{attrs}>{html.escape('| ' + ' | '.join(table_rows[0]) + ' |')}</p>")
            table_rows = []

        for raw in normalize_inline_table_lines(markdown):
            line = raw.strip()
            if not line:
                flush_table()
                continue
            table_row = parse_table_row(line)
            if table_row:
                table_rows.append(table_row)
                continue
            flush_table()
            attrs = f' data-history-block-id="{html.escape(block_id)}"' if block_id else ""
            heading = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading:
                level = min(len(heading.group(1)), 6)
                parts.append(f"<h{level}{attrs}>{html.escape(heading.group(2))}</h{level}>")
            else:
                parts.append(f"<p{attrs}>{html.escape(line)}</p>")
        flush_table()
        if wrap:
            parts.append("</div>")
        return "".join(parts)

    @staticmethod
    def _compact_history_reference(reference: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "match_level": reference.get("match_level"),
            "score": reference.get("score"),
            "project_title": reference.get("project_title"),
            "file_name": reference.get("file_name"),
            "document_id": reference.get("document_id"),
            "matched_term": reference.get("matched_term"),
            "source_paths": reference.get("source_paths") or {},
            "matched_block_ids": reference.get("matched_block_ids") or [
                str(block.get("id")) for block in (reference.get("matched_blocks") or []) if isinstance(block, dict) and block.get("id")
            ],
        }
