#!/usr/bin/env python3
"""Strict prompt diff between the repo, a source Langfuse project and an
optional target Langfuse project.

Checks, for every prompts/*.md module (and any extra names passed as args):
  1. repo file content == source project prompt content (for LANGFUSE_PROMPT_LABEL)
  2. if TARGET_* keys are set: source prompt == target prompt
     (content, type, config and variables must match exactly)

Environment:
  LANGFUSE_HOST            e.g. https://langfuse.supergeoff.top
  LANGFUSE_PROMPT_LABEL    label to compare (e.g. production)
  SOURCE_PUBLIC_KEY / SOURCE_SECRET_KEY   source project (read)
  TARGET_PUBLIC_KEY / TARGET_SECRET_KEY   optional target project (read)

Exits 1 on any mismatch or fetch failure.
"""

from __future__ import annotations

import base64
import difflib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROMPT_DIR = Path("prompts")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required.")
        sys.exit(1)
    return value


def fetch_prompt(host: str, public_key: str, secret_key: str, name: str, label: str):
    url = (
        f"{host.rstrip('/')}/api/public/v2/prompts/"
        f"{urllib.parse.quote(name, safe='')}?label={urllib.parse.quote(label)}"
    )
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def unified_diff(left: str, right: str, left_name: str, right_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=left_name,
            tofile=right_name,
        )
    )


def main() -> None:
    host = require_env("LANGFUSE_HOST")
    label = require_env("LANGFUSE_PROMPT_LABEL")
    source_pk = require_env("SOURCE_PUBLIC_KEY")
    source_sk = require_env("SOURCE_SECRET_KEY")
    target_pk = os.getenv("TARGET_PUBLIC_KEY")
    target_sk = os.getenv("TARGET_SECRET_KEY")

    names = sorted(path.stem for path in PROMPT_DIR.glob("*.md"))
    names.extend(arg for arg in sys.argv[1:] if arg not in names)
    if not names:
        print("No prompt names to compare.")
        sys.exit(1)

    failures = 0
    for name in names:
        repo_path = PROMPT_DIR / f"{name}.md"
        repo_text = (
            repo_path.read_text(encoding="utf-8").strip() if repo_path.exists() else None
        )

        source = fetch_prompt(host, source_pk, source_sk, name, label)
        if source is None:
            print(f"❌ {name}: missing in source project (label '{label}')")
            failures += 1
            continue
        source_text = str(source.get("prompt", "")).strip()

        if repo_text is not None:
            if repo_text != source_text:
                print(f"❌ {name}: repo file differs from source project")
                print(unified_diff(repo_text, source_text, f"repo/{name}.md", f"source/{name}"))
                failures += 1
            else:
                print(f"✅ {name}: repo == source")
        else:
            print(f"ℹ️  {name}: no repo file, source-only prompt")

        if not (target_pk and target_sk):
            continue

        target = fetch_prompt(host, target_pk, target_sk, name, label)
        if target is None:
            print(f"❌ {name}: missing in target project (label '{label}')")
            failures += 1
            continue

        target_text = str(target.get("prompt", "")).strip()
        if source_text != target_text:
            print(f"❌ {name}: source and target contents differ")
            print(unified_diff(source_text, target_text, f"source/{name}", f"target/{name}"))
            failures += 1
            continue

        mismatched_fields = [
            field
            for field in ("type", "config")
            if source.get(field) != target.get(field)
        ]
        if mismatched_fields:
            print(f"❌ {name}: source and target differ on {', '.join(mismatched_fields)}")
            for field in mismatched_fields:
                print(f"   source {field}: {json.dumps(source.get(field), ensure_ascii=False)}")
                print(f"   target {field}: {json.dumps(target.get(field), ensure_ascii=False)}")
            failures += 1
        else:
            print(f"✅ {name}: source == target (content, type, config)")

    if failures:
        print(f"\n{failures} mismatch(es) found.")
        sys.exit(1)
    print("\nAll prompts match.")


if __name__ == "__main__":
    main()
