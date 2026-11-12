# qBittorrent and Gluetun

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

The `full-managed` mode adds **qBittorrent isolated inside Gluetun's VPN network namespace**. Other modes can use an external, separately configured qBittorrent instance.

## Required isolation

- qBittorrent uses `network_mode: service:gluetun`, with no independent network route.
- Gluetun manages WireGuard, its firewall, `NET_ADMIN` and `/dev/net/tun`.
- The managed qBittorrent Web UI is restricted to the configured bind; never publish it directly to the Internet.
- WireGuard *private* key and qBittorrent password are private mounted files.

A healthy Gluetun process **does not prove** that the VPN kill switch blocks traffic when the tunnel is lost. Test DNS/HTTPS VPN egress, real tunnel-loss fail-closed behavior, qBittorrent state/resume continuity and actual credentials on **isolated staging** before use.

Never disable the VPN firewall or route qBittorrent independently just to make health checks pass.

Read [VPN safety contract](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/torrent-vpn.md), [staging validation](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/gluetun-validation.md), [qBittorrent recovery](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/qbittorrent-recovery.md), and [security overview](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md).