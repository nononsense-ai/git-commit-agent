# gcommit

A small AI agent that reads your staged git changes and commits them with a decent message. It is the demo project for the video "Who actually runs the command? How AI agents work".

It has a model, two tools, a loop and a few safeguards that live in your code, and it is small enough to read in one sitting.

Video: [\[VIDEO LINK\]](https://youtu.be/m2zhe3uJ6sE)

## How it works

1. `gcommit` sends the model a task and a list of tools (`git_diff` and `git_commit`).
2. The model replies with a tool request in JSON. Nothing runs yet, because it is only text.
3. Our code runs the matching Python function and sends the result back.
4. This repeats until the model answers without asking for a tool, or the step limit is reached.

Git is only ever run by your code. The model just asks.

## Files

| File | What it holds |
|------|---------------|
| `src/gcommit/tools.py` | The tool schemas, the functions behind them, and the allowlist |
| `src/gcommit/agent.py` | The loop, the messages list, and the command-line entry point |

## Safeguards

All of these live in the code, so none of them depend on the model behaving well.

- Only tools in `DISPATCH` can run. There is no push tool, so the "never push" line in the prompt is backed by code.
- The loop stops after 10 steps by default (`--max-steps` changes it).
- Each git command is cut off after 10 seconds.
- Before `git commit` runs, you see the message and have to type `y`.
- Diffs over 10,000 characters are cut, and the model is told to request files one at a time.

## Requirements

- Python 3.12 or newer
- git
- [uv](https://docs.astral.sh/uv/) (the video uses 0.13.1, and older versions generate a different starter layout)
- An [OpenRouter](https://openrouter.ai) account and API key

## Setup

1. Create an API key on the OpenRouter API Keys page. Copy it right away, because it is shown once. For a demo, set a short expiration. For real projects, set a credit limit.

2. Clone the repo into a folder named `gcommit` and install dependencies:

   ```bash
   git clone https://github.com/nononsense-ai/git-commit-agent.git gcommit
   cd gcommit
   uv sync
   ```

   The `gcommit` at the end of the clone command renames the folder. If you already cloned it under the default name, rename the folder to `gcommit` before the next step.

3. Put the key in a `.env` file at the project root:

   ```
   OPENROUTER_API_KEY=your-key-here
   ```

   `.env` is listed in `.gitignore`. Keep it there. Anyone with your key can spend your credits.

4. Install the command:

   ```bash
   uv tool install --editable .
   ```

   If your terminal says `gcommit` is not found, run `uv tool update-shell` and open a new terminal window.

## Usage

From inside any git repo with staged changes:

```bash
gcommit
```

Add `-v` to watch each step of the loop:

```bash
gcommit -v
```

| Flag | Meaning |
|------|---------|
| `-v`, `--verbose` | Print each request, tool result and message count |
| `--max-steps N` | Stop after N loop iterations (default 10) |

### Choosing a model

By default `gcommit` uses `openrouter/free`, which picks one of OpenRouter's free models for each request. Free models have usage limits and differ in how well they handle tool calling. If a run acts up, run it again or set another model:

```bash
GCOMMIT_MODEL=some/model-id gcommit
```

## What to try

- Run it with nothing staged and watch the model react to `OK: (no changes)`.
- Reject the proposed message and see it propose another.
- Stage a large change across a few big files and run with `-v` to see the truncation and the extra steps.

## Challenge

Add a third tool, `git_status`. You need three things:

1. A schema in `available_tools`
2. A function that runs `git status`
3. One line in `DISPATCH`

## License

MIT. See [LICENSE](LICENSE).
