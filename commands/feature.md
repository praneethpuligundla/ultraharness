---
description: Manage feature checklist (add, update, list features)
argument-hint: Action and details (e.g., "add User login", "pass 3", "list")
---

# Manage Feature Checklist

Manage the feature checklist in `claude-features.json`.

## Actions

Parse the user's input to determine the action:

- **add [name] - [description]** - Add a new feature (status: failing)
- **pass [id or name]** - Mark feature as passing
- **fail [id or name]** - Mark feature as failing
- **start [id or name]** - Mark feature as in_progress
- **list** - List all features with status
- **next** - Show next 5 priority items
- **import** - Import features from a list

## Arguments

$ARGUMENTS

## File Format

`claude-features.json`:
```json
{
  "metadata": {...},
  "features": [
    {
      "id": 1,
      "name": "User authentication",
      "description": "Login, logout, session management",
      "status": "failing|in_progress|passing",
      "category": "auth",
      "priority": 1,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

## Actions Detail

### Add Feature
```
/harness:feature add User authentication - Login and session management
```
Creates new feature with status "failing" and next available ID.

### Update Status
```
/harness:feature pass 1
/harness:feature pass "User authentication"
/harness:feature start 2
/harness:feature fail 3
```

### List Features
```
/harness:feature list
```
Shows all features grouped by status.

### Import Features
```
/harness:feature import
```
Then prompt user for a list of features (one per line or JSON format).

## Important Notes

- New features ALWAYS start as "failing" per Anthropic's guidance
- This prevents premature completion claims
- Features should be specific and testable
- Update the progress log when marking features as passing
