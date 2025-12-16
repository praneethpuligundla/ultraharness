---
description: Initialize agent harness for the current project
---

# Initialize Agent Harness

You are initializing the agent harness for this project. This sets up the infrastructure for effective long-running agent workflows based on Anthropic's engineering best practices.

## What to Create

1. **Progress Tracking File** (`claude-progress.txt`)
   - A log file that persists across sessions
   - Records what was accomplished, blockers, and notes
   - Read at session start for context

2. **Feature Checklist** (`claude-features.json`)
   - JSON file listing all features/tasks
   - Each starts as "failing" and moves to "passing" when complete
   - Prevents premature completion claims

3. **Initialization Marker** (`.claude/.claude-harness-initialized`)
   - Signals that harness is set up
   - Enables session startup hooks

4. **Init Script** (`init.sh`) - Optional
   - Script to start dev server or other services
   - Run at the beginning of work sessions

## Steps

1. Ask the user about their project:
   - What is the project name?
   - Do they have a list of features/tasks to track?
   - Do they need an init.sh script (dev server, etc.)?

2. Create the necessary files:
   - Use the Write tool to create claude-progress.txt with header
   - Use the Write tool to create claude-features.json
   - Create .claude/.claude-harness-initialized marker
   - Optionally create init.sh

3. If the user has features to track:
   - Ask them to list all features/requirements
   - Add each to claude-features.json with status "failing"
   - Prioritize them

4. Make an initial git commit:
   - Stage the new harness files
   - Commit with message "Initialize agent harness for long-running workflows"

5. Explain next steps:
   - How to use `/harness:status` to see current state
   - How to use `/harness:feature` to manage features
   - How to use `/harness:log` to add progress entries
   - Remind them to commit checkpoints frequently

## File Templates

### claude-progress.txt
```
# Claude Agent Progress Log
# Project: {PROJECT_NAME}
# Created: {TIMESTAMP}
#
# This file tracks progress across Claude Code sessions.
# Update as you complete tasks.
#
# ============================================

[{TIMESTAMP}] INITIALIZED: Progress tracking enabled
```

### claude-features.json
```json
{
  "metadata": {
    "project": "{PROJECT_NAME}",
    "created_at": "{TIMESTAMP}",
    "description": "Feature checklist for long-running agent workflows"
  },
  "features": []
}
```

### init.sh (if needed)
```bash
#!/bin/bash
# Startup script for {PROJECT_NAME}
# Run this at the start of each session

# Example: Start dev server
# npm run dev &

# Example: Start database
# docker-compose up -d

echo "Development environment ready"
```

IMPORTANT: Be thorough in gathering requirements. The feature list is critical - it prevents the agent from claiming work is complete prematurely.
