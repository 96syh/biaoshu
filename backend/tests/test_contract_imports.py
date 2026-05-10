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
