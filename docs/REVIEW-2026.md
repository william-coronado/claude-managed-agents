# Codebase Review — Claude Managed Agents (2026)

A review of the `claude-managed-agents` scaffold against the current Anthropic
Managed Agents SDK, covering four questions: what changed in the API/SDK, which
new platform features are worth adopting, how the two existing use cases can
improve, and a new use case for a solo AI-engineer consultant. The
modernizations and the new use case described here have been implemented in this
branch; this document is the written assessment behind them.

---

## TL;DR

The scaffold was well-structured but built around a **workaround the platform has
since removed**: it reconstructed agent-created files by intercepting `write`
tool events from the SSE stream, because "the platform does not expose files
agents create at runtime." That is no longer true — session outputs are now
first-class in the Files API. Removing the workaround simplifies the core and
unlocks binary deliverables. The bigger opportunity is architectural: the
pipelines chained **separate sessions**, so a downstream role (the SE tester)
could never touch an upstream role's real files. Managed Agents now solves this
natively with **multiagent coordinator sessions** (one shared filesystem) and
**outcomes** (rubric-graded iterate-until-done). Those two features are the
backbone of the modernized SE pipeline and the new "AI delivery team" use case.

---

## 1. What changed in the API / SDK

| Area | Before (in this repo) | Current |
|---|---|---|
| **Session outputs** | Intercept `agent.tool_use` `write` events and rebuild file content from the stream (`messaging.py`, `downloads.py`). Text only. | Platform captures `/mnt/session/outputs/` and serves it via the **Files API**: `client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])` + `files.download()`. Handles binary artifacts. |
| **SDK pin** | `anthropic>=0.51.0` | `scope_id` session-output listing needs **`anthropic>=0.92.0`**; current line is ~0.117. |
| **Models** | `claude-sonnet-4-6` everywhere; `default_model` also 4.6 and effectively dead (every agent overrode it) | `claude-sonnet-5` (drop-in for 4.6) or `claude-opus-4-8` for reasoning-heavy roles. |
| **Stream gate** | Breaks on `session.status_idle` unconditionally; never handles `session.status_terminated` | Idle can be **transient** (`stop_reason.type == "requires_action"` — waiting on a tool confirmation/custom-tool result). Correct gate: break on `session.status_terminated` or a terminal idle; continue on `requires_action`. |
| **Reconnect** | None | SSE has no replay; a dropped stream should reconcile via `events.list()` + dedupe by event id. |
| **Version pinning** | Ignored (string-ID shorthand = latest) | `agents.create()` returns a `version`; sessions can pin `{type:"agent", id, version}` for reproducibility. |

**What was done:** bumped the SDK pin; replaced the write-event capture with a
Files API implementation (`src/outputs.py`, with a path-traversal guard and an
indexing-lag retry); corrected the stream gate in `src/messaging.py`; updated
models; added optional version pinning to `create_session`.

---

## 2. New Managed-Agents features worth adopting

| Feature | Why it matters here | Status in this branch |
|---|---|---|
| **Session outputs (Files API)** | Removes the fragile workaround; supports `.docx`/`.pptx`/`.xlsx`/`.pdf`/images | **Adopted** (`src/outputs.py`) |
| **Multiagent coordinator** (`multiagent` on the agent) | One session, shared filesystem, subagent threads — fixes the cross-session file-loss flaw | **Adopted** (`src/team.py`, SE pipeline, delivery team) |
| **Outcomes** (`user.define_outcome` + rubric) | Server-run iterate → grade → revise loop; replaces the one-shot waterfall | **Adopted** (`src/outcomes.py`) |
| **Skills** | `AgentConfig` already parsed `skills`; nothing set them. Anthropic `docx`/`pptx`/`xlsx`/`pdf` turn streamed text into real deliverables | **Adopted** (content editor, delivery tech-writer) |
| **Vaults** | MCP + `environment_variable` credentials injected at egress; prereq for GitHub PRs | **Wired** (`vault_ids` on sessions; delivery `--vault`) |
| **GitHub repository resources** + GitHub MCP | Mount a repo, edit/commit/push, open PRs | **Wired** (delivery `--repo`) |
| **Memory stores** | Cross-session per-client context | **Wired** (delivery `--memory-store`) |
| **Scheduled deployments** | Cron-fired sessions (recurring status reports) | Documented as a follow-on |
| **Permission policies** (`always_ask`) | Human-in-the-loop gating on risky tools | Available via config passthrough |

