#!/usr/bin/env python3
"""PreCompact hook for FIC context preservation.

This hook runs before context compaction to:
1. Extract essential context (decisions, blockers, discoveries)
2. Save to preserved context file
3. Inject focus directive for post-compaction
4. Summarize current phase and active plan steps
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
    from core.config import load_config, is_harness_initialized
except ImportError:
    def load_config(work_dir=None):
        return {"fic_enabled": True}
    def is_harness_initialized(work_dir=None):
        return False

try:
    from core.context_intelligence import (
        load_context_state, extract_essential_context, get_context_summary
    )
    CONTEXT_AVAILABLE = True
except ImportError:
    CONTEXT_AVAILABLE = False
    def load_context_state(session_id, work_dir=None):
        return None
    def extract_essential_context(state):
        return {}
    def get_context_summary(state):
        return ""

try:
    from core.artifacts import (
        ArtifactType, get_latest_artifact
    )
    ARTIFACTS_AVAILABLE = True
except ImportError:
    ARTIFACTS_AVAILABLE = False
    class ArtifactType:
        RESEARCH = "research"
        PLAN = "plan"
        IMPLEMENTATION = "implementation"
    def get_latest_artifact(artifact_type, work_dir=None):
        return None


PRESERVED_CONTEXT_FILE = "fic-preserved-context.json"


def get_current_phase(work_dir: str) -> dict:
    """Get current FIC phase and active artifacts."""
    if not ARTIFACTS_AVAILABLE:
        return {'phase': 'UNKNOWN', 'details': {}}

    try:
        research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)
        plan = get_latest_artifact(ArtifactType.PLAN, work_dir)
        impl = get_latest_artifact(ArtifactType.IMPLEMENTATION, work_dir)

        phase_info = {
            'phase': 'NEW_SESSION',
            'details': {}
        }

        if impl:
            phase_info['phase'] = 'IMPLEMENTATION'
            phase_info['details'] = {
                'implementation_id': getattr(impl, 'id', None),
                'steps_completed': len(getattr(impl, 'steps_completed', [])),
                'steps_in_progress': getattr(impl, 'steps_in_progress', []),
                'plan_id': getattr(impl, 'plan_artifact_id', None)
            }
        elif plan:
            is_actionable = hasattr(plan, 'is_actionable') and plan.is_actionable()
            phase_info['phase'] = 'IMPLEMENTATION_READY' if is_actionable else 'PLANNING'
            phase_info['details'] = {
                'plan_id': getattr(plan, 'id', None),
                'goal': getattr(plan, 'goal', '')[:100],
                'total_steps': len(getattr(plan, 'steps', [])),
                'is_validated': getattr(plan, 'validation_result', None) is not None
            }
        elif research:
            is_complete = hasattr(research, 'is_complete') and research.is_complete()
            phase_info['phase'] = 'PLANNING_READY' if is_complete else 'RESEARCH'
            phase_info['details'] = {
                'research_id': getattr(research, 'id', None),
                'feature': getattr(research, 'feature_or_task', ''),
                'confidence': getattr(research, 'confidence_score', 0),
                'discoveries': len(getattr(research, 'discoveries', [])),
                'open_questions': len(getattr(research, 'open_questions', []))
            }

        return phase_info

    except Exception:
        return {'phase': 'UNKNOWN', 'details': {}}


def build_focus_directive(phase_info: dict, essential_context: dict) -> str:
    """Build a focus directive for post-compaction."""
    phase = phase_info.get('phase', 'UNKNOWN')
    details = phase_info.get('details', {})

    if phase == 'IMPLEMENTATION':
        steps_in_progress = details.get('steps_in_progress', [])
        if steps_in_progress:
            return f"Continue implementation. In progress: {', '.join(steps_in_progress[:3])}"
        return f"Continue implementation. {details.get('steps_completed', 0)} steps completed."

    elif phase == 'IMPLEMENTATION_READY':
        return f"Plan validated. Begin implementation of: {details.get('goal', 'Unknown goal')[:60]}"

    elif phase == 'PLANNING':
        return f"Continue planning. Goal: {details.get('goal', 'Unknown')[:60]}"

    elif phase == 'PLANNING_READY':
        return f"Research complete (confidence: {details.get('confidence', 0):.0%}). Create implementation plan."

    elif phase == 'RESEARCH':
        return f"Continue research on: {details.get('feature', 'Unknown')}. Build confidence to >= 70%."

    return "Review context and determine next steps."


def save_preserved_context(context: dict, work_dir: str) -> bool:
    """Save preserved context to file."""
    preserved_path = Path(work_dir) / '.claude' / PRESERVED_CONTEXT_FILE
    try:
        preserved_path.parent.mkdir(parents=True, exist_ok=True)
        with open(preserved_path, 'w') as f:
            json.dump(context, f, indent=2, default=str)
        return True
    except Exception:
        return False


def main():
    """Main entry point for PreCompact hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        session_id = input_data.get('session_id', 'default')
        work_dir = os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())

        # Check if harness is initialized
        if not is_harness_initialized(work_dir):
            print(json.dumps({}))
            sys.exit(0)

        # Load config
        config = load_config(work_dir)

        # Check if FIC is enabled
        if not config.get('fic_enabled', True):
            print(json.dumps({}))
            sys.exit(0)

        fic_config = config.get('fic_config', {})
        preserve_essential = fic_config.get('preserve_essential_on_compact', True)

        if not preserve_essential:
            print(json.dumps({}))
            sys.exit(0)

        messages = []

        # Get current phase
        phase_info = get_current_phase(work_dir)

        # Extract essential context
        essential_context = {}
        if CONTEXT_AVAILABLE:
            context_state = load_context_state(session_id, work_dir)
            if context_state:
                essential_context = extract_essential_context(context_state)
                context_summary = get_context_summary(context_state)
                if context_summary:
                    messages.append(f"[FIC] Context state: {context_summary}")

        # Build focus directive
        focus_directive = build_focus_directive(phase_info, essential_context)

        # Assemble preserved context
        preserved_context = {
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'phase': phase_info['phase'],
            'phase_details': phase_info['details'],
            'focus_directive': focus_directive,
            'essential_discoveries': essential_context.get('essential_discoveries', []),
            'token_estimate_at_compact': essential_context.get('token_estimate', 0),
            'utilization_at_compact': essential_context.get('utilization_at_extraction', 0)
        }

        # Save preserved context
        if save_preserved_context(preserved_context, work_dir):
            messages.append("[FIC] Context preserved for next session.")

        # Build focus directive message
        messages.append("")
        messages.append("=" * 50)
        messages.append("FIC CONTEXT PRESERVATION")
        messages.append("=" * 50)
        messages.append(f"Phase: {phase_info['phase']}")
        messages.append(f"Focus: {focus_directive}")

        if essential_context.get('essential_discoveries'):
            messages.append("")
            messages.append("Essential Discoveries Preserved:")
            for disc in essential_context['essential_discoveries'][:5]:
                messages.append(f"  - {disc.get('summary', 'Unknown')}")

        messages.append("=" * 50)
        messages.append("")
        messages.append("After compaction, continue with the focus directive above.")
        messages.append("Disregard exploration noise. Focus on completing the current phase.")

        # Output result
        result = {}
        if messages:
            result['systemMessage'] = '\n'.join(messages)

        print(json.dumps(result))

    except Exception as e:
        # Non-blocking error handling
        error_msg = {"systemMessage": f"[FIC] PreCompact hook error: {str(e)}"}
        print(json.dumps(error_msg))

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
