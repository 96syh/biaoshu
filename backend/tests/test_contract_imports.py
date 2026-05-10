import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


class BackendContractImportTests(unittest.TestCase):
    def test_schema_reexports_stay_compatible(self):
        from backend.app.models import schemas
        from backend.app.models.schema_defs.analysis import AnalysisReport as SplitAnalysisReport

        self.assertIs(schemas.AnalysisReport, SplitAnalysisReport)
        self.assertEqual(schemas.ConfigRequest().provider, "litellm")
        self.assertEqual(schemas.OutlineItem(id="1", title="章", description="").id, "1")

    def test_prompt_manager_reexports_stay_compatible(self):
        from backend.app.utils import prompt_manager

        self.assertIsInstance(prompt_manager.get_analysis_report_schema(), dict)
        self.assertIsInstance(prompt_manager.get_reference_bid_style_profile_schema(), dict)
        system_prompt, user_prompt = prompt_manager.generate_outline_prompt("项目概述", "评分要求")
        self.assertIn("目录", system_prompt)
        self.assertIn("项目概述", user_prompt)

    def test_openai_service_facade_keeps_public_methods(self):
        from backend.app.services.openai_service import OpenAIService

        service = OpenAIService()
        for name in (
            "generate_analysis_report",
            "generate_reference_bid_style_profile",
            "generate_document_blocks_plan",
            "generate_consistency_revision_report",
            "generate_response_matrix",
            "generate_compliance_review",
            "generate_content_for_outline",
            "_generate_chapter_content",
            "generate_outline_v2",
            "stream_chat_completion",
            "verify_current_endpoint",
        ):
            self.assertTrue(hasattr(service, name), name)

    def test_default_app_routes_exclude_optional_search_and_legacy_expand(self):
        os.environ["ENABLE_SEARCH_ROUTER"] = "0"
        os.environ["ENABLE_LEGACY_EXPAND_ROUTER"] = "0"
        sys.modules.pop("backend.app.main", None)

        main = importlib.import_module("backend.app.main")
        paths = {route.path for route in main.app.routes}

        self.assertIn("/api/document/upload", paths)
        self.assertIn("/api/document/upload-text", paths)
        self.assertIn("/api/document/source-preview/{source_preview_id}", paths)
        self.assertIn("/api/outline/generate", paths)
        self.assertIn("/api/projects", paths)
        self.assertFalse(any(path.startswith("/api/search") for path in paths))
        self.assertFalse(any(path.startswith("/api/expand") for path in paths))
        self.assertNotIn("duckduckgo_search", sys.modules)

    def test_runtime_data_defaults_to_artifacts(self):
        from backend.app.services.file_service import FileService
        from backend.app.services.generation_cache_service import GenerationCacheService
        from backend.app.services.history_case_service import HistoryCaseService
        from backend.app.services.project_service import ProjectService

        self.assertIn("artifacts/data/generated_assets", str(FileService.GENERATED_ASSET_DIR))
        self.assertIn("artifacts/data/generation_cache", str(GenerationCacheService.CACHE_DIR))
        self.assertIn("artifacts/data/history_cases.sqlite3", str(HistoryCaseService.DB_PATH))
        self.assertIn("artifacts/data/projects.sqlite3", str(ProjectService.DB_PATH))

    def test_model_gateway_concurrency_env_has_safe_floor(self):
        from backend.app.services.model_gateway_service import ModelGatewayService

        original_value = os.environ.get("YIBIAO_MODEL_CONCURRENCY")
        try:
            os.environ["YIBIAO_MODEL_CONCURRENCY"] = "0"
            self.assertEqual(ModelGatewayService._model_concurrency_limit(), 1)
            os.environ["YIBIAO_MODEL_CONCURRENCY"] = "3"
            self.assertEqual(ModelGatewayService._model_concurrency_limit(), 3)
        finally:
            if original_value is None:
                os.environ.pop("YIBIAO_MODEL_CONCURRENCY", None)
            else:
                os.environ["YIBIAO_MODEL_CONCURRENCY"] = original_value

    def test_generation_cache_round_trip(self):
        from backend.app.services.generation_cache_service import GenerationCacheService

        original_dir = GenerationCacheService.CACHE_DIR
        original_enabled = os.environ.get("YIBIAO_ENABLE_GENERATION_CACHE")
        with tempfile.TemporaryDirectory() as temp_dir:
            GenerationCacheService.CACHE_DIR = Path(temp_dir)
            os.environ["YIBIAO_ENABLE_GENERATION_CACHE"] = "1"
            try:
                key = GenerationCacheService.build_key("analysis", "model-a", {"x": 1})
                self.assertIsNone(GenerationCacheService.get("analysis", key))
                GenerationCacheService.set("analysis", key, {"ok": True})
                self.assertEqual(GenerationCacheService.get("analysis", key), {"ok": True})
            finally:
                GenerationCacheService.CACHE_DIR = original_dir
                if original_enabled is None:
                    os.environ.pop("YIBIAO_ENABLE_GENERATION_CACHE", None)
                else:
                    os.environ["YIBIAO_ENABLE_GENERATION_CACHE"] = original_enabled

    def test_scheme_outline_items_include_technical_composition_children(self):
        from backend.app.services.fallback_generation import FallbackGenerationMixin

        report = {
            "bid_document_requirements": {
                "composition": [
                    {
                        "id": "BD-TECH",
                        "title": "技术标",
                        "volume_id": "V-TECH",
                        "chapter_type": "technical",
                        "source_ref": "BD-SRC-01",
                        "children": [
                            {"id": "BD-TECH-01", "order": 1, "title": "服务范围"},
                            {"id": "BD-TECH-02", "order": 2, "title": "服务内容"},
                            {"id": "BD-TECH-03", "order": 3, "title": "质量承诺及措施"},
                        ],
                    }
                ],
                "selected_generation_target": {
                    "target_id": "BD-TECH",
                    "target_title": "技术标",
                    "parent_composition_id": "BD-TECH",
                    "base_outline_items": [],
                },
                "scheme_or_technical_outline_requirements": [],
            }
        }

        titles = [item["title"] for item in FallbackGenerationMixin._collect_scheme_outline_items(report)]

        self.assertEqual(titles[:3], ["服务范围", "服务内容", "质量承诺及措施"])

    def test_outline_guard_uses_tender_required_technical_chapters(self):
        from backend.app.services.generation.outline import OutlineGenerationMixin

        report = {
            "bid_document_requirements": {
                "composition": [
                    {
                        "id": "BD-TECH",
                        "title": "技术标",
                        "volume_id": "V-TECH",
                        "chapter_type": "technical",
                        "children": [
                            {"id": "BD-TECH-01", "order": 1, "title": "服务范围"},
                            {"id": "BD-TECH-02", "order": 2, "title": "服务内容"},
                        ],
                    }
                ],
                "selected_generation_target": {
                    "target_id": "BD-TECH",
                    "target_title": "技术标",
                    "parent_composition_id": "BD-TECH",
                    "base_outline_items": [],
                },
                "scheme_or_technical_outline_requirements": [],
            },
            "response_matrix": {"items": []},
        }

        tech_only_outline, changed, _ = OutlineGenerationMixin._apply_scheme_outline_guard(
            [{"id": "1", "title": "通用实施方案", "children": []}],
            report,
            "technical_only",
        )
        self.assertTrue(changed)
        self.assertEqual([item["title"] for item in tech_only_outline], ["服务范围", "服务内容"])

        full_bid_outline, changed, _ = OutlineGenerationMixin._apply_scheme_outline_guard(
            [{"id": "1", "title": "商务标"}, {"id": "2", "title": "技术标", "volume_id": "V-TECH"}],
            report,
            "full_bid",
        )
        self.assertTrue(changed)
        self.assertEqual([item["title"] for item in full_bid_outline[1]["children"]], ["服务范围", "服务内容"])

    def test_docx_html_preview_defaults_to_enabled_for_source_location(self):
        from backend.app.services.file_service import FileService

        original_value = os.environ.pop("YIBIAO_ENABLE_DOCX_HTML_PREVIEW", None)
        try:
            self.assertTrue(FileService.docx_html_preview_enabled())
            os.environ["YIBIAO_ENABLE_DOCX_HTML_PREVIEW"] = "0"
            self.assertFalse(FileService.docx_html_preview_enabled())
        finally:
            if original_value is not None:
                os.environ["YIBIAO_ENABLE_DOCX_HTML_PREVIEW"] = original_value
            else:
                os.environ.pop("YIBIAO_ENABLE_DOCX_HTML_PREVIEW", None)

    def test_source_preview_saved_upload_path_stays_under_upload_dir(self):
        from backend.app.config import settings
        from backend.app.services.file_service import FileService

        original_upload_dir = settings.upload_dir
        with tempfile.TemporaryDirectory() as temp_dir:
            settings.upload_dir = temp_dir
            safe_path = Path(temp_dir) / "sample.docx"
            safe_path.write_text("placeholder", encoding="utf-8")
            try:
                self.assertEqual(FileService._resolve_saved_upload_path("sample.docx"), str(safe_path.resolve()))
                with self.assertRaises(Exception):
                    FileService._resolve_saved_upload_path("../sample.docx")
            finally:
                settings.upload_dir = original_upload_dir

    def test_empty_docx_preview_html_is_not_treated_as_renderable(self):
        from backend.app.services.file_service import FileService

        self.assertFalse(FileService.source_preview_html_has_text('<div class="docx-source-preview"><p>&nbsp;</p></div>'))
        self.assertTrue(FileService.source_preview_html_has_text('<div class="docx-source-preview"><p>服务质量保证</p></div>'))

    def test_docx_line_spacing_conversion_does_not_emit_raw_emu_values(self):
        from backend.app.services.file_service import FileService

        class EmuLength:
            pt = 22

            def __float__(self):
                return 279400.0

        self.assertEqual(FileService._line_spacing_to_css(EmuLength()), "22.0pt")
        self.assertEqual(FileService._line_spacing_to_css(1.5), "1.50")
        self.assertEqual(FileService._line_spacing_to_css(279400), "")

    def test_history_case_legacy_artifact_paths_resolve_to_artifacts(self):
        from backend.app.services.history_case_service import HistoryCaseService

        original_artifact_root = HistoryCaseService.HISTORY_ARTIFACT_ROOT
        original_legacy_root = HistoryCaseService.LEGACY_HISTORY_ARTIFACT_ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            HistoryCaseService.HISTORY_ARTIFACT_ROOT = temp_root / "artifacts" / "data" / "history_cases"
            HistoryCaseService.LEGACY_HISTORY_ARTIFACT_ROOT = temp_root / "backend" / "data" / "history_cases"
            target = HistoryCaseService.HISTORY_ARTIFACT_ROOT / "markdown" / "case.md"
            target.parent.mkdir(parents=True)
            target.write_text("history markdown", encoding="utf-8")
            legacy_path = HistoryCaseService.LEGACY_HISTORY_ARTIFACT_ROOT / "markdown" / "case.md"

            try:
                self.assertEqual(HistoryCaseService.load_markdown(str(legacy_path)), "history markdown")
                self.assertEqual(
                    HistoryCaseService._normalize_artifact_path_for_response(str(legacy_path)),
                    str(target),
                )
            finally:
                HistoryCaseService.HISTORY_ARTIFACT_ROOT = original_artifact_root
                HistoryCaseService.LEGACY_HISTORY_ARTIFACT_ROOT = original_legacy_root

    def test_history_chapter_reference_extracts_matching_section(self):
        from backend.app.services.history_case_service import HistoryCaseService

        markdown = (
            "# 技术标\n\n"
            "## 服务范围\n旧服务范围正文\n\n"
            "## 质量保证措施\n质量目标明确，建立校审、复核和问题闭环机制。\n\n"
            "## 进度保证措施\n进度计划正文"
        )

        section = HistoryCaseService._extract_markdown_section(markdown, "质量保证措施")

        self.assertIn("质量目标明确", section)
        self.assertNotIn("进度计划正文", section)

    def test_history_chapter_reference_preserves_images_and_tables(self):
        from backend.app.services.history_case_service import HistoryCaseService

        markdown = (
            "# 技术标\n\n"
            "## 第一章 服务质量保证\n"
            "![组织架构图](assets/org.png)\n\n"
            "| 序号 | 措施 |\n"
            "| --- | --- |\n"
            "| 1 | 校审复核 |\n"
        )

        section = HistoryCaseService._extract_markdown_section(markdown, "服务质量保证")
        inventory = HistoryCaseService._reference_block_inventory(section)

        self.assertIn("![组织架构图](assets/org.png)", section)
        self.assertIn("| 序号 | 措施 |", section)
        self.assertTrue(inventory["has_image"])
        self.assertTrue(inventory["has_table"])

    def test_chapter_content_prompt_carries_history_rewrite_rules(self):
        from backend.app.utils import prompt_manager

        system_prompt, user_prompt = prompt_manager.generate_chapter_content_prompt(
            chapter={"id": "c1", "title": "质量保证措施", "description": "响应质量评分项"},
            parent_chapters=[],
            sibling_chapters=[],
            project_overview="油库设计服务",
            analysis_report={"project": {"name": "当前项目"}},
            history_reference_drafts=[
                {
                    "match_level": "high",
                    "project_title": "历史项目",
                    "reference_text": "历史质量保证正文",
                }
            ],
        )

        self.assertIn("历史正文主稿规则", system_prompt)
        self.assertIn("当前招标文件", system_prompt)
        self.assertIn("不得扩写超过历史 reference_text 字数的 130%", system_prompt)
        self.assertIn("历史企业固定资料复用", system_prompt)
        self.assertIn("人员姓名、职称、证书编号", system_prompt)
        self.assertIn("图片语法", system_prompt)
        self.assertIn("表格", system_prompt)
        self.assertIn("history_reference_drafts", user_prompt)
        self.assertIn("历史质量保证正文", user_prompt)

    def test_chapter_patch_prompt_emits_patch_contract(self):
        from backend.app.utils import prompt_manager

        system_prompt, user_prompt = prompt_manager.generate_chapter_patch_prompt(
            chapter={"id": "1", "title": "服务范围"},
            parent_chapters=[],
            project_overview="油库设计服务",
            analysis_report={"technical_scoring_items": [{"name": "服务范围", "standard": "响应全面"}]},
            response_matrix={"items": []},
            history_reference_draft={"matched_blocks": [{"id": "b-1", "text": "历史服务范围"}]},
        )

        self.assertIn("补丁指令", system_prompt)
        self.assertIn("matched_blocks", user_prompt)
        self.assertIn("当前目录标题", system_prompt)
        self.assertIn("不要替换成 〖待补充〗", system_prompt)

    def test_personnel_chapter_reference_terms_include_fixed_material_aliases(self):
        from backend.app.services.history_case_service import HistoryCaseService

        terms = HistoryCaseService._chapter_reference_terms(
            "5.1 项目负责人",
            "拟投入的服务人员、项目负责人、人员证书和职称要求",
        )

        self.assertIn("项目负责人", terms)
        self.assertIn("拟投入人员", terms)
        self.assertIn("拟委任的主要人员", terms)
        self.assertIn("主要人员汇总表", terms)

    def test_personnel_semantic_tokens_match_history_headings(self):
        from backend.app.services.history_case_service import HistoryCaseService

        title_tokens = HistoryCaseService._chapter_reference_semantic_tokens("项目组成人员详情")
        heading_tokens = HistoryCaseService._chapter_reference_semantic_tokens("拟委任的主要人员汇总表")

        self.assertTrue(title_tokens & heading_tokens)

    def test_history_patch_operations_apply_text_replacements(self):
        from backend.app.services.openai_service import OpenAIService

        operations = [
            {"op": "replace_text", "from": "历史项目", "to": "当前项目"},
            {"op": "append_text", "text": "补充评分项响应。"},
        ]

        patched = OpenAIService._apply_history_patch_operations("历史项目服务范围。", operations)

        self.assertIn("当前项目服务范围。", patched)
        self.assertIn("补充评分项响应。", patched)

    def test_history_patch_operations_apply_to_blocks_by_id(self):
        from backend.app.services.openai_service import OpenAIService

        blocks = [
            {"id": "p-1", "type": "paragraph", "text": "历史项目服务范围", "markdown": "历史项目服务范围", "html": '<p data-history-block-id="p-1">历史项目服务范围</p>'},
            {"id": "img-1", "type": "paragraph", "text": "", "markdown": "![组织架构](assets/org.png)", "html": '<figure data-history-block-id="img-1"><img src="assets/org.png" /></figure>'},
            {"id": "p-2", "type": "paragraph", "text": "后续说明", "markdown": "后续说明", "html": '<p data-history-block-id="p-2">后续说明</p>'},
        ]
        operations = [
            {"op": "replace_text", "block_id": "p-1", "from": "历史项目", "to": "当前项目"},
            {"op": "insert_after", "after_block_id": "p-1", "text": "补充评分项响应。"},
            {"op": "update_caption", "block_id": "img-1", "caption": "本项目服务组织架构图"},
            {"op": "move_block_after", "block_id": "img-1", "after_block_id": "p-2"},
        ]

        patched = OpenAIService._apply_history_patch_to_blocks(blocks, operations)
        markdown = "\n".join(str(block.get("markdown") or "") for block in patched)

        self.assertIn("当前项目服务范围", markdown)
        self.assertIn("补充评分项响应。", markdown)
        self.assertIn("本项目服务组织架构图", markdown)
        self.assertEqual([block["id"] for block in patched][-1], "img-1")

    def test_history_patch_inserted_markdown_table_renders_as_html_table(self):
        from backend.app.services.openai_service import OpenAIService

        blocks = [
            {"id": "p-1", "type": "paragraph", "text": "进度目标", "markdown": "进度目标", "html": '<p data-history-block-id="p-1">进度目标</p>'},
        ]
        operations = [{
            "op": "insert_after",
            "after_block_id": "p-1",
            "text": "进度目标响应表 | 序号 | 进度事项 | 招标文件要求 | 本章响应目标 | 管控方式 | | 1 | 服务期限 | 至2026年12月31日 | 动态组织设计服务 | 建立任务台账 |",
        }]

        patched = OpenAIService._apply_history_patch_to_blocks(blocks, operations)
        html = patched[1]["html"]

        self.assertIn("进度目标响应表", html)
        self.assertIn("<table", html)
        self.assertIn("<th>序号</th>", html)
        self.assertIn("<td>服务期限</td>", html)
        self.assertNotIn("| 序号 |", html)

    def test_primary_history_draft_requires_word_heading_blocks(self):
        from backend.app.services.openai_service import OpenAIService

        selected = OpenAIService._select_primary_history_draft([
            {"match_level": "high", "matched_blocks": [], "reference_source": "markdown_fallback"},
            {"match_level": "medium", "matched_blocks": [{"id": "b-1"}], "reference_source": "word_heading_blocks"},
        ])

        self.assertEqual(selected["matched_blocks"][0]["id"], "b-1")
        self.assertIsNone(OpenAIService._select_primary_history_draft([
            {"match_level": "high", "matched_blocks": [], "reference_source": "markdown_fallback"},
        ]))

    def test_history_blocks_convert_to_markdown_and_html(self):
        from backend.app.services.history_case_service import HistoryCaseService

        blocks = [
            {"id": "b-1", "type": "heading", "text": "服务范围", "markdown": "## 服务范围", "html": "<h2 data-history-block-id=\"b-1\">服务范围</h2>"},
            {"id": "b-2", "type": "table", "text": "序号 | 内容", "markdown": "| 序号 | 内容 |\n| --- | --- |\n| 1 | 响应 |", "html": "<table data-history-block-id=\"b-2\"></table>"},
        ]

        self.assertIn("| 序号 | 内容 |", HistoryCaseService._blocks_to_markdown(blocks))
        self.assertIn("data-history-block-id", HistoryCaseService._blocks_to_html(blocks))

    def test_history_matching_anchors_only_heading_and_excludes_service_tables(self):
        from backend.app.services.history_case_service import HistoryCaseService

        blocks = [
            {
                "id": "b-1",
                "type": "heading",
                "level": 1,
                "text": "业绩文件",
                "markdown": "# 业绩文件",
                "html": '<h1 data-history-block-id="b-1">业绩文件</h1>',
                "heading_path": [{"id": "b-1", "level": 1, "title": "业绩文件"}],
            },
            {
                "id": "b-2",
                "type": "table",
                "level": 0,
                "text": "项目法人 | 服务范围 | 服务人员人数",
                "markdown": "| 项目法人 | 服务范围 | 服务人员人数 |",
                "html": '<table data-history-block-id="b-2"></table>',
                "heading_path": [{"id": "b-1", "level": 1, "title": "业绩文件"}],
            },
            {
                "id": "b-3",
                "type": "heading",
                "level": 1,
                "text": "服务范围、服务内容",
                "markdown": "# 服务范围、服务内容",
                "html": '<h1 data-history-block-id="b-3">服务范围、服务内容</h1>',
                "heading_path": [{"id": "b-3", "level": 1, "title": "服务范围、服务内容"}],
            },
            {
                "id": "b-4",
                "type": "paragraph",
                "level": 0,
                "text": "本节说明服务范围。",
                "markdown": "本节说明服务范围。",
                "html": '<p data-history-block-id="b-4">本节说明服务范围。</p>',
                "heading_path": [{"id": "b-3", "level": 1, "title": "服务范围、服务内容"}],
            },
            {
                "id": "b-5",
                "type": "heading",
                "level": 1,
                "text": "拟投入人员",
                "markdown": "# 拟投入人员",
                "html": '<h1 data-history-block-id="b-5">拟投入人员</h1>',
                "heading_path": [{"id": "b-5", "level": 1, "title": "拟投入人员"}],
            },
            {
                "id": "b-6",
                "type": "table",
                "level": 0,
                "text": "层级 | 职务 | 姓名",
                "markdown": "| 层级 | 职务 | 姓名 |",
                "html": '<table data-history-block-id="b-6"></table>',
                "heading_path": [{"id": "b-5", "level": 1, "title": "拟投入人员"}],
            },
        ]

        matched = HistoryCaseService._extract_matching_blocks(blocks, "服务范围、服务内容")

        self.assertEqual([block["id"] for block in matched], ["b-3", "b-4"])
        matched_text = HistoryCaseService._blocks_to_markdown(matched)
        self.assertIn("本节说明服务范围", matched_text)
        self.assertNotIn("项目法人", matched_text)
        self.assertNotIn("层级 | 职务 | 姓名", matched_text)

    def test_history_matching_uses_heading_path_for_descendants(self):
        from backend.app.services.history_case_service import HistoryCaseService

        root_path = [{"id": "b-1", "level": 1, "title": "服务范围、服务内容"}]
        blocks = [
            {"id": "b-1", "type": "heading", "level": 1, "text": "服务范围、服务内容", "markdown": "# 服务范围、服务内容", "heading_path": root_path},
            {
                "id": "b-2",
                "type": "heading",
                "level": 2,
                "text": "服务范围",
                "markdown": "## 服务范围",
                "heading_path": [*root_path, {"id": "b-2", "level": 2, "title": "服务范围"}],
            },
            {
                "id": "b-3",
                "type": "paragraph",
                "text": "历史服务范围正文",
                "markdown": "历史服务范围正文",
                "heading_path": [*root_path, {"id": "b-2", "level": 2, "title": "服务范围"}],
            },
            {
                "id": "b-4",
                "type": "heading",
                "level": 2,
                "text": "服务内容",
                "markdown": "## 服务内容",
                "heading_path": [*root_path, {"id": "b-4", "level": 2, "title": "服务内容"}],
            },
            {
                "id": "b-5",
                "type": "paragraph",
                "text": "历史服务内容正文",
                "markdown": "历史服务内容正文",
                "heading_path": [*root_path, {"id": "b-4", "level": 2, "title": "服务内容"}],
            },
            {
                "id": "b-6",
                "type": "heading",
                "level": 1,
                "text": "拟投入人员",
                "markdown": "# 拟投入人员",
                "heading_path": [{"id": "b-6", "level": 1, "title": "拟投入人员"}],
            },
        ]

        matched = HistoryCaseService._extract_matching_blocks(blocks, "服务范围、服务内容")

        self.assertEqual([block["id"] for block in matched], ["b-1", "b-2", "b-3", "b-4", "b-5"])

    def test_markdown_section_does_not_fallback_to_document_start(self):
        from backend.app.services.history_case_service import HistoryCaseService

        markdown = "# 技术文件\n\n# 业绩文件\n\n项目法人 | 服务范围 | 姓名 | 职称 | 证书"

        section = HistoryCaseService._extract_markdown_section(markdown, "服务范围")

        self.assertEqual(section, "")

    def test_docx_block_extraction_keeps_original_ooxml(self):
        import docx
        from backend.scripts.build_history_case_library import extract_docx_blocks

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_path = temp_root / "history.docx"
            document = docx.Document()
            document.add_heading("服务范围", level=1)
            document.add_paragraph("历史项目服务范围")
            table = document.add_table(rows=1, cols=2)
            table.rows[0].cells[0].text = "序号"
            table.rows[0].cells[1].text = "内容"
            document.save(source_path)

            payload = extract_docx_blocks(source_path, temp_root / "assets")
            blocks = payload["blocks"]

            self.assertTrue(any(block.get("docx_xml", "").startswith("<w:p") for block in blocks))
            self.assertTrue(any(block.get("docx_xml", "").startswith("<w:tbl") for block in blocks))
            self.assertTrue(all("heading_path" in block for block in blocks))
            self.assertEqual(blocks[1]["heading_path"][0]["title"], "服务范围")
            self.assertEqual(blocks[2]["heading_path"][0]["title"], "服务范围")

    def test_history_patch_updates_original_ooxml_text(self):
        from backend.app.services.openai_service import OpenAIService

        blocks = [
            {
                "id": "p-1",
                "type": "paragraph",
                "text": "历史项目服务范围",
                "markdown": "历史项目服务范围",
                "html": '<p data-history-block-id="p-1">历史项目服务范围</p>',
                "docx_xml": (
                    '<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    "<w:r><w:t>历史项目服务范围</w:t></w:r></w:p>"
                ),
            }
        ]

        patched = OpenAIService._apply_history_patch_to_blocks(
            blocks,
            [{"op": "replace_text", "block_id": "p-1", "from": "历史项目", "to": "当前项目"}],
        )

        self.assertIn("当前项目服务范围", patched[0]["docx_xml"])

    def test_word_export_uses_history_docx_as_style_template(self):
        import docx
        from docx.shared import Cm
        from backend.app.models.schemas import OutlineItem, WordExportRequest
        from backend.app.services.word_export_service import create_export_document

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "template.docx"
            template = docx.Document()
            template.sections[0].left_margin = Cm(3.3)
            template.add_paragraph("旧正文")
            template.save(template_path)

            request = WordExportRequest(
                manual_review_confirmed=True,
                outline=[
                    OutlineItem(
                        id="1",
                        title="服务范围",
                        description="",
                        history_reference={"source_paths": {"source_docx_path": str(template_path)}},
                    )
                ],
            )

            doc, inherited_path = create_export_document(request)

            self.assertEqual(inherited_path, template_path)
            self.assertAlmostEqual(int(doc.sections[0].left_margin), int(Cm(3.3)), delta=200)
            self.assertNotIn("旧正文", "\n".join(paragraph.text for paragraph in doc.paragraphs))

    def test_history_case_match_terms_prioritize_specific_project_terms(self):
        from backend.app.services.history_case_service import HistoryCaseService

        terms = HistoryCaseService._extract_match_terms(
            "中国石油辽宁销售公司2025年油库、加油站、新能源工程项目设计服务项目 工程设计 设计方案"
        )

        self.assertIn("中国石油辽宁销售公司2025年油库、加油站、新能源工程项目", terms[0])
        self.assertLess(terms.index("油库 工程设计"), terms.index("油库"))

    def test_history_case_match_deduplicates_same_project_document_hits(self):
        from backend.app.services.history_case_service import HistoryCaseService

        original_db_path = HistoryCaseService.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "history.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.executescript(
                    """
                    CREATE TABLE case_projects (
                        id TEXT PRIMARY KEY,
                        year TEXT,
                        batch TEXT,
                        sequence TEXT,
                        subject TEXT,
                        result TEXT,
                        primary_domain TEXT,
                        primary_subdomain TEXT,
                        domain_confidence REAL,
                        domain_keywords TEXT,
                        title TEXT,
                        source_path TEXT,
                        folder_name TEXT
                    );
                    CREATE TABLE case_documents (
                        id TEXT PRIMARY KEY,
                        project_id TEXT,
                        file_name TEXT,
                        source_path TEXT,
                        markdown_path TEXT,
                        pageindex_tree_path TEXT
                    );
                    CREATE VIRTUAL TABLE history_case_fts USING fts5(
                        project_id,
                        document_id,
                        project_title,
                        file_name,
                        body
                    );
                    """
                )
                projects = [
                    ("p1", "1", "重复文档油库设计项目"),
                    ("p2", "2", "单文档油库设计项目"),
                ]
                for project_id, sequence, title in projects:
                    conn.execute(
                        """
                        INSERT INTO case_projects(
                            id, year, batch, sequence, subject, result, primary_domain,
                            primary_subdomain, domain_confidence, domain_keywords,
                            title, source_path, folder_name
                        ) VALUES (?, '2025', '技术1', ?, '华正', '中标', '油库加油站',
                            '油库/加油站', 0.9, '["油库","设计"]', ?, '', ?)
                        """,
                        (project_id, sequence, title, title),
                    )
                docs = [
                    ("d1", "p1", "技术标.docx"),
                    ("d2", "p1", "技术标.pdf"),
                    ("d3", "p2", "技术标.docx"),
                ]
                for doc_id, project_id, file_name in docs:
                    conn.execute(
                        """
                        INSERT INTO case_documents(
                            id, project_id, file_name, source_path, markdown_path, pageindex_tree_path
                        ) VALUES (?, ?, ?, '', '', '')
                        """,
                        (doc_id, project_id, file_name),
                    )
                    conn.execute(
                        """
                        INSERT INTO history_case_fts(project_id, document_id, project_title, file_name, body)
                        VALUES (?, ?, '油库设计项目', ?, '油库 加油站 工程设计 服务方案')
                        """,
                        (project_id, doc_id, file_name),
                    )
                conn.commit()
            finally:
                conn.close()

            HistoryCaseService.DB_PATH = db_path
            try:
                candidates = HistoryCaseService.match_candidates("油库 工程设计", {}, limit=2)
                scores = {item["project_id"]: item["score"] for item in candidates}
                self.assertEqual(scores.get("p1"), scores.get("p2"))
            finally:
                HistoryCaseService.DB_PATH = original_db_path

    def test_history_reference_rule_based_profile_is_usable(self):
        from backend.app.routers.history_cases import _build_rule_based_reference_profile

        profile = _build_rule_based_reference_profile(
            "# 技术标\n\n## 服务方案\n\n### 质量保证措施\n正文",
            {"project_title": "历史油库设计案例"},
            "model unavailable",
        )

        self.assertEqual(profile["profile_name"], "历史案例库规则匹配模板")
        self.assertTrue(profile["outline_template"])
        self.assertTrue(profile["chapter_blueprints"])
        self.assertIn("model unavailable", profile["quality_risks"][-1]["fix_rule"])


if __name__ == "__main__":
    unittest.main()
