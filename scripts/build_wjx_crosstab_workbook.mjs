import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const analysisPath = process.argv[2];
const outputPath = process.argv[3];
const previewDir = process.argv[4];
if (!analysisPath || !outputPath || !previewDir) {
  throw new Error("Usage: build_wjx_crosstab_workbook.mjs <analysis.json> <output.xlsx> <previewDir>");
}

const data = JSON.parse(await fs.readFile(analysisPath, "utf8"));
const groups = data.groups;
const rows = data.rows;
const quality = data.quality;

function colName(n) {
  let result = "";
  for (let x = n; x > 0; x = Math.floor((x - 1) / 26)) {
    result = String.fromCharCode(65 + ((x - 1) % 26)) + result;
  }
  return result;
}

function typeLabel(q) {
  if (data.metadata?.nps_question === q.q_index || q.q_subtype === 302) return "NPS/量表题";
  if (q.q_type === 7) return "矩阵题";
  if (q.q_subtype === 402) return "排序题";
  if (q.q_type === 4 && q.q_subtype === 4) return "多选题";
  if (q.q_type === 3 && q.q_subtype === 302) return "量表题";
  if (q.q_type === 3) return q.q_index === 4 ? "评分单选题" : "单选题";
  if (q.q_type === 5) return "开放填空题";
  return `${q.q_type}/${q.q_subtype}`;
}

function indicatorLabel(qIndex) {
  return data.metadata?.indicator_labels?.[String(qIndex)] || data.metadata?.indicator_labels?.[qIndex] || typeLabel(data.questions.find(q => q.q_index === qIndex) || {});
}

function familyDisplay(family) {
  return data.metadata?.family_display?.[family] || family;
}

const wb = Workbook.create();
const index = wb.worksheets.add("Index");
const info = wb.worksheets.add("说明");
const table = wb.worksheets.add("体验问卷大表");
const sig = wb.worksheets.add("体验问卷显著性检验");
const mapping = wb.worksheets.add("变量映射");
const qa = wb.worksheets.add("数据质量");

const navy = "#17365D";
const blue = "#2F75B5";
const teal = "#2A7F8E";
const headerText = "#FFFFFF";
const lightBlue = "#DDEBF7";
const lightGray = "#F2F2F2";
const line = "#D9E2F3";
const purple = "#7030A0";
const yellow = "#FFF2CC";
const peach = "#FCE4D6";
const cyan = "#D9EAF0";
const cyanStrong = "#A9D2DC";
const tableBorder = "#404040";

