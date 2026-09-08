#!/usr/bin/env python3
"""Configuration-driven survey crosstab analyzer."""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from analyze_wjx_crosstabs import add_significance


def clean(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def main(source_dir, output_path, labels_path=None, config_path=None):
    source = Path(source_dir)
    survey = json.loads((source / "survey.json").read_text())
    records = json.loads((source / "responses.deidentified.json").read_text())
    receipt_path = source / "fetch-receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    labels_meta = json.loads(Path(labels_path).read_text()) if labels_path and labels_path != "-" else {}
    labels = labels_meta.get("labels")
    config = json.loads(Path(config_path).read_text()) if config_path and config_path != "-" else {}
    if labels is not None and len(labels) != len(records):
        raise ValueError(f"record/label mismatch: {len(records)} vs {len(labels)}")

    questions = {}
    for question in survey.get("questions", []):
        index = int(question.get("q_index") or 0)
        if index > 0 and question.get("q_title") and int(question.get("q_type") or 0) not in (1, 2):
            questions[index] = question

    people = []
    for record in records:
        by_question = defaultdict(list)
        for answer in record.get("answer_items", {}).values():
            by_question[int(answer.get("q_index") or 0)].append(answer)
        people.append(by_question)

    def primary(person, question):
        answers = person.get(question, [])
        return next((answer for answer in answers if int(answer.get("q_column") or 0) == 0), answers[0] if answers else None)

    def indexes(person, question):
        answer = primary(person, question) or {}
        return [int(value) for value in answer.get("item_index", []) if isinstance(value, (int, float)) and int(value) >= 0]

    def single(person, question):
        values = indexes(person, question)
        return values[0] if values else None

    def selected(person, question):
        answer = primary(person, question)
        if not answer:
            return None
        raw = answer.get("item_index", [])
        if not raw or any(int(value) < 0 for value in raw):
            return None
        return {int(value) for value in raw}

    def numeric_value(person, question):
        answer = primary(person, question) or {}
        try:
            return float(answer.get("item_value"))
        except (TypeError, ValueError):
            return None

    def ranking(person, question):
        result = {}
        for answer in person.get(question, []):
            position = int(answer.get("q_column") or 0)
            values = [int(value) for value in answer.get("item_index", [])]
            if position > 0 and values and values[0] > 0:
                result[values[0]] = position
        return result or None

    def answered(person, question):
        qtype = int(questions[question].get("q_type") or 0)
        if qtype == 5:
            answer = primary(person, question) or {}
            return bool(answer.get("answered") or str(answer.get("answer_text") or "").strip())
        if qtype == 4:
            return selected(person, question) is not None
        if qtype == 7:
            return bool(person.get(question))
        return single(person, question) is not None

    groups = [{"family": "总体", "label": "总体", "members": list(range(len(people))), "letter": ""}]
    if labels:
        for spec in labels_meta.get("exclusive_groups", []):
            field = spec.get("field", "exclusive_group")
            groups.append({"family": spec["family"], "label": spec["label"], "members": [i for i, row in enumerate(labels) if row.get(field) == spec["label"]]})
        for spec in labels_meta.get("label_groups", []):
            field = spec.get("field", spec["family"])
            groups.append({"family": spec["family"], "label": spec["label"], "members": [i for i, row in enumerate(labels) if row.get(field) == spec["label"]]})
        for spec in config.get("categorical_label_fields", []):
            values = spec.get("values") or list(dict.fromkeys(row.get(spec["field"]) for row in labels if row.get(spec["field"]) not in (None, "")))
            for value in values:
                groups.append({"family": spec["family"], "label": value, "members": [i for i, row in enumerate(labels) if row.get(spec["field"]) == value]})
        for spec in config.get("boolean_label_prefixes", []):
            keys = list(dict.fromkeys(key for row in labels for key in row if key.startswith(spec["prefix"])))
            for key in keys:
                groups.append({"family": spec["family"], "label": key[len(spec["prefix"]):], "members": [i for i, row in enumerate(labels) if row.get(key) is True]})

    for spec in config.get("native_segments", []):
        question = int(spec["question"])
        for option in questions.get(question, {}).get("items", []):
            option_index = int(option.get("item_index") or 0)
            groups.append({"family": spec["family"], "label": clean(option.get("item_title")), "members": [i for i, person in enumerate(people) if single(person, question) == option_index]})

    counters = defaultdict(int)
    for group in groups[1:]:
        counters[group["family"]] += 1
        number = counters[group["family"]]
        group["letter"] = chr(64 + number) if number <= 26 else f"A{chr(64 + number - 26)}"

    alpha = float(config.get("alpha", 0.10))
    nps_question = int(config["nps_question"]) if config.get("nps_question") else None
    rating_questions = {int(value) for value in config.get("rating_questions", [])}
    auto_rating = bool(config.get("auto_rating_five_point", True))
    rows = []

    def append(question, item, metric, kind, test, cell_function):
        cells = []
        for group in groups:
            cell = cell_function(group["members"])
            cell.setdefault("value", None)
            cell.setdefault("numerator", None)
            cell.setdefault("denominator", None)
            cell.setdefault("raw", [])
            cell.setdefault("sig_high", [])
            cell.setdefault("sig_low_all", False)
            cells.append(cell)
        row = {"q_index": question, "question": f"Q{question}. {clean(questions[question]['q_title'])}", "item": item, "metric": metric, "kind": kind, "test": test, "cells": cells}
        add_significance(row, groups, alpha)
        rows.append(row)

    for question in sorted(questions):
        meta = questions[question]
        qtype, subtype = int(meta.get("q_type") or 0), int(meta.get("q_subtype") or 0)
        if question == nps_question:
            def scores(indices):
                return [numeric_value(people[i], question) for i in indices if numeric_value(people[i], question) is not None and 0 <= numeric_value(people[i], question) <= 10]
            append(question, "", "total", "total", "none", lambda indices: {"value": len(scores(indices))})
            append(question, "", "NPS", "nps", "welch", lambda indices: (lambda values: {"value": (sum(value >= 9 for value in values) - sum(value <= 6 for value in values)) * 100 / len(values) if values else None, "raw": [1 if value >= 9 else -1 if value <= 6 else 0 for value in values]})(scores(indices)))
            for label, predicate in [("批评者（0–6分）", lambda value: value <= 6), ("中立者（7–8分）", lambda value: 7 <= value <= 8), ("推荐者（9–10分）", lambda value: value >= 9)]:
                append(question, label, "列百分比", "percent", "proportion", lambda indices, pred=predicate: (lambda values: {"value": sum(pred(value) for value in values) / len(values) if values else None, "numerator": sum(pred(value) for value in values), "denominator": len(values)})(scores(indices)))
            continue

        if qtype == 5:
            append(question, "", "total", "total", "none", lambda indices: {"value": sum(answered(people[i], question) for i in indices)})
            continue
        if qtype == 7:
            append(question, "", "total", "total", "none", lambda indices: {"value": sum(answered(people[i], question) for i in indices)})
            options = [(int(option.get("item_index") or 0), clean(option.get("item_title"))) for option in meta.get("items", [])]
            for row_option in meta.get("item_rows", []):
                row_index, row_label = int(row_option.get("item_index") or 0), clean(row_option.get("item_title"))
                for option_index, option_label in options:
                    def matrix_cell(indices, ri=row_index, oi=option_index):
                        valid = [people[i] for i in indices if any(int(answer.get("q_row") or 0) == ri and answer.get("item_index") for answer in people[i].get(question, []))]
                        count = sum(any(int(answer.get("q_row") or 0) == ri and oi in [int(value) for value in answer.get("item_index", [])] for answer in person.get(question, [])) for person in valid)
                        return {"value": count / len(valid) if valid else None, "numerator": count, "denominator": len(valid)}
                    append(question, f"{row_label}｜{option_label}", "列百分比", "matrix_percent", "proportion", matrix_cell)
            continue
        if subtype == 402:
            append(question, "", "total", "total", "none", lambda indices: {"value": sum(ranking(people[i], question) is not None for i in indices)})
            for option in meta.get("items", []):
                option_index, label = int(option.get("item_index") or 0), clean(option.get("item_title"))
                append(question, label, "入选率", "percent", "proportion", lambda indices, oi=option_index: (lambda values: {"value": sum(oi in value for value in values) / len(values) if values else None, "numerator": sum(oi in value for value in values), "denominator": len(values)})([ranking(people[i], question) for i in indices if ranking(people[i], question) is not None]))
                append(question, label, "平均名次", "rank_mean", "welch", lambda indices, oi=option_index: (lambda values: {"value": float(np.mean(values)) if values else None, "raw": values})([ranking(people[i], question)[oi] for i in indices if ranking(people[i], question) and oi in ranking(people[i], question)]))
            continue

        is_multi = qtype == 4 and subtype == 4
        append(question, "", "total", "total", "none", lambda indices: {"value": sum(answered(people[i], question) for i in indices)})
        if is_multi:
            for option in meta.get("items", []):
                option_index, label = int(option.get("item_index") or 0), clean(option.get("item_title"))
                append(question, label, "列百分比", "percent", "proportion", lambda indices, oi=option_index: (lambda values: {"value": sum(oi in value for value in values) / len(values) if values else None, "numerator": sum(oi in value for value in values), "denominator": len(values)})([selected(people[i], question) for i in indices if selected(people[i], question) is not None]))
            continue

        is_rating = question in rating_questions or (auto_rating and qtype == 3 and len(meta.get("items", [])) == 5)
        if is_rating:
            append(question, "", "均值", "mean", "welch", lambda indices: (lambda values: {"value": float(np.mean(values)) if values else None, "raw": values})([single(people[i], question) for i in indices if single(people[i], question) in range(1, 6)]))
        for option in meta.get("items", []):
            option_index, label = int(option.get("item_index") or 0), clean(option.get("item_title"))
            append(question, label, "列百分比", "percent", "proportion", lambda indices, oi=option_index: (lambda values: {"value": sum(value == oi for value in values) / len(values) if values else None, "numerator": sum(value == oi for value in values), "denominator": len(values)})([single(people[i], question) for i in indices if single(people[i], question) is not None]))

    respondent_ids = [record.get("respondent_id") for record in records]
    quality = {"survey_title": survey.get("title"), "vid": survey.get("vid"), "answer_total": survey.get("answer_total"), "answer_valid": len(records), "answer_invalid": max(0, int(survey.get("answer_total") or len(records)) - len(records)), "records_loaded": len(records), "duplicate_respondent_ids": len(respondent_ids) - len(set(respondent_ids)), "question_count": len(questions), "output_row_count": len(rows), "output_column_count": len(groups), "question_bases": {str(question): sum(answered(person, question) for person in people) for question in questions}, "nps_encoding": "item_value 原生 0–10" if nps_question else "不适用", "group_scope": "；".join(dict.fromkeys(group["family"] for group in groups if group["family"] != "总体")), "source_receipt": receipt}
    if labels is not None and labels_meta.get("linkage", True):
        matched = sum(bool(label.get("matched", True)) for label in labels)
        quality["linkage"] = {"matched": matched, "target_total": len(labels), "coverage": matched / len(labels) if labels else 0}
    result = {"metadata": {"title": survey.get("title"), "vid": survey.get("vid"), "alpha": alpha, "scope": config.get("scope", "配置驱动交叉表"), "subtitle": config.get("subtitle"), "mapping_note": config.get("mapping_note"), "multi_select_missing_note": config.get("multi_select_missing_note"), "overlap_warning": config.get("overlap_warning"), "minimum_base_note": config.get("minimum_base_note"), "nps_question": nps_question, "indicator_labels": config.get("indicator_labels", {}), "family_display": config.get("family_display", {})}, "groups": [{key: value for key, value in group.items() if key != "members"} for group in groups], "questions": [{"q_index": question, "title": clean(meta.get("q_title")), "q_type": meta.get("q_type"), "q_subtype": meta.get("q_subtype"), "item_count": len(meta.get("items", [])), "row_count": len(meta.get("item_rows", []))} for question, meta in sorted(questions.items())], "rows": rows, "quality": quality}
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False))
    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if not 3 <= len(sys.argv) <= 5:
        raise SystemExit("Usage: analyze_wjx_dynamic.py <source_dir> <output.json> [labels.json|-] [config.json|-]")
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None, sys.argv[4] if len(sys.argv) > 4 else None)
