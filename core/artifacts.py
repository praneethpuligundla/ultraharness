#!/usr/bin/env python3
"""Artifact definitions for FIC system.

Each phase PRODUCES a structured artifact that INPUTS to the next phase.
Artifacts are verification gates - they must meet criteria before proceeding.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class ArtifactType(Enum):
    RESEARCH = "research"
    PLAN = "plan"
    IMPLEMENTATION = "implementation"


class ValidationRecommendation(Enum):
    PROCEED = "proceed"
    REVISE = "revise"
    BLOCK = "block"


@dataclass
class Discovery:
    """A single discovery from research."""
    description: str
    confidence: float  # 0-1
    source_files: List[str]
    category: str  # e.g., "architecture", "pattern", "dependency"


@dataclass
class FileReference:
    """Reference to a relevant file."""
    path: str
    purpose: str
    relevance: float  # 0-1


@dataclass
class OpenQuestion:
    """An unresolved question from research."""
    question: str
    priority: str  # "high", "medium", "low"
    blocking: bool  # Whether this blocks proceeding


@dataclass
class PlanStep:
    """A single step in an implementation plan."""
    id: str
    description: str
    files_affected: List[str]
    dependencies: List[str]  # IDs of steps that must complete first
    verification: str  # How to verify this step is done
    is_specific: bool  # Whether step is actionable


@dataclass
class SuccessCriterion:
    """A criterion for plan success."""
    description: str
    verification_method: str
    status: str  # "pending", "met", "failed"


@dataclass
class RiskMitigation:
    """A risk and its mitigation strategy."""
    risk: str
    likelihood: str  # "high", "medium", "low"
    mitigation: str


@dataclass
class ValidationResult:
    """Result of plan validation."""
    recommendation: str  # ValidationRecommendation value
    completeness_score: float  # 0-10
    coverage_analysis: Dict[str, str]  # requirement -> COVERED|MISSING|PARTIAL
    missing_steps: List[str]
    risks_identified: List[str]


@dataclass
class PlanDeviation:
    """A deviation from the plan during implementation."""
    step_id: str
    description: str
    reason: str
    timestamp: str


@dataclass
class ResearchArtifact:
    """Output of research phase, input to planning phase."""
    id: str
    created_at: str
    updated_at: str
    feature_or_task: str

    # What was learned
    discoveries: List[Discovery]
    relevant_files: List[FileReference]
    patterns_identified: List[str]

    # Verification criteria
    requirements_addressed: Dict[str, str]  # requirement -> coverage status
    open_questions: List[OpenQuestion]

    # Metadata
    research_sessions: int
    confidence_score: float  # 0-1

    def is_complete(self) -> bool:
        """Check if research is sufficient for planning."""
        blocking_questions = [q for q in self.open_questions if q.blocking]
        return (
            self.confidence_score >= 0.7 and
            len(blocking_questions) == 0 and
            len(self.open_questions) <= 2
        )

    def get_completion_status(self) -> Dict[str, Any]:
        """Get detailed completion status."""
        blocking = [q for q in self.open_questions if q.blocking]
        return {
            'is_complete': self.is_complete(),
            'confidence_score': self.confidence_score,
            'open_questions': len(self.open_questions),
            'blocking_questions': len(blocking),
            'discoveries': len(self.discoveries),
            'files_identified': len(self.relevant_files)
        }


@dataclass
class PlanArtifact:
    """Output of planning phase, input to implementation phase."""
    id: str
    created_at: str
    updated_at: str
    research_artifact_id: str  # Links to research

    # The plan
    goal: str
    approach: str
    steps: List[PlanStep]
    success_criteria: List[SuccessCriterion]
    risk_mitigations: List[RiskMitigation]

    # Implementation guidance
    file_order: List[str]  # Which files to modify in order
    test_strategy: str

    # Verification
    validation_result: Optional[ValidationResult] = None

    def is_actionable(self) -> bool:
        """Check if plan is ready for implementation."""
        if self.validation_result is None:
            return False
        return (
            self.validation_result.recommendation == ValidationRecommendation.PROCEED.value and
            all(step.is_specific for step in self.steps)
        )

    def get_actionability_status(self) -> Dict[str, Any]:
        """Get detailed actionability status."""
        specific_steps = [s for s in self.steps if s.is_specific]
        return {
            'is_actionable': self.is_actionable(),
            'has_validation': self.validation_result is not None,
            'recommendation': self.validation_result.recommendation if self.validation_result else None,
            'total_steps': len(self.steps),
            'specific_steps': len(specific_steps),
            'success_criteria': len(self.success_criteria)
        }


@dataclass
class ImplementationArtifact:
    """Tracks implementation progress against plan."""
    id: str
    created_at: str
    updated_at: str
    plan_artifact_id: str

    # Progress
    steps_completed: List[str]  # IDs of completed plan steps
    steps_in_progress: List[str]
    files_modified: List[str]
    tests_run: bool
    tests_passed: bool

    # Deviations
    plan_deviations: List[PlanDeviation]

    def get_progress(self, plan: PlanArtifact) -> Dict[str, Any]:
        """Get implementation progress."""
        total_steps = len(plan.steps)
        completed = len(self.steps_completed)
        return {
            'total_steps': total_steps,
            'completed_steps': completed,
            'progress_percent': (completed / total_steps * 100) if total_steps > 0 else 0,
            'in_progress': len(self.steps_in_progress),
            'deviations': len(self.plan_deviations),
            'tests_status': 'passed' if self.tests_passed else ('failed' if self.tests_run else 'not_run')
        }


# Artifact storage functions

def get_artifacts_dir(work_dir: str = None) -> Path:
    """Get path to artifacts directory."""
    if work_dir is None:
        work_dir = os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())
    return Path(work_dir) / '.claude' / 'fic-artifacts'


def get_artifact_path(artifact_type: ArtifactType, artifact_id: str, work_dir: str = None) -> Path:
    """Get path to a specific artifact file."""
    base = get_artifacts_dir(work_dir)
    return base / artifact_type.value / f"{artifact_id}.json"


def save_artifact(artifact: Any, artifact_type: ArtifactType, work_dir: str = None) -> bool:
    """Save an artifact to disk."""
    try:
        path = get_artifact_path(artifact_type, artifact.id, work_dir)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(asdict(artifact), f, indent=2, default=str)
        return True
    except Exception:
        return False


def load_artifact(artifact_type: ArtifactType, artifact_id: str, work_dir: str = None) -> Optional[Any]:
    """Load an artifact from disk."""
    path = get_artifact_path(artifact_type, artifact_id, work_dir)
    if not path.exists():
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        if artifact_type == ArtifactType.RESEARCH:
            data['discoveries'] = [Discovery(**d) for d in data.get('discoveries', [])]
            data['relevant_files'] = [FileReference(**f) for f in data.get('relevant_files', [])]
            data['open_questions'] = [OpenQuestion(**q) for q in data.get('open_questions', [])]
            return ResearchArtifact(**data)

        elif artifact_type == ArtifactType.PLAN:
            data['steps'] = [PlanStep(**s) for s in data.get('steps', [])]
            data['success_criteria'] = [SuccessCriterion(**c) for c in data.get('success_criteria', [])]
            data['risk_mitigations'] = [RiskMitigation(**r) for r in data.get('risk_mitigations', [])]
            if data.get('validation_result'):
                data['validation_result'] = ValidationResult(**data['validation_result'])
            return PlanArtifact(**data)

        elif artifact_type == ArtifactType.IMPLEMENTATION:
            data['plan_deviations'] = [PlanDeviation(**d) for d in data.get('plan_deviations', [])]
            return ImplementationArtifact(**data)

    except Exception:
        return None


def list_artifacts(artifact_type: ArtifactType, work_dir: str = None) -> List[str]:
    """List all artifact IDs of a given type."""
    base = get_artifacts_dir(work_dir) / artifact_type.value
    if not base.exists():
        return []

    return [f.stem for f in base.glob('*.json')]


def get_latest_artifact(artifact_type: ArtifactType, work_dir: str = None) -> Optional[Any]:
    """Get the most recently created artifact of a type."""
    base = get_artifacts_dir(work_dir) / artifact_type.value
    if not base.exists():
        return []

    files = sorted(base.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None

    artifact_id = files[0].stem
    return load_artifact(artifact_type, artifact_id, work_dir)


def create_research_artifact(
    feature_or_task: str,
    work_dir: str = None
) -> ResearchArtifact:
    """Create a new research artifact."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact_id = f"{timestamp}-{feature_or_task.lower().replace(' ', '-')[:30]}"

    artifact = ResearchArtifact(
        id=artifact_id,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        feature_or_task=feature_or_task,
        discoveries=[],
        relevant_files=[],
        patterns_identified=[],
        requirements_addressed={},
        open_questions=[],
        research_sessions=1,
        confidence_score=0.0
    )

    save_artifact(artifact, ArtifactType.RESEARCH, work_dir)
    return artifact


def create_plan_artifact(
    research_artifact_id: str,
    goal: str,
    approach: str,
    work_dir: str = None
) -> PlanArtifact:
    """Create a new plan artifact."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact_id = f"{timestamp}-plan"

    artifact = PlanArtifact(
        id=artifact_id,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        research_artifact_id=research_artifact_id,
        goal=goal,
        approach=approach,
        steps=[],
        success_criteria=[],
        risk_mitigations=[],
        file_order=[],
        test_strategy="",
        validation_result=None
    )

    save_artifact(artifact, ArtifactType.PLAN, work_dir)
    return artifact


def create_implementation_artifact(
    plan_artifact_id: str,
    work_dir: str = None
) -> ImplementationArtifact:
    """Create a new implementation artifact."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact_id = f"{timestamp}-impl"

    artifact = ImplementationArtifact(
        id=artifact_id,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        plan_artifact_id=plan_artifact_id,
        steps_completed=[],
        steps_in_progress=[],
        files_modified=[],
        tests_run=False,
        tests_passed=False,
        plan_deviations=[]
    )

    save_artifact(artifact, ArtifactType.IMPLEMENTATION, work_dir)
    return artifact
