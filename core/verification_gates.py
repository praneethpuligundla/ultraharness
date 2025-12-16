#!/usr/bin/env python3
"""Verification Gates for FIC system.

Enforces quality checkpoints. Blocks progression when verification fails.

Gates:
- RESEARCH_TO_PLANNING: Research confidence >= 0.7, no blocking questions
- PLANNING_TO_IMPLEMENTATION: Plan validation == PROCEED
- IMPLEMENTATION_TO_COMMIT: All tests passing
"""

import os
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

# Try to import artifacts module
try:
    from core.artifacts import (
        ArtifactType, get_latest_artifact, load_artifact,
        ResearchArtifact, PlanArtifact, ImplementationArtifact,
        ValidationRecommendation
    )
    ARTIFACTS_AVAILABLE = True
except ImportError:
    ARTIFACTS_AVAILABLE = False

# Try to import config
try:
    from core.config import load_config, is_strict_mode, is_relaxed_mode
except ImportError:
    def load_config(work_dir=None):
        return {"fic_strict_gates": True}
    def is_strict_mode(work_dir=None):
        return False
    def is_relaxed_mode(work_dir=None):
        return False


class Gate(Enum):
    """Verification gates in the FIC workflow."""
    RESEARCH_TO_PLANNING = "research_to_planning"
    PLANNING_TO_IMPLEMENTATION = "planning_to_implementation"
    IMPLEMENTATION_TO_COMMIT = "implementation_to_commit"
    ALLOW_EDIT = "allow_edit"
    ALLOW_WRITE = "allow_write"


class GateAction(Enum):
    """Actions a gate can take."""
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class GateResult:
    """Result of a gate check."""
    action: GateAction
    gate: Gate
    reason: str
    suggestions: list
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'action': self.action.value,
            'gate': self.gate.value,
            'reason': self.reason,
            'suggestions': self.suggestions,
            'details': self.details
        }


def check_research_gate(work_dir: str = None) -> GateResult:
    """
    Check if research is complete enough to proceed to planning.

    Criteria:
    - Confidence score >= 0.7
    - No blocking open questions
    - At least some discoveries made
    """
    if not ARTIFACTS_AVAILABLE:
        return GateResult(
            action=GateAction.ALLOW,
            gate=Gate.RESEARCH_TO_PLANNING,
            reason="Artifacts module not available",
            suggestions=[],
            details={}
        )

    research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)

    if not research:
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.RESEARCH_TO_PLANNING,
            reason="No research artifact found. Starting from scratch.",
            suggestions=[
                "Consider creating a research artifact to track findings",
                "Use the @fic-researcher subagent for systematic exploration"
            ],
            details={'has_research': False}
        )

    # Get research status
    status = research.get_completion_status() if hasattr(research, 'get_completion_status') else {}
    confidence = getattr(research, 'confidence_score', 0)
    open_questions = getattr(research, 'open_questions', [])
    blocking_questions = [q for q in open_questions if getattr(q, 'blocking', False)]
    discoveries = getattr(research, 'discoveries', [])

    details = {
        'confidence_score': confidence,
        'open_questions': len(open_questions),
        'blocking_questions': len(blocking_questions),
        'discoveries': len(discoveries),
        'is_complete': research.is_complete() if hasattr(research, 'is_complete') else False
    }

    # Check gate conditions
    if confidence < 0.7:
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.RESEARCH_TO_PLANNING,
            reason=f"Research confidence ({confidence:.0%}) below threshold (70%)",
            suggestions=[
                "Continue exploration to build confidence",
                "Address unknown areas in the codebase",
                "Use @fic-researcher for systematic research"
            ],
            details=details
        )

    if blocking_questions:
        blocking_text = [getattr(q, 'question', str(q)) for q in blocking_questions[:3]]
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.RESEARCH_TO_PLANNING,
            reason=f"{len(blocking_questions)} blocking question(s) remain",
            suggestions=[
                "Resolve blocking questions before planning",
                f"Questions: {', '.join(blocking_text)}"
            ],
            details=details
        )

    if len(discoveries) == 0:
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.RESEARCH_TO_PLANNING,
            reason="No discoveries recorded in research",
            suggestions=[
                "Document key findings from exploration",
                "Record relevant files and patterns discovered"
            ],
            details=details
        )

    # Gate passed
    return GateResult(
        action=GateAction.ALLOW,
        gate=Gate.RESEARCH_TO_PLANNING,
        reason="Research complete. Ready for planning.",
        suggestions=[],
        details=details
    )


