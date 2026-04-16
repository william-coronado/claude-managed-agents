"""
Software Engineering use case — sequential pipeline:
  planner → coder → reviewer → tester
"""
import os
import sys
import argparse

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from anthropic import Anthropic
from src.config_loader import load_global_config
from src.loader import load_resources
from src.session import create_session
from src.messaging import stream_message

USE_CASE_DIR = os.path.dirname(__file__)
GLOBAL_CONFIG = os.path.join(USE_CASE_DIR, "..", "..", "config", "global.yaml")
ENV_CONFIG = os.path.join(USE_CASE_DIR, "config", "environments.yaml")
AGENT_CONFIG = os.path.join(USE_CASE_DIR, "config", "agents.yaml")


def run_agent_step(client, agents: dict, envs: dict, agent_name: str, env_name: str, prompt: str) -> str:
    print(f"\n{'='*60}")
    print(f"[{agent_name.upper()}]")
    print(f"{'='*60}")
    if agent_name not in agents:
        raise SystemExit(f"Error: agent '{agent_name}' not found in loaded agents")
    if env_name not in envs:
        raise SystemExit(f"Error: environment '{env_name}' not found in loaded environments")
    agent = agents[agent_name]
    env = envs[env_name]
    session = create_session(client, agent.id, env.id, title=prompt[:80])
    return stream_message(client, session.id, prompt)


def main():
    parser = argparse.ArgumentParser(description="Software Engineering agent pipeline")
    parser.add_argument("--task", required=True, help="High-level task description")
    parser.add_argument("--config", default=GLOBAL_CONFIG, help="Path to global config")
    parser.add_argument("--existing", action="store_true", help="Reuse existing resources")
    args = parser.parse_args()

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set in environment or config")

    client = Anthropic(api_key=api_key)

    envs, agents = load_resources(client, cfg, ENV_CONFIG, AGENT_CONFIG, existing=args.existing)

    # Step 1: planner
    plan_prompt = f"Task: {args.task}\n\nProduce a detailed technical plan."
    plan_output = run_agent_step(client, agents, envs, "se-planner", "se-env", plan_prompt)

    # Step 2: coder — receives the technical plan
    code_prompt = (
        f"Task: {args.task}\n\n"
        "A planner has produced the following architecture:\n\n"
        f"{plan_output}\n\n"
        "Implement complete, working Python code following that plan."
    )
    code_output = run_agent_step(client, agents, envs, "se-coder", "se-env", code_prompt)

    # Step 3: reviewer — receives the implementation
    review_prompt = (
        f"Task: {args.task}\n\n"
        "The coder has produced the following implementation:\n\n"
        f"{code_output}\n\n"
        "Review it for correctness, security, performance, and style."
    )
    review_output = run_agent_step(client, agents, envs, "se-reviewer", "se-env", review_prompt)

    # Step 4: tester — receives the implementation and review
    test_prompt = (
        f"Task: {args.task}\n\n"
        "The implementation:\n\n"
        f"{code_output}\n\n"
        "Review feedback:\n\n"
        f"{review_output}\n\n"
        "Write a comprehensive pytest test suite for it and run the tests."
    )
    run_agent_step(client, agents, envs, "se-tester", "se-env", test_prompt)


if __name__ == "__main__":
    main()
