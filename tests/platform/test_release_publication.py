"""R5 release publication: offline malicious/missing-evidence regressions.

No network, Docker, GHCR, tags, GitHub Releases or NAS access is exercised.
"""
from __future__ import annotations

import datetime as dt
import base64
import os
import hashlib
import importlib.util
import json
import shutil
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
    """Representative strict R2 images map plus separate R4 evidence."""
    images = {}
    evidence = {}
    for component in COMPONENTS:
        images[component] = {
            "ref": R5.FIRST_PARTY[component] + "@" + DIGESTS[component],
            "platform": "linux/amd64",
            "platform_digest": DIGESTS[component].split(":", 1)[1],
            "source_sha": SHA,
        }
        evidence[component] = {
            "candidate_tag": "sha-" + SHA,
            "security_decision": "pass",
            "ref": images[component]["ref"],
            "platform_digest": images[component]["platform_digest"],
            "sbom": "reports/" + component + ".sbom.spdx.json",
            "provenance": "provenance/" + component + ".json",
            "vulnerability_report": "reports/" + component + ".vuln.json",
        }
    images["nginx"] = {
        "ref": "docker.io/library/nginx@sha256:" + "e" * 64,
        "platform": "linux/amd64",
        "platform_digest": "e" * 64,
        "source_sha": None,
    }
    evidence["nginx"] = {
        "approved_upstream": True, "security_decision": "pass",
        "ref": images["nginx"]["ref"],
        "platform_digest": images["nginx"]["platform_digest"],
        "provenance": "provenance/nginx.json",
        "sbom": "reports/nginx.sbom.spdx.json",
        "vulnerability_report": "reports/nginx.vuln.json",
    }
    lock = {
        "schema_version": 1, "version": "1.0.0",
        "source_sha": SHA, "compose_sha256": "f" * 64,
        "platform": "linux/amd64", "profiles": ["music", "media"],
        "images": images,
        "services": {
            "ingress": "nginx", "portal": "portal", "music": "music",
            "music-worker": "music", "media": "media",
        },
        "publisher": {
            "workflow": "ghcr-candidates.yml",
            "run_id": R3, "source_sha": SHA,
        },
        "rollback": {"version": "0.9.6", "lock_sha256": "9" * 64},
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
    for item in evidence.values():
        for key in ("sbom", "provenance", "vulnerability_report"):
            if key not in item:
                continue
            dest = folder / item[key]
            dest.parent.mkdir(exist_ok=True)
            dest.write_text(json.dumps({"fixture": key}), encoding="utf-8")
    # Synthetic R4-v2 review: structurally authentic, NOT a real signature.
    # PR #93's separate Ed25519 verifier is required at actual R5 publication.
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    stamp = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
    review_doc = {
        "schema_version": 1, "repository": R5.REPOSITORY,
        "source_sha": SHA, "producer_actor": "github:scan-producer",
        "release_lock_sha256": "sha256:" + lock_sha,
        "r3_run_id": R3, "scan_run_id": 34567,
        "created_at": stamp(now - dt.timedelta(hours=3)),
        "reviewed_at": stamp(now - dt.timedelta(hours=2)),
        "expires_at": stamp(now + dt.timedelta(days=7)),
        "records": [],
    }
    integration = folder / "integration"
    integration.mkdir()
    (integration / "security-dispositions.json").write_text(
        json.dumps(review_doc), encoding="utf-8")
    (integration / "security-disposition-signatures.json").write_text(
        json.dumps({"schema_version": 1, "document_sha256":
                    R5.canonical_hash(review_doc), "signatures": []}),
        encoding="utf-8")
    review_output = {
        "schema_version": 1, "decision": "pass",
        "disposition_document_sha256": R5.canonical_hash(review_doc),
        "lifecycle_sha256": "sha256:" + "1" * 64,
        "source_sha": SHA, "release_lock_sha256": "sha256:" + lock_sha,
        "r3_run_id": R3, "scan_run_id": review_doc["scan_run_id"],
        "reviewed_at": review_doc["reviewed_at"],
        "expires_at": review_doc["expires_at"],
        "cleared_finding_count": 0, "image_count": len(images),
    }
    (integration / "disposition-verification.json").write_text(
        json.dumps(review_output), encoding="utf-8")
    review = {
        "schema_version": 1, "artifact_name": R5.REVIEW_ARTIFACT,
        "verification_file": "integration/disposition-verification.json",
        "verification_sha256": "sha256:" + R5.hash_file(
            integration / "disposition-verification.json"),
        "dispositions_sha256": R5.canonical_hash(review_doc),
        "review_workflow": R5.REVIEW_WORKFLOW,
        "review_run_id": 45678,
        "verified_at": stamp(now - dt.timedelta(hours=1)),
    }
    security_review = dict(review, verification_file="disposition-verification.json")
    (folder / "security-contract.json").write_text(
        json.dumps({"schema_version": 2, "disposition_review": security_review}),
        encoding="utf-8")
    for name in ("scanner.json", "rendered-release-compose.json"):
        (folder / name).write_text(json.dumps({"fixture": name}), encoding="utf-8")
    records = [p for p in folder.rglob("*") if p.is_file()]
    files = {str(p.relative_to(folder)): R5.hash_file(p) for p in records}
    verified = {
        "schema_version": 1, "version": "1.0.0", "source_sha": SHA,
        "r4_run_id": R4, "r3_run_id": R3,
        "decision": "pass", "rollback_verified": True,
        "security_policy_result": "pass", "no_rebuild_integration": "passed",
        "security_policy_version": "v1:" + "9" * 64,
        "high_critical_unaccepted": 0,
        "source_promotion_approval": {
            "decision": "approved", "approved_by": "ItsFoxxin",
            "source_sha": SHA,
            "record_url": "https://github.com/ItsFoxxin/Fox_Den_Media/issues/123",
        },
        "github_security_review": "pass", "unapproved_security_findings": 0,
        "image_evidence": evidence,
        "exceptions": [], "files": files,
        "disposition_review": review,
    }
    (folder / "verification.json").write_text(
        json.dumps(verified, indent=2) + "\n", encoding="utf-8")
    refresh_manifest(folder, verified)
    return lock, verified


def refresh_manifest(folder: Path, verified: dict) -> dict:
    files = dict(verified["files"])
    files["verification.json"] = R5.hash_file(folder / "verification.json")
    manifest = {
        "schema_version": R5.RELEASE_READY_SCHEMA,
        "version": "1.0.0",
        "repository": R5.REPOSITORY,
        "workflow": R5.R4_WORKFLOW,
        "source_sha": SHA,
        "r3_run_id": R3,
        "r4_run_id": R4,
        "files": files,
    }
    (folder / "release-ready.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


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
        refresh_manifest(self.root, self.verified)

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


    def refresh_review(self, *, document=None, result=None, binding=None):
        """Rehash synthetic evidence; never invents genuine signatures."""
        doc_path = self.root / "integration/security-dispositions.json"
        result_path = self.root / "integration/disposition-verification.json"
        if document is None:
            document = R5.read_json(doc_path)
        doc_path.write_text(json.dumps(document), encoding="utf-8")
        result = result or R5.read_json(result_path)
        result["disposition_document_sha256"] = R5.canonical_hash(document)
        result["source_sha"] = document["source_sha"]
        result["reviewed_at"] = document["reviewed_at"]
        result["expires_at"] = document["expires_at"]
        result_path.write_text(json.dumps(result), encoding="utf-8")
        signatures = self.root / "integration/security-disposition-signatures.json"
        statement = R5.read_json(signatures)
        statement["document_sha256"] = R5.canonical_hash(document)
        signatures.write_text(json.dumps(statement), encoding="utf-8")
        b = binding or self.verified["disposition_review"]
        b["dispositions_sha256"] = R5.canonical_hash(document)
        b["verification_sha256"] = "sha256:" + R5.hash_file(result_path)
        security_path = self.root / "security-contract.json"
        contract = R5.read_json(security_path)
        contract["disposition_review"] = dict(
            b, verification_file="disposition-verification.json")
        security_path.write_text(json.dumps(contract), encoding="utf-8")
        self.verified["files"].update({
            name: R5.hash_file(self.root / name)
            for name in (
                "integration/security-dispositions.json",
                "integration/security-disposition-signatures.json",
                "integration/disposition-verification.json",
                "security-contract.json",
            )
        })
        self.update_verification(disposition_review=b)

    def test_review_expired_after_r4_acceptance_fails(self):
        doc = R5.read_json(self.root / "integration/security-dispositions.json")
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        stamp = lambda x: x.strftime("%Y-%m-%dT%H:%M:%SZ")
        doc["created_at"] = stamp(now - dt.timedelta(days=6))
        doc["reviewed_at"] = stamp(now - dt.timedelta(days=5))
        doc["expires_at"] = stamp(now - dt.timedelta(minutes=1))
        self.refresh_review(document=doc)
        self.assert_blocked()

    def test_signed_review_v1_fallback_never_allowed(self):
        contract = self.root / "security-contract.json"
        value = R5.read_json(contract)
        value["schema_version"] = 1
        contract.write_text(json.dumps(value), encoding="utf-8")
        self.verified["files"]["security-contract.json"] = R5.hash_file(contract)
        self.update_verification()
        self.assert_blocked()

    def test_signed_review_binding_wrong_run_or_hash_fails(self):
        for changed in (
            {"review_run_id": -1}, {"review_workflow": ".github/workflows/other.yml"},
            {"dispositions_sha256": "sha256:" + "0" * 64},
            {"verification_file": "disposition-verification.json"},
        ):
            with self.subTest(changed=changed):
                old = dict(self.verified["disposition_review"])
                self.update_verification(disposition_review={**old, **changed})
                self.assert_blocked()
                self.update_verification(disposition_review=old)

    def test_missing_or_unsigned_review_parts_fail(self):
        for rel in (
            "integration/disposition-verification.json",
            "integration/security-dispositions.json",
            "integration/security-disposition-signatures.json",
        ):
            with self.subTest(file=rel):
                target = self.root / rel
                data = target.read_bytes()
                target.unlink()
                self.assert_blocked()
                target.write_bytes(data)

    def test_review_original_proof_must_be_in_signed_file_map(self):
        doc = R5.read_json(self.root / "integration/security-dispositions.json")
        proof = {"fixture": "proof"}
        p = self.root / "integration/disposition-proof-case1.json"
        p.write_text(json.dumps(proof))
        doc["records"] = [{
            "status": "FIXED", "subject": {}, "reviewer_id": "github:reviewer",
            "proof_path": "proofs/case1.json",
            "proof_sha256": "sha256:" + R5.hash_file(p),
        }]
        result = R5.read_json(self.root / "integration/disposition-verification.json")
        result["cleared_finding_count"] = 1
        self.refresh_review(document=doc, result=result)
        self.assert_blocked()
        self.verified["files"]["integration/disposition-proof-case1.json"] = R5.hash_file(p)
        self.update_verification()
        R5.validate_bundle(self.root, SHA, R4)
        p.write_text('{"tampered":true}')
        self.assert_blocked()

    def test_clean_verified_artifacts_pass(self):
        summary = R5.validate_bundle(self.root, SHA, R4)
        self.assertEqual(summary["lock"]["services"]["music-worker"], "music")

    def test_legacy_list_shaped_lock_is_not_r2_and_fails(self):
        self.update_lock(images=list(self.lock["images"].values()))
        self.assert_blocked()

    def test_missing_upstream_security_evidence_fails(self):
        del self.verified["image_evidence"]["nginx"]
        self.update_verification()
        self.assert_blocked()

    def test_missing_release_artifact_fails(self):
        (self.root / "reports/portal.sbom.spdx.json").unlink()
        self.assert_blocked()

    def test_modified_release_artifact_fails(self):
        (self.root / "reports/media.vuln.json").write_text("tampered")
        self.assert_blocked()

    def test_unlisted_evidence_fails(self):
        (self.root / "extra.txt").write_text("unexpected")
        self.assert_blocked()

    def test_symlink_evidence_fails(self):
        target = self.root / "reports/music.vuln.json"
        target.unlink()
        target.symlink_to(self.root / "reports/media.vuln.json")
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
        self.verified["image_evidence"]["portal"]["security_decision"] = "unknown"
        self.update_verification()
        self.assert_blocked()

    def test_music_web_worker_must_share_digest(self):
        self.lock["services"]["music-worker"] = "portal"
        self.update_lock(services=self.lock["services"])
        self.assert_blocked()

    def test_missing_first_party_image_fails(self):
        del self.lock["images"]["portal"]
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_mutable_digest_fails(self):
        self.lock["images"]["portal"]["ref"] = R5.FIRST_PARTY["portal"] + ":latest"
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_unapproved_upstream_fails(self):
        self.verified["image_evidence"]["nginx"]["approved_upstream"] = False
        self.update_verification()
        self.assert_blocked()

    def test_wrong_platform_fails(self):
        self.lock["images"]["portal"]["platform"] = "linux/armv7"
        self.update_lock(images=self.lock["images"])
        self.assert_blocked()

    def test_unverified_rollback_fails(self):
        self.update_verification(rollback_verified=False)
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

    def test_release_ready_manifest_wrong_run_source_or_signer_fails(self):
        for key, altered in (
            ("source_sha", "0" * 40),
            ("r3_run_id", R3 + 1),
            ("r4_run_id", R4 + 1),
            ("workflow", ".github/workflows/untrusted.yml"),
            ("repository", "other/repository"),
            ("schema_version", "foxden.r4.release-ready.v2"),
        ):
            with self.subTest(key=key):
                manifest = refresh_manifest(self.root, self.verified)
                manifest[key] = altered
                (self.root / "release-ready.json").write_text(json.dumps(manifest))
                self.assert_blocked()
        refresh_manifest(self.root, self.verified)

    def test_manifest_missing_and_wrong_exact_file_digest_fail(self):
        (self.root / "release-ready.json").unlink()
        self.assert_blocked()
        manifest = refresh_manifest(self.root, self.verified)
        manifest["files"]["release-lock.json"] = "0" * 64
        (self.root / "release-ready.json").write_text(json.dumps(manifest))
        self.assert_blocked()

    def test_unsigned_security_top_level_file_not_optional(self):
        (self.root / "scanner.json").unlink()
        self.assert_blocked()

    def test_wrong_digest_subject_even_with_recomputed_envelope_fails(self):
        self.verified["image_evidence"]["portal"]["ref"] = (
            R5.FIRST_PARTY["portal"] + "@sha256:" + "f" * 64)
        self.update_verification()
        self.assert_blocked()

    def test_reject_unknown_json_keys_and_duplicate_keys(self):
        path = self.root / "release-ready.json"
        path.write_text(path.read_text().replace(
            '"version": "1.0.0",', '"version": "1.0.0", "version": "1.0.0",'))
        self.assert_blocked()
        manifest = refresh_manifest(self.root, self.verified)
        manifest["unknown"] = "unreviewed"
        path.write_text(json.dumps(manifest))
        self.assert_blocked()

    def test_nonempty_security_exceptions_fail_even_if_unexpired(self):
        self.update_verification(exceptions=[{
            "issue": 70, "approved_by": "ItsFoxxin",
            "expires_at": "2099-01-01T00:00:00Z",
        }])
        self.assert_blocked()

    def test_output_assets_with_sha256_sums(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch)
            R5.stage_assets(self.root, out)
            self.assertTrue((out / "assets.sha256").is_file())
            self.assertTrue((out / "release-lock.json").is_file())
            self.assertTrue((out / "reports--portal.sbom.spdx.json").is_file())
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


class SignedEnvelopeTests(unittest.TestCase):
    """Offline validation of the required exact R4 signing verification call."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        make_bundle(self.root)
        self.manifest_digest = R5.hash_file(self.root / "release-ready.json")
        self.r4_run = {
            "id": R4, "run_attempt": 1,
            "repository": {"full_name": R5.REPOSITORY},
            "path": R5.R4_WORKFLOW, "head_branch": "main",
            "head_sha": SHA, "event": "workflow_dispatch",
            "status": "completed", "conclusion": "success",
        }

    def attestation(self, digest=None, invocation=None):
        invocation = invocation or (
            "https://github.com/" + R5.REPOSITORY +
            "/actions/runs/" + str(R4) + "/attempts/1")
        return json.dumps([{"verificationResult": {"statement": {
            "subject": [{"digest": {"sha256":
                digest if digest is not None else self.manifest_digest}}],
            "predicate": {"runDetails": {"metadata": {
                "invocationId": invocation,
            }}},
        }}}])

    def test_verified_signature_requires_exact_repo_workflow_source(self):
        with patch.object(R5, "run_command", side_effect=[
            "gh version 2.102.0 (synthetic)\n", self.attestation()
        ]) as run:
            R5.verify_signed_release_ready(self.root, SHA, R4, run=self.r4_run)
        cmd = run.call_args_list[1].args[0]
        self.assertEqual(cmd[:3], ["gh", "attestation", "verify"])
        for flag, required in (
            ("--repo", R5.REPOSITORY),
            ("--source-ref", "refs/heads/main"),
            ("--source-digest", SHA),
            ("--signer-workflow", R5.R4_SIGNER_WORKFLOW),
            ("--predicate-type", "https://slsa.dev/provenance/v1"),
            ("--format", "json"),
        ):
            self.assertEqual(cmd[cmd.index(flag) + 1], required)

    def test_missing_signature_or_mismatched_signed_digest_fails(self):
        for response in ("[]", "{}", "not-json", self.attestation("f" * 64)):
            with self.subTest(response=response[:40]):
                with patch.object(R5, "run_command", side_effect=[
                    "gh version 2.102.0\n", response,
                ]), self.assertRaises(R5.ReleaseBlocked):
                    R5.verify_signed_release_ready(self.root, SHA, R4, run=self.r4_run)

    def test_r4_signed_manifest_rejects_other_run_attempt(self):
        with patch.object(R5, "run_command", side_effect=[
            "gh version 2.102.0\n",
            self.attestation(invocation="https://github.com/" + R5.REPOSITORY +
                             "/actions/runs/" + str(R4) + "/attempts/2"),
        ]), self.assertRaises(R5.ReleaseBlocked):
            R5.verify_signed_release_ready(self.root, SHA, R4, run=self.r4_run)

    def test_untrusted_attestation_verifier_failure_fails(self):
        with patch.object(R5, "run_command", side_effect=[
            "gh version 2.102.0\n",
            R5.ReleaseBlocked("untrusted signer or missing signature"),
        ]), self.assertRaises(R5.ReleaseBlocked):
            R5.verify_signed_release_ready(self.root, SHA, R4, run=self.r4_run)

    def test_vulnerable_gh_or_missing_manifest_fails(self):
        for version in ("gh version 2.101.0\n", "gh version unknown\n"):
            with patch.object(R5, "run_command", return_value=version):
                with self.assertRaises(R5.ReleaseBlocked):
                    R5.verify_signed_release_ready(self.root, SHA, R4, run=self.r4_run)
        (self.root / "release-ready.json").unlink()
        with self.assertRaises(R5.ReleaseBlocked):
            R5.verify_signed_release_ready(self.root, SHA, R4, run=self.r4_run)



class DispositionContractRuntimeTests(unittest.TestCase):
    """Mocked network/run boundaries. PR #93 owns real Ed25519 test vectors."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "bundle"
        self.root.mkdir()
        self.lock, self.verified = make_bundle(self.root)
        self.summary = R5.validate_bundle(self.root, SHA, R4)
        self.document = self.summary["disposition"]["document"]
        self.scan_id = self.document["scan_run_id"]
        self.review_id = self.summary["disposition"]["binding"]["review_run_id"]

    def mock_run(self, ident, workflow, *, at="2026-11-01T00:00:00Z",
                 actor="scan-producer", inputs=None):
        return {
            "id": ident, "repository": {"full_name": R5.REPOSITORY},
            "head_branch": "main", "head_sha": SHA, "event": "workflow_dispatch",
            "path": workflow, "status": "completed", "conclusion": "success",
            "run_attempt": 1, "actor": {"login": actor},
            "created_at": at, "inputs": inputs or {"source_sha": SHA},
        }

    def chain_runs(self):
        a, b, c = self.scan_id, self.review_id, 56789
        ids = {"publisher_run_id": str(R3), "scan_run_id": str(a),
               "review_run_id": str(b)}
        return {
            R3: self.mock_run(R3, R5.CHAIN_R3),
            a: self.mock_run(a, R5.SCAN_WORKFLOW,
                             at="2026-11-02T00:00:00Z",
                             inputs={"source_sha": SHA, "stage": "collect",
                                     "publisher_run_id": str(R3)}),
            b: self.mock_run(b, R5.REVIEW_WORKFLOW,
                             at="2026-11-03T00:00:00Z",
                             actor="independent-reviewer",
                             inputs={"source_sha": SHA, "r3_run_id": str(R3),
                                     "scan_run_id": str(a)}),
            c: self.mock_run(c, R5.SCAN_WORKFLOW,
                             at="2026-11-04T00:00:00Z",
                             inputs={"source_sha": SHA, "stage": "finalize", **ids}),
            R4: self.mock_run(R4, R5.R4_WORKFLOW,
                              at="2026-11-05T00:00:00Z",
                              inputs={"source_sha": SHA,
                                      "security_run_id": str(c), **ids}),
        }

    def assert_chain(self, runs):
        R5.authenticated_chain(
            source_sha=SHA, r4_run=runs[R4], r3_run=runs[R3],
            scan_run=runs[self.scan_id], review_run=runs[self.review_id],
            final_run=runs[56789], r3_id=R3, scan_id=self.scan_id,
            review_id=self.review_id, final_id=56789,
        )

    def test_authenticate_complete_r3_a_b_c_r4_chain(self):
        self.assert_chain(self.chain_runs())

    def test_reject_stale_misordered_or_wrong_stage_chain(self):
        for ident, field, altered in (
            (R4, "inputs", {"source_sha": SHA, "publisher_run_id": str(R3),
                             "scan_run_id": str(self.scan_id),
                             "review_run_id": str(self.review_id),
                             "security_run_id": "8"}),
            (56789, "inputs", {"source_sha": SHA, "stage": "collect",
                               "publisher_run_id": str(R3),
                               "scan_run_id": str(self.scan_id),
                               "review_run_id": str(self.review_id)}),
            (self.review_id, "created_at", "2026-10-29T00:00:00Z"),
            (R3, "head_sha", "0" * 40),
            (self.scan_id, "inputs", {"source_sha": SHA, "stage": "finalize",
                                      "publisher_run_id": str(R3)}),
            (self.review_id, "actor", {"login": "scan-producer"}),
        ):
            with self.subTest(ident=ident, field=field):
                runs = self.chain_runs()
                runs[ident][field] = altered
                with self.assertRaises(R5.ReleaseBlocked):
                    self.assert_chain(runs)

    def test_disposition_workflow_run_source_and_identity_must_match(self):
        good = self.mock_run(self.review_id, R5.REVIEW_WORKFLOW)
        R5.validate_authenticated_run(good, SHA, self.review_id, R5.REVIEW_WORKFLOW)
        for bad in (
            dict(good, head_sha="0" * 40),
            dict(good, path=R5.SCAN_WORKFLOW),
            dict(good, id=self.review_id + 1),
            dict(good, conclusion="skipped"),
            dict(good, run_attempt=0),
        ):
            with self.subTest(bad=bad), self.assertRaises(R5.ReleaseBlocked):
                R5.validate_authenticated_run(
                    bad, SHA, self.review_id, R5.REVIEW_WORKFLOW)

    def test_attestation_requires_correct_run_invocation_and_exact_hash(self):
        result = self.root / "integration/disposition-verification.json"
        run = self.mock_run(self.review_id, R5.REVIEW_WORKFLOW)
        expected = ("https://github.com/" + R5.REPOSITORY +
                    "/actions/runs/" + str(self.review_id) + "/attempts/1")
        def envelope(invocation, digest):
            return json.dumps([{"verificationResult": {
                "statement": {
                    "subject": [{"digest": {"sha256": digest}}],
                    "predicate": {"runDetails": {
                        "metadata": {"invocationId": invocation}}},
                },
            }}])
        with patch.object(R5, "run_command", side_effect=[
            "gh version 2.102.0\n", envelope(expected, R5.hash_file(result)),
        ]) as mocked:
            R5.verify_attested_review_file(result, SHA, R5.REVIEW_WORKFLOW, run)
        cmd = mocked.call_args_list[1].args[0]
        for key, value in (
            ("--repo", R5.REPOSITORY),
            ("--source-ref", "refs/heads/main"),
            ("--source-digest", SHA),
            ("--signer-workflow", R5.REPOSITORY + "/" + R5.REVIEW_WORKFLOW),
        ):
            self.assertEqual(cmd[cmd.index(key) + 1], value)
        for invocation, digest in (
            (expected.replace("/attempts/1", "/attempts/2"), R5.hash_file(result)),
            (expected.replace(str(self.review_id), str(self.review_id + 1)),
             R5.hash_file(result)),
            (expected, "0" * 64),
        ):
            with self.subTest(invocation=invocation), patch.object(
                R5, "run_command", side_effect=[
                    "gh version 2.102.0\n", envelope(invocation, digest),
                ]), self.assertRaises(R5.ReleaseBlocked):
                R5.verify_attested_review_file(
                    result, SHA, R5.REVIEW_WORKFLOW, run)

    def test_owner_latest_state_rejects_stale_revocation_and_trust(self):
        values = {
            name: base64.b64encode((name + ":synthetic").encode()).decode()
            for name in R5.OWNER_STATE_VARIABLES[:-1]
        }
        values["SECURITY_DISPOSITION_LIFECYCLE_SHA256"] = (
            "sha256:" + hashlib.sha256(
                base64.b64decode(values["SECURITY_DISPOSITION_LIFECYCLE_B64"])
            ).hexdigest())
        values["SECURITY_DISPOSITION_STATE_READ_TOKEN"] = "read-only-fixture"
        with patch.dict(os.environ, values):
            def api_ok(path, *, token=None, **kwargs):
                name = path.rsplit("/", 1)[-1]
                self.assertEqual(token, "read-only-fixture")
                return {"name": name, "value": values[name],
                        "updated_at": "2026-11-10T01:00:00Z"}
            with patch.object(R5, "api", side_effect=api_ok):
                current = R5.owner_disposition_state(latest=True)
                self.assertTrue(current["SECURITY_DISPOSITION_TRUST_B64"])
            for changed in (
                "SECURITY_DISPOSITION_TRUST_B64",
                "SECURITY_DISPOSITION_LIFECYCLE_B64",
                "SECURITY_DISPOSITION_LIFECYCLE_SIG_B64",
                "SECURITY_DISPOSITION_LIFECYCLE_SHA256",
            ):
                with self.subTest(changed=changed):
                    def api_changed(path, *, token=None, **kwargs):
                        name = path.rsplit("/", 1)[-1]
                        return {"name": name,
                                "value": "replaced" if name == changed else values[name],
                                "updated_at": "2026-11-10T01:01:00Z"}
                    with patch.object(R5, "api", side_effect=api_changed):
                        with self.assertRaises(R5.ReleaseBlocked):
                            R5.owner_disposition_state(latest=True)
            with patch.dict(os.environ, {
                "SECURITY_DISPOSITION_LIFECYCLE_SHA256": "sha256:" + "0" * 64
            }):
                with patch.object(R5, "api", side_effect=lambda path, *, token=None:
                                  {"name": path.rsplit("/", 1)[-1],
                                   "value": os.environ[path.rsplit("/", 1)[-1]],
                                   "updated_at": "2026-11-10T01:00:00Z"}):
                    with self.assertRaises(R5.ReleaseBlocked):
                        R5.owner_disposition_state(latest=True)

    def test_missing_latest_state_credential_rejected(self):
        with patch.dict(os.environ, {"SECURITY_DISPOSITION_STATE_READ_TOKEN": ""},
                        clear=True), self.assertRaises(R5.ReleaseBlocked):
            R5.owner_disposition_state(latest=True)

    def test_live_recheck_runs_original_cli_and_rejects_revoked_review(self):
        scans = self.chain_runs()
        old_result = self.summary["disposition"]["result"]
        context = {
            "source_sha": SHA, "r3_run_id": R3, "scan_run_id": self.scan_id,
            "producer_actor": self.document["producer_actor"],
            "release_lock_sha256": "sha256:" + self.summary["lock_sha256"],
        }
        def mock_api(path, **kwargs):
            return scans[int(path.rsplit("/", 1)[-1])]

        def runner(command, *, output=False):
            if command[:3] == ["gh", "run", "download"]:
                dst = Path(command[command.index("--dir") + 1])
                artifact = command[command.index("--name") + 1]
                (dst / "context.json").write_text(json.dumps(context))
                for file in ("release-lock.json", "scanner.json"):
                    shutil.copyfile(self.root / file, dst / file)
                (dst / "vulnerability-exceptions.json").write_bytes(
                    (ROOT / "security/vulnerability-exceptions.json").read_bytes())
                shutil.copytree(self.root / "reports", dst / "reports")
                if artifact == "ghcr-security-contract-v2":
                    for file in ("security-contract.json",
                                 "rendered-release-compose.json"):
                        shutil.copyfile(self.root / file, dst / file)
                    (dst / "review").mkdir()
                    shutil.copyfile(
                        self.root / "integration/disposition-verification.json",
                        dst / "review/disposition-verification.json")
            if "-m" in command and "scripts.verify_security_dispositions" in command:
                out = Path(command[command.index("--output") + 1])
                out.write_text(json.dumps(dict(
                    old_result, lifecycle_sha256="sha256:" + "c" * 64)))
            return ""
        state = {
            name: b"synthetic-owner-" + name.encode()
            for name in R5.OWNER_STATE_VARIABLES[:-1]
        }
        with patch.object(R5, "api", side_effect=mock_api), patch.object(
            R5, "verify_attested_review_file"
        ), patch.object(R5, "owner_disposition_state", return_value=state), patch.object(
            R5, "run_command", side_effect=runner
        ) as invoked:
            R5.revalidate_current_dispositions(self.root, self.summary, SHA,
                                               latest=True)
            self.assertTrue(any("scripts.verify_security_dispositions" in c.args[0]
                                for c in invoked.call_args_list))
        def revoked(command, *, output=False):
            if "-m" in command and "scripts.verify_security_dispositions" in command:
                raise R5.ReleaseBlocked("revoked independent signature")
            return runner(command, output=output)
        with patch.object(R5, "api", side_effect=mock_api), patch.object(
            R5, "verify_attested_review_file"
        ), patch.object(R5, "owner_disposition_state", return_value=state), patch.object(
            R5, "run_command", side_effect=revoked
        ), self.assertRaises(R5.ReleaseBlocked):
            R5.revalidate_current_dispositions(
                self.root, self.summary, SHA, latest=True)



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

    def test_master_issue_18_cannot_be_bypassed_by_label_removal(self):
        R5.validate_master_acceptance_issue({"number": 18, "state": "closed"})
        for issue in (
            {"number": 18, "state": "open"},
            {"number": 18, "state": "open", "labels": []},
            {"number": 19, "state": "closed"},
            {"number": 18, "state": "closed", "pull_request": {}},
            {},
        ):
            with self.subTest(issue=issue), self.assertRaises(R5.ReleaseBlocked):
                R5.validate_master_acceptance_issue(issue)

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