---

## 3. Improvements to the two existing use cases

**Both pipelines shared these problems:**

- **No feedback loop.** SE reviewer feedback flowed only to the tester, never
  back to the coder — a one-shot waterfall with no "fix until tests pass."
- **Cross-session artifact loss.** Each step was its own session with a fresh
  container, so the tester was asked to "run the tests" on code it only received
  as pasted text; the coder's real files never reached it. Both pipelines
  discarded the final step's output.
- **Fragile prompt-stuffing hand-off.** Each step re-embedded the prior full
  output as raw text ("Do not truncate" — but no guard).
- **Narrow error handling.** `run.py` caught only `KeyError`; a transient
  `session.error` raised `RuntimeError` and killed the run with lost state.
- **Stale models; dead `default_model`.**

**What was done:**

- **Software Engineering → coordinator + outcome.** The four roles now run as one
  `se-lead` coordinator session sharing a filesystem, kicked off with a
  `user.define_outcome` whose rubric requires that the code implements the plan,
  the reviewer's issues are resolved, and a pytest suite **was actually run and
  passes**. The tester now runs the coder's real files; feedback loops
  automatically.
- **Content Creator** stays sequential (genuinely linear) but now writes each
  artifact to the shared outputs dir, captures the final result, and attaches the
  `docx` skill so the editor emits a real `article.docx`.
- **Retry/backoff** (`src/retry.py`) wraps session creation; error handling was
  broadened. Models updated to `opus-4-8`/`sonnet-5`; `default_model` made
  authoritative.

---

## 4. New use case — "AI delivery team"

`use_cases/ai_delivery_team/` lets a solo AI engineer deliver like a whole team.
An `adt-delivery-lead` coordinator delegates to five roles in **one
shared-filesystem session**, graded against an acceptance rubric:

```
requirements-analyst → solution-architect → implementation-engineer → qa-engineer → tech-writer
                              (all in one coordinator session, iterating until the rubric passes)
```

It exercises the full modern feature set:

- **Multiagent coordinator + outcome** — plan, delegate across subagent threads,
  iterate until "done" is objectively met.
- **Skills** — the tech-writer produces a client-ready `SUMMARY.docx` (and a deck
  when appropriate) via the `docx`/`pptx`/`xlsx`/`pdf` skills.
- **GitHub repo resource + GitHub MCP + vault** — mount a repo (`--repo`),
  supply the MCP credential (`--vault`), and open a pull request.
- **Memory store** (`--memory-store`) — carry per-client context across
  engagements.
- **Session outputs** — download the deliverables (code, QA report, summary doc)
  to a local directory.

```bash
python use_cases/ai_delivery_team/run.py \
  --brief "@briefs/acme.md" --rubric "@briefs/acme-rubric.md" \
  --repo https://github.com/acme/widget --vault vlt_github123 \
  --output-dir ./deliverables
```

A natural follow-on (documented, not built): register a **scheduled deployment**
so the team produces a recurring status report on a cron cadence without a
client-side scheduler.

---

## Verification

All modernizations ship with unit tests that mock the Anthropic client (no live
API): the corrected stream gate, Files-API session-output download (traversal
guard, indexing-lag retry, binary content), outcome kickoff, coordinator session,
and retry backoff. Run `pytest tests/`. The entry points (`--help`) all parse.
A live smoke run requires an API key with managed-agents beta access.
