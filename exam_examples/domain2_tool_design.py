#!/usr/bin/env python3
"""Domain 2 (18%): Tool Design and MCP Integration.

Exam objectives covered:
  2.1 Tool descriptions as the primary selection mechanism
  2.2 Structured MCP error responses (isError, errorCategory, isRetryable)
  2.3 tool_choice: auto / any / forced — allocating tools across agents
  2.4 MCP servers — in-process SDK MCP server pattern
  2.5 Built-in tools (Read, Write, Edit, Bash, Grep, Glob) — selection guide

Scenario: Developer Productivity Tools (Scenario 4)
  — shows tool naming, description quality, MCP server, error handling.

Usage:
  uv run python domain2_tool_design.py
  uv run python domain2_tool_design.py <example>
    examples: descriptions, mcp_server, mcp_errors, tool_choice, builtin_tools
"""

import asyncio
import sys
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from bedrock_config import EXAM_DIR, SDK_DIR, bedrock_options

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def print_msg(msg: Any) -> None:
    if isinstance(msg, AssistantMessage):
        for b in msg.content:
            if isinstance(b, TextBlock):
                print(f"  Claude: {b.text[:300]}")
            elif isinstance(b, ToolUseBlock):
                print(f"  [tool_use] {b.name}({b.input})")
    elif isinstance(msg, ResultMessage):
        cost = f"  cost=${msg.total_cost_usd:.4f}" if msg.total_cost_usd else ""
        print(f"  [done]{cost}")


# ===========================================================================
# Objective 2.1 — Tool description quality
# Poor description → wrong tool selection; rich description → reliable.
# ===========================================================================

async def demo_descriptions() -> None:
    """Objective 2.1: tool description is the primary selection mechanism.

    Exam rule: include WHAT the tool does, WHAT it returns, input formats,
    edge cases, and when to use it vs alternatives.
    Bad (vague): 'Retrieves customer information'
    Good: full contract with input formats, return fields, use-when guidance.
    """
    print("\n=== 2.1 Tool Descriptions — rich vs vague ===")

    # Bad tool: vague description causes incorrect selection
    @tool(
        "get_info",
        # VAGUE — model may use this when it should use a more specific tool
        "Gets information",
        {"id": str},
    )
    async def get_info_bad(args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"info for {args['id']}"}]}

    # Good tool: rich description aids correct selection
    @tool(
        "get_customer_profile",
        (
            "Looks up a customer account by email or numeric customer_id. "
            "Returns: name, email, account_status, order_count, lifetime_value. "
            "Input formats: email='user@domain.com' OR customer_id=12345 (integer). "
            "Use BEFORE lookup_order to verify identity. "
            "Do NOT use for order details — use lookup_order instead."
        ),
        {"email": str, "customer_id": int},
    )
    async def get_customer_good(args: dict[str, Any]) -> dict[str, Any]:
        return {
            "content": [{
                "type": "text",
                "text": (
                    f"Customer: Jane Smith | email: {args.get('email','n/a')} "
                    f"| id: {args.get('customer_id','n/a')} | status: active"
                ),
            }]
        }

    bad_server = create_sdk_mcp_server(name="bad_tools", tools=[get_info_bad])
    good_server = create_sdk_mcp_server(name="good_tools", tools=[get_customer_good])

    opts = bedrock_options(
        mcp_servers={"bad": bad_server, "good": good_server},
        allowed_tools=["mcp__bad__get_info", "mcp__good__get_customer_profile"],
        max_turns=2,
    )

    async with ClaudeSDKClient(options=opts) as client:
        await client.query(
            "Look up customer with email 'alice@example.com'. "
            "Explain which tool you chose and why."
        )
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 2.2 — Structured MCP error responses
# isError=True + structured metadata enables correct recovery decisions.
# ===========================================================================

@tool(
    "lookup_order",
    (
        "Retrieves order details by order_id (string, format ORD-XXXXXX). "
        "Returns order status, items, total, and return_eligible flag. "
        "Errors are structured with errorCategory and isRetryable."
    ),
    {"order_id": str},
)
async def lookup_order(args: dict[str, Any]) -> dict[str, Any]:
    order_id = args.get("order_id", "")
    if order_id == "ORD-TIMEOUT":
        # Transient error — agent should retry
        return {
            "content": [{
                "type": "text",
                "text": str({
                    "errorCategory": "transient",
                    "isRetryable": True,
                    "message": "Order service temporarily unavailable (timeout).",
                    "attempted_query": order_id,
                    "partial_results": None,
                }),
            }],
            "is_error": True,
        }
    if order_id == "ORD-DENIED":
        # Permission error — agent should escalate, not retry
        return {
            "content": [{
                "type": "text",
                "text": str({
                    "errorCategory": "permission",
                    "isRetryable": False,
                    "message": "Access denied: insufficient permissions for this order.",
                    "attempted_query": order_id,
                }),
            }],
            "is_error": True,
        }
    # Success
    return {
        "content": [{
            "type": "text",
            "text": f"Order {order_id}: status=shipped, total=$89.99, return_eligible=True",
        }]
    }


