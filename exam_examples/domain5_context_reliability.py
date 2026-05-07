#!/usr/bin/env python3
"""Domain 5 (15%): Context Management and Reliability.

Exam objectives covered:
  5.1 Context window management — lost-in-middle, tool result accumulation
  5.2 Extract key facts into a separate block (survives summarization)
  5.3 Trim tool results via PostToolUse hook (keep relevant fields only)
  5.4 Position-aware input (key info at top/bottom, not middle)
  5.5 Escalation patterns — when to escalate, structured handoff
  5.6 Error categories and recovery — transient/validation/business/permission
  5.7 Provenance preservation — claim → source link across summarization
  5.8 Structured state persistence (crash recovery, coverage annotations)

Scenario: Customer Support Agent (Scenario 1) + Multi-Agent Research (Scenario 3)

Usage:
  uv run python domain5_context_reliability.py
  uv run python domain5_context_reliability.py <example>
    examples: context_facts, trim_results, position_aware, escalation,
              error_categories, provenance, state_persistence
"""

import asyncio
import json
import sys
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput, HookMatcher

from bedrock_config import bedrock_options

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
# Objective 5.1 / 5.2 — Context window management + facts block
# Extract key facts that survive /compact summarization
# ===========================================================================

async def demo_context_facts() -> None:
    """Objectives 5.1 + 5.2: key facts block survives history summarization.

    Problem: /compact (history compression) loses exact numbers, dates, IDs.
    Solution: extract critical facts to a dedicated block included in EVERY prompt.

    Exam concept:
    - Lost-in-the-middle effect: models reliably process start/end but miss middle
    - Tool results accumulate context — filter to relevant fields only
    - Progressive summarization loses numeric precision
    """
    print("\n=== 5.1/5.2 Context Facts Block ===")

    # This block is regenerated and prepended to each prompt
    # so critical data survives context compression
    CASE_FACTS_TEMPLATE = (
        "=== CASE FACTS (always included, survives summarization) ===\n"
        "Customer ID: {customer_id}\n"
        "Order ID: {order_id}\n"
        "Order Date: {order_date}\n"
        "Order Amount: {order_amount}\n"
        "Issue: {issue}\n"
        "Status: {status}\n"
        "=== END FACTS ==="
    )

    facts = {
        "customer_id": "CUST-12345",
        "order_id": "ORD-67890",
        "order_date": "2025-01-15",
        "order_amount": "$89.99",
        "issue": "Item arrived damaged",
        "status": "Awaiting resolution",
    }

    facts_block = CASE_FACTS_TEMPLATE.format(**facts)

    opts = bedrock_options(max_turns=1)

    prompt = (
        f"{facts_block}\n\n"
        "Given these case facts, draft a one-sentence escalation summary "
        "that includes the customer_id, order_id, and refund_amount. "
        "Show that the facts block preserves exact IDs."
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 5.3 — Trim tool results (PostToolUse hook)
# Keep only relevant fields; discard 35 of 40 returned fields
# ===========================================================================

FULL_ORDER_RESPONSE = {
    "order_id": "ORD-67890",
    "status": "shipped",
    "total": 89.99,
    "items": [{"name": "Widget", "qty": 1, "price": 89.99}],
    "return_eligible": True,
    # Noise fields we don't need:
    "warehouse_id": "WH-04",
    "shipping_carrier": "FedEx",
    "tracking_number": "1Z999AA10123456784",
    "packaging_weight_kg": 0.4,
    "packaging_dimensions": "30x20x10cm",
    "warehouse_pick_time": "2025-01-14T08:23:11Z",
    "last_scan_location": "Memphis TN Hub",
    "carrier_internal_ref": "FX-REF-999",
    "estimated_delivery": "2025-01-17",
    "insurance_value": 100.00,
    "customs_form": None,
    "is_hazmat": False,
    "fulfillment_partner": "3PL-West",
}


@tool(
    "lookup_order",
    "Returns full order record. Contains 40+ fields; use PostToolUse hook to trim.",
    {"order_id": str},
)
async def lookup_order_full(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(FULL_ORDER_RESPONSE)}]
    }


async def _trim_order_result(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """PostToolUse hook: keep only the 5 fields relevant to the support agent.

    Exam rule: trim tool results to conserve context window.
    40+ field response → 5 field response = significant token savings.
    """
    # In production this would parse and filter the actual tool response.
    # The hook API sends the raw tool output in input_data["tool_response"].
    print("  [PostToolUse trim_hook] Keeping: order_id, status, total, items, return_eligible")
    return {}


async def demo_trim_results() -> None:
    """Objective 5.3: PostToolUse hook trims noisy tool output."""
    print("\n=== 5.3 Trim Tool Results via PostToolUse Hook ===")

    order_server = create_sdk_mcp_server(name="orders", tools=[lookup_order_full])

    opts = bedrock_options(
        mcp_servers={"orders": order_server},
        allowed_tools=["mcp__orders__lookup_order"],
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="mcp__orders__lookup_order", hooks=[_trim_order_result])
            ],
        },
        max_turns=2,
    )

    async with ClaudeSDKClient(options=opts) as client:
        await client.query(
            "Look up order ORD-67890. Is it return eligible? "
            "Note the hook fires after the tool result."
        )
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 5.4 — Position-aware input (lost-in-middle mitigation)
# ===========================================================================

