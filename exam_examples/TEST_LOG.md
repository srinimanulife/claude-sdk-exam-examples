# Exam Examples — Test Log & Study Notes

> All examples run against **Amazon Bedrock** (`us.anthropic.claude-sonnet-4-6`, `us-west-2`)
> SDK: claude-agent-sdk v0.1.68 via Claude Code CLI v2.1.119

---

## How to Run

```bash
# From the exam_examples/ directory
# (env vars already set in this WSL2 session)
CLAUDE_CODE_USE_BEDROCK=true AWS_REGION=us-west-2 ANTHROPIC_MODEL=us.anthropic.claude-sonnet-4-6 \
  ../.venv/bin/python <domain_file>.py <example_name>

# Run all examples in a domain
../.venv/bin/python domain1_agent_architecture.py all
```

---

## WSL2 / Bedrock Configuration Notes

**Critical knowledge for setup** (not exam content, but required for these examples):

| Setting | Value | Why |
|---------|-------|-----|
| `CLAUDE_CODE_USE_BEDROCK=true` | Env var | Routes CLI traffic to AWS Bedrock |
| `AWS_REGION=us-west-2` | Env var | Bedrock endpoint region |
| `ANTHROPIC_MODEL=us.anthropic.claude-sonnet-4-6` | Env var | Cross-region inference profile ID |
| `cwd='/tmp'` | ClaudeAgentOptions | WSL2: CLI must start from Linux path, not `/mnt/c` |
| File paths | Absolute `/mnt/c/...` | Read/Grep/Glob work with absolute paths regardless of cwd |

**bedrock_options()** in `bedrock_config.py` encapsulates all of the above.

---

## Domain 1: Agent Architecture and Orchestration (27%)

### ✅ `loop` — Agentic Loop (Objective 1.1)

**Command:** `python domain1_agent_architecture.py loop`

**What it tests:** The SDK's internal agentic loop that drives `stop_reason`.

**Output observed:**
```
→ stop_reason=tool_use: calling Bash
← tool_result returned to model
Tool uses: 1, Tool results fed back: 1
Loop ended on stop_reason=end_turn
```

**Exam takeaways:**
- `ToolUseBlock` in `AssistantMessage` = stop_reason was `tool_use` internally
- `ToolResultBlock` in `UserMessage` = tool result fed back to model
- Final `AssistantMessage` with no tool use = stop_reason was `end_turn`
- ❌ WRONG: `max_iterations=5` as stopping criterion
- ✅ RIGHT: Only `stop_reason=="end_turn"` is reliable

---

### ✅ `multi_agent` — Hub-and-Spoke (Objectives 1.2 + 1.3)

**Command:** `python domain1_agent_architecture.py multi_agent`

**What it tests:** Coordinator delegates to two specialized subagents.

**Exam takeaways:**
- `AgentDefinition` defines specialized subagents with restricted tools
- Coordinator `AgentDefinition` agents dict = defines available subagents
- Subagents have **isolated context** — they don't see coordinator history
- Must pass ALL context explicitly in the task prompt to subagent
- ❌ WRONG: "The subagent knows what the coordinator told it earlier"
- ✅ RIGHT: Include full prior outputs in each subagent Task prompt

---

### ✅ `hooks` — Deterministic Enforcement (Objectives 1.4 + 1.5)

**Command:** `python domain1_agent_architecture.py hooks`

**Output observed:**
```
Test 1: rm -rf → BLOCKED by hook
  tool_result: "Destructive rm -rf is blocked by policy hook"
  Claude: "The command was blocked by a policy hook..."

Test 2: echo → ALLOWED
  [PostToolUse hook] tool=Bash — result available for normalization
  Claude: "The command ran successfully and output: hooks work!"
```

**Exam takeaways:**
- `PreToolUse` hook with `permissionDecision: "deny"` = deterministic block
- `PostToolUse` hook fires after tool execution — use to normalize/trim results
- Hooks are **deterministic** (100%); prompt instructions are **probabilistic** (~90%)
- **Rule:** use hooks for financial limits, safety rules, compliance — NOT prompts
- `hookSpecificOutput.hookEventName` must match the hook type

