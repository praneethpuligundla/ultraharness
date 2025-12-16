#!/usr/bin/env python3
"""Context Intelligence Engine for FIC system.

Tracks what INFORMATION enters context (not just tool calls), classifies it,
detects redundancy, and estimates context utilization.

From ACE article: "The only thing affecting output quality is context window contents."
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class InformationClass(Enum):
    """Classification of information entering context."""
    ESSENTIAL = "essential"    # Core findings, decisions, blockers
    HELPFUL = "helpful"        # Supporting details, alternatives considered
    NOISE = "noise"            # Exploration dead-ends, verbose tool output


@dataclass
class ContextEntry:
    """A single entry of information in context."""
    id: str
    timestamp: str
    source: str  # e.g., "Read:/src/api.ts" or "Grep:pattern"
    classification: str
    summary: str
    content_hash: str  # For redundancy detection
    token_estimate: int
    metadata: Dict[str, Any]


@dataclass
class ContextState:
    """Current state of context intelligence tracking."""
    session_id: str
    entries: List[ContextEntry]
    total_token_estimate: int
    utilization_percent: float
    redundant_discoveries: List[str]
    prunable_items: List[str]
    last_updated: str


# Token estimation constants
TOKENS_PER_CHAR = 0.25  # Rough approximation
MAX_CONTEXT_TOKENS = 170000  # Approximate max context
TARGET_UTILIZATION_LOW = 0.40
TARGET_UTILIZATION_HIGH = 0.60


def get_state_path(work_dir: str = None) -> Path:
    """Get path to context state file."""
    if work_dir is None:
        work_dir = os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())
    return Path(work_dir) / '.claude' / 'fic-context-state.json'


def load_context_state(session_id: str, work_dir: str = None) -> ContextState:
    """Load context state from file or create new."""
    state_path = get_state_path(work_dir)

    if state_path.exists():
        try:
            with open(state_path, 'r') as f:
                data = json.load(f)
                # Check if same session
                if data.get('session_id') == session_id:
                    entries = [ContextEntry(**e) for e in data.get('entries', [])]
                    return ContextState(
                        session_id=data['session_id'],
                        entries=entries,
                        total_token_estimate=data.get('total_token_estimate', 0),
                        utilization_percent=data.get('utilization_percent', 0.0),
                        redundant_discoveries=data.get('redundant_discoveries', []),
                        prunable_items=data.get('prunable_items', []),
                        last_updated=data.get('last_updated', datetime.now().isoformat())
                    )
        except Exception:
            pass

    # New session or failed to load
    return ContextState(
        session_id=session_id,
        entries=[],
        total_token_estimate=0,
        utilization_percent=0.0,
        redundant_discoveries=[],
        prunable_items=[],
        last_updated=datetime.now().isoformat()
    )


def save_context_state(state: ContextState, work_dir: str = None) -> bool:
    """Save context state to file."""
    state_path = get_state_path(work_dir)
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'session_id': state.session_id,
            'entries': [asdict(e) for e in state.entries],
            'total_token_estimate': state.total_token_estimate,
            'utilization_percent': state.utilization_percent,
            'redundant_discoveries': state.redundant_discoveries,
            'prunable_items': state.prunable_items,
            'last_updated': datetime.now().isoformat()
        }

        with open(state_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def estimate_tokens(content: str) -> int:
    """Estimate token count from content."""
    return int(len(content) * TOKENS_PER_CHAR)


def hash_content(content: str) -> str:
    """Create hash of content for redundancy detection."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def classify_information(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: str
) -> Tuple[InformationClass, str, int]:
    """
    Classify information from a tool use.

    Returns:
        (classification, summary, token_estimate)
    """
    result_str = str(tool_result)
    token_estimate = estimate_tokens(result_str)

    # Classify based on tool type and result
    if tool_name == 'Read':
        file_path = tool_input.get('file_path', '')

        # Check if it's a config/important file
        important_patterns = ['config', 'settings', 'main', 'index', 'app', 'routes']
        is_important = any(p in file_path.lower() for p in important_patterns)

        if is_important:
            classification = InformationClass.ESSENTIAL
            summary = f"Read important file: {Path(file_path).name}"
        elif len(result_str) > 5000:
            classification = InformationClass.NOISE
            summary = f"Large file read: {Path(file_path).name} ({len(result_str)} chars)"
        else:
            classification = InformationClass.HELPFUL
            summary = f"Read file: {Path(file_path).name}"

    elif tool_name == 'Grep':
        pattern = tool_input.get('pattern', '')
        matches = result_str.count('\n') + 1 if result_str.strip() else 0

        if matches == 0:
            classification = InformationClass.NOISE
            summary = f"No matches for: {pattern[:30]}"
        elif matches <= 10:
            classification = InformationClass.ESSENTIAL
            summary = f"Found {matches} matches for: {pattern[:30]}"
        else:
            classification = InformationClass.HELPFUL
            summary = f"Found {matches} matches for: {pattern[:30]} (many results)"

    elif tool_name == 'Glob':
        pattern = tool_input.get('pattern', '')
        files = result_str.strip().split('\n') if result_str.strip() else []

        classification = InformationClass.HELPFUL
        summary = f"Found {len(files)} files matching: {pattern}"

    elif tool_name == 'Bash':
        command = tool_input.get('command', '')

        # Check for test commands
        if any(tc in command for tc in ['test', 'pytest', 'jest', 'cargo test']):
            if 'failed' in result_str.lower() or 'error' in result_str.lower():
                classification = InformationClass.ESSENTIAL
                summary = f"Test FAILED: {command[:40]}"
            else:
                classification = InformationClass.ESSENTIAL
                summary = f"Test PASSED: {command[:40]}"
        # Check for git commands
        elif command.startswith('git '):
            classification = InformationClass.HELPFUL
            summary = f"Git: {command[:40]}"
        # Check for exploration commands
        elif any(cmd in command for cmd in ['ls', 'find', 'tree', 'cat', 'head']):
            if len(result_str) > 2000:
                classification = InformationClass.NOISE
                summary = f"Large exploration output: {command[:30]}"
            else:
                classification = InformationClass.HELPFUL
                summary = f"Exploration: {command[:30]}"
        else:
            classification = InformationClass.HELPFUL
            summary = f"Command: {command[:40]}"

    elif tool_name == 'Task':
        description = tool_input.get('description', '')
        # Subagent results are always essential
        classification = InformationClass.ESSENTIAL
        summary = f"Subagent: {description}"

    else:
        classification = InformationClass.HELPFUL
        summary = f"{tool_name}: {str(tool_input)[:40]}"

    return classification, summary, token_estimate


