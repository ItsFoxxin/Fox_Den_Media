"""Safe Trivy Phase 2 synthetic fixtures; no production dependency changes."""

import io
import json
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

from scripts import trivy_pr_reporting as r
from scripts.trivy_report import normalized_findings, summarize

HEAD = "a" * 40
MERGE = "b" * 40
BASE = "c" * 40


def sample(component="portal", vuln=None, source=MERGE):
    report = {
        "ArtifactType": "container_image",
        "ArtifactName": "foxden-ci-" + component + ":" + source,
        "Metadata": {"ImageID": "sha256:" + "d" * 64},
        "Trivy": {"Version": "0.76.2"},
        "Results": [{"Type": "debian", "Target": "debian", "Vulnerabilities": vuln or []}],
    }
    rows = normalized_findings(report)
    info = summarize(component, report["ArtifactName"], report["Metadata"]["ImageID"],
                     source, rows)
    baseline = {"component": component, "image": info["image"],
                "image_id": info["image_id"], "source_sha": source, "findings": rows}
    version = {"Version": "0.76.2",
               "VulnerabilityDB": {"UpdatedAt": "2026-11-07T20:00:00Z"}}
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.7", "components": []}
    files = {"vulnerabilities.json": report, "summary.json": info,
             "baseline.json": baseline, "sbom.cdx.json": sbom,
             "trivy-version.json": version}
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, json.dumps(data))
    result = r.verify_artifact(memory.getvalue(), component, source)
    result["url"] = "https://github.com/ItsFoxxin/Fox_Den_Media/actions/runs/8/artifacts/9"
    return result, memory.getvalue(), files


def finding(code, severity, fixed=""):
    return {"VulnerabilityID": code, "PkgName": "fixture",
            "InstalledVersion": "1.0", "Severity": severity, "FixedVersion": fixed}


def scans(items=None):
    return {component: sample(component, (items or {}).get(component))[0]
            for component in r.COMPONENTS}


