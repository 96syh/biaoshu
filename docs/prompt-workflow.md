# 标书提示词工作流与优化方案

## 目标

本文档固定“华正 AI 标书创作平台”的提示词工作流，说明当前链路、主要问题、优化后的阶段设计、结构化数据契约和后续代码改造顺序。

核心目标：

- 让每个提示词阶段有明确输入、输出和验收标准。
- 将“标准解析报告”从模型内部思考升级为可复用的结构化数据。
- 让目录节点与评分项、审查项、证明材料和待补资料建立映射。
- 在导出前增加合规审校，降低漏项、虚构和重复风险。

## 当前工作流

当前代码中的主要入口如下：

- 文档解析：`backend/app/routers/document.py`
  - `analysis_type=overview`：提取项目概述。
  - `analysis_type=requirements`：提取技术评分要求。
- 方案扩写目录提取：`backend/app/routers/expand.py`
  - 调用 `prompt_manager.read_expand_outline_prompt()`。
- 目录生成：`backend/app/services/openai_service.py`
  - `generate_outline_v2()` 先生成一级目录。
  - `process_level1_node()` 并发补全每个一级章节的二、三级目录。
- 正文生成：`backend/app/services/openai_service.py`
  - `_generate_chapter_content()` 根据当前章节、上级章节、同级章节和项目概述生成正文。
- 前端解析与消费：
  - `frontend/src/pages/DocumentAnalysis.tsx` 顺序调用 overview 和 requirements。
  - `frontend/src/pages/OutlineEdit.tsx` 接收目录 JSON 并做前端 JSON 提取。
  - `frontend/src/pages/ContentEdit.tsx` 批量按叶子节点生成正文。

当前链路：

```text
招标文件全文
  -> 项目概述文本
  -> 技术评分要求文本
  -> 一级目录 JSON
  -> 二三级目录 JSON
  -> 叶子章节正文
  -> Word 导出
```

## 当前主要问题

### 1. 标准解析报告没有落地

多个提示词要求模型“先在内部完成《标准解析报告》”，但这个报告没有作为 JSON 返回、保存或传递。后续正文提示词声称要“回顾《标准解析报告》”，实际只能看到：

- 项目概述。
- 当前章节。
- 上级章节。
- 同级章节。

这会导致章节写作缺少完整依据，尤其是废标条款、资格要求、证明材料、待补资料和评分点覆盖关系。

### 2. 生成模式不明确

解析阶段偏向“只提取技术评分项”，目录提示词又要求识别商务、资格、报价、形式评审和完整投标文件结构。建议显式区分：

- `technical_only`：只生成技术标。
- `full_bid`：生成完整投标文件。

所有提示词都应接收同一个 `bid_mode`，避免阶段之间范围漂移。

### 3. 目录节点缺少评分映射

当前目录节点主要包含：

```json
{
  "id": "1.1.1",
  "title": "",
  "description": ""
}
```

缺少 `scoring_item_ids`、`requirement_ids`、`risk_ids`、`material_ids` 等映射字段。后续无法自动检查评分项是否覆盖，也无法判断章节需要哪些证明材料。

### 4. 正文生成缺少资料缺口上下文

正文提示词要求不得虚构，缺失资料用 `【待补充：...】` 标注。但缺失资料没有作为结构化清单传入，模型只能凭章节标题和描述猜测。

### 5. 缺少导出前审校阶段

当前正文生成后可以直接导出 Word。标书场景至少需要导出前检查：

- 评分项是否覆盖。
- 否决投标/实质性条款是否响应。
- 证明材料是否缺失。
- 章节内容是否重复。
- 是否存在虚构企业信息。

## 优化后的工作流

建议升级为 6 阶段：

