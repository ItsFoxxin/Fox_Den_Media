# Intel N100 Jellyfin hardware-transcoding validation

Hardware acceleration is optional and disabled unless the reviewed
`deploy/compose.jellyfin-hwaccel.yaml` override is selected.

## Read-only discovery

```bash
python scripts/migration.py hardware-inventory --output private-reports/n100-hardware.json
ls -l /dev/dri
getent group video
getent group render
```

Record the numeric groups owning `card*` and `renderD*`; names vary by host.
Configure `JELLYFIN_DRI_DEVICE`, `JELLYFIN_VIDEO_GID`, and
`JELLYFIN_RENDER_GID` only after this review. Device presence or successful
container startup is not proof of transcoding.

## Isolated validation

1. Use a disposable Jellyfin config/cache and a short synthetic source clip.
2. Start only the rehearsal Jellyfin profile with the hardware override.
3. Confirm the device is visible inside the container without privileged mode.
4. Run a forced codec/resolution conversion that cannot direct-play.
5. Observe Jellyfin/FFmpeg logs for the selected QSV or VA-API decoder/encoder.
6. Observe host GPU media-engine activity and compare CPU use with a software
   transcode.
7. Seek and play long enough to detect initialization or permission failures.
8. Save the command, image digest, source checksum, output checksum, logs and
   observed engine/CPU evidence as an isolated-staging artifact.

Do not mount the production Jellyfin config into this test. Do not mark the
hardware gate passed from `vainfo`, `ffmpeg -hwaccels`, direct play, or container
health alone.
