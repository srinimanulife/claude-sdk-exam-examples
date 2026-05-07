# Python vs TypeScript SDK — Exam Objective Coverage

> **Both SDKs expose the same Claude Code CLI subprocess**; they differ in
> language idioms, available examples, and ecosystem integration — not in what
> the underlying agent can do.

---

## TL;DR — Which SDK for the exam?

- **Python examples** (`claude-agent-sdk-python-main/examples/`) cover **all 5
  domains** of the exam. Start here for comprehensive study.
- **TypeScript examples** (`claude-agent-sdk-typescript-main/examples/`) cover
  **only `SessionStore` adapters** (D5.8, with resume / error-handling
  corollaries). Useful for deep-diving session persistence and comparing how
  the same contract is implemented in TS.
- **The exam is SDK-language-agnostic**. Questions are about *concepts* (hooks
  vs prompts, `tool_choice` modes, CLAUDE.md hierarchy, planning mode,
  structured output) — both SDKs expose the same primitives under different
  names.

---

## Example Inventory — Side by Side

| Capability | Python example | TypeScript example | Exam domain |
|------------|---------------|--------------------|-------------|
| `query()` basics, options | `quick_start.py` | — (see README snippets) | D1.1 |
| AgentDefinition, multi-agent | `agents.py` | — | D1.2, D1.3 |
| Hooks (PreToolUse / PostToolUse / UserPromptSubmit) | `hooks.py` | — | D1.4, D1.5 |
| Streaming multi-turn, interrupt | `streaming_mode.py`, `streaming_mode_ipython.py`, `streaming_mode_trio.py` | — | D1.1, D1.7 |
| Include partial messages | `include_partial_messages.py` | — | D1.1 |
| MCP server (`@tool`, `create_sdk_mcp_server`) | `mcp_calculator.py` | — | D2.4 |
| `tools` option / permission callback | `tools_option.py`, `tool_permission_callback.py` | — | D2.3 |
| Filesystem agents (`.claude/agents/`) | `filesystem_agents.py` | — | D3.2 |
| Setting sources (user / project / local) | `setting_sources.py` | — | D3.1 |
| System prompt | `system_prompt.py` | — | D1, D4 |
| Max budget USD | `max_budget_usd.py` | — | D5.5 |
| Plugin example | `plugin_example.py`, `plugins/` | — | D3.2 |
| Stderr callback | `stderr_callback_example.py` | — | D5.6 |
| **SessionStore: S3** | `session_stores/s3_session_store.py` | `session-stores/s3/` | D5.8 |
| **SessionStore: Redis** | `session_stores/redis_session_store.py` | `session-stores/redis/` | D5.8 |
| **SessionStore: Postgres** | `session_stores/postgres_session_store.py` | `session-stores/postgres/` | D5.8 |
| **Conformance suite** | `claude_agent_sdk.testing.run_session_store_conformance` | `session-stores/shared/conformance.ts` (vendored) | D5.8 |

**Gap**: The TypeScript repo intentionally ships *only* session-store
examples — "the SDK package stays free of heavyweight optional dependencies".
For every other exam objective, reach for the Python examples.

---

## Per-Domain — Which SDK's examples help?

### Domain 1: Agent Architecture and Orchestration (27%)

| Objective | Python | TypeScript | Notes |
|-----------|--------|-----------|-------|
| 1.1 Agentic loops | ✅ `streaming_mode.py` | Partial — demo.ts in each store | Concept same; `for await` replaces `async for` |
| 1.2 Coordinator + subagents | ✅ `agents.py` | ❌ | TS uses `AgentDefinition` identically — no example |
| 1.3 Context passing / Task tool | ✅ `domain1_agent_architecture.py` `demo_multi_agent` | ❌ | Same rule: pass context explicitly |
| 1.4 Workflow enforcement | ✅ `hooks.py` | ❌ | `HookMatcher` shape differs — same semantics |
| 1.5 Hooks (Pre/PostToolUse) | ✅ `hooks.py` | ❌ | TS signature: `(input, toolUseId, options) => Promise<HookOutput>` |
| 1.6 Task decomposition | ✅ Python domain file | ❌ | Pure prompt pattern — SDK-agnostic |
| 1.7 Session management | ✅ `streaming_mode.py` | ✅ `session-stores/*/demo.ts` | TS examples focused on resume via sessionStore |

