import argparse
import json
import os
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
)

from gcommit.tools import DISPATCH, available_tools

MAX_STEPS = 10

# Default is OpenRouter's free router, so the demo costs viewers nothing.
# (openrouter/auto is billed at whichever model it picks.) Override with
# GCOMMIT_MODEL, e.g. a specific free model, or any tool-capable model id.
DEFAULT_MODEL = "openrouter/free"

SYSTEM_PROMPT = (
    "You write commit messages. Inspect the diff first, "
    "follow conventional commits, never push. "
    "If a diff result says it was TRUNCATED, call git_diff again with "
    "'path' for every file in the diff, one at a time, before you commit."
)
USER_PROMPT = "Commit the staged changes with a good message"


def make_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def execute_tool(name: str, raw_arguments: str) -> str:
    """Run one tool requested by the model. Always returns an OK:/ERROR: string."""
    if name not in DISPATCH:
        return f"ERROR: unknown tool '{name}'"
    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return "ERROR: arguments were not valid JSON"
    if not isinstance(args, dict):
        return "ERROR: arguments must be a JSON object"
    try:
        return DISPATCH[name](**args)
    except TypeError as e:
        return f"ERROR: bad arguments: {e}"


def agent_loop(
    max_steps: int = MAX_STEPS, verbose: bool = False, model: str = DEFAULT_MODEL
) -> None:
    def log(text: str) -> None:
        if verbose:
            print(text)

    # The messages list IS the agent's state. The model has no memory;
    # we resend this whole list on every iteration.
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ]

    client = make_client()
    for step in range(1, max_steps + 1):
        log(f"\n[step {step}] sending {len(messages)} messages to {model}")
        response = client.chat.completions.create(  # type: ignore[call-overload]
            model=model, messages=messages, tools=available_tools
        )
        msg = response.choices[0].message

        # No tool call means the model is done: that is the stop condition.
        if not msg.tool_calls:
            print("Agent:", msg.content)
            break

        messages.append(
            cast(ChatCompletionAssistantMessageParam, msg.model_dump(exclude_none=True))
        )

        for call in msg.tool_calls:
            if call.type != "function":
                # Every tool_call needs a matching tool message, so answer it.
                result = f"ERROR: unsupported tool call type '{call.type}'"
            else:
                log(
                    f"  -> model requested {call.function.name}({call.function.arguments})"
                )
                result = execute_tool(call.function.name, call.function.arguments)
                log(f"  <- tool returned {len(result)} chars: {result[:80]!r}")

            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )
    else:
        print(f"Stopped: hit step limit ({max_steps})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="An AI agent that commits your staged changes"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show each loop step"
    )
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args()

    load_dotenv()
    load_dotenv(Path.home() / ".config/gcommit/.env")
    agent_loop(
        max_steps=args.max_steps,
        verbose=args.verbose,
        model=os.getenv("GCOMMIT_MODEL", DEFAULT_MODEL),
    )


if __name__ == "__main__":
    main()
