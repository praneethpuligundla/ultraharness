#!/usr/bin/env python3
"""Configuration management for harness plugin.

Supports three strictness levels:
- relaxed: Suggestions only, no blocking
- standard: Block on critical issues, suggest on others
- strict: Block on all validation failures
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILE = "claude-harness.json"

DEFAULT_CONFIG = {
    "strictness": "standard",  # relaxed, standard, strict
    "auto_progress_logging": True,
    "auto_checkpoint_suggestions": True,
    "feature_enforcement": True,
    "baseline_tests_on_startup": True,
    "init_script_execution": True,
    "browser_automation": False,  # Opt-in
    "significant_change_threshold": 50,  # Lines changed
    "checkpoint_interval_minutes": 30,
    "test_commands": {
        "node": "npm test -- --passWithNoTests 2>&1 || true",
        "python": "pytest -v 2>&1 || true",
        "rust": "cargo test 2>&1 || true",
        "go": "go test ./... 2>&1 || true",
        "java": "mvn test 2>&1 || true"
    },
    "browser_config": {
        "headless": True,
        "timeout": 30000,
        "screenshot_dir": ".claude/screenshots"
    },
    # FIC (Flow-Information-Context) Configuration
    "fic_enabled": True,
    "fic_strict_gates": True,  # Enforce verification gates in strict mode
    "fic_auto_delegate_research": True,  # Auto-suggest subagent for research
    "fic_context_tracking": True,  # Track context intelligence
    "fic_artifact_workflow": True,  # Use artifact-driven workflow
    "fic_knowledge_graph_enabled": False,  # MCP knowledge graph (opt-in)
    "fic_config": {
        "target_utilization_low": 0.40,
        "target_utilization_high": 0.60,
        "research_confidence_threshold": 0.7,  # Min confidence to proceed to planning
        "max_open_questions": 2,  # Max open questions to proceed
        "compaction_tool_threshold": 25,  # Tool calls before suggesting compaction
        "research_delegation_patterns": [
            "how does", "where is", "find the", "understand",
            "explore", "investigate", "what is", "explain the"
        ],
        "preserve_essential_on_compact": True,
        "auto_create_artifacts": True
    }
}


def get_working_directory() -> str:
    """Get the current working directory."""
    return os.environ.get('CLAUDE_WORKING_DIRECTORY', os.getcwd())


def get_config_path(work_dir: str = None) -> Path:
    """Get path to harness config file."""
    if work_dir is None:
        work_dir = get_working_directory()
    return Path(work_dir) / '.claude' / CONFIG_FILE


def load_config(work_dir: str = None) -> Dict[str, Any]:
    """Load configuration, merging with defaults."""
    config = DEFAULT_CONFIG.copy()
    # Deep copy nested dicts
    config['test_commands'] = DEFAULT_CONFIG['test_commands'].copy()
    config['browser_config'] = DEFAULT_CONFIG['browser_config'].copy()

    config_path = get_config_path(work_dir)

    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                # Merge user config into defaults
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                        config[key].update(value)
                    else:
                        config[key] = value
        except Exception:
            pass

    return config


def save_config(config: Dict[str, Any], work_dir: str = None) -> bool:
    """Save configuration to file."""
    config_path = get_config_path(work_dir)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


def get_strictness(work_dir: str = None) -> str:
    """Get current strictness level."""
    return load_config(work_dir).get('strictness', 'standard')


def is_strict_mode(work_dir: str = None) -> bool:
    """Check if strict mode is enabled."""
    return get_strictness(work_dir) == 'strict'


def is_relaxed_mode(work_dir: str = None) -> bool:
    """Check if relaxed mode is enabled."""
    return get_strictness(work_dir) == 'relaxed'


def is_standard_mode(work_dir: str = None) -> bool:
    """Check if standard mode is enabled."""
    return get_strictness(work_dir) == 'standard'


def get_setting(key: str, work_dir: str = None) -> Any:
    """Get a specific config setting."""
    config = load_config(work_dir)
    return config.get(key)


def set_setting(key: str, value: Any, work_dir: str = None) -> bool:
    """Set a specific config setting."""
    config = load_config(work_dir)
    config[key] = value
    return save_config(config, work_dir)


def is_harness_initialized(work_dir: str = None) -> bool:
    """Check if harness has been initialized for this project."""
    if work_dir is None:
        work_dir = get_working_directory()
    marker_path = Path(work_dir) / '.claude' / '.claude-harness-initialized'
    return marker_path.exists()
