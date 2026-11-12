"""Synthetic R4 consumer integration with the merged A/C producer and B verifier.

No GitHub OIDC attestation, real CVE disposition, publication or release is
performed here. Workflow attestation and protected owner state are separate
runtime gates, never replaced with these generated test identities.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from scripts import ghcr_digest_security as producer
from scripts import r4_release_ready as consumer
from scripts import verify_security_dispositions as verifier
from test_ghcr_digest_security import (
    SOURCE, decimal_trivy_fixture, metadata, v2_fixture,
)


def utc(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(verifier.canonical(value) + b"\n")


def sign(key, domain, value):
    digest = bytes.fromhex(verifier.canonical_digest(value)[7:])
    return base64.b64encode(key.sign(domain + digest)).decode("ascii")


def public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def evidence(tmp_path, severity="HIGH", status="FIXED"):
    """Build original A bytes, real C v2 contract and real signed B result."""
    if severity == "CLEAN":
        plan, reports, lock_path, scanner_path, policy, _ = v2_fixture(tmp_path)
    else:
        plan, reports, lock_path, scanner_path, policy, _, _ = (
            decimal_trivy_fixture(tmp_path, severity=severity)
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    scanner = metadata(utc(now))
    write(scanner_path, scanner)
    context = producer.collect_v2_context(
        plan, reports, scanner, policy, lock_path, scanner_path,
        SOURCE, 113, 235, "github:scan-bot", now,
    )
    inventory = producer.severe_inventory(context, reports)
    records = []
    review_dir = tmp_path / "review-b"
    reviewer = Ed25519PrivateKey.generate()
    owner = Ed25519PrivateKey.generate()
    if inventory:
        subject = inventory[("portal", 0, 0)]
        original = verifier.load_json(
            reports / "portal.vuln.json", scanner_evidence=True)
        vulnerability = original["Results"][0]["Vulnerabilities"][0]
        assert subject == verifier.finding_subject(
            "portal", 0, 0, original["Results"][0], vulnerability,
            context["images"]["portal"])
        if severity != "CLEAN":
            assert vulnerability["CVSS"]["redhat"]["V2Score"] == 3.7
            assert vulnerability["CVSS"]["redhat"]["V3Score"] == 7.8
            assert vulnerability["CVSS"]["nvd"]["V3Score"] == 8.1
            assert subject["finding_sha256"] == verifier.canonical_digest(vulnerability)
        proof = {
            "schema_version": 1, "kind": status,
            "source_sha": SOURCE,
            "release_lock_sha256": context["release_lock_sha256"],
            "r3_run_id": 113, "scan_run_id": 235,
            "image_repository": subject["image_repository"],
            "manifest_digest": subject["manifest_digest"],
            "platform_digest": subject["platform_digest"],
            "finding_sha256": subject["finding_sha256"],
            "reference_url": "https://security.example.org/synthetic-test",
            "reference_sha256": "sha256:" + "d" * 64,
            "verification_method": "Independently inspect synthetic locked binary",
            "binary_sha256": "sha256:" + "e" * 64,
            "installed_version": subject["installed_version"],
            "technical_basis": (
                "authoritative-remediation-and-installed-image" if status == "FIXED"
                else "vulnerable-implementation-absent"
            ),
        }
        proof_path = review_dir / "review/proofs/finding.json"
        write(proof_path, proof)
        records.append({
            "status": status, "subject": subject,
            "proof_path": "proofs/finding.json",
            "proof_sha256": verifier.raw_digest(proof_path),
            "reviewer_id": "github:independent-reviewer",
        })
    document = {
        "schema_version": 1, "repository": verifier.REPOSITORY,
        "source_sha": SOURCE, "producer_actor": "github:scan-bot",
        "release_lock_sha256": context["release_lock_sha256"],
        "r3_run_id": 113, "scan_run_id": 235,
        "created_at": utc(now - timedelta(hours=2)),
        "reviewed_at": utc(now - timedelta(hours=1)),
        "expires_at": utc(now + timedelta(days=14)),
        "records": records,
    }
    signatures = []
    if records:
        signatures.append({
            "role": "reviewer", "identity": "github:independent-reviewer",
            "key_id": "reviewer-test",
            "signature_base64": sign(reviewer, b"foxden.dispositions.v1\n", document),
        })
    if severity == "CRITICAL" and status == "NOT_AFFECTED":
        signatures.append({
            "role": "owner", "identity": "github:ItsFoxxin",
            "key_id": "owner-test",
            "signature_base64": sign(owner, b"foxden.dispositions.v1\n", document),
        })
    signature_doc = {
        "schema_version": 1,
        "document_sha256": verifier.canonical_digest(document),
        "signatures": signatures,
    }
    trust = {
        "schema_version": 1, "repository": verifier.REPOSITORY,
        "review_workflow": verifier.REVIEW_WORKFLOW,
        "producer_workflow": verifier.PRODUCER_WORKFLOW,
        "reviewers": {
            "github:independent-reviewer": {
                "key_id": "reviewer-test", "public_key_pem": public(reviewer),
            },
        },
        "owner": {
            "identity": "github:ItsFoxxin", "key_id": "owner-test",
            "public_key_pem": public(owner),
        },
    }
    lifecycle = {
        "schema_version": 1,
        "issued_at": utc(now - timedelta(minutes=10)),
        "expires_at": utc(now + timedelta(hours=12)),
        "revoked_document_sha256": [], "superseded_document_sha256": [],
    }
    trusted = tmp_path / "owner-managed"
    write(trusted / "trust.json", trust)
    write(trusted / "lifecycle.json", lifecycle)
    (trusted / "lifecycle.sig").write_text(
        sign(owner, b"foxden.lifecycle.v1\n", lifecycle), encoding="ascii")
    write(review_dir / "review/dispositions.json", document)
    write(review_dir / "review/signatures.json", signature_doc)

    scan = tmp_path / "scan-a"
    final = tmp_path / "security-c"
    source_policy = tmp_path / "source-policy.json"
    write(source_policy, policy)
    for root in (scan, final):
        for src_name, src in (
            ("release-lock.json", lock_path),
            ("scanner.json", scanner_path),
            ("vulnerability-exceptions.json", source_policy),
        ):
            target = root / src_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        write(root / "context.json", context)
        write(root / "rendered-release-compose.json", {"services": {}})
        (root / "reports").mkdir(parents=True)
        for artifact in reports.glob("*"):
            if artifact.name.endswith((".vuln.json", ".sbom.spdx.json")):
                shutil.copyfile(artifact, root / "reports" / artifact.name)

    result = verifier.verify(
        context=context, dispositions=document, signatures=signature_doc,
        lifecycle=lifecycle,
        lifecycle_signature=(trusted / "lifecycle.sig").read_text(),
        trust=trust, evidence_dir=scan, proofs_dir=review_dir / "review",
        lock_path=scan / "release-lock.json", scanner=scanner,
        scanner_path=scan / "scanner.json", exceptions=policy,
        expected_source_sha=SOURCE, expected_r3_run_id=113,
        expected_scan_run_id=235, expected_producer_actor="github:scan-bot",
        now=now,
    )
    write(review_dir / "security/disposition-verification.json", result)
    write(final / "review/disposition-verification.json", result)
    original_bytes = (review_dir / "security/disposition-verification.json").read_bytes()
    contract = producer.final_v2_contract(
        plan, reports, scanner, policy, lock_path, scanner_path,
        context, result, result, original_bytes, document,
        SOURCE, 113, 235, "github:scan-bot", 236, now,
    )
    verifier.require_r4_contract_v2(contract, result, original_bytes)
    assert contract["schema_version"] == 2
    assert contract["disposition_review"]["review_run_id"] == 236
    return {
        "contract": contract, "context": context, "document": document,
        "result": result, "scanner": scanner, "policy": policy,
        "lock": json.loads(lock_path.read_text()), "review": review_dir,
        "scan": scan, "final": final, "trust": trusted, "owner": owner,
        "lifecycle": lifecycle, "output": tmp_path / "r4-output",
        "source_policy": source_policy, "reports": reports,
    }


def accept(case, **changes):
    inputs = dict(
        security=case["contract"], lock=case["lock"],
        scanner=case["scanner"], ledger=case["policy"],
        source=SOURCE, r3_id=113, scan_id=235, review_id=236,
        scan_actor="github:scan-bot", security_dir=case["final"],
        scan_dir=case["scan"], policy_path=case["source_policy"],
        review_dir=case["review"], trust_path=case["trust"] / "trust.json",
        lifecycle_path=case["trust"] / "lifecycle.json",
        lifecycle_signature_path=case["trust"] / "lifecycle.sig",
    )
    inputs.update(changes)
    return consumer.revalidate_independent_dispositions(**inputs)


@pytest.mark.parametrize("severity,status", [
    ("HIGH", "FIXED"), ("CRITICAL", "NOT_AFFECTED"), ("CLEAN", "FIXED"),
])
def test_real_integrated_v2_verifier_to_r4_signed_handoff(tmp_path, severity, status):
    case = evidence(tmp_path, severity, status)
    signed, records = accept(case)
    assert signed == case["result"]
    assert records == case["document"]
    if not records["records"]:
        assert not (case["review"] / "review/proofs").exists()
    binding = consumer.stage_independent_dispositions(
        review_dir=case["review"], output=case["output"],
        dispositions=records, signed_result=signed,
        binding=case["contract"]["disposition_review"], review_id=236,
    )
    files = {
        p.relative_to(case["output"]).as_posix(): consumer.sha_file(p)
        for p in case["output"].rglob("*.json")
    }
    consumer.validate_disposition_file_map(
        files=files, output=case["output"],
        dispositions=records, binding=binding,
    )
    assert binding["verification_file"] == "integration/disposition-verification.json"
    assert binding["dispositions_sha256"] == verifier.canonical_digest(records)
    expected_proofs = {
        "integration/disposition-proof-finding.json"
    } if records["records"] else set()
    assert {p for p in files if "disposition-proof-" in p} == expected_proofs


@pytest.mark.parametrize("mutation", [
    "v1", "wrong-review-run", "wrong-r3-run", "wrong-source", "wrong-scan-actor",
    "altered-a-report", "altered-c-spdx", "wrong-lock", "wrong-oci-digest",
    "missing-proof", "missing-owner", "missing-lifecycle", "stale-lifecycle",
    "revoked-lifecycle", "tampered-lifecycle-signature",
    "tampered-review", "unresolved-high",
])
def test_real_integrated_consumer_rejects_broken_security_evidence(
    tmp_path, mutation,
):
    critical = mutation == "missing-owner"
    case = evidence(
        tmp_path, "CRITICAL" if critical else "HIGH",
        "NOT_AFFECTED" if critical else "FIXED",
    )
    overrides = {}
    if mutation == "v1":
        case["contract"]["schema_version"] = 1
    elif mutation == "wrong-review-run":
        overrides["review_id"] = 237
    elif mutation == "wrong-r3-run":
        overrides["r3_id"] = 114
    elif mutation == "wrong-source":
        overrides["source"] = "b" * 40
    elif mutation == "wrong-scan-actor":
        overrides["scan_actor"] = "github:imposter"
    elif mutation == "altered-a-report":
        path = case["scan"] / "reports/portal.vuln.json"
        path.write_bytes(path.read_bytes().replace(b"3.7", b"3.8"))
    elif mutation == "altered-c-spdx":
        path = case["final"] / "reports/portal.sbom.spdx.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "wrong-lock":
        path = case["scan"] / "release-lock.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "wrong-oci-digest":
        for root in (case["scan"], case["final"]):
            path = root / "context.json"
            context = verifier.load_json(path)
            context["images"]["portal"]["manifest_digest"] = "sha256:" + "f" * 64
            write(path, context)
    elif mutation == "missing-proof":
        (case["review"] / "review/proofs/finding.json").unlink()
    elif mutation == "missing-owner":
        path = case["review"] / "review/signatures.json"
        sigs = verifier.load_json(path)
        sigs["signatures"] = [s for s in sigs["signatures"] if s["role"] != "owner"]
        write(path, sigs)
    elif mutation == "missing-lifecycle":
        (case["trust"] / "lifecycle.json").unlink()
    elif mutation in ("stale-lifecycle", "revoked-lifecycle"):
        lifecycle = case["lifecycle"]
        if mutation == "stale-lifecycle":
            lifecycle["expires_at"] = utc(datetime.now(timezone.utc) - timedelta(minutes=1))
        else:
            lifecycle["revoked_document_sha256"] = [
                verifier.canonical_digest(case["document"])]
        write(case["trust"] / "lifecycle.json", lifecycle)
        (case["trust"] / "lifecycle.sig").write_text(
            sign(case["owner"], b"foxden.lifecycle.v1\n", lifecycle),
            encoding="ascii")
    elif mutation == "tampered-lifecycle-signature":
        (case["trust"] / "lifecycle.sig").write_text(
            base64.b64encode(b"\0" * 64).decode(), encoding="ascii")
    elif mutation == "tampered-review":
        path = case["review"] / "review/dispositions.json"
        path.write_bytes(path.read_bytes().replace(
            b'"status":"FIXED"', b'"status":"NOT_AFFECTED"'))
    else:
        assert mutation == "unresolved-high"
        path = case["review"] / "review/dispositions.json"
        doc = verifier.load_json(path)
        doc["records"] = []
        write(path, doc)
    with pytest.raises((
        consumer.ReleaseEvidenceError, verifier.DispositionError,
    )):
        accept(case, **overrides)


def test_signed_v2_contract_rejects_unknown_and_nonempty_exception(tmp_path):
    plan, reports, lock_path, scanner_path, policy, context = v2_fixture(
        tmp_path, severity="UNKNOWN")
    with pytest.raises(producer.EvidenceError, match="UNKNOWN"):
        producer.severe_inventory(context, reports)
    separate = tmp_path / "separate"
    separate.mkdir()
    case = evidence(separate, "HIGH")
    case["policy"]["exceptions"] = [{"unapproved": True}]
    with pytest.raises(verifier.DispositionError):
        verifier.verify(
            context=case["context"],
            dispositions=case["document"], signatures=verifier.load_json(
                case["review"] / "review/signatures.json"),
            lifecycle=case["lifecycle"],
            lifecycle_signature=(case["trust"] / "lifecycle.sig").read_text(),
            trust=verifier.load_json(case["trust"] / "trust.json"),
            evidence_dir=case["scan"], proofs_dir=case["review"] / "review",
            lock_path=case["scan"] / "release-lock.json",
            scanner=case["scanner"], scanner_path=case["scan"] / "scanner.json",
            exceptions=case["policy"], expected_source_sha=SOURCE,
            expected_r3_run_id=113, expected_scan_run_id=235,
            expected_producer_actor="github:scan-bot",
        )


def test_r4_exact_run_attempt_attestation_binding_and_owner_gate():
    """The synthetic Ed25519 tests never substitute for real GitHub OIDC."""
    source = Path(".github/workflows/ghcr-verify.yml").read_text()
    assert 'attempt="$(jq -er .run_attempt "$RUNNER_TEMP/$kind-run.json")"' in source
    assert "invocation == invocation_id" in source
    assert '"$SCAN_RUN" trivy-digest-security.yml scan' in source
    assert '"$REVIEW_RUN" security-disposition-review.yml review' in source
    assert '"$SECURITY_RUN" trivy-digest-security.yml security' in source
    assert "gh attestation verify" in source
    assert '--source-ref "refs/heads/main"' in source
    assert '--source-digest "$SOURCE_SHA"' in source
    assert "SECURITY_DISPOSITION_STATE_READ_TOKEN" in source
    assert 'test -n "$STATE_READ_TOKEN"' in source