def check_planning_gate(work_dir: str = None) -> GateResult:
    """
    Check if plan is validated and ready for implementation.

    Criteria:
    - Plan validation result == PROCEED
    - All steps are specific/actionable
    - Success criteria defined
    """
    if not ARTIFACTS_AVAILABLE:
        return GateResult(
            action=GateAction.ALLOW,
            gate=Gate.PLANNING_TO_IMPLEMENTATION,
            reason="Artifacts module not available",
            suggestions=[],
            details={}
        )

    plan = get_latest_artifact(ArtifactType.PLAN, work_dir)

    if not plan:
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.PLANNING_TO_IMPLEMENTATION,
            reason="No plan artifact found.",
            suggestions=[
                "Create an implementation plan before coding",
                "Define specific steps with verification criteria"
            ],
            details={'has_plan': False}
        )

    # Get plan status
    status = plan.get_actionability_status() if hasattr(plan, 'get_actionability_status') else {}
    validation = getattr(plan, 'validation_result', None)
    steps = getattr(plan, 'steps', [])
    specific_steps = [s for s in steps if getattr(s, 'is_specific', False)]
    success_criteria = getattr(plan, 'success_criteria', [])

    details = {
        'has_validation': validation is not None,
        'recommendation': getattr(validation, 'recommendation', None) if validation else None,
        'total_steps': len(steps),
        'specific_steps': len(specific_steps),
        'success_criteria': len(success_criteria),
        'is_actionable': plan.is_actionable() if hasattr(plan, 'is_actionable') else False
    }

    # Check for validation
    if not validation:
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.PLANNING_TO_IMPLEMENTATION,
            reason="Plan has not been validated",
            suggestions=[
                "Run plan validation before implementation",
                "Use @fic-plan-validator to review the plan"
            ],
            details=details
        )

    # Check validation result
    recommendation = getattr(validation, 'recommendation', '')
    if recommendation == ValidationRecommendation.BLOCK.value:
        return GateResult(
            action=GateAction.BLOCK,
            gate=Gate.PLANNING_TO_IMPLEMENTATION,
            reason="Plan validation BLOCKED. Plan needs major revision.",
            suggestions=[
                "Review validation feedback",
                "Address critical issues before proceeding"
            ],
            details=details
        )

    if recommendation == ValidationRecommendation.REVISE.value:
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.PLANNING_TO_IMPLEMENTATION,
            reason="Plan needs revision before implementation",
            suggestions=[
                "Address feedback from validation",
                "Re-validate after making changes"
            ],
            details=details
        )

    # Check step specificity
    if len(steps) > 0 and len(specific_steps) < len(steps) * 0.8:
        vague_count = len(steps) - len(specific_steps)
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.PLANNING_TO_IMPLEMENTATION,
            reason=f"{vague_count} step(s) are too vague to implement",
            suggestions=[
                "Make steps more specific and actionable",
                "Add file paths, function names, and exact changes"
            ],
            details=details
        )

    # Gate passed
    return GateResult(
        action=GateAction.ALLOW,
        gate=Gate.PLANNING_TO_IMPLEMENTATION,
        reason="Plan validated. Ready for implementation.",
        suggestions=[],
        details=details
    )


