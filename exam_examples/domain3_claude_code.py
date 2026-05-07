#!/usr/bin/env python3
"""Domain 3 (20%): Claude Code Configuration and Workflows.

Exam objectives covered:
  3.1 CLAUDE.md hierarchy — user / project / directory levels; @path imports
  3.2 Custom slash commands and Skills (context:fork, allowed-tools, argument-hint)
  3.3 Path-specific rules (.claude/rules/ with YAML frontmatter paths)
  3.4 Planning mode vs direct execution — when to use each
  3.5 Iterative refinement — few-shot examples, interview pattern, test-driven
  3.6 CI/CD integration — -p flag, --output-format json, session isolation

Scenario: Code Generation with Claude Code (Scenario 2)
         + Claude Code for CI/CD (Scenario 5)

Usage:
  uv run python domain3_claude_code.py
  uv run python domain3_claude_code.py <example>
    examples: claude_md, skills, path_rules, planning, refinement, cicd
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from bedrock_config import EXAM_DIR as BASE, SDK_DIR, bedrock_options

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def print_msg(msg: Any) -> None:
    if isinstance(msg, AssistantMessage):
        for b in msg.content:
            if isinstance(b, TextBlock):
                print(f"  Claude: {b.text[:400]}")
            elif isinstance(b, ToolUseBlock):
                print(f"  [tool_use] {b.name}")
    elif isinstance(msg, ResultMessage):
        cost = f"  cost=${msg.total_cost_usd:.4f}" if msg.total_cost_usd else ""
        print(f"  [done]{cost}")


# ===========================================================================
# Objective 3.1 — CLAUDE.md hierarchy
# user > project > directory; @path for modular imports
# ===========================================================================

async def demo_claude_md() -> None:
    """Objective 3.1: CLAUDE.md 3-level hierarchy and @path imports.

    Hierarchy (lower overrides higher for conflicts):
      1. User:      ~/.claude/CLAUDE.md  — personal, NOT shared via VCS
      2. Project:   .claude/CLAUDE.md    — team-wide, IN VCS
      3. Directory: <subdir>/CLAUDE.md   — subtree-specific, IN VCS

    @path syntax: @./standards/coding-style.md (max nesting depth: 5)

    Common exam trap: placing team standards in user-level CLAUDE.md means
    new team members miss them.
    """
    print("\n=== 3.1 CLAUDE.md Hierarchy ===")

    # Read the SDK's CLAUDE.md by absolute path — no cwd needed
    claude_md_path = SDK_DIR / "CLAUDE.md"
    opts = bedrock_options(
        allowed_tools=["Read"],
        max_turns=3,
    )

    prompt = (
        f"1. Read {claude_md_path}\n"
        "2. Explain its hierarchy level (user/project/directory) and why.\n"
        "3. What would happen if a new team member's @path file was missing?\n"
        "Keep your answer to 5 sentences max."
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 3.2 — Custom skills and slash commands
# context:fork isolates verbose output; allowed-tools restricts access
# ===========================================================================

async def demo_skills() -> None:
    """Objective 3.2: AgentDefinition mirrors Skill frontmatter concepts.

    Skill frontmatter maps to SDK:
      context: fork  → AgentDefinition runs in isolated context
      allowed-tools  → AgentDefinition.tools = ["Read", "Grep"]
      argument-hint  → prompt instructs agent to ask for parameter

    Project commands: .claude/commands/ (VCS, team-wide)
    User commands:    ~/.claude/commands/ (personal, not shared)
    """
    print("\n=== 3.2 Skills — isolated subagent (context:fork equivalent) ===")

    from claude_agent_sdk import AgentDefinition

    # AgentDefinition with restricted tools = Skill with allowed-tools frontmatter
    opts = bedrock_options(
        agents={
            # This agent mirrors a Skill with context:fork + allowed-tools
            "code-analyzer": AgentDefinition(
                description="Analyzes code structure — isolated from main session",
                prompt=(
                    "You are a code structure analyzer. "
                    "Use ONLY Read and Grep. Do NOT write or modify any files. "
                    "Report: imports used, function count, and main purpose in 3 sentences."
                ),
                tools=["Read", "Grep"],
            ),
        },
        max_turns=5,
    )

    # Invoke the isolated subagent — verbose output doesn't pollute main session
    quick_start = SDK_DIR / "examples" / "quick_start.py"
    prompt = f"Use the 'code-analyzer' agent to analyze {quick_start}"

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 3.3 — Path-specific rules (.claude/rules/ with paths frontmatter)
# Rules load ONLY when editing matching files — saves context and tokens
# ===========================================================================

async def demo_path_rules() -> None:
    """Objective 3.3: path-specific rule files.

    .claude/rules/ file with frontmatter:
      ---
      paths: ["**/*.test.ts", "**/*.test.tsx"]
      ---
      Tests must use describe/it blocks.

    The rule loads ONLY when editing a matching file.
    vs. directory-level CLAUDE.md: use rules/ when convention spans many dirs.
    """
    print("\n=== 3.3 Path-Specific Rules ===")

    # Create a demo rules directory to illustrate the concept
    rules_dir = BASE / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    testing_rule = rules_dir / "testing.md"
    testing_rule.write_text(
        "---\n"
        'paths: ["**/*.test.py", "**/*_test.py"]\n'
        "---\n\n"
        "# Testing Rules (loaded only for test files)\n"
        "- Tests must use pytest with describe-style naming\n"
        "- Use data factories, not hardcoded fixtures\n"
        "- Never mock the database — use a test database\n",
        encoding="utf-8",
    )

    api_rule = rules_dir / "api-conventions.md"
    api_rule.write_text(
        "---\n"
        'paths: ["src/api/**/*", "**/routes/**/*"]\n'
        "---\n\n"
        "# API Rules (loaded only for API files)\n"
        "- Use async/await with explicit error handling\n"
        "- Each endpoint must return a standard response wrapper\n",
        encoding="utf-8",
    )

    opts = bedrock_options(
        allowed_tools=["Read"],
        max_turns=3,
    )

    prompt = (
        f"Read the rule files at {testing_rule} and {api_rule}. "
        "Explain: when does each rule load, and why is this 'paths' pattern "
        "better than a monolithic CLAUDE.md for conventions that span many directories?"
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 3.4 — Planning mode vs direct execution
# Planning = safe exploration, no side effects; Direct = single clear fix
# ===========================================================================

async def demo_planning() -> None:
    """Objective 3.4: planning mode vs direct execution.

    Planning mode (permission_mode='plan'):
      - Uses Read, Grep, Glob to explore
      - Produces a plan for user approval
      - NO writes/edits/bash side-effects
      - Use for: large changes, multiple approaches, architectural decisions

    Direct execution:
      - Use for: single-file fix with clear stack trace, one validation check
    """
    print("\n=== 3.4 Planning Mode vs Direct Execution ===")

    # Plan-only mode — Claude explores but makes no changes
    # Read types.py by absolute path to avoid SDK's ruff hook on cwd
    types_file = SDK_DIR / "src" / "claude_agent_sdk" / "types.py"
    opts_plan = bedrock_options(
        permission_mode="plan",
        allowed_tools=["Read", "Grep", "Glob"],
        max_turns=5,
    )

    print("  PLANNING MODE (no writes/edits):")
    plan_prompt = (
        f"Plan (do NOT implement) how you would add a retry_count parameter to "
        f"ClaudeAgentOptions. Read {types_file} first, "
        "then output a numbered implementation plan."
    )

    async for msg in query(prompt=plan_prompt, options=opts_plan):
        print_msg(msg)


# ===========================================================================
# Objective 3.5 — Iterative refinement
# Concrete examples > vague instructions; interview pattern; test-driven
# ===========================================================================

async def demo_refinement() -> None:
    """Objective 3.5: iterative refinement with examples.

    Most effective techniques:
    1. Few-shot examples (show input → output) — beats vague instructions
    2. Interview pattern — Claude asks clarifying questions first
    3. Test-driven — write tests first, iterate on failures
    """
    print("\n=== 3.5 Iterative Refinement ===")

    # Technique: few-shot examples are clearer than vague instructions
    opts = bedrock_options(max_turns=2)

    few_shot_prompt = (
        "Extract price data from text. Use EXACTLY this format:\n\n"
        "EXAMPLE 1:\n"
        "Input: 'The widget costs five bucks'\n"
        "Output: {\"amount\": 5, \"currency\": \"USD\", \"original_text\": \"five bucks\"}\n\n"
        "EXAMPLE 2:\n"
        "Input: 'Prix: 42,50 EUR'\n"
        "Output: {\"amount\": 42.50, \"currency\": \"EUR\", \"original_text\": \"42,50 EUR\"}\n\n"
        "Now extract from: 'The subscription is twenty dollars per month'"
    )

    async for msg in query(prompt=few_shot_prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 3.6 — CI/CD integration
# -p flag for non-interactive; session isolation for independent review
# ===========================================================================

async def demo_cicd() -> None:
    """Objective 3.6: CI/CD patterns.

    Key CI/CD rules:
    - Use ClaudeAgentOptions(max_turns=1) for headless/non-interactive mode
      (equivalent to claude -p flag)
    - New ClaudeSDKClient() per review = session context isolation
      (same session that wrote code is biased; use independent instance)
    - Structured output via JSON for inline PR comment posting
    - Include prior review results to avoid duplicate comments

    Session isolation: the model that wrote code retains its reasoning
    context and is less likely to challenge its own decisions.
    Use a FRESH session for code review.
    """
    print("\n=== 3.6 CI/CD — session isolation + structured output ===")

    # Simulate CI/CD: single-task, structured JSON output.
    # max_turns=3: tool_call + tool_result + final_answer (tool use needs >1 turn)
    # In actual CI the -p flag (non-interactive) is the key concept, not max_turns.
    opts = bedrock_options(
        allowed_tools=["Read", "Grep"],
        max_turns=3,
        # cwd defaults to /tmp (WSL2: CLI must start from Linux path)
    )

    target_file = SDK_DIR / "examples" / "quick_start.py"

    # CI prompt: explicit criteria, structured output, no vague instructions
    ci_prompt = (
        f"Review the file {target_file} for issues. "
        "Output ONLY valid JSON matching this schema exactly:\n"
        '{"findings": [{"file": "string", "line": "string", '
        '"issue": "string", "severity": "critical|high|medium|low", '
        '"suggested_fix": "string"}], "summary": "string"}\n'
        "If no issues, return: {\"findings\": [], \"summary\": \"No issues found\"}"
    )

    issues_found = []
    async for msg in query(prompt=ci_prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    raw = b.text.strip()
                    print(f"  Raw CI output: {raw[:200]}")
                    try:
                        parsed = json.loads(raw)
                        issues_found = parsed.get("findings", [])
                        print(f"  Parsed: {len(issues_found)} findings")
                        for f in issues_found:
                            print(f"    [{f.get('severity','?')}] {f.get('issue','')}")
                    except json.JSONDecodeError:
                        print("  (response is prose, not JSON — add schema enforcement in prod)")
        elif isinstance(msg, ResultMessage):
            pass

    print(f"  CI review complete. Total issues: {len(issues_found)}")
    print("  In real CI: post each finding as inline PR comment via GitHub API")


# ===========================================================================
# Main
# ===========================================================================

async def main() -> None:
    examples = {
        "claude_md": demo_claude_md,
        "skills": demo_skills,
        "path_rules": demo_path_rules,
        "planning": demo_planning,
        "refinement": demo_refinement,
        "cicd": demo_cicd,
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
