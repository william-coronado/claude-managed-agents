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
```

## Architecture

This is a Python scaffolding framework for orchestrating **Claude Managed Agents** — cloud-hosted agents that run in provisioned environments and communicate via SSE streaming.

### Core modules (`src/`)

| Module | Role |
|--------|------|
| `config_loader.py` | Parses YAML files into `GlobalConfig`, `EnvironmentConfig`, `AgentConfig` dataclasses with field validation |
| `exceptions.py` | Defines `ResourceNotFoundError(LookupError)` raised by `agent.py` / `environment.py` when a named resource is not found in `--existing` mode |
| `environment.py` | Thin wrapper around `client.beta.environments` API; supports create-new or find-existing-by-name |
| `agent.py` | Thin wrapper around `client.beta.agents` API; supports create-new or find-existing-by-name |
| `loader.py` | `load_resources()` helper used by all entry points — iterates over all environments and agents, collects every `ResourceNotFoundError`, and raises a single `SystemExit` listing all missing resources |
| `session.py` | Creates a session via `client.beta.sessions` API; sanitizes titles by stripping non-printable Unicode |
| `messaging.py` | Opens an SSE stream (`client.beta.sessions.events.stream`), sends a user message, prints output, returns accumulated text; logs skipped non-text blocks at DEBUG level |

### Configuration hierarchy

1. `config/global.yaml` — API key (overridden by `ANTHROPIC_API_KEY` env var), default model, and paths to agents/environments YAML files
2. `config/agents.yaml` / `config/environments.yaml` — Declarative agent and environment definitions

Each use case has its own `config/` subdirectory that overrides the defaults.

### Multi-agent pipelines (`use_cases/`)

Both `software_engineering/run.py` and `content_creator/run.py` follow the same pattern:
1. Load config and construct an `Anthropic` client
2. Call `load_resources()` to create (or look up) all environments and agents; any missing resources are reported together before exiting
3. Run agents sequentially, passing the output of each step as input to the next via `stream_message()`

The `run_agent_step()` helper (defined in each `run.py`) builds the prompt for each step and calls `stream_message()`.

### Anthropic SDK beta APIs used

- `client.beta.environments.create / list`
- `client.beta.agents.create / list`
- `client.beta.sessions.create`
- `client.beta.sessions.events.stream` (SSE)
- `client.beta.sessions.events.send`

### Test approach

All 59 tests are unit tests that mock the Anthropic client; there are no integration tests hitting the real API. Tests live in `tests/` and mirror the `src/` module structure, including `tests/test_loader.py` which verifies the bulk-error-collection contract in `load_resources()`.
