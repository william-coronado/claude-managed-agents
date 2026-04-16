import os
import argparse
from anthropic import Anthropic
from src.config_loader import load_global_config, load_environments_config, load_agents_config
from src.environment import create_environment
from src.agent import create_agent
from src.session import create_session
from src.messaging import stream_message


def main():
    parser = argparse.ArgumentParser(description="Claude Managed Agents orchestrator")
    parser.add_argument("--config", default="config/global.yaml", help="Path to global config")
    parser.add_argument("--prompt", required=True, help="Message to send to the agent")
    parser.add_argument("--agent", required=True, help="Agent name to use")
    parser.add_argument("--env", required=True, help="Environment name to use")
    parser.add_argument("--existing", action="store_true", help="Reuse existing resources instead of creating new ones")
    args = parser.parse_args()

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set in environment or config")

    client = Anthropic(api_key=api_key)

    try:
        envs = {
            e.name: create_environment(client, e, existing=args.existing)
            for e in load_environments_config(cfg.environments_config)
        }
        agents = {
            a.name: create_agent(client, a, cfg.default_model, existing=args.existing)
            for a in load_agents_config(cfg.agents_config)
        }
    except LookupError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    if args.env not in envs:
        raise SystemExit(f"Error: environment '{args.env}' not found in {cfg.environments_config}")
    if args.agent not in agents:
        raise SystemExit(f"Error: agent '{args.agent}' not found in {cfg.agents_config}")

    env = envs[args.env]
    agent = agents[args.agent]
    session = create_session(client, agent.id, env.id, title=args.prompt[:80])
    stream_message(client, session.id, args.prompt)


if __name__ == "__main__":
    main()
