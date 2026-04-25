from src.session import create_session
from src.messaging import stream_message


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
