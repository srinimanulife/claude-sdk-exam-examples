# Claude Certified Architect — Foundations: Exam Objective Map

> **Setup**: `cd exam_examples && uv run python <domain_file>.py <example>`
> All examples use **Amazon Bedrock** (`us.anthropic.claude-sonnet-4-6`, `us-west-2`).

---

## How to Use This Map

Each row links an **exam objective** → **guide section** → **SDK example** → **what to observe**.
Run any example individually or run the full domain file with `all`.

---

## Domain 1: Agent Architecture and Orchestration (27%)

| Objective | Guide Chapter | Example File | Function | Key Concept |
|-----------|--------------|--------------|----------|-------------|
| 1.1 Agentic loops — stop_reason | Ch 3.1 | `domain1_agent_architecture.py` | `demo_agentic_loop` | ToolUseBlock → tool_result → end_turn cycle |
| 1.2 Coordinator + subagents | Ch 3.3 | `domain1_agent_architecture.py` | `demo_multi_agent` | Hub-and-spoke; coordinator aggregates |
| 1.3 Context passing / Task tool | Ch 3.4 | `domain1_agent_architecture.py` | `demo_multi_agent` | Explicit context in subagent prompt |
| 1.4 Workflow enforcement | Ch 3.5 | `domain1_agent_architecture.py` | `demo_hooks` | Hooks block actions; prompts can't guarantee |
| 1.5 Hooks (Pre/PostToolUse) | Ch 3.5 | `domain1_agent_architecture.py` | `demo_hooks` | Deterministic vs probabilistic compliance |
| 1.6 Task decomposition | Ch 8 | `domain1_agent_architecture.py` | `demo_decomposition` | Fixed pipeline vs dynamic adaptive |
| 1.7 Session management | Ch 5.10 | SDK `streaming_mode.py` | `example_multi_turn_conversation` | `--resume` / `fork_session` concepts |

**Also see SDK examples:**
- `examples/agents.py` — AgentDefinition with tools and models
- `examples/hooks.py` — PreToolUse/PostToolUse/UserPromptSubmit patterns
- `examples/streaming_mode.py` — Multi-turn, interrupt, error handling

**Key exam traps:**
- ❌ `max_iterations=5` as primary stop condition → ✅ only `stop_reason=="end_turn"`
- ❌ Parsing assistant text for "Task completed" → ✅ check stop_reason
- ❌ Subagent inherits coordinator history → ✅ pass context explicitly
- ❌ Prompt instruction for financial limits → ✅ PreToolUse hook (deterministic)

---

## Domain 2: Tool Design and MCP Integration (18%)

| Objective | Guide Chapter | Example File | Function | Key Concept |
|-----------|--------------|--------------|----------|-------------|
| 2.1 Tool description quality | Ch 2.2 | `domain2_tool_design.py` | `demo_descriptions` | Rich description = reliable selection |
| 2.2 Structured MCP errors | Ch 4.4 | `domain2_tool_design.py` | `demo_mcp_errors` | isError + errorCategory + isRetryable |
| 2.3 tool_choice modes | Ch 2.3 | `domain2_tool_design.py` | `demo_tool_choice` | auto / any / forced — when to use each |
| 2.4 In-process MCP server | Ch 4.2 | `domain2_tool_design.py` | `demo_mcp_server` | create_sdk_mcp_server, tool naming |
| 2.5 Built-in tool selection | Ch 13 | `domain2_tool_design.py` | `demo_builtin_tools` | Grep vs Glob vs Read vs Edit vs Bash |

**Also see SDK examples:**
- `examples/mcp_calculator.py` — Complete @tool + create_sdk_mcp_server demo
- `examples/tools_option.py` — tools preset, array, empty array
- `examples/tool_permission_callback.py` — can_use_tool callback

**Key exam traps:**
- ❌ Vague description "Gets info" → ✅ include what, returns, input formats, when vs alternatives
- ❌ `isError: true` with "Operation failed" → ✅ errorCategory + isRetryable + alternatives
- ❌ tool_choice auto for guaranteed output → ✅ use "any"
- ❌ Built-in agents prefer Read over MCP "fetch" → ✅ strengthen MCP tool descriptions
- MCP tool names: `mcp__{server_name}__{tool_name}` (double underscores)

---

## Domain 3: Claude Code Configuration and Workflows (20%)

