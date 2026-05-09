from typing import Dict, Any, List, AsyncGenerator
import asyncio
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
