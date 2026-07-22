"""
AI delivery team use case — a solo AI engineer delivering like a whole team.

A ``delivery-lead`` coordinator delegates to a requirements analyst, solution
architect, implementation engineer, QA engineer, and technical writer, all in a
single shared-filesystem session, driven by a graded outcome (iterate until the
acceptance rubric passes). Optionally mounts a GitHub repository (open a PR),
attaches a memory store (per-client context), and downloads client-ready
deliverables (code, QA report, .docx/.pptx summary).

Examples:
  python use_cases/ai_delivery_team/run.py \\
      --brief "Build a CLI that summarises a CSV of sales into a markdown report" \\
      --output-dir ./deliverables

  python use_cases/ai_delivery_team/run.py --brief "@briefs/acme.md" \\
      --rubric "@briefs/acme-rubric.md" \\
      --repo https://github.com/acme/widget --vault vlt_github123 \\
      --output-dir ./deliverables
"""
import os
import sys
import argparse
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from anthropic import Anthropic
from src.config_loader import load_global_config
from src.loader import load_resources
from src.team import create_coordinator, run_outcome_session

USE_CASE_DIR = os.path.dirname(__file__)
GLOBAL_CONFIG = os.path.join(USE_CASE_DIR, "..", "..", "config", "global.yaml")
ENV_CONFIG = os.path.join(USE_CASE_DIR, "config", "environments.yaml")
AGENT_CONFIG = os.path.join(USE_CASE_DIR, "config", "agents.yaml")

ROLE_AGENTS = [
    "adt-requirements-analyst",
    "adt-solution-architect",
    "adt-implementation-engineer",
    "adt-qa-engineer",
    "adt-tech-writer",
]

LEAD_SYSTEM = """\
You are the delivery lead for an AI engineering consultancy. You have a full team to delegate to:
adt-requirements-analyst, adt-solution-architect, adt-implementation-engineer, adt-qa-engineer, and
adt-tech-writer. You all share one workspace at /mnt/session/outputs/ (and a mounted repository, if
one is attached).

Deliver the engagement end to end: scope requirements, design the solution, implement it, verify it
with real tests, and package client-ready deliverables. Loop QA feedback back to the engineer until
the work meets the acceptance rubric. If a GitHub repository is mounted, have the engineer commit,
push a feature branch, and open a pull request. Keep client-facing writing clear and non-technical."""

DEFAULT_RUBRIC = """\
- The solution described in the brief is fully implemented as real, runnable files.
- Tests were written AND run against the actual deliverable; results are reported (paste the summary).
- Requirements, design, and a QA report are present in /mnt/session/outputs/.
- A client-ready summary document (SUMMARY.docx) is produced.
- If a repository was provided, a pull request was opened with the change."""


def _resolve_text(value: str) -> str:
    """Return literal text, or the contents of a file when value is '@path'."""
    if value.startswith("@"):
        return Path(value[1:]).read_text(encoding="utf-8")
    return value


def _build_resources(args) -> list:
    resources: list = []
    if args.repo:
        token = args.repo_token or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Error: --repo requires --repo-token or a GITHUB_TOKEN env var")
        resources.append({
            "type": "github_repository",
            "url": args.repo,
            "authorization_token": token,
            "checkout": {"type": "branch", "name": args.branch},
        })
    if args.memory_store:
        resources.append({
            "type": "memory_store",
            "memory_store_id": args.memory_store,
            "access": "read_write",
        })
    return resources


def main():
    parser = argparse.ArgumentParser(description="AI delivery team — deliver like a whole team")
    parser.add_argument("--brief", required=True, help="Client brief (literal text, or @path to a file)")
    parser.add_argument("--rubric", help="Acceptance rubric (literal text, or @path); default provided")
    parser.add_argument("--repo", help="GitHub repository URL to mount and (optionally) open a PR against")
    parser.add_argument("--repo-token", help="GitHub token for the mounted repo (else GITHUB_TOKEN env)")
    parser.add_argument("--branch", default="main", help="Repository branch to check out (default: main)")
    parser.add_argument("--vault", action="append", default=[], metavar="VAULT_ID",
                        help="Vault ID supplying credentials (e.g. GitHub MCP OAuth); repeatable")
    parser.add_argument("--memory-store", help="Memory store ID to attach for per-client context")
    parser.add_argument("--config", default=GLOBAL_CONFIG, help="Path to global config")
    parser.add_argument("--existing", action="store_true", help="Reuse existing resources")
    parser.add_argument("--output-dir", metavar="DIR", help="Download deliverables to this local directory")
    parser.add_argument("--max-iterations", type=int, default=6, help="Max outcome revision iterations")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    brief = _resolve_text(args.brief)
    rubric = _resolve_text(args.rubric) if args.rubric else DEFAULT_RUBRIC
    resources = _build_resources(args)

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set in environment or config")

    client = Anthropic(api_key=api_key)

    envs, agents = load_resources(client, cfg.default_model, ENV_CONFIG, AGENT_CONFIG, existing=args.existing)

    try:
        members = [agents[name] for name in ROLE_AGENTS]
        env = envs["adt-env"]
    except KeyError as e:
        raise SystemExit(f"Error: missing resource {e}") from e

    coordinator = create_coordinator(
        client,
        name="adt-delivery-lead",
        system=LEAD_SYSTEM,
        members=members,
        default_model=cfg.default_model,
        model="claude-opus-4-8",
        existing=args.existing,
    )

    description = f"Client brief:\n\n{brief}\n\nDeliver this engagement end to end."

    try:
        tracker = run_outcome_session(
            client, coordinator, env, description, rubric,
            output_dir=output_dir,
            resources=resources or None,
            vault_ids=args.vault or None,
            max_iterations=args.max_iterations,
        )
    except RuntimeError as e:
        raise SystemExit(f"Error: session failed: {e}") from e

    print(f"\n=== Engagement outcome: {tracker.last_result} ===")
    if output_dir:
        print(f"Deliverables downloaded to {output_dir}")


if __name__ == "__main__":
    main()
