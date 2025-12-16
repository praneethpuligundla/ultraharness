#!/usr/bin/env python3
"""Stop hook for harness plugin.

Enhanced to provide blocking validation:
1. Check if tests were run (if code was modified)
2. Check if features are incomplete
3. Check for uncommitted changes
4. Validate merge-ready state

In strict mode, blocks stopping if validation fails.
In standard mode, provides strong reminders.
In relaxed mode, passive suggestions only.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, PLUGIN_ROOT)

# Constants
PROGRESS_FILE = "claude-progress.txt"
INIT_MARKER = ".claude-harness-initialized"

# Code file extensions
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.rs', '.go',
    '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb',
    '.swift', '.kt', '.scala', '.php', '.vue', '.svelte'
}

# Try to import modules
try:
    from core.config import load_config, is_strict_mode, is_relaxed_mode
except ImportError:
    def load_config(work_dir=None):
        return {"strictness": "standard"}
    def is_strict_mode(work_dir=None):
        return False
    def is_relaxed_mode(work_dir=None):
        return False

try:
    from core.features import load_features
except ImportError:
    def load_features(work_dir=None):
        return {"features": []}

try:
    from core.test_runner import did_tests_run_in_session
except ImportError:
    def did_tests_run_in_session(transcript_path):
        return False


def get_working_directory():
    """Get the working directory from environment."""
    return os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())


def check_harness_initialized(path):
    """Check if harness has been initialized."""
    marker_path = Path(path) / '.claude' / INIT_MARKER
    return marker_path.exists()


def has_uncommitted_changes(path):
    """Check if there are uncommitted changes."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_modified_files(path):
    """Get list of modified files."""
    try:
        # Get both staged and unstaged changes
        result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        files = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Also get untracked files
        result2 = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        untracked = result2.stdout.strip().split('\n') if result2.stdout.strip() else []

        return files + untracked
    except Exception:
        return []


def code_was_modified(path):
    """Check if code files were modified."""
    modified = get_modified_files(path)
    return any(
        Path(f).suffix.lower() in CODE_EXTENSIONS
        for f in modified if f
    )


def get_progress_file_status(path):
    """Check if progress file was modified in current session."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain', PROGRESS_FILE],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_features_status(work_dir):
    """Get status of features."""
    try:
        features_data = load_features(work_dir)
        features = features_data.get('features', [])

        in_progress = [f for f in features if f.get('status') == 'in_progress']
        failing = [f for f in features if f.get('status') == 'failing']
        passing = [f for f in features if f.get('status') == 'passing']

        return {
            'total': len(features),
            'in_progress': in_progress,
            'failing': failing,
            'passing': passing
        }
    except Exception:
        return {'total': 0, 'in_progress': [], 'failing': [], 'passing': []}


def validate_stop(work_dir: str, input_data: dict, config: dict) -> tuple:
    """
    Validate if agent can stop.

    Returns: (can_stop, blocking_reasons, warnings)
    """
    blocking_reasons = []  # Reasons that block stopping (in strict mode)
    warnings = []  # Non-blocking warnings

    transcript_path = input_data.get('transcript_path', '')

    # Check 1: Tests not run (if code was modified)
    if code_was_modified(work_dir):
        if not did_tests_run_in_session(transcript_path):
            blocking_reasons.append("Code was modified but tests were not run")

    # Check 2: Uncommitted changes
    if has_uncommitted_changes(work_dir):
        warnings.append("Uncommitted changes exist - consider creating a checkpoint")

    # Check 3: Features still in progress
    features = get_features_status(work_dir)
    if features['in_progress']:
        feature_names = ', '.join([f['name'] for f in features['in_progress'][:3]])
        warnings.append(f"Features still in progress: {feature_names}")

    # Check 4: Progress log not updated
    if not get_progress_file_status(work_dir) and code_was_modified(work_dir):
        warnings.append("Progress log not updated - consider logging your accomplishments")

    # Determine if stopping is allowed
    can_stop = len(blocking_reasons) == 0

    return can_stop, blocking_reasons, warnings


def build_stop_message(work_dir: str, input_data: dict):
    """Build validation message for session stop."""
    # Check if harness is initialized
    if not check_harness_initialized(work_dir):
        return {}

    # Load config
    config = load_config(work_dir)
    stop_reason = input_data.get('stopReason', input_data.get('reason', 'unknown'))

    # Only validate for normal stops (not errors/interrupts)
    if stop_reason not in ('end_turn', 'stop_sequence', 'unknown'):
        return {}

    # Run validation
    can_stop, blocking_reasons, warnings = validate_stop(work_dir, input_data, config)

    result = {}

    if is_strict_mode(work_dir):
        # Strict mode: block if validation fails
        if not can_stop:
            result['decision'] = 'block'
            result['reason'] = "Validation failed: " + "; ".join(blocking_reasons)

            message_parts = [
                "[Harness - STRICT MODE] Cannot stop due to:"
            ]
            message_parts.extend([f"  ! {r}" for r in blocking_reasons])

            if warnings:
                message_parts.append("")
                message_parts.append("Additional reminders:")
                message_parts.extend([f"  - {w}" for w in warnings])

            result['systemMessage'] = '\n'.join(message_parts)
        else:
            result['decision'] = 'approve'
            if warnings:
                result['systemMessage'] = "[Harness] Approved to stop.\n\nReminders:\n" + '\n'.join([f"  - {w}" for w in warnings])

    elif not is_relaxed_mode(work_dir):
        # Standard mode: strong warnings but no blocking
        message_parts = []

        if blocking_reasons:
            message_parts.append("[Harness] IMPORTANT - Before stopping:")
            message_parts.extend([f"  ! {r}" for r in blocking_reasons])
            message_parts.append("")

        if warnings:
            if not message_parts:
                message_parts.append("[Harness] Reminders before stopping:")
            else:
                message_parts.append("Additional reminders:")
            message_parts.extend([f"  - {w}" for w in warnings])

        if message_parts:
            result['systemMessage'] = '\n'.join(message_parts)

    else:
        # Relaxed mode: minimal suggestions
        all_items = blocking_reasons + warnings
        if all_items:
            result['systemMessage'] = f"[Harness] FYI: {all_items[0]}"

    return result


def main():
    """Main entry point for Stop hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)
        work_dir = get_working_directory()

        # Build stop message
        result = build_stop_message(work_dir, input_data)
        print(json.dumps(result))

    except Exception as e:
        # Non-blocking error handling
        error_msg = {"systemMessage": f"[Harness] Stop hook error: {str(e)}"}
        print(json.dumps(error_msg))

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
