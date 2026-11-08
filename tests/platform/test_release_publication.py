"""R5 release publication: offline malicious/missing-evidence regressions.

No network, Docker, GHCR, tags, GitHub Releases or NAS access is exercised.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "r5", ROOT / "scripts" / "release_publication.py")
R5 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(R5)

SHA = "a" * 40
R4 = 12345
R3 = 98765
DIGESTS = {x: "sha256:" + letter * 64
           for x, letter in (("portal", "b"), ("music", "c"), ("media", "d"))}
COMPONENTS = ["portal", "music", "media"]


def make_bundle(folder: Path) -> tuple[dict, dict]:
    images = []
    for component in COMPONENTS:
        images.append({
            "kind": "first-party", "component": component,
            "name": R5.FIRST_PARTY[component], "digest": DIGESTS[component],
            "source_sha": SHA, "candidate_tag": "sha-" + SHA,
            "platform": "linux/amd64", "security_decision": "pass",
            "sbom": "sboms/" + component + ".spdx.json",
            "provenance": "provenance/" + component + ".json",
            "vulnerability_report": "reports/" + component + "-trivy.json",
        })
    images.append({
        "kind": "upstream", "component": "nginx",
        "name": "docker.io/library/nginx", "digest": "sha256:" + "e" * 64,
        "platform": "linux/amd64", "security_decision": "pass",
        "approved_upstream": True,
    })
    lock = {
        "schema_version": 1, "version": "1.0.0", "source_sha": SHA,
        "r3_run_id": R3, "r4_run_id": R4, "compose_sha256": "f" * 64,
        "images": images, "music_worker_digest": DIGESTS["music"],
        "profiles": ["music", "media", "managed", "browser", "jellyfin"],
        "rollback": {"verified": True, "lock_sha256": "9" * 64},
    }
    (folder / "release-lock.json").write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    lock_sha = R5.hash_file(folder / "release-lock.json")
    notes = "# Fox Den Media v1.0.0\n\n"
    for heading in R5.NOTE_HEADINGS:
        notes += "## " + heading + "\n\nVerified release information.\n\n"
    notes += "Main source: " + SHA + "\nRelease lock SHA-256: " + lock_sha + "\n"
    for component in COMPONENTS:
        notes += R5.FIRST_PARTY[component] + "@" + DIGESTS[component] + "\n"
    (folder / "release-notes.md").write_text(notes, encoding="utf-8")
    for image in images[:3]:
        for field in ("sbom", "provenance", "vulnerability_report"):
            dest = folder / image[field]
            dest.parent.mkdir(exist_ok=True)
            dest.write_text(json.dumps({"fixture": field}), encoding="utf-8")
    checksum_files = [p for p in folder.rglob("*") if p.is_file()]
    files = {str(p.relative_to(folder)): R5.hash_file(p) for p in checksum_files}
    verified = {
        "schema_version": 1, "version": "1.0.0", "source_sha": SHA,
        "r4_run_id": R4, "r3_run_id": R3, "decision": "pass",
        "security_policy_result": "pass", "no_rebuild_integration": "passed",
        "security_policy_version": "fixture-policy-1", "high_critical_unaccepted": 0,
        "source_promotion_approval": {
            "decision": "approved", "approved_by": "ItsFoxxin",
            "source_sha": SHA,
            "record_url": "https://github.com/ItsFoxxin/Fox_Den_Media/issues/123",
        },
        "github_security_review": "pass", "unapproved_security_findings": 0,
        "exceptions": [], "files": files,
    }
    (folder / "verification.json").write_text(
        json.dumps(verified, indent=2) + "\n", encoding="utf-8")
    return lock, verified


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lock, self.verified = make_bundle(self.root)

    def update_verification(self, **updates):
        self.verified.update(updates)
        (self.root / "verification.json").write_text(
            json.dumps(self.verified), encoding="utf-8")

    def update_lock(self, **updates):
        self.lock.update(updates)
        (self.root / "release-lock.json").write_text(
            json.dumps(self.lock), encoding="utf-8")
        self.verified["files"]["release-lock.json"] = R5.hash_file(
            self.root / "release-lock.json")
        self.update_verification()

    def assert_blocked(self):
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_bundle(self.root, SHA, R4)

    def test_clean_verified_artifacts_pass(self):
        summary = R5.validate_bundle(self.root, SHA, R4)
        self.assertEqual(summary["lock"]["music_worker_digest"], DIGESTS["music"])

    def test_missing_release_artifact_fails(self):
        (self.root / "sboms/portal.spdx.json").unlink()
        self.assert_blocked()

    def test_modified_release_artifact_fails(self):
        (self.root / "reports/media-trivy.json").write_text("tampered")
        self.assert_blocked()

    def test_unlisted_evidence_fails(self):
        (self.root / "extra.txt").write_text("unexpected")
        self.assert_blocked()

    def test_symlink_evidence_fails(self):
        target = self.root / "reports/music-trivy.json"
        target.unlink()
        target.symlink_to(self.root / "reports/media-trivy.json")
        self.assert_blocked()

    def test_missing_or_wrong_source_promotion_approval_fails(self):
        self.update_verification(source_promotion_approval={})
        self.assert_blocked()
        self.update_verification(source_promotion_approval={
            "decision": "approved", "approved_by": "ItsFoxxin",
            "source_sha": "0" * 40,
            "record_url": "https://github.com/ItsFoxxin/Fox_Den_Media/issues/123",
        })
        self.assert_blocked()

    def test_original_policy_cannot_bypass_adopted_order(self):
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_adopted_policy("old checklist: stabilize before source promotion")
        R5.validate_adopted_policy(
            "PR #63\nBefore source promotion\n"
            "After independent source-promotion approval\n"
            "Before NAS production cutover\nAfter authorized cutover\n")

    def test_wrong_source_fails(self):
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_bundle(self.root, "0" * 40, R4)

    def test_wrong_r4_run_fails(self):
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_bundle(self.root, SHA, R4 + 1)

    def test_unaccepted_critical_fails(self):
        self.update_verification(high_critical_unaccepted=1)
        self.assert_blocked()

    def test_native_security_alerts_must_be_dispositioned(self):
        self.update_verification(github_security_review="unknown")
        self.assert_blocked()
        self.update_verification(github_security_review="pass",
                                 unapproved_security_findings=2)
        self.assert_blocked()

    def test_failed_policy_fails(self):
        self.update_verification(security_policy_result="failed")
        self.assert_blocked()

    def test_no_rebuild_evidence_missing_fails(self):
        self.update_verification(no_rebuild_integration="unknown")
        self.assert_blocked()

    def test_invalid_signature_status_fails(self):
        self.lock["images"][0]["security_decision"] = "unknown"
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_music_web_worker_must_share_digest(self):
        self.update_lock(music_worker_digest="sha256:" + "0" * 64)
        self.assert_blocked()

    def test_missing_first_party_image_fails(self):
        self.lock["images"] = self.lock["images"][1:]
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_mutable_digest_fails(self):
        self.lock["images"][0]["digest"] = "latest"
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_unapproved_upstream_fails(self):
        self.lock["images"][-1]["approved_upstream"] = False
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_wrong_platform_fails(self):
        self.lock["images"][0]["platform"] = "linux/armv7"
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_unverified_rollback_fails(self):
        self.update_lock(rollback={"verified": False, "lock_sha256": "9" * 64})
        self.assert_blocked()

    def test_expired_security_exception_fails(self):
        self.update_verification(exceptions=[{
            "issue": 70, "approved_by": "ItsFoxxin",
            "expires_at": "2020-01-01T00:00:00Z",
        }])
        self.assert_blocked()

    def test_unknown_exception_approver_fails(self):
        self.update_verification(exceptions=[{
            "issue": 70, "expires_at": "2099-01-01T00:00:00Z",
        }])
        self.assert_blocked()

    def test_missing_release_notes_section_fails(self):
        path = self.root / "release-notes.md"
        path.write_text(path.read_text().replace("## Rollback", "## Other"))
        self.verified["files"]["release-notes.md"] = R5.hash_file(path)
        self.update_verification()
        self.assert_blocked()

    def test_unfinished_notes_fails(self):
        path = self.root / "release-notes.md"
        path.write_text(path.read_text() + "TODO: add details\n")
        self.verified["files"]["release-notes.md"] = R5.hash_file(path)
        self.update_verification()
        self.assert_blocked()

    def test_output_assets_with_sha256_sums(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch)
            R5.stage_assets(self.root, out)
            self.assertTrue((out / "assets.sha256").is_file())
            self.assertTrue((out / "release-lock.json").is_file())
            self.assertTrue((out / "sboms--portal.spdx.json").is_file())
            with self.assertRaises(R5.ReleaseBlocked):
                R5.stage_assets(self.root, out)

    def test_idempotent_existing_release_verification(self):
        assets = {}
        for path in self.root.rglob("*"):
            if path.is_file():
                assets[str(path.relative_to(self.root)).replace("/", "--")] = R5.hash_file(path)
        lines = "".join(h + "  " + n + "\n" for n, h in sorted(assets.items()))
        assets["assets.sha256"] = hashlib.sha256(lines.encode()).hexdigest()
        tag_ref = {"ref": "refs/tags/v1.0.0",
                   "object": {"type": "tag", "sha": "f" * 40}}
        annotated = {"tag": "v1.0.0", "object": {"type": "commit", "sha": SHA}}
        release = {"tag_name": "v1.0.0", "draft": False, "prerelease": False,
                   "body": "Main " + SHA,
                   "assets": [{"name": n, "digest": "sha256:" + h}
                              for n, h in assets.items()]}
        R5.verify_published_records(tag_ref, annotated, release, SHA, assets)
        R5.verify_published_records(tag_ref, annotated, release, SHA, assets)
        release["assets"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(R5.ReleaseBlocked):
            R5.verify_published_records(tag_ref, annotated, release, SHA, assets)
        release["assets"][0]["digest"] = "sha256:" + next(iter(assets.values()))
        annotated["object"]["sha"] = "0" * 40
        with self.assertRaises(R5.ReleaseBlocked):
            R5.verify_published_records(tag_ref, annotated, release, SHA, assets)


class ExternalGateTests(unittest.TestCase):
    def test_r4_workflow_identity_matches_r3_r4_workstream(self):
        self.assertEqual(R5.R4_WORKFLOW, ".github/workflows/ghcr-verify.yml")
        self.assertEqual(
            R5.R3_WORKFLOW,
            "ItsFoxxin/Fox_Den_Media/.github/workflows/ghcr-candidates.yml",
        )
        good = {
            "id": R4, "repository": {"full_name": R5.REPOSITORY},
            "path": R5.R4_WORKFLOW, "event": "workflow_dispatch",
            "head_branch": "main", "head_sha": SHA,
            "status": "completed", "conclusion": "success",
        }
        R5.validate_r4_run(good, SHA, R4)
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_r4_run(
                dict(good, path=".github/workflows/release-verify.yml"), SHA, R4
            )

    def test_required_checks_all_success(self):
        items = {"check_runs": [
            {"name": name, "status": "completed",
             "conclusion": "success", "head_sha": SHA}
            for name in R5.REQUIRED_CHECKS
        ]}
        R5.validate_checks(items, SHA)
        for index in range(len(items["check_runs"])):
            test = json.loads(json.dumps(items))
            test["check_runs"][index]["conclusion"] = "failure"
            with self.assertRaises(R5.ReleaseBlocked):
                R5.validate_checks(test, SHA)

    def test_missing_stale_or_skipped_checks_fail(self):
        checks = {"check_runs": [
            {"name": name, "status": "completed",
             "conclusion": "success", "head_sha": SHA}
            for name in R5.REQUIRED_CHECKS
        ]}
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_checks({"check_runs": checks["check_runs"][:2]}, SHA)
        checks["check_runs"][0]["head_sha"] = "0" * 40
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_checks(checks, SHA)
        checks["check_runs"][0]["head_sha"] = SHA
        checks["check_runs"][0]["conclusion"] = "skipped"
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_checks(checks, SHA)

    def test_existing_release_tag_or_release_blocks_publication(self):
        R5.validate_release_absence(None, None)
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_release_absence(
                {"ref": "refs/tags/v1.0.0"}, None)
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_release_absence(
                None, {"tag_name": "v1.0.0"})

    def test_open_release_blocker_fails(self):
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_blockers([{"number": 18, "state": "open"}])
        R5.validate_blockers([{"number": 18, "state": "closed"}])

    def test_mismatched_or_untrusted_r4_run_fails(self):
        good = {
            "id": R4, "repository": {"full_name": R5.REPOSITORY},
            "path": R5.R4_WORKFLOW, "event": "workflow_dispatch",
            "head_branch": "main", "head_sha": SHA,
            "status": "completed", "conclusion": "success",
        }
        R5.validate_r4_run(good, SHA, R4)
        for field, replacement in (
            ("path", ".github/workflows/other.yml"),
            ("event", "pull_request"),
            ("head_branch", "dev"),
            ("head_sha", "0" * 40),
            ("conclusion", "failure"),
        ):
            tampered = dict(good, **{field: replacement})
            with self.subTest(field=field), self.assertRaises(R5.ReleaseBlocked):
                R5.validate_r4_run(tampered, SHA, R4)

    def test_owner_approval_requires_exact_fresh_statement(self):
        statement = ("APPROVE_FOXDEN_RELEASE v1.0.0 main=" + SHA +
                     " lock_sha256=" + "f" * 64 + " r4_run_id=" + str(R4))
        approval = {"user": {"login": "ItsFoxxin"}, "body": statement,
                    "created_at": "2026-11-08T01:10:00Z"}
        R5.validate_approval([approval], "ItsFoxxin", SHA, "f" * 64, R4,
                             "2026-11-08T01:00:00Z")
        for altered in (
            dict(approval, user={"login": "OtherUser"}),
            dict(approval, body="Approved"),
            dict(approval, created_at="2026-11-07T01:00:00Z"),
        ):
            with self.assertRaises(R5.ReleaseBlocked):
                R5.validate_approval([altered], "ItsFoxxin", SHA, "f" * 64, R4,
                                     "2026-11-08T01:00:00Z")
        with self.assertRaises(R5.ReleaseBlocked):
            R5.validate_approval([], "ItsFoxxin", SHA, "f" * 64, R4,
                                 "2026-11-08T01:00:00Z")

    def test_registry_manifest_tag_drift_blocks(self):
        lock = {"images": [{
            "kind": "first-party", "name": R5.FIRST_PARTY["portal"],
            "digest": DIGESTS["portal"], "candidate_tag": "sha-" + SHA,
        }]}
        with patch.object(R5, "run_command", side_effect=[
            "Name: x\nDigest: " + DIGESTS["portal"],
            "Name: x\nDigest: sha256:" + "1" * 64,
        ]):
            with self.assertRaises(R5.ReleaseBlocked):
                R5.verify_registry(lock, SHA)

    def test_provenance_verification_is_mandatory(self):
        lock = {"images": [{
            "kind": "first-party", "name": R5.FIRST_PARTY["portal"],
            "digest": DIGESTS["portal"], "candidate_tag": "sha-" + SHA,
        }]}
        with patch.object(R5, "run_command", side_effect=[
            "Name: x\nDigest: " + DIGESTS["portal"],
            "Name: x\nDigest: " + DIGESTS["portal"],
            R5.ReleaseBlocked("missing cryptographic provenance"),
        ]):
            with self.assertRaises(R5.ReleaseBlocked):
                R5.verify_registry(lock, SHA)

    def test_workflow_is_manual_and_has_no_production_access(self):
        workflow = (ROOT / ".github/workflows/release-publish.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^  (push|release|registry_package):")
        self.assertIn("name: release-publication", workflow)
        self.assertIn("RELEASE_PUBLICATION_ARMED", workflow)
        self.assertNotIn("production-nas", workflow)
        self.assertNotIn("ssh ", workflow)
        self.assertNotIn("docker compose up", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("packages: write", workflow)


if __name__ == "__main__":
    unittest.main()