**Verdict**: **Python-first for D1.** Only D1.7 is demonstrated in TS.

### Domain 2: Tool Design and MCP Integration (18%)

| Objective | Python | TypeScript | Notes |
|-----------|--------|-----------|-------|
| 2.1 Tool description quality | ✅ `domain2_tool_design.py` | ❌ | Pure prompt/metadata — applies identically |
| 2.2 Structured MCP errors | ✅ `domain2_tool_design.py` | ❌ | `{ isError: true, errorCategory, isRetryable }` shape is wire-level |
| 2.3 `tool_choice` modes | ✅ `tools_option.py`, `tool_permission_callback.py` | ❌ | TS `canUseTool` = Python `can_use_tool` |
| 2.4 In-process MCP server | ✅ `mcp_calculator.py` | ❌ | TS: `createSdkMcpServer({ name, version, tools: [tool(...)] })` |
| 2.5 Built-in tool selection | ✅ Python domain file | ❌ | CLI-level — SDK-agnostic |

**Verdict**: **Python-only for D2 examples.** The TS API exists (`createSdkMcpServer`, `tool`), just no demo files.

### Domain 3: Claude Code Configuration and Workflows (20%)

| Objective | Python | TypeScript | Notes |
|-----------|--------|-----------|-------|
| 3.1 CLAUDE.md hierarchy | ✅ `setting_sources.py` | ❌ | File-layout concept; SDK-agnostic |
| 3.2 Custom skills / commands | ✅ `plugin_example.py`, `filesystem_agents.py` | ❌ | `.claude/agents/`, `.claude/skills/` same on both |
| 3.3 Path-specific rules | ✅ Python domain file | ❌ | `.claude/rules/` YAML frontmatter — filesystem |
| 3.4 Planning vs direct execution | ✅ Python domain file | ❌ | `permissionMode: 'plan'` in both SDKs |
| 3.5 Iterative refinement | ✅ Python domain file | ❌ | Prompt pattern |
| 3.6 CI/CD integration | ✅ Python domain file | ❌ | `--print` / headless — CLI-level |

**Verdict**: **Python-only for D3 examples.** These are file-system and
CLI-level concepts — either SDK is fine in production; only Python ships demos.

### Domain 4: Prompt Engineering and Structured Output (20%)

| Objective | Python | TypeScript | Notes |
|-----------|--------|-----------|-------|
| 4.1 Explicit criteria | ✅ `domain4_prompt_engineering.py` | ❌ | Prompt pattern |
| 4.2 Few-shot prompting | ✅ Python domain file | ❌ | Prompt pattern |
| 4.3 Structured output (tool_use / zod) | ✅ Python domain file | ⚠️ CHANGELOG 0.1.45 | TS uses `zod` for schemas; see CHANGELOG "Structured outputs support" |
| 4.4 Validation + retry loop | ✅ Python domain file | ⚠️ Conformance + `append()` retry (0.2.119) | Retry-with-backoff is built in for sessionStore writes |
| 4.5 Self-correction | ✅ Python domain file | ❌ | Prompt pattern |
| 4.6 Prompt chaining | ✅ Python domain file | ❌ | Prompt pattern |
| 4.7 Interview pattern | ✅ Python domain file | ❌ | Prompt pattern |

**Verdict**: **Python-first for D4.** TS SDK *supports* structured output (via
`zod` peer dep, CHANGELOG 0.1.45 / 0.2.23) but ships no standalone example.

