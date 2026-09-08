# QuestionStar Research Crosstabs

面向问卷星及问卷导出数据的 Codex Skill，用于生成中文研究频率表、交叉表和显著性检验工作簿。

## 主要能力

- 问卷数据清洗与跨问卷样本关联
- 问卷原生分组和业务标签分群
- 单选、多选、评分、矩阵、排序和 NPS 题处理
- Mean、T2B、B2B 与列比例显著性检验
- 可选的 Total 降序版本；默认保留问卷选项原始顺序
- MDNF 风格 Excel 排版和 Index 题目跳转链接
- 数据、结构、公式与输出质量校验
- 可切换分组族的指标概览、原生横向 T2B/NPS 图和评分分布图
- 稳定匿名 ID 关联、清洗原因记录、矩阵逐行有效基数、反向/非评分映射
- 两张主表保留数值单元格，精度统一，附低基数/定义性分组标记

## 运行项目（v2）

```bash
python scripts/run_project.py --source /path/to/source \
  --config /path/to/project.json --output-dir /path/to/new-version \
  --node /path/to/bundled/node
```

默认不排序，显著性保留双侧 p < 0.10。明确需要排序版时加 `--sorted`。详细配置、清洗、业务优先级和跨问卷关联见 [项目工作流](references/project-workflow.md)。源数据必须符合问卷结构/答卷 JSON 格式；Excel 导出需要先按问卷映射。Python 需要 NumPy，Excel 生成需要 Codex 电子表格运行环境中的 `@oai/artifact-tool`。

每次生成新版本目录，输出工作簿、口径配置、清洗记录、校验回执和数据/代码版本指纹。缺少关联 ID、重复关联键、错误数值或导出验证失败会中止。

```bash
python -m unittest discover -s tests -v
```

## 安装

将仓库克隆到 Codex 的个人 Skills 目录：

```bash
git clone https://github.com/fivehang1996-lab/questionstar-research-crosstabs.git \
  ~/.codex/skills/questionstar-research-crosstabs
```

重新打开 Codex 任务后，可以在请求中使用：

```text
使用 $questionstar-research-crosstabs 清洗问卷数据并生成交叉数表。
```

完整工作流、输出要求和脚本说明见 [SKILL.md](SKILL.md)。配置示例见 [references/project-config.example.json](references/project-config.example.json)。

## 完整案例

[合成游戏体验问卷案例](examples/synthetic-game-survey/README.md)覆盖 180 名合成玩家、原生分组、指标分层、显著性检验、Mean、T2B/B2B、NPS、矩阵题、排序题和 Index 超链接。仓库内同时提供输入、配置、校验回执、预览图和最终 Excel，可用于快速理解或回归测试。

## 安全说明

- 问卷星 API Key 只通过环境变量提供，禁止写入配置、日志或输出文件。
- 原始问卷数据、Excel 输出、环境文件和运行缓存已加入 `.gitignore`。
- 题号、样本量、选项和业务分群必须按当前项目重新映射，不跨项目硬编码复用。
- 拉取时另需环境变量 `WJX_ID_SALT`；需要跨问卷关联时，配置经过核实的 `WJX_LINKAGE_FIELD`。所有开放题按题型处理，不再依赖固定题号。
