---
description: Add an entry to the progress log
argument-hint: Entry type and message (e.g., "completed User authentication")
---

# Add Progress Log Entry

Add an entry to `claude-progress.txt` to track progress across sessions.

## Entry Types

Parse the user's input to determine the entry type:

- **started [task]** - Beginning work on a task
- **completed [task]** - Finished a task
- **checkpoint [message]** - Creating a git checkpoint
- **note [message]** - General observation
- **blocker [issue]** - Something preventing progress
- **session-start** - Mark beginning of session
- **session-end** - Mark end of session

## Arguments

$ARGUMENTS

## Actions

1. Parse the entry type and message from arguments
2. Format the entry with timestamp:
   ```
   [YYYY-MM-DD HH:MM:SS] TYPE: message
   ```
3. Append to `claude-progress.txt` using Edit or Write tool
4. Confirm the entry was added
5. If entry type is "completed", ask if the corresponding feature should be marked as passing

## Examples

User: `/harness:log completed User authentication`
→ Appends: `[2024-01-15 10:30:00] COMPLETED: User authentication`

User: `/harness:log blocker API rate limiting issue`
→ Appends: `[2024-01-15 10:30:00] BLOCKER: API rate limiting issue`

User: `/harness:log note Consider refactoring the auth module`
→ Appends: `[2024-01-15 10:30:00] NOTE: Consider refactoring the auth module`
