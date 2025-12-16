# UltraHarness Plugin

Advanced Claude Code plugin with **FIC (Flow-Information-Context) System** for intelligent context management, verification gates, and subagent orchestration.

> For a lightweight version without FIC, see [harness](https://github.com/praneethpuligundla/harness)

## Overview

Long-running AI agents struggle across multiple context windows because each new session begins without memory of prior work. This plugin solves that problem by providing:

- **FIC System** - Automatic Research → Plan → Implement workflow with verification gates
- **Context Intelligence** - Tracks what information enters context, detects redundancy
- **Progress Tracking** - Persistent log file (`claude-progress.txt`) that records accomplishments
- **Feature Checklists** - JSON file (`claude-features.json`) tracking feature status
- **Git Checkpoints** - Encourages frequent commits as safe recovery points
- **Session Startup Routine** - Automatically reads context and FIC state at session start
- **Subagent Orchestration** - Auto-suggests delegation to keep main context clean

Based on:
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Advanced Context Engineering for Coding Agents](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents)

## Installation

Install this plugin globally to enable it for all your Claude Code projects:

```bash
claude plugins:add praneethpuligundla/ultraharness
```

Or install from URL:

```bash
claude plugins:add https://github.com/praneethpuligundla/ultraharness
```

The plugin is installed at user scope and applies to all Claude Code projects.

### Upgrading from Harness

If you're using the lightweight [harness](https://github.com/praneethpuligundla/harness) plugin:

```bash
claude plugins:remove harness
claude plugins:add praneethpuligundla/ultraharness
```

Then run `/ultraharness:init` in your project. Existing `claude-progress.txt` and `claude-features.json` files are preserved - UltraHarness adds FIC artifacts alongside them.

## Usage

### Initialize a Project

```
/ultraharness:init
```

This creates:
- `.claude/.claude-harness-initialized` - Marker file
- `.claude/claude-harness.json` - FIC configuration
- `.claude/fic-artifacts/` - Artifact storage directories

### Check Status

```
/ultraharness:status
```

Shows FIC phase, research confidence, plan validation status, and git state.

### Configure FIC Mode

```
/ultraharness:configure strict    # Block operations until gates pass
/ultraharness:configure relaxed   # Allow all operations (override gates)
/ultraharness:configure standard  # Warn but don't block
```

### Run Baseline Tests

```
/ultraharness:baseline
```

Manually run tests to verify implementation.

## How It Works

### Session Start Hook

When a Claude Code session starts in an initialized project:
1. Reads git log for recent commits
2. Reads progress file for context
3. Summarizes feature checklist status
4. Injects this context into the session

### Session Stop Hook

When Claude stops responding:
1. Reminds to update progress file
2. Suggests committing work as checkpoint
3. Encourages merge-ready state

## FIC (Flow-Information-Context) System

The FIC system implements intelligent context management for complex, long-running tasks.

### How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FIC SYSTEM ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   USER      │     │  RESEARCH   │     │  PLANNING   │     │IMPLEMENTATION│
│   PROMPT    │────▶│   PHASE     │────▶│   PHASE     │────▶│    PHASE    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ UserPrompt  │     │   Gate:     │     │   Gate:     │     │   Gate:     │
│  Submit     │     │ Confidence  │     │   Plan      │     │   Tests     │
│   Hook      │     │   >= 70%    │     │ Validated   │     │  Passing    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT INTELLIGENCE ENGINE                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │  Information  │  │  Redundancy   │  │  Utilization  │  │  Compaction  │ │
│  │Classification │  │  Detection    │  │   Tracking    │  │ Preservation │ │
│  │Essential/Noise│  │  Same content │  │  Target 40-60%│  │  Save state  │ │
│  └───────────────┘  └───────────────┘  └───────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SUBAGENT DELEGATION                              │
│                                                                             │
│   "How does X work?"  ───▶  @fic-researcher  ───▶  Structured Findings     │
│                                                    (Only essential enters   │
│   "Validate my plan"  ───▶  @fic-plan-validator ──▶  main context)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              HOOK FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SessionStart ──▶ Load preserved context, show FIC state & phase guidance  │
│        │                                                                    │
│        ▼                                                                    │
│  UserPromptSubmit ──▶ Detect research/planning prompts, suggest delegation │
│        │                                                                    │
│        ▼                                                                    │
│  PreToolUse ──▶ Check verification gates before Edit/Write operations      │
│        │                                                                    │
│        ▼                                                                    │
│  PostToolUse ──▶ Track context entries, classify information, warn on noise│
│        │                                                                    │
│        ▼                                                                    │
│  SubagentStop ──▶ Extract structured findings from research subagents      │
│        │                                                                    │
│        ▼                                                                    │
│  PreCompact ──▶ Preserve essential context, inject focus directive         │
│        │                                                                    │
│        ▼                                                                    │
│  Stop ──▶ Final validation, suggest checkpoint                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARTIFACTS FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
│  │ ResearchArtifact │───▶│   PlanArtifact   │───▶│ImplementationArtifact│  │
│  ├──────────────────┤    ├──────────────────┤    ├──────────────────────┤  │
│  │ - discoveries    │    │ - steps          │    │ - steps_completed    │  │
│  │ - relevant_files │    │ - success_criteria│   │ - plan_deviations    │  │
│  │ - confidence     │    │ - validation     │    │ - tests_status       │  │
│  │ - open_questions │    │ - risk_mitigations│   │ - files_modified     │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────────┘  │
│          │                       │                        │                 │
│          ▼                       ▼                        ▼                 │
│    is_complete()?          is_actionable()?        get_progress()          │
│    confidence >= 0.7       validation == PROCEED   track plan adherence    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Workflow Phases

