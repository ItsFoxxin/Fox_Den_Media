# Gluetun health and fail-closed validation

The November 3, 2026 inventory proves `tun0` routing, DNS, HTTPS status 200 and a
VPN egress IP distinct from the NAS host. It does not prove the kill switch.

The first rehearsal pins production `qmcgaw/gluetun:v3.41.1` and its recorded
digest. `HEALTH_SMALL_CHECK_TYPE=dns` is rejected for this baseline because that
setting belongs to newer health-check behavior and has not been verified for
v3.41.1. The reviewed variables are `HEALTH_TARGET_ADDRESSES`,
`HEALTH_ICMP_TARGET_IPS`, and `HEALTH_RESTART_VPN`; auto-recovery stays enabled.

Validation sequence using synthetic traffic only:

1. Confirm the secret file is read-only and no key appears in rendered Compose or logs.
2. Start Gluetun alone and verify route, DNS, HTTPS, and external IP through its namespace.
3. Start a fixture client with `network_mode: service:gluetun`; verify it has no independent network or ports.
4. Start qBittorrent only after the Gluetun Docker health gate succeeds.
5. Remove or invalidate the rehearsal tunnel and prove the fixture cannot reach LAN, DNS, HTTPS, trackers, or peers.
6. Prove qBittorrent remains unavailable while Gluetun is unhealthy or restarting.
7. Restore the tunnel and verify controlled recovery without bypass traffic.

Do not make Docker green by deleting the health check or disabling the firewall.
If ICMP alone remains the failing path, capture the exact v3.41.1 logs and test a
version-pinned alternative in isolation. An image upgrade is a separate gate.

References:

- https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/healthcheck.md
- https://github.com/qdm12/gluetun-wiki/blob/main/faq/healthcheck.md
