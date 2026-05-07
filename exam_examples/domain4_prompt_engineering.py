#!/usr/bin/env python3
"""Domain 4 (20%): Prompt Engineering and Structured Output.

Exam objectives covered:
  4.1 Explicit criteria vs vague instructions — false positives, severity
  4.2 Few-shot prompting — consistency, ambiguous cases, format normalization
  4.3 Structured output with tool_use + JSON schemas
  4.4 Validation and retry-with-feedback (Pydantic-style loop)
  4.5 Self-correction — conflict_detected pattern
  4.6 Prompt chaining (sequential focused steps)
  4.7 The "interview" pattern — clarifying questions first

Scenario: Structured Data Extraction (Scenario 6)
         + Code Generation (Scenario 2, prompt engineering aspects)

Usage:
  uv run python domain4_prompt_engineering.py
  uv run python domain4_prompt_engineering.py <example>
    examples: explicit_criteria, few_shot, structured_output, retry_loop,
              self_correction, prompt_chaining, interview
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

from bedrock_config import SDK_DIR, bedrock_options

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def print_msg(msg: Any) -> None:
    if isinstance(msg, AssistantMessage):
        for b in msg.content:
            if isinstance(b, TextBlock):
                print(f"  Claude: {b.text[:500]}")
            elif isinstance(b, ToolUseBlock):
                print(f"  [tool_use] {b.name}({json.dumps(b.input)[:200]})")
    elif isinstance(msg, ResultMessage):
        cost = f"  cost=${msg.total_cost_usd:.4f}" if msg.total_cost_usd else ""
        print(f"  [done]{cost}")


# ===========================================================================
# Objective 4.1 — Explicit criteria vs vague instructions
# Exam: high false-positive rates erode developer trust
# ===========================================================================

async def demo_explicit_criteria() -> None:
    """Objective 4.1: explicit review criteria eliminate false positives.

    Vague:    "Check code for issues. Be conservative."
    Explicit: "Flag ONLY if: (1) comment contradicts code behavior,
               (2) references non-existent function, (3) fixed TODO."

    Exam rule: define severity WITH examples — not just labels.
    """
    print("\n=== 4.1 Explicit Criteria vs Vague Instructions ===")

    # VAGUE (anti-pattern)
    vague_prompt = (
        "Review this Python code for issues. Be conservative.\n\n"
        "```python\n"
        "def calculate_total(items):\n"
        "    # Sum all item prices\n"
        "    return sum(item['price'] for item in items)\n"
        "```"
    )

    # EXPLICIT (best practice) — same code, dramatically different accuracy
    explicit_prompt = (
        "Review this Python code. Flag a comment as problematic ONLY if:\n"
        "1. The comment CONTRADICTS the actual code behavior\n"
        "2. The comment references a non-existent function or variable\n"
        "3. A TODO/FIXME refers to a bug already fixed in the code\n\n"
        "Do NOT flag:\n"
        "- Comments that are merely stylistically outdated\n"
        "- Missing comments (separate category)\n"
        "- Minor wording inaccuracies\n\n"
        "Severity criteria:\n"
        "CRITICAL: Runtime failure for users (e.g., wrong return type causes crash)\n"
        "HIGH:     Security vulnerability (e.g., SQL injection)\n"
        "MEDIUM:   Logic bug without immediate impact\n"
        "LOW:      Code quality issue\n\n"
        "Code:\n"
        "```python\n"
        "def calculate_total(items):\n"
        "    # Sum all item prices\n"
        "    return sum(item['price'] for item in items)\n"
        "```\n\n"
        "Output your findings as JSON: "
        '[{"issue": "...", "severity": "...", "line": "..."}] or []'
    )

    opts = bedrock_options(max_turns=1)

    print("  VAGUE criteria:")
    async for msg in query(prompt=vague_prompt, options=opts):
        print_msg(msg)

    print("\n  EXPLICIT criteria:")
    async for msg in query(prompt=explicit_prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 4.2 — Few-shot prompting
# 2-4 examples beat vague descriptions; model generalizes the pattern
# ===========================================================================

async def demo_few_shot() -> None:
    """Objective 4.2: few-shot prompting for consistent formatted output.

    When to use few-shot:
    - Ambiguous scenarios (show decision logic)
    - Output format (show exact structure)
    - Distinguishing acceptable vs problematic patterns
    - Extracting from different document formats
    - Informal measurement normalization
    """
    print("\n=== 4.2 Few-Shot Prompting ===")

    opts = bedrock_options(max_turns=1)

    # Few-shot for informal measurement extraction (exam example)
    few_shot_measurements = (
        "Extract measurements to structured JSON. Follow these examples EXACTLY:\n\n"
        "Input: 'about two handfuls of rice'\n"
        "Output: {\"amount\": \"~100g\", \"original_text\": \"two handfuls\", \"precision\": \"approximate\"}\n\n"
        "Input: 'a pinch of salt'\n"
        "Output: {\"amount\": \"~1g\", \"original_text\": \"a pinch\", \"precision\": \"approximate\"}\n\n"
        "Input: 'exactly 500ml of water'\n"
        "Output: {\"amount\": \"500ml\", \"original_text\": \"500ml\", \"precision\": \"exact\"}\n\n"
        "Now extract from: 'Add a couple tablespoons of olive oil'"
    )

    async for msg in query(prompt=few_shot_measurements, options=opts):
        print_msg(msg)

    # Few-shot for ambiguous customer support scenarios (Scenario 1)
    few_shot_escalation = (
        "Classify customer messages. Follow these examples:\n\n"
        "Message: 'My order is broken'\n"
        "Action: lookup_order\n"
        "Reason: 'broken' may mean damaged item — need order details first\n\n"
        "Message: 'Get me a manager'\n"
        "Action: escalate_immediately\n"
        "Reason: Customer explicitly requests human — do not attempt to solve\n\n"
        "Message: 'I want to return something'\n"
        "Action: lookup_order\n"
        "Reason: Need order details before processing return\n\n"
        "Now classify: 'I am so frustrated, this is outrageous!'"
    )

    async for msg in query(prompt=few_shot_escalation, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 4.3 — Structured output with tool_use + JSON schemas
# tool_use guarantees syntactic validity; semantic validation is separate
# ===========================================================================

@tool(
    "extract_invoice",
    (
        "Extracts structured data from invoice text. "
        "Returns invoice_number, date (ISO 8601), vendor, line_items[], "
        "stated_total (numeric), and confidence (0-1). "
        "Use null for fields not found in source — do NOT fabricate values."
    ),
    {
        "invoice_number": str,
        "date": str,
        "vendor": str,
        "stated_total": float,
        "confidence": float,
    },
)
async def extract_invoice_tool(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(args)}]}


async def demo_structured_output() -> None:
    """Objective 4.3: tool_use guarantees syntactic JSON correctness.

    Exam rule:
    - tool_use = syntactic correctness guaranteed (no missing braces)
    - Semantic errors still possible (wrong field value, hallucinated total)
    - Nullable fields prevent hallucination of absent data
    - Enum + "other" + detail = extensible without losing data
    """
    print("\n=== 4.3 Structured Output via tool_use ===")

    invoice_server = create_sdk_mcp_server(
        name="invoice", tools=[extract_invoice_tool]
    )

    opts = bedrock_options(
        mcp_servers={"invoice": invoice_server},
        allowed_tools=["mcp__invoice__extract_invoice"],
        max_turns=2,
    )

    invoice_text = (
        "INVOICE\n"
        "Vendor: Acme Corp\n"
        "Invoice #: INV-2025-042\n"
        "Date: January 15, 2025\n"
        "Items:\n"
        "  Widget A: $75.00\n"
        "  Widget B: $70.00\n"
        "Total: $150.00\n"  # Intentional discrepancy: 75+70=145 ≠ 150
    )

    async with ClaudeSDKClient(options=opts) as client:
        await client.query(f"Extract invoice data from:\n{invoice_text}")
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 4.4 — Validation and retry-with-feedback
# Retry works for format errors; won't help if data is absent from source
# ===========================================================================

async def demo_retry_loop() -> None:
    """Objective 4.4: validate → retry-with-feedback loop.

    Effective for: format errors, arithmetic inconsistencies
    NOT effective for: missing information not in source document

    Pydantic-style validation: check types, required fields, business logic
    (e.g., sum(line_items) == stated_total)
    """
    print("\n=== 4.4 Validation + Retry-with-Feedback ===")

    opts = bedrock_options(max_turns=1)

    # Step 1: initial extraction
    extraction_prompt = (
        "Extract from this invoice. Output ONLY valid JSON:\n"
        '{"invoice_number": "...", "total": <number>, '
        '"line_items": [{"name": "...", "price": <number>}]}\n\n'
        "Invoice:\n"
        "Acme Corp INV-001\n"
        "Widget A: $75.00\n"
        "Widget B: $70.00\n"
        "Total: $150.00"
    )

    raw_output = ""
    async for msg in query(prompt=extraction_prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    raw_output = b.text.strip()

    print(f"  Initial extraction: {raw_output[:200]}")

    # Step 2: validate
    try:
        data = json.loads(raw_output)
        calc_total = sum(item.get("price", 0) for item in data.get("line_items", []))
        stated = data.get("total", 0)

        if abs(calc_total - stated) > 0.01:
            print(f"  VALIDATION FAILED: stated={stated}, calculated={calc_total}")

            # Step 3: retry WITH specific error context
            retry_prompt = (
                "The previous extraction had an arithmetic inconsistency.\n"
                f"Previous extraction: {raw_output}\n"
                f"Error: 'total'={stated} but sum(line_items)={calc_total}. "
                "Re-extract and fix. Output ONLY valid JSON:\n"
                '{"invoice_number": "...", "total": <number>, '
                '"line_items": [{"name": "...", "price": <number>}], '
                '"conflict_detected": true, "stated_total": <number>, '
                '"calculated_total": <number>}'
            )
            async for msg in query(prompt=retry_prompt, options=opts):
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            print(f"  After retry: {b.text[:300]}")
        else:
            print(f"  Validation PASSED: total={stated}")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  Parse error: {e} — in prod, retry with parse error context")


# ===========================================================================
# Objective 4.5 — Self-correction: conflict_detected pattern
# ===========================================================================

async def demo_self_correction() -> None:
    """Objective 4.5: self-correction by extracting both stated and computed values.

    Schema includes conflict_detected so discrepancies surface automatically.
    The model extracts BOTH the stated value AND a computed value; if they
    differ, conflict_detected=true lets you handle the discrepancy explicitly.
    """
    print("\n=== 4.5 Self-Correction (conflict_detected) ===")

    opts = bedrock_options(max_turns=1)

    prompt = (
        "Extract from this invoice AND detect conflicts. "
        "Output JSON with: stated_total, calculated_total, conflict_detected, line_items.\n\n"
        "Invoice:\n"
        "Widget A: $75.00\n"
        "Widget B: $70.00\n"
        "TOTAL: $150.00\n\n"  # 75+70=145 ≠ 150
        "The 'calculated_total' must be sum(line_items prices). "
        "Set conflict_detected=true if stated_total != calculated_total."
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Objective 4.6 — Prompt chaining (sequential focused steps)
# Avoids attention dilution; consistent quality per file
# ===========================================================================

async def demo_prompt_chaining() -> None:
    """Objective 4.6: prompt chaining for predictable multi-step tasks.

    Exam concept: analyzing all files in one prompt causes attention dilution.
    Chain: file-by-file analysis → cross-file integration pass.
    Use chaining for predictable tasks; dynamic decomposition for open-ended.
    """
    print("\n=== 4.6 Prompt Chaining ===")

    opts = bedrock_options(
        allowed_tools=["Read"],
        max_turns=3,
        cwd=str(BASE),
    )

    quick_start = SDK_DIR / "examples" / "quick_start.py"

    async with ClaudeSDKClient(options=opts) as client:
        # Step 1: analyze ONE file (focused attention)
        print("  STEP 1: Analyze quick_start.py (local issues only)")
        await client.query(
            f"STEP 1 of 2: Read {quick_start}. "
            "List its imports and main function names ONLY. Be brief."
        )
        step1_result = []
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        step1_result.append(b.text)
            print_msg(msg)

        # Step 2: synthesis (use step 1 output explicitly)
        print("\n  STEP 2: Synthesis (cross-file integration pass)")
        await client.query(
            "STEP 2 of 2: Based on STEP 1 findings above, "
            "in one sentence: what is the role of quick_start.py in this SDK?"
        )
        async for msg in client.receive_response():
            print_msg(msg)


# ===========================================================================
# Objective 4.7 — Interview pattern (ask clarifying questions first)
# ===========================================================================

async def demo_interview() -> None:
    """Objective 4.7: interview pattern — surface design considerations.

    Use when:
    - Unfamiliar domain (fintech, healthcare, legal)
    - Multiple viable approaches where best depends on context
    - Non-obvious implications (cache strategies, failure modes)
    """
    print("\n=== 4.7 Interview Pattern ===")

    opts = bedrock_options(max_turns=2)

    prompt = (
        "Before implementing a caching layer for a REST API, ask me exactly "
        "3 clarifying questions that would affect the architecture. "
        "Do NOT implement yet — only ask questions."
    )

    async for msg in query(prompt=prompt, options=opts):
        print_msg(msg)


# ===========================================================================
# Main
# ===========================================================================

async def main() -> None:
    examples = {
        "explicit_criteria": demo_explicit_criteria,
        "few_shot": demo_few_shot,
        "structured_output": demo_structured_output,
        "retry_loop": demo_retry_loop,
        "self_correction": demo_self_correction,
        "prompt_chaining": demo_prompt_chaining,
        "interview": demo_interview,
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
