"""Sandbox test runner.

Runs the detected test command inside the repo workspace with a timeout and
parses the output into a structured report (passed, totals, failures) so the
self-healing loop can reason about failures.

Two execution backends:
  * ``subprocess`` (default) — fast, reliable, isolated to the workspace dir.
  * ``docker`` — set DEVPILOT_SANDBOX=docker to run tests in a throwaway
    python:3.12-slim container (stronger isolation; requires Docker).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.sandbox.detectors import detect_project

_PYTEST_SUMMARY = re.compile(
    r"(?:(\d+) failed)?(?:,\s*)?(?:(\d+) passed)?(?:,\s*)?(?:(\d+) error)?", re.IGNORECASE
)


@dataclass
class TestResult:
    command: str
    passed: bool
    total_tests: int
    failed_tests: int
    logs: str


def _parse_pytest(output: str) -> tuple[int, int]:
    """Return (total, failed). Robust to the various pytest summary formats."""
    failed = passed = errors = 0
    for line in output.strip().splitlines()[::-1]:
        if "passed" in line or "failed" in line or "error" in line:
            m = _PYTEST_SUMMARY.search(line)
            if m:
                failed = int(m.group(1) or 0)
                passed = int(m.group(2) or 0)
                errors = int(m.group(3) or 0)
                if failed or passed or errors:
                    break
    return passed + failed + errors, failed + errors


def _run_subprocess(workspace: Path, command: list[str]) -> tuple[str, int]:
    cmd = list(command)
    if cmd[:2] == ["python", "-m"]:
        cmd[0] = sys.executable  # use the active interpreter
    try:
        proc = subprocess.run(
            cmd, cwd=workspace, capture_output=True, text=True,
            timeout=settings.sandbox_timeout_seconds,
        )
        return (proc.stdout + "\n" + proc.stderr), proc.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT: test run exceeded limit", 124
    except FileNotFoundError as exc:
        return f"RUNNER ERROR: {exc}", 127


def _run_docker(workspace: Path, command: list[str]) -> tuple[str, int]:  # pragma: no cover
    docker_cmd = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{workspace}:/work", "-w", "/work", "python:3.12-slim",
        "sh", "-c", "pip install -q pytest fastapi httpx >/dev/null 2>&1; " + " ".join(command),
    ]
    proc = subprocess.run(docker_cmd, capture_output=True, text=True,
                          timeout=settings.sandbox_timeout_seconds + 120)
    return (proc.stdout + "\n" + proc.stderr), proc.returncode


def run_tests(workspace: Path) -> TestResult:
    project = detect_project(workspace)
    command = project["command"]
    backend = os.environ.get("DEVPILOT_SANDBOX", "subprocess")

    if backend == "docker":
        logs, code = _run_docker(workspace, command)
    else:
        logs, code = _run_subprocess(workspace, command)

    if project["type"] == "python":
        total, failed = _parse_pytest(logs)
    else:
        # Generic: rely on exit code for non-python toolchains.
        total, failed = (1, 0 if code == 0 else 1)

    passed = code == 0 and failed == 0
    return TestResult(
        command=" ".join(command),
        passed=passed,
        total_tests=total,
        failed_tests=failed,
        logs=logs[-6000:],
    )
