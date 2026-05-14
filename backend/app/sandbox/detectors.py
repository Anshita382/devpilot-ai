"""Detect project type and the appropriate test command."""
from __future__ import annotations

from pathlib import Path


def detect_project(workspace: Path) -> dict:
    if (workspace / "go.mod").exists():
        return {"type": "go", "command": ["go", "test", "./..."]}
    if (workspace / "pom.xml").exists():
        return {"type": "maven", "command": ["mvn", "-q", "test"]}
    if (workspace / "package.json").exists():
        return {"type": "node", "command": ["npm", "test", "--silent"]}
    # Python is the default / fallback.
    return {"type": "python", "command": ["python", "-m", "pytest", "-q"]}