def detect_redundancy(
    state: ContextState,
    content_hash: str,
    source: str
) -> Optional[str]:
    """
    Detect if this content was already discovered.

    Returns description of redundancy if found, None otherwise.
    """
    for entry in state.entries:
        if entry.content_hash == content_hash:
            return f"Same content as {entry.source} at {entry.timestamp[:10]}"

    # Check for same source accessed multiple times
    same_source = [e for e in state.entries if e.source == source]
    if len(same_source) >= 2:
        return f"Source {source} accessed {len(same_source) + 1} times"

    return None


def estimate_utilization(state: ContextState) -> float:
    """Estimate current context utilization."""
    return min(1.0, state.total_token_estimate / MAX_CONTEXT_TOKENS)


def identify_prunable(state: ContextState) -> List[str]:
    """Identify entries that could be safely pruned."""
    prunable = []

    for entry in state.entries:
        # Noise is always prunable
        if entry.classification == InformationClass.NOISE.value:
            prunable.append(f"[NOISE] {entry.summary}")
        # Old helpful entries with low token count
        elif entry.classification == InformationClass.HELPFUL.value:
            if entry.token_estimate < 100:
                prunable.append(f"[LOW-VALUE] {entry.summary}")

    return prunable


def add_context_entry(
    state: ContextState,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: str
) -> Tuple[ContextState, Optional[str]]:
    """
    Add a new context entry and return updated state.

    Returns:
        (updated_state, warning_message_if_any)
    """
    # Classify the information
    classification, summary, token_estimate = classify_information(
        tool_name, tool_input, tool_result
    )

    # Create content hash
    content_hash = hash_content(str(tool_result))

    # Build source identifier
    if tool_name == 'Read':
        source = f"Read:{tool_input.get('file_path', 'unknown')}"
    elif tool_name == 'Grep':
        source = f"Grep:{tool_input.get('pattern', 'unknown')}"
    elif tool_name == 'Glob':
        source = f"Glob:{tool_input.get('pattern', 'unknown')}"
    elif tool_name == 'Bash':
        source = f"Bash:{tool_input.get('command', 'unknown')[:30]}"
    else:
        source = f"{tool_name}:{str(tool_input)[:20]}"

    # Check for redundancy
    redundancy = detect_redundancy(state, content_hash, source)
    if redundancy:
        state.redundant_discoveries.append(redundancy)

    # Create entry
    entry = ContextEntry(
        id=f"{tool_name}-{datetime.now().strftime('%H%M%S')}",
        timestamp=datetime.now().isoformat(),
        source=source,
        classification=classification.value,
        summary=summary,
        content_hash=content_hash,
        token_estimate=token_estimate,
        metadata={'tool_name': tool_name}
    )

    # Add to state
    state.entries.append(entry)
    state.total_token_estimate += token_estimate
    state.utilization_percent = estimate_utilization(state)
    state.prunable_items = identify_prunable(state)
    state.last_updated = datetime.now().isoformat()

    # Keep entries bounded (last 100)
    if len(state.entries) > 100:
        # Remove oldest noise/helpful entries
        state.entries = [e for e in state.entries if e.classification == InformationClass.ESSENTIAL.value][-50:] + \
                       [e for e in state.entries if e.classification != InformationClass.ESSENTIAL.value][-50:]

    # Generate warning if needed
    warning = None
    if state.utilization_percent >= TARGET_UTILIZATION_HIGH:
        warning = f"Context utilization HIGH ({state.utilization_percent:.0%}). Consider compacting."
    elif redundancy:
        warning = f"Redundant discovery: {redundancy}"

    return state, warning


