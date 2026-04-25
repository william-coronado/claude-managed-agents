"""
Software Engineering use case — sequential pipeline:
  planner → coder → reviewer → tester
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
from src.pipeline import run_agent_step

USE_CASE_DIR = os.path.dirname(__file__)
GLOBAL_CONFIG = os.path.join(USE_CASE_DIR, "..", "..", "config", "global.yaml")
ENV_CONFIG = os.path.join(USE_CASE_DIR, "config", "environments.yaml")
AGENT_CONFIG = os.path.join(USE_CASE_DIR, "config", "agents.yaml")


def main():
    parser = argparse.ArgumentParser(description="Software Engineering agent pipeline")
    parser.add_argument("--task", required=True, help="High-level task description")
    parser.add_argument("--config", default=GLOBAL_CONFIG, help="Path to global config")
    parser.add_argument("--existing", action="store_true", help="Reuse existing resources")
    parser.add_argument("--output-dir", metavar="DIR", help="Download session output files to this local directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set in environment or config")

    client = Anthropic(api_key=api_key)

    envs, agents = load_resources(client, cfg.default_model, ENV_CONFIG, AGENT_CONFIG, existing=args.existing)

    try:
        # Step 1: planner
        plan_prompt = f"Task: {args.task}\n\nProduce a detailed technical plan."
        plan_output = run_agent_step(client, agents, envs, "se-planner", "se-env", plan_prompt, output_dir)

        # Step 2: coder — receives the technical plan
        code_prompt = (
            f"Task: {args.task}\n\n"
            "A planner has produced the following architecture:\n\n"
            f"{plan_output}\n\n"
            "Implement complete, working Python code following that plan."
        )
        code_output = run_agent_step(client, agents, envs, "se-coder", "se-env", code_prompt, output_dir)

        # Step 3: reviewer — receives the implementation
        review_prompt = (
            f"Task: {args.task}\n\n"
            "The coder has produced the following implementation:\n\n"
            f"{code_output}\n\n"
            "Review it for correctness, security, performance, and style."
        )
        review_output = run_agent_step(client, agents, envs, "se-reviewer", "se-env", review_prompt, output_dir)

        # Step 4: tester — receives the implementation and review
        test_prompt = (
            f"Task: {args.task}\n\n"
            "The implementation:\n\n"
            f"{code_output}\n\n"
            "Review feedback:\n\n"
            f"{review_output}\n\n"
            "Write a comprehensive pytest test suite for it and run the tests."
        )
        run_agent_step(client, agents, envs, "se-tester", "se-env", test_prompt, output_dir)
    except KeyError as e:
        raise SystemExit(f"Error: {e}") from e


if __name__ == "__main__":
    main()
