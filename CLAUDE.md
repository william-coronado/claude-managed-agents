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

# Software engineering team (planner + coder + reviewer + tester as one coordinator
# session, driven by a graded outcome — iterate until tests pass)
python use_cases/software_engineering/run.py --task "Build a todo app" --output-dir ./outputs

# Content creator pipeline (researcher → author → editor; editor emits article.docx)
python use_cases/content_creator/run.py --topic "AI agents in 2026" --output-dir ./outputs

# AI delivery team (solo consultant delivering like a whole team; optional GitHub PR)
python use_cases/ai_delivery_team/run.py --brief "Build a CSV-to-report CLI" --output-dir ./deliverables

# Pass --existing to reuse already-created cloud resources instead of creating new ones
python use_cases/software_engineering/run.py --task "..." --existing

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
| `session.py` | Creates a session via `client.beta.sessions` API; sanitizes titles by stripping non-printable Unicode; supports `resources` (files / GitHub repos / memory stores), `vault_ids`, and agent version pinning |
| `messaging.py` | `stream_session()` opens an SSE stream (`client.beta.sessions.events.stream`), runs a caller-supplied kickoff, and consumes to a terminal state; `stream_message()` is the user-message kickoff. Correct gate: breaks on `session.status_terminated` or a terminal `session.status_idle`, continues through a transient idle (`requires_action`). Surfaces tool use, multiagent thread activity, and outcome grades |
| `outputs.py` | `download_session_outputs()` — lists session-scoped output files via the Files API (`client.beta.files.list(scope_id=..., betas=["managed-agents-2026-04-01"])`) and downloads each with `files.download()`, preserving subdirectories, guarding against path traversal, and retrying briefly to cover indexing lag. Supports binary artifacts (`.docx`/`.pptx`/`.xlsx`/`.pdf`/images) |
| `outcomes.py` | `define_outcome()` sends a `user.define_outcome` event (goal + rubric); `OutcomeTracker` collects `span.outcome_evaluation_end` grades from the stream |
| `team.py` | `create_coordinator()` builds a multiagent coordinator whose roster is a set of role agents; `run_outcome_session()` runs one shared-filesystem coordinator session driven by a graded outcome and downloads the deliverables |
| `retry.py` | `with_retries()` — exponential backoff (2/4/8/16s) around transient API failures; wraps session creation |
| `pipeline.py` | `run_agent_step()` (used by the content pipeline) — creates a session, streams, and downloads that session's outputs to `<output_dir>/<agent_name>` via the Files API |
| `downloads.py` | Backward-compat re-export of `download_session_outputs` from `outputs.py` (the module used to replay events to reconstruct files; that workaround is gone) |

### Configuration hierarchy

1. `config/global.yaml` — API key (overridden by `ANTHROPIC_API_KEY` env var), default model, and paths to agents/environments YAML files
2. `config/agents.yaml` / `config/environments.yaml` — Declarative agent and environment definitions

Each use case has its own `config/` subdirectory that overrides the defaults.

### Use cases (`use_cases/`)

Two orchestration shapes are used:

- **Sequential pipeline** (`content_creator/run.py`): loads resources via `load_resources()`, runs agents in order with `run_agent_step()` (each its own session), feeding each step's text output into the next. `--output-dir` downloads each session's outputs to `<output_dir>/<agent_name>`.
- **Multiagent coordinator + outcome** (`software_engineering/run.py`, `ai_delivery_team/run.py`): creates the role agents, then builds a coordinator (`create_coordinator()`) whose `multiagent` roster is those agents. `run_outcome_session()` opens **one** session (all roles share the container and filesystem), sends a `user.define_outcome` with an acceptance rubric, streams until the grader is satisfied (or hits `max_iterations`), and downloads the deliverables. This lets QA run the engineer's *actual* files and loops reviewer/QA feedback back to the engineer automatically.

**How output capture works:** The platform captures anything the agent writes under `/mnt/session/outputs/` and serves it through the Files API. `download_session_outputs()` (`src/outputs.py`) lists session-scoped files (`client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])`) and downloads each one. This supersedes the earlier approach of reconstructing files from `write` tool events (which only handled text and re-derived content from the stream) and supports binary deliverables.

### Anthropic SDK beta APIs used

- `client.beta.environments.create / list`
- `client.beta.agents.create / list` (incl. the `multiagent` coordinator roster)
- `client.beta.sessions.create` (incl. `resources` and `vault_ids`)
- `client.beta.sessions.events.stream / send` (SSE); `send` also delivers `user.define_outcome`
- `client.beta.files.list(scope_id=...) / download` — session outputs (Files API)

### Test approach

All tests are unit tests that mock the Anthropic client; there are no integration tests hitting the real API. Tests live in `tests/` and mirror the `src/` module structure, including `tests/test_loader.py` (bulk-error-collection in `load_resources()`), `tests/test_messaging.py` (the corrected idle/terminated/requires_action stream gate), `tests/test_outputs.py` (Files API session-output download, traversal guard, indexing-lag retry, binary content), `tests/test_outcomes.py` and `tests/test_team.py` (outcome kickoff + coordinator session), `tests/test_retry.py` (transient-error backoff), and `tests/test_downloads.py` (the re-export and CLI).
