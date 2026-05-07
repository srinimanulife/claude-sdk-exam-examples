#!/usr/bin/env python3
"""Domain 1 (27%): Agent Architecture and Orchestration.

Exam objectives covered:
  1.1 Agentic loops — stop_reason "tool_use" vs "end_turn"
  1.2 Coordinator + subagents (hub-and-spoke)
  1.3 Subagent context passing / spawning via Task tool
  1.4 Multi-step workflows with hooks-based enforcement
  1.5 Agent SDK hooks (PreToolUse / PostToolUse)
  1.6 Task decomposition: fixed pipelines vs dynamic adaptive
  1.7 Session management (resume / fork)

Scenario: Customer Support Agent (Scenario 1 from exam)
  — Agent handles returns, billing disputes, account issues.
  — Demonstrates the agentic loop, context passing, and hooks.

Usage:
  uv run python domain1_agent_architecture.py
  uv run python domain1_agent_architecture.py <example>
    examples: loop, multi_agent, hooks, decomposition
"""

import asyncio
import sys
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput, HookMatcher

from bedrock_config import SDK_DIR, bedrock_options

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_msg(msg: Any) -> None:
    if isinstance(msg, AssistantMessage):
        for b in msg.content:
            if isinstance(b, TextBlock):
                print(f"  Claude: {b.text[:200]}")
            elif isinstance(b, ToolUseBlock):
                print(f"  [tool_use] {b.name}({b.input})")
    elif isinstance(msg, UserMessage):
        for b in msg.content:
            if isinstance(b, ToolResultBlock):
                print(f"  [tool_result] {str(b.content)[:120]}")
    elif isinstance(msg, ResultMessage):
        cost = f"  cost=${msg.total_cost_usd:.4f}" if msg.total_cost_usd else ""
        print(f"  [done]{cost}")


# ===========================================================================
# Objective 1.1 — Agentic Loop
# stop_reason "tool_use" drives the loop; "end_turn" signals completion.
# The SDK handles this internally — here we observe the message stream.
# ===========================================================================

