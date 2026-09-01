import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import fs from "node:fs/promises";

const file = process.argv[2];
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const sheetList = await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 4000 });
const tableHead = await wb.inspect({ kind: "table", range: "体验问卷大表!A1:P18", include: "values,formulas", tableMaxRows: 18, tableMaxCols: 16, maxChars: 16000 });
const sigHead = await wb.inspect({ kind: "table", range: "体验问卷显著性检验!A1:P18", include: "values,formulas", tableMaxRows: 18, tableMaxCols: 16, maxChars: 16000 });
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan", maxChars: 6000 });
if (process.argv[3] && process.argv[3] !== "--compact") {
  const rendered = await wb.render({ sheetName: "体验问卷显著性检验", range: "A1:P40", scale: 1.2, format: "png" });
  await fs.writeFile(process.argv[3], new Uint8Array(await rendered.arrayBuffer()));
}
if (process.argv.includes("--compact")) {
  const requiredSheets = ["Index", "体验问卷大表", "体验问卷显著性检验", "说明", "变量映射", "数据质量"];
  process.stdout.write(JSON.stringify({
    requiredSheetsPresent: requiredSheets.every(name => sheetList.ndjson.includes(`"name":"${name}"`) || sheetList.ndjson.includes(`"name": "${name}"`)),
    tableTitlePresent: tableHead.ndjson.includes("频率表"),
    significanceTitlePresent: sigHead.ndjson.includes("显著性检验"),
    errorScan: errors.ndjson,
  }, null, 2));
} else {
  process.stdout.write(JSON.stringify({
    sheets: sheetList.ndjson,
    tableHead: tableHead.ndjson,
    sigHead: sigHead.ndjson,
    errors: errors.ndjson,
  }, null, 2));
}
