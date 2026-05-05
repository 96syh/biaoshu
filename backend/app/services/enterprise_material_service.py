"""Enterprise material parsing helpers.

This module keeps enterprise material readiness separate from tender
requirements, while still projecting compatible legacy fields for older
generation paths.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


MATERIAL_TYPE_KEYWORDS = (
    ("人员", ("人员", "项目负责人", "团队", "社保", "劳动合同", "职称", "注册证")),
    ("业绩", ("业绩", "合同", "中标通知书", "验收", "发票")),
    ("资质", ("资质", "资格", "营业执照", "许可证", "认证", "证书")),
    ("设备", ("设备", "软件", "车辆", "工具", "仪器")),
    ("图片", ("图片", "截图", "照片", "效果图", "扫描件")),
    ("承诺", ("承诺", "声明", "函")),
    ("报价", ("报价", "价格", "费用", "金额")),
)


class EnterpriseMaterialService:
    """Build and normalize the independent enterprise material profile."""

    @staticmethod
    def infer_material_type(text: str) -> str:
        value = text or ""
        for material_type, keywords in MATERIAL_TYPE_KEYWORDS:
            if any(keyword in value for keyword in keywords):
                return material_type
        return "其他"

    @staticmethod
    def _dedupe_key(item: Dict[str, Any]) -> str:
        return re.sub(r"\s+", "", str(item.get("name") or item.get("placeholder") or "")).lower()

    @staticmethod
    def build_profile(
        required_materials: Iterable[Dict[str, Any]] | None = None,
        missing_company_materials: Iterable[Dict[str, Any]] | None = None,
        evidence_chain_requirements: Iterable[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Create an EnterpriseMaterialProfile from parsed tender requirements."""
        required_materials = list(required_materials or [])
        missing_company_materials = list(missing_company_materials or [])
        evidence_chain_requirements = list(evidence_chain_requirements or [])
        requirements: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def append_requirement(raw: Dict[str, Any], index: int, *, fallback_id_prefix: str = "EM-R") -> None:
            name = str(raw.get("name") or raw.get("target") or raw.get("purpose") or "企业资料").strip()
            placeholder = str(raw.get("placeholder") or f"〖待补充：{name}〗")
            key = EnterpriseMaterialService._dedupe_key({"name": name, "placeholder": placeholder})
            if not key or key in seen:
                return
            seen.add(key)
            material_type = str(raw.get("material_type") or EnterpriseMaterialService.infer_material_type(name + placeholder))
            source = str(raw.get("source") or raw.get("source_ref") or "")
            used_by = raw.get("used_by") or raw.get("required_by") or []
            if isinstance(used_by, str):
                used_by = [used_by]
            status = str(raw.get("status") or "missing")
            requirements.append({
                "id": str(raw.get("id") or f"{fallback_id_prefix}-{index:02d}"),
                "name": name,
                "material_type": material_type,
                "required_by": [str(item) for item in used_by if item],
                "source": source,
                "required": bool(raw.get("required", True)),
                "blocking": bool(raw.get("blocking", status == "missing" and material_type in {"资质", "报价"})),
                "placeholder": placeholder,
                "status": status if status in {"missing", "provided", "unknown", "not_applicable"} else "unknown",
                "validation_rule": str(raw.get("validation_rule") or "人工核对原件、有效期、主体名称、页码和招标文件要求是否一致"),
            })

        for index, item in enumerate(required_materials, start=1):
            append_requirement(item, index)
        offset = len(requirements)
        for index, item in enumerate(missing_company_materials, start=offset + 1):
            append_requirement({**item, "status": "missing"}, index)
        offset = len(requirements)
        for index, item in enumerate(evidence_chain_requirements, start=offset + 1):
            required_evidence = item.get("required_evidence") or []
            if isinstance(required_evidence, list) and required_evidence:
                name = f"{item.get('target') or '证据链'}：{'、'.join(str(x) for x in required_evidence[:4])}"
            else:
                name = str(item.get("target") or "证据链材料")
            append_requirement({
                "id": item.get("id"),
                "name": name,
                "source": item.get("source"),
                "status": "missing",
                "placeholder": f"〖待补充：{name}〗",
                "validation_rule": item.get("validation_rule") or "核验证据链完整性",
            }, index, fallback_id_prefix="EM-EV")

        provided = [
            {
                "id": f"EM-P-{index:02d}",
                "name": item["name"],
                "material_type": item["material_type"],
                "source": item.get("source", ""),
                "used_by": item.get("required_by", []),
                "confidence": "medium",
                "verification_status": "unverified",
            }
            for index, item in enumerate(requirements, start=1)
            if item.get("status") == "provided"
        ]
        missing = [item for item in requirements if item.get("status") != "provided"]
        verification_tasks = [
            "逐项核对企业资料原件、扫描件、有效期、主体名称和页码。",
            "对模型生成正文中的业绩、人员、资质、金额、日期和证书编号做人工复核。",
            "在 Word 中确认附件页码、签章位置、图表占位和固定格式未被破坏。",
        ]
        summary = (
            f"已识别 {len(requirements)} 项企业资料需求，"
            f"已提供 {len(provided)} 项，待补/待确认 {len(missing)} 项。"
        )
        return {
            "requirements": requirements,
            "provided_materials": provided,
            "missing_materials": missing,
            "verification_tasks": verification_tasks,
            "summary": summary,
        }

    @staticmethod
    def legacy_required_materials(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Project profile requirements to the old RequiredMaterial shape."""
        materials = []
        for item in profile.get("requirements") or []:
            materials.append({
                "id": item.get("id") or "",
                "name": item.get("name") or "",
                "purpose": "企业资料支撑",
                "source": item.get("source") or "",
                "status": item.get("status") or "missing",
                "used_by": item.get("required_by") or [],
                "volume_id": "",
            })
        return materials

    @staticmethod
    def legacy_missing_materials(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Project profile missing items to the old MissingCompanyMaterial shape."""
        missing = []
        for item in profile.get("missing_materials") or []:
            missing.append({
                "id": item.get("id") or "",
                "name": item.get("name") or "",
                "used_by": item.get("required_by") or [],
                "placeholder": item.get("placeholder") or f"〖待补充：{item.get('name') or '企业资料'}〗",
                "blocking": bool(item.get("blocking")),
            })
        return missing
