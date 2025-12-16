#!/usr/bin/env python3
"""Smart change detection for determining when to auto-log and checkpoint.

Classifies changes into:
- trivial: Comments, formatting, imports only
- significant: Logic changes, new functions, bug fixes
- major: New files, large refactors, feature completions
"""

import re
from typing import Dict, Any, Tuple
from enum import Enum
from pathlib import Path


class ChangeLevel(Enum):
    TRIVIAL = "trivial"
    SIGNIFICANT = "significant"
    MAJOR = "major"


# Patterns that indicate trivial changes (comments, whitespace, imports)
TRIVIAL_PATTERNS = [
    r'^\s*#.*$',              # Python comments
    r'^\s*//.*$',             # JS/C++ line comments
    r'^\s*/\*.*\*/\s*$',      # Single-line block comments
    r'^\s*\*.*$',             # Block comment continuation
    r'^\s*import\s+',         # Import statements
    r'^\s*from\s+.*import',   # From imports
    r'^\s*$',                 # Empty lines
    r'^\s*""".*"""$',         # Single-line docstrings
    r"^\s*'''.*'''$",         # Single-line docstrings
    r'^\s*export\s+',         # JS exports
    r'^\s*require\(',         # CommonJS require
]

# Patterns that indicate significant changes
SIGNIFICANT_PATTERNS = [
    r'\bdef\s+\w+\s*\(',      # Python function definition
    r'\bclass\s+\w+',         # Class definition
    r'\bfunction\s+\w+\s*\(', # JS function definition
    r'\bconst\s+\w+\s*=\s*\(.*\)\s*=>', # Arrow functions
    r'\bif\s+.*[:{]',         # Conditional logic
    r'\bfor\s+.*[:{]',        # For loops
    r'\bwhile\s+.*[:{]',      # While loops
    r'\btry\s*[:{]',          # Try blocks
    r'\bcatch\s*\(',          # Catch blocks
    r'\breturn\s+',           # Return statements
    r'\braise\s+',            # Python exceptions
    r'\bthrow\s+',            # JS exceptions
    r'\basync\s+',            # Async functions
    r'\bawait\s+',            # Await expressions
]

# File extensions that indicate code files
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.rs', '.go',
    '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb',
    '.swift', '.kt', '.scala', '.php', '.vue', '.svelte'
}

# Test-related patterns in commands
TEST_COMMAND_PATTERNS = [
    r'\bnpm\s+test\b',
    r'\bpytest\b',
    r'\bcargo\s+test\b',
    r'\bgo\s+test\b',
    r'\bjest\b',
    r'\bmocha\b',
    r'\bvitest\b',
    r'\bunittest\b',
    r'\bmvn\s+test\b',
    r'\bgradle\s+test\b',
]

# Build-related patterns in commands
BUILD_COMMAND_PATTERNS = [
    r'\bnpm\s+run\s+build\b',
    r'\bcargo\s+build\b',
    r'\bgo\s+build\b',
    r'\bmvn\s+package\b',
    r'\bgradle\s+build\b',
    r'\bmake\b',
    r'\btsc\b',
]


def is_code_file(file_path: str) -> bool:
    """Check if file is a code file based on extension."""
    return Path(file_path).suffix.lower() in CODE_EXTENSIONS


def count_non_trivial_lines(content: str) -> int:
    """Count lines that aren't trivial (comments, whitespace, imports)."""
    lines = content.split('\n')
    count = 0
    for line in lines:
        is_trivial = False
        for pattern in TRIVIAL_PATTERNS:
            if re.match(pattern, line):
                is_trivial = True
                break
        if not is_trivial and line.strip():
            count += 1
    return count


def has_significant_patterns(content: str) -> bool:
    """Check if content contains significant code patterns."""
    for pattern in SIGNIFICANT_PATTERNS:
        if re.search(pattern, content):
            return True
    return False


