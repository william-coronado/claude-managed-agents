"""Download output files from a completed session to a local directory."""
import os
import argparse
from pathlib import Path

from anthropic import Anthropic
from src.config_loader import load_global_config
from src.downloads import download_session_outputs


def main():
    parser = argparse.ArgumentParser(
        description="Download output files from a completed session to a local directory"
    )
    parser.add_argument("--session-id", required=True, help="ID of the session to download outputs from")
    parser.add_argument("--output-dir", required=True, metavar="DIR", help="Local directory to save downloaded files")
    parser.add_argument("--remote-dir", default="/mnt/session/outputs/",
                        help="Remote directory to download from (default: /mnt/session/outputs/)")
    parser.add_argument("--config", default="config/global.yaml", help="Path to global config")
    args = parser.parse_args()

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set in environment or config")

    client = Anthropic(api_key=api_key)
    download_session_outputs(client, args.session_id, Path(args.output_dir), args.remote_dir)


if __name__ == "__main__":
    main()
