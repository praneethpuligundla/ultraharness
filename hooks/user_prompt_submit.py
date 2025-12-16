#!/usr/bin/env python3
"""UserPromptSubmit hook for FIC auto-delegation and phase detection.

This hook runs when the user submits a prompt and:
1. Detects research-triggering prompts (exploration, investigation)
2. Detects planning-triggering prompts
3. Injects directives to delegate to appropriate subagents
4. Enforces workflow phase transitions
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
if PLUGIN_ROOT:
    sys.path.insert(0, PLUGIN_ROOT)

try:
    from core.config import load_config, is_harness_initialized, get_setting
except ImportError:
    def load_config(work_dir=None):
        return {"fic_enabled": True, "fic_auto_delegate_research": True}
    def is_harness_initialized(work_dir=None):
        return False
    def get_setting(key, work_dir=None):
        return None

try:
    from core.artifacts import ArtifactType, get_latest_artifact
except ImportError:
    class ArtifactType:
        RESEARCH = "research"
        PLAN = "plan"
        IMPLEMENTATION = "implementation"
    def get_latest_artifact(artifact_type, work_dir=None):
        return None


# Research-triggering patterns
DEFAULT_RESEARCH_PATTERNS = [
    r'\bhow does\b',
    r'\bwhere is\b',
    r'\bfind the\b',
    r'\bunderstand\b',
    r'\bexplore\b',
    r'\binvestigate\b',
    r'\bwhat is\b',
    r'\bexplain the\b',
    r'\bwhat does\b',
    r'\bhow is\b',
    r'\bwhere are\b',
    r'\blook for\b',
    r'\bsearch for\b',
    r'\bfigure out\b',
    r'\blearn about\b',
    r'\bresearch\b',
]

# Planning-triggering patterns
PLANNING_PATTERNS = [
    r'\bimplement\b',
    r'\badd\b.*\bfeature\b',
    r'\bcreate\b.*\bfunction\b',
    r'\bbuild\b',
    r'\brefactor\b',
    r'\bfix\b.*\bbug\b',
    r'\bupdate\b.*\bcode\b',
    r'\bmodify\b',
    r'\bchange\b.*\bimplementation\b',
]


def detect_research_prompt(prompt: str, patterns: list) -> bool:
    """Detect if prompt is requesting research/exploration."""
    prompt_lower = prompt.lower()

    for pattern in patterns:
        if re.search(pattern, prompt_lower):
            return True

    return False


def detect_planning_prompt(prompt: str) -> bool:
    """Detect if prompt is requesting implementation/planning."""
    prompt_lower = prompt.lower()

    for pattern in PLANNING_PATTERNS:
        if re.search(pattern, prompt_lower):
            return True

    return False


def get_current_phase(work_dir: str) -> str:
    """Determine current FIC workflow phase."""
    try:
        research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)
        plan = get_latest_artifact(ArtifactType.PLAN, work_dir)
        impl = get_latest_artifact(ArtifactType.IMPLEMENTATION, work_dir)

        if impl:
            return 'IMPLEMENTATION'
        elif plan:
            if hasattr(plan, 'is_actionable') and plan.is_actionable():
                return 'IMPLEMENTATION_READY'
            return 'PLANNING'
        elif research:
            if hasattr(research, 'is_complete') and research.is_complete():
                return 'PLANNING_READY'
            return 'RESEARCH'
        else:
            return 'NEW_SESSION'
    except Exception:
        return 'UNKNOWN'


def build_research_directive(prompt: str, phase: str) -> str:
    """Build directive to delegate research to subagent."""
    return f"""[FIC] Research request detected.

DIRECTIVE: For complex exploration tasks, consider delegating to the @fic-researcher subagent.
This keeps exploration noise OUT of your main context.

Use the Task tool with subagent_type="Explore" or a custom research agent.

Current Phase: {phase}
Original Request: {prompt[:100]}{'...' if len(prompt) > 100 else ''}

Only ESSENTIAL FINDINGS should enter this context. The subagent will return structured research results."""


def build_planning_directive(prompt: str, phase: str, has_research: bool) -> str:
    """Build directive for planning phase."""
    if phase == 'NEW_SESSION' or (phase == 'RESEARCH' and not has_research):
        return f"""[FIC] Implementation request detected, but research phase incomplete.

DIRECTIVE: Before implementing, complete RESEARCH to understand:
- What existing code does this affect?
- What patterns does the codebase use?
- What dependencies exist?

Consider delegating exploration to a subagent first.

Current Phase: {phase}
Request: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"""

    elif phase == 'PLANNING_READY':
        return f"""[FIC] Implementation request detected. Research is complete.

DIRECTIVE: Create an implementation PLAN before writing code.
- Define specific, actionable steps
- Identify files to modify
- Set verification criteria

Consider using the @fic-plan-validator subagent to validate your plan.

Current Phase: {phase}"""

    elif phase == 'PLANNING':
        return f"""[FIC] Implementation request detected. A plan exists but may not be validated.

DIRECTIVE: Validate the current plan before implementation.
- Review plan completeness
- Check for missing steps
- Ensure verification criteria exist

Current Phase: {phase}"""

    return None


def main():
    """Main entry point for UserPromptSubmit hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        # Extract data
        prompt = input_data.get('prompt', '')
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

        # Get FIC configuration
        fic_config = config.get('fic_config', {})
        research_patterns = fic_config.get('research_delegation_patterns', [])

        # Convert string patterns to regex patterns
        if research_patterns:
            pattern_list = [rf'\b{p}\b' for p in research_patterns]
        else:
            pattern_list = DEFAULT_RESEARCH_PATTERNS

        messages = []

        # Get current phase
        phase = get_current_phase(work_dir)

        # Check for research prompt
        is_research = detect_research_prompt(prompt, pattern_list)
        is_planning = detect_planning_prompt(prompt)

        # Auto-delegate research
        if config.get('fic_auto_delegate_research', True) and is_research:
            directive = build_research_directive(prompt, phase)
            messages.append(directive)

        # Planning guidance
        elif is_planning and phase in ('NEW_SESSION', 'RESEARCH', 'PLANNING_READY', 'PLANNING'):
            research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)
            has_complete_research = research and hasattr(research, 'is_complete') and research.is_complete()
            directive = build_planning_directive(prompt, phase, has_complete_research)
            if directive:
                messages.append(directive)

        # Output result
        result = {}
        if messages:
            result['systemMessage'] = '\n\n'.join(messages)

        print(json.dumps(result))

    except Exception as e:
        # Non-blocking error handling
        error_msg = {"systemMessage": f"[FIC] UserPromptSubmit hook error: {str(e)}"}
        print(json.dumps(error_msg))

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
