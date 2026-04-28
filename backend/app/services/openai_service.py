"""多模型兼容服务（基于 OpenAI SDK 兼容层）"""
import openai
from typing import Dict, Any, List, AsyncGenerator
import json
import asyncio
import re
import aiohttp
import os

from ..utils.outline_util import generate_one_outline_json_by_level1
from ..utils import prompt_manager
from ..utils.json_util import check_json
from ..utils.config_manager import config_manager
from ..models.schemas import AnalysisReport, ResponseMatrix, ReviewReport
from ..utils.provider_registry import (
    DEFAULT_PROVIDER,
    get_base_url_candidates,
    get_default_base_url,
    get_default_models,
    get_provider_api_mode,
    normalize_base_url,
    provider_supports_model_listing,
    resolve_api_key,
)


class OpenAIService:
    """多模型服务类"""
    
    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化模型服务，支持传入运行时配置覆盖已保存配置"""
        runtime_config = dict(config or config_manager.load_config())
        # 模型接入统一收敛到 LiteLLM Proxy，由 LiteLLM 负责把各厂商协议转换成 OpenAI 格式。
        self.provider = DEFAULT_PROVIDER
        self.api_key = runtime_config.get('api_key', '')
        self.base_url = runtime_config.get('base_url', '')
        self.model_name = runtime_config.get('model_name', 'gpt-4.1-mini')
        self.api_mode = get_provider_api_mode(self.provider, runtime_config.get('api_mode', 'auto'))
        self.normalized_base_url = normalize_base_url(self.provider, self.base_url)
        self.base_url_candidates = get_base_url_candidates(self.provider, self.base_url)
        self.resolved_base_url = (
            self.base_url_candidates[0]
            if self.base_url_candidates
            else (self.normalized_base_url or get_default_base_url(self.provider))
        )
        self.uses_anthropic_api = False
        self.uses_responses_api = False

        # 统一走 LiteLLM Proxy 暴露的 OpenAI Chat Completions 兼容接口。
        self.client = self._create_client(self.resolved_base_url)

    def _create_client(self, base_url: str | None) -> openai.AsyncOpenAI:
        """按指定 Base URL 创建客户端实例"""
        return openai.AsyncOpenAI(
            api_key=resolve_api_key(self.provider, self.api_key),
            base_url=base_url if base_url else None,
            default_headers={
                "Accept": "application/json",
                "User-Agent": "curl/8.7.1",
            },
        )

    @staticmethod
    def _force_local_fallback() -> bool:
        """端到端本地验证开关，避免测试时把用户招标文件外传到第三方模型。"""
        return os.getenv("YIBIAO_FORCE_LOCAL_FALLBACK") == "1"

    def _iter_base_urls(self) -> list[str | None]:
        """获取本次请求应尝试的 Base URL 列表"""
        if self.provider in {"custom", "anthropic", "litellm"} and self.base_url_candidates:
            return list(self.base_url_candidates)
        return [self.resolved_base_url]

    @staticmethod
    def _join_endpoint(base_url: str, path: str, force_v1: bool = False) -> str:
        """拼接 API 端点路径，兼容根地址和 /v1 根地址"""
        normalized_base = (base_url or "").rstrip("/")
        normalized_path = path if path.startswith("/") else f"/{path}"
        if force_v1 and not normalized_base.endswith("/v1"):
            normalized_base = f"{normalized_base}/v1"
        return f"{normalized_base}{normalized_path}"

    @staticmethod
    def _response_format_requires_json_guard(response_format: dict | None) -> bool:
        """判断当前响应格式是否需要额外的 JSON 输出约束"""
        if not response_format:
            return False
        return response_format.get("type") in {"json_object", "json_schema"}

    def _augment_messages_for_json_output(self, messages: list, response_format: dict | None) -> list:
        """为不支持 response_format 的本地兼容端点追加 JSON 纯输出约束"""
        if not self._response_format_requires_json_guard(response_format):
            return messages

        json_guard = (
            "你必须只输出合法 JSON，不要输出 markdown 代码块，不要输出解释性文字，"
            "不要在 JSON 前后添加任何多余内容。"
        )

        augmented_messages: list[dict[str, Any]] = []
        appended_to_system = False
        for message in messages:
            cloned = dict(message)
            if not appended_to_system and cloned.get("role") == "system":
                original_content = str(cloned.get("content", "")).strip()
                cloned["content"] = f"{original_content}\n\n{json_guard}" if original_content else json_guard
                appended_to_system = True
            augmented_messages.append(cloned)

        if not appended_to_system:
            augmented_messages.insert(0, {"role": "system", "content": json_guard})

        return augmented_messages

    @staticmethod
    def _extract_json_payload(full_content: str) -> str:
        """尽量从模型返回中提取纯 JSON 文本，兼容本地模型常见的代码块包裹"""
        if not isinstance(full_content, str):
            return full_content

        candidate = full_content.strip()
        if not candidate:
            return candidate

        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)
            candidate = candidate.strip()

        first_positions = [pos for pos in (candidate.find("{"), candidate.find("[")) if pos != -1]
        if first_positions:
            start = min(first_positions)
            opening = candidate[start]
            closing = "}" if opening == "{" else "]"
            end = candidate.rfind(closing)
            if end != -1 and end > start:
                sliced = candidate[start:end + 1].strip()
                if sliced:
                    return sliced

        return candidate

    @staticmethod
    def _compact_text(text: str, limit: int = 120) -> str:
        """压缩模型/文本抽取内容，避免兜底报告继续制造超长 JSON。"""
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        return normalized[:limit]

    @staticmethod
    def _clean_extracted_value(value: str, limit: int = 80) -> str:
        """清洗从段落或表格中抽出的字段值。"""
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" |:：\t")
        if "||" in cleaned:
            cleaned = cleaned.split("||", 1)[0].strip()
        if "|" in cleaned:
            cleaned = cleaned.split("|", 1)[0].strip()
        return cleaned[:limit]

    @staticmethod
    def _extract_table_value(text: str, labels: list[str], limit: int = 80) -> str:
        """从 file_service 扁平化后的 Word 表格行中抽取字段。"""
        for raw_line in str(text or "").splitlines():
            if "||" not in raw_line and "|" not in raw_line:
                continue
            cells = [cell.strip() for cell in re.split(r"\s*\|\|?\s*", raw_line) if cell.strip()]
            for index, cell in enumerate(cells[:-1]):
                normalized_cell = re.sub(r"^\d+(?:\.\d+)*\s*", "", cell).strip()
                for label in labels:
                    colon_match = re.match(rf"^{re.escape(label)}\s*[：:]\s*(.+)$", normalized_cell)
                    if colon_match:
                        return OpenAIService._clean_extracted_value(colon_match.group(1), limit)
                if any(label == normalized_cell for label in labels):
                    for candidate in cells[index + 1:]:
                        if candidate and candidate not in {"编列内容", "要求", "评审标准"}:
                            return OpenAIService._clean_extracted_value(candidate, limit)
        return ""

    @staticmethod
    def _extract_labeled_value(text: str, labels: list[str], limit: int = 80) -> str:
        """从招标文本中按常见标签抽取一行字段。"""
        table_value = OpenAIService._extract_table_value(text, labels, limit)
        if table_value:
            return table_value
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[：:]\s*([^\n\r。；;]{{1,120}})"
            match = re.search(pattern, text)
            if match:
                return OpenAIService._clean_extracted_value(match.group(1), limit)
        return ""

    @staticmethod
    def _extract_project_name(text: str) -> str:
        """优先从封面、公告标题或须知表抽取项目名称。"""
        table_value = OpenAIService._extract_table_value(text, ["招标项目名称", "项目名称", "采购项目名称"], 100)
        if table_value and not table_value.startswith("见"):
            return table_value
        cover_match = re.search(r"([^|\n\r]{4,100}?(?:服务框架|项目|工程|采购))\s*\|\s*招标文件", str(text or ""))
        if cover_match:
            return OpenAIService._clean_extracted_value(cover_match.group(1), 100)
        for raw_line in str(text or "").splitlines()[:40]:
            line = raw_line.strip()
            if not line or line in {"招标文件", "采购文件"}:
                continue
            if "招标文件" in line:
                candidate = line.replace("招标文件", "").strip()
                if candidate:
                    return OpenAIService._clean_extracted_value(candidate, 100)
            if re.search(r"服务框架|项目|工程|采购", line) and len(line) <= 80:
                return OpenAIService._clean_extracted_value(line, 100)
        match = re.search(r"本招标项目\s*([^\n\r，。]{4,100}?)(?:已|，|。)", text)
        if match:
            return OpenAIService._clean_extracted_value(match.group(1), 100)
        return table_value

    @staticmethod
    def _extract_project_number(text: str) -> str:
        """抽取招标/采购编号，避免表格残片误识别。"""
        match = re.search(r"(?:招标编号|项目编号|采购编号)\s*[：:]\s*([A-Za-z0-9_\-]+)", str(text or ""))
        if match:
            return OpenAIService._clean_extracted_value(match.group(1), 80)
        return OpenAIService._extract_labeled_value(text, ["项目编号", "招标编号", "采购编号"])

    @staticmethod
    def _keyword_source(text: str, keyword: str) -> str:
        """为兜底条目生成可追溯的粗粒度出处。"""
        index = text.find(keyword)
        if index == -1:
            return ""
        prefix = text[max(0, index - 80):index]
        chapter_match = re.findall(r"(第[一二三四五六七八九十\d]+章[^。\n\r]{0,30}|[一二三四五六七八九十\d]+[\.、][^。\n\r]{0,30})", prefix)
        return OpenAIService._compact_text(chapter_match[-1] if chapter_match else "招标文件相关条款", 60)

    @staticmethod
    def _fallback_analysis_report(file_content: str, reason: str = "") -> Dict[str, Any]:
        """模型结构化输出失败时的保底 AnalysisReport。

        该兜底只使用招标文件原文可见信息，不虚构企业材料，目标是让后续目录、
        正文、审校、导出流程继续可执行，并在 UI 上暴露待补与风险。
        """
        text = str(file_content or "")
        project_name = OpenAIService._extract_project_name(text)
        project_number = OpenAIService._extract_project_number(text)
        purchaser = OpenAIService._extract_labeled_value(text, ["招标人", "采购人", "建设单位"])
        budget = OpenAIService._extract_labeled_value(text, ["预算金额", "最高限价", "招标控制价", "最高投标限价"])
        service_period = OpenAIService._extract_labeled_value(text, ["服务期限", "工期", "合同履行期限"])
        deadline = OpenAIService._extract_labeled_value(text, ["投标截止时间", "递交截止时间", "开标时间"])
        signature_req = "按招标文件格式完成法定代表人/授权代表签字或盖章并加盖公章" if re.search(r"签字|盖章|公章|法定代表人", text) else ""

        score_blocks = re.findall(
            r"【评分项名称】[：:]\s*(.*?)\s*【权重/分值】[：:]\s*(.*?)\s*【评分标准】[：:]\s*(.*?)(?=【评分项名称】|【数据来源】|$)",
            text,
            flags=re.S,
        )
        if not score_blocks:
            score_blocks = re.findall(
                r"([^\n\r。；;]{2,30})\s*([0-9]+(?:\.[0-9]+)?\s*分)\s*([^\n\r]{20,240})",
                text,
            )

        technical_items = []
        business_items = []
        required_materials = []
        missing_materials = []
        evidence_requirements = []
        for index, block in enumerate(score_blocks[:8], start=1):
            name, score, standard = (OpenAIService._compact_text(part, 80) for part in block[:3])
            material_id = f"M-{index:02d}"
            evidence = []
            for keyword in ["证书", "合同", "业绩", "社保", "发票", "截图", "承诺函", "名单"]:
                if keyword in standard:
                    evidence.append(keyword)
            if evidence:
                required_materials.append({
                    "id": material_id,
                    "name": f"{name}证明材料",
                    "purpose": name,
                    "source": OpenAIService._keyword_source(text, name),
                    "status": "unknown",
                })
                missing_materials.append({
                    "id": f"X-{index:02d}",
                    "name": f"{name}相关企业材料",
                    "used_by": [f"T-{index:02d}"],
                    "placeholder": f"〖待补充：{name}相关证明材料〗",
                })
                evidence_requirements.append({
                    "id": f"EV-{index:02d}",
                    "target": name,
                    "required_evidence": evidence[:4],
                    "validation_rule": "按招标文件评分标准逐项核验",
                    "source": OpenAIService._keyword_source(text, name),
                    "risk": "证明材料缺失或专业不匹配会影响得分",
                })

            item = {
                "id": f"T-{index:02d}",
                "name": name or f"技术评分项{index}",
                "score": score,
                "standard": OpenAIService._compact_text(standard, 140),
                "source": OpenAIService._keyword_source(text, name) or "评分办法",
                "writing_focus": "正文需逐条响应评分标准并引用证明材料",
                "evidence_requirements": evidence[:4],
                "easy_loss_points": ["未按评分标准逐项响应", "证明材料缺失或不一致"],
            }
            if re.search(r"报价|价格|商务|业绩|资信|信誉", name):
                business_items.append({**item, "id": f"B-{len(business_items) + 1:02d}"})
            else:
                technical_items.append(item)

        if not technical_items:
            technical_items.append({
                "id": "T-01",
                "name": "技术服务方案",
                "score": "",
                "standard": "按招标文件技术评审要求响应",
                "source": OpenAIService._keyword_source(text, "技术") or "技术评审条款",
                "writing_focus": "围绕项目理解、实施方案、质量安全和服务保障展开",
                "evidence_requirements": [],
                "easy_loss_points": ["响应不完整", "缺少针对性"],
            })

        bid_structure = [
            {"id": "S-01", "parent_id": "", "title": "投标函及投标函附录", "purpose": "正式响应招标要求", "category": "承诺", "required": True, "fixed_format": True, "signature_required": True, "attachment_required": False, "source": OpenAIService._keyword_source(text, "投标函")},
            {"id": "S-02", "parent_id": "", "title": "资格审查资料", "purpose": "证明投标资格", "category": "资格", "required": True, "fixed_format": False, "signature_required": True, "attachment_required": True, "source": OpenAIService._keyword_source(text, "资格")},
            {"id": "S-03", "parent_id": "", "title": "技术服务方案", "purpose": "响应技术评分项", "category": "技术", "required": True, "fixed_format": False, "signature_required": False, "attachment_required": False, "source": OpenAIService._keyword_source(text, "技术")},
            {"id": "S-04", "parent_id": "", "title": "商务响应与报价文件", "purpose": "响应商务和报价要求", "category": "商务/报价", "required": True, "fixed_format": True, "signature_required": True, "attachment_required": True, "source": OpenAIService._keyword_source(text, "报价")},
        ]

        formal_review = [{
            "id": "E-01",
            "review_type": "形式评审",
            "requirement": "投标文件格式、签字盖章、递交方式需符合招标文件要求",
            "criterion": "格式完整且签章齐全",
            "required_materials": [],
            "risk": "格式或签章缺失可能导致否决",
            "target_chapters": ["投标函及投标函附录"],
            "source": OpenAIService._keyword_source(text, "形式评审"),
        }]
        qualification_review = [{
            "id": "E-02",
            "review_type": "资格评审",
            "requirement": "按招标文件提交企业资质、业绩、人员等资格证明",
            "criterion": "资格证明真实、有效、覆盖要求",
            "required_materials": [item["id"] for item in required_materials[:4]],
            "risk": "资格证明缺失或过期可能导致否决",
            "target_chapters": ["资格审查资料"],
            "source": OpenAIService._keyword_source(text, "资格评审"),
        }]
        responsiveness_review = [{
            "id": "E-03",
            "review_type": "响应性评审",
            "requirement": "服务期限、质量、报价、实质性条款需无偏离响应",
            "criterion": "未出现重大偏离",
            "required_materials": [],
            "risk": "实质性条款未响应可能导致否决",
            "target_chapters": ["技术服务方案", "商务响应与报价文件"],
            "source": OpenAIService._keyword_source(text, "响应性评审"),
        }]

        if not required_materials:
            required_materials.append({
                "id": "M-01",
                "name": "企业资格与评分证明材料",
                "purpose": "资格审查和评分佐证",
                "source": OpenAIService._keyword_source(text, "证明材料"),
                "status": "unknown",
            })
            missing_materials.append({
                "id": "X-01",
                "name": "企业资格与评分证明材料",
                "used_by": ["Q-01", "T-01"],
                "placeholder": "〖待补充：企业资质、业绩、人员、承诺等证明材料〗",
            })

        report = {
            "project": {
                "name": project_name,
                "number": project_number,
                "package_name": "",
                "package_or_lot": "",
                "purchaser": purchaser,
                "agency": OpenAIService._extract_labeled_value(text, ["代理机构", "招标代理"]),
                "procurement_method": OpenAIService._extract_labeled_value(text, ["采购方式", "招标方式"]),
                "project_type": "",
                "budget": budget,
                "maximum_price": budget,
                "funding_source": OpenAIService._extract_labeled_value(text, ["资金来源"]),
                "service_scope": OpenAIService._extract_labeled_value(text, ["服务范围", "采购内容", "招标范围"], 100),
                "service_period": service_period,
                "service_location": OpenAIService._extract_labeled_value(text, ["服务地点", "项目地点", "建设地点"]),
                "quality_requirements": OpenAIService._extract_labeled_value(text, ["质量要求", "服务质量"]),
                "bid_validity": OpenAIService._extract_labeled_value(text, ["投标有效期"]),
                "bid_bond": OpenAIService._extract_labeled_value(text, ["投标保证金"]),
                "performance_bond": OpenAIService._extract_labeled_value(text, ["履约担保", "履约保证金"]),
                "bid_deadline": deadline,
                "opening_time": OpenAIService._extract_labeled_value(text, ["开标时间"]),
                "submission_method": OpenAIService._extract_labeled_value(text, ["递交方式"]),
                "electronic_platform": OpenAIService._extract_labeled_value(text, ["电子交易平台", "电子招投标平台"]),
                "submission_requirements": OpenAIService._extract_labeled_value(text, ["递交要求", "投标文件递交", "电子投标"]),
                "signature_requirements": signature_req,
            },
            "bid_mode_recommendation": "full_bid" if re.search(r"报价|商务|资格|投标函|开标一览表", text) else "technical_only",
            "source_refs": [
                {
                    "id": "SRC-01",
                    "location": "招标文件关键条款",
                    "excerpt": OpenAIService._compact_text(text[:240], 120),
                    "related_ids": ["S-01", "T-01", "E-01"],
                }
            ],
            "volume_rules": [
                {
                    "id": "V-TECH",
                    "name": "技术标",
                    "scope": "技术服务方案与技术评分响应",
                    "separate_submission": bool(re.search(r"技术标.*单独|暗标|双盲", text)),
                    "price_allowed": not bool(re.search(r"技术.*不得.*报价|暗标|双盲", text)),
                    "anonymity_required": bool(re.search(r"暗标|双盲|匿名", text)),
                    "seal_signature_rule": signature_req,
                    "source": OpenAIService._keyword_source(text, "技术标"),
                },
                {
                    "id": "V-PRICE",
                    "name": "报价文件",
                    "scope": "报价表、费用明细和价格响应",
                    "separate_submission": bool(re.search(r"报价.*单独|价格.*单独", text)),
                    "price_allowed": True,
                    "anonymity_required": False,
                    "seal_signature_rule": signature_req,
                    "source": OpenAIService._keyword_source(text, "报价"),
                },
            ],
            "anonymity_rules": {
                "enabled": bool(re.search(r"暗标|双盲|匿名", text)),
                "scope": OpenAIService._extract_labeled_value(text, ["暗标", "双盲", "匿名"], 100),
                "forbidden_identifiers": ["企业名称", "人员姓名", "联系方式", "Logo", "商标"] if re.search(r"暗标|双盲|匿名", text) else [],
                "formatting_rules": [],
                "source": OpenAIService._keyword_source(text, "暗标") or OpenAIService._keyword_source(text, "双盲"),
            },
            "bid_structure": bid_structure,
            "formal_review_items": formal_review,
            "qualification_review_items": qualification_review,
            "responsiveness_review_items": responsiveness_review,
            "business_scoring_items": business_items[:8],
            "technical_scoring_items": technical_items[:8],
            "price_scoring_items": [{
                "id": "P-01",
                "name": "报价评分",
                "score": "",
                "logic": "按招标文件价格评分办法执行",
                "source": OpenAIService._keyword_source(text, "报价"),
                "risk": "报价口径、税费或格式错误会影响评审",
            }] if "报价" in text or "价格" in text else [],
            "price_rules": {
                "quote_method": OpenAIService._extract_labeled_value(text, ["报价方式", "报价要求"]),
                "currency": "人民币" if "人民币" in text else "",
                "maximum_price_rule": budget,
                "abnormally_low_price_rule": OpenAIService._extract_labeled_value(text, ["异常低价", "低于成本"]),
                "separate_price_volume_required": bool(re.search(r"报价.*单独|价格.*单独", text)),
                "price_forbidden_in_other_volumes": bool(re.search(r"技术.*不得.*报价|商务.*不得.*报价|价格.*不得.*技术", text)),
                "tax_requirement": "按招标文件要求含税/不含税报价" if re.search(r"含税|税率|不含税", text) else "",
                "decimal_places": OpenAIService._extract_labeled_value(text, ["小数位", "精确到"]),
                "uniqueness_requirement": "投标报价应唯一" if "唯一" in text and "报价" in text else "",
                "form_requirements": "按开标一览表或报价表格式填写" if re.search(r"开标一览表|报价表", text) else "",
                "arithmetic_correction_rule": OpenAIService._extract_labeled_value(text, ["算术错误", "修正"]),
                "missing_item_rule": OpenAIService._extract_labeled_value(text, ["缺漏项", "漏项"]),
                "prohibited_format_changes": ["不得擅自修改固定格式"] if re.search(r"不得.*修改|格式.*不得", text) else [],
                "source_ref": "SRC-01",
            },
            "qualification_requirements": [{
                "id": "Q-01",
                "name": "投标人资格要求",
                "requirement": "满足招标文件资格审查要求并提供有效证明",
                "source": OpenAIService._keyword_source(text, "资格"),
                "required_materials": [item["id"] for item in required_materials[:4]],
            }],
            "formal_response_requirements": [{
                "id": "F-01",
                "name": "投标文件格式与签章",
                "requirement": "使用招标文件规定格式，按要求签字盖章",
                "source": OpenAIService._keyword_source(text, "签字"),
                "fixed_format": True,
                "signature_required": bool(signature_req),
                "attachment_required": False,
            }],
            "mandatory_clauses": [{
                "id": "C-01",
                "clause": "服务期限、质量、报价、资格及实质性条款需逐项响应",
                "source": OpenAIService._keyword_source(text, "实质性"),
                "response_strategy": "在目录和正文中设置专门响应章节并避免负偏离",
            }],
            "rejection_risks": [{
                "id": "R-01",
                "risk": "签字盖章、资格证明、实质性响应或报价格式缺失可能导致否决",
                "source": OpenAIService._keyword_source(text, "否决") or OpenAIService._keyword_source(text, "废标"),
                "mitigation": "生成正文后执行合规审校，逐项补齐材料和格式",
            }],
            "fixed_format_forms": [{
                "id": "FF-01",
                "name": "投标函/报价表等固定格式",
                "source": OpenAIService._keyword_source(text, "格式"),
                "required_columns": [],
                "fixed_text": "",
                "fill_rules": "按招标文件模板填写，不擅自改动格式",
            }],
            "signature_requirements": [{
                "id": "SIG-01",
                "target": "投标函、授权委托书、报价表及承诺文件",
                "signer": "法定代表人或授权代表",
                "seal": "按格式要求加盖投标人公章",
                "source": OpenAIService._keyword_source(text, "盖章"),
                "risk": "漏签漏盖可能导致形式评审不通过",
            }],
            "evidence_chain_requirements": evidence_requirements[:8],
            "required_materials": required_materials[:8],
            "missing_company_materials": missing_materials[:8],
            "generation_warnings": [],
        }
        if reason:
            report["rejection_risks"].append({
                "id": "R-02",
                "risk": f"结构化模型输出未完整返回，已启用文本兜底解析：{OpenAIService._compact_text(reason, 80)}",
                "source": "系统解析状态",
                "mitigation": "可换用更快模型后重跑标准解析以获得更完整映射",
            })
            report["generation_warnings"].append({
                "id": "W-01",
                "warning": f"结构化模型输出未完整返回，已启用文本兜底解析：{OpenAIService._compact_text(reason, 80)}",
                "severity": "warning",
                "related_ids": ["R-02"],
            })
        report["response_matrix"] = OpenAIService._fallback_response_matrix(report)
        return AnalysisReport.model_validate(report).model_dump(mode="json")

    @staticmethod
    def _fallback_response_matrix(analysis_report: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """基于 AnalysisReport 稳定生成响应矩阵兜底结果。"""
        report = analysis_report or {}
        items: list[dict[str, Any]] = []

        def append_item(source_type: str, source_id: str, summary: str, materials=None, risks=None, blocking=False, priority="normal", source_refs=None):
            if not source_id:
                return
            matrix_id = f"RM-{len(items) + 1:02d}"
            items.append({
                "id": matrix_id,
                "source_item_id": source_id,
                "source_type": source_type,
                "requirement_summary": OpenAIService._compact_text(summary, 80),
                "response_strategy": "在目录和正文中设置对应章节，逐项响应并保留材料/页码占位",
                "target_chapter_ids": [],
                "required_material_ids": list(materials or []),
                "risk_ids": list(risks or []),
                "source_refs": list(source_refs or []),
                "priority": priority,
                "status": "pending",
                "blocking": blocking,
            })

        for key, source_type in (
            ("technical_scoring_items", "scoring"),
            ("business_scoring_items", "scoring"),
            ("price_scoring_items", "price"),
        ):
            for item in (report.get(key) or [])[:8]:
                append_item(
                    source_type,
                    item.get("id"),
                    item.get("standard") or item.get("logic") or item.get("name") or "",
                    item.get("evidence_requirements") or [],
                    [],
                    source_type == "price",
                    "high" if source_type == "price" or item.get("score") else "normal",
                    [item.get("source")] if item.get("source") else [],
                )

        for key in ("formal_review_items", "qualification_review_items", "responsiveness_review_items"):
            for item in (report.get(key) or [])[:8]:
                append_item(
                    "review",
                    item.get("id"),
                    item.get("requirement") or item.get("criterion") or "",
                    item.get("required_materials") or [],
                    [],
                    bool(item.get("invalid_if_missing")),
                    "high" if item.get("invalid_if_missing") else "normal",
                    [item.get("source")] if item.get("source") else [],
                )

        for item in (report.get("mandatory_clauses") or [])[:8]:
            append_item("mandatory", item.get("id"), item.get("clause") or "", [], [], True, "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("rejection_risks") or [])[:8]:
            append_item("risk", item.get("id"), item.get("risk") or "", [], [item.get("id")], bool(item.get("blocking", True)), "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("required_materials") or [])[:8]:
            append_item("material", item.get("id"), item.get("name") or item.get("purpose") or "", [item.get("id")], [], item.get("status") == "missing", "high" if item.get("status") == "missing" else "normal", [item.get("source")] if item.get("source") else [])
        for item in (report.get("fixed_format_forms") or [])[:8]:
            append_item("format", item.get("id"), item.get("name") or item.get("fill_rules") or "", [], [], True, "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("signature_requirements") or [])[:8]:
            append_item("signature", item.get("id"), item.get("target") or item.get("seal") or "", [], [], True, "high", [item.get("source")] if item.get("source") else [])
        for item in (report.get("evidence_chain_requirements") or [])[:8]:
            append_item("evidence", item.get("id"), item.get("target") or item.get("validation_rule") or "", [], [], False, "normal", [item.get("source")] if item.get("source") else [])

        high_risk_ids = [item["id"] for item in items if item.get("priority") == "high" or item.get("blocking")]
        return ResponseMatrix.model_validate({
            "items": items,
            "uncovered_ids": [item.get("source_item_id") for item in items if item.get("source_item_id")],
            "high_risk_ids": high_risk_ids,
            "coverage_summary": f"已建立 {len(items)} 条响应矩阵，待目录和正文阶段逐项覆盖。",
        }).model_dump(mode="json")

    @staticmethod
    def fallback_overview(file_content: str) -> str:
        """本地提取项目概述，用于安全 smoke 或模型异常兜底。"""
        report = OpenAIService._fallback_analysis_report(file_content)
        project = report.get("project", {})
        lines = [
            f"项目名称：{project.get('name') or '待模型解析'}",
            f"项目编号：{project.get('number') or '待模型解析'}",
            f"招标/采购人：{project.get('purchaser') or '待模型解析'}",
            f"预算/限价：{project.get('budget') or '以招标文件为准'}",
            f"服务期限：{project.get('service_period') or '以招标文件为准'}",
            f"递交截止：{project.get('bid_deadline') or '以招标文件为准'}",
            "项目概述：本项目需按招标文件要求完成资格、商务、报价和技术响应，正文应围绕评分项、实质性条款、材料清单和签字盖章要求逐项展开。",
        ]
        return "\n".join(lines)

    @staticmethod
    def fallback_requirements(file_content: str) -> str:
        """本地提取技术评分要求，用于安全 smoke 或模型异常兜底。"""
        report = OpenAIService._fallback_analysis_report(file_content)
        items = report.get("technical_scoring_items") or []
        if not items:
            return "【评分项名称】：技术服务方案\n【权重/分值】：以招标文件为准\n【评分标准】：围绕项目理解、实施方案、质量安全、进度保障、人员组织和服务响应逐项编写。\n【数据来源】：技术评审条款"
        blocks = []
        for item in items[:8]:
            blocks.append(
                "\n".join([
                    f"【评分项名称】：{item.get('name') or '技术评分项'}",
                    f"【权重/分值】：{item.get('score') or '以招标文件为准'}",
                    f"【评分标准】：{item.get('standard') or '按招标文件评分标准响应'}",
                    f"【数据来源】：{item.get('source') or '评分办法'}",
                ])
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _fallback_outline(
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
    ) -> Dict[str, Any]:
        """目录生成失败时的保底目录，字段与 OutlineItem 对齐。"""
        report = analysis_report or {}
        technical_ids = [item.get("id") for item in report.get("technical_scoring_items", []) if item.get("id")]
        material_ids = [item.get("id") for item in report.get("required_materials", []) if item.get("id")]
        material_ids.extend([item.get("id") for item in report.get("missing_company_materials", []) if item.get("id")])
        material_ids.extend([item.get("id") for item in report.get("evidence_chain_requirements", []) if item.get("id")])
        risk_ids = [item.get("id") for item in report.get("rejection_risks", []) if item.get("id")]
        requirement_ids = []
        for key in ("qualification_requirements", "formal_response_requirements", "mandatory_clauses"):
            requirement_ids.extend([item.get("id") for item in report.get(key, []) if item.get("id")])

        full_bid = bid_mode == "full_bid" or report.get("bid_mode_recommendation") == "full_bid"
        outline = [
            {
                "id": "1",
                "title": "投标函及资格商务响应",
                "description": "按正式投标文件要求完成投标函、资格审查、商务响应、签字盖章和材料索引。",
                "scoring_item_ids": [],
                "requirement_ids": requirement_ids[:8],
                "risk_ids": risk_ids[:4],
                "material_ids": material_ids[:8],
                "children": [
                    {
                        "id": "1.1",
                        "title": "投标函及承诺响应",
                        "description": "保留固定格式、签字盖章、报价和服务期限等关键字段。",
                        "scoring_item_ids": [],
                        "requirement_ids": requirement_ids[:4],
                        "risk_ids": risk_ids[:2],
                        "material_ids": [],
                    },
                    {
                        "id": "1.2",
                        "title": "资格审查资料清单",
                        "description": "列明企业资质、业绩、人员、社保、证书等应附材料和核验要点。",
                        "scoring_item_ids": [],
                        "requirement_ids": requirement_ids[:8],
                        "risk_ids": risk_ids[:4],
                        "material_ids": material_ids[:8],
                    },
                ],
            },
            {
                "id": "2",
                "title": "项目理解与总体服务方案",
                "description": "围绕项目背景、服务范围、总体思路、实施路径和成果交付展开。",
                "scoring_item_ids": technical_ids[:4],
                "requirement_ids": requirement_ids[:4],
                "risk_ids": risk_ids[:2],
                "material_ids": material_ids[:4],
                "children": [
                    {
                        "id": "2.1",
                        "title": "项目理解与需求分析",
                        "description": "结合招标范围和评分标准说明项目目标、边界和重点难点。",
                        "scoring_item_ids": technical_ids[:2],
                        "requirement_ids": [],
                        "risk_ids": [],
                        "material_ids": [],
                    },
                    {
                        "id": "2.2",
                        "title": "总体实施方案",
                        "description": "描述组织架构、工作流程、进度计划、质量安全和服务保障。",
                        "scoring_item_ids": technical_ids[:6],
                        "requirement_ids": [],
                        "risk_ids": risk_ids[:2],
                        "material_ids": [],
                    },
                ],
            },
            {
                "id": "3",
                "title": "评分项响应与证明材料",
                "description": "逐项对齐技术评分、商务评分和材料要求，避免漏项和空泛响应。",
                "scoring_item_ids": technical_ids[:8],
                "requirement_ids": requirement_ids[:8],
                "risk_ids": risk_ids[:4],
                "material_ids": material_ids[:8],
                "children": [
                    {
                        "id": "3.1",
                        "title": "技术评分项逐项响应",
                        "description": "按照评分项逐项写明响应措施、支撑材料和易失分控制。",
                        "scoring_item_ids": technical_ids[:8],
                        "requirement_ids": [],
                        "risk_ids": risk_ids[:4],
                        "material_ids": material_ids[:8],
                    },
                    {
                        "id": "3.2",
                        "title": "证明材料与页码索引",
                        "description": "汇总待补材料、证据链和最终页码索引。",
                        "scoring_item_ids": [],
                        "requirement_ids": requirement_ids[:8],
                        "risk_ids": risk_ids[:4],
                        "material_ids": material_ids[:8],
                    },
                ],
            },
        ]
        if full_bid:
            outline.append({
                "id": "4",
                "title": "报价文件与组卷自检",
                "description": "按报价规则、固定格式和导出前审校要求完成组卷检查。",
                "scoring_item_ids": [],
                "requirement_ids": requirement_ids[:8],
                "risk_ids": risk_ids[:4],
                "material_ids": material_ids[:8],
                "children": [
                    {
                        "id": "4.1",
                        "title": "报价规则响应",
                        "description": "说明报价口径、税费、唯一报价、费用明细和格式要求。",
                        "scoring_item_ids": [],
                        "requirement_ids": requirement_ids[:4],
                        "risk_ids": risk_ids[:4],
                        "material_ids": [],
                    },
                    {
                        "id": "4.2",
                        "title": "导出前合规自检",
                        "description": "检查覆盖率、缺失材料、签字盖章、固定格式和页码占位。",
                        "scoring_item_ids": technical_ids[:8],
                        "requirement_ids": requirement_ids[:8],
                        "risk_ids": risk_ids[:4],
                        "material_ids": material_ids[:8],
                    },
                ],
            })
        response_matrix = report.get("response_matrix") or OpenAIService._fallback_response_matrix(report)
        return {
            "outline": outline,
            "response_matrix": response_matrix,
            "coverage_summary": response_matrix.get("coverage_summary", ""),
        }

    @staticmethod
    def _count_analysis_items(analysis_report: Dict[str, Any] | None) -> int:
        """按已解析出的评分、审查、风险和材料数量估算目录颗粒度。"""
        report = analysis_report or {}
        keys = (
            "technical_scoring_items",
            "business_scoring_items",
            "price_scoring_items",
            "formal_review_items",
            "qualification_review_items",
            "responsiveness_review_items",
            "qualification_requirements",
            "formal_response_requirements",
            "mandatory_clauses",
            "rejection_risks",
            "required_materials",
            "missing_company_materials",
        )
        return sum(len(report.get(key) or []) for key in keys)

    @staticmethod
    def _allocate_leaf_distribution(total_leaf_nodes: int, weights: list[int]) -> list[int]:
        """按确定性权重分配叶子节点，避免随机重点章节导致生成结果漂移。"""
        if not weights:
            return []

        total_weight = max(sum(weights), 1)
        allocated = [max(2, round(total_leaf_nodes * weight / total_weight)) for weight in weights]
        diff = total_leaf_nodes - sum(allocated)
        cursor = 0
        while diff != 0 and allocated:
            index = cursor % len(allocated)
            if diff > 0:
                allocated[index] += 1
                diff -= 1
            elif allocated[index] > 2:
                allocated[index] -= 1
                diff += 1
            cursor += 1
            if cursor > len(allocated) * 20:
                break
        return allocated

    @staticmethod
    def _split_leaf_count(leaf_count: int, level2_count: int) -> list[int]:
        """把一级章节叶子节点稳定分摊给二级章节。"""
        level2_count = max(1, level2_count)
        base = leaf_count // level2_count
        extra = leaf_count % level2_count
        return [base + (1 if index < extra else 0) for index in range(level2_count)]

    @staticmethod
    def _build_nodes_distribution(
        level_l1: list[dict],
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
    ) -> dict:
        """基于评分项/审查项/风险项确定目录规模，不再使用固定十万字和随机重点章节。"""
        level1_count = len(level_l1)
        if level1_count <= 0:
            return {"level2_nodes": [], "leaf_nodes": [], "leaf_per_level2": []}

        item_count = OpenAIService._count_analysis_items(analysis_report)
        full_bid = bid_mode == "full_bid" or (analysis_report or {}).get("bid_mode_recommendation") == "full_bid"
        base_leaf_nodes = 30 if full_bid else 18
        total_leaf_nodes = max(base_leaf_nodes, level1_count * 3, item_count * 2)
        total_leaf_nodes = min(total_leaf_nodes, 72 if full_bid else 48)

        weights: list[int] = []
        for node in level_l1:
            title = str(node.get("new_title") or node.get("title") or "")
            mapped_count = (
                len(node.get("scoring_item_ids") or []) * 3
                + len(node.get("requirement_ids") or []) * 2
                + len(node.get("risk_ids") or []) * 2
                + len(node.get("material_ids") or [])
            )
            keyword_weight = 0
            if full_bid and any(keyword in title for keyword in ("资格", "商务", "报价", "投标函", "承诺", "附件", "自检")):
                keyword_weight += 2
            if any(keyword in title for keyword in ("技术", "方案", "实施", "服务", "评分", "响应")):
                keyword_weight += 2
            weights.append(max(1, mapped_count + keyword_weight + 1))

        leaf_nodes = OpenAIService._allocate_leaf_distribution(total_leaf_nodes, weights)
        level2_nodes: list[int] = []
        leaf_per_level2: list[list[int]] = []
        for leaf_count in leaf_nodes:
            level2_count = min(6, max(2, round(leaf_count / 3)))
            level2_nodes.append(level2_count)
            leaf_per_level2.append(OpenAIService._split_leaf_count(leaf_count, level2_count))

        return {
            "level2_nodes": level2_nodes,
            "leaf_nodes": leaf_nodes,
            "leaf_per_level2": leaf_per_level2,
        }

    @staticmethod
    def _fallback_chapter_content(
        chapter: dict,
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        missing_materials: list | None = None,
    ) -> str:
        """正文生成失败时的保底章节内容。"""
        title = chapter.get("title") or "当前章节"
        description = chapter.get("description") or "按招标文件要求编写。"
        project = (analysis_report or {}).get("project", {})
        missing = missing_materials or (analysis_report or {}).get("missing_company_materials", [])
        missing_lines = "\n".join(
            f"- 〖待补充：{item.get('name') or '相关证明材料'}〗{item.get('placeholder') or ''}"
            for item in missing[:6]
        ) or "- 暂未识别到企业侧已提供材料，最终组卷前需核验资格、商务、人员、业绩和签章材料。"
        return (
            f"本节围绕“{title}”进行响应。{description}\n\n"
            f"项目名称：{project.get('name') or '以招标文件为准'}。\n"
            f"响应原则：以招标文件、评分办法和标准解析报告为准，逐项覆盖当前章节关联的评分项、审查要求、风险点和材料要求。\n\n"
            "实施与响应要点：\n"
            "1. 对招标文件中的实质性条款、服务范围、进度安排、质量要求和成果交付要求逐项响应。\n"
            "2. 对评分项设置专门小节，说明工作方法、组织安排、质量控制、风险防控和交付成果。\n"
            "3. 对固定格式、报价表、承诺函、签字盖章和页码索引保留〖页码待编排〗等占位，不擅自改变格式。\n\n"
            "应附材料及核验要点：\n"
            f"{missing_lines}\n\n"
            "组卷提示：正文完成后需执行合规审校，确认覆盖率、阻塞问题、警告问题和材料缺失项。"
        )

    @staticmethod
    def _fallback_compliance_review(
        outline: list,
        analysis_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """合规审校失败时的保底审校结果。"""
        report = analysis_report or {}
        scoring_ids = [item.get("id") for item in report.get("technical_scoring_items", []) if item.get("id")]
        material_ids = [item.get("id") for item in report.get("required_materials", []) if item.get("id")]
        risk_ids = [item.get("id") for item in report.get("rejection_risks", []) if item.get("id")]
        coverage = [
            {
                "item_id": item_id,
                "target_type": "scoring",
                "covered": False,
                "chapter_ids": [],
                "issue": "需确认正文是否逐项覆盖评分标准",
                "evidence": "",
                "fix_suggestion": "在对应章节补写评分标准响应措施和支撑材料",
            }
            for item_id in scoring_ids[:8]
        ]
        missing = [
            {
                "material_id": item_id,
                "material_name": item_id,
                "used_by": [],
                "chapter_ids": [],
                "placeholder": "〖待补充或核验证明材料〗",
                "placeholder_found": False,
                "fix_suggestion": "补齐材料或在正文中保留明确待补占位",
            }
            for item_id in material_ids[:8]
        ]
        risks = [
            {"risk_id": item_id, "handled": False, "issue": "需在导出前核验签字盖章、格式、材料和实质性响应"}
            for item_id in risk_ids[:8]
        ]
        warnings = len(coverage) + len(missing) + len(risks)
        blocking_issue = {
            "item_id": "CHECK-01",
            "chapter_ids": [],
            "issue": "兜底审校无法确认完整覆盖，需要人工复核响应矩阵、材料和签章",
            "evidence": "模型审校不可用，系统返回兜底结果",
            "fix_suggestion": "重新执行合规审校或逐项检查覆盖矩阵",
            "severity": "blocking",
            "blocking": True,
        }
        return ReviewReport.model_validate({
            "coverage": coverage,
            "missing_materials": missing,
            "rejection_risks": risks,
            "duplication_issues": [],
            "fabrication_risks": [],
            "fixed_format_issues": [],
            "signature_issues": [{
                "item_id": "SIG-01",
                "chapter_ids": [],
                "issue": "签字盖章需在最终 Word 组卷后人工核验",
                "severity": "warning",
                "blocking": False,
            }],
            "price_rule_issues": [],
            "evidence_chain_issues": [],
            "page_reference_issues": [{
                "item_id": "PAGE-01",
                "chapter_ids": [],
                "issue": "最终排版前页码索引仍为待编排状态",
                "evidence": "正文导出前尚未完成 Word 页码编排",
                "fix_suggestion": "导出后更新目录、索引和页码引用",
                "severity": "warning",
                "blocking": False,
            }],
            "anonymity_issues": [],
            "blocking_issues": [blocking_issue],
            "warnings": [],
            "revision_plan": {
                "actions": [{
                    "id": "RP-01",
                    "target_chapter_ids": [],
                    "action_type": "人工确认",
                    "instruction": "逐项核验评分项、审查项、材料、签章、固定格式和报价隔离要求。",
                    "priority": "high",
                    "related_issue_ids": ["CHECK-01"],
                    "blocking": True,
                }],
                "summary": "兜底审校无法替代正式模型审校，导出前需人工复核。",
            },
            "summary": {
                "ready_to_export": False,
                "blocking_issues": 1,
                "warnings": warnings + 2,
                "blocking_issues_count": 1,
                "warnings_count": warnings + 2,
                "coverage_rate": 0,
                "blocking_summary": "需要人工复核完整响应矩阵和材料链",
                "next_actions": ["重新执行合规审校", "补齐缺失材料", "核验签章与固定格式"],
            },
        }).model_dump(mode="json")

    @staticmethod
    def _raise_if_gateway_error(payload: Any) -> None:
        """识别 OpenAI 兼容网关用 200 响应包裹的业务错误"""
        if not hasattr(payload, "model_dump"):
            return

        data = payload.model_dump()
        base_resp = data.get("base_resp")
        if not isinstance(base_resp, dict):
            return

        status_code = base_resp.get("status_code")
        status_msg = base_resp.get("status_msg") or base_resp.get("message") or "unknown error"
        if status_code not in (None, 0, "0"):
            raise Exception(f"模型网关返回错误: {status_msg} ({status_code})")

    @staticmethod
    def _is_model_selection_error(error: Exception | None) -> bool:
        """判断 OpenAI 兼容调用失败是否由模型名不匹配导致。

        这种情况下继续尝试 Claude 原生协议会掩盖真正的错误。
        """
        message = str(error or "").lower()
        return any(marker in message for marker in (
            "model",
            "not found",
            "not_found",
            "available models",
            "does not exist",
            "invalid model",
        ))
    
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        if not provider_supports_model_listing(self.provider):
            return get_default_models(self.provider)

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            client = self._create_client(candidate)
            try:
                models = await client.models.list()
                self.client = client
                self.resolved_base_url = candidate or ""
                model_ids = []
                for model in models.data:
                    if not getattr(model, "id", None):
                        continue
                    if self.provider in {"custom", "litellm"}:
                        model_ids.append(model.id)
                        continue
                    model_id = model.id.lower()
                    if any(keyword in model_id for keyword in [
                        'gpt', 'claude', 'chat', 'llama', 'qwen', 'deepseek',
                        'gemini', 'moonshot', 'kimi', 'glm', 'mistral', 'codex', 'gpt-5',
                    ]):
                        model_ids.append(model.id)
                normalized_models = sorted(list(set(model_ids)))
                if normalized_models:
                    return normalized_models

                fallback_models = get_default_models(self.provider)
                if fallback_models:
                    return fallback_models
                raise Exception("未找到可用的对话模型")
            except Exception as e:
                last_error = e

        try:
            fallback_models = get_default_models(self.provider)
            if fallback_models:
                return fallback_models
            raise Exception("未找到可用的对话模型")
        except Exception as e:
            fallback_models = get_default_models(self.provider)
            if fallback_models:
                return fallback_models
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    async def stream_chat_completion(
        self, 
        messages: list, 
        temperature: float = 0.7,
        response_format: dict = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成请求 - 真正的异步实现"""
        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            client = self._create_client(candidate)
            try:
                self.client = client
                self.resolved_base_url = candidate or ""

                request_kwargs: Dict[str, Any] = {}
                if response_format is not None:
                    request_kwargs["response_format"] = response_format
                if max_tokens is not None:
                    request_kwargs["max_tokens"] = max_tokens

                try:
                    stream = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        stream=True,
                        **request_kwargs,
                    )
                except Exception:
                    if response_format is None:
                        raise
                    fallback_messages = self._augment_messages_for_json_output(messages, response_format)
                    stream = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=fallback_messages,
                        temperature=temperature,
                        stream=True,
                        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
                    )

                received_content = False
                async for chunk in stream:
                    self._raise_if_gateway_error(chunk)
                    if not chunk.choices:
                        continue
                    if chunk.choices[0].delta.content is not None:
                        received_content = True
                        yield chunk.choices[0].delta.content
                if not received_content:
                    raise Exception("模型返回空流式内容，请确认 Base URL 指向真实 API 路径而不是管理后台页面")
                return
            except Exception as e:
                last_error = e

        if self._is_model_selection_error(last_error):
            raise Exception(
                "LiteLLM Proxy 已响应，但当前模型名不可用。请先同步模型列表并选择 LiteLLM 返回的模型 ID，"
                f"或确认 LiteLLM 配置中的 model_name。原始错误: {str(last_error)}"
            ) from last_error

        raise Exception(f"模型调用失败: {str(last_error)}") from last_error

    async def _get_anthropic_models(self) -> List[str]:
        """获取 Anthropic / Claude 原生接口的模型列表"""
        headers = {
            "x-api-key": resolve_api_key(self.provider, self.api_key),
            "anthropic-version": "2023-06-01",
        }
        last_error: Exception | None = None

        for candidate in self._iter_base_urls():
            endpoint = self._join_endpoint(candidate or "", "/models", force_v1=True)
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(endpoint, headers=headers) as response:
                        payload = await response.text()
                        if response.status >= 400:
                            raise Exception(payload[:500])

                        data = json.loads(payload)
                        models = []
                        for item in data.get("data", []):
                            model_id = item.get("id", "")
                            if "claude" in model_id.lower():
                                models.append(model_id)

                        if models:
                            self.resolved_base_url = candidate or ""
                            return sorted(list(set(models)))

                        raise Exception("未找到可用的 Claude 模型")
            except Exception as e:
                last_error = e

        raise Exception(f"获取 Claude 模型列表失败: {str(last_error)}") from last_error

    async def _stream_anthropic_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """调用 Anthropic 原生 Messages API，先以单次响应方式兼容现有流程"""
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role in {"system", "developer"}:
                system_parts.append(str(content))
                continue

            anthropic_role = "assistant" if role == "assistant" else "user"
            anthropic_messages.append({
                "role": anthropic_role,
                "content": str(content),
            })

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": ""})

        if response_format and response_format.get("type") in {"json_object", "json_schema"}:
            system_parts.append("你必须只输出合法 JSON，不要输出 markdown 代码块，不要附加解释。")

        headers = {
            "x-api-key": resolve_api_key(self.provider, self.api_key),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model_name,
            "max_tokens": 8192,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)

        last_error: Exception | None = None
        for candidate in self._iter_base_urls():
            endpoint = self._join_endpoint(candidate or "", "/messages", force_v1=True)
            try:
                timeout = aiohttp.ClientTimeout(total=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(endpoint, headers=headers, json=body) as response:
                        payload = await response.text()
                        if response.status >= 400:
                            raise Exception(payload[:1000])

                        data = json.loads(payload)
                        text_chunks = []
                        for block in data.get("content", []):
                            if block.get("type") == "text" and block.get("text"):
                                text_chunks.append(block["text"])

                        if not text_chunks:
                            raise Exception("Claude 返回内容为空")

                        self.resolved_base_url = candidate or ""
                        yield "".join(text_chunks)
                        return
            except Exception as e:
                last_error = e

        raise Exception(f"Claude 接口调用失败: {str(last_error)}") from last_error

    @staticmethod
    def _build_responses_text_config(response_format: dict | None) -> dict | None:
        """将 Chat Completions 的 response_format 映射为 Responses API 的 text.format"""
        if not response_format:
            return None

        response_type = response_format.get("type")
        if response_type in {"text", "json_object"}:
            return {"format": {"type": response_type}}

        if response_type == "json_schema":
            format_config = {"type": "json_schema"}
            for key in ("name", "schema", "strict", "description"):
                if key in response_format:
                    format_config[key] = response_format[key]
            return {"format": format_config}

        return None

    async def _stream_responses_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """针对 Codex / Responses API 的流式文本输出"""
        request_params: Dict[str, Any] = {
            "model": self.model_name,
            "input": messages,
            "temperature": temperature,
        }

        text_config = self._build_responses_text_config(response_format)
        if text_config is not None:
            request_params["text"] = text_config

        received_text = False
        async with self.client.responses.stream(**request_params) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    received_text = True
                    yield event.delta

            if not received_text:
                final_response = await stream.get_final_response()
                if final_response.output_text:
                    yield final_response.output_text

    async def _collect_stream_text(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """收集流式返回的文本到一个完整字符串"""
        full_content = ""
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=temperature,
            response_format=response_format,
            max_tokens=max_tokens,
        ):
            full_content += chunk
        return full_content

    async def verify_current_endpoint(self) -> Dict[str, Any]:
        """验证当前供应商配置是否可列模型并可发起一次对话"""
        checks: list[dict[str, Any]] = []
        visible_candidates = [candidate for candidate in self.base_url_candidates if candidate]
        models_ok = False
        chat_ok = False
        models_error = ""
        chat_error = ""

        try:
            models = await self.get_available_models()
            models_ok = True
            checks.append({
                "stage": "models",
                "success": True,
                "detail": f"获取到 {len(models)} 个模型",
                "url": self.resolved_base_url or self.normalized_base_url or "",
                "model_name": self.model_name,
                "models": models[:20],
            })
        except Exception as exc:
            models = []
            models_error = str(exc)
            checks.append({
                "stage": "models",
                "success": False,
                "detail": models_error,
                "url": self.resolved_base_url or self.normalized_base_url or "",
                "model_name": self.model_name,
            })

        if models_ok and models and self.provider in {"custom", "litellm"} and self.model_name not in models:
            chat_error = (
                f"模型名 '{self.model_name}' 不在当前端点返回的模型列表中。"
                f"可用模型: {', '.join(models[:20])}"
            )
            checks.append({
                "stage": "chat",
                "success": False,
                "detail": chat_error,
                "url": self.resolved_base_url or self.normalized_base_url or "",
                "model_name": self.model_name,
                "models": models[:20],
            })
        else:
            try:
                sample = await self._collect_stream_text(
                    messages=[{"role": "user", "content": "请只回复 OK"}],
                    temperature=0,
                )
                if not sample.strip():
                    raise Exception("模型返回空内容，请确认 Base URL、模型名和 API Key 是否正确")
                chat_ok = True
                checks.append({
                    "stage": "chat",
                    "success": True,
                    "detail": "对话请求成功",
                    "url": self.resolved_base_url or self.normalized_base_url or "",
                    "model_name": self.model_name,
                    "sample": sample.strip()[:200],
                })
            except Exception as exc:
                chat_error = str(exc)
                checks.append({
                    "stage": "chat",
                    "success": False,
                    "detail": chat_error,
                    "url": self.resolved_base_url or self.normalized_base_url or "",
                    "model_name": self.model_name,
                })

        if models_ok and chat_ok:
            message = "端点验证成功"
        elif chat_ok:
            message = f"模型列表验证失败，但对话请求成功: {models_error}"
        elif models_ok:
            message = f"对话请求验证失败: {chat_error}"
        else:
            message = f"模型列表与对话请求均失败: {chat_error or models_error}"

        return {
            "success": chat_ok,
            "message": message,
            "provider": self.provider,
            "normalized_base_url": self.normalized_base_url or "",
            "resolved_base_url": self.resolved_base_url or "",
            "base_url_candidates": visible_candidates,
            "model_name": self.model_name,
            "api_mode": self.api_mode,
            "checks": checks,
        }

    async def _generate_with_json_check(
        self,
        messages: list,
        schema: str | Dict[str, Any],
        max_retries: int = 3,
        temperature: float = 0.7,
        response_format: dict | None = None,
        log_prefix: str = "",
        raise_on_fail: bool = True,
    ) -> str:
        """
        通用的带 JSON 结构校验与重试的生成函数。

        返回：通过校验的 full_content；如果 raise_on_fail=False，则在多次失败后返回最后一次内容。
        """
        attempt = 0
        last_error_msg = ""

        while True:
            full_content = await self._collect_stream_text(
                messages,
                temperature=temperature,
                response_format=response_format,
            )

            normalized_content = self._extract_json_payload(str(full_content))
            isok, error_msg = check_json(str(normalized_content), schema)
            if isok:
                return normalized_content

            last_error_msg = error_msg
            prefix = f"{log_prefix} " if log_prefix else ""

            if attempt >= max_retries:
                print(f"{prefix}check_json 校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                if raise_on_fail:
                    raise Exception(f"{prefix}check_json 校验失败: {last_error_msg}")
                # 不抛异常，返回最后一次内容（保持原有行为）
                return normalized_content

            attempt += 1
            print(f"{prefix}check_json 校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
            await asyncio.sleep(0.5)

    async def _generate_pydantic_json(
        self,
        messages: list,
        model_cls: type,
        max_retries: int = 3,
        temperature: float = 0.3,
        response_format: dict | None = None,
        max_tokens: int | None = None,
        log_prefix: str = "",
    ) -> Dict[str, Any]:
        """生成 JSON 并使用 Pydantic 模型校验，适合允许空数组的结构化结果"""
        attempt = 0
        last_error_msg = ""

        while True:
            request_messages = messages
            if attempt > 0:
                request_messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "上一次输出不是可解析的完整 JSON，常见原因是输出过长被截断。"
                            "请重新输出一个更精简但字段完整的合法 JSON：每个数组最多保留最关键 8 项，"
                            "长文本压缩到 80 字以内，必须闭合所有对象和数组。"
                            f"上次错误：{last_error_msg}"
                        ),
                    },
                ]

            full_content = await self._collect_stream_text(
                request_messages,
                temperature=temperature,
                response_format=response_format,
                max_tokens=max_tokens,
            )
            normalized_content = self._extract_json_payload(str(full_content))

            try:
                parsed = model_cls.model_validate_json(str(normalized_content))
                return parsed.model_dump(mode="json")
            except Exception as e:
                last_error_msg = str(e)
                prefix = f"{log_prefix} " if log_prefix else ""

                if attempt >= max_retries:
                    print(f"{prefix}Pydantic JSON 校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                    raise Exception(f"{prefix}Pydantic JSON 校验失败: {last_error_msg}") from e

                attempt += 1
                print(f"{prefix}Pydantic JSON 校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
                await asyncio.sleep(0.5)

    async def generate_analysis_report(self, file_content: str) -> Dict[str, Any]:
        """从招标文件全文生成结构化标准解析报告"""
        if self._force_local_fallback():
            return self._fallback_analysis_report(file_content, "本地安全验证模式")

        system_prompt, user_prompt = prompt_manager.generate_analysis_report_prompt(file_content)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            report = await asyncio.wait_for(
                self._generate_pydantic_json(
                    messages=messages,
                    model_cls=AnalysisReport,
                    max_retries=1,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                    log_prefix="标准解析报告",
                ),
                timeout=120,
            )
            if not report.get("response_matrix"):
                report["response_matrix"] = await self.generate_response_matrix(report)
            return AnalysisReport.model_validate(report).model_dump(mode="json")
        except Exception as e:
            print(f"标准解析报告模型输出不可用，启用文本兜底解析：{str(e)}")
            return self._fallback_analysis_report(file_content, str(e))

    async def generate_response_matrix(self, analysis_report: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """基于标准解析报告生成响应矩阵"""
        report = analysis_report or {}
        if self._force_local_fallback():
            return self._fallback_response_matrix(report)

        system_prompt, user_prompt = prompt_manager.generate_response_matrix_prompt(report)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return await asyncio.wait_for(
                self._generate_pydantic_json(
                    messages=messages,
                    model_cls=ResponseMatrix,
                    max_retries=1,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                    log_prefix="响应矩阵",
                ),
                timeout=90,
            )
        except Exception as e:
            print(f"响应矩阵模型输出不可用，启用兜底矩阵：{str(e)}")
            return self._fallback_response_matrix(report)

    async def generate_compliance_review(
        self,
        outline: list,
        analysis_report: Dict[str, Any] | None = None,
        project_overview: str = "",
        response_matrix: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """生成导出前合规审校报告"""
        if self._force_local_fallback():
            return self._fallback_compliance_review(outline, analysis_report)

        system_prompt, user_prompt = prompt_manager.generate_compliance_review_prompt(
            analysis_report=analysis_report,
            outline=outline,
            project_overview=project_overview,
            response_matrix=response_matrix or (analysis_report or {}).get("response_matrix"),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return await asyncio.wait_for(
                self._generate_pydantic_json(
                    messages=messages,
                    model_cls=ReviewReport,
                    max_retries=1,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    log_prefix="合规审校",
                ),
                timeout=120,
            )
        except Exception as e:
            print(f"合规审校模型输出不可用，启用文本兜底审校：{str(e)}")
            return self._fallback_compliance_review(outline, analysis_report)

    async def generate_content_for_outline(
        self,
        outline: Dict[str, Any],
        project_overview: str = "",
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
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
    ) -> AsyncGenerator[str, None]:
        """
        为单个章节流式生成内容

        Args:
            chapter: 章节数据
            parent_chapters: 上级章节列表，每个元素包含章节id、标题和描述
            sibling_chapters: 同级章节列表，避免内容重复
            project_overview: 项目概述信息，提供项目背景和要求

        Yields:
            生成的内容流
        """
        try:
            if self._force_local_fallback():
                yield self._fallback_chapter_content(
                    chapter,
                    project_overview=project_overview,
                    analysis_report=analysis_report,
                    missing_materials=missing_materials,
                )
                return

            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            chapter_description = chapter.get('description', '')
            rulebook = prompt_manager.get_full_bid_rulebook()

            # 构建提示词
            effective_response_matrix = response_matrix or (analysis_report or {}).get("response_matrix") or {}

            system_prompt = f"""你是一个专业的标书编制工程师，负责在“开始生成标书”阶段，依据已完成的《标准解析报告》、ResponseMatrix 响应矩阵与既定目录，逐章生成正式投标文件内容。

生成前必须依据传入资料完成以下判断，但不要把判断过程写出来：
1. 回顾传入的《标准解析报告》和 ResponseMatrix 中的项目基础信息、否决投标条款、资格审查要求、评分项、正式投标文件结构、证明材料要求、待补资料清单和高风险废标点。
2. 判断当前章节属于哪一类：函件类、承诺类、表格类、报价类、证明材料类、资格商务类、技术方案类、索引表类、其他资料类。
3. 依据章节类型选择对应写法，再生成可直接用于正式投标文件的正文。

硬性要求：
1. 只输出当前章节正文，不输出标题、说明、前言、总结、markdown 代码块。
2. 只能使用传入的 AnalysisReport、ResponseMatrix、目录映射、项目概述和企业材料；不得重新解析招标文件，不得另行推断新的评分项、审查项、企业资质或证明材料。
3. 严禁编造企业名称、金额、日期、证书编号、业绩名称、人员姓名、联系方式、发票信息、查询结果、合同信息。
4. 若上下文未提供且无法确认，必须使用〖待补充：具体资料名称〗或〖以招标文件/企业资料为准〗标注，不得猜测。
5. 对营业执照、资质证书、身份证、社保、审计报告、合同、发票、税务查验截图、信誉查询截图等证明材料类章节，如缺少资料，不要写空泛叙述，直接输出“本节应附材料清单 + 核验要点”或保留规范占位内容。
6. 对投标函、附录、承诺函、授权委托书、偏离表、一览表、基本情况表、人员表、业绩表等正式文件章节，必须使用正式标书语言，字段完整、格式严谨、可直接落地。
7. 对技术方案类章节，必须围绕当前章节关联的 scoring_item_ids 展开；不得把未关联评分项强行塞入本章。
8. 与同级章节不得重复；与上级章节保持逻辑承接；与正式投标文件结构保持一致。
9. 不得写“作为 AI”“根据你的要求”“以下内容”等元话术。
10. 对固定格式表、报价表、费用明细表、承诺函、偏离表，只能生成待填内容或材料清单，不得擅自改变招标文件要求的表头、列名、固定文字、行列数量。
11. 对索引表或响应页码，未最终排版前统一使用〖页码待编排〗。
12. 对业绩、人员、社保、发票、税务查验、信用截图等证据链章节，必须写出应附材料和核验要点；缺失时保留明确占位，不得写成已满足。
13. 如 bid_mode 或 AnalysisReport 显示价格文件需要单独成册，不得在技术/商务章节生成具体报价内容。
14. 如 AnalysisReport 显示暗标、双盲或匿名要求，不得输出企业名称、人员姓名、业绩名称、联系方式、Logo、商标等身份识别信息。

{rulebook}
"""

            # 构建上下文信息
            context_info = ""
            
            # 上级章节信息
            if parent_chapters:
                context_info += "上级章节信息：\n"
                for parent in parent_chapters:
                    context_info += f"- {parent['id']} {parent['title']}\n  {parent['description']}\n"
            
            # 同级章节信息（排除当前章节）
            if sibling_chapters:
                context_info += "同级章节信息（请避免内容重复）：\n"
                for sibling in sibling_chapters:
                    if sibling.get('id') != chapter_id:  # 排除当前章节
                        context_info += f"- {sibling.get('id', 'unknown')} {sibling.get('title', '未命名')}\n  {sibling.get('description', '')}\n"

            structured_context: list[str] = []
            if bid_mode:
                structured_context.append(f"标书生成模式：{bid_mode}")
            if analysis_report:
                structured_context.append(
                    "标准解析报告(JSON)：\n"
                    f"{json.dumps(analysis_report, ensure_ascii=False)}"
                )
            chapter_links = {
                "scoring_item_ids": chapter.get("scoring_item_ids", []),
                "requirement_ids": chapter.get("requirement_ids", []),
                "risk_ids": chapter.get("risk_ids", []),
                "material_ids": chapter.get("material_ids", []),
                "response_matrix_ids": chapter.get("response_matrix_ids", []),
            }
            if any(chapter_links.values()):
                structured_context.append(
                    "当前章节关联项(JSON)：\n"
                    f"{json.dumps(chapter_links, ensure_ascii=False)}"
                )
            if effective_response_matrix:
                matrix_items = effective_response_matrix.get("items", [])
                linked_ids = set(chapter.get("response_matrix_ids", []) or [])
                linked_source_ids = set(
                    (chapter.get("scoring_item_ids", []) or [])
                    + (chapter.get("requirement_ids", []) or [])
                    + (chapter.get("risk_ids", []) or [])
                    + (chapter.get("material_ids", []) or [])
                )
                relevant_matrix = [
                    item for item in matrix_items
                    if item.get("id") in linked_ids
                    or item.get("source_item_id") in linked_source_ids
                    or not linked_ids and not linked_source_ids and item.get("priority") == "high"
                ][:12]
                structured_context.append(
                    "当前章节响应矩阵(JSON，只能据此覆盖要求，不得新增要求)：\n"
                    f"{json.dumps({'items': relevant_matrix}, ensure_ascii=False)}"
                )
            if generated_summaries:
                structured_context.append(
                    "已生成章节摘要(JSON，用于避免重复)：\n"
                    f"{json.dumps(generated_summaries, ensure_ascii=False)}"
                )
            if enterprise_materials:
                structured_context.append(
                    "已提供企业材料(JSON)：\n"
                    f"{json.dumps(enterprise_materials, ensure_ascii=False)}"
                )
            if missing_materials:
                structured_context.append(
                    "待补企业资料(JSON，正文必须保留占位)：\n"
                    f"{json.dumps(missing_materials, ensure_ascii=False)}"
                )

            # 构建用户提示词
            project_info = ""
            if project_overview.strip():
                project_info = f"项目概述信息：\n{project_overview}\n\n"
            
            user_prompt = f"""当前已完成前两步：
第一步：标准解析报告；
第二步：目录生成。
本次调用视为用户已明确下达“开始生成标书”指令。

请先结合项目概述、上级章节、同级章节和当前章节信息，判断本章节类型，再按正式投标文件写法生成正文。
若企业资料仍有缺失，请在正文中用〖待补充：...〗明确标注，不得虚构。

{project_info}{context_info if context_info else ''}{chr(10).join(structured_context)}

当前章节信息：
章节ID: {chapter_id}
章节标题: {chapter_title}
章节描述: {chapter_description}

输出要求：
1. 只输出当前章节正文。
2. 不输出章节标题。
3. 不输出解释、提示语、前后说明。
4. 不输出 markdown 代码块。"""

            # 调用AI流式生成内容
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 流式返回生成的文本
            try:
                async for chunk in self.stream_chat_completion(messages, temperature=0.4):
                    yield chunk
            except Exception as e:
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
            
    async def generate_outline_v2(
        self,
        overview: str,
        requirements: str,
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
    ) -> Dict[str, Any]:
        if self._force_local_fallback():
            return self._fallback_outline(analysis_report, bid_mode)

        scope_instruction = (
            "生成完整投标文件一级提纲，覆盖资格、商务、报价、承诺、技术、附件和组卷自检。"
            if bid_mode == "full_bid"
            else "生成技术标一级提纲，优先覆盖技术评分项和技术响应要求。"
        )
        schema_json = json.dumps([
            {
                "id": "1",
                "volume_id": "V-TECH",
                "title": "正式一级目录标题",
                "chapter_type": "technical/business/price/form/material/review",
                "description": "本章响应什么要求、覆盖哪些评分/审查/材料/风险",
                "fixed_format_sensitive": False,
                "price_sensitive": False,
                "anonymity_sensitive": False,
                "expected_word_count": 1200,
                "scoring_item_ids": [],
                "requirement_ids": [],
                "risk_ids": [],
                "material_ids": [],
                "response_matrix_ids": [],
            }
        ], ensure_ascii=False)

        system_prompt = f"""
            ### 角色
            你是专业的标书解析与编制专家，尤其适配本地 DeepSeek 类大模型。

            ### 工作流
            当前阶段只能基于传入的 AnalysisReport、ResponseMatrix、项目概述和评分要求生成一级目录。
            如果 analysis_report_json 非空，必须以它为准，不得另行推断新的审查项、评分项、材料项或风险项。
            只有等企业资料补齐且用户明确说“开始生成标书”时，才进入正文生成阶段。

            ### 当前任务
            {scope_instruction}
            当前只生成一级提纲，不生成正文，不输出解析报告。

            ### 说明
            1. 一级标题数量必须服务于 bid_mode：technical_only 时与技术评分/技术响应要求对应；full_bid 时与招标文件要求的完整投标文件结构对应。
            2. 一级标题名称应改写为正式目录标题，不能简单照抄评分项原文。
            3. 标题应服务于后续正式标书写作，避免口语化和空泛表述。
            4. full_bid 时优先按资格证明文件、商务技术文件、报价文件、附件、承诺函、偏离表、证明材料、组卷自检等卷册/章节拆分，再把评分项挂到相应章节。
            5. technical_only 时聚焦技术评分项和技术响应，不生成报价文件正文入口。
            6. scoring_item_ids 只允许引用 T/B/P ID；requirement_ids 只允许引用 E/Q/F/C/S/FF/SIG ID；risk_ids 只允许引用 R ID；material_ids 只允许引用 M/X/EV ID；response_matrix_ids 只允许引用 RM ID；无法对应时输出空数组。
            7. 价格文件要求单独递交、暗标/双盲/匿名要求、固定格式和签章要求必须体现在标题、映射或后续 description 中。
            8. 只输出 JSON，不要输出 markdown 代码块，不要输出解释。

            ### Output Format in JSON
            {schema_json}

            """
        user_prompt = f"""
            ### 项目信息
            
            <overview>
            {overview}
            </overview>

            <requirements>
            {requirements}
            </requirements>

            <bid_mode>
            {bid_mode or ""}
            </bid_mode>

            <analysis_report_json>
            {json.dumps(analysis_report, ensure_ascii=False) if analysis_report else ""}
            </analysis_report_json>

            <response_matrix_json>
            {json.dumps((analysis_report or {}).get("response_matrix", {}), ensure_ascii=False) if analysis_report else ""}
            </response_matrix_json>

            请基于传入资料输出一级目录 JSON。
            当前只执行“生成目录”这一步，不要开始生成标书正文。
            直接返回 json，不要任何额外说明或格式标记。

            """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时抛出异常）
        try:
            full_content = await asyncio.wait_for(
                self._generate_with_json_check(
                    messages=messages,
                    schema=schema_json,
                    max_retries=1,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    log_prefix="一级提纲",
                    raise_on_fail=True,
                ),
                timeout=120,
            )
        except Exception as e:
            print(f"一级提纲模型输出不可用，启用文本兜底目录：{str(e)}")
            return self._fallback_outline(analysis_report, bid_mode)

        # 通过校验后再进行 JSON 解析
        level_l1 = json.loads(full_content.strip())

        nodes_distribution = self._build_nodes_distribution(level_l1, analysis_report, bid_mode)
        
        # 并发生成每个一级节点的提纲，保持结果顺序
        tasks = [
            self.process_level1_node(
                i,
                level1_node,
                nodes_distribution,
                level_l1,
                overview,
                requirements,
                analysis_report=analysis_report,
                bid_mode=bid_mode,
                response_matrix=(analysis_report or {}).get("response_matrix"),
            )
            for i, level1_node in enumerate(level_l1)
        ]
        outline = await asyncio.gather(*tasks)
        
        
        
        return {
            "outline": outline,
            "response_matrix": (analysis_report or {}).get("response_matrix"),
            "coverage_summary": (analysis_report or {}).get("response_matrix", {}).get("coverage_summary", ""),
        }
    
    async def process_level1_node(
        self,
        i,
        level1_node,
        nodes_distribution,
        level_l1,
        overview,
        requirements,
        analysis_report: Dict[str, Any] | None = None,
        bid_mode: str | None = None,
        response_matrix: Dict[str, Any] | None = None,
    ):
        """处理单个一级节点的函数"""

        # 生成json
        title = level1_node.get("title") or level1_node.get("new_title") or level1_node.get("rating_item") or f"第{i + 1}章"
        json_outline = generate_one_outline_json_by_level1(title, i + 1, nodes_distribution)
        json_outline["volume_id"] = level1_node.get("volume_id", "")
        json_outline["chapter_type"] = level1_node.get("chapter_type", "")
        for key in ("scoring_item_ids", "requirement_ids", "risk_ids", "material_ids", "response_matrix_ids"):
            json_outline[key] = level1_node.get(key, [])
        for bool_key in ("fixed_format_sensitive", "price_sensitive", "anonymity_sensitive"):
            json_outline[bool_key] = bool(level1_node.get(bool_key, False))
        json_outline["expected_word_count"] = int(level1_node.get("expected_word_count") or 0)
        print(f"正在处理第{i+1}章: {title}")
        
        # 其他标题
        other_outline = "\n".join([f"{j+1}. {node.get('title') or node.get('new_title') or node.get('rating_item') or ''}"
                            for j, node in enumerate(level_l1) 
                            if j!= i])

        system_prompt = f"""
    ### 角色
    你是专业的标书解析与编制专家，尤其适配本地 DeepSeek 类大模型。

    ### 工作流
    1. 当前阶段只能基于传入的 AnalysisReport、ResponseMatrix、项目概述、评分要求和一级目录补全二三级目录。
    2. 如果 analysis_report_json 非空，必须以它为准，不得另行推断新的审查项、评分项、材料项或风险项。
    3. 只有等企业资料补齐且用户明确说“开始生成标书”时，才进入正文生成阶段。

    ### 当前任务
    1. 根据项目概述(overview)、评分要求(requirements)补全标书提纲的二三级目录。
    2. 当前只生成目录，不生成正文，不输出解析报告。

    ### 说明
    1. 你将得到一段 json，这是提纲中的一个一级章节，你需要在原结构上补全 title 和 description。
    2. 二级标题根据一级标题撰写，三级标题根据二级标题撰写。
    3. 补全内容必须参考项目概述、评分要求、标准解析报告、正式投标文件写法和后续正文生成需要。
    4. 你还会收到其他一级章节标题(other_outline)，你必须确保本章节不与其他章节重复。
    5. description 要写清本节点拟写内容、对应评分点/审查点、应附材料或支撑内容。
    6. scoring_item_ids 只允许引用 T/B/P ID；requirement_ids 只允许引用 E/Q/F/C/S/FF/SIG ID；risk_ids 只允许引用 R ID；material_ids 只允许引用 M/X/EV ID；response_matrix_ids 只允许引用 RM ID；一级节点既有映射必须保留，二三级节点可细化继承。
    7. 如 bid_mode=full_bid，必须补全资格、商务、报价、承诺、技术、附件等正式投标文件结构；如 bid_mode=technical_only，则聚焦技术评分和技术响应章节。
    8. 对固定格式、签字盖章、报价规则、证据链和页码占位要求，要体现在 title/description 或映射字段中。

    ### 注意事项
    1. 在原 json 上补全信息，禁止修改 json 结构，禁止修改一级标题。
    2. 只输出 JSON，不要输出 markdown 代码块，不要输出解释。

    ### Output Format in JSON
    {json_outline}

    """
        user_prompt = f"""
    ### 项目信息

    <overview>
    {overview}
    </overview>

    <requirements>
    {requirements}
    </requirements>

    <bid_mode>
    {bid_mode or ""}
    </bid_mode>

    <analysis_report_json>
    {json.dumps(analysis_report, ensure_ascii=False) if analysis_report else ""}
    </analysis_report_json>

    <response_matrix_json>
    {json.dumps(response_matrix or (analysis_report or {}).get("response_matrix", {}), ensure_ascii=False)}
    </response_matrix_json>
    
    <other_outline>
    {other_outline}
    </other_outline>

    请基于传入资料补全当前一级章节的二三级目录。
    当前只执行“生成目录”这一步，不要开始生成标书正文。
    直接返回 json，不要任何额外说明或格式标记。

    """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时不抛异常，保持原有“返回最后一次结果”的行为）
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=json_outline,
            max_retries=3,
            temperature=0.3,
            response_format={"type": "json_object"},
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )

        return json.loads(full_content.strip())
