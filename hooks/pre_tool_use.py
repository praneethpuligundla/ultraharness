#!/usr/bin/env python3
"""PreToolUse hook for FIC verification gates and feature enforcement.

This hook enforces:
1. FIC verification gates (research → planning → implementation)
2. One-feature-at-a-time discipline
3. Phase-appropriate tool usage

Non-blocking in standard mode, blocking in strict mode.
"""

import os
import sys
import json
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, PLUGIN_ROOT)

try:
    from core.config import load_config, is_strict_mode, is_relaxed_mode, is_harness_initialized
    from core.features import load_features, get_next_features
except ImportError:
    # Fallback if imports fail
    def load_config(work_dir=None):
        return {"feature_enforcement": True, "fic_enabled": True, "fic_strict_gates": True}
    def is_strict_mode(work_dir=None):
        return False
    def is_relaxed_mode(work_dir=None):
        return False
    def is_harness_initialized(work_dir=None):
        return False
    def load_features(work_dir=None):
        return {"features": []}
    def get_next_features(count=5, work_dir=None):
        return []

# FIC verification gates
try:
    from core.verification_gates import (
        Gate, GateAction, check_gate, format_gate_message
    )
    FIC_GATES_AVAILABLE = True
except ImportError:
    FIC_GATES_AVAILABLE = False
    class Gate:
        ALLOW_EDIT = "allow_edit"
        ALLOW_WRITE = "allow_write"
    class GateAction:
        ALLOW = "allow"
        WARN = "warn"
        BLOCK = "block"
    def check_gate(gate, work_dir=None, **kwargs):
        class Result:
            action = GateAction.ALLOW
            reason = ""
            suggestions = []
        return Result()
    def format_gate_message(result):
        return ""


def get_current_feature(work_dir: str) -> dict:
    """Get the currently in-progress feature."""
    try:
        features_data = load_features(work_dir)
        for feature in features_data.get('features', []):
            if feature.get('status') == 'in_progress':
                return feature
    except Exception:
        pass
    return None


def has_features_defined(work_dir: str) -> bool:
    """Check if any features are defined."""
    try:
        features_data = load_features(work_dir)
        return len(features_data.get('features', [])) > 0
    except Exception:
        return False


def validate_feature_focus(tool_name: str, tool_input: dict, work_dir: str) -> tuple:
    """
    Validate that work is focused on the current feature.

    Returns: (is_valid, message)
    """
    # Only validate file operations
    if tool_name not in ['Edit', 'Write']:
        return True, None

    # Check if features are defined
    if not has_features_defined(work_dir):
        return True, None  # No features defined, allow all

    current = get_current_feature(work_dir)

    if not current:
        # No feature in progress - prompt to select one
        try:
            next_features = get_next_features(3, work_dir)
            if next_features:
                feature_list = '\n'.join([
                    f"  {f['id']}. {f['name']}"
                    for f in next_features
                ])
                return False, (
                    f"[Harness] No feature currently in progress.\n"
                    f"Consider starting one before making changes:\n{feature_list}\n"
                    f"Use `/harness:feature start <id>` to begin."
                )
        except Exception:
            pass

        return False, (
            "[Harness] No feature currently in progress. "
            "Use `/harness:feature start <id>` to begin working on a feature."
        )

    # Feature is in progress, allow the operation
    return True, None


def check_fic_gates(tool_name: str, tool_input: dict, work_dir: str, config: dict) -> tuple:
    """
    Check FIC verification gates for Edit/Write operations.

    Returns: (action, message)
    - action: 'allow', 'warn', 'block'
    - message: Message to display (None if allow)
    """
    if not FIC_GATES_AVAILABLE:
        return 'allow', None

    if not config.get('fic_enabled', True):
        return 'allow', None

    # Only check gates for file modifications
    if tool_name not in ['Edit', 'Write']:
        return 'allow', None

    file_path = tool_input.get('file_path', '')

    # Determine which gate to check
    if tool_name == 'Edit':
        gate = Gate.ALLOW_EDIT
    else:
        gate = Gate.ALLOW_WRITE

    # Check the gate
    result = check_gate(gate, work_dir, file_path=file_path)

    if result.action == GateAction.BLOCK:
        return 'block', format_gate_message(result)
    elif result.action == GateAction.WARN:
        return 'warn', format_gate_message(result)
    else:
        return 'allow', None


def main():
    """Main entry point for PreToolUse hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        work_dir = os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())

        # Check if harness is initialized
        if not is_harness_initialized(work_dir):
            print(json.dumps({}))
            sys.exit(0)

        # Load config
        config = load_config(work_dir)

        # Skip all validation in relaxed mode
        if is_relaxed_mode(work_dir):
            print(json.dumps({}))
            sys.exit(0)

        result = {}
        messages = []

        # ========================================
        # FIC Verification Gates (Check First)
        # ========================================
        fic_action, fic_message = check_fic_gates(tool_name, tool_input, work_dir, config)

        if fic_action == 'block':
            # FIC gate blocks the operation
            result['hookSpecificOutput'] = {
                'permissionDecision': 'deny'
            }
            messages.append(fic_message)
            messages.append("\n[FIC Gate: Operation blocked. Complete prior phase first.]")
            result['systemMessage'] = '\n'.join(messages)
            print(json.dumps(result))
            sys.exit(0)
        elif fic_action == 'warn' and fic_message:
            messages.append(fic_message)

        # ========================================
        # Feature Focus Enforcement
        # ========================================
        if config.get('feature_enforcement', True):
            is_valid, feature_message = validate_feature_focus(tool_name, tool_input, work_dir)

            if not is_valid and feature_message:
                if is_strict_mode(work_dir):
                    # Block the operation in strict mode
                    result['hookSpecificOutput'] = {
                        'permissionDecision': 'deny'
                    }
                    messages.append(feature_message)
                    messages.append("\n[Strict mode: Operation blocked until a feature is started]")
                else:
                    # Just warn in standard mode
                    messages.append(feature_message)

        # Output result
        if messages:
            result['systemMessage'] = '\n'.join(messages)

        print(json.dumps(result))

    except Exception as e:
        # Non-blocking error handling
        error_msg = {"systemMessage": f"[Harness] PreToolUse hook error: {str(e)}"}
        print(json.dumps(error_msg))

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