def classify_write(tool_input: Dict[str, Any]) -> Tuple[ChangeLevel, str]:
    """Classify a Write tool use."""
    file_path = tool_input.get('file_path', '')
    content = tool_input.get('content', '')

    total_lines = len(content.split('\n'))
    non_trivial_lines = count_non_trivial_lines(content)

    # Check if it's a code file
    if not is_code_file(file_path):
        if total_lines > 200:
            return ChangeLevel.MAJOR, f"Large non-code file ({total_lines} lines)"
        elif total_lines > 50:
            return ChangeLevel.SIGNIFICANT, f"New file ({total_lines} lines)"
        return ChangeLevel.TRIVIAL, f"Small file ({total_lines} lines)"

    # Code file classification
    if non_trivial_lines > 100:
        return ChangeLevel.MAJOR, f"Large code file ({non_trivial_lines} code lines)"
    elif non_trivial_lines > 30 or has_significant_patterns(content):
        return ChangeLevel.SIGNIFICANT, f"New code file ({non_trivial_lines} code lines)"
    else:
        return ChangeLevel.TRIVIAL, f"Small code file ({non_trivial_lines} code lines)"


def classify_edit(tool_input: Dict[str, Any]) -> Tuple[ChangeLevel, str]:
    """Classify an Edit tool use."""
    file_path = tool_input.get('file_path', '')
    old_string = tool_input.get('old_string', '')
    new_string = tool_input.get('new_string', '')

    # Calculate change size
    old_lines = len(old_string.split('\n'))
    new_lines = len(new_string.split('\n'))
    char_diff = abs(len(new_string) - len(old_string))
    line_diff = abs(new_lines - old_lines)

    # Check if it's just adding/removing trivial content
    old_non_trivial = count_non_trivial_lines(old_string)
    new_non_trivial = count_non_trivial_lines(new_string)
    non_trivial_diff = abs(new_non_trivial - old_non_trivial)

    # Check for new significant patterns
    has_new_significant = has_significant_patterns(new_string) and not has_significant_patterns(old_string)

    # Large refactor
    if char_diff > 500 or line_diff > 20:
        return ChangeLevel.MAJOR, f"Large edit ({line_diff} lines, {char_diff} chars changed)"

    # Added significant code
    if has_new_significant or non_trivial_diff > 5:
        return ChangeLevel.SIGNIFICANT, f"Code structure change ({non_trivial_diff} code lines)"

    # Moderate change
    if char_diff > 100 or non_trivial_diff > 2:
        return ChangeLevel.SIGNIFICANT, f"Moderate edit ({char_diff} chars changed)"

    # Small change
    return ChangeLevel.TRIVIAL, f"Small edit ({char_diff} chars changed)"


def classify_bash(tool_input: Dict[str, Any], tool_result: Any = None) -> Tuple[ChangeLevel, str]:
    """Classify a Bash tool use."""
    command = tool_input.get('command', '')

    # Git commit is major
    if re.search(r'\bgit\s+commit\b', command):
        return ChangeLevel.MAJOR, "Git commit"

    # Test commands are significant
    for pattern in TEST_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return ChangeLevel.SIGNIFICANT, "Test execution"

    # Build commands are significant
    for pattern in BUILD_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return ChangeLevel.SIGNIFICANT, "Build execution"

    # Git operations (not commit) are minor but worth noting
    if re.search(r'\bgit\s+(add|status|diff|log|branch|checkout|push|pull)\b', command):
        return ChangeLevel.TRIVIAL, "Git operation"

    # File system exploration is trivial
    if re.search(r'^(ls|pwd|cd|cat|head|tail|find|grep)\b', command):
        return ChangeLevel.TRIVIAL, "File exploration"

    # Default to trivial for other commands
    return ChangeLevel.TRIVIAL, "Shell command"


def classify_change(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: Any = None
) -> Tuple[ChangeLevel, str]:
    """
    Classify a tool use as trivial, significant, or major.

    Args:
        tool_name: Name of the tool (Write, Edit, Bash, etc.)
        tool_input: Input parameters for the tool
        tool_result: Result from the tool (optional)

    Returns:
        Tuple of (ChangeLevel, reason string)
    """
    if tool_name == "Write":
        return classify_write(tool_input)
    elif tool_name == "Edit":
        return classify_edit(tool_input)
    elif tool_name == "Bash":
        return classify_bash(tool_input, tool_result)
    else:
        return ChangeLevel.TRIVIAL, f"Other tool: {tool_name}"


def should_auto_log(level: ChangeLevel) -> bool:
    """Determine if change should trigger auto-logging."""
    return level in (ChangeLevel.SIGNIFICANT, ChangeLevel.MAJOR)


def should_suggest_checkpoint(level: ChangeLevel) -> bool:
    """Determine if change should suggest a checkpoint."""
    return level == ChangeLevel.MAJOR
