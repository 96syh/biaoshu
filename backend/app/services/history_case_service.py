"""本地历史标书案例库检索服务。"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class HistoryCaseService:
    """Read-only access to the generated historical bid case library."""

    DB_PATH = Path(__file__).resolve().parents[2] / "data" / "history_cases.sqlite3"
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

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(str(cls.DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

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
                "markdown_path": row.get("markdown_path", ""),
                "pageindex_tree_path": row.get("pageindex_tree_path", ""),
                "snippet": row.get("snippet", ""),
                "score": 0.0,
                "match_reasons": [],
            })
            record["score"] = float(record["score"]) + score
            if reason not in record["match_reasons"]:
                record["match_reasons"].append(reason)
            if row.get("snippet") and len(str(row.get("snippet"))) > len(str(record.get("snippet") or "")):
                record["snippet"] = row.get("snippet")
                record["best_document_id"] = row.get("document_id", "")
                record["best_file_name"] = row.get("file_name", "")
                record["best_document_path"] = row.get("document_path", "")
                record["markdown_path"] = row.get("markdown_path", "")
                record["pageindex_tree_path"] = row.get("pageindex_tree_path", "")

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

        candidates = sorted(project_scores.values(), key=lambda item: (-float(item["score"]), item["year"], item["batch"]))[:limit]
        for index, item in enumerate(candidates, 1):
            item["rank"] = index
            item["score"] = round(float(item["score"]), 2)
        return candidates

    @classmethod
    def load_markdown(cls, markdown_path: str, max_chars: int = 60000) -> str:
        path = Path(markdown_path)
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
        return items[:80]

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
            parts.extend(str(project.get(key) or "") for key in ("name", "number", "owner", "location", "scope"))
        selected = analysis_report.get("selected_generation_target") if isinstance(analysis_report, dict) else None
        if isinstance(selected, dict):
            parts.extend(str(selected.get(key) or "") for key in ("target_title", "reason", "source"))
        for key in ("technical_score_items", "service_requirements", "scheme_or_technical_outline_requirements"):
            value = analysis_report.get(key) if isinstance(analysis_report, dict) else None
            if value:
                parts.append(json.dumps(value, ensure_ascii=False)[:4000])
        return "\n".join(part for part in parts if part)

    @classmethod
    def _extract_match_terms(cls, text: str) -> List[str]:
        terms: list[str] = []
        normalized = text or ""
        for hint in cls.MATCH_HINTS:
            if hint and hint in normalized and hint not in terms:
                terms.append(hint)
        title_candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9（）()、\-]{4,38}(?:项目|工程|服务|采购|设计|可研|初设|专篇|框架)", normalized)
        for term in title_candidates[:8]:
            cleaned = term.strip("：:，,。；; ")
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
        if not terms:
            compact = re.sub(r"\s+", "", normalized)
            if compact:
                terms.append(compact[:24])
        return terms[:14]

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
