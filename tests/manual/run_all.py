"""
Run all manual tests sequentially and produce a consolidated report.

Output: tests/manual/check_report.md

Usage:
    python tests/manual/run_all.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

TESTS = [
    ("01_llm",   "LLM Client",          "test_01_llm.py",   "_report_01_llm.txt"),
    ("02_graph", "Learning Graph",      "test_02_graph.py", "_report_02_graph.txt"),
    ("03_web",   "Web Background Task", "test_03_web.py",   "_report_03_web.txt"),
]


def run_test(script: str) -> tuple[int, float]:
    """Run a test script; return (exit_code, elapsed_seconds)."""
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(HERE / script)],
        cwd=str(HERE.parent.parent),
        capture_output=False,
    )
    return result.returncode, time.perf_counter() - t0


def main() -> None:
    print("=" * 78)
    print("RUNNING ALL MANUAL TESTS")
    print("=" * 78)
    print()

    results: list[dict] = []

    for idx, (key, name, script, report_file) in enumerate(TESTS, 1):
        print(f"\n[{idx}/{len(TESTS)}] {name}")
        print("-" * 78)

        exit_code, elapsed = run_test(script)
        passed = exit_code == 0

        # Read the per-test report
        report_path = HERE / report_file
        report_text = (
            report_path.read_text(encoding="utf-8")
            if report_path.exists()
            else "(no report generated)"
        )

        results.append({
            "key": key,
            "name": name,
            "passed": passed,
            "elapsed": elapsed,
            "report": report_text,
        })

        icon = "PASS" if passed else "FAIL"
        print(f"  → {icon} ({elapsed:.1f}s)")

    # --- Write consolidated report ---
    report = HERE / "check_report.md"
    lines: list[str] = []
    lines.append("# Manual Test Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| # | Test | Result | Time |")
    lines.append("|---|------|--------|------|")
    total_time = 0.0
    all_passed = True
    for idx, r in enumerate(results, 1):
        icon = "PASS" if r["passed"] else "FAIL"
        lines.append(f"| {idx} | {r['name']} | {icon} | {r['elapsed']:.1f}s |")
        total_time += r["elapsed"]
        if not r["passed"]:
            all_passed = False
    lines.append("")
    lines.append(f"**Total time:** {total_time:.1f}s")
    lines.append(f"**Overall result:** {'PASS' if all_passed else 'FAIL'}")
    lines.append("")

    # Per-test sections
    for idx, r in enumerate(results, 1):
        lines.append("---")
        lines.append("")
        lines.append(f"## {idx}. {r['name']}")
        lines.append("")
        lines.append(f"**Result:** {'PASS' if r['passed'] else 'FAIL'}")
        lines.append("")
        lines.append("```")
        lines.append(r["report"])
        lines.append("```")
        lines.append("")

    report.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("=" * 78)
    print(f"REPORT WRITTEN: {report}")
    print(f"Overall: {'PASS' if all_passed else 'FAIL'} ({total_time:.1f}s)")
    print("=" * 78)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
