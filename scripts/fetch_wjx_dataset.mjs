import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";

const vid = Number(process.argv[2]);
const outDir = process.argv[3];
const cliPath = process.env.WJX_CLI_PATH;
const nodePath = process.env.WJX_NODE_PATH;

if (!vid || !outDir || !cliPath || !nodePath || !process.env.WJX_API_KEY) {
  throw new Error("Usage: WJX_API_KEY=... WJX_CLI_PATH=... WJX_NODE_PATH=... fetch_wjx_dataset.mjs <vid> <outDir>");
}

function runCli(args) {
  const stdout = execFileSync(nodePath, [cliPath, ...args], {
    encoding: "utf8",
    env: process.env,
    maxBuffer: 256 * 1024 * 1024,
  });
  const parsed = JSON.parse(stdout);
  if (!parsed.result) throw new Error(JSON.stringify(parsed));
  return parsed.data;
}

await fs.mkdir(outDir, { recursive: true });

const survey = runCli([
  "survey", "get", "--vid", String(vid),
  "--get_questions", "--get_items", "--get_exts", "--get_setting",
  "--get_page_cut", "--get_tags",
]);

const first = runCli([
  "response", "query", "--vid", String(vid),
  "--page_index", "1", "--page_size", "500",
]);

const total = Number(first.total_count || first.join_times || 0);
// The OpenAPI currently caps returned records at 100 even when a larger
// page_size is requested, so derive the effective size from the first page.
const pageSize = Math.max(1, Object.keys(first.answers || {}).length);
const pageCount = Math.ceil(total / pageSize);
const rawPages = [first];
for (let page = 2; page <= pageCount; page += 1) {
  rawPages.push(runCli([
    "response", "query", "--vid", String(vid),
    "--page_index", String(page), "--page_size", String(pageSize),
  ]));
}

const records = [];
for (const page of rawPages) {
  for (const raw of Object.values(page.answers || {})) {
    const answerItems = {};
    for (const [answerId, item] of Object.entries(raw.answer_items || {})) {
      const qIndex = Number(item.q_index || 0);
      const copy = {
        q_index: qIndex,
        q_row: Number(item.q_row || 0),
        q_column: Number(item.q_column || 0),
        item_index: Array.isArray(item.item_index) ? item.item_index.map(Number) : [],
        item_value: item.item_value ?? null,
      };
      // Keep categorical labels and city only. Drop open-text response bodies.
      if (qIndex !== 22) copy.answer_text = item.answer_text ?? "";
      else copy.answered = Boolean(item.answer_text && item.answer_text !== "(空)");
      answerItems[answerId] = copy;
    }
    records.push({
      respondent_id: records.length + 1,
      submit_time: raw.submit_time,
      answer_seconds: raw.answer_seconds,
      source: raw.source,
      province: raw.province,
      city: raw.city,
      answer_items: answerItems,
    });
  }
}

const receipt = {
  vid,
  title: survey.title,
  fetched_at: new Date().toISOString(),
  answer_total: survey.answer_total,
  answer_valid: survey.answer_valid,
  api_valid_records: records.length,
  page_count: pageCount,
  pii_policy: "source_ip/source_detail/jid/answerer removed; Q22 text body removed",
};

await fs.writeFile(`${outDir}/survey.json`, JSON.stringify(survey, null, 2));
await fs.writeFile(`${outDir}/responses.deidentified.json`, JSON.stringify(records));
await fs.writeFile(`${outDir}/fetch-receipt.json`, JSON.stringify(receipt, null, 2));
process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
