#!/usr/bin/env python3
"""Add working internal Index hyperlinks to an artifact-tool generated XLSX."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def question_rows(analysis: dict) -> list[int]:
    blocks: list[list[dict]] = []
    for row in analysis["rows"]:
        if not blocks or blocks[-1][0]["q_index"] != row["q_index"]:
            blocks.append([])
        blocks[-1].append(row)

    starts: list[int] = []
    cursor = 3
    for block in blocks:
        starts.append(cursor + 4)
        stat_rows = [row for row in block if row["kind"] != "total"]
        percent_rows = [row for row in stat_rows if row["kind"] == "percent"]
        data_row = cursor + 5 + len(stat_rows)
        if percent_rows:
            data_row += 2
        cursor = data_row + 2
    return starts


def sheet_target(files: dict[str, bytes], sheet_name: str) -> str:
    workbook = ET.fromstring(files["xl/workbook.xml"])
    rels = ET.fromstring(files["xl/_rels/workbook.xml.rels"])
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{NS_PKG}}}Relationship")
    }
    for sheet in workbook.findall(f".//{{{NS_MAIN}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            rel_id = sheet.attrib[f"{{{NS_REL}}}id"]
            target = targets[rel_id].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError(f"Worksheet not found: {sheet_name}")


def inject_hyperlinks(xml_bytes: bytes, row_targets: list[int]) -> bytes:
    text = xml_bytes.decode("utf-8")
    text = re.sub(r"<(?:[A-Za-z_][\w.-]*:)?hyperlinks\b.*?</(?:[A-Za-z_][\w.-]*:)?hyperlinks>", "", text, flags=re.S)
    match = re.search(r"<([A-Za-z_][\w.-]*:)?worksheet\b", text)
    prefix = match.group(1) if match and match.group(1) else ""
    links = []
    for index, target_row in enumerate(row_targets, start=2):
        for column, sheet in (("A", "体验问卷大表"), ("B", "体验问卷显著性检验")):
            location = html.escape(f"'{sheet}'!A{target_row}", quote=True)
            links.append(f'<{prefix}hyperlink ref="{column}{index}" location="{location}"/>')
    block = f"<{prefix}hyperlinks>{''.join(links)}</{prefix}hyperlinks>"
    markers = [f"<{prefix}printOptions", f"<{prefix}pageMargins", f"<{prefix}drawing", f"</{prefix}worksheet>"]
    for marker in markers:
        pos = text.find(marker)
        if pos >= 0:
            return (text[:pos] + block + text[pos:]).encode("utf-8")
    raise ValueError("Could not find a valid hyperlink insertion point")


def cell_text(xml_bytes: bytes, address: str) -> str:
    root = ET.fromstring(xml_bytes)
    cell = root.find(f".//{{{NS_MAIN}}}c[@r='{address}']")
    if cell is None:
        return ""
    value = cell.find(f"{{{NS_MAIN}}}v")
    if value is not None and value.text:
        return value.text
    inline = cell.find(f".//{{{NS_MAIN}}}t")
    return inline.text if inline is not None and inline.text else ""


def verify_targets(files: dict[str, bytes], analysis: dict, row_targets: list[int]) -> dict:
    index_target = sheet_target(files, "Index")
    index_root = ET.fromstring(files[index_target])
    links = index_root.findall(f".//{{{NS_MAIN}}}hyperlink")
    expected_count = len(row_targets) * 2
    if len(links) != expected_count:
        raise ValueError(f"Index hyperlink count mismatch: {len(links)} vs {expected_count}")

    questions = list(dict.fromkeys(int(row["q_index"]) for row in analysis["rows"]))
    expected = {}
    for index, (question, target_row) in enumerate(zip(questions, row_targets), start=2):
        expected[f"A{index}"] = ("体验问卷大表", question, target_row)
        expected[f"B{index}"] = ("体验问卷显著性检验", question, target_row)

    actual = {link.attrib.get("ref"): link.attrib.get("location", "") for link in links}
    for ref, (sheet_name, question, target_row) in expected.items():
        location = f"'{sheet_name}'!A{target_row}"
        if actual.get(ref) != location:
            raise ValueError(f"Index hyperlink target mismatch for {ref}: {actual.get(ref)!r} vs {location!r}")
        target = sheet_target(files, sheet_name)
        value = cell_text(files[target], f"A{target_row}")
        if not value.startswith(f"[Q{question}]."):
            raise ValueError(f"Index hyperlink {ref} does not land on Q{question} title: {value!r}")
    return {"questions": len(questions), "hyperlinks": len(links), "targets_verified": True}


def main() -> None:
    if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != "--verify-only"):
        raise SystemExit("Usage: add_internal_index_links.py <analysis.json> <workbook.xlsx> [--verify-only]")
    analysis_path = Path(sys.argv[1])
    workbook_path = Path(sys.argv[2])
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if analysis.get('metadata', {}).get('schema_version') == 2:
        from finalize_workbook import main as finalize
        from verify_workbook_package import verify
        if len(sys.argv) != 4:
            finalize(str(analysis_path), str(workbook_path))
        result = verify(str(workbook_path), str(analysis_path))
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result['passed'] else 1)
    targets = question_rows(analysis)

    with zipfile.ZipFile(workbook_path, "r") as source:
        files = {name: source.read(name) for name in source.namelist()}
    verify_only = len(sys.argv) == 4
    if not verify_only:
        index_target = sheet_target(files, "Index")
        files[index_target] = inject_hyperlinks(files[index_target], targets)

        fd, temp_name = tempfile.mkstemp(prefix="index-links-", suffix=".xlsx", dir=workbook_path.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for name, payload in files.items():
                    output.writestr(name, payload)
            os.replace(temp_name, workbook_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

        with zipfile.ZipFile(workbook_path, "r") as source:
            files = {name: source.read(name) for name in source.namelist()}

    result = verify_targets(files, analysis, targets)
    result["workbook"] = workbook_path.name
    result["mode"] = "verify_only" if verify_only else "inject_and_verify"
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