### Domain 5: Context Management and Reliability (15%)

| Objective | Python | TypeScript | Notes |
|-----------|--------|-----------|-------|
| 5.1 Context window management | ✅ Python domain file | ❌ | `getContextUsage()` exists in both (CHANGELOG 0.2.86, 0.2.94) |
| 5.2 Key facts block | ✅ Python domain file | ❌ | Prompt pattern |
| 5.3 Trim tool results | ✅ Python domain file (PostToolUse hook) | ❌ | Hook shape TS-side is the same |
| 5.4 Position-aware input | ✅ Python domain file | ❌ | Prompt pattern |
| 5.5 Escalation patterns | ✅ `max_budget_usd.py` + domain file | ❌ | Budget callback in both SDKs |
| 5.6 Error categories | ✅ `stderr_callback_example.py` | ✅ `SDKMirrorErrorMessage` (CHANGELOG 0.2.113, 0.2.119) | TS has first-class mirror-error type |
| 5.7 Provenance preservation | ✅ Python domain file | ❌ | Prompt pattern |
| **5.8 State persistence** | ✅ `session_stores/*` | ✅ **`session-stores/*` (full parity)** | **Only domain where TS examples are as strong as Python** |

**Verdict**: **Parity on D5.8; Python-first elsewhere.**

---

## When to use TypeScript vs Python Agent SDK (production)

### Choose **TypeScript** when:

1. **You're embedding into a Node/Bun/browser-backend app already.** Shared
   types with a TS frontend, Zod schemas, native `async`/streaming idioms.
2. **You want the S3/Redis/Postgres adapters as *reference production code*.**
   The TS adapters are the canonical implementations — the Python equivalents
   reference them in READMEs.
3. **You need `zod`-validated structured outputs.** The TS SDK accepts Zod
   schemas directly (peer dep `^3.24.1` or `^4.0.0`).
4. **Your deploy target is serverless Node (Lambda, Cloudflare, Vercel).**
   Smaller cold-start and ecosystem fit.
5. **You're building a VS Code / web extension.** TS is the native surface.

### Choose **Python** when:

1. **You want the breadth of worked examples** — agents, hooks, MCP servers,
   plugins, streaming, filesystem agents all shipped and runnable.
2. **You're integrating with data/ML tooling** (pandas, Bedrock boto3,
   LangChain interop, Jupyter notebooks).
3. **You're running on Amazon Bedrock.** `bedrock_config.py` in this repo
   already wires `CLAUDE_CODE_USE_BEDROCK=1` and `us-west-2` — copy and go.
   (Bedrock works with TS too, via env vars, just no ready example.)
4. **The team's existing codebase is Python.** Mixed stacks cost more than
   the marginal benefit of the other SDK.
5. **You need `trio` or `anyio` for structured concurrency** —
   `streaming_mode_trio.py` shows the pattern.

### The two SDKs agree on (no need to choose):

- **CLI subprocess**: same `claude` binary, same `claude.ai`/Bedrock/Vertex
  backends, same transcript format on disk.
- **Concepts**: hooks, skills, slash commands, CLAUDE.md, planning mode,
  `tool_choice`, MCP servers, session resume, budget callbacks — all identical.
- **File-system artefacts**: `.claude/agents/*.md`, `.claude/skills/*`,
  `.claude/rules/*`, `CLAUDE.md` — shared; a TS client and a Python client
  will see the same project config.
- **SessionStore contract**: 13 identical behavioral tests; Python's
  `run_session_store_conformance` ≡ TS's `runSessionStoreConformance`.
  Adapters in either language can write to the **same** Postgres table (modulo
  schema alignment — see Python README's note that the Python schema uses
  `''`/`mtime bigint` while TS uses `NULL`/`TIMESTAMPTZ`).

---

## Concept → API Rosetta Stone

