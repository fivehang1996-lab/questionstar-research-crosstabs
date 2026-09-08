#!/usr/bin/env python3
"""Apply config-defined question answers as categorical column-group labels."""
import json
import sys
from pathlib import Path
from research_core import align_labels, keyed, source_value as validated_source, classify as validated_classify


def primary(rec, question):
    for item in rec.get("answer_items", {}).values():
        if int(item.get("q_index") or 0) == question and int(item.get("q_column") or 0) == 0:
            return item
    return None


def source_value(rec, spec):
    item = primary(rec, int(spec["question"])) or {}
    if spec.get("source", "item_index") == "item_value":
        value = item.get("item_value")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    values = item.get("item_index") or []
    return int(values[0]) if values else None


def classify(value, groups):
    if value is None:
        return "未回答"
    for group in groups:
        if "values" in group and value in group["values"]:
            return group["label"]
        if "min" in group or "max" in group:
            lower = group.get("min", float("-inf"))
            upper = group.get("max", float("inf"))
            if lower <= value <= upper:
                return group["label"]
    return "未回答"


def main(records_path, labels_path, config_path, output_path):
    records = json.loads(Path(records_path).read_text())
    config = json.loads(Path(config_path).read_text())
    if labels_path == "-":
        meta = {"labels": [{"respondent_id": r["respondent_id"], "matched": True} for r in records], "linkage": False}
    else:
        meta = json.loads(Path(labels_path).read_text())
    labels = align_labels(records, meta)
    meta["labels"] = labels

    new_families = {spec['family'] for spec in config.get('derived_segments', [])}
    label_groups = [spec for spec in meta.get('label_groups', []) if spec['family'] not in new_families]
    for spec in config.get("derived_segments", []):
        field = spec.get("field") or spec["family"]
        for rec, label in zip(records, labels):
            label.setdefault("matched", True)
            label[field] = validated_classify(validated_source(rec, spec), spec["groups"])
        for group in spec["groups"]:
            label_groups.append({"family": spec["family"], "field": field, "label": group["label"], "source_questions": [int(spec['question'])], "requires_match": False})

    meta["label_groups"] = label_groups
    meta["family_order"] = config.get("family_order", [])
    Path(output_path).write_text(json.dumps(meta, ensure_ascii=False))
    print(json.dumps({"records": len(records), "derived_groups": len(label_groups), "output": output_path}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("Usage: apply_derived_segments.py <responses.json> <labels.json|-> <config.json> <output.json>")
    main(*sys.argv[1:])