```text
阶段 1：招标文件解析
  输入：招标文件全文
  输出：AnalysisReport JSON

阶段 2：目录规划
  输入：AnalysisReport + bid_mode + 可选旧目录
  输出：OutlinePlan JSON

阶段 3：目录补全
  输入：AnalysisReport + OutlinePlan + 当前一级章节 + 其他一级章节
  输出：OutlineNode JSON

阶段 4：章节正文生成
  输入：AnalysisReport + OutlineNode + 上级章节 + 同级章节 + 已生成摘要
  输出：章节正文文本

阶段 5：合规审校
  输入：AnalysisReport + 完整目录 + 正文内容
  输出：ReviewReport JSON

阶段 6：导出前整理
  输入：完整目录 + 正文内容 + ReviewReport
  输出：可导出内容或待处理问题清单
```

## 核心数据契约

### AnalysisReport

`AnalysisReport` 是后续所有 prompt 的核心上下文。它应该替代当前的“内部标准解析报告”。

从完整标书提示词模板中提炼出的规则，不再作为一个巨型 prompt 直接发送，而是落到以下结构化字段：

- `bid_structure`：投标文件结构树，记录章节用途、必备性、固定格式、签字盖章和附件要求。
- `formal_review_items` / `qualification_review_items` / `responsiveness_review_items`：形式、资格、响应性评审条款。
- `business_scoring_items` / `technical_scoring_items` / `price_scoring_items`：商务、技术、价格评分项。
- `price_rules`：报价方式、税率、小数位、唯一报价、算术修正、缺漏项和禁止改格式要求。
- `fixed_format_forms`：不得改动表头、列名、固定文字、行列数量的格式表。
- `signature_requirements`：签字盖章主体、位置、印章和遗漏风险。
- `evidence_chain_requirements`：业绩、人员、社保、发票、税务查验、信用截图、保证金等证据链。

```json
{
  "project": {
    "name": "",
    "number": "",
    "purchaser": "",
    "budget": "",
    "service_scope": "",
    "service_period": "",
    "service_location": "",
    "quality_requirements": ""
  },
  "bid_mode_recommendation": "technical_only",
  "technical_scoring_items": [
    {
      "id": "T-01",
      "name": "",
      "score": "",
      "standard": "",
      "source": "",
      "writing_focus": ""
    }
  ],
  "qualification_requirements": [
    {
      "id": "Q-01",
      "name": "",
      "requirement": "",
      "source": "",
      "required_materials": ["M-01"]
    }
  ],
  "formal_response_requirements": [
    {
      "id": "F-01",
      "name": "",
      "requirement": "",
      "source": ""
    }
  ],
  "mandatory_clauses": [
    {
      "id": "C-01",
      "clause": "",
      "source": "",
      "response_strategy": ""
    }
  ],
  "rejection_risks": [
    {
      "id": "R-01",
      "risk": "",
      "source": "",
      "mitigation": ""
    }
  ],
  "required_materials": [
    {
      "id": "M-01",
      "name": "",
      "purpose": "",
      "source": "",
      "status": "missing"
    }
  ],
  "missing_company_materials": [
    {
      "id": "X-01",
      "name": "",
      "used_by": ["Q-01", "T-01"],
      "placeholder": "【待补充：...】"
    }
  ]
}
```

### OutlinePlan

一级目录规划应先建立“章节到评分项/审查项”的映射。

```json
{
  "bid_mode": "technical_only",
  "outline": [
    {
      "id": "1",
      "title": "",
      "description": "",
      "scoring_item_ids": ["T-01"],
      "requirement_ids": [],
      "risk_ids": [],
      "material_ids": []
    }
  ]
}
```

### OutlineNode

二三级目录补全时不要只补标题和描述，还要继承或细分映射关系。

```json
{
  "id": "1",
  "title": "",
  "description": "",
  "scoring_item_ids": ["T-01"],
  "requirement_ids": [],
  "risk_ids": [],
  "material_ids": [],
  "children": [
    {
      "id": "1.1",
      "title": "",
      "description": "",
      "scoring_item_ids": ["T-01"],
      "requirement_ids": [],
      "risk_ids": [],
      "material_ids": [],
      "children": [
        {
          "id": "1.1.1",
          "title": "",
          "description": "",
          "scoring_item_ids": ["T-01"],
          "requirement_ids": [],
          "risk_ids": [],
          "material_ids": []
        }
      ]
    }
  ]
}
```

