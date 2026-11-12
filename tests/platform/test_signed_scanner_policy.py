"""R4 signed raw scanner and owner-reviewed exception policy synthetic fixtures."""
from datetime import datetime, timezone
import hashlib
import json
import copy
import pytest
from scripts.verify_image_security import SecurityContractError, validate_scanner_policy

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
LEDGER = {"schema_version": 1, "exceptions": []}
POLICY_HASH = hashlib.sha256(json.dumps(
    LEDGER, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def sample():
    scanner = {"Version": "0.76.2", "VulnerabilityDB": {
        "Version": 2, "UpdatedAt": "2026-11-08T11:00:00Z"}}
    contract = {
        "scanner": {"name": "trivy", "version": "0.76.2",
                    "db_updated_at": "2026-11-08T11:00:00Z"},
        "policy_version": "v1:" + POLICY_HASH,
    }
    return contract, scanner, copy.deepcopy(LEDGER)

def test_matching_signed_scanner_and_policy():
    contract, scanner, ledger = sample()
    validate_scanner_policy(contract, scanner, ledger, now=NOW)

@pytest.mark.parametrize("mutation", [
    "missing-db", "bad-db-version", "mismatched-timestamp", "future-date",
    "stale-db", "wrong-tool-version", "wrong-policy-hash",
    "unapproved-exception", "extra-ledger-field", "missing-scanner",
    "naive-date", "invalid-date",
])
def test_mismatched_signed_security_metadata_rejected(mutation):
    contract, scanner, ledger = sample()
    if mutation == "missing-db": scanner.pop("VulnerabilityDB")
    elif mutation == "bad-db-version": scanner["VulnerabilityDB"]["Version"] = "2"
    elif mutation == "mismatched-timestamp":
        contract["scanner"]["db_updated_at"] = "2026-11-07T11:00:00Z"
    elif mutation == "future-date":
        scanner["VulnerabilityDB"]["UpdatedAt"] = contract["scanner"]["db_updated_at"] = "2026-11-09T11:00:00Z"
    elif mutation == "stale-db":
        scanner["VulnerabilityDB"]["UpdatedAt"] = contract["scanner"]["db_updated_at"] = "2026-10-01T11:00:00Z"
    elif mutation == "wrong-tool-version": scanner["Version"] = "0.77.0"
    elif mutation == "wrong-policy-hash": contract["policy_version"] = "v1:" + "f" * 64
    elif mutation == "unapproved-exception": ledger["exceptions"] = [{"id": "CVE-TEST"}]
    elif mutation == "extra-ledger-field": ledger["extra"] = "x"
    elif mutation == "missing-scanner": contract.pop("scanner")
    elif mutation == "naive-date":
        scanner["VulnerabilityDB"]["UpdatedAt"] = contract["scanner"]["db_updated_at"] = "2026-11-08T11:00:00"
    elif mutation == "invalid-date":
        scanner["VulnerabilityDB"]["UpdatedAt"] = contract["scanner"]["db_updated_at"] = "not-a-date"
    with pytest.raises(SecurityContractError):
        validate_scanner_policy(contract, scanner, ledger, now=NOW)
