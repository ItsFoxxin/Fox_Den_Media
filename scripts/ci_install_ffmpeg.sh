#!/usr/bin/env bash
set -euo pipefail

# Release asset and checksum are pinned together to avoid trusting a mutable
# download or the Ubuntu package mirror during CI.
readonly FFMPEG_ARCHIVE_URL='https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-05-12-48/ffmpeg-n8.1.3-34-ga35157abb9-linux64-gpl-8.1.tar.xz'
readonly FFMPEG_ARCHIVE_SHA256='1bbd8ff31a24ecbe0714f21e47cc0c4382cc51340c32d5d35fc6fda44e168ab5'

: "${RUNNER_TEMP:?This installer requires a GitHub Actions runner}"
: "${GITHUB_PATH:?This installer requires a GitHub Actions runner}"

archive="$RUNNER_TEMP/foxden-ci-ffmpeg.tar.xz"
extract_dir="$RUNNER_TEMP/foxden-ci-ffmpeg"
bin_dir="$RUNNER_TEMP/foxden-ci-bin"

mkdir -p "$extract_dir" "$bin_dir"
curl --fail --location --retry 2 --retry-delay 2 \
  --retry-max-time 360 --connect-timeout 15 --max-time 240 \
  "$FFMPEG_ARCHIVE_URL" --output "$archive"
printf '%s  %s\n' "$FFMPEG_ARCHIVE_SHA256" "$archive" | sha256sum --check -
tar -xJf "$archive" -C "$extract_dir" --no-same-owner

ffmpeg_bin="$(find "$extract_dir" -type f -path '*/bin/ffmpeg' -print -quit)"
ffprobe_bin="$(find "$extract_dir" -type f -path '*/bin/ffprobe' -print -quit)"
test -n "$ffmpeg_bin" && test -n "$ffprobe_bin"

install -m 0755 "$ffmpeg_bin" "$bin_dir/ffmpeg"
install -m 0755 "$ffprobe_bin" "$bin_dir/ffprobe"
printf '%s\n' "$bin_dir" >> "$GITHUB_PATH"
"$bin_dir/ffmpeg" -version
"$bin_dir/ffprobe" -version
