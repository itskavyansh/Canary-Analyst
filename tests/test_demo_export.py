import json
from pathlib import Path
import pytest

DEMO_DIR = Path("web/public/demo")


def test_exported_demo_files_exist():
    """Verify that demo/index.json, demo/summary.json and the 4 scenarios exist."""
    assert (DEMO_DIR / "index.json").exists(), "demo/index.json missing!"
    assert (DEMO_DIR / "summary.json").exists(), "demo/summary.json missing!"

    with open(DEMO_DIR / "index.json", "r", encoding="utf-8") as f:
        index_data = json.load(f)

    scenarios = index_data.get("scenarios", [])
    assert len(scenarios) == 4, f"Expected 4 exported scenarios, got {len(scenarios)}"

    for scen in scenarios:
        scen_file = DEMO_DIR / scen["file"]
        assert scen_file.exists(), f"Scenario JSON file missing: {scen['file']}"


def test_no_api_key_or_secret_leakage_in_demo_files():
    """Verify that no API keys, secrets, or .env values leak into exported demo JSONs."""
    forbidden_terms = ["META_API_KEY", "api_key", "bearer", "AIzaSy", "sk-"]

    for file_path in DEMO_DIR.glob("*.json"):
        text = file_path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in text, f"Potential sensitive token '{term}' found in {file_path.name}!"


def test_ground_truth_strictly_quarantined_in_reveal():
    """Verify that ground truth fields (is_hazard, collapse_time, onset_time, events) only exist under 'reveal'."""
    ground_truth_fields = ["is_hazard", "collapse_time", "onset_time", "events"]

    with open(DEMO_DIR / "index.json", "r", encoding="utf-8") as f:
        scenarios = json.load(f)["scenarios"]

    for scen in scenarios:
        with open(DEMO_DIR / scen["file"], "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "reveal" in data, f"Quarantined 'reveal' field missing in {scen['file']}"

        # Top-level keys must not include ground truth fields
        for field in ground_truth_fields:
            assert field not in data, f"Ground truth field '{field}' leaked at top level of {scen['file']}!"

        # Reveal field must contain them
        reveal = data["reveal"]
        assert "is_hazard" in reveal
        assert "scenario_type" in reveal
