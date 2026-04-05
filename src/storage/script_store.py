"""
Script Store: versioned YAML script management.
"""

import os
import yaml
from datetime import datetime

SCRIPTS_DIR = "scripts"


def load_script(version: int) -> dict:
    path = os.path.join(SCRIPTS_DIR, f"v{version}.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_script(script: dict) -> str:
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    version = script.get("version", 1)
    if script.get("created_at") in (None, "auto"):
        script["created_at"] = datetime.now().isoformat()

    path = os.path.join(SCRIPTS_DIR, f"v{version}.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(script, f, default_flow_style=False,
                  allow_unicode=True, sort_keys=False, width=120)
    return path


def get_latest_version() -> int:
    if not os.path.exists(SCRIPTS_DIR):
        return 0
    versions = []
    for fname in os.listdir(SCRIPTS_DIR):
        if fname.startswith("v") and fname.endswith(".yaml"):
            try:
                versions.append(int(fname[1:-5]))
            except ValueError:
                pass
    return max(versions) if versions else 0


def load_latest_script() -> dict:
    version = get_latest_version()
    if version == 0:
        raise FileNotFoundError("No scripts found in scripts/ directory")
    return load_script(version)


def validate_script(script: dict) -> bool:
    """Check that a script has the required structure."""
    if "version" not in script or "script" not in script:
        return False
    s = script["script"]
    required = ["opening", "value_propositions", "objection_handlers", "closing", "guidelines"]
    return all(k in s for k in required)