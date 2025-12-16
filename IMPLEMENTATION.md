# Harness Plugin Implementation Details

This document describes the enhanced harness plugin implementation that achieves 100% coverage of Anthropic's blog recommendations for long-running agents.

**Reference**: [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

**Implementation Date**: December 2024

---

## Architecture Overview

```
harness/
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata (v1.0.0)
├── core/                        # Core Python modules
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── change_detector.py       # Smart change classification
│   ├── test_runner.py           # Test execution utilities
│   ├── browser_automation.py    # Playwright/Puppeteer wrapper
│   ├── progress.py              # Progress file utilities
│   └── features.py              # Feature checklist management
├── hooks/                       # Claude Code hooks
│   ├── hooks.json               # Hook configuration
│   ├── session_start.py         # SessionStart hook
│   ├── stop.py                  # Stop hook
│   ├── pre_tool_use.py          # PreToolUse hook
│   └── post_tool_use.py         # PostToolUse hook
├── commands/                    # Slash commands
│   ├── init.md                  # Initialize harness
│   ├── status.md                # Show status
│   ├── log.md                   # Add progress entry
│   ├── feature.md               # Manage features
│   ├── checkpoint.md            # Create git checkpoint
│   ├── configure.md             # Configure settings
│   └── baseline.md              # Run baseline tests
├── skills/
│   └── ultraharness-workflow.md      # Workflow guidance skill
├── README.md                    # User documentation
└── IMPLEMENTATION.md            # This file
```

---

## Blog Recommendations Coverage

| Recommendation | Implementation | File(s) |
|----------------|----------------|---------|
| Two-agent system | Skill guidance + init command separation | `skills/ultraharness-workflow.md` |
| Init script execution | Auto-runs `init.sh` on session start | `hooks/session_start.py` |
| Progress documentation | `claude-progress.txt` with auto-logging | `core/progress.py`, `hooks/post_tool_use.py` |
| Feature list (JSON) | `claude-features.json` with status tracking | `core/features.py` |
| Session startup routine | Reads git, progress, features automatically | `hooks/session_start.py` |
| Baseline tests on startup | Runs tests before starting work | `hooks/session_start.py`, `core/test_runner.py` |
| Auto-progress logging | Logs significant changes automatically | `hooks/post_tool_use.py` |
| Auto-checkpoint suggestions | Suggests commits after major changes | `hooks/post_tool_use.py` |
| Feature status automation | Parses test results, suggests updates | `hooks/post_tool_use.py` |
| One-feature discipline | Enforces working on declared feature | `hooks/pre_tool_use.py` |
| Stop validation | Validates tests run, features complete | `hooks/stop.py` |
| Browser automation | Playwright/Puppeteer for UI verification | `core/browser_automation.py` |

---

## Core Modules

### config.py - Configuration Management

**Purpose**: Centralized configuration with three strictness levels.

**Key Functions**:
- `load_config(work_dir)` - Load from `.claude/claude-harness.json`
- `save_config(config, work_dir)` - Persist configuration
- `is_strict_mode()`, `is_relaxed_mode()`, `is_standard_mode()` - Mode checks
- `get_setting(key)`, `set_setting(key, value)` - Individual settings
- `is_harness_initialized(work_dir)` - Check initialization status

**Default Configuration**:
```python
{
    "strictness": "standard",
    "auto_progress_logging": True,
    "auto_checkpoint_suggestions": True,
    "feature_enforcement": True,
    "baseline_tests_on_startup": True,
    "init_script_execution": True,
    "browser_automation": False,
    "checkpoint_interval_minutes": 30,
    "test_commands": {
        "node": "npm test -- --passWithNoTests 2>&1 || true",
        "python": "python -m pytest -v 2>&1 || true",
        "rust": "cargo test 2>&1 || true",
        "go": "go test ./... 2>&1 || true"
    }
}
```

### change_detector.py - Change Classification

**Purpose**: Intelligently classify changes to determine when to auto-log and suggest checkpoints.

**Change Levels**:
- `TRIVIAL` - Comments, formatting, imports, small edits (<100 chars)
- `SIGNIFICANT` - New functions, logic changes, test runs, moderate edits
- `MAJOR` - New files >100 lines, large refactors, git commits

**Key Functions**:
- `classify_change(tool_name, tool_input, tool_result)` - Returns `(ChangeLevel, reason)`
- `should_auto_log(level)` - True for SIGNIFICANT and MAJOR
- `should_suggest_checkpoint(level)` - True for MAJOR only

**Classification Logic**:
- Analyzes Write tool: counts lines, checks for code patterns
- Analyzes Edit tool: measures diff size, detects new patterns
- Analyzes Bash tool: identifies test/build/git commands

### test_runner.py - Test Execution

**Purpose**: Unified test execution across multiple project types.

**Supported Project Types**:
- Node.js (`package.json`) - `npm test`
- Python (`pyproject.toml`, `setup.py`) - `pytest`
- Rust (`Cargo.toml`) - `cargo test`
- Go (`go.mod`) - `go test ./...`
- Java Maven (`pom.xml`) - `mvn test`
- Java Gradle (`build.gradle`) - `./gradlew test`

**Key Functions**:
- `detect_project_type(work_dir)` - Detect from config files
- `run_tests(work_dir, timeout)` - Execute tests, return `TestSummary`
- `parse_test_output(output, project_type)` - Extract pass/fail counts
- `did_tests_run_in_session(transcript_path)` - Check session transcript
- `get_test_summary_string(summary)` - Human-readable summary

**TestSummary Dataclass**:
```python
@dataclass
class TestSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    raw_output: str = ""
    result: TestResult = TestResult.NOT_RUN
    failed_tests: List[str] = field(default_factory=list)
```

### browser_automation.py - UI Verification

**Purpose**: Playwright/Puppeteer wrapper for visual verification (opt-in).

**Key Functions**:
- `detect_browser_tool(work_dir)` - Find Playwright or Puppeteer
- `take_screenshot(url, output_path, ...)` - Capture page screenshot
- `verify_element(url, selector, expected_text)` - Check element exists
- `get_installation_instructions()` - Setup instructions

**BrowserResult Dataclass**:
```python
@dataclass
class BrowserResult:
    success: bool
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    output: Optional[str] = None
    element_found: bool = False
    element_text: Optional[str] = None
```

---

## Hooks Implementation

### hooks.json - Hook Registration

```json
{
  "hooks": {
    "SessionStart": [{"matcher": "*", "hooks": [...], "timeout": 120}],
    "PreToolUse": [{"matcher": "Edit|Write", "hooks": [...], "timeout": 10}],
    "PostToolUse": [{"matcher": "Edit|Write|Bash", "hooks": [...], "timeout": 15}],
    "Stop": [{"matcher": "*", "hooks": [...], "timeout": 15}]
  }
}
```

### session_start.py - SessionStart Hook

**Triggers**: Every session start

**Actions**:
1. Check if harness is initialized
2. Load configuration
3. Execute `init.sh` if exists (60s timeout, 10KB limit)
4. Run baseline tests if configured
5. Read git status and recent commits
6. Read progress file (last 50 lines)
7. Read feature checklist summary
8. Inject context via `systemMessage`

**Output Format**:
```
=== AGENT HARNESS SESSION STARTUP ===
Session started: {timestamp}
Working directory: {path}
Mode: {strictness}

--- INIT SCRIPT ---
{init.sh output}

--- BASELINE TESTS ---
{test results}

--- GIT STATUS ---
{modified files}

--- RECENT COMMITS ---
{last 10 commits}

--- PROGRESS LOG ---
{last 50 lines}

--- FEATURE CHECKLIST STATUS ---
Total: X | Passing: X | Failing: X | In Progress: X
Next priority items:
  [WIP] 1. Feature name: description
  [TODO] 2. Feature name: description

=== END SESSION CONTEXT ===
```

### pre_tool_use.py - PreToolUse Hook

**Triggers**: Before Edit or Write tools

**Purpose**: Enforce one-feature-at-a-time discipline

**Actions**:
1. Check if features are defined
2. Check if any feature is `in_progress`
3. If no active feature:
   - Standard mode: Show warning, allow operation
   - Strict mode: Block with `permissionDecision: deny`

**Output**:
- Warning message listing available features to start
- In strict mode: operation blocked

### post_tool_use.py - PostToolUse Hook

**Triggers**: After Edit, Write, or Bash tools

**Purpose**: Auto-logging, checkpoint suggestions, test result parsing

**Actions**:
1. Classify the change (trivial/significant/major)
2. Auto-log significant changes to progress file
3. Track cumulative changes in session state file
4. Suggest checkpoint when:
   - Major change occurs
   - 5+ significant changes accumulate
   - Time threshold exceeded (default 30 min)
5. Parse test results from Bash output
6. Suggest feature status updates after test pass

**Session State** (stored in `/tmp/harness-session-{id}.json`):
```json
{
    "changes_since_checkpoint": 0,
    "last_checkpoint_time": null,
    "significant_changes": [],
    "current_feature": null
}
```

### stop.py - Stop Hook

**Triggers**: When agent considers stopping

**Purpose**: Validate work completion before allowing stop

**Validation Checks**:
1. Tests run if code was modified
2. Uncommitted changes warning
3. Features still in progress
4. Progress log updated

**Behavior by Mode**:
- **Relaxed**: Single FYI message
- **Standard**: Strong warnings, no blocking
- **Strict**: Block with `decision: block` if validation fails

---

## Commands

| Command | Description | Key Actions |
|---------|-------------|-------------|
| `/ultraharness:init` | Initialize harness | Create progress file, features file, marker |
| `/ultraharness:status` | Show current state | Display git, progress, features summary |
| `/ultraharness:log [type] [msg]` | Add progress entry | Append to progress file with timestamp |
| `/ultraharness:feature [action]` | Manage features | add, start, pass, fail, list, next |
| `/ultraharness:checkpoint [msg]` | Create git commit | Stage all, commit with prefix, log |
| `/ultraharness:configure [setting]` | Change settings | Modify `.claude/claude-harness.json` |
| `/ultraharness:baseline` | Run tests manually | Execute and display test results |

---

## File Formats

### claude-progress.txt

```
# Claude Agent Progress Log
# Project: {name}
# Created: {timestamp}

[2024-12-14 10:30:00] INITIALIZED: Progress tracking enabled
[2024-12-14 10:35:00] STARTED: User authentication feature
[2024-12-14 10:45:00] AUTO: Created auth.py (New code file, 45 code lines)
[2024-12-14 11:00:00] CHECKPOINT [abc1234]: Implemented login form
[2024-12-14 11:30:00] COMPLETED: User authentication feature
```

### claude-features.json

```json
{
  "metadata": {
    "project": "my-app",
    "created_at": "2024-12-14T10:30:00",
    "last_updated": "2024-12-14T11:30:00"
  },
  "features": [
    {
      "id": 1,
      "name": "User login",
      "description": "Email/password authentication",
      "status": "passing",
      "category": "auth",
      "priority": 1,
      "created_at": "2024-12-14T10:30:00",
      "updated_at": "2024-12-14T11:30:00",
      "notes": [
        {"timestamp": "2024-12-14T11:30:00", "content": "All tests passing"}
      ]
    }
  ]
}
```

### .claude/claude-harness.json

```json
{
  "strictness": "standard",
  "auto_progress_logging": true,
  "auto_checkpoint_suggestions": true,
  "feature_enforcement": true,
  "baseline_tests_on_startup": true,
  "init_script_execution": true,
  "browser_automation": false,
  "checkpoint_interval_minutes": 30
}
```

---

## Strictness Levels

| Feature | Relaxed | Standard | Strict |
|---------|---------|----------|--------|
| Auto-progress logging | Off | On | On |
| Checkpoint suggestions | Off | On | On |
| Feature enforcement | Off | Warn | Block |
| Stop validation | FYI | Warn | Block |
| Baseline tests | Off | On | On |
| Init script | On | On | On |

---

## Error Handling

All hooks follow these principles:
1. Never block on errors - always exit 0
2. Wrap all code in try/except
3. Return informative error messages via `systemMessage`
4. Fallback gracefully if imports fail
5. Use timeouts for external operations

---

## Testing the Implementation

1. **Test SessionStart**: Start Claude Code in an initialized project
2. **Test PreToolUse**: Try to edit without starting a feature
3. **Test PostToolUse**: Make significant edits, check for suggestions
4. **Test Stop**: Try to stop without running tests
5. **Test Strictness**: Configure strict mode and verify blocking

---

## Future Enhancements

Potential improvements not yet implemented:
- SubagentStop hook for validating subagent completion
- Notification hook for external integrations
- PreCompact hook to preserve critical context
- Integration with CI/CD pipelines
- Remote session support
- Custom test command configuration per project
