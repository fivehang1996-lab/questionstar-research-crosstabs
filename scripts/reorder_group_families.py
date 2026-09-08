#!/usr/bin/env python3
"""Reorder analysis group families and all corresponding cells together."""
import json
import sys
from pathlib import Path


def main(source_path, config_path, output_path):
    data = json.loads(Path(source_path).read_text())
    config = json.loads(Path(config_path).read_text())
    families = ['总体'] + [f for f in config.get("family_order", []) if f != '总体']
    groups = data["groups"]
    selected = []
    used = set()
    for family in families:
        for index, group in enumerate(groups):
            if index not in used and group["family"] == family:
                selected.append(index)
                used.add(index)
    selected.extend(index for index in range(len(groups)) if index not in used)
    data["groups"] = [groups[index] for index in selected]
    for row in data["rows"]:
        row["cells"] = [row["cells"][index] for index in selected]
    data.setdefault("metadata", {})["family_order"] = [data["groups"][i]["family"] for i in range(len(data["groups"]))]
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False))
    print(json.dumps({"groups": len(data["groups"]), "output": output_path}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: reorder_group_families.py <analysis.json> <config.json> <output.json>")
    main(*sys.argv[1:])