function titleBand(sheet, title, subtitle, lastCol, mergeEnd = lastCol) {
  sheet.mergeCells(`A1:${mergeEnd}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: navy,
    font: { bold: true, color: headerText, size: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1").format.horizontalAlignment = "left";
  sheet.getRange("1:1").format.rowHeight = 30;
  sheet.mergeCells(`A2:${mergeEnd}2`);
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: "#EAF2F8",
    font: { color: "#44546A", italic: true, size: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("2:2").format.rowHeight = 38;
}

function familyColor(index) {
  const palette = ["#2F75B5", "#2A7F8E", "#5B6F95", "#7F6000", "#548235", "#8064A2", "#3F6F8F", "#A64D79", "#476B6B", "#5B7F95"];
  return palette[index % palette.length];
}

function formatDisplay(cell, kind, withSig) {
  if (cell.value === null || cell.value === undefined) return "–";
  let base;
  if (kind === "total") base = String(Math.round(cell.value));
  else if (kind === "percent" || kind === "matrix_percent") base = `${Math.round(cell.value * 100)}%`;
  else if (kind === "nps") base = String(Math.round(cell.value));
  else base = Number(cell.value).toFixed(2);
  return withSig && cell.sig_high?.length ? `${base} ${cell.sig_high.join("、")}` : base;
}

function buildTableSheet(sheet, significance) {
  const firstDataCol = 2;
  const lastColNumber = 1 + groups.length;
  const lastCol = colName(lastColNumber);
  const blocks = [];
  for (const row of rows) {
    let block = blocks.at(-1);
    if (!block || block.q_index !== row.q_index) {
      block = { q_index: row.q_index, question: row.question, rows: [] };
      blocks.push(block);
    }
    block.rows.push(row);
  }

  const sortSuffix = data.metadata.sort_mode === "explicit_total_descending" ? "_Total排序版" : "";
  sheet.getRange("A1").values = [[`${data.metadata.title}_${significance ? "显著性检验" : "频率表"}${sortSuffix}`]];
  sheet.getRange("A1").format = { font: { name: "Calibri", size: 12, bold: true, color: blue }, verticalAlignment: "middle" };
  sheet.getRange("1:1").format.rowHeight = 24;
  const questionStarts = [];
  let cursor = 3;

  for (const block of blocks) {
    const totalRow = block.rows.find(r => r.kind === "total");
    const statRows = block.rows.filter(r => r.kind !== "total");
    const metricRow = cursor;
    const familyRow = cursor + 1;
    const labelRow = cursor + 2;
    const baseRow = cursor + 3;
    const questionRow = cursor + 4;
    questionStarts.push({ q_index: block.q_index, question: block.question, row: questionRow });

    sheet.mergeCells(`A${metricRow}:${lastCol}${metricRow}`);
    sheet.getRange(`A${metricRow}`).values = [[`指标标签：${indicatorLabel(block.q_index)}`]];
    sheet.getRange(`A${metricRow}:${lastCol}${metricRow}`).format = {
      fill: lightBlue,
      font: { name: "Calibri", size: 10, bold: true, color: navy },
      horizontalAlignment: "left",
      verticalAlignment: "center",
      wrapText: true,
      borders: { preset: "all", style: "thin", color: tableBorder },
    };

    sheet.getRange(`A${familyRow}:${lastCol}${labelRow}`).format = {
      fill: peach,
      font: { name: "Calibri", size: 9, color: "#222222" },
      horizontalAlignment: "center",
      verticalAlignment: "center",
      wrapText: true,
      borders: { preset: "all", style: "thin", color: tableBorder },
    };
    sheet.getRange(`A${familyRow}:A${labelRow}`).values = [["分组"], ["指标"]];

    let start = 0;
    while (start < groups.length) {
      const family = groups[start].family;
      let end = start;
      while (end + 1 < groups.length && groups[end + 1].family === family) end += 1;
      const c1 = colName(firstDataCol + start);
      const c2 = colName(firstDataCol + end);
      if (c1 !== c2) sheet.mergeCells(`${c1}${familyRow}:${c2}${familyRow}`);
      sheet.getRange(`${c1}${familyRow}`).values = [[family === "总体" ? "" : familyDisplay(family)]];
      start = end + 1;
    }
    sheet.getRange(`B${labelRow}:${lastCol}${labelRow}`).values = [groups.map(g => {
      const label = g.family === "总体" ? "Total" : g.label;
      return significance && g.letter ? `${label} (${g.letter})` : label;
    })];

    const baseValues = totalRow ? totalRow.cells.map(c => c.value ?? "-") : groups.map(() => "-");
    sheet.getRange(`A${baseRow}:${lastCol}${baseRow}`).values = [["基数（n）: 所有回答该题的被访者", ...baseValues]];
    sheet.getRange(`A${baseRow}:${lastCol}${baseRow}`).format = {
      font: { name: "Calibri", size: 9, italic: false, color: "#333333" },
      horizontalAlignment: "center",
      verticalAlignment: "center",
      borders: { preset: "all", style: "thin", color: tableBorder },
    };
    sheet.getRange(`B${baseRow}:${lastCol}${baseRow}`).format.numberFormat = "#,##0";

    sheet.getRange(`A${questionRow}:${lastCol}${questionRow}`).format = {
      font: { name: "Calibri", size: 9, bold: true, color: "#0070C0" },
      verticalAlignment: "middle",
      borders: { preset: "all", style: "thin", color: tableBorder },
    };
    sheet.getRange(`A${questionRow}`).values = [[`[Q${block.q_index}].${block.question.replace(/^Q\d+\.\s*/, "")}`]];

    let dataRow = questionRow + 1;
    for (const row of statRows) {
      const label = row.item || (row.kind === "mean" ? "Mean" : row.kind === "nps" ? "NPS" : row.metric);
      const values = row.cells.map(cell => significance ? formatDisplay(cell, row.kind, true) : cell.value);
      sheet.getRange(`A${dataRow}:${lastCol}${dataRow}`).values = [[label, ...values]];
      sheet.getRange(`A${dataRow}:${lastCol}${dataRow}`).format = {
        font: { name: "Calibri", size: 9, color: "#222222" },
        horizontalAlignment: "center",
        verticalAlignment: "center",
        borders: { preset: "all", style: "thin", color: tableBorder },
      };
      if (!significance) {
        const dataRange = sheet.getRange(`B${dataRow}:${lastCol}${dataRow}`);
        if (row.kind === "percent" || row.kind === "matrix_percent") dataRange.format.numberFormat = "0.0%";
        else if (row.kind === "mean" || row.kind === "rank_mean") dataRange.format.numberFormat = "0.0";
        else if (row.kind === "nps") dataRange.format.numberFormat = "0";
      }
      for (let j = 0; j < row.cells.length; j += 1) {
        const cell = row.cells[j];
        const address = `${colName(firstDataCol + j)}${dataRow}`;
        if (!significance && cell.sig_high?.length) {
          sheet.getRange(address).format.fill = cell.sig_high.length >= 2 ? cyanStrong : cyan;
          sheet.getRange(address).format.font = { name: "Calibri", size: 9, bold: cell.sig_high.length >= 2, color: "#222222" };
        } else if (significance && cell.sig_high?.length) {
          sheet.getRange(address).format.font = { name: "Calibri", size: 9, color: purple, bold: true };
        } else if (significance && cell.sig_low_all) {
          sheet.getRange(address).format.font = { name: "Calibri", size: 9, color: "#9C6500", bold: true };
          sheet.getRange(address).format.fill = yellow;
        }
      }
      dataRow += 1;
    }

    const percentRows = statRows.filter(r => r.kind === "percent" && !String(r.item || "").startsWith("【指标】"));
    if (percentRows.length) {
      sheet.getRange(`A${dataRow}:${lastCol}${dataRow}`).values = [["---", ...groups.map(() => "---")]];
      sheet.getRange(`A${dataRow}:${lastCol}${dataRow}`).format = {
        font: { name: "Calibri", size: 9, color: "#666666" }, horizontalAlignment: "center",
        borders: { preset: "all", style: "thin", color: tableBorder },
      };
      dataRow += 1;
      const totals = groups.map((_, j) => percentRows.reduce((sum, r) => sum + (Number(r.cells[j]?.value) || 0), 0));
      sheet.getRange(`A${dataRow}:${lastCol}${dataRow}`).values = [["Total", ...totals]];
      sheet.getRange(`A${dataRow}:${lastCol}${dataRow}`).format = {
        font: { name: "Calibri", size: 9, color: "#222222" }, horizontalAlignment: "center",
        borders: { preset: "all", style: "thin", color: tableBorder },
      };
      sheet.getRange(`B${dataRow}:${lastCol}${dataRow}`).format.numberFormat = "0.0%";
      dataRow += 1;
    }

    cursor = dataRow + 2;
  }

  const endRow = Math.max(1, cursor - 2);
  sheet.getRange(`A:A`).format.columnWidth = 100;
  sheet.getRange(`B:B`).format.columnWidth = 12;
  if (lastColNumber >= 3) sheet.getRange(`C:${lastCol}`).format.columnWidth = 10;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  sheet.showGridLines = false;
  return { endRow, lastCol, questionStarts };
}

const tableBounds = buildTableSheet(table, false);
const sigBounds = buildTableSheet(sig, true);

index.getRange("A1:B1").values = [["体验问卷大表", "体验问卷显著性检验"]];
index.getRange("A1:B1").format = {
  fill: peach,
  font: { name: "Microsoft YaHei", size: 9, bold: true, color: "#222222" },
  borders: { preset: "all", style: "thin", color: tableBorder },
};
const indexRows = tableBounds.questionStarts.map((entry) => {
  const text = `[Q${entry.q_index}].${entry.question.replace(/^Q\d+\.\s*/, "")}`;
  return {
    tableText: text,
    sigText: text,
  };
});
if (indexRows.length) {
  index.getRange(`A2:A${1 + indexRows.length}`).values = indexRows.map(r => [r.tableText]);
  index.getRange(`B2:B${1 + indexRows.length}`).values = indexRows.map(r => [r.sigText]);
  index.getRange(`A2:B${1 + indexRows.length}`).format = {
    font: { name: "Microsoft YaHei", size: 9, color: "#0070C0", underline: true },
    wrapText: true,
    borders: { preset: "all", style: "thin", color: tableBorder },
  };
}
index.getRange("A:B").format.columnWidth = 100;
index.freezePanes.freezeRows(1);
index.showGridLines = false;

titleBand(info, `${data.metadata.title}｜数表说明`, data.metadata.subtitle || "用于测试问卷星直连、原生分组交叉表和显著性检验流程。", "H");
const infoRows = [
  ["项目", "内容", "说明"],
  ["问卷 ID", String(quality.vid), quality.source_receipt?.source_note || "问卷星 OpenAPI 只读获取"],
  ["总回收样本", quality.source_receipt?.answer_total ?? quality.answer_total, "后台 answer_total"],
  ["原始有效样本", quality.source_receipt?.answer_valid ?? quality.answer_valid, "接口 valid=true 返回的答卷"],
  ["本次清洗剔除", Math.max(0, (quality.source_receipt?.answer_valid ?? quality.answer_valid) - quality.answer_valid), "未进入分析的有效答卷"],
  ["清洗后有效样本", quality.answer_valid, "进入本次数表分析的答卷"],
  ["外部标签匹配", quality.linkage ? `${quality.linkage.matched}/${quality.linkage.target_total}（${(quality.linkage.coverage * 100).toFixed(1)}%）` : "不适用", quality.linkage ? "未匹配样本保留在 Total、排除于对应标签分组" : "未使用外部标签"],
  ["显著性水平", `双侧 p < ${data.metadata.alpha ?? 0.10}`, "比例使用原始人数/基数；均值、NPS、平均名次使用 Welch 检验"],
  ["NPS 编码", "原生 0–10", "0–6 批评者，7–8 中立者，9–10 推荐者；NPS 不带百分号"],
  ["多选缺失", data.metadata.multi_select_missing_note || "-3=未展示/跳题", "问卷已作答时，未被选择的选项按 0 计入分母"],
  ["矩阵/排序题", "按实际题型处理", "矩阵逐行统计；排序题输出入选率和平均名次"],
  ["开放题", "仅保留实际填答样本量", "默认不传播开放文本正文"],
  ["分组口径", data.metadata.scope || "配置驱动", quality.group_scope || "总体"],
  ["T2B/B2B", data.metadata.box_metrics?.enabled ? `已启用：${data.metadata.box_metrics.questions.map(q => `Q${q}`).join("、")}` : "未启用", "T2B=最高两档，B2B=最低两档；使用原始人数和有效基数"],
  ["选项排序", quality.sorting?.enabled ? "已启用：Total 降序" : "未启用", quality.sorting?.enabled ? `排序题目：${(quality.sorting.sorted_questions || []).map(q => `Q${q}`).join("、") || "无"}；有序题保留问卷原顺序` : "默认保留问卷原选项顺序"],
  ["重要限制", data.metadata.overlap_warning === false ? "当前配置无重叠分组" : "经历标签可重叠", data.metadata.overlap_warning === false ? "原生分组和指标分层在各自分组族内互斥" : "按引导词执行独立样本检验；重叠人群结果应作为探索性信号解释"],
  ["最小样本阈值", data.metadata.minimum_base_note || "未设置", "低基数组合需谨慎解释"],
  ["接口说明", "https://www.wjx.cn/help/help.aspx?catid=140", "问卷星 ApiKey 官方说明"],
];
info.getRange(`A4:C${3 + infoRows.length}`).values = infoRows;
info.getRange("A4:C4").format = { fill: blue, font: { bold: true, color: headerText }, horizontalAlignment: "center" };
info.getRange(`A4:C${3 + infoRows.length}`).format.borders = { preset: "all", style: "thin", color: line };
info.getRange(`A5:C${3 + infoRows.length}`).format.wrapText = true;
info.getRange("A:A").format.columnWidth = 22;
info.getRange("B:B").format.columnWidth = 34;
info.getRange("C:C").format.columnWidth = 72;
info.getRange(`5:${3 + infoRows.length}`).format.rowHeight = 34;
info.freezePanes.freezeRows(4);
info.showGridLines = false;

titleBand(mapping, `${data.metadata.title}｜变量映射`, data.metadata.mapping_note || "题号与题型来自问卷星实际投放结构，不沿用历史列号。", "F");
mapping.getRange("A4:F4").values = [["题号", "题干", "实际题型", "原始类型", "选项数", "处理方式"]];
mapping.getRange("A4:F4").format = { fill: blue, font: { bold: true, color: headerText }, horizontalAlignment: "center" };
const mapRows = data.questions.map(q => [
  `Q${q.q_index}`,
  q.title,
  typeLabel(q),
  `${q.q_type}/${q.q_subtype}`,
  q.item_count,
  q.q_type === 5 ? "仅统计实际填答样本量" : q.q_type === 7 ? "矩阵逐行列百分比" : q.q_subtype === 402 ? "入选率 + 平均名次" : q.q_type === 4 ? "选项列百分比" : "均值/选项列百分比（按配置）",
]);
mapping.getRange(`A5:F${4 + mapRows.length}`).values = mapRows;
mapping.getRange(`A4:F${4 + mapRows.length}`).format.borders = { preset: "all", style: "thin", color: line };
mapping.getRange(`B5:F${4 + mapRows.length}`).format.wrapText = true;
mapping.getRange("A:A").format.columnWidth = 10;
mapping.getRange("B:B").format.columnWidth = 72;
mapping.getRange("C:C").format.columnWidth = 24;
mapping.getRange("D:E").format.columnWidth = 12;
mapping.getRange("F:F").format.columnWidth = 28;
mapping.freezePanes.freezeRows(4);
mapping.showGridLines = false;

titleBand(qa, `${data.metadata.title}｜数据质量`, "用于复核样本、字段完整性、题目基数和输出规模。", "D");
const qaRows = [
  ["检查项", "结果", "状态", "说明"],
  ["有效答卷对账", `${quality.records_loaded}/${quality.answer_valid}`, quality.records_loaded === quality.answer_valid ? "通过" : "异常", "API 拉取记录数必须等于后台有效数"],
  ["匿名记录唯一性", quality.duplicate_respondent_ids, quality.duplicate_respondent_ids === 0 ? "通过" : "异常", "去标识化 respondent_id 重复数"],
  ["问卷题数", quality.question_count, "通过", "实际投放题目"],
  ["大表统计行", quality.output_row_count, "通过", "含 total、均值、选项、NPS 和排序题行"],
  ["数据列数", quality.output_column_count, "通过", "总体 + 配置分组"],
  ["T2B/B2B", data.metadata.box_metrics?.enabled ? "已校验" : "未启用", "已记录", "使用原始选项人数合并，显著性重新计算"],
  ["NPS 编码", quality.nps_encoding, "通过", "使用 item_value，不使用显示序号"],
];
if (quality.linkage) qaRows.push(["标签匹配覆盖率", `${quality.linkage.matched}/${quality.linkage.target_total}`, "已记录", `覆盖率 ${(quality.linkage.coverage * 100).toFixed(1)}%`]);
if (quality.sorting) qaRows.push(["排序规则", quality.sorting.enabled ? "Total 降序" : "未启用", "已记录", `排序题目：${(quality.sorting.sorted_questions || []).map(q => `Q${q}`).join("、") || "无"}`]);
for (const [q, n] of Object.entries(quality.question_bases)) {
  qaRows.push([`Q${q} 实际有效基数`, n, "已记录", q === "22" ? "仅统计非空开放回答" : "按该题实际有效作答计算"]);
}
qa.getRange(`A4:D${3 + qaRows.length}`).values = qaRows;
qa.getRange("A4:D4").format = { fill: blue, font: { bold: true, color: headerText }, horizontalAlignment: "center" };
qa.getRange(`A4:D${3 + qaRows.length}`).format.borders = { preset: "all", style: "thin", color: line };
qa.getRange(`A5:D${3 + qaRows.length}`).format.wrapText = true;
for (let r = 5; r <= 3 + qaRows.length; r += 1) {
  const state = qaRows[r - 4][2];
  if (state === "通过") qa.getRange(`C${r}`).format = { fill: "#E2F0D9", font: { color: "#375623", bold: true } };
  if (state === "异常") qa.getRange(`C${r}`).format = { fill: "#F4CCCC", font: { color: "#9C0006", bold: true } };
}
qa.getRange("A:A").format.columnWidth = 25;
qa.getRange("B:B").format.columnWidth = 28;
qa.getRange("C:C").format.columnWidth = 14;
qa.getRange("D:D").format.columnWidth = 58;
qa.freezePanes.freezeRows(4);
qa.showGridLines = false;

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const previews = [
  ["Index", "A1:B23", "00-index.png"],
  ["说明", "A1:H20", "01-info.png"],
  ["体验问卷大表", "A1:P40", "02-table.png"],
  ["体验问卷大表", "A41:P105", "02-table-middle.png"],
  ["体验问卷大表", "A106:P153", "02-table-late.png"],
  ["体验问卷显著性检验", "A1:P40", "03-significance.png"],
  ["体验问卷显著性检验", "A41:P105", "03-significance-middle.png"],
  ["体验问卷显著性检验", "A106:P153", "03-significance-late.png"],
  ["变量映射", "A1:F26", "04-mapping.png"],
  ["数据质量", "A1:D34", "05-quality.png"],
];
wb.recalculate();
for (const [sheetName, range, fileName] of previews) {
  const blob = await wb.render({ sheetName, range, scale: 1.2, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await blob.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(outputPath);
const linkScript = fileURLToPath(new URL("./add_internal_index_links.py", import.meta.url));
execFileSync(process.env.WJX_PYTHON_PATH || "python3", [linkScript, analysisPath, outputPath], {
  encoding: "utf8",
  maxBuffer: 8 * 1024 * 1024,
});

const checks = {
  outputPath,
  sheets: 6,
  table: tableBounds,
  significance: sigBounds,
  rows: rows.length,
  groupColumns: groups.length,
};
process.stdout.write(`${JSON.stringify(checks, null, 2)}\n`);
