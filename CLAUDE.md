# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_messaging.py

# Run a single test class or method
pytest tests/test_messaging.py::TestStreamMessage::test_streams_agent_message
```

There is no build step, linter config, or formatter configured for this project.

## Running the pipelines

```bash
# Set your API key
export ANTHROPIC_API_KEY=your_key

# Single-agent orchestrator
python orchestrate.py --config config/global.yaml --prompt "Your message" --agent default-assistant --env default-env

# Software engineering pipeline (planner → coder → reviewer → tester)
python use_cases/software_engineering/run.py --task "Build a todo app"

# Content creator pipeline (researcher → author → editor)
python use_cases/content_creator/run.py --topic "AI agents in 2026"

# Pass --existing to reuse already-created cloud resources instead of creating new ones
python use_cases/software_engineering/run.py --task "..." --existing

# Download session output files to a local directory after each pipeline step
python use_cases/software_engineering/run.py --task "..." --output-dir ./outputs

# Download outputs from a specific session manually
python download_outputs.py --session-id <session-id> --output-dir ./outputs
```

## Architecture

This is a Python scaffolding framework for orchestrating **Claude Managed Agents** — cloud-hosted agents that run in provisioned environments and communicate via SSE streaming.

### Core modules (`src/`)

| Module | Role |
|--------|------|
| `config_loader.py` | Parses YAML files into `GlobalConfig`, `EnvironmentConfig`, `AgentConfig` dataclasses with field validation |
| `exceptions.py` | Defines `ResourceNotFoundError(LookupError)` raised by `agent.py` / `environment.py` when a named resource is not found in `--existing` mode |
| `environment.py` | Thin wrapper around `client.beta.environments` API; supports create-new or find-existing-by-name |
| `agent.py` | Thin wrapper around `client.beta.agents` API; supports create-new or find-existing-by-name; logs a warning when `--existing` reuses an agent whose stored model differs from the current config |
| `loader.py` | `load_resources()` helper used by all entry points — iterates over all environments and agents, collects every `ResourceNotFoundError`, and raises a single `SystemExit` listing all missing resources |
| `session.py` | Creates a session via `client.beta.sessions` API; sanitizes titles by stripping non-printable Unicode |
| `messaging.py` | Opens an SSE stream (`client.beta.sessions.events.stream`), sends a user message, prints output, returns accumulated text; intercepts `agent.tool_use` events with `name="write"` and saves their content to `output_dir` when provided; logs skipped non-text blocks at DEBUG level |
| `pipeline.py` | Shared `run_agent_step()` function used by all use-case pipeline runners — creates a session and calls `stream_message()` with `output_dir=<output_dir>/<agent_name>` so file capture happens in real time during streaming |
| `downloads.py` | `download_session_outputs()` — replays session events via `client.beta.sessions.events.list()`, finds `agent.tool_use` events with `name="write"` targeting `remote_dir`, and writes their content locally; used by `download_outputs.py` for post-session retrieval |

### Configuration hierarchy

1. `config/global.yaml` — API key (overridden by `ANTHROPIC_API_KEY` env var), default model, and paths to agents/environments YAML files
2. `config/agents.yaml` / `config/environments.yaml` — Declarative agent and environment definitions

Each use case has its own `config/` subdirectory that overrides the defaults.

### Multi-agent pipelines (`use_cases/`)

Both `software_engineering/run.py` and `content_creator/run.py` follow the same pattern:
1. Load config and construct an `Anthropic` client
2. Call `load_resources()` to create (or look up) all environments and agents; any missing resources are reported together before exiting
3. Run agents sequentially, passing the output of each step as input to the next via `run_agent_step()`
4. If `--output-dir` is provided, `run_agent_step()` passes `output_dir/<agent_name>` to `stream_message()`, which captures files in real time as the agent writes them during streaming

`run_agent_step()` lives in `src/pipeline.py` and is imported by both runners. It creates a session and calls `stream_message()` with the namespaced output directory.

**How file capture works:** Two mechanisms, for two different moments.

- *Real-time, during streaming:* `stream_message()` intercepts `agent.tool_use` SSE events named `write` (the agent's built-in `write` tool emits `file_path` and `content`) and writes the content locally as the agent works.
- *Post-session, in `download_session_outputs()` (`src/downloads.py`, used by `download_outputs.py`):* a hybrid of two API calls, because neither alone is sufficient. `sessions.events.list()` is replayed for the same `write` tool events to learn each file's full remote path — the Files API (`client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])`) only reports a bare filename with no path, so two files with the same name in different subdirectories are otherwise indistinguishable (confirmed live: writing `/mnt/session/outputs/todo/main.py` and `/mnt/session/outputs/utils/main.py` in one session returns two `files.list` entries both named `main.py`, no other field disambiguates them). Each event is matched to a `files.list` entry by `(basename, byte size)`, then downloaded via `client.beta.files.download(file_id)` for the platform's authoritative stored bytes rather than the event log's copy of the tool input. If a write has no Files API match (indexing lag exhausted, or a file written via `bash` rather than `write`), the event's logged `content` is written as a fallback so nothing is silently dropped.

### Anthropic SDK beta APIs used

- `client.beta.environments.create / list`
- `client.beta.agents.create / list`
- `client.beta.sessions.create`
- `client.beta.sessions.events.stream` (SSE) — also source of `agent.tool_use` write events used for real-time file capture
- `client.beta.sessions.events.send`
- `client.beta.sessions.events.list` (replayed post-session for each write's full path — see How file capture works)
- `client.beta.files.list` / `client.beta.files.download` (session-scoped via `scope_id`; authoritative bytes for post-session file retrieval in `download_outputs.py`)

### Test approach

All 80 tests are unit tests that mock the Anthropic client; there are no integration tests hitting the real API (the hybrid Files API + event-replay approach in `download_session_outputs()` was verified once against a live session during development — see git history — but that is not part of the regular test run). Tests live in `tests/` and mirror the `src/` module structure, including `tests/test_loader.py` which verifies the bulk-error-collection contract in `load_resources()`, `tests/test_messaging.py` which covers real-time file capture from `write` tool events, `tests/test_downloads.py` which covers `download_session_outputs()` (event-replay for paths + Files API for bytes, including the duplicate-basename disambiguation and the no-match fallback) and the `download_outputs.py` CLI, and `TestRunAgentStepOutputCapture` in `tests/test_use_case_run_agent_step.py` which verifies the subdirectory namespacing passed to `stream_message()`. Tests for `run_agent_step()` patch `src.pipeline.create_session` and `src.pipeline.stream_message`.