### ChapterGenerationContext

正文生成时应传入结构化上下文，而不是只传自然语言项目概述。

```json
{
  "bid_mode": "technical_only",
  "analysis_report": {},
  "chapter": {},
  "parent_chapters": [],
  "sibling_chapters": [],
  "generated_summaries": [
    {
      "chapter_id": "1.1.1",
      "summary": ""
    }
  ],
  "enterprise_materials": [],
  "missing_materials": []
}
```

### ReviewReport

导出前审校应返回机器可读结果。

```json
{
  "coverage": [
    {
      "item_id": "T-01",
      "covered": true,
      "chapter_ids": ["1.1.1"],
      "issue": ""
    }
  ],
  "missing_materials": [
    {
      "material_id": "M-01",
      "chapter_ids": ["2.1.1"],
      "placeholder": "【待补充：...】"
    }
  ],
  "rejection_risks": [
    {
      "risk_id": "R-01",
      "handled": false,
      "issue": ""
    }
  ],
  "duplication_issues": [
    {
      "chapter_ids": ["1.2.1", "1.3.1"],
      "issue": ""
    }
  ],
  "fabrication_risks": [
    {
      "chapter_id": "3.1.1",
      "text": "",
      "reason": ""
    }
  ],
  "fixed_format_issues": [],
  "signature_issues": [],
  "price_rule_issues": [],
  "evidence_chain_issues": [],
  "page_reference_issues": [],
  "summary": {
    "ready_to_export": false,
    "blocking_issues": 0,
    "warnings": 0
  }
}
```

审校阶段必须覆盖以下模板规则：

- 固定格式表、报价表、费用明细表、承诺函、偏离表不得擅自改表头、列名、固定文字、行列数量。
- 签字盖章位置、签署主体、印章要求不得遗漏。
- 报价方式、税率、小数位、唯一报价、算术修正和缺漏项处理必须满足招标文件。
- 业绩、项目负责人业绩、社保、退休返聘、发票、税务查验、信用截图、保证金凭证等证据链必须闭环。
- 未最终排版前，响应页码/投标文件页码应统一使用 `【页码待编排】`。
- 任何未提供或无法核实的信息不得写成“满足”，必须保留待补或待确认占位。

## Prompt 模板建议

### 1. AnalysisReport Prompt

目的：从招标文件全文一次性生成结构化解析报告。

关键要求：

- 只输出 JSON。
- 保留原文出处。
- 不编造缺失信息。
- 明确区分技术、资格、商务、形式、否决风险和证明材料。
- 输出 `bid_mode_recommendation`。

推荐 system prompt 要点：

```text
你是专业招标文件解析专家。你的任务是把招标文件解析为可供后续目录生成、正文生成和合规检查复用的 AnalysisReport JSON。

要求：
1. 只输出合法 JSON，不输出 markdown 代码块。
2. 所有条目必须尽量标注 source。
3. 未提及的信息填空字符串或空数组，不得猜测。
4. 企业资料缺失时只登记 missing_company_materials，不得虚构企业信息。
5. 根据输入内容判断 bid_mode_recommendation 为 technical_only 或 full_bid。
```

### 2. OutlinePlan Prompt

目的：生成一级目录，同时建立映射。

关键要求：

- `technical_only` 只围绕技术标和技术评分项。
- `full_bid` 覆盖资格、商务、报价、技术、承诺、附件等完整结构。
- 每个一级节点必须有映射字段。

### 3. OutlineNode Prompt

目的：并发补全某个一级章节下的二三级目录。

关键要求：

- 输入当前一级节点 JSON 骨架。
- 禁止修改一级节点 id 和 title。
- 必须参考 `other_outline` 避免重复。
- description 写清写作内容、评分/审查点和材料需求。

