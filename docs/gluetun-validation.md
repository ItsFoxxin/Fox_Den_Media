# Gluetun health and fail-closed validation

## NAS baseline and health-check correction (November 5, 2026)

The existing NAS `torrent-vpn` container was pinned to `qmcgaw/gluetun:v3.41.1`.
DNS and HTTPS requests worked from its network namespace, and its public egress
IP was distinct from the host IP. The separate real-VPN Test 57 reported
IPv4/IPv6 default-DROP firewall rules and direct-egress leak prevention.
Nevertheless, Docker health was `unhealthy`: every small periodic ICMP probe
timed out against `1.1.1.1` and `8.8.8.8`.

The operator added `HEALTH_SMALL_CHECK_TYPE=dns` to the existing NAS Compose
environment, validated Compose and container dependencies, and recreated only
`torrent-vpn` using the same v3.41.1 image. Startup logs confirmed `Plain DNS
lookup over UDP`, automatic VPN recovery enabled, the expected VPN egress IP,
and Docker `healthy`. A later check remained `healthy`, and HTTPS returned the
same VPN public IP. Firewall settings and the pinned image were not relaxed.

Proton allocated a forwarded port, but the qBittorrent API synchronization
hook logged `Connection refused`; no active qBittorrent container was found
in the NAS inventory. This is **not** evidence of a working qBittorrent
integration. Do not start the old torrent client or contact peers to clear
these messages without separately approved recovery tests.

Gluetun's official v3.41.0 release notes introduced
`HEALTH_SMALL_CHECK_TYPE=dns|icmp`. The option **does work on v3.41.1**;
earlier Fox Den documentation and validator rejection were incorrect. Managed
Compose defaults to DNS with `GLUETUN_HEALTH_SMALL_CHECK_TYPE=dns`; the
supported overrides are `dns` and `icmp`. Auto-recovery remains on.

References:

- https://github.com/passteque/gluetun/releases/tag/v3.41.0
- https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/healthcheck.md
- https://github.com/qdm12/gluetun-wiki/blob/main/faq/healthcheck.md

## Distinct managed-mode rehearsal (not yet passed)

The prior `foxden-managed56-gluetun-1` rehearsal used endpoint
`198.51.100.254`, a reserved TEST-NET-2 documentation address. That
configuration cannot establish a real Internet VPN tunnel. It also showed
startup DNS timeouts, a shutdown-time temporary-file permission failure, and
a Go shutdown panic. Those failures cannot be reclassified as a successful
real managed-mode VPN or qBittorrent test.

The NAS Compose experiment was conducted in the **existing** `torrent-vpn`
stack, not in the 0.9.1 managed-mode candidate. The release candidate still
requires valid separately supplied WireGuard credentials and a real endpoint
in an isolated test, plus an approved production image digest. Never expose
a WireGuard private key in rendered Compose, logs, or evidence artifacts.

## Managed-mode acceptance sequence

1. Check pinned image and digest, read-only secret file, network namespace,
   firewall enabled, and `HEALTH_RESTART_VPN=on`.
2. Start Gluetun alone with an authorized real endpoint in isolated staging.
   Verify `tun0`, DNS, HTTPS/TCP+TLS, the VPN IP versus host IP, and periodic
   small and full health checks.
3. Start a synthetic fixture with `network_mode: service:gluetun` and prove
   it has no independent network namespace or published ports.
4. Verify IPv4 and IPv6 default-deny and direct `eth0` egress blocking.
5. Intentionally invalidate only the **rehearsal** tunnel and prove fixture
   LAN, DNS, HTTPS, tracker and peer egress all fail closed. Never interrupt
   the existing production `torrent-vpn` to run this test.
6. Verify qBittorrent stays unavailable while Gluetun is unhealthy, then
   starts only after Gluetun becomes healthy; verify the Web API and
   port-forward synchronization using copied/disposable state without
   contacting live torrent peers unless separately approved.
7. Restore the rehearsal tunnel, verify recovery and leak protection, and
   record time-stamped redacted evidence including container/image digests.

Do not delete the Docker health check, turn off the firewall, disable VPN
auto-recovery, or give qBittorrent any independent outbound network.
These observations support the health configuration change, **not** a merge,
production cutover, or `1.0.0` tag. Follow the release checklist and obtain
separate operator approval.
