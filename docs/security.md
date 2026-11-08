# Security model and operator checklist

This guide describes protections visible in the **0.9.1 code/configuration**; it is **not** a penetration-test certificate or approval to deploy production. Read the detailed [0.9.1 review](security-0.9.1.md), [permissions](permissions.md), [VPN validation](gluetun-validation.md) and [readiness](production-readiness.md). Source of truth: [Compose](../deploy/compose.yaml), [ingress config](../infra/gateway/portal-ingress.conf) and application tests.

## Implemented boundaries (source and CI validated)

| Area | Implemented control | Operational caveat |
| --- | --- | --- |
| Portal | Local accounts; optional OIDC/hybrid with issuer/nonce/state/signature checks; scoped administrator routes | Real Authentik setup and recovery need NAS testing |
| Internal service identity | Portal-only Ed25519 signing key; audience/issuer/key-ID/time/roles/scopes/replay checks in module consumers | Secure file ownership and key rotation must be planned |
| Proxy | Protected `auth_request`, client identity-header stripping, private backend ports | External TLS/Caddy, DNS and host firewall are operator responsibilities |
| First-party containers | Numeric non-root users, read-only root FS, all capabilities dropped, `no-new-privileges`, bounded tmpfs/resource limits | Bind mount ACLs and effective UID/GID must be verified on host |
| Movies/TV imports | Staging containment, no-follow descriptor-based Linux handling, reviewed source hashes, no-overwrite publishing | Trust administrators controlling host path parents and local filesystem semantics |
| Music private files and published library | Staging/work files are owner-only; published media is group-readable for Jellyfin | Validate actual NAS shared group, ACLs and mount options before accepting CodeQL alert #13 |
| Managed torrent | qBittorrent `network_mode: service:gluetun`; Gluetun firewall enabled; healthy tunnel required before qBittorrent starts | Synthetic fail-closed test is **not** a real tunnel interruption test |
| Passwords and keys | Restricted secret files, no Docker socket, public-only identity keys mounted to modules | Init makes empty provider-secret placeholders; backups and permissions remain essential |
| CI supply chain | Pinned GitHub Actions commits, pip-audit, Bandit, secret-history scan, CodeQL Python/JS | Some third-party container defaults use tags, not frozen digests |
| Recovery | Checksummed state archives, empty-target restore, rollback fixture | Large data is excluded and needs separate backup/snapshot |

The third-party Firefox and LinuxServer qBittorrent images have different init/process requirements and **do not** inherit the full first-party `x-hardening` profile. Do not claim every container runs as an unprivileged immutable filesystem. Gluetun requires `NET_ADMIN` and `/dev/net/tun` for VPN setup.

## Authentication and authorization

Keep `FOXDEN_PUBLIC_ORIGIN`, TLS termination, `PORTAL_COOKIE_SECURE=true`, OIDC issuer/client/redirect and group mapping consistent. Only Portal administrators should access Music and Movies/TV acquisition or the contained browser. A Jellyfin account does **not** imply Fox Den admin access, and a Portal administrator does **not** inherit Jellyfin admin access. Jellyfin's dedicated hostname must preserve native-client login; avoid inserting browser-only Authentik forward auth in front of TVs and apps.

The Music-worker `jellyfin-api-key` refresh integration and the user-scoped Watch & Listen Jellyfin tokens are independent. Portal encrypts user links with `portal-secret`; preserve it in backups and rotate deliberately. Test emergency local administrator recovery before requiring OIDC.

## Secrets and networking

- Put only non-secret settings in untracked `.env`. Use file-mounted secrets under `FOXDEN_SECRETS_DIR`; mode `0600` for private files, appropriate owner/group traversal, and encrypted backups. Do not paste expanded Compose config, Docker container environments, private IPs, passwords or real VPN keys into public issues.
- Restrict external routing to a reviewed HTTPS proxy; retain loopback host port bindings. Do not expose `:8020`, `:8000`, `:8010`, `:5800`, qBittorrent or Docker API externally.
- Keep the `platform` network internal. The `outbound` network is deliberately available to selected application services; this is **not** a guarantee of total container egress isolation.
- Managed qBittorrent **must** share only Gluetun's namespace. Do not add a parallel network, change to host mode, remove its Gluetun health dependency, disable Gluetun firewall, or bypass the VPN for downloads.
- Validate both success (DNS/HTTPS through expected VPN IP) **and** failure (blocked egress on controlled tunnel loss) in isolated staging before any real torrent operations. An `unhealthy` container or an `ICMP` issue is not grounds to disable health checks.

## Backups and safe change control

Before updates, stop or quiesce writers, verify the state archive and separate library/torrent backups, record commit/image digests, and test restoration to empty targets. Do not share mutable production databases between candidate and old containers. Preserve the former deployment and Git repo through approved rollback. Follow [rehearsal](production-migration-rehearsal.md), [side-by-side migration](side-by-side-migration.md), and [recovery](recovery.md).

## Still unverified or planned

- Actual NAS firewall/VLAN rules, file ACLs and effective process IDs.
- Verify CodeQL Music published-file alert #13 against the intentional `0640` group-read policy and actual NAS ownership. See [file-permission review](security/media-file-permissions.md).
- Real Gluetun managed-mode WireGuard connection, port-forward coordination, kill switch and qBittorrent resume/seeding continuity.
- Production Authentik/OIDC and local emergency recovery; Jellyfin clients/plugins/schema/playback and optional hardware transcoding.
- Frozen/approved digests for every production image and independent restore evidence.
- Bound **total** WebSocket lifetime for an active contained-browser session after Portal revocation (existing Nginx inactivity timeouts do not guarantee a maximum lifetime).

These are operator gates, not claims that features already work in production. Refer to the [release checklist](release-1.0-checklist.md).

## Image vulnerability evidence

For advisory Trivy scans of current first-party Docker-built images, per-image CycloneDX SBOMs, and time-limited finding reviews, see [Trivy image scanning](trivy.md). Image scanning does not replace the operational NAS/VPN security acceptance checks above.
