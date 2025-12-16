---
description: Guidelines for effective long-running agent workflows with progress tracking, git checkpoints, and feature checklists
triggers:
  - long-running task
  - multi-session work
  - complex feature implementation
  - project initialization
  - tracking progress
---

# Long-Running Agent Harness Workflow

This skill provides guidance for effective long-running agent workflows based on Anthropic's engineering best practices.

## Core Principles

### 1. Session Context Continuity
Each session starts without memory of prior work. The harness provides context through:
- `claude-progress.txt` - Log of what was accomplished
- `claude-features.json` - Checklist of features and their status
- Git history - Commits as checkpoints

### 2. Feature-First Development
- All features start as "failing"
- Work on one feature at a time
- Mark as "passing" only when fully complete and tested
- Never remove or edit tests to make them pass

### 3. Checkpoint Discipline
- Commit frequently with descriptive messages
- Leave code in merge-ready state
- Log checkpoints to progress file
- Each commit should be a safe recovery point

## Automation Features

The enhanced harness provides extensive automation to reduce manual overhead:

### Auto-Progress Logging
Significant actions are logged automatically to `claude-progress.txt`:
- New file creations (significant size)
- Major code edits
- Test executions
- Build commands

Format: `[timestamp] AUTO: <action> (<reason>)`

### Auto-Checkpoint Suggestions
The harness suggests creating checkpoints when:
- Major changes occur (new files, large refactors)
- 5+ significant changes accumulate
- Time threshold exceeded (default: 30 minutes)

### Feature Enforcement
When features are defined in `claude-features.json`:
- Prompts to start a feature before editing code
- In strict mode, blocks edits without an active feature
- Helps maintain one-feature-at-a-time discipline

### Stop Validation
Before stopping, the harness validates:
- Tests were run (if code was modified)
- No uncommitted changes remain
- Progress log was updated
- Features aren't left incomplete

In strict mode, stopping is blocked until validation passes.

### Init Script Execution
If `init.sh` exists in the project root:
- Automatically executed at session start
- Use for starting dev servers, setting up environment
- 60-second timeout for safety

### Baseline Tests
At session start:
- Automatically runs project tests
- Warns if tests are failing before you start
- Helps identify pre-existing issues

## Strictness Levels

| Level | Auto-Log | Checkpoint | Feature Enforce | Stop Block |
|-------|----------|------------|-----------------|------------|
| relaxed | No | No | No | No |
| standard | Yes | Suggest | Warn | Warn |
| strict | Yes | Suggest | Block | Block |

Configure with `/ultraharness:configure <level>`

## Session Startup Routine

At the start of each session, the harness automatically:
1. Executes `init.sh` if present
2. Runs baseline tests (if configured)
3. Reads git log to understand recent changes
4. Reads `claude-progress.txt` for context
5. Checks `claude-features.json` for next priority
6. Injects this context into the session

## During Development

### Before Starting a Feature
```
/ultraharness:feature start [feature-id]
/ultraharness:log started [feature-name]
```

### While Working
- Make incremental changes
- Test frequently
- Create checkpoints for significant progress:
```
/ultraharness:checkpoint [description of progress]
```

### After Completing a Feature
```
/ultraharness:feature pass [feature-id]
/ultraharness:log completed [feature-name]
/ultraharness:checkpoint [final implementation description]
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `/ultraharness:init` | Initialize harness for project |
| `/ultraharness:status` | Show current status |
| `/ultraharness:log [type] [message]` | Add progress entry |
| `/ultraharness:feature [action] [args]` | Manage features |
| `/ultraharness:checkpoint [message]` | Create git checkpoint |
| `/ultraharness:configure [setting]` | Configure automation |
| `/ultraharness:baseline` | Run baseline tests manually |

## Progress Log Entry Types

- `started` - Beginning work on a task
- `completed` - Finished a task
- `checkpoint` - Git commit created
- `note` - General observation
- `blocker` - Issue preventing progress

## Feature Statuses

- `failing` - Not yet implemented (default)
- `in_progress` - Currently being worked on
- `passing` - Complete and verified

## Browser Automation (Opt-in)

For UI features, enable browser automation:
```
/ultraharness:configure browser on
```

Requires Playwright or Puppeteer:
```bash
npm install @playwright/test && npx playwright install chromium
```

Capabilities:
- Take screenshots for visual verification
- Check UI elements exist with expected content
- Automated end-to-end verification

## Configuration Options

Stored in `.claude/claude-harness.json`:

| Setting | Description | Default |
|---------|-------------|---------|
| `strictness` | Mode: relaxed/standard/strict | standard |
| `auto_progress_logging` | Log changes automatically | true |
| `auto_checkpoint_suggestions` | Suggest checkpoints | true |
| `feature_enforcement` | Enforce active feature | true |
| `baseline_tests_on_startup` | Run tests on start | true |
| `init_script_execution` | Run init.sh | true |
| `browser_automation` | Enable Playwright | false |
| `checkpoint_interval_minutes` | Time between suggestions | 30 |

## Best Practices

1. **Be Specific with Features**
   - Each feature should be testable
   - Include acceptance criteria
   - Break large features into smaller ones

2. **Document Blockers**
   - Log any issues preventing progress
   - Include context for future sessions

3. **Verify Before Marking Complete**
   - Run tests
   - Check manually if needed
   - Use browser automation for UI features

4. **Leave Clear Handoff Notes**
   - What was accomplished
   - What's next
   - Any known issues

## Example Workflow

```
# Session 1 - Initialize
/ultraharness:init
# Add features...
/ultraharness:feature add User login - Email/password authentication
/ultraharness:feature add User registration - Sign up with email verification
/ultraharness:feature start 1
/ultraharness:log started User login implementation
# ... work on feature ...
/ultraharness:checkpoint Implemented login form and basic validation
# ... more work ...
/ultraharness:feature pass 1
/ultraharness:log completed User login with tests passing
/ultraharness:checkpoint Completed user login feature

# Session 2 (context injected automatically)
/ultraharness:status
# Shows: Login complete, registration next
/ultraharness:feature start 2
# ... continue working ...
```

## Troubleshooting

### Hooks Not Running
- Restart Claude Code to reload hook configuration
- Check hook timeout settings in hooks.json
- Verify Python 3 is available

### Tests Not Detected
- Ensure standard test commands are used
- Check `test_commands` in configuration
- Run `/ultraharness:baseline` manually to verify

### Feature Enforcement Too Strict
- Switch to relaxed mode: `/ultraharness:configure relaxed`
- Or disable feature enforcement: `/ultraharness:configure feature-enforcement off`
