# Permissions and application boundaries

| Capability | General Portal user | Portal administrator | Jellyfin user | Jellyfin administrator |
|---|---:|---:|---:|---:|
| Portal media-server link | yes | yes | n/a | n/a |
| Watch & Listen browsing/search | after own Jellyfin link | after own Jellyfin link | assigned libraries only | assigned libraries only |
| Portal module health/activity | no | yes | n/a | n/a |
| Music acquisition interface | no | yes | no | no |
| Movies/TV acquisition interface | no | yes | no | no |
| Contained server browser | no | yes | no | no |
| qBittorrent operations exposed by Fox Den | no | authorized admin only | no | no |
| Jellyfin library playback | Jellyfin handoff | Jellyfin handoff | assigned libraries | assigned libraries |
| Jellyfin account preferences | no | no | own account | own account |
| Jellyfin server administration | no | no automatic grant | no | yes |
| Gluetun/infrastructure management | no | not exposed by Portal | no | no |

Nginx now requests an administrator-qualified Portal session before forwarding
Music, Movies/TV, or `/server-browser/`. The Portal independently hides module
status/activity from general users, and the status API requires an administrator.
Module backends continue validating signed, audience-bound Fox Den identities;
UI visibility is never the authorization control.

Jellyfin remains a separate security domain. Portal roles are not translated into
Jellyfin administrator privileges. Native or LDAP-backed Jellyfin accounts receive
libraries and playback permissions inside Jellyfin.
Watch & Listen queries with the linked user's token and does not turn a general
Portal account into a Music or Movies/TV acquisition administrator.
