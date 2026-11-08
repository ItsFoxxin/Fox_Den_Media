#!/usr/bin/env python3
"""Bounded, read-only replacement-image evidence for Issue #76 (stdlib only).

Never records container file contents, raw command output, environment or full symbols.
This is an evidence *collector*, not a vulnerability applicability decision.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE_RE = re.compile(r"[a-f0-9]{40}\Z")
IMAGE_RE = re.compile(r"sha256:[a-f0-9]{64}\Z")
LIB_RE = re.compile(
    r"^(?:libz\.so|libminizip\.so|libmbedcrypto\.so|libmbedtls\.so|"
    r"libmbedx509\.so|libavcodec\.so|libavformat\.so|libavfilter\.so|"
    r"libavutil\.so|libswscale\.so|libswresample\.so|libsqlite3\.so|"
    r"libglib-2\.0\.so|libgobject-2\.0\.so|libgio-2\.0\.so|"
    r"libxml2\.so|libexpat\.so|libaom\.so|librist\.so|"
    r"libgnutls\.so|libssl\.so|libcrypto\.so|"
    r"libminizip[^\s/]*\.a|libzip[^\s/]*\.a|librist[^\s/]*\.a|"
    r"_sqlite3\..*\.so|pyexpat\..*\.so|_etree\..*\.so)"
    r"(?:\..*)?\Z"
)
SYMBOLS = {
    "zlib_minizip": re.compile(r"^(?:inflate|deflate|crc32|uncompress|unz[A-Za-z0-9_]*|zip[A-Za-z0-9_]*|mz_(?:zip|unzip|stream)_[A-Za-z0-9_]*)$"),
    "mbedtls_crypto_ffdh": re.compile(r"^mbedtls_(?:dhm|mpi|rsa|ecdh|ctr_drbg|version)_[A-Za-z0-9_]+$"),
    "psa_crypto": re.compile(r"^(?:psa_export_public_key|psa_(?:import|generate|export|destroy|sign|verify|key_derivation|raw_key_agreement)[A-Za-z0-9_]*)$"),
    "mbedtls_x509_tls": re.compile(r"^(?:mbedtls_(?:x509|ssl)_[A-Za-z0-9_]+|X509_[A-Za-z0-9_]+|SSL_[A-Za-z0-9_]+|gnutls_(?:x509|handshake|certificate)[A-Za-z0-9_]*)$"),
    "sqlite_fts_session": re.compile(r"^sqlite3(?:session|changeset|_compileoption|_fts5)[A-Za-z0-9_]*$"),
    "glib_parser": re.compile(r"^g_(?:markup|variant_parse|bytes_new)[A-Za-z0-9_]*$"),
    "gio_gdbus": re.compile(r"^(?:g_dbus_[A-Za-z0-9_]+|g_bus_(?:get|own|watch)[A-Za-z0-9_]*|g_io_[A-Za-z0-9_]+)$"),
    "libxml2_parser": re.compile(r"^(?:xml|html)(?:Read|Parse|Ctxt|SAX|CreatePush|XPath|FreeDoc|NewParser)[A-Za-z0-9_]*$"),
    "expat_parser": re.compile(r"^XML_(?:Parser|Parse|Set)[A-Za-z0-9_]*$"),
}
PACKAGES = ("zlib", "minizip", "libminizip", "mbed", "libmbed", "ffmpeg", "libav", "libaom", "libsqlite", "libglib", "libgobject", "libgio", "libxml2", "libexpat", "librist", "libgnutls", "libssl", "openssl", "perl-base")
COMPONENTS = {
    "portal": ("apps/portal", "apps/portal/Dockerfile"),
    "music": ("apps/music/backend", "apps/music/backend/Dockerfile"),
    "media": (".", "apps/media/Dockerfile"),
}
REQUIRED = {"schema", "component", "source_sha", "harness_sha", "image_ref", "image_id", "image", "build", "packages", "binaries", "ffmpeg", "targeted_ffmpeg", "sqlite", "sqlite_copy", "python_xml", "native_relationships", "synthetic", "interpretation_limits"}
FFMPEG_FLAGS = {"encoders": "-encoders", "decoders": "-decoders", "demuxers": "-demuxers", "muxers": "-muxers", "filters": "-filters", "protocols": "-protocols"}
PY_PROBE = r'''
import json, sqlite3, zlib, xml.parsers.expat, pyexpat, importlib.util
result={"version":sqlite3.sqlite_version,"compile_options":[],"fts5":"unavailable","json1":"unavailable","memory":"pass","zlib":"pass","expat":"pass","python_xml":{}}
con=sqlite3.connect(":memory:")
try:
    con.execute("create table sample(value text)")
    con.execute("insert into sample values ('synthetic')")
    assert con.execute("select value from sample").fetchone()[0]=="synthetic"
    result["compile_options"]=sorted({str(r[0]) for r in con.execute("pragma compile_options")})
    try:
        con.execute("create virtual table synthetic_fts using fts5(body)")
        con.execute("insert into synthetic_fts values ('harmless sample')")
        assert con.execute("select count(*) from synthetic_fts where synthetic_fts match 'harmless'").fetchone()[0]==1
        result["fts5"]="pass"
    except sqlite3.DatabaseError:
        pass
    try:
        assert con.execute("select json_valid(?)", ('{"test":true}',)).fetchone()[0]==1
        result["json1"]="pass"
    except sqlite3.DatabaseError:
        pass
finally:
    con.close()
assert zlib.decompress(zlib.compress(b"synthetic zlib"))==b"synthetic zlib"
p=xml.parsers.expat.ParserCreate(); p.Parse(b"<fixture><safe/></fixture>",True)
result["python_xml"]["pyexpat_version"]=str(pyexpat.EXPAT_VERSION)
result["python_xml"]["xml_parsers_expat_version"]=str(xml.parsers.expat.EXPAT_VERSION)
for name in ("libxml2", "libxml2mod", "lxml", "lxml.etree", "lxml.sax"):
    try:
        result["python_xml"][name]="available" if importlib.util.find_spec(name) is not None else "not_importable"
    except (ImportError, AttributeError, ValueError):
        result["python_xml"][name]="not_importable"
print(json.dumps(result,sort_keys=True))
'''


SQLITE_COPY_PROBE = r'''
import json, sqlite3
from pathlib import Path
p=Path("/tmp/foxden-synthetic-copy.db")
source=sqlite3.connect(":memory:")
source.execute("create table synthetic_fixture(id integer primary key, sample text not null)")
source.execute("insert into synthetic_fixture(sample) values ('synthetic-only')")
source.commit()  # close the write transaction before sqlite3.Connection.backup()
target=sqlite3.connect(str(p)); source.backup(target); target.close(); source.close()
readonly=sqlite3.connect("file:/tmp/foxden-synthetic-copy.db?mode=ro", uri=True)
readonly.execute("pragma trusted_schema=off")
readonly.execute("pragma query_only=on")
value=readonly.execute("select sample from synthetic_fixture where id=1").fetchone()
integrity=readonly.execute("pragma integrity_check").fetchone()
try:
    readonly.execute("insert into synthetic_fixture(sample) values ('rejected')")
    denied=False
except sqlite3.OperationalError:
    denied=True
result={"copy_reopen":"pass" if value == ("synthetic-only",) else "failed",
        "integrity_check":"pass" if integrity == ("ok",) else "failed",
        "read_only_write_rejected":"pass" if denied else "failed",
        "trusted_schema_off":"pass" if readonly.execute("pragma trusted_schema").fetchone() == (0,) else "failed",
        "input":"fresh_synthetic_in_memory_database_copied_to_disposable_tmpfs"}
readonly.close(); p.unlink()
print(json.dumps(result, sort_keys=True))
'''

# Runs only innocuous generated color frames, never vulnerability proof-of-concepts.
# AVI/RASC is deliberately fixture_unavailable until an independently validated
# non-exploit RASC sample can be supplied. A codec listed as registered is NOT tested.
TARGET_FFMPEG_PROBE = r'''
import hashlib, json, shutil, subprocess
from pathlib import Path
root=Path("/tmp")
out={}
def call(args, limit=15):
    try:
        p=subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=limit, check=False)
        return p.returncode, p.stdout[:8192].decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, ""
def fields(text):
    d={}
    for line in text.splitlines():
        if "=" in line:
            k,v=line.split("=",1)
            if k in ("codec_name","format_name") and len(v)<100 and all(ch.isascii() and (ch.isalnum() or ch in "_,.") for ch in v):
                d[k]=v
    return d
for codec in ("cfhd","magicyuv"):
    name="avi_"+codec
    path=root/("synthetic_"+codec+".avi")
    rc,_=call(["ffmpeg","-nostdin","-hide_banner","-v","error","-y","-f","lavfi","-i","color=c=black:s=64x64:r=1",
               "-frames:v","1","-pix_fmt","yuv422p","-c:v",codec,"-f","avi",str(path)])
    if rc or not path.is_file() or path.stat().st_size > 1000000:
        out[name]={"state":"failed","stage":"synthetic_encode","input":"one_64x64_black_lavfi_frame"}
        continue
    b=path.read_bytes()
    rc,stdout=call(["ffprobe","-hide_banner","-v","error","-show_entries","stream=codec_name:format=format_name",
                    "-of","default=noprint_wrappers=1",str(path)])
    selected=fields(stdout)
    if rc or selected.get("codec_name") != codec or "avi" not in selected.get("format_name","").split(","):
        out[name]={"state":"failed","stage":"format_or_codec_selection","selected":selected,
                   "input_sha256":hashlib.sha256(b).hexdigest()}
        continue
    rc,_=call(["ffmpeg","-nostdin","-hide_banner","-v","error","-c:v",codec,"-i",str(path),
               "-frames:v","1","-f","null","-"])
    out[name]={"state":"pass" if rc == 0 else "failed",
               "stage":"forced_decoder_synthetic_roundtrip",
               "selected":selected,"input_sha256":hashlib.sha256(b).hexdigest(),
               "input":"synthetic_avi_one_black_frame","forced_decoder":codec}
base=next((root/("synthetic_"+c+".avi") for c in ("cfhd","magicyuv")
           if out.get("avi_"+c,{}).get("state") == "pass"),None)
for suffix,label in ((".sub","music_ffprobe_vobsub_mislabel"),(".mpd","music_ffprobe_dash_mislabel")):
    if base is None:
        out[label]={"state":"fixture_unavailable","reason":"no_valid_synthetic_avi_baseline"}
        continue
    dest=root/("synthetic_mislabeled"+suffix)
    shutil.copyfile(base,dest)
    rc,stdout=call(["ffprobe","-hide_banner","-v","error","-show_entries","format=format_name",
                    "-of","default=noprint_wrappers=1",str(dest)])
    out[label]={"state":"accepted" if rc == 0 else "rejected","input":"synthetic_avi_bytes_mislabeled_extension",
                "input_sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),
                "selected_format":fields(stdout).get("format_name"),
                "application_invocation":"not_demonstrated"}
out["avi_rasc"]={"state":"fixture_unavailable",
                  "reason":"no_verified_benign_RASC_AVI_fixture_or_RASC_encoder",
                  "decoder_invocation":"not_demonstrated"}
print(json.dumps(out, sort_keys=True))
'''

def sqlite_copy_probe(image):
    raw = run(container_cmd(image, "python", "-I", "-c", SQLITE_COPY_PROBE, tmpfs=True), timeout=30).stdout
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        raise ValueError("malformed copied SQLite probe output") from e
    if not isinstance(data, dict) or any(data.get(k) != "pass" for k in
       ("copy_reopen", "integrity_check", "read_only_write_rejected", "trusted_schema_off")):
        raise ValueError("incomplete copied SQLite trust-boundary evidence")
    return data

def targeted_ffmpeg_probe(image, registrations):
    if registrations is None:
        return {"state":"not_found_on_PATH", "fixtures": None}
    raw = run(container_cmd(image, "python", "-I", "-c", TARGET_FFMPEG_PROBE, tmpfs=True),
              timeout=100).stdout
    try:
        fixtures = json.loads(raw)
    except (ValueError, TypeError) as e:
        raise ValueError("malformed targeted FFmpeg probe output") from e
    required = {"avi_rasc", "avi_cfhd", "avi_magicyuv",
                "music_ffprobe_vobsub_mislabel", "music_ffprobe_dash_mislabel"}
    if not isinstance(fixtures, dict) or fixtures.keys() != required:
        raise ValueError("missing targeted FFmpeg fixture report")
    for key in required:
        row = fixtures[key]
        if not isinstance(row, dict) or row.get("state") not in (
            "pass", "failed", "accepted", "rejected", "fixture_unavailable"):
            raise ValueError("malformed targeted FFmpeg fixture state")
        if row.get("input_sha256") is not None and not re.fullmatch(
                r"[a-f0-9]{64}", row["input_sha256"]):
            raise ValueError("unbound synthetic fixture hash")
    # Do not imply decode was tested from registry entries without a valid fixture.
    fixtures["avi_rasc"]["decoder_registered"] = "rasc" in registrations["decoders"]
    fixtures["avi_rasc"]["demuxer_registered"] = "avi" in registrations["demuxers"]
    return {"state":"tested_synthetic_only", "fixtures": fixtures}

def require_sha(value, label):
    if not isinstance(value, str) or not SOURCE_RE.fullmatch(value):
        raise ValueError(f"invalid {label}: expected full lowercase Git SHA")
    return value


def require_image_id(value):
    if not isinstance(value, str) or not IMAGE_RE.fullmatch(value):
        raise ValueError("unbound/invalid image ID: expected sha256 configuration ID")
    return value


def run(argv, timeout=40, ok=True):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if ok and p.returncode != 0:
        raise ValueError(f"probe failed: {argv[0]} returned {p.returncode}")
    if len(p.stdout) > 2_000_000:
        raise ValueError("probe output exceeds bounded limit")
    return p


def validate_checkout(path, sha, name):
    observed = run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout.strip()
    if observed != require_sha(sha, name + " sha"):
        raise ValueError(f"wrong {name} checkout identity")


def container_cmd(image, *argv, tmpfs=False):
    flags = ["docker", "run", "--rm", "--pull", "never", "--network", "none",
             "--cap-drop", "ALL", "--read-only", "--security-opt", "no-new-privileges",
             "--pids-limit", "64", "--memory", "512m", "--cpus", "1"]
    if tmpfs:
        flags += ["--tmpfs", "/tmp:rw,nosuid,noexec,size=32m"]
    return flags + ["--entrypoint", argv[0], image, *argv[1:]]


def parse_ffmpeg(text, kind):
    if kind == "protocols":
        input_names, output_names, section = set(), set(), None
        for raw in text.splitlines():
            s = raw.strip()
            if s == "Input:":
                section = input_names
            elif s == "Output:":
                section = output_names
            elif section is not None and re.fullmatch(r"[A-Za-z0-9_+.-]{1,80}", s):
                section.add(s)
        if not input_names and not output_names:
            raise ValueError("malformed FFmpeg protocol output")
        return {"input": sorted(input_names), "output": sorted(output_names)}
    found = set()
    for line in text.splitlines():
        # FFmpeg list output has a short flag column followed by registered names.
        m = re.match(r"^\s*[A-Z.]{1,6}\s+([A-Za-z0-9_.,+\-]{1,120})(?:\s|$)", line)
        if m and not line.lstrip().startswith("="):
            for name in m.group(1).split(","):
                if name and name != "=":
                    found.add(name)
    if not found:
        raise ValueError(f"malformed/empty FFmpeg {kind} output")
    return sorted(found)


def ffmpeg_inventory(image):
    # Dash uses exit 127 (not 1) for a missing command. Always report a
    # literal token so absence is not confused with a Docker/exec failure.
    probe = ("if command -v ffmpeg >/dev/null 2>&1; "
             "then printf present; else printf absent; fi")
    state = run(container_cmd(image, "/bin/sh", "-c", probe)).stdout.strip()
    if state == "absent":
        return {"state": "not_found_on_PATH", "registrations": None, "fixture": "not_run"}
    if state != "present":
        raise ValueError("malformed FFmpeg presence probe output")
    registrations = {}
    for kind, flag in FFMPEG_FLAGS.items():
        out = run(container_cmd(image, "ffmpeg", "-hide_banner", flag), timeout=25)
        registrations[kind] = parse_ffmpeg(out.stdout, kind)
    # In the disposable container: /tmp is memory-only; no network or capabilities.
    fixture = ("ffmpeg -nostdin -hide_banner -loglevel error -y -f lavfi -i "
               "color=c=black:s=16x16:r=1 -frames:v 1 -c:v mpeg4 -f matroska /tmp/synthetic.mkv "
               "&& ffmpeg -nostdin -hide_banner -loglevel error -i /tmp/synthetic.mkv "
               "-frames:v 1 -f null -")
    result = run(container_cmd(image, "/bin/sh", "-c", fixture, tmpfs=True), timeout=35, ok=False)
    return {"state": "present", "registrations": registrations,
            "fixture": "pass" if result.returncode == 0 else "failed"}


def find_binary_paths(image):
    # Inspect only fixed code/library roots, never media/config/user-state paths.
    cmd = ("find /usr/lib /usr/local/lib /app -maxdepth 9 -type f "
           "\\( -name '*.so*' -o -name '*.a' \\) -print 2>/dev/null || true")
    out = run(container_cmd(image, "/bin/sh", "-c", cmd), timeout=30).stdout
    paths = set()
    app_count = 0
    for path in out.splitlines():
        if not path.startswith(("/usr/lib/", "/usr/local/lib/", "/app/")):
            continue
        name = Path(path).name
        if LIB_RE.fullmatch(name):
            paths.add(path)
        elif path.startswith("/app/") and (".so" in name or name.endswith(".a")):
            paths.add(path)
            app_count += 1
    if app_count > 24:
        raise ValueError("bounded application native library inventory exceeded")
    for tool in ("/usr/bin/ffmpeg", "/usr/bin/ffprobe"):
        if run(container_cmd(image, "/bin/sh", "-c", f"test -f {tool}"), ok=False).returncode == 0:
            paths.add(tool)
    if len(paths) > 96:
        raise ValueError("unexpectedly large bounded binary inventory")
    return sorted(paths)


def package_ownership(image, paths):
    out = run(container_cmd(image, "dpkg-query", "-S", *paths), timeout=30, ok=False).stdout
    owned = {}
    for line in out.splitlines():
        for path in paths:
            if line.endswith(": " + path):
                prefix = line[:-(len(path)+2)]
                names = {x.strip().split(":", 1)[0] for x in prefix.split(",")}
                names = sorted(x for x in names if re.fullmatch(r"[a-z0-9][a-z0-9.+-]{0,90}", x))
                if names:
                    owned[path] = names[:6]
    return owned


def host_binary_details(container, paths, owners):
    results = []
    with tempfile.TemporaryDirectory(prefix="foxden-elf-") as t:
        for index, path in enumerate(paths):
            target = Path(t) / f"binary-{index}"
            run(["docker", "cp", "-L", f"{container}:{path}", str(target)], timeout=40)
            if target.stat().st_size > 35_000_000:
                raise ValueError("extracted library exceeds 35 MB bound")
            data = target.read_bytes()
            elf = data.startswith(b"\x7fELF")
            archive = path.endswith(".a") and data.startswith(b"!<arch>\n")
            if not (elf or archive):
                continue
            needed, machine, linked = [], "static_archive_unknown_machine", False
            if elf:
                hdr = run(["readelf", "-h", str(target)], timeout=10)
                dyn = run(["readelf", "-d", str(target)], timeout=10, ok=False)
                machine = next((x.split(":", 1)[1].strip() for x in hdr.stdout.splitlines()
                                if x.strip().startswith("Machine:")), "unknown")
                linked = dyn.returncode == 0
                if linked:
                    needed = sorted(set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", dyn.stdout)))
            defs = run(["nm", "-D" if elf else "-g", "--defined-only", str(target)], timeout=25, ok=False)
            imps = run(["nm", "-D", "--undefined-only", str(target)], timeout=25, ok=False) if elf else None
            matched = {key: [] for key in SYMBOLS}
            imported = {key: [] for key in SYMBOLS}
            for probe, destination in ((defs, matched), (imps, imported)):
                if probe is None or probe.returncode != 0:
                    continue
                for line in probe.stdout.splitlines():
                    bits = line.split()
                    if not bits:
                        continue
                    symbol = bits[-1].split("@", 1)[0]
                    for group, pattern in SYMBOLS.items():
                        if pattern.fullmatch(symbol):
                            destination[group].append(symbol)
            results.append({
                "image_path": path, "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "format": "ELF" if elf else "static_archive",
                "machine": machine, "needed": needed,
                "package_owners": owners.get(path, []),
                "ownership_status": "dpkg_matched" if path in owners else "not_identified_by_dpkg",
                "symbols": {k: sorted(set(v))[:150] for k,v in matched.items()},
                "imports": {k: sorted(set(v))[:150] for k,v in imported.items()},
                "symbol_status": "inspected" if defs.returncode == 0 else "unknown_nm_failed",
                "import_status": "inspected" if imps is not None and imps.returncode == 0 else "not_available",
                "linkage_status": "inspected" if linked else "not_available"})
    return results


def related_native_evidence(binaries):
    def group(prefix, category, dependency):
        selected = [x for x in binaries if Path(x["image_path"]).name.startswith(prefix)]
        return {
            "state": "identified" if selected else "not_identified_in_bounded_inventory",
            "paths": [x["image_path"] for x in selected][:20],
            "needed": sorted({n for x in selected for n in x["needed"]})[:40],
            "imported_selected": sorted({n for x in selected for n in x["imports"].get(category, [])})[:60],
            "direct_needed_match": any(dependency in n for x in selected for n in x["needed"]),
            "note": "linkage/symbol observation only; usage is not demonstrated"}
    mini_names = [x["image_path"] for x in binaries if "minizip" in x["image_path"].lower()]
    bundled = [x["image_path"] for x in binaries if x["image_path"] not in mini_names and
               (x["symbols"]["zlib_minizip"] or x["imports"]["zlib_minizip"])]
    return {
        "minizip": {"named_candidates": mini_names[:40],
                    "other_binary_symbol_candidates": bundled[:40],
                    "limit": "stripped/embedded MiniZip cannot be excluded"},
        "librist_mbed_crypto": group("librist.so", "mbedtls_crypto_ffdh", "libmbedcrypto"),
        "libavformat_xml2": group("libavformat.so", "libxml2_parser", "libxml2"),
        "gio_gdbus": group("libgio-2.0.so", "gio_gdbus", "libglib"),
    }


def package_inventory(image):
    out = run(container_cmd(image, "dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"), timeout=25).stdout
    items = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError("malformed dpkg package output")
        name, version, arch = parts
        if name.startswith(PACKAGES):
            if not all(re.fullmatch(r"[A-Za-z0-9_.+~:\-]{1,150}", x) for x in parts):
                raise ValueError("unsafe package inventory field")
            items.append({"name": name, "version": version, "arch": arch})
    return sorted(items, key=lambda item: item["name"])


def python_probe(image):
    raw = run(container_cmd(image, "python", "-I", "-c", PY_PROBE), timeout=25).stdout
    try:
        result = json.loads(raw)
    except (ValueError, TypeError) as e:
        raise ValueError("malformed Python synthetic probe JSON") from e
    required = {"version", "compile_options", "fts5", "json1", "memory", "zlib", "expat"}
    if not isinstance(result, dict) or not required.issubset(result) or not isinstance(result["compile_options"], list):
        raise ValueError("incomplete Python synthetic probe")
    if not isinstance(result.get("python_xml"), dict) or not result["python_xml"].get("pyexpat_version"):
        raise ValueError("incomplete Python XML binding/version probe")
    if any(result.get(key) != "pass" for key in ("memory", "zlib", "expat")):
        raise ValueError("required harmless Python fixture failed")
    return result


def validate_report(report, *, source, harness, component=None, image_id=None):
    require_sha(source, "expected source")
    require_sha(harness, "expected harness")
    if not isinstance(report, dict) or not REQUIRED.issubset(report):
        raise ValueError("incomplete component report")
    c = report["component"]
    if c not in COMPONENTS or (component is not None and c != component):
        raise ValueError("wrong component identity")
    if report["schema"] != 1 or report["source_sha"] != source or report["harness_sha"] != harness:
        raise ValueError("wrong source/harness identity")
    bound = require_image_id(report["image_id"])
    if image_id is not None and bound != require_image_id(image_id):
        raise ValueError("wrong image binding")
    if report["image_ref"] != f"foxden-evidence-{c}:{source}":
        raise ValueError("wrong image tag binding")
    if not isinstance(report["image"], dict) or report["image"].get("local_config_id") != bound:
        raise ValueError("unbound image config ID")
    if report["image"].get("architecture") not in ("amd64", "arm64") or report["image"].get("os") != "linux":
        raise ValueError("missing/invalid image architecture")
    if report["build"] != {"context": COMPONENTS[c][0], "dockerfile": COMPONENTS[c][1], "pull": True}:
        raise ValueError("build context/identity mismatch")
    if not isinstance(report["packages"], list) or not report["packages"] or not isinstance(report["binaries"], list) or not report["binaries"]:
        raise ValueError("missing/empty component inventories")
    if not isinstance(report["sqlite"], dict) or not isinstance(report["sqlite"].get("compile_options"), list):
        raise ValueError("incomplete SQLite evidence")
    if report["sqlite"].get("memory") != "pass":
        raise ValueError("missing SQLite synthetic fixture")
    if not isinstance(report["synthetic"], dict) or any(report["synthetic"].get(k) != "pass" for k in ("zlib", "expat")):
        raise ValueError("incomplete synthetic tests")
    if not isinstance(report["ffmpeg"], dict) or report["ffmpeg"].get("state") not in ("present", "not_found_on_PATH"):
        raise ValueError("incomplete FFmpeg inventory")
    if report["ffmpeg"]["state"] == "present":
        regs = report["ffmpeg"].get("registrations")
        if not isinstance(regs, dict) or regs.keys() != FFMPEG_FLAGS.keys() or any(not v for v in regs.values()) or not regs["protocols"].get("input") or not regs["protocols"].get("output"):
            raise ValueError("missing FFmpeg registration family")
        if report["ffmpeg"].get("fixture") not in ("pass", "failed"):
            raise ValueError("missing FFmpeg fixture result")
    if not isinstance(report["python_xml"], dict) or any(
            key not in report["python_xml"] for key in
            ("pyexpat_version", "xml_parsers_expat_version", "libxml2", "libxml2mod", "lxml", "lxml.etree", "lxml.sax")):
        raise ValueError("missing Python XML binding evidence")
    if not isinstance(report["sqlite_copy"], dict) or any(
            report["sqlite_copy"].get(key) != "pass" for key in
            ("copy_reopen", "integrity_check", "read_only_write_rejected", "trusted_schema_off")):
        raise ValueError("missing copied SQLite trust boundary")
    if not isinstance(report["native_relationships"], dict) or report["native_relationships"].keys() != {
            "minizip", "librist_mbed_crypto", "libavformat_xml2", "gio_gdbus"}:
        raise ValueError("missing native linkage relationship coverage")
    if any(not isinstance(row, dict) or "imports" not in row or
           "package_owners" not in row or "format" not in row for row in report["binaries"]):
        raise ValueError("incomplete native binary ownership or symbol evidence")
    targeted = report["targeted_ffmpeg"]
    if not isinstance(targeted, dict):
        raise ValueError("incomplete targeted FFmpeg probes")
    if report["ffmpeg"]["state"] == "present":
        expected = {"avi_rasc", "avi_cfhd", "avi_magicyuv",
                    "music_ffprobe_vobsub_mislabel", "music_ffprobe_dash_mislabel"}
        fixtures = targeted.get("fixtures")
        if targeted.get("state") != "tested_synthetic_only" or not isinstance(fixtures, dict) or fixtures.keys() != expected:
            raise ValueError("missing targeted decoder/FFprobe fixtures")
        for key, row in fixtures.items():
            if not isinstance(row, dict) or row.get("state") not in ("pass", "failed", "accepted", "rejected", "fixture_unavailable"):
                raise ValueError("missing targeted decoder/FFprobe outcome")
    elif targeted != {"state": "not_found_on_PATH", "fixtures": None}:
        raise ValueError("unexpected targeted FFmpeg output for absent executable")
    if not isinstance(report["interpretation_limits"], list) or len(report["interpretation_limits"]) < 3:
        raise ValueError("missing interpretation limits")
    return True


def report_markdown(r):
    lines = [f"# Runtime/binary evidence: {r['component']}", "",
             f"- Approved source checkout: `{r['source_sha']}`",
             f"- Evidence harness checkout: `{r['harness_sha']}`",
             f"- Replacement image local config ID: `{r['image_id']}`",
             f"- Architecture: `{r['image']['architecture']}`; historical image: **not recovered**",
             f"- Selected OS packages: {len(r['packages'])}; inspected ELF files: {len(r['binaries'])}",
             f"- SQLite: {r['sqlite']['version']}; synthetic memory/FTS5/JSON1: {r['sqlite']['memory']}/{r['sqlite']['fts5']}/{r['sqlite']['json1']}",
             f"- zlib roundtrip: {r['synthetic']['zlib']}; Expat synthetic parse: {r['synthetic']['expat']}",
             f"- FFmpeg: {r['ffmpeg']['state']}; synthetic encoder→muxer→demuxer→decoder: {r['ffmpeg']['fixture']}", ""]
    lines += ["## Targeted decoder and probe fixtures", ""]
    probes = r["targeted_ffmpeg"]["fixtures"]
    if probes is None:
        lines.append("- FFmpeg not on PATH in this image; targeted probes not run.")
    else:
        for key in sorted(probes):
            lines.append(f"- {key}: {probes[key]['state']}" +
                         (f" (stage: {probes[key]['stage']})" if probes[key].get("stage") else ""))
    lines += ["", "## Native linkage and bindings", "",
              f"- MiniZip named native candidates: {len(r['native_relationships']['minizip']['named_candidates'])}",
              f"- GDBus/libgio candidate state: {r['native_relationships']['gio_gdbus']['state']}",
              f"- librist/Mbed crypto relationship: {r['native_relationships']['librist_mbed_crypto']['state']}",
              f"- libavformat/libxml2 relationship: {r['native_relationships']['libavformat_xml2']['state']}",
              f"- Python Expat version: {r['python_xml']['pyexpat_version']}",
              f"- Synthetic copied SQLite read-only / trusted schema checks: {r['sqlite_copy']['read_only_write_rejected']} / {r['sqlite_copy']['trusted_schema_off']}", ""]
    if r['ffmpeg']['registrations']:
        lines += ["## FFmpeg registered feature counts", ""]
        for key, value in r['ffmpeg']['registrations'].items():
            count = sum(len(x) for x in value.values()) if isinstance(value, dict) else len(value)
            lines.append(f"- {key}: {count}")
        lines.append("")
    lines += ["## Interpretation boundaries", ""] + [f"- {x}" for x in r['interpretation_limits']]
    return "\n".join(lines) + "\n"


LIMITS = [
    "New --pull build is a reproducible replacement, NOT a preserved historical CI image or immutable OCI manifest digest.",
    "Base tags, apt and pip dependencies may drift; exact layer equivalence to historical images is not established.",
    "Exported symbols show presence only; registration does not establish application invocation or vulnerability reachability.",
    "Not identified by bounded static/native/dynamic symbol scanning is not proof of global absence or non-applicability.",
    "Only synthetic SQLite-copy/Expat/zlib and limited FFmpeg/FFprobe fixtures were exercised; application invocation remains unproven.",
]


def collect(args):
    source = require_sha(args.source_sha, "source")
    harness = require_sha(args.harness_sha, "harness")
    validate_checkout(args.source_dir, source, "source")
    validate_checkout(args.harness_dir, harness, "harness")
    component = args.component
    expected_ref = f"foxden-evidence-{component}:{source}"
    if args.image_ref != expected_ref:
        raise ValueError("image ref does not bind to approved source")
    expected_image_id = require_image_id(args.image_id)
    raw = run(["docker", "image", "inspect", expected_ref, "--format", "{{json .}}"], timeout=20).stdout
    try:
        inspected = json.loads(raw)
    except ValueError as e:
        raise ValueError("malformed Docker inspect output") from e
    if inspected.get("Id") != expected_image_id or inspected.get("Os") != "linux":
        raise ValueError("unbound image config ID or unsupported OS")
    packages = package_inventory(expected_image_id)
    sqlite = python_probe(expected_image_id)
    sqlite_copy = sqlite_copy_probe(expected_image_id)
    ffmpeg = ffmpeg_inventory(expected_image_id)
    targeted = targeted_ffmpeg_probe(expected_image_id, ffmpeg["registrations"])
    paths = find_binary_paths(expected_image_id)
    owners = package_ownership(expected_image_id, paths)
    # 'docker create' never starts an application; docker cp reads only allowlisted system ELF paths.
    create = run(["docker", "create", "--network", "none", "--read-only", "--cap-drop", "ALL",
                  "--security-opt", "no-new-privileges", "--entrypoint", "/bin/true", expected_image_id], timeout=20)
    cid = create.stdout.strip()
    if not re.fullmatch(r"[a-f0-9]{64}", cid):
        raise ValueError("malformed disposable container ID")
    try:
        binaries = host_binary_details(cid, paths, owners)
    finally:
        run(["docker", "rm", "-f", cid], timeout=15)
    report = {"schema": 1, "component": component, "source_sha": source, "harness_sha": harness,
              "image_ref": expected_ref, "image_id": expected_image_id,
              "image": {"local_config_id": expected_image_id, "architecture": inspected.get("Architecture"),
                        "os": inspected.get("Os"), "registry_manifest_digest": None},
              "build": {"context": COMPONENTS[component][0], "dockerfile": COMPONENTS[component][1], "pull": True},
              "packages": packages, "binaries": binaries, "ffmpeg": ffmpeg,
              "targeted_ffmpeg": targeted, "native_relationships": related_native_evidence(binaries),
              "sqlite_copy": sqlite_copy, "python_xml": sqlite["python_xml"],
              "sqlite": {k: sqlite[k] for k in ("version", "compile_options", "fts5", "json1", "memory")},
              "synthetic": {"zlib": sqlite["zlib"], "expat": sqlite["expat"]},
              "interpretation_limits": LIMITS}
    validate_report(report, source=source, harness=harness, component=component, image_id=expected_image_id)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "summary.md").write_text(report_markdown(report))


def verify(args):
    source, harness = require_sha(args.source_sha, "source"), require_sha(args.harness_sha, "harness")
    root = Path(args.reports_dir)
    manifest = {"schema": 1, "source_sha": source, "harness_sha": harness,
                "historical_images_recovered": False, "components": {}}
    ids = set()
    for component in COMPONENTS:
        path = root / component / "report.json"
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError(f"missing/oversized {component} report")
        try:
            raw = path.read_bytes()
            report = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"malformed {component} report") from e
        validate_report(report, source=source, harness=harness, component=component)
        if report["image_id"] in ids:
            raise ValueError("two components share an unbound image ID")
        ids.add(report["image_id"])
        manifest["components"][component] = {"image_id": report["image_id"],
                                               "report_sha256": hashlib.sha256(raw).hexdigest()}
    if args.output:
        Path(args.output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="mode", required=True)
    a = commands.add_parser("collect")
    a.add_argument("--component", required=True, choices=COMPONENTS)
    for name in ("source-sha", "harness-sha", "source-dir", "harness-dir", "image-ref", "image-id", "output"):
        a.add_argument("--" + name, required=True)
    v = commands.add_parser("verify")
    for name in ("source-sha", "harness-sha", "reports-dir"):
        v.add_argument("--" + name, required=True)
    v.add_argument("--output")
    args = p.parse_args()
    try:
        if args.mode == "collect":
            for tool in ("docker", "readelf", "nm", "git"):
                if not shutil.which(tool):
                    raise ValueError(f"required host tool not available: {tool}")
            collect(args)
        else:
            verify(args)
    except subprocess.TimeoutExpired:
        # TimeoutExpired includes argv (and embedded Python source). Do not log it.
        p.exit(2, "evidence collection rejected: bounded probe timeout\n")
    except (ValueError, OSError) as e:
        # Never expose stderr or collected filesystem contents in CI logs.
        p.exit(2, f"evidence collection rejected: {type(e).__name__}: {e}\n")


if __name__ == "__main__":
    main()