| Objective | Guide Chapter | Example File | Function | Key Concept |
|-----------|--------------|--------------|----------|-------------|
| 3.1 CLAUDE.md hierarchy | Ch 5.1-5.2 | `domain3_claude_code.py` | `demo_claude_md` | user / project / directory levels |
| 3.2 Custom skills / commands | Ch 5.4-5.5 | `domain3_claude_code.py` | `demo_skills` | context:fork, allowed-tools, argument-hint |
| 3.3 Path-specific rules | Ch 5.3 | `domain3_claude_code.py` | `demo_path_rules` | .claude/rules/ + YAML paths frontmatter |
| 3.4 Planning vs direct execution | Ch 5.6 | `domain3_claude_code.py` | `demo_planning` | permission_mode='plan' for safe exploration |
| 3.5 Iterative refinement | Ch 6.4 | `domain3_claude_code.py` | `demo_refinement` | Few-shot > vague; interview pattern |
| 3.6 CI/CD integration | Ch 5.9 | `domain3_claude_code.py` | `demo_cicd` | headless mode, structured output, isolation |

**Also see SDK examples:**
- `examples/setting_sources.py` — user/project/local settings layering
- `examples/filesystem_agents.py` — agents loaded from .claude/agents/ files

**Key exam traps:**
- ❌ Team standards in `~/.claude/CLAUDE.md` → ✅ `.claude/CLAUDE.md` (project-level, in VCS)
- ❌ @path nesting > 5 → ✅ max 5 levels deep
- ❌ Direct execution for 45-file migration → ✅ planning mode first
- ❌ Same session reviews its own code → ✅ fresh independent session
- ❌ Re-review posts duplicate comments → ✅ include prior review, report only new issues
- path rules vs directory CLAUDE.md: rules/ when conventions span many dirs

---

## Domain 4: Prompt Engineering and Structured Output (20%)

| Objective | Guide Chapter | Example File | Function | Key Concept |
|-----------|--------------|--------------|----------|-------------|
| 4.1 Explicit criteria | Ch 6.2 | `domain4_prompt_engineering.py` | `demo_explicit_criteria` | Flag ONLY if X,Y,Z — not "be conservative" |
| 4.2 Few-shot prompting | Ch 6.1 | `domain4_prompt_engineering.py` | `demo_few_shot` | 2-4 examples beat vague descriptions |
| 4.3 Structured output (tool_use) | Ch 2.4 | `domain4_prompt_engineering.py` | `demo_structured_output` | Syntactic guaranteed; semantic not |
| 4.4 Validation + retry loop | Ch 6.5 | `domain4_prompt_engineering.py` | `demo_retry_loop` | Retry works for format/arithmetic errors |
| 4.5 Self-correction | Ch 6.6 | `domain4_prompt_engineering.py` | `demo_self_correction` | conflict_detected pattern |
| 4.6 Prompt chaining | Ch 6.3 | `domain4_prompt_engineering.py` | `demo_prompt_chaining` | File-by-file → integration pass |
| 4.7 Interview pattern | Ch 6.4 | `domain4_prompt_engineering.py` | `demo_interview` | Clarifying questions before implementation |

**Key exam traps:**
- ❌ tool_use guarantees semantic correctness → ✅ syntax only; semantic needs validation
- ❌ Required fields always present → ✅ make absent-able fields nullable to prevent hallucination
- ❌ Retry when info absent from source → ✅ retry only for format/arithmetic errors
- ❌ Analyze all 14 files in one pass → ✅ chain per-file then integration pass
- ❌ Enum without "other"/"unclear" → ✅ add both to avoid data loss
- Normalization in prompt: dates→ISO8601, currency→amount+code, percentages→decimal

---

## Domain 5: Context Management and Reliability (15%)

| Objective | Guide Chapter | Example File | Function | Key Concept |
|-----------|--------------|--------------|----------|-------------|
| 5.1 Context window management | Ch 1.5, 11 | `domain5_context_reliability.py` | `demo_context_facts` | Lost-in-middle, tool result accumulation |
| 5.2 Key facts block | Ch 11.1 | `domain5_context_reliability.py` | `demo_context_facts` | Survives /compact summarization |
| 5.3 Trim tool results | Ch 11.2 | `domain5_context_reliability.py` | `demo_trim_results` | PostToolUse keeps 5 of 40 fields |
| 5.4 Position-aware input | Ch 11.3 | `domain5_context_reliability.py` | `demo_position_aware` | Key findings at top; action items at end |
| 5.5 Escalation patterns | Ch 9 | `domain5_context_reliability.py` | `demo_escalation` | Structured handoff; immediate vs nuanced |
| 5.6 Error categories | Ch 10 | `domain5_context_reliability.py` | `demo_error_categories` | transient/validation/business/permission |
| 5.7 Provenance preservation | Ch 12 | `domain5_context_reliability.py` | `demo_provenance` | claim→source link; conflicting data |
| 5.8 State persistence | Ch 11.6 | `domain5_context_reliability.py` | `demo_state_persistence` | manifest.json; coverage annotations |

