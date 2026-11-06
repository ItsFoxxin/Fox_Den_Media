# Music file-permission review (CodeQL alerts #11–15)

## Security boundary

This review separates private acquisition/staging files from published media.
The Music web and worker services use the same configured `MUSIC_PUID:MUSIC_PGID`.
Temporary inputs and working files should be owner-only (0600 files, 0700
leaf directories). The published music library intentionally supports a
dedicated read-only media group for Jellyfin (0640 files, 0750 directories).

| Alert | Location | Disposition |
| --- | --- | --- |
| #11 | `intake.py`, staged inbox file | Tightened to 0600 inside a 0700 incoming directory |
| #12 | `intake.py`, staged web upload | Retains 0600 after rename; incoming directory is now 0700 |
| #13 | `library.py`, published library files | Intentional 0640 group-read policy; **do not dismiss until the actual host group, ACL, and mount options are verified** |
| #14 | `pipeline.py`, working cover art | Tightened to 0600 inside a 0700 working directory |
| #15 | `pipeline.py`, working audio | Tightened to 0600 inside a 0700 working directory |

## Why alert #13 is different

`_chmod_regular_file_if_supported` is called with mode 0640 when publishing
audio, artwork, and import metadata. Published media must be readable by a
separately configured Jellyfin identity. Switching to 0600 indiscriminately
would prevent a distinct Jellyfin UID from reading music even if it shares
the intended media group. Access for group members is an explicit policy,
not a blanket exception for all groups.

Before accepting this exception, verify on the actual NAS:

1. The Music UID/GID and Jellyfin UID/GID, and membership of their dedicated
   media group. Do not put unrelated users or services into that group.
2. The effective permissions and ACLs of the music root and published files.
3. The filesystem type and mount options; POSIX `chmod` may be unsupported
   or ineffective on external NTFS/SMB-style mounts.
4. Jellyfin reads the media mount read-only and cannot write into acquisition
   staging directories.
5. A Jellyfin read works with distinct service UIDs in the intended shared
   group; an unrelated group member cannot access the library.

Read-only host diagnostic examples (replace paths with actual mounted paths):

```sh
stat -c '%a %u:%g %n' /path/to/music /path/to/staging
findmnt -T /path/to/music -o SOURCE,FSTYPE,OPTIONS
getfacl -p /path/to/music
```

Record the observed permissions and group members before dismissing alert
#13 as an intentional accepted access policy (for example, `won't fix`).
Do not disable the CodeQL rule or suppress findings without that evidence.

## Remaining limits

`FILE_UMASK` defaults to 0027 in Compose and is applied by the non-root
service wrapper. Operators should not relax it to values that create files
readable by everyone. A separate configuration-hardening review should
consider rejecting unsafe overrides. Working-directory privacy ensures
temporary content is inaccessible to the shared media group, even while
external tools create or modify an output file.
