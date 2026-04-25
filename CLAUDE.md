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
| `messaging.py` | Opens an SSE stream (`client.beta.sessions.events.stream`), sends a user message, prints output, returns accumulated text; logs skipped non-text blocks at DEBUG level |
| `pipeline.py` | Shared `run_agent_step()` function used by all use-case pipeline runners — creates a session, streams a prompt, and optionally downloads session output files |
| `downloads.py` | `download_session_outputs()` — lists files scoped to a session via `client.beta.files.list(scope_id=)` and writes each to a local directory using `BinaryAPIResponse.write_to_file()` |

### Configuration hierarchy

1. `config/global.yaml` — API key (overridden by `ANTHROPIC_API_KEY` env var), default model, and paths to agents/environments YAML files
2. `config/agents.yaml` / `config/environments.yaml` — Declarative agent and environment definitions

Each use case has its own `config/` subdirectory that overrides the defaults.

### Multi-agent pipelines (`use_cases/`)

Both `software_engineering/run.py` and `content_creator/run.py` follow the same pattern:
1. Load config and construct an `Anthropic` client
2. Call `load_resources()` to create (or look up) all environments and agents; any missing resources are reported together before exiting
3. Run agents sequentially, passing the output of each step as input to the next via `run_agent_step()`
4. If `--output-dir` is provided, `run_agent_step()` calls `download_session_outputs()` after each step

`run_agent_step()` lives in `src/pipeline.py` and is imported by both runners. It creates a session, calls `stream_message()`, and optionally downloads output files via `src/downloads.py`.

### Anthropic SDK beta APIs used

- `client.beta.environments.create / list`
- `client.beta.agents.create / list`
- `client.beta.sessions.create`
- `client.beta.sessions.events.stream` (SSE)
- `client.beta.sessions.events.send`
- `client.beta.files.list` (with `scope_id` to enumerate session output files)
- `client.beta.files.download` (to retrieve file content)

### Test approach

All 65 tests are unit tests that mock the Anthropic client; there are no integration tests hitting the real API. Tests live in `tests/` and mirror the `src/` module structure, including `tests/test_loader.py` which verifies the bulk-error-collection contract in `load_resources()` and `tests/test_downloads.py` which covers `download_session_outputs()`. Tests for `run_agent_step()` patch `src.pipeline.create_session` and `src.pipeline.stream_message`.
