#!/usr/bin/env python3
"""Publish Trivy summaries from a trusted workflow_run, never from PR code."""

import argparse
from datetime import datetime
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from scripts.trivy_report import compare, normalized_findings, summarize

COMPONENTS = ("portal", "music", "media")
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
MARKER = "<!-- foxden-trivy-pr-v1 -->"
SCANNER_WORKFLOW = "Trivy first-party images (advisory)"
LABELS = {
    "security: review-required": ("D4A017", "Automated Trivy review required"),
    "security: new-critical": ("B60205", "New critical image vulnerability since trusted dev baseline"),
    "security: new-high": ("D93F0B", "New high-severity image vulnerability since trusted dev baseline"),
}
SHA_RE = re.compile("^[0-9a-f]{40}$")
DIGEST_RE = re.compile("^sha256:[0-9a-f]{64}$")


class EvidenceError(ValueError):
    pass


def check(condition, message):
    if not condition:
        raise EvidenceError(message)


class Github:
    def __init__(self, repo, token):
        check(bool(re.fullmatch("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)), "Bad repository")
        self.repo = repo
        self.token = token

    def call(self, path, method="GET", payload=None, binary=False):
        url = "https://api.github.com/repos/" + self.repo + path
        headers = {"Accept": "application/vnd.github+json",
                   "Authorization": "Bearer " + self.token,
                   "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "FoxDen-Trivy-Reporter"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(url, data, headers, method=method)

        class SafeRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                result = super().redirect_request(req, fp, code, msg, headers, newurl)
                if result and urllib.parse.urlsplit(newurl).hostname != "api.github.com":
                    result.remove_header("Authorization")
                return result

        with urllib.request.build_opener(SafeRedirect()).open(request, timeout=45) as response:
            content = response.read(12 * 1024 * 1024 + 1 if binary else 15 * 1024 * 1024)
        if binary:
            check(len(content) <= 12 * 1024 * 1024, "Compressed artifact too large")
            return content
        return json.loads(content) if content else None


def zip_json(content, name):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = [member for member in archive.infolist() if member.filename == name]
        check(len(entries) == 1, "Missing or duplicate ZIP entry " + name)
        check(entries[0].file_size <= 20 * 1024 * 1024 and not entries[0].is_dir(),
              "Unsafe ZIP entry")
        with archive.open(entries[0]) as source:
            result = source.read(20 * 1024 * 1024 + 1)
        check(len(result) <= 20 * 1024 * 1024, "ZIP decompression limit exceeded")
        return json.loads(result)


def verify_artifact(zipped, component, source_sha):
    report = zip_json(zipped, "vulnerabilities.json")
    summary = zip_json(zipped, "summary.json")
    baseline = zip_json(zipped, "baseline.json")
    sbom = zip_json(zipped, "sbom.cdx.json")
    version = zip_json(zipped, "trivy-version.json")
    image = "foxden-ci-" + component + ":" + source_sha
    check(report.get("ArtifactType") == "container_image"
          and report.get("ArtifactName") == image, "Unexpected source image")
    image_id = summary.get("image_id", "")
    check(bool(DIGEST_RE.fullmatch(image_id))
          and report.get("Metadata", {}).get("ImageID") == image_id,
          "Image ID mismatch")
    check(summary.get("component") == component
          and baseline.get("component") == component, "Wrong component")
    check(summary.get("image") == image and baseline.get("image") == image,
          "Wrong image tag")
    check(summary.get("source_sha") == source_sha
          and baseline.get("source_sha") == source_sha
          and baseline.get("image_id") == image_id, "Wrong scan SHA or image ID")
    check(sbom.get("bomFormat") == "CycloneDX"
          and isinstance(sbom.get("components"), list), "Invalid CycloneDX output")
    check(isinstance(version.get("Version"), str)
          and bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?",
                                version["Version"])), "Invalid Trivy version")
    reported_version = report.get("Trivy", {}).get("Version")
    check(not reported_version or reported_version == version["Version"],
          "Scanner version differs between report and metadata")
    rows = normalized_findings(report)
    check(rows == baseline.get("findings"), "Source findings do not match baseline")
    check(summarize(component, image, image_id, source_sha, rows) == summary,
          "Summary count mismatch")
    db = version.get("VulnerabilityDB") or {}
    updated = db.get("UpdatedAt")
    if updated is not None:
        check(isinstance(updated, str) and len(updated) <= 64, "Invalid DB timestamp")
        try:
            datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError as error:
            raise EvidenceError("Unparseable DB timestamp") from error
    return {"summary": summary, "baseline": baseline, "version": version["Version"],
            "database_updated": updated}


def load_scans(api, run, source_sha):
    check(run.get("status") == "completed" and run.get("conclusion") == "success",
          "Scan workflow failed")
    response = api.call("/actions/runs/" + str(run["id"]) + "/artifacts?per_page=100")
    check(response.get("total_count") == 3, "Expected exactly three artifact archives")
    available = response.get("artifacts") or []
    scans = {}
    for component in COMPONENTS:
        name = "trivy-" + component + "-" + str(run["id"])
        selected = [a for a in available if a.get("name") == name]
        check(len(selected) == 1, "Duplicate or missing " + component + " artifact")
        artifact = selected[0]
        source = artifact.get("workflow_run") or {}
        check(not artifact.get("expired") and source.get("id") == run["id"]
              and source.get("head_sha") == run["head_sha"], "Untrusted artifact provenance")
        data = api.call("/actions/artifacts/" + str(artifact["id"]) + "/zip", binary=True)
        scans[component] = verify_artifact(data, component, source_sha)
        scans[component]["url"] = ("https://github.com/" + api.repo + "/actions/runs/"
                                  + str(run["id"]) + "/artifacts/" + str(artifact["id"]))
    return scans


def trusted_scanner(api, run, dev_sha):
    """Do not privilege PR results when its scanner workflow or installer was edited."""
    for file_path in (".github/workflows/trivy.yml", "scripts/install_trivy.sh",
                      "scripts/trivy_report.py"):
        path = "/contents/" + urllib.parse.quote(file_path, safe="/") + "?ref="
        approved = api.call(path + dev_sha)
        submitted = api.call(path + run["head_sha"])
        if approved.get("sha") != submitted.get("sha"):
            return False
    return True


def trusted_baseline(api, run):
    branch = api.call("/branches/dev")
    check(branch.get("protected"), "Unprotected dev branch is not trusted")
    dev_sha = branch["commit"]["sha"]
    all_runs = api.call("/actions/workflows/" + str(run["workflow_id"])
                        + "/runs?branch=dev&event=push&status=success&per_page=30")
    candidates = [r for r in all_runs.get("workflow_runs", [])
                  if r.get("event") == "push" and r.get("head_branch") == "dev"
                  and r.get("status") == "completed" and r.get("conclusion") == "success"
                  and r.get("workflow_id") == run["workflow_id"]
                  and r.get("head_repository", {}).get("full_name") == api.repo
                  and r.get("created_at", "") <= run.get("created_at", "")]
    if not candidates:
        return "missing", None, None
    for candidate in candidates:
        sha = candidate.get("head_sha", "")
        if not SHA_RE.fullmatch(sha):
            continue
        ancestry = api.call("/compare/" + sha + "..." + dev_sha)
        if ancestry.get("status") not in ("ahead", "identical"):
            continue
        age = (datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
               - datetime.fromisoformat(candidate["created_at"].replace("Z", "+00:00")))
        if age.total_seconds() > 14 * 86400:
            return "stale", None, candidate
        try:
            return "valid", load_scans(api, candidate, sha), candidate
        except (EvidenceError, KeyError, ValueError, TypeError, zipfile.BadZipFile,
                urllib.error.HTTPError):
            return "invalid", None, candidate
    return "invalid", None, None


def classify(scans, baseline):
    labels = set()
    deltas = {}
    if scans is None or baseline is None:
        return {"security: review-required"}, deltas
    for component in COMPONENTS:
        current = scans[component]["baseline"]
        original = baseline[component]["baseline"]
        changes = compare(current, original)
        old = {row["key"]: row["severity"] for row in original["findings"]}
        escalated = [row for row in current["findings"]
                     if row["key"] in old and old[row["key"]] != row["severity"]
                     and row["severity"] in ("CRITICAL", "HIGH")]
        changes["escalated"] = escalated
        deltas[component] = changes
        if any(row["severity"] == "CRITICAL"
               for row in changes["new"] + escalated):
            labels.add("security: new-critical")
        if any(row["severity"] == "HIGH" for row in changes["new"] + escalated):
            labels.add("security: new-high")
    if labels:
        labels.add("security: review-required")
    return labels, deltas


def render(pr, run, scans, status, baseline_run, deltas):
    base = "https://github.com/" + run["repository"]["full_name"]
    body = [MARKER, "### Fox Den Media: Trivy container security (advisory)", "",
            "- PR: #" + str(pr["number"]) + " (head SHA " + run["head_sha"] + ")",
            "- [Scan run](" + base + "/actions/runs/" + str(run["id"]) + ")",
            "- **Advisory only**. A vulnerability finding is not a required status failure.",
            "- Protected dev baseline: **" + status + "**"]
    if baseline_run:
        body[-1] += " ([baseline run](" + base + "/actions/runs/" + str(baseline_run["id"]) + "))"
    if scans is None:
        body += ["", "**Scan failed or evidence could not be validated.**",
                 "Counts and vulnerability deltas unavailable; do not interpret as a clean scan."]
        return "\n".join(body)
    body += ["", "**Three image scans completed with valid report artifacts.**", "",
             "| Image | Scan | Critical | High | Medium | Low | Unknown | Fixable | No known fix | New | Resolved | Artifact |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for component in COMPONENTS:
        scan = scans[component]
        summary = scan["summary"]
        severity = [str(summary["by_severity"][item]) for item in SEVERITIES]
        found = deltas.get(component)
        added = str(len(found["new"])) if found else "N/A"
        resolved = str(len(found["resolved"])) if found else "N/A"
        fixable = str(sum(summary["fix_available"].values()))
        unknown_fix = str(sum(summary["no_known_fix"].values()))
        body.append("| " + component + " | OK | " + " | ".join(severity) + " | "
                    + fixable + " | " + unknown_fix + " | " + added + " | " + resolved + " | [JSON + SBOM]("
                    + scan["url"] + ") |")
    versions = sorted({s["version"] for s in scans.values()})
    dates = sorted({str(s["database_updated"]) for s in scans.values()
                    if s["database_updated"]})
    body += ["", "- Trivy version: " + ", ".join(versions),
             "- Vulnerability DB updated: " + (", ".join(dates) if dates else "unknown"),
             "- Built image identities (image ID, not published registry digest):"]
    for component in COMPONENTS:
        summary = scans[component]["summary"]
        body.append("  - " + component + ": " + summary["image"]
                    + " / " + summary["image_id"])
    body += ["", "A finding absent from the earlier scan may reflect a newer vulnerability DB "
             "or a refreshed mutable base image rather than PR-introduced code.",
             "Unfixed findings are not automatically ignored. Review detailed evidence in artifacts."]
    return "\n".join(body)


def is_current(api, run, number):
    pr = api.call("/pulls/" + str(number))
    if pr.get("state") != "open" or pr.get("head", {}).get("sha") != run["head_sha"]:
        return False
    runs = api.call("/actions/workflows/" + str(run["workflow_id"])
                    + "/runs?head_sha=" + run["head_sha"] + "&event=pull_request&per_page=30")
    for other in runs.get("workflow_runs", []):
        assoc = other.get("pull_requests") or []
        if not any(item.get("number") == number for item in assoc):
            continue
        if other.get("created_at", "") > run.get("created_at", ""):
            return False
        if (other.get("created_at") == run.get("created_at")
                and other.get("id", 0) > run["id"]):
            return False
    return True


def comment_upsert(api, number, body):
    found = []
    for page in range(1, 6):
        batch = api.call("/issues/" + str(number)
                         + "/comments?per_page=100&page=" + str(page))
        check(isinstance(batch, list), "GitHub comments were not a list")
        found.extend(item for item in batch if MARKER in (item.get("body") or "")
                     and item.get("user", {}).get("login") == "github-actions[bot]")
        if len(batch) < 100:
            break
    if found:
        previous = max(found, key=lambda item: item["id"])
        if previous.get("body") != body:
            api.call("/issues/comments/" + str(previous["id"]), "PATCH",
                     {"body": body})
        return "updated"
    api.call("/issues/" + str(number) + "/comments", "POST", {"body": body})
    return "created"


def labels_update(api, number, desired):
    issue = api.call("/issues/" + str(number))
    existing = {item["name"] for item in issue.get("labels", [])}
    additions = desired - existing
    removals = (existing & set(LABELS)) - desired
    for name in sorted(additions):
        try:
            api.call("/labels/" + urllib.parse.quote(name, safe=""))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            color, description = LABELS[name]
            api.call("/labels", "POST", {"name": name, "color": color,
                                         "description": description})
    if additions:
        api.call("/issues/" + str(number) + "/labels", "POST",
                 {"labels": sorted(additions)})
    for name in sorted(removals):
        api.call("/issues/" + str(number) + "/labels/"
                 + urllib.parse.quote(name, safe=""), "DELETE")
    return additions, removals


def process(api, event):
    run = event["workflow_run"]
    check(event.get("repository", {}).get("full_name") == api.repo,
          "Unexpected event repository")
    check(run.get("repository", {}).get("full_name") == api.repo
          and run.get("name") == SCANNER_WORKFLOW
          and run.get("event") == "pull_request"
          and run.get("status") == "completed",
          "Not a completed scanner PR workflow")
    if run.get("head_repository", {}).get("full_name") != api.repo:
        return "Fork PR: privileged reporting skipped by policy"
    associations = run.get("pull_requests") or []
    check(len(associations) == 1, "Ambiguous pull request association")
    number = associations[0]["number"]
    if not is_current(api, run, number):
        return "Closed or superseded PR, no writes"
    pr = api.call("/pulls/" + str(number))
    merge_sha = pr.get("merge_commit_sha")
    check(bool(SHA_RE.fullmatch(merge_sha or "")), "Missing merge test commit identity")
    protected = api.call("/branches/dev")
    check(protected.get("protected"), "dev must be protected")
    scans = None
    if run.get("conclusion") == "success" and trusted_scanner(
            api, run, protected["commit"]["sha"]):
        try:
            scans = load_scans(api, run, merge_sha)
        except (EvidenceError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
                urllib.error.HTTPError):
            scans = None
    baseline_status, baseline_data, baseline_run = "unavailable", None, None
    if scans is not None:
        try:
            baseline_status, baseline_data, baseline_run = trusted_baseline(api, run)
        except (EvidenceError, KeyError, ValueError, urllib.error.HTTPError):
            baseline_status = "invalid"
    labels, deltas = classify(scans, baseline_data)
    if scans is None:
        baseline_status = "not evaluated"
    report = render(pr, run, scans, baseline_status, baseline_run, deltas)
    if not is_current(api, run, number):
        return "Superseded while validating, no writes"
    comment_upsert(api, number, report)
    labels_update(api, number, labels)
    return "Published Trivy advisory result for PR #" + str(number)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    args = parser.parse_args()
    api = Github(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    with open(args.event, encoding="utf-8") as source:
        event = json.load(source)
    print(process(api, event))


if __name__ == "__main__":
    main()
