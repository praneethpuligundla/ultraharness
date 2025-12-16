---
description: Configure harness strictness and automation settings
argument-hint: Setting to configure (e.g., "strict", "relaxed", "auto-log off")
---

# Configure Agent Harness

Configure the harness strictness level and automation settings for this project.

## Arguments

$ARGUMENTS

## Strictness Levels

| Level | Description |
|-------|-------------|
| **relaxed** | Minimal intervention - suggestions only, no auto-logging |
| **standard** | Balanced automation (default) - auto-logging, checkpoint suggestions, warnings |
| **strict** | Maximum enforcement - blocks stopping if tests not run or features incomplete |

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `auto_progress_logging` | Log significant changes automatically | true |
| `auto_checkpoint_suggestions` | Suggest checkpoints after major changes | true |
| `feature_enforcement` | Enforce one-feature-at-a-time | true |
| `baseline_tests_on_startup` | Run tests at session start | true |
| `init_script_execution` | Execute init.sh at session start | true |
| `browser_automation` | Enable Playwright UI verification | false |
| `checkpoint_interval_minutes` | Time between checkpoint suggestions | 30 |

## Examples

```
/harness:configure strict
/harness:configure relaxed
/harness:configure standard
/harness:configure auto-log off
/harness:configure feature-enforcement off
/harness:configure checkpoint-interval 60
```

## Actions

1. Parse the configuration change from arguments:
   - If argument is "strict", "standard", or "relaxed" -> change strictness level
   - If argument contains "off" -> disable the specified feature
   - If argument contains "on" -> enable the specified feature
   - If argument contains a number -> set interval value

2. Read current config from `.claude/claude-harness.json` using Python:
   ```python
   import json
   from pathlib import Path
   config_path = Path('.claude/claude-harness.json')
   if config_path.exists():
       config = json.loads(config_path.read_text())
   else:
       config = {}
   ```

3. Update the config based on the argument:
   - Map "auto-log" to "auto_progress_logging"
   - Map "checkpoint" to "auto_checkpoint_suggestions"
   - Map "feature-enforcement" to "feature_enforcement"
   - Map "baseline-tests" to "baseline_tests_on_startup"
   - Map "init-script" to "init_script_execution"
   - Map "browser" to "browser_automation"

4. Save the updated config:
   ```python
   config_path.parent.mkdir(parents=True, exist_ok=True)
   config_path.write_text(json.dumps(config, indent=2))
   ```

5. Confirm the change with a summary of current settings.

## Current Mode Indicators

After configuration, show:
- Current strictness level
- Which automation features are enabled
- Any warnings about the chosen mode