class TrivyPhase2Tests(unittest.TestCase):
    def test_clean_scan_has_zero_findings(self):
        s = scans()
        self.assertEqual(s["portal"]["summary"]["total"], 0)
        self.assertEqual(r.classify(s, s)[0], set())

    def test_high_and_critical_new_findings(self):
        after = scans({"portal": [finding("CVE-TEST-1", "CRITICAL", "2.0")],
                       "music": [finding("CVE-TEST-2", "HIGH")]})
        labels, delta = r.classify(after, scans())
        self.assertEqual(labels, {"security: review-required", "security: new-critical",
                                  "security: new-high"})
        self.assertEqual(len(delta["portal"]["new"]), 1)
        self.assertEqual(len(delta["music"]["new"]), 1)

    def test_resolved_findings_do_not_generate_new_label(self):
        old = scans({"portal": [finding("CVE-TEST-OLD", "CRITICAL")]})
        labels, changes = r.classify(scans(), old)
        self.assertEqual(labels, set())
        self.assertEqual(len(changes["portal"]["resolved"]), 1)

    def test_missing_baseline_cannot_imply_clean(self):
        labels, delta = r.classify(scans(), None)
        self.assertEqual(labels, {"security: review-required"})
        self.assertFalse(delta)

    def test_missing_scan_cannot_imply_clean(self):
        self.assertEqual(r.classify(None, scans())[0],
                         {"security: review-required"})

    def test_severity_escalation_same_vulnerability_identity(self):
        old = scans({"media": [finding("CVE-TEST", "MEDIUM")]})
        new = scans({"media": [finding("CVE-TEST", "CRITICAL")]})
        labels, delta = r.classify(new, old)
        self.assertIn("security: new-critical", labels)
        self.assertEqual(len(delta["media"]["escalated"]), 1)

    def test_bad_image_identity_is_rejected(self):
        _, zipped, files = sample()
        files["summary.json"]["image_id"] = "sha256:invalid"
        self.assertNotEqual(files["summary.json"]["image_id"],
                            files["vulnerabilities.json"]["Metadata"]["ImageID"])
        self.assertRaises(r.EvidenceError, r.verify_artifact, zipped, "music", MERGE)

    def test_wrong_source_sha_rejected(self):
        _, zipped, _ = sample(source=HEAD)
        self.assertRaises(r.EvidenceError, r.verify_artifact, zipped, "portal", MERGE)

    def test_corrupt_zip_rejected(self):
        with self.assertRaises(zipfile.BadZipFile):
            r.verify_artifact(b"garbage", "portal", MERGE)

    def test_duplicate_zip_member_rejected(self):
        _, zipped, _ = sample()
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            z.writestr("vulnerabilities.json", "{}")
            z.writestr("vulnerabilities.json", "{}")
        with self.assertRaises(r.EvidenceError):
            r.zip_json(data.getvalue(), "vulnerabilities.json")

    def test_valid_artifact_records_db_timestamp(self):
        item, _, _ = sample()
        self.assertEqual(item["version"], "0.76.2")
        self.assertEqual(item["database_updated"], "2026-11-07T20:00:00Z")

    def test_missing_artifacts_do_not_pass(self):
        class API:
            def call(self, path, *args, **kwargs):
                return {"total_count": 0, "artifacts": []}
        with self.assertRaises(r.EvidenceError):
            r.load_scans(API(), {"id": 5, "head_sha": HEAD, "status": "completed",
                                 "conclusion": "success"}, MERGE)

    def test_workflow_failure_is_not_accepted_as_scan(self):
        class API:
            pass
        with self.assertRaises(r.EvidenceError):
            r.load_scans(API(), {"conclusion": "failure"}, MERGE)

    def test_safe_comment_has_marker_and_no_full_cve_inventory(self):
        event_run = {"id": 123, "head_sha": HEAD,
                     "repository": {"full_name": "ItsFoxxin/Fox_Den_Media"}}
        result = r.render({"number": 44}, event_run, scans(), "missing", None, {})
        self.assertIn(r.MARKER, result)
        self.assertIn("N/A", result)
        self.assertIn("advisory", result)
        self.assertIn("JSON + SBOM", result)

    def test_comment_created_once_then_updated(self):
        calls = []
        existing = []
        class API:
            def call(self, path, method="GET", payload=None):
                calls.append((path, method))
                if "/comments?" in path:
                    return list(existing)
                if method == "POST":
                    existing.append({"id": 99, "body": payload["body"],
                                     "user": {"login": "github-actions[bot]"}})
                if method == "PATCH":
                    existing[0]["body"] = payload["body"]
        api = API()
        self.assertEqual(r.comment_upsert(api, 42, r.MARKER + " first"), "created")
        self.assertEqual(r.comment_upsert(api, 42, r.MARKER + " first"), "updated")
        self.assertEqual(r.comment_upsert(api, 42, r.MARKER + " second"), "updated")
        self.assertEqual(sum(method == "POST" for _, method in calls), 1)
        self.assertEqual(sum(method == "PATCH" for _, method in calls), 1)

    def test_human_marker_comment_is_not_modified(self):
        calls = []
        class API:
            def call(self, path, method="GET", payload=None):
                calls.append(method)
                if "/comments?" in path:
                    return [{"id": 1, "body": r.MARKER,
                             "user": {"login": "human"}}]
        api = API()
        self.assertEqual(r.comment_upsert(api, 7, r.MARKER + " update"), "created")
        self.assertIn("POST", calls)
        self.assertNotIn("PATCH", calls)

    def test_label_update_preserves_non_owned_labels(self):
        calls = []
        class API:
            def call(self, path, method="GET", payload=None):
                calls.append((path, method, payload))
                if path.startswith("/issues/") and method == "GET":
                    return {"labels": [{"name": "type: feature"},
                                       {"name": "security: new-high"},
                                       {"name": "needs-testing"}]}
                return {}
        additions, removals = r.labels_update(API(), 11, set())
        self.assertEqual(additions, set())
        self.assertEqual(removals, {"security: new-high"})
        self.assertTrue(any("security%3A%20new-high" in path or
                            "security%3A%20new-high" in str(path)
                            for path, method, _ in calls if method == "DELETE"))
        self.assertFalse(any("type:" in path and method == "DELETE"
                             for path, method, _ in calls))

    def test_duplicate_label_addition_is_idempotent(self):
        calls = []
        class API:
            def call(self, path, method="GET", payload=None):
                calls.append((path, method))
                if path.startswith("/issues/") and method == "GET":
                    return {"labels": [{"name": "security: review-required"}]}
        r.labels_update(API(), 11, {"security: review-required"})
        self.assertFalse(any(method != "GET" for _, method in calls))

    def test_fork_run_is_skipped_without_api_writes(self):
        class API:
            repo = "ItsFoxxin/Fox_Den_Media"
            def call(self, *args, **kwargs):
                raise AssertionError("Fork PR must not require API access")
        run = {"name": r.SCANNER_WORKFLOW, "event": "pull_request",
               "status": "completed",
               "repository": {"full_name": API.repo},
               "head_repository": {"full_name": "another/repository"}}
        event = {"repository": {"full_name": API.repo}, "workflow_run": run}
        self.assertIn("Fork", r.process(API(), event))

    def test_superseded_and_closed_pr_cannot_publish(self):
        calls = []
        class API:
            def call(self, path, *args, **kwargs):
                calls.append(path)
                if path.startswith("/pulls/"):
                    return {"state": "closed", "head": {"sha": HEAD}}
        current = r.is_current(API(), {"head_sha": HEAD, "workflow_id": 1}, 8)
        self.assertFalse(current)
        self.assertEqual(calls, ["/pulls/8"])

    def test_api_failure_does_not_create_fake_comment(self):
        class API:
            def call(self, path, method="GET", payload=None):
                raise urllib.error.HTTPError("url", 403, "No permission", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            r.comment_upsert(API(), 8, r.MARKER)

    def test_cross_component_baseline_disallowed(self):
        original = scans()
        wrong = scans()
        wrong["portal"]["baseline"]["component"] = "media"
        with self.assertRaises(ValueError):
            r.classify(original, wrong)


if __name__ == "__main__":
    unittest.main()
