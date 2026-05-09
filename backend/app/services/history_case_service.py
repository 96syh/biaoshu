"""本地历史标书案例库检索服务。"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class HistoryCaseService:
    """Read-only access to the generated historical bid case library."""

    REPO_ROOT = Path(__file__).resolve().parents[3]
    HISTORY_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "data" / "history_cases"
    LEGACY_HISTORY_ARTIFACT_ROOT = REPO_ROOT / "backend" / "data" / "history_cases"
    DB_PATH = Path(
        os.getenv(
            "YIBIAO_HISTORY_CASE_DB_PATH",
            str(REPO_ROOT / "artifacts" / "data" / "history_cases.sqlite3"),
        )
    )
    MATCH_HINTS = [
        "石油", "中石油", "中石化", "油库", "加油站", "加能站", "油罐",
        "燃气", "天然气", "LNG", "CNG", "加气", "气化",
        "化工", "煤化工", "炼化", "合成氨", "纯苯", "硝酸",
        "光伏", "新能源", "充电", "电力", "储能", "国网",
        "氢", "制氢", "加氢", "输氢",
        "管道", "输气", "输油", "场站", "管线", "增压",
        "消防", "可研", "勘察", "设计", "初设", "施工图", "框架",
        "部队", "某部", "油料", "服务区", "高速", "园区",
    ]
    REQUIREMENT_KEYWORDS = [
        "资质", "资格", "证书", "许可证", "业绩", "合同", "项目负责人", "人员",
        "注册", "职称", "财务", "审计", "信誉", "信用", "失信", "行贿",
        "安全生产许可证", "质量", "进度", "方案", "服务", "技术", "响应",
        "压力管道", "特种设备", "工程设计", "工程咨询", "化工石化医药",
        "石油化工", "市政公用", "消防", "勘察", "可研", "初设", "施工图",
    ]
    OBJECT_GROUPS = {
        "oil_depot_station": ("油库", "加油站", "加能站", "油罐", "服务区", "销售公司"),
        "pipeline": ("管道", "管线", "输油", "输气", "油管", "迁改", "增压"),
        "gas_lng": ("燃气", "天然气", "LNG", "CNG", "加气"),
        "chemical": ("化工", "煤化工", "炼化", "合成氨", "硝酸", "纯苯"),
        "new_energy": ("光伏", "新能源", "充电", "储能", "电力"),
        "hydrogen": ("氢", "制氢", "加氢", "输氢"),
    }
    SERVICE_GROUPS = {
        "design": ("工程设计", "设计服务", "设计商", "施工图", "初步设计", "初设"),
        "feasibility": ("可研", "可行性研究"),
        "survey": ("勘察", "测绘"),
        "consulting": ("咨询", "评估", "造价"),
    }

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(str(cls.DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def _resolve_history_artifact_path(cls, raw_path: str) -> Path:
        """Resolve persisted history artifact paths across data directory moves."""
        path_text = str(raw_path or "").strip()
        if not path_text:
            return Path()

        original = Path(path_text)
        candidates = [original]
        marker_roots = (
            ("backend/data/history_cases/", cls.HISTORY_ARTIFACT_ROOT),
            ("artifacts/data/history_cases/", cls.HISTORY_ARTIFACT_ROOT),
        )
        for marker, target_root in marker_roots:
            if marker in path_text:
                suffix = path_text.split(marker, 1)[1]
                candidates.append(target_root / suffix)

        try:
            candidates.append(cls.HISTORY_ARTIFACT_ROOT / original.relative_to(cls.LEGACY_HISTORY_ARTIFACT_ROOT))
        except ValueError:
            pass

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return original

    @classmethod
    def _normalize_artifact_path_for_response(cls, raw_path: Any) -> str:
        resolved = cls._resolve_history_artifact_path(str(raw_path or ""))
        return str(resolved) if str(resolved) else ""

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        if not cls.DB_PATH.exists():
            return {
                "ready": False,
                "project_count": 0,
                "document_count": 0,
                "indexed_document_count": 0,
                "failed_document_count": 0,
                "db_path": str(cls.DB_PATH),
            }

        with cls._connect() as conn:
            project_count = conn.execute("SELECT COUNT(*) AS count FROM case_projects").fetchone()["count"]
            document_count = conn.execute("SELECT COUNT(*) AS count FROM case_documents").fetchone()["count"]
            indexed_count = conn.execute(
                "SELECT COUNT(*) AS count FROM case_documents WHERE status='indexed'"
            ).fetchone()["count"]
            failed_count = conn.execute(
                "SELECT COUNT(*) AS count FROM case_documents WHERE status!='indexed'"
            ).fetchone()["count"]
            by_year = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT year, COUNT(*) AS count
                    FROM case_projects
                    GROUP BY year
                    ORDER BY year
                    """
                ).fetchall()
            ]
            by_result = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT result, COUNT(*) AS count
                    FROM case_projects
                    GROUP BY result
                    ORDER BY count DESC, result
                    """
                ).fetchall()
            ]
            by_extension = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT extension, COUNT(*) AS count
                    FROM case_documents
                    GROUP BY extension
                    ORDER BY count DESC, extension
                    """
                ).fetchall()
            ]
            by_domain = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT primary_domain AS domain, COUNT(*) AS count
                    FROM case_projects
                    GROUP BY primary_domain
                    ORDER BY count DESC, primary_domain
                    """
                ).fetchall()
            ]
        return {
            "ready": True,
            "project_count": project_count,
            "document_count": document_count,
            "indexed_document_count": indexed_count,
            "failed_document_count": failed_count,
            "by_year": by_year,
            "by_result": by_result,
            "by_extension": by_extension,
            "by_domain": by_domain,
            "db_path": str(cls.DB_PATH),
        }

    @classmethod
    def list_projects(
        cls,
        limit: int = 100,
        year: str = "",
        subject: str = "",
        result: str = "",
        domain: str = "",
    ) -> List[Dict[str, Any]]:
        if not cls.DB_PATH.exists():
            return []

        where = []
        params: list[Any] = []
        if year:
            where.append("p.year = ?")
            params.append(year)
        if subject:
            where.append("p.subject LIKE ?")
            params.append(f"%{subject}%")
        if result:
            where.append("p.result LIKE ?")
            params.append(f"%{result}%")
        if domain:
            where.append(
                """
                (
                    p.primary_domain LIKE ?
                    OR p.primary_subdomain LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM case_project_domains cpd
                        WHERE cpd.project_id = p.id
                          AND (cpd.domain LIKE ? OR cpd.subdomain LIKE ?)
                    )
                )
                """
            )
            params.extend([f"%{domain}%", f"%{domain}%", f"%{domain}%", f"%{domain}%"])
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit)

        with cls._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.*,
                    COUNT(d.id) AS document_count,
                    SUM(CASE WHEN d.status='indexed' THEN 1 ELSE 0 END) AS indexed_document_count
                FROM case_projects p
                LEFT JOIN case_documents d ON d.project_id = p.id
                {where_sql}
                GROUP BY p.id
                ORDER BY p.year, p.batch, CAST(p.sequence AS REAL), p.sequence
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    @classmethod
    def list_domains(cls) -> List[Dict[str, Any]]:
        if not cls.DB_PATH.exists():
            return []

        with cls._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    domain,
                    subdomain,
                    COUNT(*) AS project_count,
                    ROUND(AVG(confidence), 2) AS avg_confidence,
                    GROUP_CONCAT(DISTINCT keywords) AS keyword_groups
                FROM case_project_domains
                GROUP BY domain, subdomain
                ORDER BY project_count DESC, domain, subdomain
                """
            ).fetchall()
            return [dict(row) for row in rows]

    @classmethod
    def search(cls, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not cls.DB_PATH.exists() or not query.strip():
            return []

        normalized_query = query.strip()
        with cls._connect() as conn:
            try:
                fts_rows = conn.execute(
                    """
                    SELECT
                        bm25(history_case_fts) AS rank,
                        p.id AS project_id,
                        p.year,
                        p.batch,
                        p.sequence,
                        p.subject,
                        p.result,
                        p.primary_domain,
                        p.primary_subdomain,
                        p.domain_confidence,
                        p.domain_keywords,
                        p.title AS project_title,
                        p.source_path AS project_path,
                        d.id AS document_id,
                        d.file_name,
                        d.source_path AS document_path,
                        d.markdown_path,
                        d.pageindex_tree_path,
                        snippet(history_case_fts, 4, '[', ']', '...', 24) AS snippet
                    FROM history_case_fts
                    JOIN case_projects p ON p.id = history_case_fts.project_id
                    JOIN case_documents d ON d.id = history_case_fts.document_id
                    WHERE history_case_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (normalized_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                fts_rows = []
            results = [dict(row) for row in fts_rows]
            seen_document_ids = {row["document_id"] for row in results}
            if len(results) >= limit:
                return results

            like = f"%{normalized_query}%"
            fallback_rows = conn.execute(
                """
                SELECT
                    0.0 AS rank,
                    p.id AS project_id,
                    p.year,
                    p.batch,
                    p.sequence,
                    p.subject,
                    p.result,
                    p.primary_domain,
                    p.primary_subdomain,
                    p.domain_confidence,
                    p.domain_keywords,
                    p.title AS project_title,
                    p.source_path AS project_path,
                    d.id AS document_id,
                    d.file_name,
                    d.source_path AS document_path,
                    d.markdown_path,
                    d.pageindex_tree_path,
                    history_case_fts.body AS body
                FROM history_case_fts
                JOIN case_projects p ON p.id = history_case_fts.project_id
                JOIN case_documents d ON d.id = history_case_fts.document_id
                WHERE
                    p.title LIKE ?
                    OR p.subject LIKE ?
                    OR p.result LIKE ?
                    OR p.primary_domain LIKE ?
                    OR p.primary_subdomain LIKE ?
                    OR p.domain_keywords LIKE ?
                    OR p.folder_name LIKE ?
                    OR d.file_name LIKE ?
                    OR history_case_fts.body LIKE ?
                ORDER BY p.year, p.batch, CAST(p.sequence AS REAL), p.sequence, d.file_name
                LIMIT ?
                """,
                (like, like, like, like, like, like, like, like, like, limit * 3),
            ).fetchall()
            for row in fallback_rows:
                if row["document_id"] in seen_document_ids:
                    continue
                record = dict(row)
                body = str(record.pop("body") or "")
                record["snippet"] = cls._make_snippet(
                    query=normalized_query,
                    body=body,
                    fallback=" ".join(
                        str(record.get(key) or "")
                        for key in ("project_title", "subject", "result", "file_name")
                    ),
                )
                results.append(record)
                seen_document_ids.add(row["document_id"])
                if len(results) >= limit:
                    break
            return results

    @classmethod
    def match_candidates(
        cls,
        tender_text: str,
        analysis_report: Dict[str, Any] | None = None,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """召回并按规则分数聚合历史案例候选。"""
        if not cls.DB_PATH.exists():
            return []

        query_text = cls._build_match_query_text(tender_text, analysis_report or {})
        query_terms = cls._extract_match_terms(query_text)
        project_scores: dict[str, Dict[str, Any]] = {}

        def add_result(row: Dict[str, Any], score: float, reason: str) -> None:
            project_id = str(row.get("project_id") or "")
            if not project_id:
                return
            record = project_scores.setdefault(project_id, {
                "project_id": project_id,
                "year": row.get("year", ""),
                "batch": row.get("batch", ""),
                "sequence": row.get("sequence", ""),
                "subject": row.get("subject", ""),
                "result": row.get("result", ""),
                "primary_domain": row.get("primary_domain", ""),
                "primary_subdomain": row.get("primary_subdomain", ""),
                "domain_confidence": row.get("domain_confidence", 0),
                "domain_keywords": row.get("domain_keywords", "[]"),
                "project_title": row.get("project_title", ""),
                "project_path": row.get("project_path", ""),
                "best_document_id": row.get("document_id", ""),
                "best_file_name": row.get("file_name", ""),
                "best_document_path": row.get("document_path", ""),
                "markdown_path": cls._normalize_artifact_path_for_response(row.get("markdown_path", "")),
                "pageindex_tree_path": cls._normalize_artifact_path_for_response(row.get("pageindex_tree_path", "")),
                "snippet": row.get("snippet", ""),
                "score": 0.0,
                "match_reasons": [],
                "_scored_hit_keys": set(),
            })
            scored_hit_keys = record.setdefault("_scored_hit_keys", set())
            if reason not in scored_hit_keys:
                record["score"] = float(record["score"]) + score
                scored_hit_keys.add(reason)
            if reason not in record["match_reasons"]:
                record["match_reasons"].append(reason)
            if row.get("snippet") and len(str(row.get("snippet"))) > len(str(record.get("snippet") or "")):
                record["snippet"] = row.get("snippet")
                record["best_document_id"] = row.get("document_id", "")
                record["best_file_name"] = row.get("file_name", "")
                record["best_document_path"] = row.get("document_path", "")
                record["markdown_path"] = cls._normalize_artifact_path_for_response(row.get("markdown_path", ""))
                record["pageindex_tree_path"] = cls._normalize_artifact_path_for_response(row.get("pageindex_tree_path", ""))

        for index, term in enumerate(query_terms[:10]):
            for row in cls.search(term, limit=12):
                add_result(row, max(1.0, 10.0 - index), f"关键词命中：{term}")

        with cls._connect() as conn:
            for term in query_terms[:8]:
                rows = conn.execute(
                    """
                    SELECT
                        p.id AS project_id,
                        p.year,
                        p.batch,
                        p.sequence,
                        p.subject,
                        p.result,
                        p.primary_domain,
                        p.primary_subdomain,
                        p.domain_confidence,
                        p.domain_keywords,
                        p.title AS project_title,
                        p.source_path AS project_path,
                        d.id AS document_id,
                        d.file_name,
                        d.source_path AS document_path,
                        d.markdown_path,
                        d.pageindex_tree_path,
                        '' AS snippet
                    FROM case_projects p
                    JOIN case_documents d ON d.project_id = p.id
                    WHERE p.primary_domain LIKE ?
                       OR p.primary_subdomain LIKE ?
                       OR p.title LIKE ?
                       OR p.folder_name LIKE ?
                    GROUP BY p.id
                    LIMIT 20
                    """,
                    (f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%"),
                ).fetchall()
                for row in rows:
                    add_result(dict(row), 3.0, f"元数据命中：{term}")

        cls._apply_reference_match_rerank(project_scores.values(), query_text)
        candidates = sorted(project_scores.values(), key=lambda item: (-float(item["score"]), item["year"], item["batch"]))[:limit]
        for index, item in enumerate(candidates, 1):
            item["rank"] = index
            item["score"] = round(float(item["score"]), 2)
            item.pop("_scored_hit_keys", None)
        return candidates

    @classmethod
    def validate_reference_selection(
        cls,
        selected: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        tender_text: str,
        analysis_report: Dict[str, Any] | None = None,
    ) -> tuple[Dict[str, Any], str]:
        """防止 LLM 为了“中标”选择领域明显错配的历史案例。"""
        if not selected or not candidates:
            return selected, ""
        best = candidates[0]
        if selected.get("project_id") == best.get("project_id"):
            return selected, ""

        query_text = cls._build_match_query_text(tender_text, analysis_report or {})
        query_groups = cls._object_groups(query_text)
        selected_groups = cls._object_groups(cls._candidate_match_text(selected))
        best_groups = cls._object_groups(cls._candidate_match_text(best))
        selected_score = float(selected.get("score") or 0)
        best_score = float(best.get("score") or 0)

        # 典型误选：当前是油库/加油站设计框架，LLM 选了中标的油管/管道迁改。
        if (
            "oil_depot_station" in query_groups
            and "oil_depot_station" not in selected_groups
            and "pipeline" in selected_groups
            and "oil_depot_station" in best_groups
        ):
            return best, "LLM 选择被规则纠偏：当前项目核心对象是油库/加油站，候选为油管/管道迁改，领域对象不匹配。"

        if query_groups and not (query_groups & selected_groups) and (query_groups & best_groups) and selected_score < best_score + 8:
            return best, "LLM 选择被规则纠偏：所选案例缺少当前项目核心对象命中，已使用规则得分最高且对象匹配的案例。"

        return selected, ""

    @classmethod
    def load_markdown(cls, markdown_path: str, max_chars: int = 60000) -> str:
        path = cls._resolve_history_artifact_path(markdown_path)
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]

    @classmethod
    def check_requirements(
        cls,
        analysis_report: Dict[str, Any] | None,
        limit_per_item: int = 3,
    ) -> Dict[str, Any]:
        """用中标历史案例库逐项检索评分项、资质项是否已有可复用满足证据。"""
        items = cls.extract_requirement_check_items(analysis_report or {})
        checks: list[dict[str, Any]] = []
        for item in items:
            checks.append(cls._check_single_requirement(item, limit_per_item=limit_per_item))

        satisfied_count = sum(1 for check in checks if check.get("satisfied"))
        return {
            "summary": {
                "total": len(checks),
                "satisfied": satisfied_count,
                "not_found": len(checks) - satisfied_count,
            },
            "checks": checks,
        }

    @classmethod
    def extract_requirement_check_items(cls, analysis_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从标准解析报告抽取需要对照历史库的资质类和打分类条目。"""
        if not isinstance(analysis_report, dict):
            return []

        sources: list[tuple[str, str, list[dict[str, Any]]]] = [
            ("qualification", "资格审查", cls._as_dict_items(analysis_report.get("qualification_review_items"))),
            ("qualification", "资格要求", cls._as_dict_items(analysis_report.get("qualification_requirements"))),
            ("scoring", "技术评分", cls._as_dict_items(analysis_report.get("technical_scoring_items"))),
            ("scoring", "商务评分", cls._as_dict_items(analysis_report.get("business_scoring_items"))),
            ("scoring", "价格/其他评分", cls._as_dict_items(analysis_report.get("price_scoring_items"))),
        ]

        price_rules = analysis_report.get("price_rules")
        if isinstance(price_rules, dict) and any(price_rules.values()):
            sources.append(("scoring", "报价规则", [{
                "id": "PRICE-RULE",
                "name": "投标报价",
                "score": price_rules.get("score") or "按规则计算",
                "logic": "；".join(
                    str(price_rules.get(key) or "")
                    for key in (
                        "quote_method",
                        "maximum_price_rule",
                        "abnormally_low_price_rule",
                        "arithmetic_correction_rule",
                        "missing_item_rule",
                    )
                    if price_rules.get(key)
                ),
                "source": price_rules.get("source_ref"),
            }]))

        items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for category, category_label, records in sources:
            for index, record in enumerate(records):
                item_id = str(record.get("id") or f"{category}-{category_label}-{index + 1}")
                if item_id in seen_ids:
                    item_id = f"{item_id}-{index + 1}"
                seen_ids.add(item_id)
                label = cls._first_text(
                    record.get("name"),
                    record.get("review_type"),
                    record.get("target"),
                    record.get("title"),
                    record.get("clause"),
                    record.get("id"),
                    fallback=f"{category_label}{index + 1}",
                )
                requirement = "；".join(
                    part
                    for part in [
                        cls._text(record.get("standard")),
                        cls._text(record.get("requirement")),
                        cls._text(record.get("criterion")),
                        cls._text(record.get("logic")),
                        cls._text(record.get("response_strategy")),
                        cls._join_list(record.get("required_materials"), "材料"),
                        cls._join_list(record.get("evidence_requirements"), "证据"),
                    ]
                    if part
                )
                query_text = "；".join(part for part in [
                    label,
                    cls._text(record.get("score")),
                    requirement,
                    cls._text(record.get("source")),
                    cls._text(record.get("source_ref")),
                ] if part)
                if not query_text.strip():
                    continue
                items.append({
                    "item_id": item_id,
                    "category": category,
                    "category_label": category_label,
                    "label": label,
                    "score": cls._text(record.get("score") or record.get("weight") or record.get("points")),
                    "requirement": requirement or query_text,
                    "query_text": query_text,
                })

        cls._append_parse_section_check_items(items, seen_ids, analysis_report)
        return items[:120]

    @classmethod
    def _append_parse_section_check_items(
        cls,
        items: list[dict[str, Any]],
        seen_ids: set[str],
        analysis_report: Dict[str, Any],
    ) -> None:
        """补充前端解析页分组项，让历史库核对结果能直接映射到左侧选项。"""
        project = analysis_report.get("project") if isinstance(analysis_report.get("project"), dict) else {}
        bid_doc = analysis_report.get("bid_document_requirements") if isinstance(analysis_report.get("bid_document_requirements"), dict) else {}
        selected_target = bid_doc.get("selected_generation_target") if isinstance(bid_doc.get("selected_generation_target"), dict) else {}
        base_outline = cls._as_dict_items(selected_target.get("base_outline_items"))
        scheme_outline = cls._as_dict_items(bid_doc.get("scheme_or_technical_outline_requirements"))
        composition = cls._as_dict_items(bid_doc.get("composition"))
        fixed_forms = cls._as_dict_items(analysis_report.get("fixed_format_forms"))
        all_requirement_items = (
            cls._as_dict_items(analysis_report.get("qualification_requirements"))
            + cls._as_dict_items(analysis_report.get("qualification_review_items"))
            + cls._as_dict_items(analysis_report.get("formal_review_items"))
            + cls._as_dict_items(analysis_report.get("responsiveness_review_items"))
            + cls._as_dict_items(analysis_report.get("formal_response_requirements"))
            + cls._as_dict_items(analysis_report.get("mandatory_clauses"))
            + cls._as_dict_items(analysis_report.get("rejection_risks"))
            + cls._as_dict_items(analysis_report.get("required_materials"))
            + fixed_forms
            + cls._as_dict_items(analysis_report.get("signature_requirements"))
            + cls._as_dict_items(analysis_report.get("evidence_chain_requirements"))
        )

        def add(item_id: str, category: str, category_label: str, label: str, parts: list[Any]) -> None:
            if item_id in seen_ids:
                return
            query_text = "；".join(
                cls._text(part)
                for part in parts
                if cls._text(part)
            )
            if not query_text.strip():
                return
            seen_ids.add(item_id)
            items.append({
                "item_id": item_id,
                "category": category,
                "category_label": category_label,
                "label": label,
                "score": "",
                "requirement": query_text,
                "query_text": f"{label}；{query_text}",
            })

        def item_text(records: list[dict[str, Any]], keywords: tuple[str, ...] = ()) -> str:
            texts: list[str] = []
            for record in records:
                text = "；".join(
                    cls._text(record.get(key))
                    for key in (
                        "title", "name", "review_type", "target", "requirement",
                        "standard", "criterion", "logic", "risk", "clause",
                        "source", "source_ref", "purpose", "requirement_summary",
                    )
                    if cls._text(record.get(key))
                )
                if not keywords or any(keyword in text for keyword in keywords):
                    texts.append(text)
            return "；".join(texts[:8])

        project_parts = [
            project.get("name"),
            project.get("number"),
            project.get("purchaser"),
            project.get("agency"),
            project.get("service_scope"),
            project.get("service_period"),
            project.get("quality_requirements"),
            project.get("submission_requirements"),
            project.get("signature_requirements"),
        ]
        add("basic-owner", "parse_section", "基础信息", "招标人/代理信息", [project.get("purchaser"), project.get("agency"), project.get("name")])
        add("basic-project", "parse_section", "基础信息", "项目信息", [project.get("name"), project.get("number"), project.get("project_type"), project.get("budget"), project.get("maximum_price")])
        add("basic-time", "parse_section", "基础信息", "关键时间/内容", [project.get("bid_deadline"), project.get("opening_time"), project.get("service_period"), project.get("service_scope")])
        add("basic-bond", "parse_section", "基础信息", "保证金相关", [project.get("bid_bond"), project.get("performance_bond")])
        add("basic-other", "parse_section", "基础信息", "其他信息", [project.get("service_location"), project.get("quality_requirements"), project.get("bid_validity"), project.get("submission_method")])

        add("qualification-review", "parse_section", "资格审查", "资格评审", [item_text(all_requirement_items, ("资格", "资质", "业绩", "人员", "信誉", "财务", "联合体"))])
        add("qualification-formal", "parse_section", "资格审查", "形式评审标准", [item_text(cls._as_dict_items(analysis_report.get("formal_review_items")))])
        add("qualification-responsive", "parse_section", "资格审查", "响应性评审标准", [item_text(cls._as_dict_items(analysis_report.get("responsiveness_review_items")) + cls._as_dict_items(analysis_report.get("formal_response_requirements")) + cls._as_dict_items(analysis_report.get("mandatory_clauses")))])

        add("document-composition", "parse_section", "投标文件要求", "投标文件组成", [item_text(composition)])
        add("document-price", "parse_section", "投标文件要求", "投标报价要求", [
            item_text(cls._as_dict_items([analysis_report.get("price_rules")]) if isinstance(analysis_report.get("price_rules"), dict) else []),
        ])
        add("document-submit", "parse_section", "投标文件要求", "投标文件递交方式", [project.get("submission_method"), project.get("submission_requirements"), project.get("electronic_platform"), project.get("signature_requirements")])
        add("document-scheme", "parse_section", "投标文件要求", "方案要求", [selected_target.get("target_title"), selected_target.get("base_outline_strategy"), item_text(base_outline + scheme_outline), item_text(fixed_forms)])

        add("process-opening", "parse_section", "开评定标流程", "开标", [project.get("opening_time"), project.get("bid_deadline"), project.get("electronic_platform"), item_text(all_requirement_items, ("开标", "解密", "签到", "开标大厅"))])
        add("process-review", "parse_section", "开评定标流程", "评标", [item_text(all_requirement_items, ("评标", "评审", "澄清", "修正"))])
        add("process-award", "parse_section", "开评定标流程", "定标", [item_text(all_requirement_items, ("定标", "中标", "推荐中标", "候选人"))])
        add("process-followup", "parse_section", "开评定标流程", "后续要求", [item_text(all_requirement_items, ("合同", "履约", "服务费", "通知书", "公示", "质疑"))])

        add("supplement-tech-spec", "parse_section", "补充信息归纳", "技术规格", [
            project.get("service_scope"),
            project.get("quality_requirements"),
            item_text(cls._as_dict_items(analysis_report.get("technical_scoring_items")) + scheme_outline, ("技术", "规格", "服务", "设计", "方案")),
        ])
        add("supplement-contract-time", "parse_section", "补充信息归纳", "合同时间", [project.get("service_period")])
        add("supplement-background", "parse_section", "补充信息归纳", "项目背景", [project.get("name"), project.get("project_type"), project.get("funding_source")])
        add("supplement-format", "parse_section", "补充信息归纳", "方案与格式要求", [selected_target.get("target_title"), item_text(base_outline + scheme_outline)])
        add("supplement-special", "parse_section", "补充信息归纳", "其他特殊要求", [item_text(all_requirement_items, ("特殊", "必须", "不得", "承诺", "偏离", "暗标"))])
        add("supplement-sample", "parse_section", "补充信息归纳", "样品要求", [item_text(all_requirement_items, ("样品", "样本", "演示"))])
        add("supplement-payment", "parse_section", "补充信息归纳", "付款方式", [item_text(all_requirement_items, ("付款", "支付", "价款", "结算"))])
        add("supplement-share", "parse_section", "补充信息归纳", "中标份额分配规则", [item_text(all_requirement_items, ("份额", "分配", "中标份额"))])
        add("supplement-count", "parse_section", "补充信息归纳", "中标数量规则", [item_text(all_requirement_items, ("中标数量", "入围", "候选人数量", "标包数量"))])

    @classmethod
    def _check_single_requirement(cls, item: Dict[str, Any], limit_per_item: int) -> Dict[str, Any]:
        terms = cls._requirement_search_terms(item.get("query_text") or item.get("requirement") or item.get("label") or "")
        evidence: list[dict[str, Any]] = []
        seen_documents: set[str] = set()
        matched_terms: set[str] = set()

        for term in terms:
            for row in cls.search(term, limit=max(4, limit_per_item * 2)):
                document_id = str(row.get("document_id") or "")
                if document_id in seen_documents:
                    continue
                seen_documents.add(document_id)
                haystack = " ".join(
                    str(row.get(key) or "")
                    for key in ("project_title", "subject", "result", "primary_domain", "file_name", "snippet")
                )
                term_hits = [candidate for candidate in terms if candidate and candidate in haystack]
                if term_hits:
                    matched_terms.update(term_hits)
                evidence.append({
                    "project_id": row.get("project_id"),
                    "project_title": row.get("project_title"),
                    "result": row.get("result"),
                    "primary_domain": row.get("primary_domain"),
                    "primary_subdomain": row.get("primary_subdomain"),
                    "document_id": row.get("document_id"),
                    "file_name": row.get("file_name"),
                    "document_path": row.get("document_path"),
                    "pageindex_tree_path": row.get("pageindex_tree_path"),
                    "snippet": row.get("snippet"),
                    "matched_term": term,
                    "is_winning_case": "中标" in str(row.get("result") or ""),
                })
                if len(evidence) >= limit_per_item * 3:
                    break
            if len(evidence) >= limit_per_item * 3:
                break

        evidence.sort(key=lambda row: (not row.get("is_winning_case"), str(row.get("project_title") or "")))
        evidence = evidence[:limit_per_item]
        winning_hits = [row for row in evidence if row.get("is_winning_case")]
        confidence = cls._requirement_confidence(item, evidence, matched_terms)
        satisfied = bool(winning_hits and confidence >= 0.35)
        reason = (
            f"命中 {len(winning_hits)} 个中标历史案例，关键词：{'、'.join(list(matched_terms)[:4]) or '要求文本'}"
            if satisfied
            else ("历史库有相似案例但未命中中标证据" if evidence else "历史库未检索到可支撑该要求的中标案例")
        )

        return {
            "item_id": item.get("item_id"),
            "category": item.get("category"),
            "category_label": item.get("category_label"),
            "label": item.get("label"),
            "score": item.get("score"),
            "requirement": item.get("requirement"),
            "search_terms": terms,
            "satisfied": satisfied,
            "confidence": round(confidence, 2),
            "reason": reason,
            "evidence": evidence,
        }

    @classmethod
    def _requirement_confidence(
        cls,
        item: Dict[str, Any],
        evidence: list[dict[str, Any]],
        matched_terms: set[str],
    ) -> float:
        if not evidence:
            return 0.0
        score = 0.2 + min(0.35, len(matched_terms) * 0.08)
        if any(row.get("is_winning_case") for row in evidence):
            score += 0.25
        if item.get("category") == "qualification" and any(
            keyword in str(item.get("query_text") or "")
            for keyword in ("资质", "资格", "业绩", "人员", "注册", "许可证", "信誉", "财务")
        ):
            score += 0.1
        return min(score, 0.95)

    @classmethod
    def _requirement_search_terms(cls, text: str) -> List[str]:
        normalized = re.sub(r"\s+", "", str(text or ""))
        terms: list[str] = []

        for keyword in cls.REQUIREMENT_KEYWORDS:
            if keyword in normalized and keyword not in terms:
                terms.append(keyword)

        patterns = [
            r"[\u4e00-\u9fffA-Za-z0-9（）()]{0,12}(?:资质|资格|证书|许可证|业绩|项目负责人|注册|职称|压力管道|特种设备|安全生产许可证|财务|审计|信誉|信用|方案|服务|质量)[\u4e00-\u9fffA-Za-z0-9（）()甲乙丙级一二三级]{0,20}",
            r"(?:石油化工|化工石化医药|市政公用|建筑|电力|消防|工程设计|工程咨询|压力管道|特种设备)[\u4e00-\u9fffA-Za-z0-9（）()甲乙丙级一二三级]{0,20}",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, normalized):
                cleaned = match.strip("：:，,。；; ")
                if 2 <= len(cleaned) <= 36 and cleaned not in terms:
                    terms.append(cleaned)

        for chunk in re.split(r"[；;。,.，、：:\n\r]", str(text or "")):
            cleaned = re.sub(r"\s+", "", chunk)
            if 4 <= len(cleaned) <= 28 and cleaned not in terms:
                terms.append(cleaned)

        if not terms and normalized:
            terms.append(normalized[:24])
        return terms[:8]

    @staticmethod
    def _as_dict_items(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _first_text(cls, *values: Any, fallback: str = "") -> str:
        for value in values:
            text = cls._text(value)
            if text:
                return text
        return fallback

    @classmethod
    def _join_list(cls, value: Any, label: str) -> str:
        if not isinstance(value, list) or not value:
            return ""
        parts = [cls._text(item) for item in value if cls._text(item)]
        return f"{label}：{'、'.join(parts)}" if parts else ""

    @classmethod
    def _build_match_query_text(cls, tender_text: str, analysis_report: Dict[str, Any]) -> str:
        parts = [tender_text[:12000]]
        project = analysis_report.get("project") if isinstance(analysis_report, dict) else None
        if isinstance(project, dict):
            parts.extend(
                str(project.get(key) or "")
                for key in (
                    "name",
                    "number",
                    "owner",
                    "purchaser",
                    "location",
                    "service_location",
                    "scope",
                    "service_scope",
                    "project_type",
                )
            )
        bid_doc = analysis_report.get("bid_document_requirements") if isinstance(analysis_report, dict) else None
        selected = bid_doc.get("selected_generation_target") if isinstance(bid_doc, dict) else None
        if isinstance(selected, dict):
            parts.extend(str(selected.get(key) or "") for key in ("target_title", "reason", "source"))
        for key in ("technical_scoring_items", "technical_score_items", "service_requirements"):
            value = analysis_report.get(key) if isinstance(analysis_report, dict) else None
            if value:
                parts.append(json.dumps(value, ensure_ascii=False)[:4000])
        if isinstance(bid_doc, dict):
            for key in ("scheme_or_technical_outline_requirements", "composition"):
                value = bid_doc.get(key)
                if value:
                    parts.append(json.dumps(value, ensure_ascii=False)[:4000])
        return "\n".join(part for part in parts if part)

    @classmethod
    def _extract_match_terms(cls, text: str) -> List[str]:
        terms: list[str] = []
        normalized = text or ""

        def add(term: str) -> None:
            cleaned = re.sub(r"\s+", " ", str(term or "")).strip("：:，,。；; ")
            if cleaned and cleaned not in terms:
                terms.append(cleaned)

        title_candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9（）()、\-]{4,38}(?:项目|工程|服务|采购|设计|可研|初设|专篇|框架)", normalized)
        for term in title_candidates[:8]:
            add(term)

        object_keywords = [
            keyword
            for keywords in cls.OBJECT_GROUPS.values()
            for keyword in keywords
            if keyword in normalized
        ]
        service_keywords = [
            keyword
            for keywords in cls.SERVICE_GROUPS.values()
            for keyword in keywords
            if keyword in normalized
        ]
        for object_keyword in object_keywords[:4]:
            for service_keyword in service_keywords[:3]:
                add(f"{object_keyword} {service_keyword}")

        for hint in cls.MATCH_HINTS:
            if hint and hint in normalized:
                add(hint)

        if not terms:
            compact = re.sub(r"\s+", "", normalized)
            if compact:
                add(compact[:24])
        return terms[:14]

    @classmethod
    def _object_groups(cls, text: str) -> set[str]:
        normalized = str(text or "")
        return {
            group
            for group, keywords in cls.OBJECT_GROUPS.items()
            if any(keyword in normalized for keyword in keywords)
        }

    @classmethod
    def _service_groups(cls, text: str) -> set[str]:
        normalized = str(text or "")
        return {
            group
            for group, keywords in cls.SERVICE_GROUPS.items()
            if any(keyword in normalized for keyword in keywords)
        }

    @staticmethod
    def _candidate_match_text(candidate: Dict[str, Any]) -> str:
        return " ".join(
            str(candidate.get(key) or "")
            for key in (
                "project_title",
                "subject",
                "primary_domain",
                "primary_subdomain",
                "domain_keywords",
                "best_file_name",
                "snippet",
            )
        )

    @classmethod
    def _apply_reference_match_rerank(cls, candidates: Any, query_text: str) -> None:
        query_groups = cls._object_groups(query_text)
        query_services = cls._service_groups(query_text)
        query_has_cnpc = bool(re.search(r"中国石油|中石油|CNPC", query_text, flags=re.IGNORECASE))

        for item in candidates:
            candidate_text = cls._candidate_match_text(item)
            candidate_groups = cls._object_groups(candidate_text)
            candidate_services = cls._service_groups(candidate_text)
            common_groups = query_groups & candidate_groups
            common_services = query_services & candidate_services
            adjustment = 0.0

            if common_groups:
                adjustment += 18.0 * len(common_groups)
                item["match_reasons"].append(f"核心对象匹配：{'、'.join(sorted(common_groups))}")

            if common_services:
                adjustment += 14.0 * len(common_services)
                item["match_reasons"].append(f"服务类型匹配：{'、'.join(sorted(common_services))}")

            if "design" in query_services and "design" not in candidate_services:
                adjustment -= 8.0
                item["match_reasons"].append("服务类型降权：当前为工程设计服务，候选缺少设计服务特征")
                if "feasibility" in candidate_services:
                    adjustment -= 12.0
                    item["match_reasons"].append("服务类型降权：候选偏可研编制")

            if "oil_depot_station" in query_groups:
                if "oil_depot_station" in candidate_groups:
                    adjustment += 24.0
                    item["match_reasons"].append("油库/加油站对象匹配")
                elif "pipeline" in candidate_groups:
                    adjustment -= 32.0
                    item["match_reasons"].append("对象降权：当前为油库/加油站，候选偏油管/管道迁改")

            if query_has_cnpc and re.search(r"中国石油|中石油|CNPC", candidate_text, flags=re.IGNORECASE):
                adjustment += 10.0
                item["match_reasons"].append("业主体系匹配：中国石油")

            result = str(item.get("result") or "")
            if "中标" in result and "未中" not in result:
                if common_groups:
                    adjustment += 6.0
                    item["match_reasons"].append("中标案例加权")
                else:
                    adjustment += 1.0

            item["score"] = float(item.get("score") or 0) + adjustment

    @staticmethod
    def _make_snippet(query: str, body: str, fallback: str = "") -> str:
        haystack = body or fallback
        if not haystack:
            return ""
        index = haystack.find(query)
        if index < 0:
            return haystack[:180]
        start = max(0, index - 70)
        end = min(len(haystack), index + len(query) + 110)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(haystack) else ""
        return f"{prefix}{haystack[start:index]}[{query}]{haystack[index + len(query):end]}{suffix}"
