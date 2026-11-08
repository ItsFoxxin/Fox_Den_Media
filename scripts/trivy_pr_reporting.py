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
    check(isinstance(version.get("Version"), str) and version["Version"],
          "Missing Trivy version")
    rows = normalized_findings(report)
    check(rows == baseline.get("findings"), "Source findings do not match baseline")
    check(summarize(component, image, image_id, source_sha, rows) == summary,
          "Summary count mismatch")
    db = version.get("VulnerabilityDB") or {}
    return {"summary": summary, "baseline": baseline, "version": version["Version"],
            "database_updated": db.get("UpdatedAt")}


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
    for file_path in (".github/workflows/trivy.yml", "scripts/install_trivy.sh"):
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
        except (EvidenceError, KeyError, ValueError, urllib.error.HTTPError):
            return "invalid", None, candidate
    return "invalid", None, None
