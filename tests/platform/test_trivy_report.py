"""Safe synthetic Trivy JSON fixtures: no vulnerable production dependency added."""

import unittest
from scripts.trivy_report import compare, normalized_findings, summarize


class TrivyReportTests(unittest.TestCase):
    def test_clean_scan(self):
        rows = normalized_findings({"Results": [{"Target": "debian", "Type": "debian",
                                                  "Vulnerabilities": None}]})
        self.assertEqual(rows, [])
        summary = summarize("portal", "image", "sha256:123", "commit", rows)
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["by_severity"]["CRITICAL"], 0)

    def test_severity_and_fixability(self):
        rows = normalized_findings({"Results": [
            {"Target": "debian", "Type": "debian", "Vulnerabilities": [
                {"VulnerabilityID": "CVE-TEST-1", "PkgName": "libexample",
                 "InstalledVersion": "1", "FixedVersion": "2", "Severity": "CRITICAL"},
                {"VulnerabilityID": "CVE-TEST-2", "PkgName": "unfixed",
                 "InstalledVersion": "1", "Severity": "HIGH"}]},
            {"Target": "site-packages", "Type": "python-pkg", "Vulnerabilities": [
                {"VulnerabilityID": "CVE-TEST-3", "PkgName": "pyexample",
                 "InstalledVersion": "2", "Severity": "MEDIUM"}]},
        ]})
        s = summarize("media", "image", "sha256:1", "abc", rows)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["fix_available"]["CRITICAL"], 1)
        self.assertEqual(s["no_known_fix"]["HIGH"], 1)
        self.assertEqual(s["no_known_fix"]["MEDIUM"], 1)

    def test_compare_new_and_resolved_with_different_image_tags(self):
        old = normalized_findings({"Results": [{"Target": "image:old", "Type": "debian",
            "Vulnerabilities": [{"VulnerabilityID": "CVE-TEST-OLD",
                                 "PkgName": "liba", "InstalledVersion": "1",
                                 "Severity": "LOW"}]}]})
        new = normalized_findings({"Results": [{"Target": "image:new", "Type": "debian",
            "Vulnerabilities": [{"VulnerabilityID": "CVE-TEST-NEW",
                                 "PkgName": "liba", "InstalledVersion": "1",
                                 "Severity": "HIGH"}]}]})
        delta = compare({"component": "portal", "findings": new},
                        {"component": "portal", "findings": old})
        self.assertEqual([r["id"] for r in delta["new"]], ["CVE-TEST-NEW"])
        self.assertEqual([r["id"] for r in delta["resolved"]], ["CVE-TEST-OLD"])

    def test_missing_results_cannot_be_mistaken_for_clean_scan(self):
        with self.assertRaises(ValueError):
            normalized_findings({})
        with self.assertRaises(ValueError):
            normalized_findings({"Results": [{"Vulnerabilities": [
                {"PkgName": "package", "Severity": "HIGH"}]}]})

    def test_cross_component_baseline_rejected(self):
        with self.assertRaises(ValueError):
            compare({"component": "portal", "findings": []},
                    {"component": "music", "findings": []})


if __name__ == "__main__":
    unittest.main()
