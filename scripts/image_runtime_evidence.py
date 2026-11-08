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
    r"libglib-2\.0\.so|libxml2\.so|libexpat\.so|libaom\.so|"
    r"_sqlite3\..*\.so|pyexpat\..*\.so)(?:\..*)?\Z"
)
SYMBOLS = {
    "zlib_minizip": re.compile(r"^(?:inflate|deflate|crc32|uncompress|unz[A-Z]\w*|zip[A-Z]\w*)$"),
    "mbedtls_crypto_ffdh": re.compile(r"^mbedtls_(?:dhm|mpi|rsa|ecdh|ctr_drbg|version)_\w+$"),
    "mbedtls_x509_tls": re.compile(r"^mbedtls_(?:x509|ssl)_\w+$"),
    "sqlite_fts_session": re.compile(r"^sqlite3(?:session|changeset|_compileoption|_fts5)\w*$"),
    "glib_parser": re.compile(r"^g_(?:markup|variant_parse|bytes_new)\w*$"),
    "libxml2_parser": re.compile(r"^(?:xml|html)(?:Read|Parse|CtxtRead|FreeDoc)\w*$"),
    "expat_parser": re.compile(r"^XML_(?:Parser|Parse|Set)\w*$"),
}
PACKAGES = ("zlib", "minizip", "libminizip", "mbed", "libmbed", "ffmpeg", "libav", "libaom", "libsqlite", "libglib", "libxml2", "libexpat", "perl-base")
COMPONENTS = {
    "portal": ("apps/portal", "apps/portal/Dockerfile"),
    "music": ("apps/music/backend", "apps/music/backend/Dockerfile"),
    "media": (".", "apps/media/Dockerfile"),
}
REQUIRED = {"schema", "component", "source_sha", "harness_sha", "image_ref", "image_id", "image", "build", "packages", "binaries", "ffmpeg", "sqlite", "synthetic", "interpretation_limits"}
FFMPEG_FLAGS = {"encoders": "-encoders", "decoders": "-decoders", "demuxers": "-demuxers", "muxers": "-muxers", "filters": "-filters", "protocols": "-protocols"}
PY_PROBE = r'''
import json, sqlite3, zlib, xml.parsers.expat
result={"version":sqlite3.sqlite_version,"compile_options":[],"fts5":"unavailable","json1":"unavailable","memory":"pass","zlib":"pass","expat":"pass"}
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
print(json.dumps(result,sort_keys=True))
'''


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
    # Fixed system library roots only: no application/source tree enumeration.
    cmd = "find /usr/lib /usr/local/lib -type f -name '*.so*' -print 2>/dev/null || true"
    out = run(container_cmd(image, "/bin/sh", "-c", cmd), timeout=30).stdout
    paths = sorted({p for p in out.splitlines() if p.startswith(("/usr/lib/", "/usr/local/lib/"))
                    and LIB_RE.fullmatch(Path(p).name)})
    for tool in ("/usr/bin/ffmpeg", "/usr/bin/ffprobe"):
        if run(container_cmd(image, "/bin/sh", "-c", f"test -f {tool}"), ok=False).returncode == 0:
            paths.append(tool)
    if len(paths) > 96:
        raise ValueError("unexpectedly large bounded binary inventory")
    return sorted(set(paths))


def host_binary_details(container, paths):
    results = []
    with tempfile.TemporaryDirectory(prefix="foxden-elf-") as t:
        for index, path in enumerate(paths):
            target = Path(t) / f"binary-{index}"
            run(["docker", "cp", "-L", f"{container}:{path}", str(target)], timeout=40)
            if target.stat().st_size > 35_000_000:
                raise ValueError("extracted library exceeds 35 MB bound")
            data = target.read_bytes()
            if not data.startswith(b"\x7fELF"):
                continue
            elf = run(["readelf", "-h", str(target)], timeout=10)
            dyn = run(["readelf", "-d", str(target)], timeout=10, ok=False)
            nm = run(["nm", "-D", "--defined-only", str(target)], timeout=20, ok=False)
            machine = next((line.split(":", 1)[1].strip() for line in elf.stdout.splitlines()
                            if line.strip().startswith("Machine:")), "unknown")
            needed = sorted(set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", dyn.stdout))) if dyn.returncode == 0 else []
            matched = {name: [] for name in SYMBOLS}
            if nm.returncode == 0:
                for line in nm.stdout.splitlines():
                    if not line.strip():
                        continue
                    sym = line.split()[-1].split("@", 1)[0]
                    for family, pattern in SYMBOLS.items():
                        if pattern.fullmatch(sym):
                            matched[family].append(sym)
            results.append({"image_path": path, "sha256": hashlib.sha256(data).hexdigest(),
                            "bytes": len(data), "machine": machine, "needed": needed,
                            "symbols": {k: sorted(set(v))[:150] for k, v in matched.items()},
                            "symbol_status": "inspected" if nm.returncode == 0 else "unknown_nm_failed",
                            "linkage_status": "inspected" if dyn.returncode == 0 else "unknown_readelf_failed"})
    return results


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
    "Not found in searched system paths/PATH is not proof of global absence; static, bundled or unloaded code may exist.",
    "Only synthetic SQLite/Expat/zlib and limited FFmpeg fixture paths were exercised; application invocation and exploitability remain unproven.",
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
    ffmpeg = ffmpeg_inventory(expected_image_id)
    paths = find_binary_paths(expected_image_id)
    # 'docker create' never starts an application; docker cp reads only allowlisted system ELF paths.
    create = run(["docker", "create", "--network", "none", "--read-only", "--cap-drop", "ALL",
                  "--security-opt", "no-new-privileges", "--entrypoint", "/bin/true", expected_image_id], timeout=20)
    cid = create.stdout.strip()
    if not re.fullmatch(r"[a-f0-9]{64}", cid):
        raise ValueError("malformed disposable container ID")
    try:
        binaries = host_binary_details(cid, paths)
    finally:
        run(["docker", "rm", "-f", cid], timeout=15)
    report = {"schema": 1, "component": component, "source_sha": source, "harness_sha": harness,
              "image_ref": expected_ref, "image_id": expected_image_id,
              "image": {"local_config_id": expected_image_id, "architecture": inspected.get("Architecture"),
                        "os": inspected.get("Os"), "registry_manifest_digest": None},
              "build": {"context": COMPONENTS[component][0], "dockerfile": COMPONENTS[component][1], "pull": True},
              "packages": packages, "binaries": binaries, "ffmpeg": ffmpeg,
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
    except (ValueError, OSError, subprocess.TimeoutExpired) as e:
        # Never expose stderr or collected filesystem contents in CI logs.
        p.exit(2, f"evidence collection rejected: {type(e).__name__}: {e}\n")


if __name__ == "__main__":
    main()