async def demo_position_aware() -> None:
    """Objective 5.4: lost-in-the-middle mitigation.

    Models reliably process START and END of context but miss the MIDDLE.
    Solution: put KEY FINDINGS at the top and ACTION ITEMS at the end.
    Detailed evidence goes in the middle (where it is less critical).
    """
    print("\n=== 5.4 Position-Aware Input (lost-in-middle mitigation) ===")

    opts = bedrock_options(max_turns=1)

    # Deliberately structured to test position-aware reading
    position_aware_prompt = (
        "[KEY FINDINGS — placed at START for reliability]\n"
        "Critical: auth.ts has SQL injection on line 42.\n"
        "Critical: database.ts missing input validation.\n\n"
        "[DETAILED EVIDENCE — middle (may be partially missed)]\n"
        + ("=" * 50 + "\n") * 3  # Simulate bulk middle content
        + "File analysis: 14 files reviewed...\n\n"
        "[ACTION ITEMS — placed at END for reliability]\n"
        "Priority 1: Fix auth.ts SQL injection before merge.\n"
        "Priority 2: Add validation to database.ts.\n\n"
        "Question: What are the top priorities? (Should match START and END.)"
    )

    async for msg in query(prompt=position_aware_prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 5.5 — Escalation patterns
# When to escalate; structured handoff with all context
# ===========================================================================

@tool(
    "escalate_to_human",
    (
        "Escalates the case to a human agent with a structured handoff summary. "
        "Required: customer_id, issue_summary, actions_taken[], escalation_reason. "
        "Call IMMEDIATELY when: customer explicitly requests a manager; "
        "policy does not cover the request; financial operation above $500 threshold."
    ),
    {
        "customer_id": str,
        "issue_summary": str,
        "actions_taken": list,
        "escalation_reason": str,
        "recommended_action": str,
    },
)
async def escalate_to_human(args: dict[str, Any]) -> dict[str, Any]:
    handoff = {
        "ticket_id": "TKT-9001",
        "assigned_to": "Senior Agent Queue",
        "handoff_data": args,
    }
    print(f"\n  [ESCALATION] Handoff: {json.dumps(handoff, indent=2)}")
    return {"content": [{"type": "text", "text": f"Escalated. Ticket: {handoff['ticket_id']}"}]}


async def demo_escalation() -> None:
    """Objective 5.5: escalation patterns and structured handoff.

    Immediate escalation triggers:
    - "Get me a manager" → escalate immediately, do NOT attempt to solve
    - Policy gap (competitor price match) → escalate
    - Financial operation above threshold → escalate (use hook, not prompt)

    Structured handoff must be self-contained:
    human operator has NO access to conversation transcript.
    """
    print("\n=== 5.5 Escalation Patterns + Structured Handoff ===")

    esc_server = create_sdk_mcp_server(name="support", tools=[escalate_to_human])

    opts = bedrock_options(
        mcp_servers={"support": esc_server},
        allowed_tools=["mcp__support__escalate_to_human"],
        max_turns=3,
        system_prompt=(
            "You are a customer support agent. "
            "Escalate IMMEDIATELY when the customer requests a manager. "
            "Include: customer_id, issue_summary, actions_taken, escalation_reason."
        ),
    )

    async with ClaudeSDKClient(options=opts) as client:
        await client.query(
            "Customer CUST-12345 says: 'I want to speak to a manager right now. "
            "My order ORD-67890 arrived damaged and I need a full refund immediately.'"
        )
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 5.6 — Error categories
# transient/validation/business/permission — different recovery for each
# ===========================================================================

async def demo_error_categories() -> None:
    """Objective 5.6: error category taxonomy drives recovery decisions.

    Transient  → retry with exponential backoff (network timeout, 503)
    Validation → fix input, retry (wrong format, missing required field)
    Business   → explain to user, propose alternative (policy violation, limit exceeded)
    Permission → escalate to human (access denied)

    Anti-pattern: generic "search unavailable" — coordinator can't decide how to recover.
    Best practice: structured error with errorCategory + isRetryable + alternatives.
    """
    print("\n=== 5.6 Error Categories + Recovery ===")

    error_examples = {
        "transient": {
            "errorCategory": "transient",
            "isRetryable": True,
            "message": "Order service timeout. Retry after 2 seconds.",
            "attempted_query": "ORD-67890",
            "partial_results": None,
        },
        "validation": {
            "errorCategory": "validation",
            "isRetryable": False,
            "message": "Invalid order_id format. Expected ORD-XXXXXX.",
            "attempted_query": "ORDER67890",
            "fix_suggestion": "Use format: ORD-67890",
        },
        "business": {
            "errorCategory": "business",
            "isRetryable": False,
            "message": "Refund amount $600 exceeds $500 policy limit.",
            "alternative": "Escalate to senior agent for amounts > $500",
        },
        "permission": {
            "errorCategory": "permission",
            "isRetryable": False,
            "message": "Access denied: agent tier does not allow bulk refunds.",
            "escalation_required": True,
        },
    }

    opts = bedrock_options(max_turns=1)

    for category, error in error_examples.items():
        prompt = (
            f"You received this MCP tool error:\n{json.dumps(error, indent=2)}\n\n"
            f"Based on errorCategory='{category}', what is the correct recovery action? "
            "One sentence."
        )
        print(f"\n  Error category: {category}")
        async for msg in query(prompt=prompt, options=opts):
            print_msg(msg)


# ===========================================================================
# Objective 5.7 — Provenance preservation
# claim → source link; handle conflicting data; include dates
# ===========================================================================

async def demo_provenance() -> None:
    """Objective 5.7: provenance — preserve claim-to-source links.

    Problem: 'The AI music market is $3.2B' — no source, no date.
    Solution: structured {claim, source_url, date, confidence}.

    Conflicting sources: preserve BOTH with attribution.
    Do NOT arbitrarily choose one — let the coordinator decide.
    Without dates: apparent contradiction may be temporal trend (not conflict).
    """
    print("\n=== 5.7 Provenance Preservation ===")

    opts = bedrock_options(max_turns=1)

    conflicting_sources = (
        "You found two data points:\n"
        "Source A: Spotify Annual Report 2024 says AI-generated music = 12%\n"
        "Source B: Music Industry Survey 2024 says AI-generated music = 8%\n\n"
        "Output JSON preserving BOTH with attribution. Do NOT choose one. "
        "Include conflict_detected and possible_explanation.\n"
        "Schema: {claim, values: [{value, source, date, methodology}], "
        "conflict_detected, possible_explanation}"
    )

    async for msg in query(prompt=conflicting_sources, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 5.8 — Structured state persistence (crash recovery)
# Each agent exports state; coordinator reads manifest on resume
# ===========================================================================

async def demo_state_persistence() -> None:
    """Objective 5.8: state persistence for multi-agent crash recovery.

    Pattern: each subagent writes to agent-state/{agent-name}.json
    Coordinator reads manifest.json on startup to skip completed work.

    Coverage annotations: mark sections as FULL / PARTIAL / NOT_STARTED
    so the final report is honest about gaps.
    """
    print("\n=== 5.8 State Persistence + Coverage Annotations ===")

    import tempfile
    from pathlib import Path

    # Simulate state files that a real multi-agent system would write
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir) / "agent-state"
        state_dir.mkdir()

        manifest = {
            "web-search": "completed",
            "doc-analysis": "partial_failure",
            "synthesis": "not_started",
        }
        (state_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        web_state = {
            "status": "completed",
            "queries_executed": ["AI music 2024", "AI music composition tools"],
            "results_count": 12,
            "coverage": ["music composition", "music production"],
            "gaps": ["music distribution", "music licensing"],
        }
        (state_dir / "web-search.json").write_text(json.dumps(web_state, indent=2))

        doc_state = {
            "status": "partial_failure",
            "failure_type": "timeout",
            "attempted_query": "AI music distribution 2024",
            "partial_results": [{"title": "AI Music Report", "relevance": 0.8}],
            "coverage_impact": "Music distribution section incomplete",
        }
        (state_dir / "doc-analysis.json").write_text(json.dumps(doc_state, indent=2))

        opts = bedrock_options(
            allowed_tools=["Read"],
            max_turns=3,
        )

        prompt = (
            f"Read the agent state manifest at {state_dir}/manifest.json and "
            f"the doc-analysis state at {state_dir}/doc-analysis.json. "
            "Then draft a coverage-annotated report outline using FULL COVERAGE / "
            "PARTIAL COVERAGE / NOT STARTED labels. Include a ⚠️ note for partial sections."
        )

        async for msg in query(prompt=prompt, options=opts):
            print_msg(msg)


# ===========================================================================
# Main
# ===========================================================================

async def main() -> None:
    examples = {
        "context_facts": demo_context_facts,
        "trim_results": demo_trim_results,
        "position_aware": demo_position_aware,
        "escalation": demo_escalation,
        "error_categories": demo_error_categories,
        "provenance": demo_provenance,
        "state_persistence": demo_state_persistence,
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
