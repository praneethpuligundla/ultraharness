#!/usr/bin/env python3
"""PostToolUse hook for FIC context intelligence and progress tracking.

This hook runs after Edit, Write, Bash, Read, Grep, Glob, and Task tools to:
1. Track what INFORMATION enters context (not just tool calls)
2. Classify information as essential/helpful/noise
3. Detect redundant discoveries
4. Estimate context utilization
5. Suggest compaction when utilization is high
6. Auto-log significant changes
7. Suggest checkpoints after major changes
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, PLUGIN_ROOT)

try:
    from core.config import load_config, is_relaxed_mode, is_harness_initialized, get_setting
    from core.change_detector import classify_change, should_auto_log, should_suggest_checkpoint, ChangeLevel
    from core.progress import append_progress
    from core.features import load_features, get_next_features
except ImportError:
    # Fallback if imports fail
    def load_config(work_dir=None):
        return {"auto_progress_logging": True, "auto_checkpoint_suggestions": True, "fic_enabled": True}
    def is_relaxed_mode(work_dir=None):
        return False
    def is_harness_initialized(work_dir=None):
        return False
    def get_setting(key, work_dir=None):
        return None
    def classify_change(tool_name, tool_input, tool_result=None):
        return ("trivial", "fallback")
    def should_auto_log(level):
        return False
    def should_suggest_checkpoint(level):
        return False
    class ChangeLevel:
        TRIVIAL = "trivial"
        SIGNIFICANT = "significant"
        MAJOR = "major"
    def append_progress(msg, work_dir=None):
        pass
    def load_features(work_dir=None):
        return {"features": []}
    def get_next_features(count=5, work_dir=None):
        return []

# FIC Context Intelligence imports
try:
    from core.context_intelligence import (
        load_context_state, save_context_state, add_context_entry,
        get_context_summary, InformationClass
    )
    FIC_AVAILABLE = True
except ImportError:
    FIC_AVAILABLE = False
    def load_context_state(session_id, work_dir=None):
        return None
    def save_context_state(state, work_dir=None):
        return False
    def add_context_entry(state, tool_name, tool_input, tool_result):
        return state, None
    def get_context_summary(state):
        return ""


# State file for tracking cumulative changes within a session
STATE_FILE_TEMPLATE = "/tmp/harness-session-{session_id}.json"


def get_state_file(session_id: str) -> Path:
    """Get path to session state file."""
    return Path(STATE_FILE_TEMPLATE.format(session_id=session_id or 'default'))


def load_session_state(session_id: str) -> dict:
    """Load session state for tracking cumulative changes."""
    state_file = get_state_file(session_id)
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "changes_since_checkpoint": 0,
        "last_checkpoint_time": None,
        "significant_changes": [],
        "current_feature": None
    }


def save_session_state(session_id: str, state: dict):
    """Save session state."""
    state_file = get_state_file(session_id)
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f)
    except Exception:
        pass


def should_suggest_checkpoint_by_time(state: dict, config: dict) -> bool:
    """Check if enough time has passed since last checkpoint."""
    interval = config.get('checkpoint_interval_minutes', 30)
    last_time = state.get('last_checkpoint_time')

    if not last_time:
        return False

    try:
        last_dt = datetime.fromisoformat(last_time)
        elapsed = (datetime.now() - last_dt).total_seconds() / 60
        return elapsed >= interval
    except Exception:
        return False


def format_auto_log_entry(tool_name: str, tool_input: dict, reason: str) -> str:
    """Format an auto-generated progress log entry."""
    if tool_name == "Write":
        file_path = tool_input.get('file_path', 'unknown')
        filename = Path(file_path).name
        return f"AUTO: Created {filename} ({reason})"
    elif tool_name == "Edit":
        file_path = tool_input.get('file_path', 'unknown')
        filename = Path(file_path).name
        return f"AUTO: Modified {filename} ({reason})"
    elif tool_name == "Bash":
        command = tool_input.get('command', '')[:40]
        if len(tool_input.get('command', '')) > 40:
            command += '...'
        return f"AUTO: Ran '{command}' ({reason})"
    return f"AUTO: {tool_name} ({reason})"


def check_test_results(tool_result: str) -> tuple:
    """
    Check if tool result contains test output.
    Returns: (has_tests, passed, failed)
    """
    if not tool_result:
        return False, False, False

    result_str = str(tool_result)

    # Check for test result indicators
    has_passed = any(indicator in result_str for indicator in [
        'passed', 'PASSED', 'passing', 'ok', 'test result: ok'
    ])
    has_failed = any(indicator in result_str for indicator in [
        'failed', 'FAILED', 'failing', 'FAIL', 'error', 'ERROR'
    ])

    has_tests = has_passed or has_failed

    return has_tests, has_passed and not has_failed, has_failed


def main():
    """Main entry point for PostToolUse hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        # Extract data
        session_id = input_data.get('session_id', 'default')
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        tool_result = input_data.get('tool_result', '')
        work_dir = os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())

        # Check if harness is initialized
        if not is_harness_initialized(work_dir):
            print(json.dumps({}))
            sys.exit(0)

        # Load config
        config = load_config(work_dir)

        messages = []

        # ========================================
        # FIC Context Intelligence Tracking
        # ========================================
        fic_enabled = config.get('fic_enabled', True) and config.get('fic_context_tracking', True)

        if fic_enabled and FIC_AVAILABLE:
            # Track ALL tools for context intelligence (Read, Grep, Glob, Task, Edit, Write, Bash)
            context_state = load_context_state(session_id, work_dir)

            if context_state:
                # Add this tool use to context tracking
                context_state, warning = add_context_entry(
                    context_state, tool_name, tool_input, str(tool_result)
                )

                # Save updated state
                save_context_state(context_state, work_dir)

                # Add warnings to messages
                if warning:
                    messages.append(f"[FIC] {warning}")

                # Check compaction threshold
                fic_config = config.get('fic_config', {})
                compaction_threshold = fic_config.get('compaction_tool_threshold', 25)

                if len(context_state.entries) >= compaction_threshold:
                    util_high = fic_config.get('target_utilization_high', 0.60)
                    if context_state.utilization_percent >= util_high:
                        messages.append(f"[FIC] Context utilization at {context_state.utilization_percent:.0%}. Consider compacting or using subagents for research.")

                # Show redundancy warnings
                if len(context_state.redundant_discoveries) > 0:
                    recent_redundant = context_state.redundant_discoveries[-1]
                    messages.append(f"[FIC] Potential redundant exploration: {recent_redundant}")

        # Skip further processing in relaxed mode
        if is_relaxed_mode(work_dir):
            if messages:
                print(json.dumps({"systemMessage": '\n'.join(messages)}))
            else:
                print(json.dumps({}))
            sys.exit(0)

        # ========================================
        # Original Progress Tracking (Edit/Write/Bash only)
        # ========================================
        if tool_name not in ['Edit', 'Write', 'Bash']:
            # Output any FIC messages but skip progress tracking for read-only tools
            if messages:
                print(json.dumps({"systemMessage": '\n'.join(messages)}))
            else:
                print(json.dumps({}))
            sys.exit(0)

        # Classify the change
        level, reason = classify_change(tool_name, tool_input, tool_result)

        # Load and update session state
        state = load_session_state(session_id)

        # Auto-log significant changes
        if config.get('auto_progress_logging', True) and should_auto_log(level):
            log_entry = format_auto_log_entry(tool_name, tool_input, reason)
            try:
                append_progress(log_entry, work_dir)
            except Exception:
                pass
            state['significant_changes'].append({
                'time': datetime.now().isoformat(),
                'level': level.value if hasattr(level, 'value') else str(level),
                'reason': reason
            })

        # Track changes for checkpoint suggestions
        if hasattr(level, 'value'):
            level_value = level.value
        else:
            level_value = str(level)

        if level_value == 'significant':
            state['changes_since_checkpoint'] += 1
        elif level_value == 'major':
            state['changes_since_checkpoint'] += 3

        # Suggest checkpoint if appropriate
        suggest_checkpoint = False
        checkpoint_reason = ""

        if config.get('auto_checkpoint_suggestions', True):
            if should_suggest_checkpoint(level):
                suggest_checkpoint = True
                checkpoint_reason = f"Major change: {reason}"
            elif state['changes_since_checkpoint'] >= 5:
                suggest_checkpoint = True
                checkpoint_reason = f"{state['changes_since_checkpoint']} significant changes accumulated"
            elif should_suggest_checkpoint_by_time(state, config):
                suggest_checkpoint = True
                interval = config.get('checkpoint_interval_minutes', 30)
                checkpoint_reason = f"Time-based checkpoint ({interval} min elapsed)"

        if suggest_checkpoint:
            messages.append(f"[Harness] Consider creating a checkpoint: {checkpoint_reason}")
            messages.append("Use `/harness:checkpoint <description>` to save progress.")

        # Check for test result parsing (for Bash commands that ran tests)
        if tool_name == "Bash":
            has_tests, tests_passed, tests_failed = check_test_results(str(tool_result))

            if has_tests:
                if tests_passed:
                    # Tests passed - suggest updating feature status
                    try:
                        next_features = get_next_features(1, work_dir)
                        if next_features and next_features[0].get('status') == 'in_progress':
                            feature = next_features[0]
                            messages.append(f"[Harness] Tests passed! Consider marking '{feature['name']}' as passing:")
                            messages.append(f"Use `/harness:feature pass {feature['id']}`")
                    except Exception:
                        pass
                elif tests_failed:
                    messages.append("[Harness] Tests failed. Review failures before continuing.")

        # Save updated state
        save_session_state(session_id, state)

        # Output result
        result = {}
        if messages:
            result['systemMessage'] = '\n'.join(messages)

        print(json.dumps(result))

    except Exception as e:
        # Non-blocking error handling
        error_msg = {"systemMessage": f"[Harness] PostToolUse hook error: {str(e)}"}
        print(json.dumps(error_msg))

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
