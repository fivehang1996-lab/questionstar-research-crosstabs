#!/usr/bin/env python3
"""Add configuration-driven T2B/B2B rows to an analysis JSON."""
import json
import math
import sys
from pathlib import Path


def proportion_p(x1, n1, x2, n2):
    if not n1 or not n2:
        return None
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(max(pooled * (1 - pooled) * (1 / n1 + 1 / n2), 0))
    if se == 0:
        return 1.0 if x1 / n1 == x2 / n2 else 0.0
    return math.erfc(abs(x1 / n1 - x2 / n2) / se / math.sqrt(2))


def selected_rows(rows, names, count, from_top):
    options = [row for row in rows if row.get("kind") == "percent" and not str(row.get("item", "")).startswith("【指标】")]
    if names:
        mapping = {row["item"]: row for row in options}
        missing = [name for name in names if name not in mapping]
        if missing:
            raise ValueError(f"box metric option labels not found: {missing}")
        return [mapping[name] for name in names]
    return options[-count:] if from_top else options[:count]


def combined_row(question_rows, groups, label, sources, alpha):
    cells = []
    for group_index in range(len(groups)):
        chosen = [row["cells"][group_index] for row in sources]
        numerator = sum(int(cell.get("numerator") or 0) for cell in chosen)
        denominators = {int(cell["denominator"]) for cell in chosen if cell.get("denominator") is not None}
        if len(denominators) > 1:
            raise ValueError(f"inconsistent box-metric denominators for Q{question_rows[0]['q_index']}: {denominators}")
        denominator = next(iter(denominators), 0)
        cells.append({"value": numerator / denominator if denominator else None, "numerator": numerator, "denominator": denominator, "raw": [], "sig_high": [], "sig_low_all": False})

    by_family = {}
    for index, group in enumerate(groups):
        if group["family"] != "总体":
            by_family.setdefault(group["family"], []).append(index)
    for indexes in by_family.values():
        for i in indexes:
            high, comparable, lower_all = [], [], True
            for j in indexes:
                if i == j or cells[i]["value"] is None or cells[j]["value"] is None:
                    continue
                p_value = proportion_p(cells[i]["numerator"], cells[i]["denominator"], cells[j]["numerator"], cells[j]["denominator"])
                if p_value is None:
                    continue
                comparable.append(j)
                if p_value < alpha and cells[i]["value"] > cells[j]["value"]:
                    high.append(groups[j].get("letter", ""))
                if not (p_value < alpha and cells[i]["value"] < cells[j]["value"]):
                    lower_all = False
            cells[i]["sig_high"] = high
            cells[i]["sig_low_all"] = bool(comparable) and lower_all
    return {"q_index": question_rows[0]["q_index"], "question": question_rows[0]["question"], "item": f"【指标】{label}", "metric": "二档合计", "kind": "percent", "test": "proportion", "cells": cells}


def main(source_path, config_path, output_path):
    data = json.loads(Path(source_path).read_text())
    config = json.loads(Path(config_path).read_text())
    specs = {int(spec["question"]): spec for spec in config.get("box_metrics", [])}
    by_question = {}
    for row in data["rows"]:
        by_question.setdefault(int(row["q_index"]), []).append(row)
    alpha = float(data.get("metadata", {}).get("alpha", 0.10))
    output_rows = []
    additions = 0
    for question, rows in by_question.items():
        spec = specs.get(question)
        if not spec:
            output_rows.extend(rows)
            continue
        top = selected_rows(rows, spec.get("top_items"), int(spec.get("top_n", 2)), True)
        bottom = selected_rows(rows, spec.get("bottom_items"), int(spec.get("bottom_n", 2)), False)
        top_label = spec.get("top_label") or f"T2B（{' + '.join(row['item'] for row in top)}）"
        bottom_label = spec.get("bottom_label") or f"B2B（{' + '.join(row['item'] for row in bottom)}）"
        derived = [combined_row(rows, data["groups"], top_label, top, alpha), combined_row(rows, data["groups"], bottom_label, bottom, alpha)]
        insert_at = 1
        while insert_at < len(rows) and rows[insert_at].get("kind") in ("mean", "rank_mean"):
            insert_at += 1
        output_rows.extend(rows[:insert_at] + derived + rows[insert_at:])
        additions += 2
    data["rows"] = output_rows
    data.setdefault("metadata", {})["box_metrics"] = {"enabled": True, "questions": sorted(specs), "placement": "after_mean"}
    data.setdefault("quality", {})["output_row_count"] = len(output_rows)
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False))
    print(json.dumps({"rows": len(output_rows), "added": additions, "questions": sorted(specs), "output": output_path}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: add_box_metrics.py <analysis.json> <config.json> <output.json>")
    main(*sys.argv[1:])