---

### ✅ `decomposition` — Fixed Pipeline (Objective 1.6)

**Command:** `python domain1_agent_architecture.py decomposition`

**What it tests:** Sequential fixed pipeline (2-step: Read → Summarize).

**Exam takeaways:**
- **Fixed pipeline** = steps defined in advance; use for predictable repeatable tasks
- **Dynamic adaptive** = next step generated from intermediate results; for open-ended tasks
- Multi-pass code review: per-file pass → cross-file integration pass
- ❌ WRONG: All 14 files in one prompt (attention dilution)
- ✅ RIGHT: File-by-file analysis, then separate integration pass

---

## Domain 2: Tool Design and MCP Integration (18%)

### ✅ `mcp_server` — In-Process MCP Server (Objective 2.4)

**Command:** `python domain2_tool_design.py mcp_server`

**Output observed:**
```
TOOL USE: mcp__calc__add({'a': 15, 'b': 27})   → 42
TOOL USE: mcp__calc__multiply({'a': 42, 'b': 3}) → 126
```

**Exam takeaways:**
- `@tool` decorator defines in-process tool functions
- `create_sdk_mcp_server(name="calc", tools=[...])` = MCP server with no subprocess
- Tool naming: `mcp__{server_name}__{tool_name}` (double underscores)
- In allowed_tools: `"mcp__calc__add"` (must match exactly)
- `ToolSearch` is called first — Claude Code loads schema dynamically

---

### ✅ `mcp_errors` — Structured Error Responses (Objective 2.2)

**Command:** `python domain2_tool_design.py mcp_errors`

**Output observed:**
- `ORD-TIMEOUT` (transient, retryable=True) → Claude says "retry after 2 seconds"
- `ORD-DENIED` (permission, retryable=False) → Claude says "escalate"

**Exam takeaways:**
- `is_error: True` in tool return = MCP `isError: true`
- Structured error fields: `errorCategory`, `isRetryable`, `message`, `attempted_query`
- **Transient** → retry with exponential backoff
- **Permission** → escalate, do not retry
- ❌ ANTI-PATTERN: `{"isError": true, "content": "Operation failed"}` — no recovery signal
- ✅ BEST PRACTICE: Full structured error with category + retryability + alternatives

---

### ✅ `tool_choice` — tool_choice Modes (Objective 2.3)

**Command:** `python domain2_tool_design.py tool_choice`

**Exam takeaways:**
- `tool_choice: "auto"` = model decides tool vs text answer
- `tool_choice: "any"` = model MUST call some tool (guarantees structured output)
- `tool_choice: {"type":"tool","name":"..."}` = forced specific tool (deterministic first step)
- **Use "any" when:** you need structured output regardless of what the model would prefer
- **Use forced when:** you need a specific first action (e.g., `extract_metadata` before enrichment)

---

### ✅ `builtin_tools` — Built-in Tool Selection (Objective 2.5)

**Command:** `python domain2_tool_design.py builtin_tools`

**Exam takeaways:**
```
Grep  → Search WITHIN file contents (function names, imports, error messages)
Glob  → Find files BY NAME/EXTENSION pattern (e.g., **/*.test.tsx)
Read  → Load FULL FILE for analysis
Edit  → PRECISE change via unique text match (fallback: Read + Write if match non-unique)
Bash  → Shell commands: git, npm, test runners, build
```
- Incremental strategy: Grep entry points → Read files → Grep usages → Read consumers
- ❌ WRONG: Read all 15 files at once to understand a module
- ✅ RIGHT: Grep for entry point → Read relevant files incrementally

---

## Domain 3: Claude Code Configuration and Workflows (20%)

### ✅ `claude_md` — CLAUDE.md Hierarchy (Objective 3.1)

