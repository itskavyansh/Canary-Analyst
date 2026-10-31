import hashlib
import json
from pathlib import Path
import pytest

from engine.baseline_b2 import B2_CONFIG


def test_b2_frozen_config_integrity():
    """Verify that the live B2_CONFIG exactly matches engine/b2_frozen.json and its SHA-256 hash."""
    frozen_file = Path("engine/b2_frozen.json")
    assert frozen_file.exists(), "engine/b2_frozen.json is missing!"

    with open(frozen_file, "r", encoding="utf-8") as f:
        frozen_data = json.load(f)

    expected_config = frozen_data["config"]
    expected_hash = frozen_data["sha256"]

    # Verify live config matches stored config
    assert B2_CONFIG == expected_config, "Live B2_CONFIG differs from frozen configuration!"

    # Verify SHA-256 hash integrity
    serialized = json.dumps(B2_CONFIG, sort_keys=True, indent=2)
    actual_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    assert actual_hash == expected_hash, f"B2_CONFIG hash mismatch! Expected {expected_hash}, got {actual_hash}"

