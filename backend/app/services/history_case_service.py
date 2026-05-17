"""本地历史标书案例库检索服务。"""
from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import docx
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def heading_level(paragraph: docx.text.paragraph.Paragraph) -> int:
    style_name = (paragraph.style.name if paragraph.style else "") or ""
    match = re.search(r"heading\s*(\d+)|标题\s*(\d+)", style_name, re.IGNORECASE)
    if match:
        return max(1, min(6, int(match.group(1) or match.group(2))))

    text = paragraph.text.strip()
    if not text or len(text) > 80:
        return 0
    if re.match(r"^第[一二三四五六七八九十百\d]+[章节篇部分]", text):
        return 1
    if re.match(r"^[一二三四五六七八九十]+[、.．]", text):
        return 2
    if re.match(r"^（[一二三四五六七八九十]+）", text):
        return 3
    if re.match(r"^\d+(?:\.\d+)*[、.．]\s*", text):
        return min(4, text.count(".") + text.count("．") + 2)
    return 0


def iter_docx_blocks(document: DocxDocument):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def extract_docx_media_assets(path: Path, asset_dir: Path) -> list[dict]:
    document = docx.Document(str(path))
    assets: list[dict] = []
    asset_dir.mkdir(parents=True, exist_ok=True)
    for index, rel in enumerate(document.part.rels.values(), 1):
        if not str(rel.reltype).endswith("/image") or not hasattr(rel.target_part, "blob"):
            continue
        content_type = getattr(rel.target_part, "content_type", "") or ""
        ext = ".png"
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "gif" in content_type:
            ext = ".gif"
        elif "bmp" in content_type:
            ext = ".bmp"
        name = f"image-{index}{ext}"
        target = asset_dir / name
        target.write_bytes(rel.target_part.blob)
        assets.append({
            "id": f"img-{index}",
            "name": name,
            "path": str(target),
            "relative_path": name,
            "content_type": content_type,
        })
    return assets


def extract_docx_blocks(path: Path, asset_dir: Path) -> dict:
    document = docx.Document(str(path))
    assets = extract_docx_media_assets(path, asset_dir)
    blocks: list[dict] = []
    markdown_lines: list[str] = [f"# {path.stem}", ""]
    html_parts: list[str] = ['<div class="history-word-preview">']
    pending_image_index = 0
    heading_stack: list[dict] = []

    def next_image_html() -> str:
        nonlocal pending_image_index
        if pending_image_index >= len(assets):
            return ""
        asset = assets[pending_image_index]
        pending_image_index += 1
        src = f"assets/{html.escape(asset['name'])}"
        return f'<figure data-history-block-id="{asset["id"]}"><img src="{src}" alt="{html.escape(asset["name"])}" /></figure>'

    for index, block in enumerate(iter_docx_blocks(document), 1):
        block_id = f"b-{index}"
        if isinstance(block, Paragraph):
            text = block.text.strip()
            has_image = bool(block._element.xpath(".//a:blip"))
            if not text and not has_image:
                continue
            level = heading_level(block)
            block_type = "heading" if level else "paragraph"
            if level:
                heading_stack = [item for item in heading_stack if int(item.get("level") or 0) < level]
                heading_path = [*heading_stack, {"id": block_id, "level": level, "title": text}]
                heading_stack = heading_path
            else:
                heading_path = list(heading_stack)
            markdown_text = f"{'#' * level} {text}" if level and text else text
            image_html = next_image_html() if has_image else ""
            if markdown_text:
                markdown_lines.extend([markdown_text, ""])
            if has_image:
                image_ref = assets[pending_image_index - 1] if pending_image_index else None
                if image_ref:
                    markdown_lines.extend([f"![{image_ref['name']}](assets/{image_ref['name']})", ""])
            tag = f"h{min(level, 6)}" if level else "p"
            html_text = f"<{tag} data-history-block-id=\"{block_id}\">{html.escape(text)}</{tag}>" if text else ""
            html_parts.append(html_text + image_html)
            blocks.append({
                "id": block_id,
                "type": block_type,
                "level": level,
                "text": text,
                "markdown": markdown_text,
                "html": html_text + image_html,
                "docx_xml": block._element.xml,
                "heading_path": heading_path,
                "asset_ids": [assets[pending_image_index - 1]["id"]] if has_image and pending_image_index else [],
            })
        elif isinstance(block, Table):
            rows = [[cell.text.strip().replace("\n", " ") for cell in row.cells] for row in block.rows]
            rows = [row for row in rows if any(row)]
            if not rows:
                continue
            markdown_lines.append("| " + " | ".join(rows[0]) + " |")
            if len(rows) > 1:
                markdown_lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                for row in rows[1:]:
                    markdown_lines.append("| " + " | ".join(row) + " |")
            markdown_lines.append("")
            html_rows = []
            for row_index, row in enumerate(rows):
                tag = "th" if row_index == 0 else "td"
                cells = "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row)
                html_rows.append(f"<tr>{cells}</tr>")
            table_html = (
                f'<table data-history-block-id="{block_id}"><tbody>'
                f'{"".join(html_rows)}</tbody></table>'
            )
            html_parts.append(table_html)
            blocks.append({
                "id": block_id,
                "type": "table",
                "level": 0,
                "text": "\n".join(" | ".join(row) for row in rows),
                "markdown": "\n".join(markdown_lines[-len(rows) - 2:]).strip(),
                "html": table_html,
                "docx_xml": block._element.xml,
                "heading_path": list(heading_stack),
                "rows": rows,
                "asset_ids": [],
            })

    html_parts.append("</div>")
    return {
        "markdown": "\n".join(markdown_lines).strip() + "\n",
        "blocks": blocks,
        "html": "".join(html_parts),
        "assets": assets,
    }


