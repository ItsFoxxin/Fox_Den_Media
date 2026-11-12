# Fox Den Media v1.0.0 — release notes template

> EDITORIAL TEMPLATE ONLY. Replace all placeholder markers with verified source, immutable artifacts and approved release evidence. Do not release this template unchanged.

## Release summary

{{SUMMARY_OF_VERIFIED_1_0_SCOPE}}

Approved main commit: {{FULL_MAIN_SOURCE_SHA}}
Release lock SHA-256: {{64_CHARACTER_RELEASE_LOCK_SHA256}}

## Major features

{{FEATURES_FROM_APPROVED_CHANGELOG_AND_REVIEW}}

## Bug fixes

{{FIXES_AND_TRACKING_ISSUES_FROM_APPROVED_CHANGELOG}}

## Security changes

{{TRIVY_POLICY_VERSION_SECURITY_REMEDIATIONS_AND_ACCEPTED_RISK_SUMMARY}}

## Compatibility

{{SUPPORTED_LINUX_AMD64_NAS_DOCKER_VERSIONS_DEPLOYMENT_MODES_AND_CLIENT_REQUIREMENTS}}

## Installation and upgrade

{{INSTALL_AND_UPGRADE_LINKS_USING_VERIFIED_IMAGE_DIGESTS_NOT_MUTABLE_TAGS}}

## Images and immutable digests

| Runtime | Verified image digest | Architecture |
| --- | --- | --- |
| Portal | {{GHCR_PORTAL_NAME_AT_DIGEST}} | linux/amd64 |
| Music web and worker (same digest) | {{GHCR_MUSIC_NAME_AT_DIGEST}} | linux/amd64 |
| Movies/TV | {{GHCR_MEDIA_NAME_AT_DIGEST}} | linux/amd64 |

{{PINNED_UPSTREAM_IMAGE_MANIFESTS_AND_PROFILES}}

## SBOM

{{VERIFIED_SPDX_SBOM_ATTESTATION_AND_ASSET_REFERENCES}}

## Build provenance

{{SLSA_WORKFLOW_MAIN_COMMIT_AND_GH_ATTESTATION_VERIFICATION_LINKS}}

## Checksums

{{RELEASE_LOCK_SHA256_AND_ASSETS_SHA256_REFERENCES}}

## Known limitations

{{OPEN_NONBLOCKING_LIMITATIONS_AND_APPROVED_RISK_EXCEPTIONS_NO_PRIVATE_DETAILS}}

## Rollback

{{SAFE_COMPATIBLE_PRIOR_LOCK_AND_BACKUP_RESTORE_MANUAL_ROLLBACK_LINKS}}

Publication is not production deployment. A separate NAS owner approval, verified backup/restore and maintenance window are mandatory.

## Documentation

- [Release acceptance checklist](release-1.0-checklist.md)
- [R5 release-publishing guide](release-publication-r5.md)
- [R6 independent production boundary](production-publication-boundary.md)
- [Deployment](deployment.md)
- [Recovery](recovery.md)
- [Security](security.md)