1. **RESEARCH** - Explore the codebase, build understanding
   - Automatic subagent delegation for exploration
   - Confidence scoring (must reach 70% to proceed)
   - Open question tracking (blocking vs non-blocking)

2. **PLANNING** - Create specific, actionable implementation plan
   - Plan validation via @fic-plan-validator
   - Verification criteria for each step
   - Risk assessment

3. **IMPLEMENTATION** - Execute the plan
   - Track progress against plan steps
   - Document deviations
   - Verification at each step

### Context Intelligence

- **Information Classification** - Essential / Helpful / Noise
- **Redundancy Detection** - Alerts when re-reading same content
- **Utilization Tracking** - Target 40-60% context utilization
- **Compaction Preservation** - Essential context preserved across sessions

### Verification Gates

In **strict mode**, gates enforce phase transitions:

| Gate | Condition |
|------|-----------|
| Research → Planning | Confidence >= 70%, no blocking questions |
| Planning → Implementation | Plan validation == PROCEED |
| Implementation → Commit | All tests passing |

### Configuration

Configure FIC in `.claude/claude-harness.json`:

```json
{
  "fic_enabled": true,
  "fic_strict_gates": true,
  "fic_auto_delegate_research": true,
  "fic_context_tracking": true,
  "fic_config": {
    "target_utilization_low": 0.40,
    "target_utilization_high": 0.60,
    "research_confidence_threshold": 0.7,
    "max_open_questions": 2,
    "compaction_tool_threshold": 25
  }
}
```

## Best Practices

1. **Initialize early** - Set up harness at project start
2. **List all features** - Comprehensive checklist prevents premature completion
3. **Work incrementally** - One feature at a time
4. **Commit often** - Each commit is a recovery point
5. **Log everything** - Future sessions depend on this context
6. **Use subagents for exploration** - Keep main context clean
7. **Build confidence before implementing** - Research thoroughly first

## File Structure

```
project/
├── claude-progress.txt      # Progress log
├── claude-features.json     # Feature checklist
├── init.sh                  # Optional startup script
└── .claude/
    ├── .claude-harness-initialized  # Marker file
    ├── claude-harness.json          # Configuration
    ├── fic-context-state.json       # Context intelligence state
    ├── fic-preserved-context.json   # Preserved context across sessions
    └── fic-artifacts/               # FIC workflow artifacts
        ├── research/
        ├── plans/
        └── implementations/
```

## Plugin Structure

```
ultraharness/
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   ├── hooks.json
│   ├── session_start.py     # Session startup with FIC state
│   ├── user_prompt_submit.py # Auto-delegation detection
│   ├── pre_tool_use.py      # Verification gates
│   ├── post_tool_use.py     # Context intelligence tracking
│   ├── pre_compact.py       # Context preservation
│   ├── subagent_stop.py     # Research result processing
│   └── stop.py
├── agents/
│   ├── fic-researcher.md    # Research subagent definition
│   └── fic-plan-validator.md # Plan validation subagent
├── commands/
│   ├── init.md
│   ├── status.md
│   ├── configure.md
│   └── baseline.md
├── core/
│   ├── config.py            # Configuration with FIC settings
│   ├── progress.py
│   ├── features.py
│   ├── context_intelligence.py  # FIC context tracking
│   ├── artifacts.py         # FIC artifact definitions
│   ├── verification_gates.py # FIC gate logic
│   └── ...
└── README.md
```
