"""
Content Creator use case — sequential pipeline:
  researcher → author → editor
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
    parser = argparse.ArgumentParser(description="Content Creator agent pipeline")
    parser.add_argument("--topic", required=True, help="Topic to research and write about")
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
        # Step 1: researcher
        research_prompt = (
            f"Topic: {args.topic}\n\n"
            "Research this topic thoroughly. Gather facts, statistics, key developments, "
            "and notable sources. Produce a structured research brief."
        )
        research_output = run_agent_step(client, agents, envs, "cc-researcher", "cc-env", research_prompt, output_dir)

        # Step 2: author — receives the research brief
        author_prompt = (
            f"Topic: {args.topic}\n\n"
            "A researcher has compiled the following brief:\n\n"
            f"{research_output}\n\n"
            "Write a compelling, well-structured article based on the research."
        )
        article_output = run_agent_step(client, agents, envs, "cc-author", "cc-env", author_prompt, output_dir)

        # Step 3: editor — receives the full article draft
        editor_prompt = (
            f"Topic: {args.topic}\n\n"
            "The author has produced the following draft:\n\n"
            f"{article_output}\n\n"
            "Edit and polish it: fix grammar, improve flow, and return the final version."
        )
        run_agent_step(client, agents, envs, "cc-editor", "cc-env", editor_prompt, output_dir)
    except KeyError as e:
        raise SystemExit(f"Error: {e}") from e


if __name__ == "__main__":
    main()
