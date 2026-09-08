import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";

const vid = Number(process.argv[2]);
const outDir = process.argv[3];
const cliPath = process.env.WJX_CLI_PATH;
const nodePath = process.env.WJX_NODE_PATH;
const idSalt = process.env.WJX_ID_SALT;

if (!vid || !outDir || !cliPath || !nodePath || !process.env.WJX_API_KEY || !idSalt) {
  throw new Error("Set WJX_API_KEY, WJX_ID_SALT, WJX_CLI_PATH and WJX_NODE_PATH before fetching <vid> <outDir>.");
}
const anonymous = value => createHmac('sha256', idSalt).update(String(value)).digest('hex');

function runCli(args) {
  const stdout = execFileSync(nodePath, [cliPath, ...args], {
    encoding: "utf8",
    env: process.env,
    maxBuffer: 256 * 1024 * 1024,
  });
  const parsed = JSON.parse(stdout);
  if (!parsed.result) throw new Error('QuestionStar request failed; no response body logged');
  return parsed.data;
}

await fs.mkdir(outDir, { recursive: true });
if ((await fs.readdir(outDir)).length) throw new Error('Output directory must be empty; never overwrite an earlier source snapshot');

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

const questionTypes = new Map((survey.questions || []).map(q => [Number(q.q_index), Number(q.q_type)]));
const records = [];
const seen = new Set();
for (const page of rawPages) {
  for (const [responseKey, raw] of Object.entries(page.answers || {})) {
    const nativeId = raw.jid ?? raw.joinid ?? responseKey;
    const respondentId = anonymous(`${vid}:${nativeId}`);
    if (seen.has(respondentId)) throw new Error('Duplicate response across API pages; rerun with a stable source snapshot');
    seen.add(respondentId);
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
      // Never export response text. Categorical labels come from survey metadata.
      if (questionTypes.get(qIndex) === 5) {
        copy.answered = Boolean(item.answer_text && String(item.answer_text).trim() && item.answer_text !== '(空)');
        copy.item_value = null;
      }
      answerItems[answerId] = copy;
    }
    records.push({
      respondent_id: respondentId,
      ...(process.env.WJX_LINKAGE_FIELD && raw[process.env.WJX_LINKAGE_FIELD] != null
        ? { linkage_key: anonymous(`link:${String(raw[process.env.WJX_LINKAGE_FIELD]).trim()}`) } : {}),
      submit_time: raw.submit_time,
      answer_seconds: raw.answer_seconds,
      source: raw.source,
      province: raw.province,
      city: raw.city,
      answer_items: answerItems,
    });
  }
}

if (records.length !== total) throw new Error(`Incomplete pagination: expected ${total}, received ${records.length}`);
const receipt = {
  vid,
  title: survey.title,
  fetched_at: new Date().toISOString(),
  answer_total: survey.answer_total,
  answer_valid: survey.answer_valid,
  api_valid_records: records.length,
  expected_records: total,
  page_count: pageCount,
  pii_policy: "Direct identifiers and answer text removed; IDs use project-scoped HMAC; linkage field only when configured",
};

await fs.writeFile(`${outDir}/survey.json`, JSON.stringify(survey, null, 2));
await fs.writeFile(`${outDir}/responses.deidentified.json`, JSON.stringify(records));
await fs.writeFile(`${outDir}/fetch-receipt.json`, JSON.stringify(receipt, null, 2));
process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
