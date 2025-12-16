#!/usr/bin/env python3
"""Test execution and result parsing utilities.

Supports multiple project types and parses test results
to help with feature status automation.
"""

import os
import subprocess
import re
from typing import Dict, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class TestResult(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    NOT_RUN = "not_run"


@dataclass
class TestSummary:
    """Summary of test execution results."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    raw_output: str = ""
    result: TestResult = TestResult.NOT_RUN
    failed_tests: List[str] = field(default_factory=list)


def detect_project_type(work_dir: str) -> Optional[str]:
    """Detect project type from config files."""
    path = Path(work_dir)

    # Check in order of specificity
    if (path / "package.json").exists():
        return "node"
    elif (path / "Cargo.toml").exists():
        return "rust"
    elif (path / "go.mod").exists():
        return "go"
    elif (path / "pyproject.toml").exists() or (path / "setup.py").exists() or (path / "pytest.ini").exists():
        return "python"
    elif (path / "pom.xml").exists():
        return "java-maven"
    elif (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
        return "java-gradle"

    # Check for Python files as fallback
    if list(path.glob("*.py")) or list(path.glob("tests/*.py")):
        return "python"

    return None


def get_test_command(work_dir: str, config: Dict = None) -> Optional[str]:
    """Get the appropriate test command for the project."""
    project_type = detect_project_type(work_dir)

    # Use config override if available
    if config and 'test_commands' in config:
        if project_type in config['test_commands']:
            return config['test_commands'][project_type]

    # Defaults with error handling
    commands = {
        "node": "npm test -- --passWithNoTests 2>&1 || true",
        "python": "python -m pytest -v 2>&1 || true",
        "rust": "cargo test 2>&1 || true",
        "go": "go test ./... 2>&1 || true",
        "java-maven": "mvn test 2>&1 || true",
        "java-gradle": "./gradlew test 2>&1 || true"
    }

    return commands.get(project_type)


def run_tests(work_dir: str, timeout: int = 300, config: Dict = None) -> TestSummary:
    """Run tests and return summary."""
    command = get_test_command(work_dir, config)

    if not command:
        return TestSummary(
            result=TestResult.NOT_RUN,
            raw_output="No test command found for this project type"
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = result.stdout + result.stderr
        project_type = detect_project_type(work_dir)
        summary = parse_test_output(output, project_type)
        summary.raw_output = output

        # Determine overall result
        if summary.failed > 0 or summary.errors > 0:
            summary.result = TestResult.FAILED
        elif summary.passed > 0:
            summary.result = TestResult.PASSED
        elif result.returncode != 0:
            summary.result = TestResult.ERROR
        else:
            summary.result = TestResult.PASSED

        return summary

    except subprocess.TimeoutExpired:
        return TestSummary(
            result=TestResult.ERROR,
            raw_output=f"Test execution timed out after {timeout} seconds"
        )
    except Exception as e:
        return TestSummary(
            result=TestResult.ERROR,
            raw_output=f"Test execution error: {str(e)}"
        )


def parse_test_output(output: str, project_type: str) -> TestSummary:
    """Parse test output to extract summary statistics."""
    summary = TestSummary()

    if project_type == "python":
        # pytest format: "5 passed, 2 failed, 1 skipped in 1.23s"
        match = re.search(r'(\d+)\s+passed', output)
        if match:
            summary.passed = int(match.group(1))
        match = re.search(r'(\d+)\s+failed', output)
        if match:
            summary.failed = int(match.group(1))
        match = re.search(r'(\d+)\s+skipped', output)
        if match:
            summary.skipped = int(match.group(1))
        match = re.search(r'(\d+)\s+error', output)
        if match:
            summary.errors = int(match.group(1))
        # Duration
        match = re.search(r'in\s+([\d.]+)s', output)
        if match:
            summary.duration = float(match.group(1))
        # Failed test names
        failed_matches = re.findall(r'FAILED\s+([\w:]+)', output)
        summary.failed_tests = failed_matches

    elif project_type == "node":
        # Jest format: "Tests: 2 failed, 5 passed, 7 total"
        match = re.search(r'Tests:\s*(\d+)\s+passed', output)
        if match:
            summary.passed = int(match.group(1))
        match = re.search(r'(\d+)\s+failed', output)
        if match:
            summary.failed = int(match.group(1))
        match = re.search(r'(\d+)\s+skipped', output)
        if match:
            summary.skipped = int(match.group(1))
        # Mocha format
        if summary.passed == 0:
            match = re.search(r'(\d+)\s+passing', output)
            if match:
                summary.passed = int(match.group(1))
            match = re.search(r'(\d+)\s+failing', output)
            if match:
                summary.failed = int(match.group(1))

    elif project_type == "rust":
        # Cargo test: "test result: ok. 5 passed; 0 failed; 0 ignored"
        match = re.search(r'(\d+)\s+passed', output)
        if match:
            summary.passed = int(match.group(1))
        match = re.search(r'(\d+)\s+failed', output)
        if match:
            summary.failed = int(match.group(1))
        match = re.search(r'(\d+)\s+ignored', output)
        if match:
            summary.skipped = int(match.group(1))

    elif project_type == "go":
        # Go test: "ok  	package	0.123s" or "FAIL"
        passed_matches = re.findall(r'^ok\s+', output, re.MULTILINE)
        summary.passed = len(passed_matches)
        failed_matches = re.findall(r'^FAIL\s+', output, re.MULTILINE)
        summary.failed = len(failed_matches)

    elif project_type in ("java-maven", "java-gradle"):
        # Maven/Gradle: "Tests run: 10, Failures: 0, Errors: 0, Skipped: 0"
        match = re.search(r'Tests run:\s*(\d+)', output)
        if match:
            summary.total = int(match.group(1))
        match = re.search(r'Failures:\s*(\d+)', output)
        if match:
            summary.failed = int(match.group(1))
        match = re.search(r'Errors:\s*(\d+)', output)
        if match:
            summary.errors = int(match.group(1))
        match = re.search(r'Skipped:\s*(\d+)', output)
        if match:
            summary.skipped = int(match.group(1))
        if summary.total > 0:
            summary.passed = summary.total - summary.failed - summary.errors - summary.skipped

    # Calculate total if not set
    if summary.total == 0:
        summary.total = summary.passed + summary.failed + summary.skipped + summary.errors

    return summary


def did_tests_run_in_session(transcript_path: str) -> bool:
    """Check if tests were run in the current session by examining transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return False

    try:
        with open(transcript_path, 'r') as f:
            content = f.read()

        # Check for test execution indicators
        test_indicators = [
            # Commands
            r'\bnpm\s+test\b',
            r'\bpytest\b',
            r'\bcargo\s+test\b',
            r'\bgo\s+test\b',
            r'\bjest\b',
            r'\bmocha\b',
            r'\bvitest\b',
            r'\bmvn\s+test\b',
            r'\bgradle\s+test\b',
            # Results
            r'\d+\s+passed',
            r'\d+\s+failed',
            r'test result:',
            r'Tests:\s*\d+',
            r'PASSED',
            r'FAILED',
        ]

        for pattern in test_indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    except Exception:
        return False


def get_test_summary_string(summary: TestSummary) -> str:
    """Format a test summary as a human-readable string."""
    if summary.result == TestResult.NOT_RUN:
        return "Tests not run"

    parts = []
    if summary.passed > 0:
        parts.append(f"{summary.passed} passed")
    if summary.failed > 0:
        parts.append(f"{summary.failed} failed")
    if summary.skipped > 0:
        parts.append(f"{summary.skipped} skipped")
    if summary.errors > 0:
        parts.append(f"{summary.errors} errors")

    result_str = ", ".join(parts) if parts else "No test results"

    if summary.duration > 0:
        result_str += f" ({summary.duration:.2f}s)"

    return result_str
