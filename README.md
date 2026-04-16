# Claude Managed Agents

A Python scaffolding framework for orchestrating [Claude Managed Agents](https://docs.anthropic.com/en/docs/agents-and-tools/claude-managed-agents) via YAML-driven configuration. Supports single-agent interactions and multi-agent sequential pipelines with real-time streaming output.

## Overview

This project provides a thin, configuration-driven layer on top of the Anthropic SDK's managed-agents beta APIs. You define agents, environments, and pipelines in YAML, then run them from the command line with no boilerplate.

**Core capabilities:**
- Create or reuse cloud execution environments with configurable networking and pip packages
- Define agents declaratively (system prompt, model, tools, MCP servers, skills)
- Stream agent responses to stdout in real-time via Server-Sent Events
- Chain agents sequentially, passing each output as input to the next

**Included use cases:**
- **Software Engineering pipeline** — planner → coder → reviewer → tester
- **Content Creator pipeline** — researcher → author → editor

## Project Structure

```
claude-managed-agents/
├── orchestrate.py                  # Generic single-agent CLI entry point
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
│   ├── agent.py                    # Managed agent creation/lookup
│   ├── loader.py                   # load_resources() helper used by all entry points
│   ├── session.py                  # User session management
│   └── messaging.py                # SSE streaming and message handling
├── use_cases/
│   ├── software_engineering/       # SE pipeline use case
│   │   ├── run.py
│   │   └── config/
│   │       ├── environments.yaml
│   │       └── agents.yaml
│   └── content_creator/            # Content creator pipeline use case
│       ├── run.py
│       └── config/
│           ├── environments.yaml
│           └── agents.yaml
├── tests/                          # 59 unit tests
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

Use `--existing` to reuse cloud resources already created in a previous run instead of provisioning new ones:

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

### Software Engineering pipeline

A four-agent sequential pipeline that takes a high-level task and produces planned, coded, reviewed, and tested Python output.

```bash
python use_cases/software_engineering/run.py \
  --task "Build a command-line todo app with file persistence and unit tests."
```

**Pipeline stages:**
1. `se-planner` — produces a detailed technical architecture plan
2. `se-coder` — implements Python code from the plan
3. `se-reviewer` — reviews for correctness, security, performance, and style
4. `se-tester` — writes and runs pytest test suites

The environment includes `pytest`, `black`, and `ruff`.

### Content Creator pipeline

A three-agent sequential pipeline that researches a topic and produces a polished article.

```bash
python use_cases/content_creator/run.py \
  --topic "The impact of AI agents on software development in 2026."
```

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
    model: "claude-sonnet-4-6"   # Optional; falls back to default_model
    description: "Does X, Y, Z"
    system: "You are a helpful assistant specialized in..."
    tools:
      - type: "agent_toolset_20260401"
    mcp_servers: []
    skills: []
```

To create your own pipeline, add a new directory under `use_cases/`, provide `config/environments.yaml` and `config/agents.yaml`, and write a `run.py` that chains agent outputs using the `src` modules.

## Architecture

```
orchestrate.py / use_cases/*/run.py
        │
        ├── config_loader.py   load & validate YAML → dataclasses
        ├── loader.py          create all environments + agents; collect errors
        │       ├── environment.py   create or reuse cloud environment
        │       └── agent.py        create or reuse managed agent
        ├── session.py         open a user session
        └── messaging.py       stream SSE events, print output, return text
```

Each layer maps directly to an Anthropic beta API:
- `client.beta.environments` — execution sandboxes
- `client.beta.agents` — stateful agent definitions
- `client.beta.sessions` — per-user conversation contexts
- `client.beta.sessions.events.stream` — SSE response stream

### Error handling

`environment.py` and `agent.py` raise `ResourceNotFoundError` (a `LookupError` subclass from `src/exceptions.py`) when a named resource is not found in `--existing` mode. `loader.py` collects all such errors across every environment and agent before surfacing them together as a single `SystemExit`, so users see every missing resource in one message rather than one at a time.

## Testing

```bash
pytest tests/
```

59 tests covering config loading, environment/agent creation and lookup, session handling, message streaming, `load_resources` error collection, and pipeline orchestration. All tests mock the Anthropic client and run in under one second.

## License

MIT
