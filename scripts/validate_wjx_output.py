#!/usr/bin/env python3
"""Project-agnostic validation for canonical survey analysis JSON."""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def main(analysis_path, expectations_path=None):
    data = json.loads(Path(analysis_path).read_text())
    expected = json.loads(Path(expectations_path).read_text()) if expectations_path else {}
    quality, rows, groups = data["quality"], data["rows"], data["groups"]
    checks = []

    def check(name, condition, detail):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    check("记录数与清洗后有效样本一致", quality.get("records_loaded") == quality.get("answer_valid"), [quality.get("records_loaded"), quality.get("answer_valid")])
    check("问卷题目存在", int(quality.get("question_count", 0)) > 0, quality.get("question_count"))
    check("总体列唯一", sum(group.get("family") == "总体" for group in groups) == 1, [group.get("family") for group in groups])
    check("统计行列宽一致", all(len(row.get("cells", [])) == len(groups) for row in rows), {"rows": len(rows), "groups": len(groups)})
    check("质量摘要行列数一致", quality.get("output_row_count") == len(rows) and quality.get("output_column_count") == len(groups), [quality.get("output_row_count"), len(rows), quality.get("output_column_count"), len(groups)])

    finite = True
    percentage_range = True
    count_integrity = True
    for row in rows:
        for cell in row.get("cells", []):
            value = cell.get("value")
            if isinstance(value, (int, float)) and not math.isfinite(value):
                finite = False
            if row.get("kind") in ("percent", "matrix_percent") and value is not None and not 0 <= value <= 1:
                percentage_range = False
            numerator, denominator = cell.get("numerator"), cell.get("denominator")
            if numerator is not None and denominator is not None and not (0 <= numerator <= denominator):
                count_integrity = False
    check("数值均有限", finite, "无 NaN/Infinity")
    check("比例值范围有效", percentage_range, "percent/matrix_percent 均在 0–1")
    check("人数与分母有效", count_integrity, "0 <= numerator <= denominator")

    letters = defaultdict(set)
    for group in groups:
        letters[group.get("family")].add(group.get("letter", ""))
    significance_ok = True
    for row in rows:
        for index, cell in enumerate(row.get("cells", [])):
            group = groups[index]
            allowed = letters[group.get("family")] - {group.get("letter", "")}
            highs = set(cell.get("sig_high") or [])
            if not highs.issubset(allowed) or (cell.get("sig_low_all") and highs):
                significance_ok = False
    check("显著性字母仅指向同族其他列", significance_ok, "不跨族、不指向自身")

    by_question = defaultdict(list)
    for row in rows:
        by_question[int(row["q_index"])].append(row)
    nps_ok = True
    box_ok = True
    for question_rows in by_question.values():
        for row in [row for row in question_rows if row.get("kind") == "nps"]:
            for cell in row["cells"]:
                if cell.get("value") is not None and not -100 <= cell["value"] <= 100:
                    nps_ok = False
        top = next((row for row in question_rows if str(row.get("item", "")).startswith("【指标】T2B")), None)
        bottom = next((row for row in question_rows if str(row.get("item", "")).startswith("【指标】B2B")), None)
        if top and bottom:
            for top_cell, bottom_cell in zip(top["cells"], bottom["cells"]):
                if top_cell.get("value") is not None and bottom_cell.get("value") is not None and top_cell["value"] + bottom_cell["value"] > 1 + 1e-9:
                    box_ok = False
    check("NPS 范围有效", nps_ok, "-100 到 100")
    check("T2B/B2B 合计不越界", box_ok, "同题两项不超过 100%")

    if "answer_valid" in expected:
        check("预期有效样本", quality.get("answer_valid") == expected["answer_valid"], [quality.get("answer_valid"), expected["answer_valid"]])
    for question, expected_base in expected.get("question_bases", {}).items():
        actual = quality.get("question_bases", {}).get(str(question))
        check(f"Q{question} 预期基数", actual == expected_base, [actual, expected_base])
    for item in expected.get("cells", []):
        row = next((row for row in rows if int(row["q_index"]) == int(item["question"]) and row.get("item") == item.get("item", "") and row.get("kind") == item["kind"]), None)
        actual = row["cells"][int(item.get("group_index", 0))]["value"] if row else None
        tolerance = float(item.get("tolerance", 1e-9))
        check(item.get("name", f"Q{item['question']} cell"), actual is not None and abs(actual - float(item["value"])) <= tolerance, [actual, item["value"], tolerance])

    failed = [item for item in checks if not item["passed"]]
    result = {"passed": not failed, "checks": checks, "failed": failed}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        raise SystemExit("Usage: validate_wjx_output.py <analysis.json> [expectations.json]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
