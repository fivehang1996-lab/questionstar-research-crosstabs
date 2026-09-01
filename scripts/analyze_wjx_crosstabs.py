#!/usr/bin/env python3
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def strip_html(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def load_inputs(source_dir):
    source = Path(source_dir)
    return (
        json.loads((source / "survey.json").read_text()),
        json.loads((source / "responses.deidentified.json").read_text()),
        json.loads((source / "fetch-receipt.json").read_text()),
    )


def question_map(survey):
    out = {}
    for q in survey.get("questions", []):
        idx = int(q.get("q_index") or 0)
        if idx <= 0 or int(q.get("q_type") or 0) in (1, 2) or not q.get("q_title"):
            continue
        q = dict(q)
        q["q_title_clean"] = strip_html(q.get("q_title"))
        q["items"] = [dict(x, item_title_clean=strip_html(x.get("item_title"))) for x in q.get("items", [])]
        out[idx] = q
    return out


def normalize(records):
    people = []
    for record in records:
        by_q = {}
        for item in record.get("answer_items", {}).values():
            q = int(item.get("q_index") or 0)
            by_q.setdefault(q, []).append(item)
        people.append({
            "respondent_id": record["respondent_id"],
            "submit_time": record.get("submit_time"),
            "answer_seconds": record.get("answer_seconds"),
            "by_q": by_q,
        })
    return people


def primary(person, q):
    items = person["by_q"].get(q, [])
    return next((x for x in items if int(x.get("q_column") or 0) == 0), items[0] if items else None)


def selected(person, q):
    item = primary(person, q)
    if not item:
        return None
    vals = [int(x) for x in item.get("item_index", [])]
    if not vals or any(x < 0 for x in vals):
        return None
    return set(vals)


def single(person, q):
    item = primary(person, q)
    if not item:
        return None
    vals = [int(x) for x in item.get("item_index", [])]
    if not vals or vals[0] < 0:
        return None
    return vals[0]


def nps_score(person):
    item = primary(person, 21)
    if not item:
        return None
    try:
        value = int(item.get("item_value"))
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 10 else None


def answered_text(person, q):
    item = primary(person, q)
    if not item:
        return False
    if q == 22:
        return bool(item.get("answered"))
    text = str(item.get("answer_text") or "").strip()
    return bool(text and text != "(空)")


def ranking(person):
    result = {}
    for item in person["by_q"].get(11, []):
        # For subtype 402 the API returns four ranking slots. q_column is the
        # rank position (1..4), while item_index[0] is the selected option ID.
        rank_position = int(item.get("q_column") or 0)
        vals = [int(x) for x in item.get("item_index", [])]
        if rank_position > 0 and vals and vals[0] > 0:
            result[vals[0]] = rank_position
    return result if result else None


def group_definitions(people, qs):
    groups = [{"family": "总体", "label": "总体", "members": list(range(len(people)))}]

    def add_single_family(family, q, item_labels, recode=None):
        for key, label in item_labels:
            members = []
            for i, p in enumerate(people):
                val = single(p, q)
                if recode:
                    val = recode(val)
                if val == key:
                    members.append(i)
            groups.append({"family": family, "label": label, "members": members})

    add_single_family("平台", 2, [(x["item_index"], x["item_title_clean"]) for x in qs[2]["items"]])
    add_single_family("性别", 17, [(x["item_index"], x["item_title_clean"]) for x in qs[17]["items"]])
    add_single_family(
        "年龄", 18,
        [(1, "18岁以下"), (2, "18–25岁"), (3, "26–35岁"), (4, "36岁及以上")],
        recode=lambda v: 4 if v in (4, 5, 6) else v,
    )
    add_single_family("每周游戏时长", 9, [(x["item_index"], x["item_title_clean"]) for x in qs[9]["items"]])
    add_single_family("每月游戏消费", 10, [(x["item_index"], x["item_title_clean"]) for x in qs[10]["items"]])

    experience = [
        (5, "手机游戏类型经历"),
        (6, "手机游戏产品经历"),
        (7, "PC/主机类型经历"),
        (8, "PC/主机产品经历"),
    ]
    for q, family in experience:
        for opt in qs[q]["items"]:
            idx = int(opt["item_index"])
            members = [i for i, p in enumerate(people) if (selected(p, q) is not None and idx in selected(p, q))]
            groups.append({"family": family, "label": opt["item_title_clean"], "members": members})

    family_letters = {}
    for g in groups:
        if g["family"] == "总体":
            g["letter"] = ""
        else:
            family_letters.setdefault(g["family"], 0)
            n = family_letters[g["family"]]
            g["letter"] = chr(ord("A") + n) if n < 26 else f"A{chr(ord('A') + n - 26)}"
            family_letters[g["family"]] += 1
        g["base_n"] = len(g["members"])
    return groups


def proportion_p(x1, n1, x2, n2):
    if n1 <= 0 or n2 <= 0:
        return None
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0 if x1 / n1 == x2 / n2 else 0.0
    z = abs(x1 / n1 - x2 / n2) / se
    return float(math.erfc(z / math.sqrt(2)))


def beta_continued_fraction(a, b, x):
    max_iter, eps, fpmin = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = fpmin if abs(d) < fpmin else d
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = fpmin if abs(d) < fpmin else d
        c = 1.0 + aa / c
        c = fpmin if abs(c) < fpmin else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = fpmin if abs(d) < fpmin else d
        c = 1.0 + aa / c
        c = fpmin if abs(c) < fpmin else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_beta(x, a, b):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * beta_continued_fraction(a, b, x) / a
    return 1.0 - bt * beta_continued_fraction(b, a, 1.0 - x) / b


def welch_p(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return None
    mean_a, mean_b = float(np.mean(a)), float(np.mean(b))
    var_a, var_b = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    term_a, term_b = var_a / len(a), var_b / len(b)
    se2 = term_a + term_b
    if se2 <= 0:
        return 0.0 if mean_a != mean_b else 1.0
    denom = (term_a * term_a) / (len(a) - 1) + (term_b * term_b) / (len(b) - 1)
    if denom <= 0:
        return None
    dof = se2 * se2 / denom
    t = abs(mean_a - mean_b) / math.sqrt(se2)
    x = dof / (dof + t * t)
    return float(regularized_beta(x, dof / 2.0, 0.5))


def add_significance(row, groups, alpha=0.10):
    if row["test"] == "none":
        return
    by_family = {}
    for i, g in enumerate(groups):
        if g["family"] != "总体":
            by_family.setdefault(g["family"], []).append(i)
    for indices in by_family.values():
        for i in indices:
            cell_i = row["cells"][i]
            high = []
            comparable = []
            lower_all = True
            for j in indices:
                if i == j:
                    continue
                cell_j = row["cells"][j]
                if cell_i["value"] is None or cell_j["value"] is None:
                    continue
                if row["test"] == "proportion":
                    p = proportion_p(cell_i["numerator"], cell_i["denominator"], cell_j["numerator"], cell_j["denominator"])
                else:
                    p = welch_p(cell_i.get("raw", []), cell_j.get("raw", []))
                if p is None:
                    continue
                comparable.append(j)
                if p < alpha and cell_i["value"] > cell_j["value"]:
                    high.append(groups[j]["letter"])
                if not (p < alpha and cell_i["value"] < cell_j["value"]):
                    lower_all = False
            cell_i["sig_high"] = high
            cell_i["sig_low_all"] = bool(comparable) and lower_all


def build_rows(people, groups, qs):
    rows = []

    def append_row(q, item, metric, kind, test, value_fn):
        cells = []
        for g in groups:
            cell = value_fn([people[i] for i in g["members"]])
            cell.setdefault("value", None)
            cell.setdefault("numerator", None)
            cell.setdefault("denominator", None)
            cell.setdefault("raw", [])
            cell["sig_high"] = []
            cell["sig_low_all"] = False
            cells.append(cell)
        row = {
            "q_index": q,
            "question": f"Q{q}. {qs[q]['q_title_clean']}",
            "item": item,
            "metric": metric,
            "kind": kind,
            "test": test,
            "cells": cells,
        }
        add_significance(row, groups)
        rows.append(row)

    for q in range(1, 23):
        if q not in qs:
            continue
        qtype = int(qs[q].get("q_type") or 0)
        subtype = int(qs[q].get("q_subtype") or 0)
        if q in (20, 22):
            append_row(q, "", "total（样本量）", "total", "none", lambda ps, qq=q: {"value": sum(answered_text(p, qq) for p in ps)})
            continue
        if q == 21:
            append_row(q, "", "total（样本量）", "total", "none", lambda ps: {"value": sum(nps_score(p) is not None for p in ps)})
            def nps_cell(ps):
                scores = [nps_score(p) for p in ps if nps_score(p) is not None]
                coded = [1 if x >= 9 else (-1 if x <= 6 else 0) for x in scores]
                return {"value": (sum(coded) / len(coded) * 100) if coded else None, "raw": coded}
            append_row(q, "", "NPS", "nps", "welch", nps_cell)
            for label, pred in [("批评者（0–6分）", lambda x: x <= 6), ("中立者（7–8分）", lambda x: 7 <= x <= 8), ("推荐者（9–10分）", lambda x: x >= 9)]:
                def share(ps, predicate=pred):
                    scores = [nps_score(p) for p in ps if nps_score(p) is not None]
                    x = sum(predicate(v) for v in scores)
                    return {"value": x / len(scores) if scores else None, "numerator": x, "denominator": len(scores)}
                append_row(q, label, "列百分比", "percent", "none", share)
            continue
        if q == 11 and subtype == 402:
            append_row(q, "", "total（样本量）", "total", "none", lambda ps: {"value": sum(ranking(p) is not None for p in ps)})
            for opt in qs[q]["items"]:
                idx, label = int(opt["item_index"]), opt["item_title_clean"]
                def inclusion(ps, ii=idx):
                    answered = [ranking(p) for p in ps if ranking(p) is not None]
                    x = sum(r.get(ii) is not None for r in answered)
                    return {"value": x / len(answered) if answered else None, "numerator": x, "denominator": len(answered)}
                append_row(q, label, "入选率", "percent", "proportion", inclusion)
                def avg_rank(ps, ii=idx):
                    vals = [ranking(p).get(ii) for p in ps if ranking(p) is not None and ranking(p).get(ii) is not None]
                    return {"value": float(np.mean(vals)) if vals else None, "raw": vals}
                append_row(q, label, "平均名次", "mean", "welch", avg_rank)
            continue

        is_multi = qtype == 4 and subtype == 4
        if is_multi:
            append_row(q, "", "total（样本量）", "total", "none", lambda ps, qq=q: {"value": sum(selected(p, qq) is not None for p in ps)})
            for opt in qs[q]["items"]:
                idx, label = int(opt["item_index"]), opt["item_title_clean"]
                def multi_share(ps, qq=q, ii=idx):
                    answered = [selected(p, qq) for p in ps if selected(p, qq) is not None]
                    x = sum(ii in values for values in answered)
                    return {"value": x / len(answered) if answered else None, "numerator": x, "denominator": len(answered)}
                append_row(q, label, "列百分比", "percent", "proportion", multi_share)
            continue

        append_row(q, "", "total（样本量）", "total", "none", lambda ps, qq=q: {"value": sum(single(p, qq) is not None for p in ps)})
        if q == 4:
            def mean_cell(ps):
                vals = [single(p, 4) for p in ps if single(p, 4) in (1, 2, 3, 4, 5)]
                return {"value": float(np.mean(vals)) if vals else None, "raw": vals}
            append_row(q, "", "均值", "mean", "welch", mean_cell)
        for opt in qs[q].get("items", []):
            idx, label = int(opt["item_index"]), opt["item_title_clean"]
            def single_share(ps, qq=q, ii=idx):
                vals = [single(p, qq) for p in ps if single(p, qq) is not None]
                x = sum(v == ii for v in vals)
                return {"value": x / len(vals) if vals else None, "numerator": x, "denominator": len(vals)}
            append_row(q, label, "列百分比", "percent", "proportion", single_share)
    return rows


def quality_summary(survey, people, groups, qs, rows, receipt):
    indices = [p["respondent_id"] for p in people]
    q_bases = {}
    for q in qs:
        if q in (20, 22):
            q_bases[str(q)] = sum(answered_text(p, q) for p in people)
        elif q == 21:
            q_bases[str(q)] = sum(nps_score(p) is not None for p in people)
        elif q == 11:
            q_bases[str(q)] = sum(ranking(p) is not None for p in people)
        elif int(qs[q].get("q_type") or 0) == 4 and int(qs[q].get("q_subtype") or 0) == 4:
            q_bases[str(q)] = sum(selected(p, q) is not None for p in people)
        else:
            q_bases[str(q)] = sum(single(p, q) is not None for p in people)
    return {
        "survey_title": survey["title"],
        "vid": survey["vid"],
        "answer_total": survey["answer_total"],
        "answer_valid": survey["answer_valid"],
        "answer_invalid": survey["answer_total"] - survey["answer_valid"],
        "records_loaded": len(people),
        "duplicate_respondent_ids": len(indices) - len(set(indices)),
        "question_count": len(qs),
        "output_row_count": len(rows),
        "output_column_count": len(groups),
        "question_bases": q_bases,
        "nps_encoding": "API item_value is native 0-10",
        "missing_rules": {"multi_skip": -3, "ranking_not_selected": -2, "open_blank": "(空)"},
        "source_receipt": receipt,
    }


def main():
    source_dir, output_path = sys.argv[1], Path(sys.argv[2])
    survey, records, receipt = load_inputs(source_dir)
    qs = question_map(survey)
    people = normalize(records)
    groups = group_definitions(people, qs)
    rows = build_rows(people, groups, qs)
    result = {
        "metadata": {
            "title": survey["title"],
            "vid": survey["vid"],
            "alpha": 0.10,
            "scope": "问卷原生分组测试版",
        },
        "groups": [{k: v for k, v in g.items() if k != "members"} for g in groups],
        "questions": [{
            "q_index": q,
            "title": qs[q]["q_title_clean"],
            "q_type": qs[q].get("q_type"),
            "q_subtype": qs[q].get("q_subtype"),
            "item_count": len(qs[q].get("items", [])),
        } for q in sorted(qs)],
        "rows": rows,
        "quality": quality_summary(survey, people, groups, qs, rows, receipt),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False))
    print(json.dumps(result["quality"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