class HistoryCaseService:
    """Read-only access to the PageIndex JSON historical bid case library."""

    REPO_ROOT = Path(__file__).resolve().parents[3]
    HISTORY_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "data" / "history_cases"
    LEGACY_HISTORY_ARTIFACT_ROOT = REPO_ROOT / "backend" / "data" / "history_cases"
    HISTORY_DB_PATH = REPO_ROOT / "artifacts" / "data" / "history_cases.sqlite3"
    PAGEINDEX_TREE_ROOT = HISTORY_ARTIFACT_ROOT / "pageindex_trees"
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
    def _pageindex_tree_files(cls) -> list[Path]:
        if not cls.PAGEINDEX_TREE_ROOT.exists():
            return []
        return sorted(cls.PAGEINDEX_TREE_ROOT.rglob("*.json"))

    @classmethod
    def _history_db_available(cls) -> bool:
        return cls.HISTORY_DB_PATH.exists() and cls.HISTORY_DB_PATH.is_file()

    @classmethod
    def _is_path_under_pageindex_root(cls, raw_path: Any) -> bool:
        path_text = str(raw_path or "").strip()
        if not path_text:
            return False
        resolved = cls._resolve_history_artifact_path(path_text)
        try:
            resolved.resolve().relative_to(cls.PAGEINDEX_TREE_ROOT.resolve())
            return True
        except (OSError, ValueError):
            return False

    @classmethod
    def _connect_history_db(cls) -> sqlite3.Connection:
        connection = sqlite3.connect(str(cls.HISTORY_DB_PATH))
        connection.row_factory = sqlite3.Row
        return connection

    @classmethod
    def _load_pageindex_tree(cls, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _tree_metadata(cls, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            parts = path.relative_to(cls.PAGEINDEX_TREE_ROOT).parts
        except ValueError:
            parts = path.parts
        year = parts[0] if len(parts) >= 1 else ""
        batch = parts[1] if len(parts) >= 2 else ""
        folder = parts[2] if len(parts) >= 3 else path.parent.name
        sequence = folder.split("-", 1)[0] if folder else ""
        doc_name = str(payload.get("doc_name") or path.stem)
        category = "技术标" if "技术" in batch or "技术" in doc_name else "商务标" if "商务" in batch or "商务" in doc_name else "未分类"
        return {
            "project_id": folder or path.stem,
            "document_id": path.stem,
            "year": year,
            "batch": batch,
            "sequence": sequence,
            "subject": doc_name,
            "result": "",
            "primary_domain": "",
            "primary_subdomain": "",
            "domain_confidence": 0,
            "domain_keywords": "[]",
            "project_title": doc_name,
            "project_path": str(path.parent),
            "file_name": f"{doc_name}.json",
            "document_category": category,
            "document_category_basis": "PageIndex JSON 路径推断",
            "document_path": str(path),
            "markdown_path": "",
            "block_json_path": "",
            "html_preview_path": "",
            "asset_dir": "",
            "pageindex_tree_path": str(path),
        }

    @classmethod
    def _flatten_pageindex_nodes(
        cls,
        nodes: list[Any],
        *,
        metadata: dict[str, Any],
        parent_id: str = "",
        parent_titles: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        parent_titles = parent_titles or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or f"node-{len(records) + 1}")
            title = str(node.get("title") or "").strip()
            text = str(node.get("text") or "").strip()
            level = max(1, min(6, len(re.match(r"^(#+)", text).group(1)) if re.match(r"^(#+)", text) else len(parent_titles) + 1))
            node_path = [*parent_titles, title] if title else list(parent_titles)
            record = {
                **metadata,
                "rank": 0.0,
                "pageindex_node_id": f"{metadata['document_id']}:{node_id}",
                "node_id": node_id,
                "parent_node_id": parent_id,
                "node_title": title,
                "node_level": level,
                "node_line_num": int(node.get("line_num") or 0),
                "node_text": text,
                "node_path": node_path,
                "node_path_text": " > ".join(node_path),
            }
            records.append(record)
            children = node.get("nodes")
            if isinstance(children, list):
                records.extend(
                    cls._flatten_pageindex_nodes(
                        children,
                        metadata=metadata,
                        parent_id=node_id,
                        parent_titles=node_path,
                    )
                )
        return records

    @classmethod
    def _sqlite_document_category(cls, row: Dict[str, Any]) -> str:
        batch = str(row.get("batch") or "")
        file_name = str(row.get("file_name") or "")
        project_title = str(row.get("project_title") or row.get("subject") or "")
        haystack = f"{batch} {file_name} {project_title}"
        if "技术" in haystack:
            return "技术标"
        if "商务" in haystack or "非技术" in haystack:
            return "商务标"
        return "未分类"

    @classmethod
    def _metadata_from_sqlite_row(cls, row: Dict[str, Any]) -> dict[str, Any]:
        category = cls._sqlite_document_category(row)
        return {
            "project_id": str(row.get("project_id") or ""),
            "document_id": str(row.get("document_id") or ""),
            "year": str(row.get("year") or ""),
            "batch": str(row.get("batch") or ""),
            "sequence": str(row.get("sequence") or ""),
            "subject": str(row.get("subject") or ""),
            "result": str(row.get("result") or ""),
            "primary_domain": str(row.get("primary_domain") or ""),
            "primary_subdomain": str(row.get("primary_subdomain") or ""),
            "domain_confidence": row.get("domain_confidence") or 0,
            "domain_keywords": str(row.get("domain_keywords") or "[]"),
            "project_title": str(row.get("project_title") or row.get("subject") or ""),
            "project_path": str(row.get("project_path") or ""),
            "file_name": str(row.get("file_name") or ""),
            "document_category": category,
            "document_category_basis": "SQLite 元数据推断",
            "document_path": str(row.get("document_path") or ""),
            "markdown_path": str(row.get("markdown_path") or ""),
            "block_json_path": str(row.get("block_json_path") or ""),
            "html_preview_path": str(row.get("html_preview_path") or ""),
            "asset_dir": str(row.get("asset_dir") or ""),
            "pageindex_tree_path": str(row.get("pageindex_tree_path") or ""),
        }

    @classmethod
    def _pageindex_record_from_sqlite_row(cls, row: Dict[str, Any]) -> dict[str, Any]:
        """Use SQLite for recall, then load the matching PageIndex node as source of truth."""
        metadata = cls._metadata_from_sqlite_row(row)
        fallback = {
            **metadata,
            "rank": 0.0,
            "pageindex_node_id": str(row.get("pageindex_node_id") or ""),
            "node_id": str(row.get("node_id") or ""),
            "parent_node_id": str(row.get("parent_node_id") or ""),
            "node_title": str(row.get("node_title") or ""),
            "node_level": int(row.get("node_level") or 1),
            "node_line_num": int(row.get("node_line_num") or 0),
            "node_text": str(row.get("node_text") or ""),
            "node_path": [str(row.get("node_title") or "")] if row.get("node_title") else [],
            "node_path_text": str(row.get("node_title") or ""),
        }

        tree_path = cls._resolve_history_artifact_path(str(row.get("pageindex_tree_path") or ""))
        payload = cls._load_pageindex_tree(tree_path) if tree_path else {}
        structure = payload.get("structure")
        if not isinstance(structure, list):
            return fallback

        target_node_id = str(row.get("node_id") or "")
        for record in cls._flatten_pageindex_nodes(structure, metadata=metadata):
            if str(record.get("node_id") or "") == target_node_id:
                record["pageindex_node_id"] = str(row.get("pageindex_node_id") or record.get("pageindex_node_id") or "")
                return record
        return fallback

    @classmethod
    def _search_sqlite_pageindex_nodes(
        cls,
        query: str,
        limit: int,
        *,
        document_category: str = "",
    ) -> list[dict[str, Any]]:
        if not cls._history_db_available():
            return []

        terms = cls._pageindex_search_terms(query)
        if not terms:
            return []

        searchable_terms = terms[:10]
        like_parts: list[str] = []
        params: list[Any] = []
        for term in searchable_terms:
            pattern = f"%{term}%"
            like_parts.append(
                "(n.title LIKE ? OR n.text LIKE ? OR p.title LIKE ? OR p.subject LIKE ? "
                "OR p.primary_domain LIKE ? OR p.primary_subdomain LIKE ? OR d.file_name LIKE ?)"
            )
            params.extend([pattern, pattern, pattern, pattern, pattern, pattern, pattern])

        category_clause = ""
        if document_category == "技术标":
            category_clause = "AND (p.batch LIKE '%技术%' OR d.file_name LIKE '%技术%' OR p.title LIKE '%技术%')"
        elif document_category in {"商务标", "非技术标"}:
            category_clause = "AND (p.batch LIKE '%商务%' OR d.file_name LIKE '%商务%' OR p.title LIKE '%商务%' OR p.batch LIKE '%非技术%')"

        sql = f"""
            SELECT
                n.id AS pageindex_node_id,
                n.document_id AS document_id,
                n.node_id AS node_id,
                n.parent_node_id AS parent_node_id,
                n.title AS node_title,
                n.line_num AS node_line_num,
                n.level AS node_level,
                n.text AS node_text,
                d.project_id AS project_id,
                d.file_name AS file_name,
                d.source_path AS document_path,
                d.markdown_path AS markdown_path,
                d.block_json_path AS block_json_path,
                d.html_preview_path AS html_preview_path,
                d.asset_dir AS asset_dir,
                d.pageindex_tree_path AS pageindex_tree_path,
                p.year AS year,
                p.batch AS batch,
                p.sequence AS sequence,
                p.result AS result,
                p.subject AS subject,
                p.primary_domain AS primary_domain,
                p.primary_subdomain AS primary_subdomain,
                p.domain_confidence AS domain_confidence,
                p.domain_keywords AS domain_keywords,
                p.title AS project_title,
                p.source_path AS project_path
            FROM pageindex_nodes n
            JOIN case_documents d ON d.id = n.document_id
            JOIN case_projects p ON p.id = d.project_id
            WHERE d.status = 'indexed'
              AND ({' OR '.join(like_parts)})
              {category_clause}
            LIMIT ?
        """
        params.append(max(limit * 24, 120))

        try:
            with cls._connect_history_db() as connection:
                raw_rows = [dict(row) for row in connection.execute(sql, params)]
        except sqlite3.Error:
            return []

        scored: list[dict[str, Any]] = []
        for raw in raw_rows:
            if not cls._is_path_under_pageindex_root(raw.get("pageindex_tree_path")):
                continue
            record = cls._pageindex_record_from_sqlite_row(raw)
            score = cls._pageindex_node_score(record, query, terms)
            if score <= 0:
                continue
            record["snippet"] = cls._make_pageindex_snippet(
                query,
                node_title=str(record.get("node_title") or ""),
                node_text=str(record.get("node_text") or ""),
                terms=terms,
            )
            record["rank"] = round(score, 4)
            scored.append(record)

        scored.sort(
            key=lambda item: (
                -float(item.get("rank") or 0),
                int(item.get("node_level") or 99),
                str(item.get("project_title") or ""),
            )
        )
        return scored[:limit]

    @classmethod
    def _iter_pageindex_records(cls) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in cls._pageindex_tree_files():
            payload = cls._load_pageindex_tree(path)
            structure = payload.get("structure")
            if not isinstance(structure, list):
                continue
            records.extend(
                cls._flatten_pageindex_nodes(
                    structure,
                    metadata=cls._tree_metadata(path, payload),
                )
            )
        return records

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        if cls._history_db_available():
            try:
                with cls._connect_history_db() as connection:
                    document_rows = [
                        dict(row)
                        for row in connection.execute(
                            """
                            SELECT
                                p.id AS project_id,
                                p.year AS year,
                                p.result AS result,
                                p.primary_domain AS primary_domain,
                                p.primary_subdomain AS primary_subdomain,
                                p.batch AS batch,
                                p.title AS project_title,
                                d.file_name AS file_name,
                                d.pageindex_tree_path AS pageindex_tree_path,
                                d.extension AS extension,
                                d.status AS status
                            FROM case_documents d
                            JOIN case_projects p ON p.id = d.project_id
                            """
                        )
                    ]
                aligned_rows = [
                    row for row in document_rows if cls._is_path_under_pageindex_root(row.get("pageindex_tree_path"))
                ]
                if aligned_rows:
                    by_year_map: dict[str, int] = {}
                    by_result_map: dict[str, int] = {}
                    by_extension_map: dict[str, int] = {}
                    by_category_map: dict[str, int] = {}
                    by_domain_map: dict[tuple[str, str], int] = {}
                    project_ids: set[str] = set()
                    indexed_count = 0
                    failed_count = 0
                    for row in aligned_rows:
                        project_ids.add(str(row.get("project_id") or ""))
                        by_year_map[str(row.get("year") or "")] = by_year_map.get(str(row.get("year") or ""), 0) + 1
                        result = str(row.get("result") or "未标注")
                        by_result_map[result] = by_result_map.get(result, 0) + 1
                        extension = str(row.get("extension") or Path(str(row.get("file_name") or "")).suffix or "unknown")
                        by_extension_map[extension] = by_extension_map.get(extension, 0) + 1
                        category = cls._sqlite_document_category(row)
                        by_category_map[category] = by_category_map.get(category, 0) + 1
                        domain_key = (
                            str(row.get("primary_domain") or "其他"),
                            str(row.get("primary_subdomain") or "未分类"),
                        )
                        by_domain_map[domain_key] = by_domain_map.get(domain_key, 0) + 1
                        if str(row.get("status") or "") == "indexed":
                            indexed_count += 1
                        else:
                            failed_count += 1
                    return {
                        "ready": True,
                        "project_count": len(project_ids),
                        "document_count": len(aligned_rows),
                        "indexed_document_count": indexed_count,
                        "failed_document_count": failed_count,
                        "by_year": [{"year": key, "count": value} for key, value in sorted(by_year_map.items())],
                        "by_result": [
                            {"result": key, "count": value}
                            for key, value in sorted(by_result_map.items(), key=lambda item: (-item[1], item[0]))
                        ],
                        "by_extension": [
                            {"extension": key, "count": value}
                            for key, value in sorted(by_extension_map.items(), key=lambda item: (-item[1], item[0]))
                        ],
                        "by_document_category": [
                            {"category": key, "count": value}
                            for key, value in sorted(by_category_map.items(), key=lambda item: (-item[1], item[0]))
                        ],
                        "by_domain": [
                            {"domain": key[0], "subdomain": key[1], "count": value}
                            for key, value in sorted(by_domain_map.items(), key=lambda item: (-item[1], item[0]))
                        ],
                        "history_db_path": str(cls.HISTORY_DB_PATH),
                        "pageindex_tree_root": str(cls.PAGEINDEX_TREE_ROOT),
                        "index_mode": "sqlite_recall_pageindex_context",
                    }
            except sqlite3.Error:
                pass

        files = cls._pageindex_tree_files()
        by_year_map: dict[str, int] = {}
        by_category_map: dict[str, int] = {}
        project_ids: set[str] = set()
        for path in files:
            payload = cls._load_pageindex_tree(path)
            metadata = cls._tree_metadata(path, payload)
            project_ids.add(str(metadata["project_id"]))
            by_year_map[str(metadata["year"])] = by_year_map.get(str(metadata["year"]), 0) + 1
            category = str(metadata["document_category"])
            by_category_map[category] = by_category_map.get(category, 0) + 1
        return {
            "ready": bool(files),
            "project_count": len(project_ids),
            "document_count": len(files),
            "indexed_document_count": len(files),
            "failed_document_count": 0,
            "by_year": [{"year": key, "count": value} for key, value in sorted(by_year_map.items())],
            "by_result": [],
            "by_extension": [{"extension": ".json", "count": len(files)}] if files else [],
            "by_document_category": [
                {"category": key, "count": value}
                for key, value in sorted(by_category_map.items(), key=lambda item: (-item[1], item[0]))
            ],
            "by_domain": [],
            "pageindex_tree_root": str(cls.PAGEINDEX_TREE_ROOT),
            "index_mode": "pageindex_json_fallback",
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
        if cls._history_db_available():
            try:
                with cls._connect_history_db() as connection:
                    rows = [
                        dict(row)
                        for row in connection.execute(
                            """
                            SELECT
                                p.id AS id,
                                p.year AS year,
                                p.batch AS batch,
                                p.sequence AS sequence,
                                p.subject AS subject,
                                p.result AS result,
                                p.primary_domain AS primary_domain,
                                p.primary_subdomain AS primary_subdomain,
                                p.domain_confidence AS domain_confidence,
                                p.domain_keywords AS domain_keywords,
                                p.title AS title,
                                p.source_path AS source_path,
                                SUM(CASE WHEN d.status = 'indexed' THEN 1 ELSE 0 END) AS indexed_document_count,
                                COUNT(d.id) AS document_count,
                                MAX(d.pageindex_tree_path) AS pageindex_tree_path
                            FROM case_projects p
                            JOIN case_documents d ON d.project_id = p.id
                            GROUP BY p.id
                            ORDER BY p.year, p.batch, p.sequence
                            """
                        )
                    ]
                records = []
                for row in rows:
                    if not cls._is_path_under_pageindex_root(row.get("pageindex_tree_path")):
                        continue
                    haystack = " ".join(str(row.get(key) or "") for key in ("subject", "title", "batch", "primary_domain", "primary_subdomain"))
                    if year and row.get("year") != year:
                        continue
                    if subject and subject not in haystack:
                        continue
                    if result and result not in str(row.get("result") or ""):
                        continue
                    if domain and domain not in haystack:
                        continue
                    records.append({key: value for key, value in row.items() if key != "pageindex_tree_path"})
                    if len(records) >= limit:
                        break
                if records:
                    return records
            except sqlite3.Error:
                pass

        projects: dict[str, dict[str, Any]] = {}
        for path in cls._pageindex_tree_files():
            payload = cls._load_pageindex_tree(path)
            metadata = cls._tree_metadata(path, payload)
            haystack = " ".join(str(metadata.get(key) or "") for key in ("subject", "project_title", "batch"))
            if year and metadata["year"] != year:
                continue
            if subject and subject not in haystack:
                continue
            if result and result not in str(metadata.get("result") or ""):
                continue
            if domain and domain not in haystack:
                continue
            record = projects.setdefault(str(metadata["project_id"]), {
                "id": metadata["project_id"],
                "year": metadata["year"],
                "batch": metadata["batch"],
                "sequence": metadata["sequence"],
                "subject": metadata["subject"],
                "result": metadata["result"],
                "primary_domain": metadata["primary_domain"],
                "primary_subdomain": metadata["primary_subdomain"],
                "domain_confidence": metadata["domain_confidence"],
                "domain_keywords": metadata["domain_keywords"],
                "title": metadata["project_title"],
                "source_path": metadata["project_path"],
                "document_count": 0,
                "indexed_document_count": 0,
            })
            record["document_count"] += 1
            record["indexed_document_count"] += 1
        records = list(projects.values())
        records.sort(key=lambda item: (item.get("year") or "", item.get("batch") or "", item.get("sequence") or ""))
        return records[:limit]

    @classmethod
    def list_domains(cls) -> List[Dict[str, Any]]:
        if cls._history_db_available():
            try:
                with cls._connect_history_db() as connection:
                    rows = [
                        dict(row)
                        for row in connection.execute(
                            """
                            SELECT
                                p.primary_domain AS domain,
                                p.primary_subdomain AS subdomain,
                                COUNT(DISTINCT p.id) AS project_count
                            FROM case_projects p
                            JOIN case_documents d ON d.project_id = p.id
                            WHERE d.status = 'indexed'
                            GROUP BY p.primary_domain, p.primary_subdomain
                            ORDER BY project_count DESC, domain, subdomain
                            """
                        )
                    ]
                return [
                    {
                        "domain": str(row.get("domain") or "其他"),
                        "subdomain": str(row.get("subdomain") or "未分类"),
                        "project_count": int(row.get("project_count") or 0),
                    }
                    for row in rows
                ]
            except sqlite3.Error:
                pass
        return []

    @classmethod
    def search_pageindex_nodes(
        cls,
        query: str,
        limit: int = 10,
        *,
        document_category: str = "",
    ) -> List[Dict[str, Any]]:
        """Search historical PageIndex JSON nodes and return node-level evidence."""
        if not query.strip() or limit <= 0:
            return []

        normalized_query = query.strip()
        sqlite_rows = cls._search_sqlite_pageindex_nodes(
            normalized_query,
            limit=limit,
            document_category=document_category,
        )
        if sqlite_rows:
            return sqlite_rows

        terms = cls._pageindex_search_terms(normalized_query)
        scored: list[dict[str, Any]] = []
        for record in cls._iter_pageindex_records():
            if document_category and record.get("document_category") != document_category:
                continue
            score = cls._pageindex_node_score(record, normalized_query, terms)
            if score <= 0:
                continue
            record = dict(record)
            record["snippet"] = cls._make_pageindex_snippet(
                normalized_query,
                node_title=str(record.get("node_title") or ""),
                node_text=str(record.get("node_text") or ""),
                terms=terms,
            )
            record["rank"] = round(score, 4)
            scored.append(record)

        scored.sort(
            key=lambda item: (
                -float(item.get("rank") or 0),
                int(item.get("node_level") or 99),
                str(item.get("project_title") or ""),
            )
        )
        return scored[:limit]

    @classmethod
    def _pageindex_search_terms(cls, query: str) -> List[str]:
        terms: list[str] = []

        def add(term: str) -> None:
            cleaned = re.sub(r"\s+", " ", str(term or "")).strip("：:，,。；; ")
            if 2 <= len(cleaned) <= 48 and cleaned not in terms:
                terms.append(cleaned)

        normalized = str(query or "").strip()
        compact = re.sub(r"\s+", "", normalized)
        add(normalized)
        add(compact)
        for term in cls._extract_match_terms(normalized):
            add(term)
        for term in cls._requirement_search_terms(normalized):
            add(term)
        for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9（）()]{2,24}", normalized):
            add(token)
        for keyword in (*cls.MATCH_HINTS, *cls.REQUIREMENT_KEYWORDS):
            if keyword in normalized or keyword in compact:
                add(keyword)
        return terms[:16]

    @classmethod
    def _pageindex_node_score(cls, row: Dict[str, Any], query: str, terms: list[str]) -> float:
        title = str(row.get("node_title") or "")
        text = str(row.get("node_text") or "")
        metadata = " ".join(
            str(row.get(key) or "")
            for key in (
                "project_title",
                "subject",
                "result",
                "primary_domain",
                "primary_subdomain",
                "domain_keywords",
                "file_name",
                "document_category",
            )
        )
        compact_title = re.sub(r"\s+", "", title)
        compact_text = re.sub(r"\s+", "", text)
        compact_metadata = re.sub(r"\s+", "", metadata)
        compact_query = re.sub(r"\s+", "", str(query or ""))
        score = 0.0

        if compact_query:
            if compact_query in compact_title:
                score += 18.0
            if compact_query in compact_text:
                score += 12.0
            if compact_query in compact_metadata:
                score += 5.0

        seen_terms: set[str] = set()
        for index, term in enumerate(terms):
            compact_term = re.sub(r"\s+", "", term)
            if not compact_term or compact_term in seen_terms:
                continue
            seen_terms.add(compact_term)
            weight = max(1.0, 6.0 - index * 0.22)
            if compact_term in compact_title:
                score += weight * 2.2
            if compact_term in compact_text:
                score += weight
            if compact_term in compact_metadata:
                score += weight * 0.55

        result = str(row.get("result") or "")
        if "中标" in result and "未中" not in result:
            score += 2.0
        if str(row.get("document_category") or "") == "技术标":
            score += 1.4
        node_level = int(row.get("node_level") or 0)
        if 1 <= node_level <= 2:
            score += 0.8
        return score

    @classmethod
    def _make_pageindex_snippet(cls, query: str, node_title: str, node_text: str, terms: list[str]) -> str:
        body = re.sub(r"\n{3,}", "\n\n", str(node_text or "")).strip()
        for term in [query, *terms]:
            cleaned = str(term or "").strip()
            if cleaned and cleaned in body:
                return cls._make_snippet(query=cleaned, body=body, fallback=node_title)
        fallback = "\n".join(part for part in [node_title, body] if part)
        return cls._make_snippet(query=query, body=fallback, fallback=node_title)

    @classmethod
    def search(cls, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        return cls.search_pageindex_nodes(query.strip(), limit=limit)

    @classmethod
    def match_candidates(
        cls,
        tender_text: str,
        analysis_report: Dict[str, Any] | None = None,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """召回并按规则分数聚合历史案例候选。"""
        if not cls._pageindex_tree_files():
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
                "best_document_category": row.get("document_category", ""),
                "best_document_category_basis": row.get("document_category_basis", ""),
                "best_document_path": row.get("document_path", ""),
                "markdown_path": cls._normalize_artifact_path_for_response(row.get("markdown_path", "")),
                "block_json_path": cls._normalize_artifact_path_for_response(row.get("block_json_path", "")),
                "html_preview_path": cls._normalize_artifact_path_for_response(row.get("html_preview_path", "")),
                "asset_dir": cls._normalize_artifact_path_for_response(row.get("asset_dir", "")),
                "pageindex_tree_path": cls._normalize_artifact_path_for_response(row.get("pageindex_tree_path", "")),
                "best_pageindex_node_id": row.get("pageindex_node_id", ""),
                "best_node_id": row.get("node_id", ""),
                "best_node_title": row.get("node_title", ""),
                "best_node_path": row.get("node_path", []),
                "best_node_path_text": row.get("node_path_text", ""),
                "best_node_level": row.get("node_level", 0),
                "best_node_line_num": row.get("node_line_num", 0),
                "best_node_text": cls._trim_reference_text(str(row.get("node_text") or ""), max_chars=1200),
                "pageindex_snippets": [],
                "snippet": row.get("snippet", ""),
                "score": 0.0,
                "match_reasons": [],
                "_scored_hit_keys": set(),
            })
            if row.get("pageindex_node_id") and not any(
                item.get("pageindex_node_id") == row.get("pageindex_node_id")
                for item in record.get("pageindex_snippets", [])
            ):
                record["pageindex_snippets"].append({
                    "pageindex_node_id": row.get("pageindex_node_id", ""),
                    "node_id": row.get("node_id", ""),
                    "node_title": row.get("node_title", ""),
                    "node_path": row.get("node_path", []),
                    "node_path_text": row.get("node_path_text", ""),
                    "node_level": row.get("node_level", 0),
                    "node_line_num": row.get("node_line_num", 0),
                    "snippet": row.get("snippet", ""),
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
                record["best_document_category"] = row.get("document_category", "")
                record["best_document_category_basis"] = row.get("document_category_basis", "")
                record["best_document_path"] = row.get("document_path", "")
                record["markdown_path"] = cls._normalize_artifact_path_for_response(row.get("markdown_path", ""))
                record["block_json_path"] = cls._normalize_artifact_path_for_response(row.get("block_json_path", ""))
                record["html_preview_path"] = cls._normalize_artifact_path_for_response(row.get("html_preview_path", ""))
                record["asset_dir"] = cls._normalize_artifact_path_for_response(row.get("asset_dir", ""))
                record["pageindex_tree_path"] = cls._normalize_artifact_path_for_response(row.get("pageindex_tree_path", ""))
                record["best_pageindex_node_id"] = row.get("pageindex_node_id", "")
                record["best_node_id"] = row.get("node_id", "")
                record["best_node_title"] = row.get("node_title", "")
                record["best_node_path"] = row.get("node_path", [])
                record["best_node_path_text"] = row.get("node_path_text", "")
                record["best_node_level"] = row.get("node_level", 0)
                record["best_node_line_num"] = row.get("node_line_num", 0)
                record["best_node_text"] = cls._trim_reference_text(str(row.get("node_text") or ""), max_chars=1200)

        for index, term in enumerate(query_terms[:10]):
            for row in cls.search(term, limit=12):
                add_result(row, max(1.0, 10.0 - index), f"关键词命中：{term}")

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
    def load_pageindex_context_for_candidate(cls, candidate: Dict[str, Any], max_chars: int = 60000) -> str:
        """Load compact PageIndex context for a matched historical candidate."""
        if not candidate:
            return ""
        parts: list[str] = []
        best_text = cls._trim_reference_text(str(candidate.get("best_node_text") or ""), max_chars=12000)
        if best_text:
            parts.append(
                "【最相关 PageIndex 节点】\n"
                f"项目：{candidate.get('project_title') or candidate.get('subject') or ''}\n"
                f"文档：{candidate.get('best_file_name') or candidate.get('file_name') or ''}\n"
                f"标题：{candidate.get('best_node_title') or candidate.get('node_title') or ''}\n"
                f"{best_text}"
            )

        tree_path = cls._first_text(
            candidate.get("pageindex_tree_path"),
            (candidate.get("source_paths") or {}).get("pageindex_tree_path") if isinstance(candidate.get("source_paths"), dict) else "",
        )
        tree = cls._load_pageindex_tree(Path(tree_path)) if tree_path else {}
        structure = tree.get("structure")
        if isinstance(structure, list):
            metadata = cls._tree_metadata(Path(tree_path), tree)
            rows = [
                row
                for row in cls._flatten_pageindex_nodes(structure, metadata=metadata)
                if int(row.get("node_level") or 1) <= 2
            ][:80]
            if rows:
                parts.append(f"【PageIndex 文档结构：{tree.get('doc_name') or metadata['project_title']}】")
            for row in rows:
                if sum(len(part) for part in parts) >= max_chars:
                    break
                level = max(1, min(6, int(row.get("node_level") or 1)))
                heading = f"{'#' * level} {row.get('node_title') or ''}".strip()
                text = str(row.get("node_text") or "").strip()
                payload = cls._trim_reference_text(text if text.startswith("#") else f"{heading}\n{text}", max_chars=2400)
                if payload:
                    parts.append(payload)
        context = "\n\n".join(part for part in parts if str(part or "").strip())
        return context[:max_chars]

    @classmethod
    def load_block_json(cls, block_json_path: str) -> Dict[str, Any]:
        path = cls._resolve_history_artifact_path(block_json_path)
        if not path.exists() or not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return {}

    @classmethod
    def load_html_preview(cls, html_preview_path: str, max_chars: int = 120000) -> str:
        path = cls._resolve_history_artifact_path(html_preview_path)
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]

    @classmethod
    def find_chapter_reference_drafts(
        cls,
        chapter: Dict[str, Any],
        parent_chapters: List[Dict[str, Any]] | None = None,
        sibling_chapters: List[Dict[str, Any]] | None = None,
        analysis_report: Dict[str, Any] | None = None,
        response_matrix: Dict[str, Any] | None = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find reusable historical chapter drafts for the current outline node.

        This is intentionally rule-based and read-only: it provides candidate text
        for the model to rewrite, while the current tender analysis remains the
        source of truth.
        """
        if limit <= 0:
            return []
        query_text = cls._chapter_reference_query_text(
            chapter,
            parent_chapters=parent_chapters,
            analysis_report=analysis_report,
            response_matrix=response_matrix,
        )
        title = cls._text((chapter or {}).get("title"))
        terms = cls._chapter_reference_terms(title, query_text)
        if not terms:
            return []

        candidates: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        for term in terms:
            rows = cls.search_pageindex_nodes(term, limit=max(limit * 6, 12), document_category="技术标")
            if not rows:
                rows = cls.search(term, limit=max(limit * 3, 6))
            for row in rows:
                node_key = cls._first_text(
                    row.get("pageindex_node_id"),
                    row.get("node_id"),
                    row.get("markdown_path"),
                    row.get("document_path"),
                    fallback=str(len(seen_nodes)),
                )
                if node_key in seen_nodes:
                    continue
                seen_nodes.add(node_key)

                markdown = cls.load_markdown(str(row.get("markdown_path") or ""), max_chars=90000)
                block_payload = cls.load_block_json(str(row.get("block_json_path") or ""))
                all_blocks = block_payload.get("blocks") if isinstance(block_payload, dict) else []
                matched_blocks = cls._extract_pageindex_matched_blocks(
                    all_blocks if isinstance(all_blocks, list) else [],
                    title=title,
                    row=row,
                )
                has_word_heading_match = bool(matched_blocks)
                reference_text = cls._blocks_to_markdown(matched_blocks) if matched_blocks else ""
                if not reference_text:
                    node_text = cls._trim_reference_text(str(row.get("node_text") or ""), max_chars=4200)
                    reference_text = node_text or cls._extract_markdown_section(
                        markdown,
                        title,
                        fallback_snippet=str(row.get("snippet") or ""),
                        search_term=term,
                        max_chars=3600,
                    )
                if (
                    not has_word_heading_match
                    and cls._is_service_scope_title(title)
                    and cls._has_excluded_history_topic(reference_text)
                ):
                    continue
                if not has_word_heading_match:
                    reference_text = cls._strip_non_text_markdown_from_reference(reference_text)
                if not reference_text.strip():
                    reference_text = cls._blocks_to_markdown(matched_blocks)
                if not reference_text.strip():
                    continue
                html_fragment = cls._blocks_to_html(matched_blocks) or cls._extract_html_fragment(
                    cls.load_html_preview(str(row.get("html_preview_path") or "")),
                    matched_blocks,
                )
                html_fragment = cls._inline_history_html_assets(html_fragment, str(row.get("asset_dir") or ""))

                score, reasons = cls._chapter_reference_score(
                    row,
                    query_text=query_text,
                    title=title,
                    matched_term=term,
                    reference_text=reference_text,
                )
                if not has_word_heading_match:
                    score = min(score - 0.22, 0.36)
                    reasons.append("未命中历史 Word 标题块，仅作语义参考")
                if score < 0.18:
                    continue

                match_level = "high" if score >= 0.62 else "medium" if score >= 0.38 else "low"
                block_inventory = cls._reference_block_inventory(reference_text)
                candidates.append(
                    {
                        "match_level": match_level,
                        "score": round(score, 3),
                        "reuse_rule": "primary_draft" if match_level == "high" else "minimal_revision",
                        "project_title": row.get("project_title") or row.get("subject") or "",
                        "result": row.get("result") or "",
                        "file_name": row.get("file_name") or "",
                        "document_id": row.get("document_id") or "",
                        "matched_term": term,
                        "match_reasons": reasons,
                        "snippet": row.get("snippet") or "",
                        "reference_text": reference_text,
                        "markdown_text": reference_text,
                        "html_fragment": html_fragment,
                        "matched_blocks": matched_blocks,
                        "has_word_heading_match": has_word_heading_match,
                        "reference_source": "pageindex_word_blocks" if has_word_heading_match else "pageindex_node",
                        "pageindex_node": {
                            "pageindex_node_id": row.get("pageindex_node_id") or "",
                            "node_id": row.get("node_id") or "",
                            "node_title": row.get("node_title") or "",
                            "node_path": row.get("node_path") or [],
                            "node_path_text": row.get("node_path_text") or "",
                            "node_level": row.get("node_level") or 0,
                            "node_line_num": row.get("node_line_num") or 0,
                        },
                        "source_paths": {
                            "markdown_path": cls._normalize_artifact_path_for_response(row.get("markdown_path", "")),
                            "block_json_path": cls._normalize_artifact_path_for_response(row.get("block_json_path", "")),
                            "html_preview_path": cls._normalize_artifact_path_for_response(row.get("html_preview_path", "")),
                            "asset_dir": cls._normalize_artifact_path_for_response(row.get("asset_dir", "")),
                            "source_docx_path": cls._normalize_artifact_path_for_response(row.get("document_path", "")),
                            "pageindex_tree_path": cls._normalize_artifact_path_for_response(row.get("pageindex_tree_path", "")),
                        },
                        "reference_char_count": len(reference_text),
                        "block_inventory": block_inventory,
                    }
                )
                if len(candidates) >= limit * 4:
                    break
            if len(candidates) >= limit * 4:
                break

        candidates.sort(
            key=lambda item: (
                1 if item.get("has_word_heading_match") else 0,
                item.get("score") or 0,
            ),
            reverse=True,
        )
        return candidates[:limit]

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
        seen_sources: set[str] = set()
        matched_terms: set[str] = set()

        for term in terms:
            rows = cls.search_pageindex_nodes(term, limit=max(6, limit_per_item * 3))
            if not rows:
                rows = cls.search(term, limit=max(4, limit_per_item * 2))
            for row in rows:
                source_id = cls._first_text(row.get("pageindex_node_id"), row.get("document_id"), fallback=str(len(seen_sources)))
                if source_id in seen_sources:
                    continue
                seen_sources.add(source_id)
                haystack = " ".join(
                    str(row.get(key) or "")
                    for key in (
                        "project_title",
                        "subject",
                        "result",
                        "primary_domain",
                        "file_name",
                        "node_title",
                        "node_path_text",
                        "node_text",
                        "snippet",
                    )
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
                    "document_category": row.get("document_category"),
                    "document_category_basis": row.get("document_category_basis"),
                    "document_path": row.get("document_path"),
                    "pageindex_tree_path": row.get("pageindex_tree_path"),
                    "pageindex_node_id": row.get("pageindex_node_id"),
                    "node_id": row.get("node_id"),
                    "node_title": row.get("node_title"),
                    "node_path": row.get("node_path"),
                    "node_path_text": row.get("node_path_text"),
                    "node_level": row.get("node_level"),
                    "node_line_num": row.get("node_line_num"),
                    "snippet": row.get("snippet"),
                    "matched_term": term,
                    "is_winning_case": "中标" in str(row.get("result") or "") and "未中" not in str(row.get("result") or ""),
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

    @classmethod
    def _chapter_reference_query_text(
        cls,
        chapter: Dict[str, Any],
        parent_chapters: List[Dict[str, Any]] | None = None,
        analysis_report: Dict[str, Any] | None = None,
        response_matrix: Dict[str, Any] | None = None,
    ) -> str:
        report = analysis_report or {}
        parts: list[str] = []
        for item in [*(parent_chapters or []), chapter or {}]:
            parts.extend(
                cls._text(item.get(key))
                for key in ("title", "description", "requirement", "response_suggestion", "source_ref")
                if isinstance(item, dict)
            )
        project = report.get("project") if isinstance(report, dict) else None
        if isinstance(project, dict):
            parts.extend(
                cls._text(project.get(key))
                for key in (
                    "name",
                    "service_scope",
                    "project_type",
                    "service_location",
                    "quality_requirements",
                )
            )

        response_ids = set()
        for key in ("response_matrix_ids", "mapped_response_ids", "scoring_item_ids", "requirement_ids"):
            value = (chapter or {}).get(key)
            if isinstance(value, list):
                response_ids.update(cls._text(item) for item in value if cls._text(item))

        matrix = response_matrix or report.get("response_matrix") or {}
        matrix_items = matrix.get("items") if isinstance(matrix, dict) else None
        if response_ids and isinstance(matrix_items, list):
            for item in matrix_items:
                if not isinstance(item, dict):
                    continue
                item_id = cls._first_text(item.get("id"), item.get("item_id"), item.get("requirement_id"))
                if item_id in response_ids:
                    parts.append(json.dumps(item, ensure_ascii=False)[:1200])

        for key in ("technical_scoring_items", "business_scoring_items", "qualification_review_items"):
            value = report.get(key) if isinstance(report, dict) else None
            if isinstance(value, list):
                for item in value[:40]:
                    if isinstance(item, dict):
                        item_text = json.dumps(item, ensure_ascii=False)
                        if cls._text((chapter or {}).get("title")) and cls._text((chapter or {}).get("title")) in item_text:
                            parts.append(item_text[:1000])

        return "\n".join(part for part in parts if part)

    @classmethod
    def _chapter_reference_terms(cls, title: str, query_text: str) -> List[str]:
        terms: list[str] = []

        def add(term: str) -> None:
            cleaned = re.sub(r"\s+", " ", str(term or "")).strip("：:，,。；; ")
            if 2 <= len(cleaned) <= 48 and cleaned not in terms:
                terms.append(cleaned)

        add(title)
        compact_title = re.sub(r"[\s　]+", "", title)
        if compact_title != title:
            add(compact_title)
        combined = f"{title}\n{query_text}"
        if cls._is_personnel_reference_title(combined):
            for term in (
                "拟投入人员",
                "拟委任的主要人员",
                "主要人员汇总表",
                "项目团队情况",
                "项目组成人员",
                "项目负责人",
                "技术负责人",
                "专业负责人",
                "人员资格",
                "职称证书",
                "执业资格证明",
            ):
                add(term)
        if cls._is_equipment_reference_title(combined):
            for term in (
                "拟投入设备",
                "主要仪器设备",
                "软件设备清单",
                "设备配置",
                "资源配置",
            ):
                add(term)
        for term in cls._requirement_search_terms(query_text):
            add(term)
        for hint in cls.MATCH_HINTS:
            if hint in query_text:
                add(f"{hint} {title}" if title else hint)
        if not terms and query_text:
            add(re.sub(r"\s+", "", query_text)[:28])
        return terms[:10]

    @classmethod
    def _extract_markdown_section(
        cls,
        markdown: str,
        title: str,
        fallback_snippet: str = "",
        search_term: str = "",
        max_chars: int = 3600,
    ) -> str:
        if not markdown:
            return cls._clean_history_snippet(fallback_snippet)[:max_chars]

        title_tokens = cls._chapter_reference_semantic_tokens(title)
        best: tuple[float, int, int] | None = None
        lines = markdown.splitlines()
        for index, line in enumerate(lines):
            heading = cls._parse_markdown_heading(line)
            if not heading:
                continue
            level, heading_title = heading
            heading_tokens = cls._chapter_reference_tokens(heading_title)
            if not title_tokens or not heading_tokens:
                continue
            overlap = title_tokens & heading_tokens
            score = len(overlap) / max(len(title_tokens), 1)
            if title and title in heading_title:
                score += 0.45
            if score >= 0.34 and (best is None or score > best[0]):
                best = (score, index, level)

        if best:
            _, start, level = best
            end = len(lines)
            for index in range(start + 1, len(lines)):
                heading = cls._parse_markdown_heading(lines[index])
                if heading and heading[0] <= level:
                    end = index
                    break
            section = "\n".join(lines[start:end]).strip()
            return cls._trim_reference_text(section, max_chars=max_chars)

        for needle in (search_term, cls._clean_history_snippet(fallback_snippet), title):
            cleaned = re.sub(r"\[[^\]]+\]", "", str(needle or "")).strip()
            if not cleaned:
                continue
            index = markdown.find(cleaned[:40])
            if index < 0 and len(cleaned) > 6:
                index = markdown.find(cleaned[:8])
            if index >= 0:
                start = max(0, index - max_chars // 3)
                end = min(len(markdown), index + max_chars)
                candidate = cls._trim_reference_text(markdown[start:end], max_chars=max_chars)
                if cls._is_service_scope_title(title) and cls._has_excluded_history_topic(candidate):
                    continue
                return candidate

        return ""

    @staticmethod
    def _parse_markdown_heading(line: str) -> tuple[int, str] | None:
        markdown_match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line or "")
        if markdown_match:
            return len(markdown_match.group(1)), markdown_match.group(2).strip()
        numbered_match = re.match(
            r"^\s*((?:第[一二三四五六七八九十百]+[章节篇]|[一二三四五六七八九十]+[、.．]|[0-9]+(?:\.[0-9]+){0,2})\s+)([\u4e00-\u9fffA-Za-z][^\n]{2,48})\s*$",
            line or "",
        )
        if numbered_match:
            prefix = numbered_match.group(1) or ""
            level = 2 + min(prefix.count(".") + prefix.count("．"), 3)
            return level, numbered_match.group(2).strip()
        return None

    @classmethod
    def _chapter_reference_score(
        cls,
        row: Dict[str, Any],
        query_text: str,
        title: str,
        matched_term: str,
        reference_text: str,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.18
        candidate_text = " ".join(
            cls._text(row.get(key))
            for key in (
                "project_title",
                "subject",
                "primary_domain",
                "primary_subdomain",
                "domain_keywords",
                "file_name",
                "node_title",
                "node_path_text",
                "node_text",
                "snippet",
            )
        )
        query_groups = cls._object_groups(query_text)
        candidate_groups = cls._object_groups(candidate_text)
        common_groups = query_groups & candidate_groups
        if common_groups:
            score += min(0.18, 0.07 * len(common_groups))
            reasons.append(f"核心对象匹配：{'、'.join(sorted(common_groups))}")

        query_services = cls._service_groups(query_text)
        candidate_services = cls._service_groups(candidate_text)
        common_services = query_services & candidate_services
        if common_services:
            score += min(0.14, 0.07 * len(common_services))
            reasons.append(f"服务类型匹配：{'、'.join(sorted(common_services))}")

        title_tokens = cls._chapter_reference_semantic_tokens(title)
        reference_tokens = cls._chapter_reference_tokens(reference_text[:1600])
        if title_tokens:
            overlap = title_tokens & reference_tokens
            if overlap:
                score += min(0.22, 0.08 * len(overlap))
                reasons.append(f"章节关键词匹配：{'、'.join(sorted(overlap)[:4])}")

        if matched_term and matched_term in reference_text:
            score += 0.08
            reasons.append("检索词命中正文")
        result = cls._text(row.get("result"))
        if "中标" in result and "未中" not in result:
            score += 0.12
            reasons.append("中标案例")
        return min(score, 0.95), reasons or ["历史库章节检索命中"]

    @staticmethod
    def _chapter_reference_tokens(value: str) -> set[str]:
        text = re.sub(r"\s+", "", str(value or ""))
        raw_tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z0-9]{2,}", text)
        stopwords = {
            "项目",
            "工程",
            "服务",
            "方案",
            "措施",
            "要求",
            "内容",
            "本章",
            "投标",
            "招标",
        }
        tokens: set[str] = set()
        for token in raw_tokens:
            if token in stopwords:
                continue
            tokens.add(token)
            if len(token) >= 4:
                for size in (2, 3):
                    tokens.update(token[index:index + size] for index in range(0, len(token) - size + 1))
        return {token for token in tokens if token and token not in stopwords}

    @staticmethod
    def _clean_history_snippet(snippet: str) -> str:
        return re.sub(r"[\[\]]", "", str(snippet or "")).strip()

    @classmethod
    def _trim_reference_text(cls, text: str, max_chars: int = 3600) -> str:
        cleaned = str(text or "").strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return f"{cleaned[:max_chars].rstrip()}\n……"

    @classmethod
    def _strip_non_text_markdown_from_reference(cls, text: str) -> str:
        """Keep only text Markdown from fallback references before generation."""
        lines = str(text or "").splitlines()
        output: list[str] = []
        table_buffer: list[str] = []
        in_html_block = False

        def is_table_row(line: str) -> bool:
            stripped = line.strip()
            if "|" not in stripped:
                return False
            normalized = stripped.strip("|")
            cells = [cell.strip() for cell in normalized.split("|")]
            return len(cells) >= 2 and len([cell for cell in cells if cell]) >= 2

        def is_divider(line: str) -> bool:
            return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line or ""))

        def is_image_line(line: str) -> bool:
            stripped = line.strip()
            return bool(
                re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", stripped)
                or re.fullmatch(r"<img\b[^>]*>", stripped, flags=re.IGNORECASE)
            )

        def html_block_tag(line: str) -> str:
            match = re.match(r"^\s*<(?P<tag>table|figure|svg|canvas|iframe|object|embed)\b", line or "", flags=re.IGNORECASE)
            return match.group("tag").lower() if match else ""

        def flush_table_buffer() -> None:
            nonlocal table_buffer
            if not table_buffer:
                return
            should_strip = any(is_divider(line) for line in table_buffer) or len(table_buffer) >= 2
            if not should_strip:
                output.extend(table_buffer)
            table_buffer = []

        for line in lines:
            if in_html_block:
                if re.search(r"</(?:table|figure|svg|canvas|iframe|object|embed)>\s*$", line, flags=re.IGNORECASE):
                    in_html_block = False
                continue
            tag = html_block_tag(line)
            if tag:
                if not re.search(rf"</{tag}>\s*$", line, flags=re.IGNORECASE):
                    in_html_block = True
                flush_table_buffer()
                continue
            if is_image_line(line):
                flush_table_buffer()
                continue
            if is_table_row(line) or is_divider(line):
                table_buffer.append(line)
                continue
            flush_table_buffer()
            output.append(line)
        flush_table_buffer()

        cleaned = "\n".join(output).strip()
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    @staticmethod
    def _reference_block_inventory(text: str) -> Dict[str, Any]:
        lines = str(text or "").splitlines()
        table_lines = [line for line in lines if "|" in line and re.search(r"\|.*\|", line)]
        image_matches = re.findall(r"!\[[^\]]*\]\([^)]+\)|<img\b[^>]*>", str(text or ""), flags=re.IGNORECASE)
        return {
            "char_count": len(str(text or "")),
            "image_count": len(image_matches),
            "table_line_count": len(table_lines),
            "has_table": bool(table_lines),
            "has_image": bool(image_matches),
        }

    @classmethod
    def _extract_pageindex_matched_blocks(
        cls,
        blocks: list[dict[str, Any]],
        *,
        title: str,
        row: Dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not blocks:
            return []
        titles: list[str] = []

        def add(candidate: Any) -> None:
            text = cls._text(candidate)
            if text and text not in titles:
                titles.append(text)

        add(row.get("node_title"))
        add(title)
        node_path = row.get("node_path")
        if isinstance(node_path, list):
            for item in reversed(node_path):
                add(item)
        add(row.get("node_path_text"))

        for candidate_title in titles:
            matched = cls._extract_matching_blocks(blocks, candidate_title)
            if matched:
                if cls._should_prefer_full_personnel_roster(title, candidate_title):
                    return cls._prefer_full_personnel_roster_blocks(blocks, matched)
                return matched
        return []

    @classmethod
    def _should_prefer_full_personnel_roster(cls, title: str, candidate_title: str) -> bool:
        text = re.sub(r"\s+", "", f"{title or ''}{candidate_title or ''}")
        if cls._is_equipment_reference_title(text):
            return False
        return any(
            keyword in text
            for keyword in (
                "项目组成人员",
                "组成人员详情",
                "人员配置",
                "主要人员",
                "拟投入人员",
                "团队人员",
            )
        )

    @classmethod
    def _prefer_full_personnel_roster_blocks(
        cls,
        blocks: list[dict[str, Any]],
        matched_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        roster_table = cls._largest_personnel_roster_table(blocks)
        if not roster_table:
            return matched_blocks

        matched_table_rows = [
            len(block.get("rows") or [])
            for block in matched_blocks
            if isinstance(block, dict) and str(block.get("type") or "") == "table"
        ]
        best_matched_rows = max(matched_table_rows or [0])
        roster_rows = len(roster_table.get("rows") or [])
        if roster_rows < max(8, best_matched_rows + 3):
            return matched_blocks

        roster_id = str(roster_table.get("id") or "")
        roster_index = next(
            (index for index, block in enumerate(blocks) if str(block.get("id") or "") == roster_id),
            -1,
        )
        if roster_index < 0:
            return matched_blocks

        start = roster_index
        while start > 0 and str(blocks[start - 1].get("type") or "") == "paragraph":
            previous_text = cls._text(blocks[start - 1].get("text") or blocks[start - 1].get("markdown"))
            if not re.search(r"人员|配置|见下表|如下", previous_text):
                break
            start -= 1
        if start > 0 and str(blocks[start - 1].get("type") or "") == "heading":
            heading_text = cls._text(blocks[start - 1].get("text") or blocks[start - 1].get("markdown"))
            if cls._is_personnel_reference_title(heading_text):
                start -= 1

        selected = blocks[start : roster_index + 1]
        if selected:
            return selected
        return [roster_table]

    @classmethod
    def _largest_personnel_roster_table(cls, blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        best_score = -1
        for block in blocks:
            if not isinstance(block, dict) or str(block.get("type") or "") != "table":
                continue
            rows = block.get("rows")
            if not isinstance(rows, list) or len(rows) < 8:
                continue
            text = re.sub(r"\s+", "", cls._text(block.get("text") or block.get("markdown")))
            if not (
                "姓名" in text
                and ("职称" in text or "注册证书" in text or "执业证书" in text)
                and ("本项目职务" in text or "负责事项" in text or "专业" in text or "岗位" in text)
            ):
                continue
            heading_text = "".join(
                cls._text(item.get("title") or item.get("text"))
                for item in (block.get("heading_path") or [])
                if isinstance(item, dict)
            )
            score = len(rows) * 10
            if re.search(r"人员配置|项目管理机构|主要人员|拟投入人员|人员表", heading_text + text):
                score += 1000
            if score > best_score:
                best = block
                best_score = score
        return best

    @classmethod
    def _extract_matching_blocks(cls, blocks: list[dict[str, Any]], title: str, max_blocks: int = 160) -> list[dict[str, Any]]:
        if not blocks:
            return []
        title_tokens = cls._chapter_reference_semantic_tokens(title)
        if not title_tokens:
            return []
        prefer_personnel_only = cls._is_personnel_reference_title(title) and not cls._is_equipment_reference_title(title)
        prefer_equipment_only = cls._is_equipment_reference_title(title) and not cls._is_personnel_reference_title(title)
        best_index = -1
        best_score = 0.0
        best_precision = 0.0
        best_level = -1
        for index, block in enumerate(blocks):
            if not isinstance(block, dict) or block.get("type") != "heading":
                continue
            text = cls._text(block.get("text") or block.get("markdown"))
            if prefer_personnel_only and cls._is_mixed_personnel_equipment_heading(text):
                continue
            if prefer_equipment_only and cls._is_mixed_personnel_equipment_heading(text):
                continue
            tokens = cls._chapter_reference_semantic_tokens(text)
            if not tokens:
                continue
            overlap_count = len(title_tokens & tokens)
            recall = overlap_count / max(len(title_tokens), 1)
            precision = overlap_count / max(len(tokens), 1)
            score = recall * 0.72 + precision * 0.28
            compact_title = re.sub(r"\s+", "", str(title or ""))
            compact_text = re.sub(r"\s+", "", text)
            if compact_title and compact_title in compact_text:
                score += 0.65
            level = int(block.get("level") or 0)
            if level:
                score += min(0.06, 0.01 * min(level, 6))
            if cls._should_skip_history_heading_candidate(blocks, index, title):
                score -= 0.65
            if (
                score > best_score
                or (
                    abs(score - best_score) <= 1e-9
                    and (
                        precision > best_precision
                        or (abs(precision - best_precision) <= 1e-9 and level > best_level)
                    )
                )
            ):
                best_index = index
                best_score = score
                best_precision = precision
                best_level = level
        if best_index < 0 or best_score < 0.34:
            return []

        anchor = blocks[best_index]
        anchor_path = cls._heading_path_ids(anchor)
        if anchor_path:
            selected_by_path: list[dict[str, Any]] = []
            for block in blocks[best_index:]:
                path = cls._heading_path_ids(block)
                if selected_by_path and path and not cls._heading_path_startswith(path, anchor_path):
                    break
                if not path and selected_by_path and block.get("type") == "heading":
                    level = int(block.get("level") or 0)
                    base_level = int(anchor.get("level") or 0)
                    if base_level and level and level <= base_level:
                        break
                selected_by_path.append(block)
                if len(selected_by_path) >= max_blocks:
                    break
            return selected_by_path

        start = max(0, best_index)
        base_level = int(blocks[best_index].get("level") or 0)
        selected: list[dict[str, Any]] = []
        for block in blocks[start:]:
            if selected and block.get("type") == "heading":
                level = int(block.get("level") or 0)
                if base_level and level and level <= base_level:
                    break
            selected.append(block)
            if len(selected) >= max_blocks:
                break
        return selected

    @staticmethod
    def _heading_path_ids(block: dict[str, Any]) -> list[str]:
        path = block.get("heading_path")
        if not isinstance(path, list):
            return []
        ids: list[str] = []
        for item in path:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item.get("id")))
        return ids

    @staticmethod
    def _heading_path_startswith(path: list[str], prefix: list[str]) -> bool:
        return bool(prefix) and len(path) >= len(prefix) and path[: len(prefix)] == prefix

    @classmethod
    def _should_skip_history_heading_candidate(cls, blocks: list[dict[str, Any]], index: int, title: str) -> bool:
        if not cls._is_service_scope_title(title):
            return False
        section_text = cls._candidate_section_probe_text(blocks, index)
        return cls._has_excluded_history_topic(section_text)

    @staticmethod
    def _has_excluded_history_topic(text: str) -> bool:
        excluded_keywords = (
            "业绩文件",
            "项目法人",
            "服务对象单位名称",
            "近年完成",
            "类似项目",
            "拟投入人员",
            "项目团队",
            "主要人员",
            "姓名",
            "职称",
            "证书",
            "执业或职业资格证明",
        )
        return any(keyword in str(text or "") for keyword in excluded_keywords)

    @staticmethod
    def _is_service_scope_title(title: str) -> bool:
        text = re.sub(r"\s+", "", str(title or ""))
        return any(keyword in text for keyword in ("服务范围", "服务内容", "设计范围", "设计内容", "工作范围"))

    @staticmethod
    def _is_personnel_reference_title(title: str) -> bool:
        text = re.sub(r"\s+", "", str(title or ""))
        return any(
            keyword in text
            for keyword in (
                "人员",
                "团队",
                "项目组",
                "负责人",
                "专业负责人",
                "技术负责人",
                "质量负责人",
                "资源配置",
                "证书",
                "职称",
                "执业资格",
                "社保",
                "劳动合同",
            )
        )

    @staticmethod
    def _is_equipment_reference_title(title: str) -> bool:
        text = re.sub(r"\s+", "", str(title or ""))
        return any(keyword in text for keyword in ("设备", "软件", "仪器", "资源配置", "工具"))

    @classmethod
    def _is_mixed_personnel_equipment_heading(cls, title: str) -> bool:
        text = re.sub(r"\s+", "", str(title or ""))
        return cls._is_personnel_reference_title(text) and cls._is_equipment_reference_title(text)

    @classmethod
    def _candidate_section_probe_text(cls, blocks: list[dict[str, Any]], index: int, max_chars: int = 900) -> str:
        if index < 0 or index >= len(blocks):
            return ""
        anchor = blocks[index]
        anchor_path = cls._heading_path_ids(anchor)
        parts: list[str] = []
        base_level = int(anchor.get("level") or 0)
        for block in blocks[index:]:
            if parts:
                path = cls._heading_path_ids(block)
                if anchor_path and path and not cls._heading_path_startswith(path, anchor_path):
                    break
                if not anchor_path and block.get("type") == "heading":
                    level = int(block.get("level") or 0)
                    if base_level and level and level <= base_level:
                        break
            parts.append(cls._text(block.get("text") or block.get("markdown")))
            if sum(len(part) for part in parts) >= max_chars:
                break
        return "\n".join(parts)[:max_chars]

    @classmethod
    def _chapter_reference_semantic_tokens(cls, value: str) -> set[str]:
        text = str(value or "")
        variants = {text}
        if "服务" in text:
            variants.add(text.replace("服务", "设计"))
        if "设计" in text:
            variants.add(text.replace("设计", "服务"))
        if any(keyword in text for keyword in ("拟投入人员", "投入人员", "人员配置")):
            variants.update({"项目团队情况", "主要人员", "拟委任的主要人员", "项目团队"})
        if any(keyword in text for keyword in ("项目团队", "主要人员", "拟委任")):
            variants.update({"拟投入人员", "投入人员", "人员配置"})
        if cls._is_personnel_reference_title(text):
            variants.update(
                {
                    "拟投入人员",
                    "拟委任的主要人员",
                    "主要人员汇总表",
                    "项目团队情况",
                    "项目负责人",
                    "技术负责人",
                    "专业负责人",
                    "人员资格",
                    "职称证书",
                    "执业资格证明",
                }
            )
        if cls._is_equipment_reference_title(text):
            variants.update({"拟投入设备", "主要仪器设备", "软件设备清单", "资源配置"})
        tokens: set[str] = set()
        for item in variants:
            tokens.update(cls._chapter_reference_tokens(item))
        return tokens

    @staticmethod
    def _blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in blocks:
            markdown = str(block.get("markdown") or "").strip()
            if markdown:
                parts.append(markdown)
        return "\n\n".join(parts).strip()

    @staticmethod
    def _blocks_to_html(blocks: list[dict[str, Any]]) -> str:
        parts = [str(block.get("html") or "").strip() for block in blocks if str(block.get("html") or "").strip()]
        return "".join(parts)

    @staticmethod
    def _extract_html_fragment(html_preview: str, blocks: list[dict[str, Any]]) -> str:
        if not html_preview or not blocks:
            return ""
        ids = [str(block.get("id") or "") for block in blocks if block.get("id")]
        parts: list[str] = []
        for block_id in ids:
            match = re.search(
                rf"<(?P<tag>[a-zA-Z0-9]+)[^>]*data-history-block-id=[\"']{re.escape(block_id)}[\"'][\s\S]*?</(?P=tag)>",
                html_preview,
            )
            if match:
                parts.append(match.group(0))
        return "".join(parts)

    @classmethod
    def _inline_history_html_assets(cls, html_fragment: str, asset_dir: str) -> str:
        if not html_fragment or not asset_dir:
            return html_fragment
        root = cls._resolve_history_artifact_path(asset_dir)
        if not root.exists() or not root.is_dir():
            return html_fragment

        def replace_src(match: re.Match) -> str:
            quote = match.group("quote")
            src = match.group("src")
            if src.startswith(("data:", "http://", "https://", "/")):
                return match.group(0)
            relative = src.replace("\\", "/")
            if relative.startswith("assets/"):
                relative = relative.split("/", 1)[1]
            candidate = (root / relative).resolve()
            try:
                if root.resolve() not in candidate.parents or not candidate.exists() or not candidate.is_file():
                    return match.group(0)
                mime_type = mimetypes.guess_type(candidate.name)[0] or "image/png"
                payload = base64.b64encode(candidate.read_bytes()).decode("ascii")
                return f"src={quote}data:{mime_type};base64,{payload}{quote}"
            except Exception:
                return match.group(0)

        return re.sub(
            r"src=(?P<quote>[\"'])(?P<src>[^\"']+)(?P=quote)",
            replace_src,
            html_fragment,
        )

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
                "best_node_title",
                "best_node_path_text",
                "best_node_text",
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
