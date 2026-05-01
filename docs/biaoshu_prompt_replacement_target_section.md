# biaoshu 提示词替换包说明

本包用于直接覆盖项目中的三个后端文件：

```text
backend/app/utils/prompt_manager.py
backend/app/services/openai_service.py
backend/app/models/schemas.py
```

## 本次重点修正

这版专门修正“招标文件里到底哪一部分才是需要生成目录和正文的投标方案内容”的问题。

系统现在会先解析招标文件中的以下位置：

- 第二章或类似章节中的“3. 投标文件”“3.1 投标文件的组成”“3.1.1 投标文件应包括下列内容”；
- 第六章或类似章节中的“投标文件格式”“投标文件编制格式说明”；
- 其中的“服务方案”“设计方案”“技术方案”“实施方案”“施工组织设计”“供货方案”“售后服务方案”等方案类章节；
- 第三章评标办法中的技术/服务详细评分项；
- 第五章发包人要求/招标人要求/采购需求中的服务范围、质量、进度、安全、保密、交付等实质性要求。

新增核心字段：

```python
AnalysisReport.bid_document_requirements.selected_generation_target
```

它用于告诉后续目录生成和正文生成：本次到底应该基于哪个投标文件组成项来写。例如：

- 辽宁销售样例：识别第六章“七、服务方案”为生成对象，目录基于“服务方案”要求生成，而不是生成整本投标文件；
- 长庆样例：识别“3.1.1（7）设计方案”为投标文件组成项，同时结合第六章“六、设计方案”中的“设计方案应包括……”十项内容生成目录。

## 目录生成优先级

当生成技术/服务/方案分册时，目录标题依据以下优先级生成：

1. `selected_generation_target.base_outline_items`，即招标文件投标格式中明确要求的方案子项；
2. `bid_document_requirements.scheme_or_technical_outline_requirements`；
3. 第三章技术/服务详细评分项；
4. 用户提供的成熟投标文件样例风格；
5. 通用服务/技术方案保底目录。

这意味着样例文件只提供写作深度、结构风格、表格/承诺/图片位置参考，不会覆盖招标文件中的投标文件格式要求。

## 已接入的 7 个 Prompt

1. 目标投标文件样例解析：`generate_reference_bid_style_profile_prompt()`；
2. 招标文件解析：`generate_analysis_report_prompt()`，新增 selected_generation_target；
3. 响应矩阵：`generate_response_matrix_prompt()`；
4. 目录生成：`generate_level1_outline_prompt()` 和 `generate_level23_outline_prompt()`；
5. 章节正文生成：`generate_chapter_content_prompt()`；
6. 图表与素材规划：`generate_document_blocks_prompt()`；
7. 全文一致性修订/导出前审校：`generate_consistency_revision_prompt()` 和 `generate_compliance_review_prompt()`。

## 使用方式

将压缩包中的文件覆盖到项目对应路径后，重启后端服务。

如果前端未显式传 `full_bid`，系统在识别到“服务方案/设计方案/技术方案”等方案类生成对象时，会默认优先生成该方案分册，而不是整本投标文件。