**Command:** `python domain3_claude_code.py claude_md`

**Output observed:**
```
Claude: "This CLAUDE.md is a project-level file because it lives at the root of 
the claude-agent-sdk-python-main/ repository — not in ~/.claude/ (user-level) 
or inside a subdirectory (directory-level)..."
```

**Exam takeaways:**
```
~/.claude/CLAUDE.md           → User-level: personal, NOT in VCS
.claude/CLAUDE.md             → Project-level: team-wide, IN VCS ← most important
<subdir>/CLAUDE.md            → Directory-level: subtree-specific, IN VCS
```
- `@path` syntax: `@./standards/coding-style.md` — max depth 5
- ❌ TRAP: Team puts standards in `~/.claude/CLAUDE.md` → new members miss them
- `.claude/rules/` vs directory CLAUDE.md: use rules/ when conventions span many dirs

---

### ✅ `skills` — AgentDefinition as Skill (Objective 3.2)

**Command:** `python domain3_claude_code.py skills`

**Exam takeaways:**
```
Skill frontmatter       → SDK equivalent
context: fork           → AgentDefinition (runs isolated from main session)
allowed-tools: [...]    → AgentDefinition.tools = ["Read", "Grep"]
argument-hint: "..."    → System prompt: "ask user for parameter if not given"
```
- Project commands → `.claude/commands/` (VCS, team-wide)
- User commands → `~/.claude/commands/` (personal, not shared)
- Personal skill variant → `~/.claude/skills/different-name/` (doesn't affect teammates)

---

### ✅ `path_rules` — Path-Specific Rules (Objective 3.3)

**Command:** `python domain3_claude_code.py path_rules`

**Exam takeaways:**
```yaml
# .claude/rules/testing.md
---
paths: ["**/*.test.py", "**/*_test.py"]
---
Tests must use pytest with describe-style naming
```
- Rule loads **only** when editing a file matching the `paths` glob
- Saves context and tokens — irrelevant rules aren't loaded
- **Use `paths` rules when:** convention applies to files in many directories (tests, migrations)
- **Use directory CLAUDE.md when:** convention is tied to one specific directory

---

### ✅ `cicd` — CI/CD Integration (Objective 3.6)

**Command:** `python domain3_claude_code.py cicd`

**Output observed:**
```
Raw CI output: {"findings":[{"file":"...quick_start.py","line":"63","issue":"AttributeError risk..."},...]}
```

**Exam takeaways:**
- `-p` flag (CLI) / `query()` (SDK) = non-interactive headless mode
- `--output-format json` + `--json-schema` = structured CI output for inline PR comments
- **Session isolation:** fresh session for code review = independent perspective
  - Same session that wrote code is biased (retains its reasoning context)
- **Duplicate comment prevention:** include prior review results; report only new/unresolved issues
- CLAUDE.md provides project context (testing standards, review criteria) in CI runs

---

## Domain 4: Prompt Engineering and Structured Output (20%)

### ✅ `few_shot` — Few-Shot Prompting (Objective 4.2)

**Command:** `python domain4_prompt_engineering.py few_shot`

**Output observed:**
```
Input: 'Add a couple tablespoons of olive oil'
→ {"amount": "~30ml", "original_text": "a couple tablespoons", "precision": "approximate"}

Input: 'I am so frustrated, this is outrageous!'
→ Action: escalate_immediately (reasoning: intense emotion, no actionable request)
```

**Exam takeaways:**
- 2-4 examples beat vague instructions like "be more precise"
- Few-shot shows the exact format AND the decision logic, not just what to do
- Model **generalizes** the pattern — doesn't just repeat the examples
- **Use few-shot for:** ambiguous scenarios, exact output format, informal measurements
- Informal measurements especially benefit: "a handful", "a pinch" — too diverse for rules

---

### ✅ `structured_output` — tool_use + JSON Schema (Objective 4.3)

**Command:** `python domain4_prompt_engineering.py structured_output`

**Exam takeaways:**
- `tool_use` + JSON schema = **syntactic** validity guaranteed (no missing braces)
- **Semantic** errors still possible: wrong value in field, arithmetic mismatch, hallucination
- `type: ["string", "null"]` = nullable field → prevents hallucination of absent data
- `enum + "other" + detail_field` = extensible without data loss
- ❌ WRONG: "tool_use guarantees the values are correct"
- ✅ RIGHT: "tool_use guarantees the JSON is structurally valid"

---

### ✅ `retry_loop` — Validation + Retry (Objective 4.4)

**Command:** `python domain4_prompt_engineering.py retry_loop`

**What it tests:** Extract → validate arithmetic → retry with specific error context.

**Exam takeaways:**
- Retry IS effective for: format errors (wrong date format), arithmetic inconsistencies
- Retry IS NOT effective for: information absent from source document
- Retry prompt must include: original document + previous wrong extraction + specific error
- Pydantic-style semantic validation: `sum(line_items) == stated_total`

---

### ✅ `self_correction` — conflict_detected (Objective 4.5)

**Command:** `python domain4_prompt_engineering.py self_correction`

**Output observed:**
```json
{"stated_total": 150.0, "calculated_total": 145.0, "conflict_detected": true, ...}
```

**Exam takeaways:**
- Extract BOTH `stated_total` and `calculated_total` in the schema
- `conflict_detected: true` lets you handle discrepancy explicitly
- ❌ WRONG: Trust the stated total without verification
- ✅ RIGHT: Extract both, compare, flag conflict, let downstream decide

---

### ✅ `explicit_criteria` — Explicit vs Vague (Objective 4.1)

**Command:** `python domain4_prompt_engineering.py explicit_criteria`

**Exam takeaways:**
- Vague: "Check code for issues. Be conservative." → high false-positive rate
- Explicit: "Flag ONLY if comment contradicts code behavior" → low false-positive rate
- High false-positive rates in some categories erode developer trust in ALL categories
- **Define severity with CODE EXAMPLES**, not just labels
- Temporal fix: temporarily disable high-false-positive categories while tuning

---

## Domain 5: Context Management and Reliability (15%)

### ✅ `context_facts` — Facts Block Survives Summarization (Objective 5.2)

**Command:** `python domain5_context_reliability.py context_facts`

**Exam takeaways:**
- `/compact` (history compression) loses exact numbers, dates, IDs — they become "about", "roughly"
- Fix: structured CASE FACTS block prepended to every prompt
- Block includes: customer_id, order_id, order_date, order_amount, issue, status
- Block is regenerated from authoritative data, not from compressed history

---

### ✅ `trim_results` — PostToolUse Trim (Objective 5.3)

**Command:** `python domain5_context_reliability.py trim_results`

**Output observed:**
```
[PostToolUse trim_hook] Keeping: order_id, status, total, items, return_eligible
```

**Exam takeaways:**
- `lookup_order` returns 40+ fields; agent needs 5
- PostToolUse hook intercepts result before model consumes it
- Trim to relevant fields = saves context = reduces noise in model reasoning
- Pattern used in production: filter out warehouse_id, tracking_number, packaging_weight, etc.

---

### ✅ `escalation` — Structured Handoff (Objective 5.5)

**Command:** `python domain5_context_reliability.py escalation`

**Output observed:**
```json
{
  "customer_id": "CUST-12345",
  "issue_summary": "Order ORD-67890 arrived damaged...",
  "actions_taken": ["Acknowledged complaint", "Apologized", "Escalated per request"],
  "escalation_reason": "Customer explicitly requested manager",
  "recommended_action": "Review for damage claim, assess refund eligibility"
}
```

**Exam takeaways:**
```
Trigger                              → Action
"Get me a manager"                   → IMMEDIATE escalation (do NOT attempt to solve first)
Policy gap (competitor price match)  → escalate
Financial threshold exceeded         → hook enforcement (not prompt)
First expression of frustration      → acknowledge → offer resolution → escalate only on reiteration
Model confidence 3/10               → NOT a trigger (model calibration is unreliable)
```
- Human operator has NO access to conversation transcript
- Handoff must be **self-contained**: customer_id, issue_summary, actions_taken, escalation_reason

---

### ✅ `error_categories` — Error Taxonomy (Objective 5.6)

**Command:** `python domain5_context_reliability.py error_categories`

**Output observed:**
```
transient  → "retry after 2 seconds (isRetryable: true)"
validation → "fix input format, retry as ORD-67890"
business   → "escalate to senior agent (exceeds $500 limit)"
permission → "escalate to human/higher-privileged system"
```

**Exam takeaways:**
```
Category    | Retryable | Agent Action
transient   | YES       | Retry with exponential backoff (timeout, 503)
validation  | fix input | Modify request, retry (wrong format)
business    | NO        | Explain, propose alternative (policy violation)
permission  | NO        | Escalate to human (access denied)
```
- Anti-patterns: generic "search unavailable" (no recovery signal), silent suppression (empty = success)
- Subagent: 1-2 local retries for transient, then propagate to coordinator

---

### ✅ `provenance` — Claim-to-Source Link (Objective 5.7)

**Command:** `python domain5_context_reliability.py provenance`

**Output observed:**
```json
{
  "claim": "Share of AI-generated music on streaming platforms",
  "values": [
    {"value": "12%", "source": "Spotify Annual Report 2024", "methodology": "Automated classification"},
    {"value": "8%", "source": "Music Industry Survey 2024", "methodology": "Survey of 500 labels"}
  ],
  "conflict_detected": true,
  "possible_explanation": "Different methodologies and time periods"
}
```

**Exam takeaways:**
- ❌ WRONG: Arbitrarily choose one value and discard the other
- ✅ RIGHT: Preserve both with attribution; let coordinator decide
- Without dates: "10% vs 15%" may be a trend (+5% growth), not a contradiction
- Financial data → tables; News/analysis → prose; Technical findings → structured lists

---

### ✅ `state_persistence` — Crash Recovery + Coverage Annotations (Objective 5.8)

**Command:** `python domain5_context_reliability.py state_persistence`

**What it tests:** Coordinator reads manifest.json to resume after partial failure.

**Exam takeaways:**
- Each subagent writes to `agent-state/{name}.json`
- Coordinator reads `manifest.json` on startup: skip completed, resume partial
- Coverage annotations: FULL / PARTIAL (timeout) / NOT STARTED
- ⚠️ Note: always annotate gaps — don't silently omit failed sections
- Long investigations: agent writes to scratchpad file; loaded in new session instead of re-running discovery

---

## Quick-Reference Decision Matrix

```
HOOK OR PROMPT?
  Financial limit / safety / compliance  → HOOK (deterministic 100%)
  Style / general preference             → PROMPT (probabilistic ~90%)

TOOL_CHOICE?
  Normal operation                       → "auto"
  Must have structured output            → "any"
  Must call specific tool first          → {"type":"tool","name":"..."}

CLAUDE.MD LEVEL?
  All team members need it               → .claude/CLAUDE.md (project, VCS)
  Just me                                → ~/.claude/CLAUDE.md (user, NOT VCS)
  One directory only                     → subdir/CLAUDE.md (directory)
  Spans many directories                 → .claude/rules/ with paths frontmatter

PLANNING vs DIRECT?
  45+ files / architectural decision     → planning mode
  Clear single-file fix                  → direct execution

RETRY AFTER FAILURE?
  Format/arithmetic error                → YES (retry with error context)
  Missing info in source                 → NO (won't help)

ESCALATION TRIGGER?
  "Get me a manager"                     → IMMEDIATE
  First frustration expression           → NO → acknowledge → resolve → escalate on reiteration
  Model confidence low                   → NOT a trigger (unreliable)
  Amount > threshold                     → HOOK enforcement (not prompt)
```
