"""
Software Engineering use case — one multiagent coordinator session.

An ``se-lead`` coordinator delegates to planner / coder / reviewer / tester,
all sharing a single container and filesystem, and drives the work with a graded
outcome (iterate until the rubric passes). Unlike the old separate-session
waterfall, the tester runs the coder's *actual* files, and reviewer feedback
loops back to the coder automatically.
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

ROLE_AGENTS = ["se-planner", "se-coder", "se-reviewer", "se-tester"]

LEAD_SYSTEM = """\
You are the delivery lead for a software engineering team. You have four teammates you can delegate
to: se-planner (architecture), se-coder (implementation), se-reviewer (code review), and se-tester
(pytest). You all share one workspace at /mnt/session/outputs/.

Run the work to completion: have the planner write the plan, the coder implement it, the reviewer
review, and the tester write and RUN tests against the real files. Loop reviewer/tester feedback
back to the coder until the code is correct, clean, and the tests pass. Deliver the finished code,
tests, PLAN.md, and REVIEW.md in /mnt/session/outputs/."""


def _rubric() -> str:
    return (
        "- /mnt/session/outputs/ contains complete, runnable Python source files implementing the task.\n"
        "- A pytest suite exists and was actually run; all tests pass (paste the pytest summary).\n"
        "- The reviewer's issues in REVIEW.md are resolved in the code (no open correctness or security findings).\n"
        "- PLAN.md describes the architecture the code follows."
    )


def main():
    parser = argparse.ArgumentParser(description="Software Engineering agent team")
    parser.add_argument("--task", required=True, help="High-level task description")
    parser.add_argument("--config", default=GLOBAL_CONFIG, help="Path to global config")
    parser.add_argument("--existing", action="store_true", help="Reuse existing resources")
    parser.add_argument("--output-dir", metavar="DIR", help="Download session output files to this local directory")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max outcome revision iterations")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set in environment or config")

    client = Anthropic(api_key=api_key)

    envs, agents = load_resources(client, cfg.default_model, ENV_CONFIG, AGENT_CONFIG, existing=args.existing)

    try:
        members = [agents[name] for name in ROLE_AGENTS]
        env = envs["se-env"]
    except KeyError as e:
        raise SystemExit(f"Error: missing resource {e}") from e

    coordinator = create_coordinator(
        client,
        name="se-lead",
        system=LEAD_SYSTEM,
        members=members,
        default_model=cfg.default_model,
        model="claude-opus-4-8",
        existing=args.existing,
    )

    description = (
        f"Task: {args.task}\n\n"
        "Deliver working, reviewed, and tested Python code for this task in /mnt/session/outputs/."
    )

    try:
        tracker = run_outcome_session(
            client, coordinator, env, description, _rubric(),
            output_dir=output_dir, max_iterations=args.max_iterations,
        )
    except RuntimeError as e:
        raise SystemExit(f"Error: session failed: {e}") from e

    print(f"\n=== Outcome result: {tracker.last_result} ===")
    if not tracker.satisfied:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
