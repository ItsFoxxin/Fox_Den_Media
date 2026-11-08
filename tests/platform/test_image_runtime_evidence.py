"""Fail-closed identity, component completeness and synthetic-output regressions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import image_runtime_evidence as evidence

SOURCE = "a" * 40
HARNESS = "b" * 40
IDS = {name: "sha256:" + str(i) * 64 for i, name in enumerate(evidence.COMPONENTS, 1)}


def report(name):
    return {
        "schema": 1, "component": name, "source_sha": SOURCE, "harness_sha": HARNESS,
        "image_ref": f"foxden-evidence-{name}:{SOURCE}", "image_id": IDS[name],
        "image": {"local_config_id": IDS[name], "architecture": "amd64", "os": "linux",
                  "registry_manifest_digest": None},
        "build": {"context": evidence.COMPONENTS[name][0],
                  "dockerfile": evidence.COMPONENTS[name][1], "pull": True},
        "packages": [{"name": "zlib1g", "version": "1.2.13", "arch": "amd64"}],
        "binaries": [{"image_path": "/usr/lib/libz.so.1", "sha256": "1" * 64}],
        "ffmpeg": {"state": "not_found_on_PATH", "registrations": None, "fixture": "not_run"},
        "sqlite": {"version": "3.40.1", "compile_options": [], "fts5": "pass",
                   "json1": "pass", "memory": "pass"},
        "synthetic": {"zlib": "pass", "expat": "pass"},
        "interpretation_limits": list(evidence.LIMITS),
    }


class EvidenceTests(unittest.TestCase):
    def test_all_three_component_identities(self):
        for component in evidence.COMPONENTS:
            self.assertTrue(evidence.validate_report(report(component), source=SOURCE,
                                                     harness=HARNESS, component=component,
                                                     image_id=IDS[component]))

    def test_wrong_and_missing_source_rejected(self):
        r = report("portal")
        for corrupt in (None, "", "not-a-sha", "c" * 40):
            r["source_sha"] = corrupt
            with self.assertRaises(ValueError):
                evidence.validate_report(r, source=SOURCE, harness=HARNESS)

    def test_wrong_harness_sha_rejected(self):
        r = report("media")
        r["harness_sha"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "identity"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)

    def test_unbound_and_invalid_image_ids_rejected(self):
        for bad in ("", "sha256:abc", "sha256:" + "d" * 64):
            r = report("music")
            r["image"]["local_config_id"] = bad
            with self.assertRaises(ValueError):
                evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        with self.assertRaisesRegex(ValueError, "wrong image binding"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS,
                                     image_id="sha256:" + "f" * 64)

    def test_wrong_component_and_build_context_rejected(self):
        r = report("media")
        r["build"]["context"] = "apps/portal"
        with self.assertRaisesRegex(ValueError, "build context"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        with self.assertRaisesRegex(ValueError, "component"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS, component="music")

    def test_incomplete_reports_rejected(self):
        for key in evidence.REQUIRED:
            r = report("portal")
            r.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        r["sqlite"].pop("compile_options")
        with self.assertRaises(ValueError):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        r["synthetic"]["expat"] = "not_run"
        with self.assertRaises(ValueError):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)

    def test_incomplete_ffmpeg_registration_rejected(self):
        r = report("media")
        r["ffmpeg"] = {"state": "present", "registrations": {"encoders": ["mpeg4"]},
                       "fixture": "pass"}
        with self.assertRaisesRegex(ValueError, "registration family"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)

    def test_bad_probe_output_rejected(self):
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": "invalid json"})()):
            with self.assertRaisesRegex(ValueError, "malformed"):
                evidence.python_probe("sha256:" + "1" * 64)
        with self.assertRaisesRegex(ValueError, "protocol"):
            evidence.parse_ffmpeg("garbage", "protocols")
        with self.assertRaisesRegex(ValueError, "encoders"):
            evidence.parse_ffmpeg("garbage", "encoders")

    def test_checkout_identity_rejected(self):
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": "c" * 40 + "\n"})()):
            with self.assertRaisesRegex(ValueError, "wrong source checkout"):
                evidence.validate_checkout("/synthetic", SOURCE, "source")

    def test_bundle_missing_malformed_wrong_sha_and_duplicate_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            args = type("Args", (), {"source_sha": SOURCE, "harness_sha": HARNESS,
                                     "reports_dir": d, "output": str(root / "bundle.json")})()
            for name in evidence.COMPONENTS:
                (root / name).mkdir()
                (root / name / "report.json").write_text(json.dumps(report(name)))
            manifest = evidence.verify(args)
            self.assertEqual(set(manifest["components"]), set(evidence.COMPONENTS))
            self.assertTrue((root / "bundle.json").exists())
            path = root / "music" / "report.json"
            original = path.read_text()
            path.unlink()
            with self.assertRaisesRegex(ValueError, "missing"):
                evidence.verify(args)
            path.write_text("{malformed")
            with self.assertRaisesRegex(ValueError, "malformed"):
                evidence.verify(args)
            r = report("music")
            r["source_sha"] = "c" * 40
            path.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError, "identity"):
                evidence.verify(args)
            r = report("music")
            r["image_id"] = IDS["portal"]
            r["image"]["local_config_id"] = IDS["portal"]
            path.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError, "share"):
                evidence.verify(args)
            path.write_text(original)
            self.assertTrue(evidence.verify(args))

    def test_missing_ffmpeg_is_a_clean_absence_even_with_dash(self):
        # A no-FFmpeg Portal image must not depend on shell-specific 1/127 codes.
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": "absent"})()):
            self.assertEqual(evidence.ffmpeg_inventory(IDS["portal"])["state"], "not_found_on_PATH")
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": "garbage"})()):
            with self.assertRaisesRegex(ValueError, "malformed FFmpeg presence"):
                evidence.ffmpeg_inventory(IDS["portal"])

    def test_parser_synthetic_registration_samples(self):
        self.assertEqual(evidence.parse_ffmpeg(" V..... mpeg4 MPEG-4\n", "encoders"), ["mpeg4"])
        self.assertEqual(evidence.parse_ffmpeg("Input:\n  file\nOutput:\n  pipe\n", "protocols"),
                         {"input": ["file"], "output": ["pipe"]})


if __name__ == "__main__":
    unittest.main()
