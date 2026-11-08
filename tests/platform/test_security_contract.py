"""Synthetic negative testing of release-facing security contract; no dependency changes."""
import unittest
from datetime import date, datetime, timezone
from scripts.security_contract import InvalidEvidence, assess, exceptions_by_identity

SOURCE = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64
DIGEST = "sha256:" + "c" * 64
REF = "foxden-ci-portal:" + SOURCE
TODAY = date(2026, 11, 8)


def vuln(severity="CRITICAL"):
    return {"VulnerabilityID": "CVE-2099-1000", "PkgName": "libfixture",
            "InstalledVersion": "1", "Severity": severity, "FixedVersion": "2"}


def sample(vulns=None):
    return {
        "component": "portal",
        "report": {"ArtifactType": "container_image", "ArtifactName": REF,
                   "Metadata": {"ImageID": IMAGE_ID},
                   "Trivy": {"Version": "0.76.2"},
                   "Results": [{"Target": "debian", "Type": "debian",
                                "Vulnerabilities": vulns if vulns is not None else []}]},
        "sbom": {"bomFormat": "CycloneDX", "specVersion": "1.7", "components": []},
        "scanner": {"Version": "0.76.2",
                    "VulnerabilityDB": {"UpdatedAt": "2026-11-08T00:00:00Z"}},
        "ledger": {"schema_version": 1, "exceptions": []},
        "source_sha": SOURCE, "expected_source_sha": SOURCE,
        "image_ref": REF, "image_id": IMAGE_ID, "today": TODAY
    }


def exception(expiry="2099-12-31"):
    return {"component": "portal", "finding_id": "CVE-2099-1000",
            "package_type": "debian", "package": "libfixture", "installed": "1",
            "owner": "ItsFoxxin", "approved_by": "ItsFoxxin",
            "justification": "Synthetic reviewed exception for policy regression tests.",
            "issue": "https://github.com/ItsFoxxin/Fox_Den_Media/issues/71",
            "expires": expiry}


class SecurityContractTests(unittest.TestCase):
    def test_clean_scan_never_claims_release_eligible_in_advisory(self):
        contract = assess(**sample())
        self.assertEqual(contract["policy"]["decision"], "review_required")
        self.assertFalse(contract["policy"]["release_eligible"])
        self.assertIsNone(contract["image"]["manifest_digest"])

    def test_unaccepted_critical_detected_but_advisory_does_not_raise(self):
        contract = assess(**sample([vuln()]))
        self.assertEqual(contract["policy"]["decision"], "fail")
        self.assertEqual(len(contract["policy"]["critical_high_unaccepted"]), 1)

    def test_unaccepted_high_detected(self):
        self.assertEqual(assess(**sample([vuln("HIGH")]))["policy"]["decision"], "fail")

    def test_exception_is_specific_to_component_and_version(self):
        s = sample([vuln()])
        s["ledger"]["exceptions"] = [exception()]
        result = assess(**s)
        self.assertEqual(len(result["policy"]["approved_exceptions"]), 1)
        s["report"]["Results"][0]["Vulnerabilities"][0]["InstalledVersion"] = "2"
        self.assertEqual(len(assess(**s)["policy"]["critical_high_unaccepted"]), 1)

    def test_expired_exception_fails_closed(self):
        s = sample([vuln()])
        s["ledger"]["exceptions"] = [exception("2026-11-08")]
        result = assess(**s)
        self.assertEqual(result["policy"]["decision"], "fail")
        self.assertEqual(len(result["policy"]["expired_exceptions"]), 1)

    def test_expired_ledger_entry_fails_even_if_finding_removed(self):
        s = sample()
        s["ledger"]["exceptions"] = [exception("2026-11-07")]
        self.assertEqual(assess(**s)["policy"]["decision"], "fail")

    def test_missing_scan_results_rejected(self):
        s = sample()
        del s["report"]["Results"]
        with self.assertRaises(ValueError):
            assess(**s)

    def test_malformed_cyclonedx_rejected(self):
        s = sample()
        del s["sbom"]["components"]
        with self.assertRaises(InvalidEvidence):
            assess(**s)

    def test_missing_scanner_metadata_rejected(self):
        s = sample()
        s["scanner"] = {}
        with self.assertRaises(InvalidEvidence):
            assess(**s)

    def test_wrong_image_id_rejected(self):
        s = sample()
        s["image_id"] = "sha256:" + "e" * 64
        with self.assertRaises(InvalidEvidence):
            assess(**s)

    def test_stale_source_commit_rejected(self):
        s = sample()
        s["expected_source_sha"] = "d" * 40
        with self.assertRaises(InvalidEvidence):
            assess(**s)

    def test_incorrect_manifest_digest_rejected(self):
        s = sample()
        s["image_digest"] = DIGEST
        s["expected_image_digest"] = "sha256:" + "d" * 64
        with self.assertRaises(InvalidEvidence):
            assess(**s)

    def test_unknown_severity_requires_review(self):
        self.assertEqual(assess(**sample([vuln("UNKNOWN")]))["policy"]["decision"],
                         "review_required")

    def test_no_baseline_means_enforcement_fails(self):
        s = sample()
        s.update(mode="enforce", image_digest=DIGEST, expected_image_digest=DIGEST)
        self.assertEqual(assess(**s)["policy"]["decision"], "fail")

    def test_baseline_delta_does_not_exempt_new_critical(self):
        s = sample([vuln()])
        s["baseline"] = {"component": "portal", "source_sha": "d" * 40, "findings": []}
        s["baseline_verified"] = True
        c = assess(**s)
        self.assertEqual(c["baseline"]["new"], 1)
        self.assertEqual(c["policy"]["decision"], "fail")

    def test_synthetic_enforcement_success_requires_digest_and_baseline(self):
        s = sample()
        s["scanner"]["VulnerabilityDB"]["UpdatedAt"] = datetime.now(timezone.utc).isoformat()
        s.update(mode="enforce", baseline_verified=True,
                 baseline={"component": "portal", "source_sha": "d" * 40, "findings": []},
                 image_digest=DIGEST, expected_image_digest=DIGEST)
        # The fixture establishes logic only. A future workflow must verify provenance.
        self.assertEqual(assess(**s)["policy"]["decision"], "pass")

    def test_duplicate_or_untracked_exception_is_rejected(self):
        e = exception()
        with self.assertRaises(InvalidEvidence):
            exceptions_by_identity({"schema_version": 1, "exceptions": [e, e]}, TODAY)
        with self.assertRaises(InvalidEvidence):
            exceptions_by_identity({"schema_version": 1, "exceptions": [
                dict(e, issue="https://example.org/not-an-issue")]}, TODAY)

    def test_malformed_baseline_rejected(self):
        s = sample()
        s["baseline"] = {"component": "music", "findings": [], "source_sha": SOURCE}
        with self.assertRaises(InvalidEvidence):
            assess(**s)


if __name__ == "__main__":
    unittest.main()
