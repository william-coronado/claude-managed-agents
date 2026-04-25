"""Diagnostic: print everything the API returns for a completed session."""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from anthropic import Anthropic
from src.config_loader import load_global_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--config", default="config/global.yaml")
    args = parser.parse_args()

    cfg = load_global_config(args.config)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    client = Anthropic(api_key=api_key)

    print(f"\n=== Session {args.session_id} ===")
    try:
        session = client.beta.sessions.retrieve(args.session_id)
        print(f"status      : {session.status}")
        print(f"archived_at : {session.archived_at}")
        print(f"resources in session object: {len(session.resources)}")
        for r in session.resources:
            print(f"  type={r.type} mount_path={getattr(r, 'mount_path', '-')} file_id={getattr(r, 'file_id', '-')}")
    except Exception as e:
        print(f"sessions.retrieve failed: {e}")

    print("\n=== sessions.resources.list ===")
    try:
        resources = list(client.beta.sessions.resources.list(args.session_id))
        print(f"Total resources: {len(resources)}")
        for r in resources:
            print(f"  type={r.type} mount_path={getattr(r, 'mount_path', '-')} file_id={getattr(r, 'file_id', '-')}")
    except Exception as e:
        print(f"sessions.resources.list failed: {e}")

    print("\n=== files.list (no filter) ===")
    try:
        files = list(client.beta.files.list(limit=20))
        print(f"Total files: {len(files)}")
        for f in files:
            print(f"  id={f.id} filename={f.filename!r} downloadable={f.downloadable} scope={f.scope}")
    except Exception as e:
        print(f"files.list failed: {e}")

    print("\n=== files.list (scope_id filter) ===")
    try:
        files = list(client.beta.files.list(scope_id=args.session_id))
        print(f"Total files with scope_id filter: {len(files)}")
        for f in files:
            print(f"  id={f.id} filename={f.filename!r} downloadable={f.downloadable}")
    except Exception as e:
        print(f"files.list(scope_id=...) failed: {e}")


if __name__ == "__main__":
    main()
