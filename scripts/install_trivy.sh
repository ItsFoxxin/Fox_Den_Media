#!/usr/bin/env bash
# Official release artifact, pinned release version and pinned checksum manifest.
# Call with "bash scripts/install_trivy.sh <destination-directory>".
set -euo pipefail
destination="$1"
version="0.76.2"
manifest_sha256="802e4ac1418ed967cd3c4b901f4f71ca00b7363ede67778665a22d9f13f58c83"
archive="trivy_${version}_Linux-64bit.tar.gz"
base="https://github.com/aquasecurity/trivy/releases/download/v${version}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$destination"
curl --fail --location --silent --show-error --retry 3 --retry-all-errors   "$base/trivy_${version}_checksums.txt" --output "$tmp/checksums.txt"
printf '%s  %s\n' "$manifest_sha256" "$tmp/checksums.txt" | sha256sum --check
curl --fail --location --silent --show-error --retry 3 --retry-all-errors   "$base/$archive" --output "$tmp/$archive"
(
  cd "$tmp"
  awk -v name="$archive" '$2 == name {print $1 "  " name}' checksums.txt | sha256sum --check
)
tar -xzf "$tmp/$archive" -C "$tmp" trivy
install -m 0755 "$tmp/trivy" "$destination/trivy"
"$destination/trivy" --version