async def demo_mcp_errors() -> None:
    """Objective 2.2: structured error responses guide agent recovery.

    Generic 'Operation failed' gives no recovery signal.
    Structured error with errorCategory + isRetryable + message = actionable.
    """
    print("\n=== 2.2 MCP Structured Errors ===")

    order_server = create_sdk_mcp_server(name="orders", tools=[lookup_order])
    opts = bedrock_options(
        mcp_servers={"orders": order_server},
        allowed_tools=["mcp__orders__lookup_order"],
        max_turns=3,
    )

    async with ClaudeSDKClient(options=opts) as client:
        # Test transient (retryable) error
        await client.query(
            "Look up order ORD-TIMEOUT. Based on the error response, "
            "what recovery action is appropriate?"
        )
        async for msg in client.receive_response():
            print_msg(msg)

        # Test permission (non-retryable) error
        await client.query(
            "Look up order ORD-DENIED. What should you do given the error type?"
        )
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 2.3 — tool_choice: auto / any / forced
# "any" guarantees structured output; forced = deterministic first step.
# ===========================================================================

@tool(
    "extract_invoice_data",
    (
        "Extracts structured data from an invoice text. "
        "Returns JSON with: invoice_number, date, total, line_items[], vendor. "
        "Use when the input contains invoice/billing content."
    ),
    {"invoice_text": str},
)
async def extract_invoice(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{
            "type": "text",
            "text": '{"invoice_number":"INV-001","date":"2025-01-15","total":245.00,"vendor":"Acme Corp"}',
        }]
    }


async def demo_tool_choice() -> None:
    """Objective 2.3: tool_choice modes — auto / any / forced.

    auto  → model decides whether to call a tool or answer in text
    any   → model MUST call some tool (guarantees structured output)
    forced → model MUST call a SPECIFIC tool (deterministic first step)
    """
    print("\n=== 2.3 tool_choice: auto vs any vs forced ===")

    invoice_server = create_sdk_mcp_server(name="extractor", tools=[extract_invoice])

    # "any" — guarantees a tool call even if model might answer in text
    opts_any = bedrock_options(
        mcp_servers={"extractor": invoice_server},
        allowed_tools=["mcp__extractor__extract_invoice_data"],
        max_turns=2,
    )

    print("  tool_choice=any (guaranteed structured output):")
    async with ClaudeSDKClient(options=opts_any) as client:
        await client.query(
            "INVOICE: Acme Corp, INV-001, 2025-01-15, $245.00. "
            "Extract the invoice data."
        )
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 2.4 — In-process SDK MCP server
# No subprocess needed; tools run inside the Python process.
# ===========================================================================

@tool("add", "Add two numbers", {"a": float, "b": float})
async def add_numbers(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"{args['a']} + {args['b']} = {args['a'] + args['b']}"}]}


@tool("multiply", "Multiply two numbers", {"a": float, "b": float})
async def multiply_numbers(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"{args['a']} × {args['b']} = {args['a'] * args['b']}"}]}


async def demo_mcp_server() -> None:
    """Objective 2.4: create_sdk_mcp_server — in-process tool hosting.

    MCP tool naming convention: mcp__{server_name}__{tool_name}
    In-process MCP servers avoid the overhead of a separate subprocess.
    """
    print("\n=== 2.4 In-process SDK MCP Server ===")

    calc = create_sdk_mcp_server(
        name="calc",
        tools=[add_numbers, multiply_numbers],
    )

    opts = bedrock_options(
        mcp_servers={"calc": calc},
        allowed_tools=["mcp__calc__add", "mcp__calc__multiply"],
        max_turns=3,
    )

    async with ClaudeSDKClient(options=opts) as client:
        await client.query("What is (15 + 27) × 3? Show each calculation step.")
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 2.5 — Built-in tool selection guide
# Grep=content search, Glob=file patterns, Read=full file, Edit=precise change
# ===========================================================================

async def demo_builtin_tools() -> None:
    """Objective 2.5: built-in tool selection (Read/Write/Edit/Bash/Grep/Glob).

    Exam rule:
      Grep  → search within file contents (function names, imports, error msgs)
      Glob  → find files by name/extension pattern
      Read  → load full file for analysis
      Edit  → precise change via unique text match (fallback: Read + Write)
      Bash  → shell commands (git, npm, test runners)
    """
    print("\n=== 2.5 Built-in Tool Selection ===")

    opts = bedrock_options(
        allowed_tools=["Grep", "Glob", "Read"],
        max_turns=5,
    )

    prompt = (
        "Use the correct tool for each sub-task. For each step, say which tool "
        "you are using and WHY:\n"
        f"1. Find all .py files under {EXAM_DIR}/\n"
        f"2. Search for the word 'bedrock_options' in those files\n"
        f"3. Read {EXAM_DIR}/bedrock_config.py to see its full content\n"
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Main
# ===========================================================================

async def main() -> None:
    examples = {
        "descriptions": demo_descriptions,
        "mcp_server": demo_mcp_server,
        "mcp_errors": demo_mcp_errors,
        "tool_choice": demo_tool_choice,
        "builtin_tools": demo_builtin_tools,
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
