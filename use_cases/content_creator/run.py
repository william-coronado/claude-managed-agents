"""
Content Creator use case — sequential pipeline:
  researcher → author → editor
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
    env = envs["cc-env"]
    session = create_session(client, agent.id, env.id, title=prompt[:80])
    stream_message(client, session.id, prompt)


def main():
    parser = argparse.ArgumentParser(description="Content Creator agent pipeline")
    parser.add_argument("--topic", required=True, help="Topic to research and write about")
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

    # Step 1: researcher
    research_prompt = (
        f"Topic: {args.topic}\n\n"
        "Research this topic thoroughly. Gather facts, statistics, key developments, "
        "and notable sources. Produce a structured research brief."
    )
    run_agent_step(client, agents, envs, "cc-researcher", research_prompt)

    # Step 2: author
    author_prompt = (
        f"Topic: {args.topic}\n\n"
        "A researcher has compiled the brief above. "
        "Write a compelling, well-structured article based on the research."
    )
    run_agent_step(client, agents, envs, "cc-author", author_prompt)

    # Step 3: editor
    editor_prompt = (
        f"Topic: {args.topic}\n\n"
        "The author has produced the draft above. "
        "Edit and polish it: fix grammar, improve flow, and return the final version."
    )
    run_agent_step(client, agents, envs, "cc-editor", editor_prompt)


if __name__ == "__main__":
    main()
