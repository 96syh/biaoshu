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
        self.assertIn("/api/outline/generate", paths)
        self.assertIn("/api/projects", paths)
        self.assertFalse(any(path.startswith("/api/search") for path in paths))
        self.assertFalse(any(path.startswith("/api/expand") for path in paths))
        self.assertNotIn("duckduckgo_search", sys.modules)

    def test_runtime_data_defaults_to_artifacts(self):
        from backend.app.services.file_service import FileService
        from backend.app.services.history_case_service import HistoryCaseService
        from backend.app.services.project_service import ProjectService

        self.assertIn("artifacts/data/generated_assets", str(FileService.GENERATED_ASSET_DIR))
        self.assertIn("artifacts/data/history_cases.sqlite3", str(HistoryCaseService.DB_PATH))
        self.assertIn("artifacts/data/projects.sqlite3", str(ProjectService.DB_PATH))

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


if __name__ == "__main__":
    unittest.main()