def get_context_summary(state: ContextState) -> str:
    """Get a human-readable summary of context state."""
    essential = len([e for e in state.entries if e.classification == InformationClass.ESSENTIAL.value])
    helpful = len([e for e in state.entries if e.classification == InformationClass.HELPFUL.value])
    noise = len([e for e in state.entries if e.classification == InformationClass.NOISE.value])

    lines = [
        f"Context Utilization: {state.utilization_percent:.0%}",
        f"Entries: {essential} essential, {helpful} helpful, {noise} noise",
        f"Estimated tokens: {state.total_token_estimate:,}",
    ]

    if state.redundant_discoveries:
        lines.append(f"Redundancies detected: {len(state.redundant_discoveries)}")

    if state.prunable_items:
        lines.append(f"Prunable items: {len(state.prunable_items)}")

    return '\n'.join(lines)


def extract_essential_context(state: ContextState) -> Dict[str, Any]:
    """Extract essential context for preservation across compaction."""
    essential_entries = [
        e for e in state.entries
        if e.classification == InformationClass.ESSENTIAL.value
    ]

    return {
        'essential_discoveries': [
            {'source': e.source, 'summary': e.summary, 'timestamp': e.timestamp}
            for e in essential_entries[-10:]  # Last 10 essential entries
        ],
        'token_estimate': state.total_token_estimate,
        'utilization_at_extraction': state.utilization_percent
    }