**Also see SDK examples:**
- `examples/session_stores/` — S3, Redis, Postgres session persistence

**Key exam traps:**
- ❌ Rely on conversation history for key values → ✅ structured facts block in every prompt
- ❌ Return all 40 tool fields → ✅ PostToolUse trim to relevant fields
- ❌ Escalate on first frustration expression → ✅ acknowledge → resolve → escalate on reiteration
- ❌ Escalate on model confidence score → ✅ unreliable; use explicit triggers
- ❌ Generic error suppression (empty = success) → ✅ distinguish no-results from failure
- ❌ Infinite retry inside subagent → ✅ 1-2 retries then propagate to coordinator
- Subagent scratchpad files: external memory for long investigations

---

## Exam Scenarios → Domain Files

| Scenario | Primary Domain | Example File |
|----------|---------------|--------------|
| 1. Customer Support Agent | D1 + D5 | `domain1_agent_architecture.py` + `domain5_context_reliability.py` |
| 2. Code Generation with Claude Code | D3 | `domain3_claude_code.py` |
| 3. Multi-Agent Research System | D1 + D5 | `domain1_agent_architecture.py` + `domain5_context_reliability.py` |
| 4. Developer Productivity Tools | D2 | `domain2_tool_design.py` |
| 5. Claude Code for CI/CD | D3 | `domain3_claude_code.py` (cicd example) |
| 6. Structured Data Extraction | D4 | `domain4_prompt_engineering.py` |

---

## SDK Examples → Exam Objectives

| SDK File | Exam Objectives |
|----------|----------------|
| `examples/quick_start.py` | Basics: query(), ClaudeAgentOptions, allowed_tools |
| `examples/agents.py` | D1.2, D1.3: AgentDefinition, multi-agent |
| `examples/hooks.py` | D1.4, D1.5: PreToolUse deny, PostToolUse normalize, UserPromptSubmit |
| `examples/mcp_calculator.py` | D2.4: create_sdk_mcp_server, @tool decorator, MCP naming |
| `examples/streaming_mode.py` | D1.1: agentic loop observation, multi-turn, interrupt |
| `examples/tools_option.py` | D2.3: tool configuration (preset, array, empty) |
| `examples/filesystem_agents.py` | D3.2: agents loaded from .claude/agents/ |
| `examples/setting_sources.py` | D3.1: settings hierarchy (user/project/local) |
| `examples/tool_permission_callback.py` | D2.3: can_use_tool callback |
| `examples/max_budget_usd.py` | D5.5: cost control / escalation triggers |
| `examples/session_stores/` | D5.8: S3/Redis/Postgres state persistence |

---

## Quick Reference: Critical Exam Decisions

```
Should you use a hook or prompt instruction?
  → Financial/legal/safety consequences: HOOK (deterministic)
  → General preference/style: prompt instruction (probabilistic)

tool_choice mode?
  → Want structured output guaranteed: "any"
  → Need specific first step: {"type":"tool","name":"extract_metadata"}
  → Normal operation: "auto"

CLAUDE.md level?
  → All team members must have it: .claude/CLAUDE.md (project, VCS)
  → Personal only: ~/.claude/CLAUDE.md (user, NOT VCS)
  → Subtree rules: <subdir>/CLAUDE.md (directory)

Planning vs direct execution?
  → Architectural decision / 45+ files: planning mode
  → Single clear fix with stack trace: direct execution

Retry after validation failure?
  → Format/arithmetic error: YES (retry with error context)
  → Missing information in source: NO (retry won't help)

Escalation trigger?
  → "Get me a manager": IMMEDIATE (do not attempt to solve first)
  → First expression of frustration: NO (acknowledge → resolve → escalate on reiteration)
  → Model confidence score 3/10: NO (unreliable; use explicit rule triggers)
```

---

## Running All Examples

```bash
cd /mnt/c/projects/claude/claude-certified-architect-main/exam_examples

# Install SDK
cd .. && uv pip install -e claude-agent-sdk-python-main && cd exam_examples

# Run individual domains
uv run python domain1_agent_architecture.py loop
uv run python domain2_tool_design.py mcp_server
uv run python domain3_claude_code.py cicd
uv run python domain4_prompt_engineering.py few_shot
uv run python domain5_context_reliability.py escalation

# Run all in a domain
uv run python domain1_agent_architecture.py all
```
