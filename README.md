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

## 安全说明

- 问卷星 API Key 只通过环境变量提供，禁止写入配置、日志或输出文件。
- 原始问卷数据、Excel 输出、环境文件和运行缓存已加入 `.gitignore`。
- 题号、样本量、选项和业务分群必须按当前项目重新映射，不跨项目硬编码复用。