def check_edit_gate(
    file_path: str,
    work_dir: str = None
) -> GateResult:
    """
    Check if edit operation should be allowed based on current phase.

    In strict mode:
    - RESEARCH phase: Block edits (except to artifacts)
    - PLANNING phase: Block edits (except to plans)
    - IMPLEMENTATION phase: Allow edits
    """
    config = load_config(work_dir)

    # Check if strict gates are enabled
    if not config.get('fic_strict_gates', True):
        return GateResult(
            action=GateAction.ALLOW,
            gate=Gate.ALLOW_EDIT,
            reason="Strict gates disabled",
            suggestions=[],
            details={}
        )

    # In relaxed mode, always allow
    if is_relaxed_mode(work_dir):
        return GateResult(
            action=GateAction.ALLOW,
            gate=Gate.ALLOW_EDIT,
            reason="Relaxed mode",
            suggestions=[],
            details={}
        )

    # Allow edits to FIC artifacts and config
    fic_paths = ['.claude/', 'claude-progress.txt', 'claude-features.json']
    if any(fp in file_path for fp in fic_paths):
        return GateResult(
            action=GateAction.ALLOW,
            gate=Gate.ALLOW_EDIT,
            reason="FIC artifact edit",
            suggestions=[],
            details={'is_fic_file': True}
        )

    # Determine current phase
    if not ARTIFACTS_AVAILABLE:
        return GateResult(
            action=GateAction.ALLOW,
            gate=Gate.ALLOW_EDIT,
            reason="Cannot determine phase",
            suggestions=[],
            details={}
        )

    impl = get_latest_artifact(ArtifactType.IMPLEMENTATION, work_dir)
    plan = get_latest_artifact(ArtifactType.PLAN, work_dir)
    research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)

    # Determine phase
    if impl:
        phase = 'IMPLEMENTATION'
    elif plan and hasattr(plan, 'is_actionable') and plan.is_actionable():
        phase = 'IMPLEMENTATION_READY'
    elif plan:
        phase = 'PLANNING'
    elif research:
        phase = 'RESEARCH'
    else:
        phase = 'NEW_SESSION'

    details = {'phase': phase, 'file': file_path}

    # Phase-specific gate logic (strict mode only)
    if is_strict_mode(work_dir):
        if phase in ('RESEARCH', 'NEW_SESSION'):
            return GateResult(
                action=GateAction.BLOCK,
                gate=Gate.ALLOW_EDIT,
                reason=f"In {phase} phase. Complete research before editing code.",
                suggestions=[
                    "Finish codebase exploration first",
                    "Build research confidence to >= 70%",
                    "Use /harness:configure relaxed to override"
                ],
                details=details
            )

        if phase == 'PLANNING':
            return GateResult(
                action=GateAction.BLOCK,
                gate=Gate.ALLOW_EDIT,
                reason="In PLANNING phase. Validate plan before implementation.",
                suggestions=[
                    "Validate your plan first",
                    "Use @fic-plan-validator",
                    "Use /harness:configure relaxed to override"
                ],
                details=details
            )

    # Standard mode: warn but don't block
    if phase in ('RESEARCH', 'NEW_SESSION'):
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.ALLOW_EDIT,
            reason=f"Editing in {phase} phase. Consider completing research first.",
            suggestions=["Build confidence before making changes"],
            details=details
        )

    if phase == 'PLANNING':
        return GateResult(
            action=GateAction.WARN,
            gate=Gate.ALLOW_EDIT,
            reason="Editing in PLANNING phase. Consider validating plan first.",
            suggestions=["Validate plan before implementation"],
            details=details
        )

    # Implementation phase - allow
    return GateResult(
        action=GateAction.ALLOW,
        gate=Gate.ALLOW_EDIT,
        reason="Implementation phase. Edit allowed.",
        suggestions=[],
        details=details
    )


def check_gate(
    gate: Gate,
    work_dir: str = None,
    **kwargs
) -> GateResult:
    """
    Main entry point for gate checking.

    Args:
        gate: The gate to check
        work_dir: Working directory
        **kwargs: Gate-specific parameters

    Returns:
        GateResult with action, reason, and suggestions
    """
    if gate == Gate.RESEARCH_TO_PLANNING:
        return check_research_gate(work_dir)
    elif gate == Gate.PLANNING_TO_IMPLEMENTATION:
        return check_planning_gate(work_dir)
    elif gate == Gate.ALLOW_EDIT:
        file_path = kwargs.get('file_path', '')
        return check_edit_gate(file_path, work_dir)
    elif gate == Gate.ALLOW_WRITE:
        file_path = kwargs.get('file_path', '')
        return check_edit_gate(file_path, work_dir)  # Same logic as edit
    else:
        return GateResult(
            action=GateAction.ALLOW,
            gate=gate,
            reason="Unknown gate",
            suggestions=[],
            details={}
        )


def format_gate_message(result: GateResult) -> str:
    """Format a gate result for display."""
    lines = []

    if result.action == GateAction.BLOCK:
        lines.append(f"[FIC GATE BLOCKED] {result.reason}")
    elif result.action == GateAction.WARN:
        lines.append(f"[FIC GATE WARNING] {result.reason}")
    else:
        return ""  # No message for ALLOW

    if result.suggestions:
        lines.append("Suggestions:")
        for suggestion in result.suggestions:
            lines.append(f"  - {suggestion}")

    return '\n'.join(lines)
