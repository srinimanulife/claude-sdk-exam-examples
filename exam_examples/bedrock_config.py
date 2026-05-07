"""Shared Bedrock configuration for all exam examples.

The Claude Agent SDK communicates via Claude Code CLI subprocess.
Bedrock is enabled by passing env vars to the CLI process via ClaudeAgentOptions.

WSL2 note: Claude Code CLI must start from a Linux path (e.g. /tmp), not /mnt/c.
File tools (Read, Grep, Glob) work with absolute /mnt/c paths once the CLI is running.
Always set cwd='/tmp' (or another Linux path) unless the SDK itself requires a specific cwd.
"""

from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

# Bedrock model to use across all examples
BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-6"

# Env vars forwarded to the Claude Code CLI subprocess
BEDROCK_ENV = {
    "CLAUDE_CODE_USE_BEDROCK": "true",
    "AWS_REGION": "us-west-2",
}

# Stable Linux cwd for CLI subprocess (WSL2 requirement: must be Linux path)
CLI_CWD = "/tmp"

# Absolute paths to key directories (readable by Claude Code regardless of cwd)
EXAM_DIR = Path(__file__).resolve().parent
SDK_DIR = EXAM_DIR.parent / "claude-agent-sdk-python-main"


def bedrock_options(**kwargs) -> ClaudeAgentOptions:
    """Return ClaudeAgentOptions pre-configured for Bedrock.

    Any extra kwargs override or extend the defaults.
    cwd defaults to /tmp (WSL2: CLI must start from a Linux path).
    """
    env = {**BEDROCK_ENV, **kwargs.pop("env", {})}
    # Default cwd to /tmp unless caller explicitly sets it
    if "cwd" not in kwargs:
        kwargs["cwd"] = CLI_CWD
    return ClaudeAgentOptions(
        model=BEDROCK_MODEL,
        env=env,
        **kwargs,
    )
