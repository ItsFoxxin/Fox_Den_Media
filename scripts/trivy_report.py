#!/usr/bin/env python3
"""Summarize Trivy JSON without hiding unfixed findings; compare trusted baselines."""

import argparse
from collections import Counter
import json
from pathlib import Path

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")


def normalized_findings(report):
    if not isinstance(report, dict) or not isinstance(report.get("Results"), list):
        raise ValueError("Expected Trivy JSON with a Results array")
    findings = {}
    for result in report["Results"]:
        target = result.get("Target", "")
        package_type = result.get("Type", "unknown")
        for vuln in result.get("Vulnerabilities") or []:
            identifier = vuln.get("VulnerabilityID", "")
            package = vuln.get("PkgName", "")
            installed = vuln.get("InstalledVersion", "")
            if not identifier or not package:
                raise ValueError("Trivy vulnerability is missing its identifier or package")
            severity = str(vuln.get("Severity", "UNKNOWN")).upper()
            if severity not in SEVERITIES:
                severity = "UNKNOWN"
            fixed = str(vuln.get("FixedVersion") or "").strip()
            # No image name or transient tag in the key: compare builds of the same component.
            key = json.dumps([identifier, package_type, package, installed],
                             ensure_ascii=False, separators=(",", ":"))
            findings[key] = {
                "key": key, "id": identifier, "severity": severity,
                "package_type": package_type, "package": package,
                "installed": installed, "fixed": fixed, "target": target,
            }
    return sorted(findings.values(), key=lambda row: row["key"])


def summarize(component, image, image_id, source_sha, rows):
    totals = Counter(row["severity"] for row in rows)
    with_fix = Counter(row["severity"] for row in rows if row["fixed"])
    return {
        "component": component, "image": image, "image_id": image_id,
        "source_sha": source_sha, "total": len(rows),
        "by_severity": {level: totals[level] for level in SEVERITIES},
        "fix_available": {level: with_fix[level] for level in SEVERITIES},
        "no_known_fix": {level: totals[level] - with_fix[level] for level in SEVERITIES},
    }


def compare(current, baseline):
    if baseline.get("component") != current.get("component"):
        raise ValueError("Baseline component differs from current image")
    previous = {row["key"]: row for row in baseline["findings"]}
    now = {row["key"]: row for row in current["findings"]}
    return {
        "new": [now[key] for key in sorted(now.keys() - previous.keys())],
        "resolved": [previous[key] for key in sorted(previous.keys() - now.keys())],
        "unchanged": len(now.keys() & previous.keys()),
    }


def markdown(summary, changes=None):
    lines = [
        "### Trivy advisory: " + summary["component"],
        "",
        "- Image: " + summary["image"],
        "- Local image ID: " + summary["image_id"],
        "- Source SHA: " + summary["source_sha"],
        "- Findings: **" + str(summary["total"]) + "** (advisory; not a policy pass)",
        "",
        "| Severity | Findings | Known fix | No known fix |",
        "| --- | ---: | ---: | ---: |",
    ]
    for level in SEVERITIES:
        lines.append("| " + level + " | " + str(summary["by_severity"][level])
                     + " | " + str(summary["fix_available"][level])
                     + " | " + str(summary["no_known_fix"][level]) + " |")
    if changes is not None:
        lines += ["", "- Newly detected compared with selected baseline: **"
                  + str(len(changes["new"])) + "**",
                  "- No longer detected: **" + str(len(changes["resolved"])) + "**"]
    else:
        lines += ["", "Baseline delta not computed. Compare an approved dev run "
                  "using the instructions in docs/trivy.md."]
    lines += ["", "A missing fix is not an exception; triage all critical and high findings."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--component", required=True, choices=("portal", "music", "media"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--baseline", type=Path,
                        help="Optional, deliberately selected trusted dev baseline.json")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    rows = normalized_findings(raw)
    result = {"component": args.component, "findings": rows,
              "image": args.image, "image_id": args.image_id,
              "source_sha": args.source_sha}
    summary = summarize(args.component, args.image, args.image_id, args.source_sha, rows)
    changes = None
    if args.baseline:
        prior = json.loads(args.baseline.read_text(encoding="utf-8"))
        changes = compare(result, prior)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, contents in [
        ("baseline.json", result), ("summary.json", summary),
        *(([("delta.json", changes)]) if changes is not None else []),
    ]:
        (args.output_dir / filename).write_text(
            json.dumps(contents, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    (args.output_dir / "summary.md").write_text(
        markdown(summary, changes), encoding="utf-8")
    print(markdown(summary, changes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
