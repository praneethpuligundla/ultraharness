#!/usr/bin/env python3
"""SubagentStop hook for processing research subagent results.

This hook runs when a subagent completes and:
1. Detects if it was a FIC research subagent
2. Extracts structured findings from the output
3. Updates research artifacts
4. Injects only essential findings into main context
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
    from core.config import load_config, is_harness_initialized
except ImportError:
    def load_config(work_dir=None):
        return {"fic_enabled": True}
    def is_harness_initialized(work_dir=None):
        return False

try:
    from core.artifacts import (
        ArtifactType, get_latest_artifact, save_artifact,
        create_research_artifact, ResearchArtifact,
        Discovery, FileReference, OpenQuestion
    )
    ARTIFACTS_AVAILABLE = True
except ImportError:
    ARTIFACTS_AVAILABLE = False
    class ArtifactType:
        RESEARCH = "research"
    def get_latest_artifact(artifact_type, work_dir=None):
        return None
    def save_artifact(artifact, artifact_type, work_dir=None):
        return False
    def create_research_artifact(feature, work_dir=None):
        return None


def is_research_subagent(subagent_type: str, description: str) -> bool:
    """Detect if this was a FIC research subagent."""
    research_indicators = [
        'fic-researcher',
        'research',
        'explore',
        'investigation',
        'analysis',
        'exploration'
    ]

    subagent_lower = (subagent_type or '').lower()
    desc_lower = (description or '').lower()

    for indicator in research_indicators:
        if indicator in subagent_lower or indicator in desc_lower:
            return True

    return False


def is_plan_validator(subagent_type: str, description: str) -> bool:
    """Detect if this was a FIC plan validator subagent."""
    validator_indicators = [
        'fic-plan-validator',
        'plan-validator',
        'validation',
        'validate plan'
    ]

    subagent_lower = (subagent_type or '').lower()
    desc_lower = (description or '').lower()

    for indicator in validator_indicators:
        if indicator in subagent_lower or indicator in desc_lower:
            return True

    return False


def extract_confidence_score(output: str) -> float:
    """Extract confidence score from research output."""
    # Look for patterns like "Confidence Score: 0.8" or "Confidence: 80%"
    patterns = [
        r'confidence\s*(?:score)?[:\s]+(\d+\.?\d*)%?',
        r'confidence[:\s]+(\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, output.lower())
        if match:
            value = float(match.group(1))
            # Normalize to 0-1 range
            if value > 1:
                value = value / 100
            return min(1.0, max(0.0, value))

    return 0.5  # Default confidence


def extract_discoveries(output: str) -> list:
    """Extract key discoveries from research output."""
    discoveries = []

    # Look for discoveries section
    discovery_pattern = r'(?:key\s+)?discover(?:y|ies)[:\s]*\n((?:[-*\d.]+\s+.+\n?)+)'
    match = re.search(discovery_pattern, output.lower())

    if match:
        lines = match.group(1).strip().split('\n')
        for line in lines[:10]:  # Limit to 10 discoveries
            # Clean up the line
            line = re.sub(r'^[-*\d.]+\s*', '', line.strip())
            if line and len(line) > 10:
                discoveries.append(line[:200])  # Truncate long discoveries

    return discoveries


def extract_relevant_files(output: str) -> list:
    """Extract relevant file references from output."""
    files = []

    # Look for file paths
    file_pattern = r'(?:relevant\s+)?files?[:\s]*\n((?:[-*]\s+.+\n?)+)'
    match = re.search(file_pattern, output.lower())

    if match:
        lines = match.group(1).strip().split('\n')
        for line in lines[:15]:  # Limit to 15 files
            # Extract path (look for common path patterns)
            path_match = re.search(r'([\w./\-_]+\.\w+)', line)
            if path_match:
                files.append(path_match.group(1))

    return files


def extract_open_questions(output: str) -> list:
    """Extract open questions from output."""
    questions = []

    # Look for questions section
    question_pattern = r'(?:open\s+)?questions?[:\s]*\n((?:[-*\d.]+\s+.+\??\n?)+)'
    match = re.search(question_pattern, output.lower())

    if match:
        lines = match.group(1).strip().split('\n')
        for line in lines[:5]:  # Limit to 5 questions
            line = re.sub(r'^[-*\d.]+\s*', '', line.strip())
            if line and len(line) > 10:
                # Check if marked as blocking
                is_blocking = '[blocking]' in line.lower()
                line = re.sub(r'\[blocking\]', '', line, flags=re.IGNORECASE).strip()
                questions.append({
                    'question': line[:200],
                    'blocking': is_blocking
                })

    return questions


def extract_recommendation(output: str) -> str:
    """Extract recommendation from plan validator output."""
    # Look for PROCEED, REVISE, or BLOCK
    if re.search(r'\bPROCEED\b', output, re.IGNORECASE):
        return 'PROCEED'
    elif re.search(r'\bBLOCK\b', output, re.IGNORECASE):
        return 'BLOCK'
    elif re.search(r'\bREVISE\b', output, re.IGNORECASE):
        return 'REVISE'
    return 'UNKNOWN'


def format_research_summary(
    confidence: float,
    discoveries: list,
    files: list,
    questions: list
) -> str:
    """Format a concise research summary for main context."""
    lines = []

    lines.append("=" * 40)
    lines.append("RESEARCH SUBAGENT RESULTS")
    lines.append("=" * 40)
    lines.append(f"Confidence: {confidence:.0%}")

    if discoveries:
        lines.append("")
        lines.append(f"Key Discoveries ({len(discoveries)}):")
        for disc in discoveries[:5]:
            lines.append(f"  - {disc[:80]}...")

    if files:
        lines.append("")
        lines.append(f"Relevant Files ({len(files)}):")
        for f in files[:5]:
            lines.append(f"  - {f}")

    if questions:
        blocking = [q for q in questions if q.get('blocking')]
        lines.append("")
        lines.append(f"Open Questions: {len(questions)} ({len(blocking)} blocking)")
        for q in questions[:3]:
            prefix = "[BLOCKING] " if q.get('blocking') else ""
            lines.append(f"  - {prefix}{q['question'][:60]}...")

    lines.append("=" * 40)

    return '\n'.join(lines)


def format_validation_summary(recommendation: str, output: str) -> str:
    """Format plan validation summary for main context."""
    lines = []

    lines.append("=" * 40)
    lines.append("PLAN VALIDATION RESULTS")
    lines.append("=" * 40)
    lines.append(f"Recommendation: {recommendation}")

    # Extract overall score if present
    score_match = re.search(r'overall\s+score[:\s]+(\d+)/10', output.lower())
    if score_match:
        lines.append(f"Overall Score: {score_match.group(1)}/10")

    # Extract critical issues
    issues_match = re.search(r'\[CRITICAL\]\s+(.+?)(?:\n|$)', output, re.IGNORECASE)
    if issues_match:
        lines.append("")
        lines.append(f"Critical Issue: {issues_match.group(1)[:100]}")

    lines.append("=" * 40)

    return '\n'.join(lines)


def main():
    """Main entry point for SubagentStop hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        subagent_type = input_data.get('subagent_type', '')
        description = input_data.get('description', '')
        output = input_data.get('output', '')
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

        messages = []

        # Check if this was a research subagent
        if is_research_subagent(subagent_type, description):
            # Extract structured information
            confidence = extract_confidence_score(output)
            discoveries = extract_discoveries(output)
            files = extract_relevant_files(output)
            questions = extract_open_questions(output)

            # Update research artifact if available
            if ARTIFACTS_AVAILABLE:
                research = get_latest_artifact(ArtifactType.RESEARCH, work_dir)
                if research:
                    # Update confidence
                    research.confidence_score = max(research.confidence_score, confidence)
                    research.research_sessions += 1
                    research.updated_at = datetime.now().isoformat()

                    # Note: Full artifact updates would require more complex merging
                    # For now, just update confidence and session count
                    save_artifact(research, ArtifactType.RESEARCH, work_dir)

            # Format summary for main context
            summary = format_research_summary(confidence, discoveries, files, questions)
            messages.append(summary)

            # Add guidance based on confidence
            if confidence >= 0.7:
                messages.append("")
                messages.append("[FIC] Research confidence threshold met. Ready for PLANNING phase.")
            else:
                messages.append("")
                messages.append(f"[FIC] Research confidence at {confidence:.0%}. Continue to build understanding.")

        # Check if this was a plan validator
        elif is_plan_validator(subagent_type, description):
            recommendation = extract_recommendation(output)
            summary = format_validation_summary(recommendation, output)
            messages.append(summary)

            if recommendation == 'PROCEED':
                messages.append("")
                messages.append("[FIC] Plan validated. Ready for IMPLEMENTATION phase.")
            elif recommendation == 'BLOCK':
                messages.append("")
                messages.append("[FIC] Plan validation BLOCKED. Major revision required.")
            elif recommendation == 'REVISE':
                messages.append("")
                messages.append("[FIC] Plan needs revision. Address feedback before implementation.")

        # Output result
        result = {}
        if messages:
            result['systemMessage'] = '\n'.join(messages)

        print(json.dumps(result))

    except Exception as e:
        # Non-blocking error handling
        error_msg = {"systemMessage": f"[FIC] SubagentStop hook error: {str(e)}"}
        print(json.dumps(error_msg))

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
