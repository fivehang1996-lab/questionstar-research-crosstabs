# Versioned project workflow

Use the actual questionnaire definition and deidentified response records. The source directory contains `survey.json`, `responses.deidentified.json` and preferably `fetch-receipt.json`. Workbook exports must first be mapped into this schema using the delivered questionnaire; arbitrary Excel columns are not automatically interchangeable with QuestionStar IDs.

## Run

```bash
python scripts/run_project.py --source /path/to/source \
  --config /path/to/project.json --output-dir /path/to/new-version \
  --node /path/to/bundled/node
```

Use the spreadsheet runtime loader to locate Python/Node and `@oai/artifact-tool`. Python requires NumPy; install requirements only in an appropriate isolated environment outside Codex. The Node builder requires the artifact runtime, not a generic npm package substitution. Pass `WJX_PYTHON_PATH`/`WJX_NODE_PATH` when running component scripts directly. The unified runner forwards its Python executable.

Before workbook generation, ensure the skill directory's `node_modules` resolves to the loaded runtime's provided Node libraries (a local symlink is sufficient). Do not commit this machine-specific link or copy the dependency tree into the skill. If a link already exists, verify its target and do not silently overwrite a different runtime.

Optional flags:
- `--labels keyed-labels.json`: same-survey label rows each include `respondent_id`.
- `--profile-source profile-responses.json`: cross-survey profile responses, matched through `linkage.key`.
- `--sorted`: explicit display-only Total sorting. Omission preserves source order regardless of prior projects.
- `--expectations expected.json`: independent base/count/metric controls.
- `--analysis-only`: skip workbook generation for numerical regression tests.

Each run gets an empty version directory. Output includes the workbook, canonical `analysis.json`, effective config, cleaning and validation receipts, layout map and run manifest. Hashes identify data, configuration and code used. Modifying raw data or rules requires rerunning; the overview dropdown only switches already-computed groups.

## Configuration

```json
{
  "alpha": 0.10,
  "low_base_warning": 30,
  "minimum_test_base": 0,
  "cleaning": {
    "duplicates": "error",
    "min_answer_seconds": 30,
    "required_questions": [1],
    "exclude_if": [{"name": "未通过筛选", "when": {"question": 1, "values": [2]}}]
  },
  "linkage": {"key": "linkage_key", "unmatched": "exclude"},
  "native_segments": [{"family": "参与平台", "question": 2}],
  "scales": {
    "4": {"scores": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": null}, "direction": "higher"}
  },
  "box_metrics_all_ratings": true,
  "nps_question": 21,
  "ordered_questions": [9, 10],
  "family_order": ["总体", "游戏经验", "参与平台", "满意度分层"]
}
```

Question IDs above are illustrative, not defaults. Keep cleaning thresholds off unless the user approved them. `low_base_warning=30` is a display advisory, not sample deletion or a new test cutoff. `minimum_test_base=0` preserves the original method's eligibility (Welch still needs two values per group).

Cleaning accepts an optional `valid_field` plus `valid_values` (default `[true]`). Duplicate policy is `error`, `first` or `last`; first/last refer to input order and must be intentional. Receipts list exclusion reasons and anonymous IDs. Overlapping exclusion reasons may sum to more than the unique number excluded.

## Keyed labels and cross-survey matching

Never zip externally supplied rows by position. Anonymous IDs must be present and unique; missing IDs and duplicates fail. Label input is `{ "labels": [{"respondent_id":"...", "matched":true, "tag":"..."}], "label_groups":[{"family":"...","field":"tag","label":"..."}] }`.

Cross-survey matching requires a stable shared `linkage_key` in both response files. Duplicate nonempty profile or target linkage keys fail rather than silently choosing a person. Missing profile matches follow `linkage.unmatched` (`keep` or `exclude`). A keep policy excludes only unavailable profile memberships, not locally derived score labels.

For fresh API fetching, keep `WJX_API_KEY` and `WJX_ID_SALT` in environment variables. Reuse the project salt for stable anonymous IDs. Set `WJX_LINKAGE_FIELD` only to the user-authorized, verified identifier field for cross-survey matching. The fetcher HMACs it and removes direct identifier/text bodies. Never commit the salt or credentials. Pagination must reconcile the queried total with unique received records.

## Business segments and priority

Use `business_segments` with `family`, optional `field`, `source` (`target` or `profile`), `mode` (`exclusive` or `overlap`), `groups`, optional `fallback`.

```json
{
  "family": "游戏经验",
  "field": "experience",
  "source": "profile",
  "mode": "exclusive",
  "groups": [
    {"label": "横版动作", "when": {"any": [{"question": 3, "selected_any": [1, 2]}, {"question": 6, "selected_any": [3, 4]}]}},
    {"label": "归龙潮", "when": {"question": 7, "selected_any": [2]}}
  ],
  "fallback": "其他玩家"
}
```

Exclusive groups use the configured order: first matching group wins. This expresses the accepted horizontal-action-before-Guilongchao priority; rebuild option IDs from the current survey. Overlap mode creates separate boolean memberships. Conditions support nested `all`/`any`/`not`, `question` with `selected_any`/`selected_all`/`values`/`min`/`max`, or a record `field` with `equals`/`values`/`min`/`max`. Unknown operators fail.

Target-survey business rules record their source-question dependencies for the ‡ definition-based warning. Exclusive families include priority-rule dependencies; overlapping groups track their own rules. Profile question IDs belong to the other questionnaire and must not be treated as target-survey self-crosses.

## Verification boundaries

Numerical tests use prepared fixtures and independent expectations. Actual QuestionStar service behavior requires a live fetch; mocked tests do not establish live API compatibility. Native workbook package checks and artifact rendering do not establish mouse/keyboard behavior in Excel; explicitly distinguish these verification levels in a handoff.
