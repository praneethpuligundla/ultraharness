---
description: Show current harness status (progress, features, git state)
---

# Show Agent Harness Status

Display the current state of the agent harness for this project.

## What to Show

1. **Harness Initialization Status**
   - Check if `.claude/.claude-harness-initialized` exists
   - If not initialized, suggest running `/harness:init`

2. **Git Status**
   - Current branch
   - Uncommitted changes (if any)
   - Recent commits (last 5)

3. **Progress Log Summary**
   - Read `claude-progress.txt`
   - Show last 10 entries
   - Highlight any blockers

4. **Feature Checklist Summary**
   - Read `claude-features.json`
   - Show counts: total, passing, failing, in_progress
   - List next 5 priority items to work on

5. **Recommendations**
   - If there are uncommitted changes, suggest committing
   - If there are in_progress features, suggest continuing them
   - If there are failing features, suggest starting highest priority

## Output Format

```
=== AGENT HARNESS STATUS ===

Project: {project_name}
Initialized: Yes/No

--- GIT ---
Branch: {branch}
Status: {clean/uncommitted changes}
Recent commits:
  - {hash} {message}
  ...

--- PROGRESS LOG (last 10) ---
[timestamp] entry
...

--- FEATURES ---
Total: X | Passing: X | Failing: X | In Progress: X

Next priority items:
1. [status] Feature name - description
...

--- RECOMMENDATIONS ---
- {actionable suggestions}
```

Use Read tool to check files, and Bash for git commands.
