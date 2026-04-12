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
from src.config_loader import load_global_config, load_environments_config, load_agents_config
from src.environment import create_environment
from src.agent import create_agent
from src.session import create_session
from src.messaging import stream_message

USE_CASE_DIR = os.path.dirname(__file__)
GLOBAL_CONFIG = os.path.join(USE_CASE_DIR, "..", "..", "config", "global.yaml")
ENV_CONFIG = os.path.join(USE_CASE_DIR, "config", "environments.yaml")
AGENT_CONFIG = os.path.join(USE_CASE_DIR, "config", "agents.yaml")


def run_agent_step(client, agents: dict, envs: dict, agent_name: str, prompt: str) -> None:
    print(f"\n{'='*60}")
    print(f"[{agent_name.upper()}]")
    print(f"{'='*60}")
    agent = agents[agent_name]
    env = envs["se-env"]
    session = create_session(client, agent.id, env.id, title=prompt[:80])
    stream_message(client, session.id, prompt)


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

    envs = {
        e.name: create_environment(client, e, existing=args.existing)
        for e in load_environments_config(ENV_CONFIG)
    }
    agents = {
        a.name: create_agent(client, a, cfg.default_model, existing=args.existing)
        for a in load_agents_config(AGENT_CONFIG)
    }

    # Step 1: planner
    plan_prompt = f"Task: {args.task}\n\nProduce a detailed technical plan."
    run_agent_step(client, agents, envs, "se-planner", plan_prompt)

    # Step 2: coder — include the task so the agent has full context
    code_prompt = (
        f"Task: {args.task}\n\n"
        "A planner has produced the architecture above. "
        "Implement complete, working Python code following that plan."
    )
    run_agent_step(client, agents, envs, "se-coder", code_prompt)

    # Step 3: reviewer
    review_prompt = (
        f"Task: {args.task}\n\n"
        "The coder has produced the implementation above. "
        "Review it for correctness, security, performance, and style."
    )
    run_agent_step(client, agents, envs, "se-reviewer", review_prompt)

    # Step 4: tester
    test_prompt = (
        f"Task: {args.task}\n\n"
        "The implementation has been reviewed. "
        "Write a comprehensive pytest test suite for it and run the tests."
    )
    run_agent_step(client, agents, envs, "se-tester", test_prompt)


if __name__ == "__main__":
    main()
