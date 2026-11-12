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
        "binaries": [{"image_path": "/usr/lib/libz.so.1", "sha256": "1" * 64,
                      "format": "ELF", "imports": {k: [] for k in evidence.SYMBOLS},
                      "package_owners": ["zlib1g"]}],
        "ffmpeg": {"state": "not_found_on_PATH", "registrations": None, "fixture": "not_run"},
        "sqlite": {"version": "3.40.1", "compile_options": [], "fts5": "pass",
                   "json1": "pass", "memory": "pass"},
        "sqlite_copy": {k: "pass" for k in ("copy_reopen", "integrity_check",
                      "read_only_write_rejected", "trusted_schema_off")},
        "python_xml": {"pyexpat_version": "expat_2.5.0",
                       "xml_parsers_expat_version": "expat_2.5.0",
                       **{k: "not_importable" for k in
                          ("libxml2", "libxml2mod", "lxml", "lxml.etree", "lxml.sax")}},
        "native_relationships": {
            "minizip": {"named_candidates": [], "other_binary_symbol_candidates": []},
            "librist_mbed_crypto": {"state": "not_identified_in_bounded_inventory"},
            "libavformat_xml2": {"state": "not_identified_in_bounded_inventory"},
            "gio_gdbus": {"state": "not_identified_in_bounded_inventory"}},
        "targeted_ffmpeg": {"state": "not_found_on_PATH", "fixtures": None},
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

    def test_debian_mbed_and_minizip_package_versions_retained(self):
        fixture = ("libmbedcrypto7\t2.28.3-1\tamd64\n"
                   "libmbedx509-1\t2.28.3-1\tamd64\n"
                   "libmbedtls14\t2.28.3-1\tamd64\n"
                   "libminizip1\t1.2.13-1\tamd64\n"
                   "unrelated\t1.0\tamd64\n")
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": fixture})()):
            packages = evidence.package_inventory(IDS["media"])
        self.assertEqual({p["name"] for p in packages},
                         {"libmbedcrypto7", "libmbedx509-1", "libmbedtls14", "libminizip1"})

    def test_parser_synthetic_registration_samples(self):
        self.assertEqual(evidence.parse_ffmpeg(" V..... mpeg4 MPEG-4\n", "encoders"), ["mpeg4"])
        self.assertEqual(evidence.parse_ffmpeg("Input:\n  file\nOutput:\n  pipe\n", "protocols"),
                         {"input": ["file"], "output": ["pipe"]})


    def test_missing_followup_coverage_fails_closed(self):
        for key in ("python_xml", "sqlite_copy", "native_relationships", "targeted_ffmpeg"):
            r = report("music")
            r.pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "incomplete"):
                evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        r["sqlite_copy"]["trusted_schema_off"] = "failed"
        with self.assertRaisesRegex(ValueError, "SQLite trust"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        r["binaries"][0].pop("imports")
        with self.assertRaisesRegex(ValueError, "ownership or symbol"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)
        r = report("portal")
        r["python_xml"].pop("pyexpat_version")
        with self.assertRaisesRegex(ValueError, "Python XML"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)

    def test_targeted_ffmpeg_probe_rejects_malformed_and_missing_fixtures(self):
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": "not JSON"})()):
            with self.assertRaisesRegex(ValueError, "malformed targeted"):
                evidence.targeted_ffmpeg_probe(IDS["music"], {"decoders": [], "demuxers": []})
        fake = {
            "avi_rasc": {"state": "fixture_unavailable"},
            "avi_cfhd": {"state": "pass", "input_sha256": "e" * 64},
            "avi_magicyuv": {"state": "pass", "input_sha256": "e" * 64},
            "music_ffprobe_vobsub_mislabel": {"state": "rejected"},
            "music_ffprobe_dash_mislabel": {"state": "rejected"}}
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": json.dumps(fake)})()):
            good = evidence.targeted_ffmpeg_probe(IDS["music"], {"decoders": ["rasc"], "demuxers": ["avi"]})
        self.assertTrue(good["fixtures"]["avi_rasc"]["decoder_registered"])
        self.assertEqual(good["fixtures"]["avi_rasc"]["state"], "fixture_unavailable")
        for bad in ({k: v for k,v in fake.items() if k != "avi_rasc"},
                    {**fake, "avi_cfhd": {"state": "unproven"}},
                    {**fake, "avi_cfhd": {"state": "pass", "input_sha256": "wrong"}}):
            with patch.object(evidence, "run", return_value=type("P", (), {"stdout": json.dumps(bad)})()):
                with self.assertRaises(ValueError):
                    evidence.targeted_ffmpeg_probe(IDS["music"], {"decoders": [], "demuxers": []})

    def test_targeted_reports_require_every_fixture_when_ffmpeg_present(self):
        r = report("media")
        r["ffmpeg"] = {"state": "present", "registrations": {
            k: {"input": ["file"], "output": ["pipe"]} if k == "protocols" else ["avi"]
            for k in evidence.FFMPEG_FLAGS}, "fixture": "pass"}
        r["targeted_ffmpeg"] = {"state": "tested_synthetic_only",
                                "fixtures": {"avi_cfhd": {"state": "pass"}}}
        with self.assertRaisesRegex(ValueError, "targeted"):
            evidence.validate_report(r, source=SOURCE, harness=HARNESS)

    def test_sqlite_copy_fixture_requires_all_trust_boundary_results(self):
        good = {k: "pass" for k in
                ("copy_reopen", "integrity_check", "read_only_write_rejected", "trusted_schema_off")}
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": json.dumps(good)})()):
            self.assertEqual(evidence.sqlite_copy_probe(IDS["portal"]), good)
        for invalid in ("not JSON", json.dumps({"copy_reopen": "pass"}),
                        json.dumps({**good, "read_only_write_rejected": "failed"})):
            with patch.object(evidence, "run", return_value=type("P", (), {"stdout": invalid})()):
                with self.assertRaises(ValueError):
                    evidence.sqlite_copy_probe(IDS["portal"])

    def test_native_relationships_do_not_infer_non_applicability(self):
        row = {"image_path": "/usr/lib/librist.so.4", "needed": ["libmbedcrypto.so.7"],
               "imports": {k: [] for k in evidence.SYMBOLS},
               "symbols": {k: [] for k in evidence.SYMBOLS}}
        row["imports"]["mbedtls_crypto_ffdh"] = ["mbedtls_dhm_init"]
        result = evidence.related_native_evidence([row])
        self.assertEqual(result["librist_mbed_crypto"]["state"], "identified")
        self.assertTrue(result["librist_mbed_crypto"]["direct_needed_match"])
        self.assertIn("mbedtls_dhm_init", result["librist_mbed_crypto"]["imported_selected"])
        self.assertEqual(result["libavformat_xml2"]["state"], "not_identified_in_bounded_inventory")
        # Generic zlib exports alone are not bundled MiniZip implementation evidence.
        row2 = {"image_path": "/usr/lib/libz.so.1", "needed": [],
                "imports": {k: [] for k in evidence.SYMBOLS},
                "symbols": {k: [] for k in evidence.SYMBOLS}}
        row2["symbols"]["zlib_minizip"] = ["inflate", "deflate"]
        only_zlib = evidence.related_native_evidence([row2])
        self.assertEqual(only_zlib["minizip"]["other_binary_symbol_candidates"], [])
        row2["symbols"]["minizip_api"] = ["unzOpen"]
        mini = evidence.related_native_evidence([row2])
        self.assertEqual(mini["minizip"]["other_binary_symbol_candidates"], ["/usr/lib/libz.so.1"])

    def test_native_path_bounding_and_symbol_pattern(self):
        self.assertIsNotNone(evidence.SYMBOLS["psa_crypto"].fullmatch("psa_export_public_key"))
        self.assertIsNotNone(evidence.SYMBOLS["gio_gdbus"].fullmatch("g_dbus_connection_call"))
        self.assertIsNotNone(evidence.LIB_RE.fullmatch("librist.so.4.2.0"))
        self.assertIsNotNone(evidence.LIB_RE.fullmatch("libminizip.a"))
        raw = "\n".join("/app/native/lib-%d.so" % i for i in range(25))
        with patch.object(evidence, "run", return_value=type("P", (), {"stdout": raw, "returncode": 0})()):
            with self.assertRaisesRegex(ValueError, "bounded application"):
                evidence.find_binary_paths(IDS["portal"])


if __name__ == "__main__":
    unittest.main()
