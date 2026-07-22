# Claude Managed Agents

A Python scaffolding framework for orchestrating [Claude Managed Agents](https://docs.anthropic.com/en/docs/agents-and-tools/claude-managed-agents) via YAML-driven configuration. Supports single-agent interactions, multi-agent sequential pipelines, and multiagent **coordinator** sessions driven by graded **outcomes**, with real-time streaming output.

## Overview

This project provides a thin, configuration-driven layer on top of the Anthropic SDK's managed-agents beta APIs. You define agents, environments, and pipelines in YAML, then run them from the command line with no boilerplate.

**Core capabilities:**
- Create or reuse cloud execution environments with configurable networking and pip packages
- Define agents declaratively (system prompt, model, tools, MCP servers, skills, multiagent roster)
- Stream agent responses to stdout in real-time via Server-Sent Events
- Chain agents sequentially, or run a coordinator that delegates to a roster in one shared session
- Drive work with graded **outcomes** (a rubric the platform iterates against until satisfied)
- Download deliverables the agent writes to `/mnt/session/outputs/` via the Files API (incl. binary `.docx`/`.pptx`/`.xlsx`/`.pdf`)

**Included use cases:**
- **Software Engineering team** — planner + coder + reviewer + tester as one coordinator session, graded until tests pass
- **Content Creator pipeline** — researcher → author → editor (editor emits `article.docx`)
- **AI delivery team** — a solo consultant delivering like a whole team: requirements → design → build → QA → client docs, with an optional GitHub pull request

## Project Structure

```
claude-managed-agents/
├── orchestrate.py                  # Generic single-agent CLI entry point
├── download_outputs.py             # Standalone script: download a session's output files
├── requirements.txt
├── .env.example
├── config/                         # Default global configuration
│   ├── global.yaml                 # API key, default model, config file paths
│   ├── environments.yaml           # Execution environment definitions
│   └── agents.yaml                 # Agent definitions
├── src/                            # Core library
│   ├── config_loader.py            # YAML config loading and validation
│   ├── exceptions.py               # Custom exceptions (ResourceNotFoundError)
│   ├── environment.py              # Managed environment creation/lookup
│   ├── agent.py                    # Managed agent creation/lookup (incl. multiagent roster)
│   ├── loader.py                   # load_resources() helper used by all entry points
│   ├── session.py                  # Session creation (resources, vaults, version pinning)
│   ├── messaging.py                # SSE streaming with corrected idle/terminated gate
│   ├── outputs.py                  # download_session_outputs() — Files API session outputs
│   ├── outcomes.py                 # define_outcome() + OutcomeTracker (graded work)
│   ├── team.py                     # create_coordinator() + run_outcome_session()
│   ├── retry.py                    # with_retries() — backoff on transient API errors
│   ├── pipeline.py                 # run_agent_step() used by the sequential pipeline
│   └── downloads.py                # backward-compat re-export of download_session_outputs
├── use_cases/
│   ├── software_engineering/       # SE team (coordinator + outcome)
│   ├── content_creator/            # Content creator sequential pipeline
│   └── ai_delivery_team/           # Solo-consultant delivery team (coordinator + outcome)
├── tests/                          # unit tests (mock the Anthropic client)
└── docs/
    └── plan.md
```

## Requirements

- Python 3.10+
- An Anthropic API key with access to the managed-agents beta

## Installation

```bash
git clone <repo-url>
cd claude-managed-agents
pip install -r requirements.txt
```

Set your API key as an environment variable (recommended):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Alternatively, add it to `config/global.yaml` under `anthropic_api_key`.

## Usage

### Generic orchestrator

Run a single prompt against a named agent and environment:

```bash
python orchestrate.py \
  --agent default-assistant \
  --env default-env \
  --prompt "Explain the CAP theorem in one paragraph."
```

Use `--existing` to reuse cloud resources already created in a previous run instead of provisioning new ones. If a reused agent's stored model differs from the current config, a warning is logged:

```bash
python orchestrate.py \
  --agent default-assistant \
  --env default-env \
  --prompt "Follow up on the previous response." \
  --existing
```

**All CLI flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `config/global.yaml` | Path to global config file |
| `--agent` | _(required)_ | Name of the agent to use |
| `--env` | _(required)_ | Name of the environment to use |
| `--prompt` | _(required)_ | Message to send to the agent |
| `--existing` | `false` | Reuse existing cloud resources |

> Output file download is not available in `orchestrate.py`. Use `download_outputs.py` to fetch files from a specific session ID.

### Software Engineering team

A `se-lead` coordinator delegates to planner / coder / reviewer / tester in **one shared-filesystem session**, driven by a graded outcome — the platform iterates until the acceptance rubric passes (code implements the plan, the reviewer's issues are resolved, and a pytest suite was run and passes). Because the roles share the container, the tester runs the coder's *actual* files, and reviewer/QA feedback loops back to the coder automatically.

```bash
python use_cases/software_engineering/run.py \
  --task "Build a command-line todo app with file persistence and unit tests." \
  --output-dir ./se-outputs
```

Deliverables (code, tests, `PLAN.md`, `REVIEW.md`) are downloaded from `/mnt/session/outputs/` to `./se-outputs/` via the Files API. Use `--max-iterations` to cap the revision loop.

**Roles:** `se-planner` (architecture), `se-coder` (implementation), `se-reviewer` (review), `se-tester` (pytest). The environment includes `pytest`, `black`, and `ruff`.

### AI delivery team

A solo AI engineer delivering like a whole team. An `adt-delivery-lead` coordinator delegates to a requirements analyst, solution architect, implementation engineer, QA engineer, and technical writer in one shared session, graded against an acceptance rubric. Produces client-ready deliverables (a `SUMMARY.docx`, QA report, and code), and — when a repository is mounted with a GitHub MCP credential — opens a pull request.

```bash
# Simplest form
python use_cases/ai_delivery_team/run.py \
  --brief "Build a CLI that summarises a CSV of sales into a markdown report" \
  --output-dir ./deliverables

# With a client brief + rubric from files, a mounted repo, and a GitHub MCP vault
python use_cases/ai_delivery_team/run.py \
  --brief "@briefs/acme.md" --rubric "@briefs/acme-rubric.md" \
  --repo https://github.com/acme/widget --vault vlt_github123 \
  --output-dir ./deliverables
```

Key flags: `--brief`/`--rubric` accept literal text or `@path`; `--repo` (+`--repo-token` or `GITHUB_TOKEN`) mounts a repository; `--vault` supplies credentials (e.g. the GitHub MCP OAuth token); `--memory-store` attaches per-client memory.

### Content Creator pipeline

A three-agent sequential pipeline that researches a topic and produces a polished article.

```bash
python use_cases/content_creator/run.py \
  --topic "The impact of AI agents on software development in 2026."
```

Add `--output-dir` to capture any files the agents write to `/mnt/session/outputs/` during each step:

```bash
python use_cases/content_creator/run.py \
  --topic "The impact of AI agents on software development in 2026." \
  --output-dir ./cc-outputs
```

Files are captured in real time from the SSE stream and saved under `<output-dir>/<agent-name>/` (e.g. `./cc-outputs/cc-author/article.md`).

**Pipeline stages:**
1. `cc-researcher` — gathers facts, statistics, and sources via web search
2. `cc-author` — writes an engaging long-form article from the research brief
3. `cc-editor` — polishes for clarity, accuracy, and style

The environment uses unrestricted networking to enable web research.

## Configuration

### Global config (`config/global.yaml`)

```yaml
anthropic_api_key: ""          # Overridden by ANTHROPIC_API_KEY env var
default_model: "claude-sonnet-4-6"
environments_config: "config/environments.yaml"
agents_config: "config/agents.yaml"
```

### Environments (`config/environments.yaml`)

```yaml
environments:
  - name: "default-env"
    description: "General purpose development environment"
    config:
      networking:
        type: "unrestricted"   # or "none"
      packages:
        pip:
          - "requests"
          - "numpy"
```

### Agents (`config/agents.yaml`)

```yaml
agents:
  - name: "my-agent"
    model: "claude-sonnet-5"   # Optional; falls back to default_model
    description: "Does X, Y, Z"
    system: "You are a helpful assistant specialized in..."
    tools:
      - type: "agent_toolset_20260401"
    mcp_servers: []
    skills: []
```

To create your own pipeline, add a new directory under `use_cases/`, provide `config/environments.yaml` and `config/agents.yaml`, and write a `run.py` that imports `run_agent_step` from `src.pipeline` and chains agent outputs.

### Downloading session output files

Anything the agent writes under `/mnt/session/outputs/` is captured by the platform and served through the Files API. Retrieve it two ways:

**Via `--output-dir` in any runner** (downloaded after the session completes):

```bash
python use_cases/software_engineering/run.py --task "..." --output-dir ./outputs
```

**Via the standalone script** (for any past session by ID):

```bash
python download_outputs.py --session-id <session-id> --output-dir ./outputs
```

**How it works:** `download_session_outputs()` (`src/outputs.py`) lists the session's output files with `client.beta.files.list(scope_id=<session-id>, betas=["managed-agents-2026-04-01"])` and downloads each with `client.beta.files.download(...)`, preserving subdirectory structure and guarding against path traversal. It retries briefly to cover the short indexing lag between the session going idle and files appearing.

Unlike the earlier approach of reconstructing files from `write` tool events, this captures **any** file the agent produces — including those written via `bash` and **binary artifacts** such as `.docx`, `.pptx`, `.xlsx`, `.pdf`, and images. Coordinator/outcome runners download to `<output-dir>/`; the sequential pipeline downloads each step to `<output-dir>/<agent-name>/`.

## Sequence Diagrams

Focused flow diagrams are available in:

- [Orchestrate flow](docs/sequence_diagram_orchestrate.mmd)
- [Content Creator pipeline flow](docs/sequence_diagram_content_creator.mmd)
- [Software Engineering pipeline flow](docs/sequence_diagram_software_engineering.mmd)

## Architecture

```
orchestrate.py / use_cases/*/run.py / download_outputs.py
        │
        ├── config_loader.py   load & validate YAML → dataclasses
        ├── loader.py          create all environments + agents; collect errors
        │       ├── environment.py   create or reuse cloud environment
        │       └── agent.py         create or reuse managed agent (multiagent roster; model-drift warning)
        ├── pipeline.py        run_agent_step() — sequential step runner (content pipeline)
        ├── team.py            create_coordinator() + run_outcome_session() (SE + delivery team)
        │       ├── session.py       create a session (resources, vaults, version pin)
        │       ├── outcomes.py      define_outcome() + OutcomeTracker
        │       ├── messaging.py     stream SSE events (corrected idle/terminated gate)
        │       └── outputs.py       download deliverables via the Files API
        └── retry.py           with_retries() — backoff on transient API errors
```

Each layer maps directly to an Anthropic beta API:
- `client.beta.environments` — execution sandboxes
- `client.beta.agents` — stateful agent definitions
- `client.beta.sessions` — per-user conversation contexts
- `client.beta.sessions.events.stream` — SSE response stream (also source of `write` tool events for file capture)
- `client.beta.sessions.events.list` — replay past events (used by `download_outputs.py` for post-session retrieval)

### Error handling

`environment.py` and `agent.py` raise `ResourceNotFoundError` (a `LookupError` subclass from `src/exceptions.py`) when a named resource is not found in `--existing` mode. `loader.py` collects all such errors across every environment and agent before surfacing them together as a single `SystemExit`, so users see every missing resource in one message rather than one at a time.

## Testing

```bash
pytest tests/
```

77 tests covering config loading, environment/agent creation and lookup, session handling, message streaming, real-time file capture from write tool events, `load_resources` error collection, pipeline orchestration, event-replay file download, and the `download_outputs.py` CLI. All tests mock the Anthropic client and run in under one second.

## License

MIT