async def demo_agentic_loop() -> None:
    """Objective 1.1: observe the tool_use / end_turn cycle.

    Claude Code CLI implements the agentic loop: when stop_reason=="tool_use"
    it executes the tool and feeds the result back. We see AssistantMessage
    with ToolUseBlock, then UserMessage with ToolResultBlock, then the final
    AssistantMessage when stop_reason=="end_turn".
    """
    print("\n=== 1.1 Agentic Loop — observe tool_use → end_turn ===")
    opts = bedrock_options(
        allowed_tools=["Bash"],
        max_turns=3,
    )

    tool_uses = 0
    tool_results = 0

    async for msg in query(prompt="Run: echo 'loop demo' && pwd", options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    tool_uses += 1
                    print(f"  → stop_reason=tool_use: calling {b.name}")
        elif isinstance(msg, UserMessage):
            for b in msg.content:
                if isinstance(b, ToolResultBlock):
                    tool_results += 1
                    print(f"  ← tool_result returned to model")
        print_msg(msg)

    print(f"  Tool uses: {tool_uses}, Tool results fed back: {tool_results}")
    print("  Loop ended on stop_reason=end_turn")


# ===========================================================================
# Objective 1.2 / 1.3 — Coordinator + Subagents (hub-and-spoke)
# The coordinator defines subagents; context must be passed explicitly.
# ===========================================================================

async def demo_multi_agent() -> None:
    """Objectives 1.2 + 1.3: hub-and-spoke multi-agent system.

    Coordinator owns:
      - Task decomposition
      - Delegating to specialized subagents
      - Result aggregation

    Key principle: subagents have ISOLATED context — all required info
    must be explicitly included in the Task prompt.
    """
    print("\n=== 1.2/1.3 Multi-Agent (Coordinator + Subagents) ===")

    opts = bedrock_options(
        agents={
            # Subagent 1: codebase analyst
            "analyzer": AgentDefinition(
                description="Analyzes code structure and counts Python files",
                prompt=(
                    "You are a code structure analyst. "
                    "Use Glob and Grep to find Python files and count them. "
                    "Report ONLY: total count and top-level directories found."
                ),
                tools=["Glob", "Grep"],
            ),
            # Subagent 2: summarizer (gets explicit context from coordinator)
            "summarizer": AgentDefinition(
                description="Summarizes findings passed to it in the prompt",
                prompt=(
                    "You are a report writer. "
                    "You receive structured findings and produce a 2-sentence summary. "
                    "Do NOT use any tools — summarize the text provided."
                ),
                tools=[],
            ),
        },
        max_turns=10,
    )

    prompt = (
        "You are the coordinator. Do this in two explicit steps:\n"
        "STEP 1: Use the 'analyzer' subagent to count Python files under examples/. "
        "Pass it this cwd context: /mnt/c/projects/claude/claude-certified-architect-main/claude-agent-sdk-python-main\n"
        "STEP 2: Pass the analyzer's raw output to the 'summarizer' subagent. "
        "Include the full output — subagents have no memory of prior steps."
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 1.4 / 1.5 — Hooks: PreToolUse enforcement (deterministic)
# Hooks guarantee compliance; prompt instructions are probabilistic.
# ===========================================================================

async def _refund_guard(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PreToolUse hook: block any Bash command that mentions 'rm -rf'.

    Exam concept: hooks provide DETERMINISTIC enforcement.
    Use hooks (not prompt instructions) for financial/safety/legal rules.
    """
    if input_data.get("tool_name") == "Bash":
        cmd = input_data.get("tool_input", {}).get("command", "")
        if "rm -rf" in cmd:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Destructive rm -rf is blocked by policy hook",
                }
            }
    return {}


async def _log_tool_result(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PostToolUse hook: normalize/trim tool output.

    Exam concept: PostToolUse can trim noisy tool results before the model
    consumes them (e.g., keep only 5 of 40 returned fields).
    """
    tool_name = input_data.get("tool_name", "")
    print(f"  [PostToolUse hook] tool={tool_name} — result available for normalization")
    return {}


async def demo_hooks() -> None:
    """Objectives 1.4 + 1.5: hooks for deterministic policy enforcement."""
    print("\n=== 1.4/1.5 Hooks — Deterministic PreToolUse + PostToolUse ===")

    opts = bedrock_options(
        allowed_tools=["Bash"],
        hooks={
            "PreToolUse": [HookMatcher(matcher="Bash", hooks=[_refund_guard])],
            "PostToolUse": [HookMatcher(matcher="Bash", hooks=[_log_tool_result])],
        },
    )

    async with ClaudeSDKClient(options=opts) as client:
        # This should be BLOCKED by the hook
        print("  Test 1: attempt rm -rf /tmp/test (should be blocked by hook)")
        await client.query("Run this bash command: rm -rf /tmp/test_dir_that_does_not_exist")
        async for msg in client.receive_response():
            print_msg(msg)

        # This should be ALLOWED
        print("  Test 2: safe echo command (should be allowed)")
        await client.query("Run: echo 'hooks work!'")
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 1.6 — Task Decomposition: fixed pipeline vs adaptive
# ===========================================================================

async def demo_decomposition() -> None:
    """Objective 1.6: fixed pipeline vs dynamic adaptive decomposition.

    Fixed pipeline (prompt chaining):
      Step 1 → Step 2 → Step 3 (defined in advance, predictable)

    Dynamic decomposition:
      Model generates next steps from intermediate results.
    """
    print("\n=== 1.6 Task Decomposition — Fixed Pipeline ===")

    # Fixed pipeline: analyze one file, then summarize — predictable steps
    opts = bedrock_options(
        allowed_tools=["Read"],
        max_turns=5,
    )

    pipeline_prompt = (
        "Execute this FIXED 2-step pipeline:\n"
        f"STEP 1 (Read): Read the file {SDK_DIR}/examples/quick_start.py "
        "and list its imports.\n"
        "STEP 2 (Summarize): In one sentence, describe what the file does based on its imports.\n"
        "Output both steps clearly labeled."
    )

    async for msg in query(prompt=pipeline_prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Main
# ===========================================================================

async def main() -> None:
    examples = {
        "loop": demo_agentic_loop,
        "multi_agent": demo_multi_agent,
        "hooks": demo_hooks,
        "decomposition": demo_decomposition,
    }

    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "all":
        for fn in examples.values():
            await fn()
    elif arg in examples:
        await examples[arg]()
    else:
        print(f"Unknown: {arg}. Options: {list(examples)} or 'all'")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
