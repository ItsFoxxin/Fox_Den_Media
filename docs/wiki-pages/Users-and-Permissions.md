# Users and Permissions

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den deliberately separates **Portal access** from **Jellyfin access** and separates media acquisition from viewing.

| Action | Portal general user | Portal administrator |
| --- | --- | --- |
| General Portal / linked Watch & Listen | Available subject to own Jellyfin access | Available subject to own Jellyfin access |
| Module health and acquisition controls | Not permitted | Permitted |
| Music / Movies & TV administration | Not permitted | Permitted |
| Contained Firefox server browser | Not permitted | Permitted |
| Jellyfin server administration | No automatic right | No automatic right |

Jellyfin enforces its own library visibility and native-client roles. An administrator in one service is not automatically administrator in the other.

## Storage permissions are separate

Application container UIDs/GIDs must be able to read private secrets and write only their assigned mutable directories. A successful host-user access check does not guarantee container access. Test effective UID/GID, ACLs and deliberate read-only mounts.

Read [full permission matrix](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/permissions.md), [security policy](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/security.md), [numeric ownership](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/configuration.md) and [ownership review](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/secret-ownership-1.0.md).