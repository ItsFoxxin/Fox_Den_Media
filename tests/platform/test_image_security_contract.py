"""R4 scanner-contract consumer synthetic tests; no scanner or GHCR required."""
import copy
import pytest
from scripts.verify_image_security import (
    COMPONENTS, SecurityContractError, validate_contract,
)

SHA = "a" * 40
IMAGE_DIGEST = "sha256:" + "b" * 64
PLATFORM_DIGEST = "sha256:" + "c" * 64

def sample():
    candidates = {}
    images = {}
    for name, repo in COMPONENTS.items():
        candidates[name] = {
            "component": name, "image": repo, "source_sha": SHA,
            "digest": IMAGE_DIGEST, "platform_digest": PLATFORM_DIGEST,
            "platform": "linux/amd64", "workflow": "ghcr-candidates.yml",
            "run_id": 99,
        }
        images[name] = {
            "ref": f"{repo}@{IMAGE_DIGEST}",
            "platform_digest": PLATFORM_DIGEST, "source_sha": SHA,
            "provenance": "verified", "sbom_format": "spdx-json",
            "sbom_sha256": "sha256:" + "d" * 64,
            "sbom_subject": IMAGE_DIGEST,
            "vulnerability_report_sha256": "sha256:" + "e" * 64,
            "scan_subject": IMAGE_DIGEST, "decision": "pass", "exceptions": [],
        }
    contract = {
        "schema_version": 1,
        "producer": ".github/workflows/trivy-digest-security.yml",
        "source_sha": SHA, "publisher_run_id": 99, "platform": "linux/amd64",
        "scanner": {"name": "trivy", "version": "0.76.2",
                    "db_updated_at": "2026-11-07T00:00:00Z"},
        "policy_version": "1", "images": images,
        "upstream": {
            "nginx": {
                "ref": f"docker.io/library/nginx@{IMAGE_DIGEST}",
                "platform_digest": PLATFORM_DIGEST, "scan_subject": IMAGE_DIGEST,
                "sbom_subject": IMAGE_DIGEST, "sbom_sha256": "sha256:" + "d" * 64,
                "vulnerability_report_sha256": "sha256:" + "e" * 64,
                "decision": "pass", "exceptions": [], "provenance_status": "verified",
            },
        },
    }
    return contract, candidates

def test_exact_digest_contract():
    contract, candidates = sample()
    validate_contract(contract, candidates, SHA, 99)

@pytest.mark.parametrize("mod", [
    lambda c, d: c.update(source_sha="f" * 40),
    lambda c, d: c.update(publisher_run_id=100),
    lambda c, d: c.update(producer=".github/workflows/other.yml"),
    lambda c, d: c.update(platform="linux/arm64"),
    lambda c, d: c["images"]["music"].update(ref="ghcr.io/evil/music@" + IMAGE_DIGEST),
    lambda c, d: c["images"]["portal"].update(scan_subject="sha256:" + "f" * 64),
    lambda c, d: c["images"]["portal"].update(sbom_subject="sha256:" + "f" * 64),
    lambda c, d: c["images"]["music"].update(decision="unknown"),
    lambda c, d: c["images"]["media"].update(decision="fail"),
    lambda c, d: c["images"]["music"].update(exceptions=["GHSA-unreviewed"]),
    lambda c, d: c["images"]["portal"].update(provenance="missing"),
    lambda c, d: c["scanner"].update(db_updated_at=""),
    lambda c, d: d["music"].update(digest="sha256:" + "f" * 64),
    lambda c, d: d["portal"].update(workflow="untrusted.yml"),
    lambda c, d: d["media"].update(source_sha="f" * 40),
    lambda c, d: c["images"].pop("portal"),
    lambda c, d: c["upstream"].pop("nginx"),
    lambda c, d: c["upstream"]["nginx"].update(decision="unknown"),
])
def test_mismatch_or_unverified_contract_fails(mod):
    contract, candidates = sample()
    mod(contract, candidates)
    with pytest.raises(SecurityContractError):
        validate_contract(contract, candidates, SHA, 99)