### 4. ChapterContent Prompt

目的：为叶子节点生成正文。

关键要求：

- 只输出正文，不输出标题。
- 必须使用 `AnalysisReport` 和当前节点映射字段。
- 对缺失企业资料使用 `【待补充：资料名称】`。
- 对证明材料类章节输出“材料清单 + 核验要点”，不要写空泛正文。
- 对技术方案类章节围绕评分点展开。
- 不得使用“作为 AI”“以下内容”等元话术。

### 5. ComplianceCheck Prompt

目的：导出前检查。

关键要求：

- 输出 `ReviewReport JSON`。
- 检查评分项、审查项、否决风险、证明材料、重复内容和虚构风险。
- `ready_to_export=false` 时必须给出阻塞原因。

## 推荐代码改造顺序

### Step 1：新增文档与数据契约

先引入本文档，不改业务行为。

### Step 2：新增 Pydantic/TypeScript 类型

建议新增或扩展：

- `AnalysisReport`
- `BidMode`
- `ScoringItem`
- `RequirementItem`
- `RequiredMaterial`
- `ReviewReport`
- `OutlineItem` 映射字段

风险：会影响前后端接口，需要同步更新 `frontend/src/services/api.ts` 和 `frontend/src/types/index.ts`。

### Step 3：新增结构化解析接口

新增或替换：

```text
POST /api/document/analyze-report-stream
```

输出 `AnalysisReport JSON`。保留现有 overview/requirements 接口作为兼容路径。

### Step 4：目录生成改用 AnalysisReport

让 `generate_outline_v2()` 接收 `AnalysisReport` 和 `bid_mode`，而不是 `overview + requirements` 两段自然语言。

### Step 5：正文生成传入完整上下文

扩展 `ChapterContentRequest`，加入：

- `analysis_report`
- `bid_mode`
- `generated_summaries`
- `enterprise_materials`
- `missing_materials`

### Step 6：增加合规审校接口

新增：

```text
POST /api/review/compliance-stream
```

生成 `ReviewReport JSON`，前端在导出前提示阻塞问题或警告。

### Step 7：逐步迁移 UI

前端从：

```text
项目概述 + 技术评分要求
```

逐步迁移为：

```text
AnalysisReport + OutlinePlan + ReviewReport
```

保留旧字段用于展示和兼容。

## 验证策略

### 文档级验证

- 确认本文档覆盖当前所有 prompt 入口。
- 确认每个阶段都有输入、输出和失败处理。

### 单元/脚本验证

- 对 JSON 提取和 `check_json` 做样例验证。
- 准备一个伪造招标文件文本，验证 `AnalysisReport` schema。
- 准备一个带代码块包裹、前后说明文字的模型输出，验证 JSON 提取。

### 集成验证

- 使用同一份样例招标文件跑完整链路。
- 检查所有技术评分项是否被至少一个目录节点覆盖。
- 检查正文中的 `【待补充：...】` 是否来自 `missing_company_materials`。
- 导出前运行 `ReviewReport`，确认阻塞项能展示给用户。

## 第一批可执行改造任务

建议拆成以下 Trellis 子任务：

1. `define-analysis-report-schema`
   - 新增后端 Pydantic 和前端 TypeScript 类型。
2. `add-analysis-report-endpoint`
   - 新增结构化解析接口，保留旧接口。
3. `map-outline-to-requirements`
   - 扩展目录节点映射字段。
4. `pass-analysis-report-to-chapter-generation`
   - 正文生成使用完整上下文。
5. `add-compliance-review-step`
   - 增加导出前审校接口和 UI。

## 近期建议

不要一次性重写全部 prompt 和接口。推荐先完成：

1. 新增 `AnalysisReport` schema。
2. 新增结构化解析接口。
3. 在目录生成阶段优先使用 `AnalysisReport`。

这三步完成后，当前“标准解析报告只存在于模型内部”的最大可靠性问题就能消除。
