#!/usr/bin/env python3
"""Run the repository's synthetic survey example end to end."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parents[1]


def run(command, *, env=None, stdout_path=None):
    print("+", " ".join(map(str, command)))
    if stdout_path:
        with Path(stdout_path).open("w", encoding="utf-8") as handle:
            subprocess.run(command, check=True, env=env, stdout=handle)
    else:
        subprocess.run(command, check=True, env=env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=os.environ.get("WJX_PYTHON_PATH", sys.executable))
    parser.add_argument("--node", default=os.environ.get("WJX_NODE_PATH", "node"))
    parser.add_argument("--node-modules", default=os.environ.get("WJX_NODE_MODULES"))
    parser.add_argument("--output-dir", type=Path, default=EXAMPLE_DIR / "build")
    parser.add_argument("--regenerate-source", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    source_dir = EXAMPLE_DIR / "source"
    config = EXAMPLE_DIR / "project-config.json"
    expectations = EXAMPLE_DIR / "expectations.json"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.regenerate_source or not (source_dir / "responses.deidentified.json").exists():
        run([args.python, EXAMPLE_DIR / "generate_synthetic_source.py", source_dir])

    if args.node_modules:
        link = REPO_ROOT / "node_modules"
        target = Path(args.node_modules).resolve()
        if link.is_symlink() and link.resolve() != target:
            raise RuntimeError(f"node_modules points to {link.resolve()}, expected {target}")
        if not link.exists():
            link.symlink_to(target, target_is_directory=True)

    labels = output_dir / "labels.json"
    analysis = output_dir / "analysis.json"
    reordered = output_dir / "analysis.reordered.json"
    final_analysis = output_dir / "final-analysis.json"
    workbook = output_dir / "synthetic-game-survey-crosstabs.xlsx"
    previews = output_dir / "previews"
    validation = output_dir / "validation-receipt.json"
    verification = output_dir / "workbook-verification.json"
    link_verification = output_dir / "index-link-verification.json"

    run([args.python, REPO_ROOT / "scripts/apply_derived_segments.py", source_dir / "responses.deidentified.json", "-", config, labels])
    run([args.python, REPO_ROOT / "scripts/analyze_wjx_dynamic.py", source_dir, analysis, labels, config])
    run([args.python, REPO_ROOT / "scripts/reorder_group_families.py", analysis, config, reordered])
    run([args.python, REPO_ROOT / "scripts/add_box_metrics.py", reordered, config, final_analysis])
    run([args.python, REPO_ROOT / "scripts/validate_wjx_output.py", final_analysis, expectations], stdout_path=validation)

    environment = dict(os.environ)
    environment["WJX_PYTHON_PATH"] = str(args.python)
    run([args.node, REPO_ROOT / "scripts/build_wjx_crosstab_workbook.mjs", final_analysis, workbook, previews], env=environment)
    run([args.node, REPO_ROOT / "scripts/verify_wjx_workbook.mjs", workbook, "--compact"], stdout_path=verification)
    run([args.python, REPO_ROOT / "scripts/add_internal_index_links.py", final_analysis, workbook, "--verify-only"], stdout_path=link_verification)

    if args.publish:
        published_output = EXAMPLE_DIR / "outputs"
        published_preview = EXAMPLE_DIR / "previews"
        published_output.mkdir(exist_ok=True)
        published_preview.mkdir(exist_ok=True)
        shutil.copy2(workbook, published_output / workbook.name)
        shutil.copy2(previews / "00-index.png", published_preview / "index.png")
        shutil.copy2(previews / "02-table.png", published_preview / "frequency-table.png")
        shutil.copy2(previews / "03-significance.png", published_preview / "significance-table.png")
        shutil.copy2(validation, EXAMPLE_DIR / "validation-receipt.json")
        shutil.copy2(verification, EXAMPLE_DIR / "workbook-verification.json")
        shutil.copy2(link_verification, EXAMPLE_DIR / "index-link-verification.json")

    print(f"Workbook: {workbook}")


if __name__ == "__main__":
    main()
