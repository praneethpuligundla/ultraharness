---
description: Create a git checkpoint commit with progress logging
argument-hint: Commit message describing what was accomplished
---

# Create Git Checkpoint

Create a git checkpoint commit and log it to the progress file.

## Arguments

$ARGUMENTS

## Purpose

Checkpoints are critical for long-running agent workflows:
- They preserve work in case of session interruption
- They provide recovery points
- They document incremental progress
- They leave code in merge-ready state

## Actions

1. Check for uncommitted changes with `git status`
2. If no changes, inform user nothing to commit
3. Stage all changes: `git add -A`
4. Create commit with provided message (or generate one if not provided)
5. Log checkpoint to `claude-progress.txt`
6. Show commit hash and summary

## Commit Message Guidelines

If user provides a message, use it. If not, generate one that:
- Summarizes what was accomplished
- References feature IDs if applicable
- Is concise but descriptive

Format: `[checkpoint] {message}`

## Example

User: `/harness:checkpoint Implemented user login form and validation`

Actions:
1. `git status` - check changes
2. `git add -A` - stage everything
3. `git commit -m "[checkpoint] Implemented user login form and validation"`
4. Append to progress: `[timestamp] CHECKPOINT [abc1234]: Implemented user login form and validation`
5. Show: "Created checkpoint abc1234: Implemented user login form and validation"

## Important

- Always verify there are changes before committing
- Don't commit if tests are failing (ask user to confirm)
- Include the checkpoint hash in the progress log
- Leave code in a state that could be merged