| Concept | Python | TypeScript |
|---------|--------|-----------|
| One-shot query | `query(prompt=..., options=ClaudeAgentOptions(...))` | `query({ prompt, options })` |
| Streaming client | `ClaudeSDKClient(...)` | n/a — `query()` is async-iterable |
| Options type | `ClaudeAgentOptions` | `Options` |
| Agent def | `AgentDefinition(description, prompt, tools, model)` | `AgentDefinition` (same fields) |
| Hook | `HookMatcher(matcher, hooks=[callable])` | `{ matcher, hooks: [(input, tid, opts) => ...] }` |
| MCP server | `create_sdk_mcp_server(name, version, tools=[tool(...)])` | `createSdkMcpServer({ name, version, tools: [tool(...)] })` |
| Tool helper | `@tool(name, description, input_schema)` decorator | `tool(name, description, zodSchema, handler)` |
| Permission callback | `can_use_tool` | `canUseTool` |
| Result message | `ResultMessage` (dataclass) | `{ type: 'result', subtype: 'success' \| 'error_*' }` |
| Session store | `SessionStore` Protocol | `SessionStore` interface |
| Conformance | `from claude_agent_sdk.testing import run_session_store_conformance` | `import { runSessionStoreConformance } from './conformance.ts'` (vendored) |
| Planning mode | `permission_mode='plan'` | `permissionMode: 'plan'` |
| Resume | `options.resume='<session-id>'` | `options: { resume: '<session-id>' }` |
| Fork session | `fork_session=True` (per CHANGELOG) | `forkSession(sessionId, opts?)` (CHANGELOG 0.2.76) |
| Budget cap | `max_budget_usd=...` | `maxBudgetUsd: ...` |
| Structured output | `output_format={...}` with JSON schema | Zod schema on `output_format` |
| Setting sources | `setting_sources=['user','project','local']` | `settingSources: ['user','project','local']` |
| Mirror error | `MirrorErrorMessage` | `SDKMirrorErrorMessage` (`subtype: 'mirror_error'`) |

---

## Exam study plan — combining both SDKs

1. **Read the Python `EXAM_MAP.md`** end to end — it maps every objective to
   a runnable example.
2. **Run one example per domain** in Python against Bedrock to build muscle
   memory (D1 hooks, D2 MCP server, D3 planning mode, D4 few-shot, D5 trim).
3. **For D5.8 specifically**, diff the Python and TS implementations:
   - S3 adapter: identical layout, identical ordering scheme, identical
     conformance contracts.
   - Redis adapter: identical key scheme, same `MULTI` pattern for append.
   - Postgres adapter: schemas **differ slightly** (see Python README line
     357 — Python uses `subpath text NOT NULL DEFAULT ''`, TS uses `subpath TEXT NULL`).
   - This diff is the clearest way to learn *what the contract actually
     requires* vs *what each language made ergonomic*.
4. **Skim `claude-agent-sdk-typescript-main/CHANGELOG.md`** — it's the
   fastest cross-reference for "what does this SDK feature look like in TS".
5. **Memorize the Rosetta Stone** above — exam questions may use either
   naming convention.

---

## Key exam traps specific to SDK choice

- ❌ "Only Python supports SessionStore" → ✅ Both do, with parity conformance.
- ❌ "Only TypeScript supports Zod / structured outputs" → ✅ Python has native
  JSON-schema support; `zod` is the TS-specific ergonomics layer.
- ❌ "Hooks are Python-only" → ✅ Hooks exist in both; only the callback
  signature differs.
- ❌ "Postgres sharing across SDKs just works" → ✅ **No** — the two reference
  schemas differ. Unify before sharing a table.
- ❌ "TS `sessionStore` is GA" → ✅ Marked **alpha** in CHANGELOG 0.2.113; stable
  contract but subject to iteration.
- ❌ "Pick the SDK that matches the exam language" → ✅ The exam tests
  concepts, not SDK syntax; pick by team/stack fit.
