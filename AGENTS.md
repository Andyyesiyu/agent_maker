AGENTS.md — Guidance for Coding Agents on Agent Maker

This file provides agent-focused instructions: reliable setup, run/validate steps, code style, and safety notes. Prefer these commands and conventions when working in this repo.

## Setup commands
- Use uv for Python and deps:
  - Install uv: `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Optional venv: `uv venv && source .venv/bin/activate`
  - Generate lockfile (commit it): `uv lock`
- Run CLI via uv:
  - List tools: `uv run python -m agent_maker.cli list-tools`
  - Minimal run: `uv run python -m agent_maker.cli run --task "创建 TODO 并写入 demo.txt"`
- Optional OpenAI provider:
  - Install: `uv add openai`
  - Design spec: `uv run python -m agent_maker.cli design --prompt "……" --provider openai`

## Validate changes (smoke checks)
- Core CLI works: `uv run python -m agent_maker.cli list-tools`
- Scaffold a new agent:
  - `uv run python -m agent_maker.cli new my_agent --desc "示例 Agent" --tools todo,fs`
  - Run it: `uv run python agents/my_agent/main.py --task "创建一个 TODO 并写入文件"`
- Design + scaffold path:
  - `uv run python -m agent_maker.cli design --prompt "做一个能读写文件并管理待办的 Agent" --out spec.json`
  - `uv run python -m agent_maker.cli scaffold --spec spec.json --dest agents/auto_agent`
- Traces: outputs under `runs/<run_id>/trace.jsonl`

## Code style and conventions
- Python >= 3.10, standard library first; optional `openai` only when needed.
- Strong typing, dataclasses; keep patches minimal and focused.
- Don’t add unrelated fixes or new deps without need.
- Keep filenames, APIs, and CLI args stable unless requested.
- Avoid adding license headers. Follow existing code style.

## Repository structure
- `agent_maker/core`: agent loop, tools, llm providers, state, runner
- `agent_maker/cli.py`: CLI entry with subcommands
- `agent_maker/scaffold.py`: scaffolding utilities
- `agents/`: generated agents
- `runs/`: JSONL traces
- `pyproject.toml`, `uv.lock`: env and lock

## Security considerations
- File tools (`fs.read`, `fs.write`) are sandboxed to repo workspace; path traversal is denied.
- `shell` tool is allowlisted (default `echo`, `ls`). Modify with care.
- Respect least privilege; don’t escalate unless the user asks. Keep external network calls minimal.

## Environment and privacy
- Env file: copy `.env.example` to `.env` (git-ignored). The CLI and demo agent auto-load it.
- Core env vars:
  - `AGENT_MAKER_PRIVACY`: `off` | `standard` | `strict` (default `standard`). Controls redaction in traces.
  - `AGENT_MAKER_TRACE_ENABLED`: `true`/`false` (default `true`). Disables writing `runs/<id>/trace.jsonl` when false.
  - `AGENT_MAKER_REDACT_PLACEHOLDER`: replacement for sensitive fields (default `***`).
  - `AGENT_MAKER_MAX_VALUE_LEN`: truncate long values when not strict (default `2000`).
  - `AGENT_MAKER_DOTENV`: custom dotenv path (default `.env`).
- Redaction behavior:
  - Sensitive keys like `api_key`, `token`, `password`, `secret` are redacted recursively.
  - In `strict` mode: model outputs in traces are omitted; filesystem tool contents and patches are masked.
  - In `standard` mode: large values are truncated; sensitive keys are still masked.

## Docker (optional)
- Quick one-off run (host repo mounted):
  - `docker run --rm -it -v "$PWD":/app -w /app python:3.12-slim bash -lc 'apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/* && curl -LsSf https://astral.sh/uv/install.sh | sh && ~/.local/bin/uv run python -m agent_maker.cli list-tools'`
- Custom Dockerfile suggested steps: install uv, copy `pyproject.toml` (+ `uv.lock`), run `uv lock`, then copy source.

## PR instructions (if applicable)
- Title: `[agent-maker] <Title>`
- Run smoke checks above before submitting.
- If you touch CLI contracts or tool schemas, update README and examples.
