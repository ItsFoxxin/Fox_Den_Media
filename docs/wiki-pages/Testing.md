# Testing

> **Status:** Development documentation; 1.0.0 is not approved or published. No Wiki procedure authorizes production changes.

Fox Den Media uses layered evidence; not all tests establish the same guarantees.

| Layer | What it checks |
| --- | --- |
| Static/metadata | Python, JavaScript, release metadata and Compose profile render |
| Unit/integration | Portal, Music, Movies/TV, migration and signed identity behaviors |
| Security | CodeQL, Bandit, dependency audits and secret-history scan |
| Container smoke | Disposable runtime health, optional Jellyfin, synthetic VPN fixture |
| NAS acceptance | Real ownership/ACLs, authentication, Firefox/noVNC, VPN kill switch, media clients, backup/restore |

CI's **Monorepo strict gate** aggregates prerequisite jobs. CodeQL has separate checks. A green CI build is **not** approval for production NAS access or a release.

## Selected local commands

~~~bash
python -m compileall -q apps scripts tests
python scripts/check_release.py
python -m pytest tests/platform tests/test_integration_compose.py tests/test_ingress_config.py -q
~~~

Install documented test dependencies first. A safe Compose configuration check uses `docker compose ... config --quiet`; it does not prove live networking, secrets, ACLs or VPN tunnel-loss behavior.

Sources: [CI and local tests](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/ci.md), [historical test evidence](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/validation.md), [NAS acceptance plan](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/nas-current-dev-acceptance.md) and [1.0.0 acceptance gates](https://github.com/ItsFoxxin/Fox_Den_Media/blob/dev/docs/release-1.0-checklist.md).