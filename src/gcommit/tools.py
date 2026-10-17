import subprocess
from typing import Optional

from openai.types.chat import ChatCompletionFunctionToolParam

# Harness-level limits: these do not depend on the model behaving.
GIT_TIMEOUT_SECONDS = 10
MAX_DIFF_CHARS = 10_000

# --------------------------------------------------------------------------
# 1. A tool is just: name + description + JSON Schema
#    The description is the prompt that teaches the model WHEN to use it.
# --------------------------------------------------------------------------
available_tools: list[ChatCompletionFunctionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Returns a git diff for the current repo. "
                "By default returns the staged diff. "
                "Pass 'path' to see the diff of a single file, which is useful "
                "when the full diff is too large or has been truncated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "If true (default), diff staged changes. If false, diff unstaged changes",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional. Relative path of a single file to diff",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Creates a commit with a given message",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The commit message"}
                },
                "required": ["message"],
            },
        },
    },
]


# --------------------------------------------------------------------------
# 2. The functions. The model never runs these, our code does.
#    Every return value starts with OK: or ERROR: so the model can recover
#    instead of guessing. The return value is the model's ONLY view of reality.
# --------------------------------------------------------------------------
def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str] | str:
    """Run a git command. Returns the result, or an ERROR string on failure."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: git timed out after {GIT_TIMEOUT_SECONDS}s"
    except FileNotFoundError:
        return "ERROR: git is not installed or not on PATH"


def run_git_diff(staged: bool = True, path: Optional[str] = None) -> str:
    cmd = ["git", "diff"]

    if staged:
        cmd.append("--staged")

    if path:
        cmd += ["--", path]

    result = _run_git(cmd)
    if isinstance(result, str):
        return result
    if result.returncode != 0:
        return f"ERROR (exit {result.returncode}): {result.stderr or result.stdout}"
    if not result.stdout:
        return "OK: (no changes)"

    diff = result.stdout
    if len(diff) > MAX_DIFF_CHARS:
        # Truncating is what gives the agent a real reason to loop:
        # it has to call git_diff again, one file at a time.
        return (
            f"OK: {diff[:MAX_DIFF_CHARS]}\n"
            f"...(TRUNCATED at {MAX_DIFF_CHARS} chars. "
            "Call git_diff again with 'path' to see individual files.)"
        )
    return f"OK: {diff}"


def run_git_commit(message: str) -> str:
    # Human approval gate: the harness, not the model, has the final say.
    print(f"\nProposed commit message:\n\n{message}\n")
    answer = input("Proceed with this commit? [y/N] ").strip().lower()
    if answer != "y":
        return (
            "ERROR: the user rejected this commit message. "
            "Do not retry the same message. Propose a different one or stop."
        )

    result = _run_git(["git", "commit", "-m", message])
    if isinstance(result, str):
        return result
    if result.returncode != 0:
        return f"ERROR (exit {result.returncode}): {result.stderr or result.stdout}"
    return f"OK: {result.stdout}"


# --------------------------------------------------------------------------
# 3. The allowlist. If a tool is not in here, the model cannot make it run.
#    There is no git_push, so "never push" is enforced by code, not by prompt.
# --------------------------------------------------------------------------
DISPATCH = {"git_diff": run_git_diff, "git_commit": run_git_commit}
