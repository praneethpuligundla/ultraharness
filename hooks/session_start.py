#!/usr/bin/env python3
"""SessionStart hook for harness plugin with FIC system.

This hook runs at the start of each Claude Code session and:
1. Checks if harness is initialized for the current project
2. Loads preserved context from prior sessions (FIC)
3. Shows FIC state: phase, confidence, open questions
4. Loads active artifacts (research, plan, implementation)
5. Executes init.sh if it exists
6. Runs baseline tests if configured
7. Reads git log for recent commits
8. Reads progress file for context
9. Reads feature checklist status
10. Injects context into the session via systemMessage
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, PLUGIN_ROOT)

# Constants
PROGRESS_FILE = "claude-progress.txt"
FEATURES_FILE = "claude-features.json"
INIT_MARKER = ".claude-harness-initialized"
INIT_SCRIPT = "init.sh"
PRESERVED_CONTEXT_FILE = "fic-preserved-context.json"

# Try to import config module
try:
    from core.config import load_config
except ImportError:
    def load_config(work_dir=None):
        return {
            "init_script_execution": True,
            "baseline_tests_on_startup": True,
            "fic_enabled": True
        }

# Try to import test runner
try:
    from core.test_runner import run_tests, get_test_summary_string, TestResult
except ImportError:
    class TestResult:
        NOT_RUN = "not_run"
        PASSED = "passed"
        FAILED = "failed"
    def run_tests(work_dir, timeout=120):
        class Summary:
            result = TestResult.NOT_RUN
            raw_output = "Test runner not available"
        return Summary()
    def get_test_summary_string(summary):
        return "Tests not run"

# FIC imports
try:
    from core.artifacts import (
        ArtifactType, get_latest_artifact, load_artifact
    )
    from core.context_intelligence import (
        extract_essential_context, get_state_path
    )
    FIC_AVAILABLE = True
except ImportError:
    FIC_AVAILABLE = False
    class ArtifactType:
        RESEARCH = "research"
        PLAN = "plan"
        IMPLEMENTATION = "implementation"
    def get_latest_artifact(artifact_type, work_dir=None):
        return None
    def load_artifact(artifact_type, artifact_id, work_dir=None):
        return None
    def extract_essential_context(state):
        return {}
    def get_state_path(work_dir=None):
        return Path(work_dir or '.') / '.claude' / 'fic-context-state.json'


def get_working_directory():
    """Get the working directory from environment or input."""
    return os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())


def is_git_repo(path):
    """Check if path is inside a git repository."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_git_log(path, num_commits=10):
    """Get recent git commits."""
    try:
        result = subprocess.run(
            ['git', 'log', f'-{num_commits}', '--oneline', '--no-decorate'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def get_git_status(path):
    """Get git status summary."""
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def read_progress_file(path):
    """Read the progress tracking file."""
    progress_path = Path(path) / PROGRESS_FILE
    if progress_path.exists():
        try:
            content = progress_path.read_text()
            # Return last 50 lines to avoid overwhelming context
            lines = content.strip().split('\n')
            if len(lines) > 50:
                return '\n'.join(['[...truncated...]'] + lines[-50:])
            return content
        except Exception:
            return None
    return None


def read_features_file(path):
    """Read and summarize the features checklist."""
    features_path = Path(path) / FEATURES_FILE
    if features_path.exists():
        try:
            with open(features_path, 'r') as f:
                features = json.load(f)

            # Count statuses
            total = len(features.get('features', []))
            passing = sum(1 for f in features.get('features', []) if f.get('status') == 'passing')
            failing = sum(1 for f in features.get('features', []) if f.get('status') == 'failing')
            in_progress = sum(1 for f in features.get('features', []) if f.get('status') == 'in_progress')

            # Get next priority items
            next_items = [
                f for f in features.get('features', [])
                if f.get('status') in ('failing', 'in_progress')
            ][:5]

            summary = {
                'total': total,
                'passing': passing,
                'failing': failing,
                'in_progress': in_progress,
                'next_items': next_items
            }
            return summary
        except Exception:
            return None
    return None


def check_harness_initialized(path):
    """Check if harness has been initialized for this project."""
    marker_path = Path(path) / '.claude' / INIT_MARKER
    return marker_path.exists()


def load_preserved_context(work_dir: str) -> dict:
    """Load preserved context from prior session."""
    preserved_path = Path(work_dir) / '.claude' / PRESERVED_CONTEXT_FILE
    if preserved_path.exists():
        try:
            with open(preserved_path, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def get_fic_state(work_dir: str, config: dict) -> dict:
    """Get current FIC state including active artifacts."""
    if not FIC_AVAILABLE or not config.get('fic_enabled', True):
        return None

    state = {
        'phase': 'UNKNOWN',
        'research': None,
        'plan': None,
        'implementation': None,
        'preserved_context': None
    }

    try:
        # Check for preserved context from prior session
        state['preserved_context'] = load_preserved_context(work_dir)

        # Get latest artifacts to determine phase
        research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)
        plan = get_latest_artifact(ArtifactType.PLAN, work_dir)
        impl = get_latest_artifact(ArtifactType.IMPLEMENTATION, work_dir)

        if impl:
            state['implementation'] = impl
            state['phase'] = 'IMPLEMENTATION'
            # Load the linked plan
            if hasattr(impl, 'plan_artifact_id'):
                state['plan'] = load_artifact(ArtifactType.PLAN, impl.plan_artifact_id, work_dir)
        elif plan:
            state['plan'] = plan
            if hasattr(plan, 'is_actionable') and plan.is_actionable():
                state['phase'] = 'IMPLEMENTATION_READY'
            else:
                state['phase'] = 'PLANNING'
            # Load the linked research
            if hasattr(plan, 'research_artifact_id'):
                state['research'] = load_artifact(ArtifactType.RESEARCH, plan.research_artifact_id, work_dir)
        elif research:
            state['research'] = research
            if hasattr(research, 'is_complete') and research.is_complete():
                state['phase'] = 'PLANNING_READY'
            else:
                state['phase'] = 'RESEARCH'
        else:
            state['phase'] = 'NEW_SESSION'

        return state

    except Exception:
        return None


def format_fic_context(fic_state: dict) -> list:
    """Format FIC state for session startup message."""
    messages = []

    if not fic_state:
        return messages

    messages.append("--- FIC WORKFLOW STATE ---")
    messages.append(f"Phase: {fic_state['phase']}")

    # Show preserved context from prior session
    if fic_state.get('preserved_context'):
        preserved = fic_state['preserved_context']
        messages.append("")
        messages.append("Prior Session Context:")
        if preserved.get('essential_discoveries'):
            for disc in preserved['essential_discoveries'][:5]:
                messages.append(f"  - {disc.get('summary', 'Unknown discovery')}")
        if preserved.get('focus_directive'):
            messages.append(f"Focus: {preserved['focus_directive']}")

    # Show research state
    if fic_state.get('research'):
        research = fic_state['research']
        messages.append("")
        messages.append(f"Active Research: {getattr(research, 'feature_or_task', 'Unknown')}")
        messages.append(f"  Confidence: {getattr(research, 'confidence_score', 0):.0%}")
        messages.append(f"  Discoveries: {len(getattr(research, 'discoveries', []))}")
        open_q = getattr(research, 'open_questions', [])
        blocking_q = [q for q in open_q if getattr(q, 'blocking', False)]
        messages.append(f"  Open Questions: {len(open_q)} ({len(blocking_q)} blocking)")

    # Show plan state
    if fic_state.get('plan'):
        plan = fic_state['plan']
        messages.append("")
        messages.append(f"Active Plan: {getattr(plan, 'goal', 'Unknown')[:60]}")
        steps = getattr(plan, 'steps', [])
        messages.append(f"  Steps: {len(steps)}")
        validation = getattr(plan, 'validation_result', None)
        if validation:
            messages.append(f"  Validation: {getattr(validation, 'recommendation', 'Unknown')}")

    # Show implementation progress
    if fic_state.get('implementation'):
        impl = fic_state['implementation']
        completed = len(getattr(impl, 'steps_completed', []))
        in_progress = len(getattr(impl, 'steps_in_progress', []))
        deviations = len(getattr(impl, 'plan_deviations', []))
        messages.append("")
        messages.append(f"Implementation Progress:")
        messages.append(f"  Completed Steps: {completed}")
        messages.append(f"  In Progress: {in_progress}")
        if deviations:
            messages.append(f"  Plan Deviations: {deviations}")

    messages.append("")
    return messages


def run_init_script(work_dir: str, config: dict) -> str:
    """Execute init.sh if it exists and is configured."""
    if not config.get('init_script_execution', True):
        return None

    init_script = Path(work_dir) / INIT_SCRIPT

    if not init_script.exists():
        return None

    # Validate script is readable and not too large (10KB limit)
    try:
        if init_script.stat().st_size > 10000:
            return "Warning: init.sh too large (>10KB), skipping for safety"
    except Exception:
        return None

    try:
        # Run with timeout and capture output
        result = subprocess.run(
            ['bash', str(init_script)],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=60  # 1 minute max
        )

        output = result.stdout[:500] if result.stdout else ""
        if result.returncode == 0:
            if output:
                return f"init.sh executed successfully:\n{output}"
            return "init.sh executed successfully"
        else:
            error = result.stderr[:200] if result.stderr else "Unknown error"
            return f"init.sh warning (exit {result.returncode}): {error}"

    except subprocess.TimeoutExpired:
        return "Warning: init.sh timed out after 60 seconds"
    except PermissionError:
        return "Warning: init.sh not executable (run: chmod +x init.sh)"
    except Exception as e:
        return f"Warning: init.sh failed: {str(e)}"


def run_baseline_tests(work_dir: str, config: dict) -> str:
    """Run baseline tests before starting work."""
    if not config.get('baseline_tests_on_startup', True):
        return None

    try:
        summary = run_tests(work_dir, timeout=120)

        if summary.result == TestResult.NOT_RUN:
            return None  # No test command found, skip silently

        summary_str = get_test_summary_string(summary)

        if summary.result == TestResult.PASSED:
            return f"Baseline tests PASSED: {summary_str}"
        elif summary.result == TestResult.FAILED:
            return f"WARNING: Baseline tests FAILING: {summary_str}\nReview failures before making changes."
        else:
            return f"Baseline test error: {summary.raw_output[:200]}"

    except Exception as e:
        return f"Baseline test error: {str(e)}"


def build_context_message(work_dir):
    """Build the context message for session startup."""
    messages = []

    # Check if harness is initialized
    if not check_harness_initialized(work_dir):
        return {
            "systemMessage": (
                "[Agent Harness] This project has not been initialized with the agent harness. "
                "Run `/harness:init` to set up progress tracking, feature checklists, and git checkpoints. "
                "This enables effective long-running agent workflows with automatic progress logging."
            )
        }

    # Load configuration
    config = load_config(work_dir)

    messages.append("=== AGENT HARNESS SESSION STARTUP ===")
    messages.append(f"Session started: {datetime.now().isoformat()}")
    messages.append(f"Working directory: {work_dir}")
    messages.append(f"Mode: {config.get('strictness', 'standard')}")
    messages.append("")

    # ========================================
    # FIC Workflow State (High Priority)
    # ========================================
    if config.get('fic_enabled', True) and FIC_AVAILABLE:
        fic_state = get_fic_state(work_dir, config)
        fic_messages = format_fic_context(fic_state)
        if fic_messages:
            messages.extend(fic_messages)

    # Run init script
    init_result = run_init_script(work_dir, config)
    if init_result:
        messages.append("--- INIT SCRIPT ---")
        messages.append(init_result)
        messages.append("")

    # Run baseline tests
    baseline_result = run_baseline_tests(work_dir, config)
    if baseline_result:
        messages.append("--- BASELINE TESTS ---")
        messages.append(baseline_result)
        messages.append("")

    # Git status and log
    if is_git_repo(work_dir):
        messages.append("--- GIT STATUS ---")
        git_status = get_git_status(work_dir)
        if git_status:
            messages.append(git_status)
        else:
            messages.append("(clean)")
        messages.append("")

        messages.append("--- RECENT COMMITS ---")
        git_log = get_git_log(work_dir)
        if git_log:
            messages.append(git_log)
        else:
            messages.append("(no commits)")
        messages.append("")

    # Progress file
    progress = read_progress_file(work_dir)
    if progress:
        messages.append("--- PROGRESS LOG ---")
        messages.append(progress)
        messages.append("")

    # Features checklist
    features = read_features_file(work_dir)
    if features:
        messages.append("--- FEATURE CHECKLIST STATUS ---")
        messages.append(f"Total: {features['total']} | Passing: {features['passing']} | Failing: {features['failing']} | In Progress: {features['in_progress']}")
        if features['next_items']:
            messages.append("")
            messages.append("Next priority items:")
            for item in features['next_items']:
                status_icon = "[WIP]" if item.get('status') == 'in_progress' else "[TODO]"
                messages.append(f"  {status_icon} {item.get('id', '?')}. {item.get('name', 'Unnamed')}: {item.get('description', '')[:60]}")
        messages.append("")

    messages.append("=== END SESSION CONTEXT ===")
    messages.append("")

    # Add automation reminders
    auto_features = []
    if config.get('auto_progress_logging', True):
        auto_features.append("auto-logging")
    if config.get('auto_checkpoint_suggestions', True):
        auto_features.append("checkpoint suggestions")
    if config.get('feature_enforcement', True):
        auto_features.append("feature enforcement")
    if config.get('fic_enabled', True):
        auto_features.append("FIC context tracking")

    if auto_features:
        messages.append(f"Automation enabled: {', '.join(auto_features)}")
        messages.append("")

    # Phase-specific guidance
    fic_state = get_fic_state(work_dir, config) if config.get('fic_enabled', True) else None
    if fic_state and fic_state.get('phase'):
        phase = fic_state['phase']
        if phase == 'NEW_SESSION':
            messages.append("IMPORTANT: This is a new session. For complex tasks, start with RESEARCH to understand the codebase.")
            messages.append("Delegate exploration to subagents to keep main context clean.")
        elif phase == 'RESEARCH':
            messages.append("IMPORTANT: Continue RESEARCH phase. Build confidence before planning.")
            messages.append("Use subagents for exploration. Only essential findings should enter main context.")
        elif phase == 'PLANNING_READY':
            messages.append("IMPORTANT: Research complete. Ready to create an implementation PLAN.")
            messages.append("Create specific, actionable steps with verification criteria.")
        elif phase == 'PLANNING':
            messages.append("IMPORTANT: Continue PLANNING. Validate the plan before implementation.")
        elif phase == 'IMPLEMENTATION_READY':
            messages.append("IMPORTANT: Plan validated. Ready to IMPLEMENT.")
            messages.append("Follow the plan steps. Document any deviations.")
        elif phase == 'IMPLEMENTATION':
            messages.append("IMPORTANT: Continue IMPLEMENTATION. Track progress against the plan.")
    else:
        messages.append("IMPORTANT: Review the above context. Select the highest-priority feature to work on.")
        if features and features['in_progress'] == 0 and features['failing'] > 0:
            messages.append("Use `/harness:feature start <id>` to begin working on a feature.")

    return {"systemMessage": '\n'.join(messages)}


def main():
    """Main entry point for SessionStart hook."""
    try:
        # Read input from stdin (contains session info)
        input_data = json.load(sys.stdin)

        # Get working directory
        work_dir = get_working_directory()

        # Build and output context message
        result = build_context_message(work_dir)
        print(json.dumps(result), file=sys.stdout)

    except Exception as e:
        # On error, output informative message but don't block
        error_output = {
            "systemMessage": f"[Agent Harness] Session startup check failed: {str(e)}"
        }
        print(json.dumps(error_output), file=sys.stdout)

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
