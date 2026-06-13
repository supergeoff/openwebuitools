#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NamedTuple


PROMPT_DIR = Path("prompts")
PROMPT_TYPE = "text"


class DeploymentConfig(NamedTuple):
    host: str
    public_key: str
    secret_key: str
    prompt_label: str


class PromptDefinition(NamedTuple):
    path: Path
    name: str
    label: str
    type: str
    prompt: str


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required.")
        sys.exit(1)
    return value


def read_deployment_config() -> DeploymentConfig:
    return DeploymentConfig(
        host=require_env("LANGFUSE_HOST").rstrip("/"),
        public_key=require_env("LANGFUSE_PUBLIC_KEY"),
        secret_key=require_env("LANGFUSE_SECRET_KEY"),
        prompt_label=require_env("LANGFUSE_PROMPT_LABEL"),
    )


def parse_prompt_file(path: Path, label: str) -> PromptDefinition:
    prompt = path.read_text(encoding="utf-8").strip()
    name = path.stem

    if not name:
        raise ValueError(f"{path}: prompt name is empty")
    if not label:
        raise ValueError(f"{path}: prompt label is empty")
    if not prompt:
        raise ValueError(f"{path}: prompt body is empty")

    return PromptDefinition(
        path=path,
        name=name,
        label=label,
        type=PROMPT_TYPE,
        prompt=prompt,
    )


def deploy_prompt(client, definition: PromptDefinition) -> bool:
    created = client.create_prompt(
        name=definition.name,
        prompt=definition.prompt,
        labels=[definition.label],
        type=definition.type,
    )
    version = getattr(created, "version", "unknown")
    labels = getattr(created, "labels", [definition.label])
    print(
        f"✅ Deployed prompt '{definition.name}' "
        f"from {definition.path} as version {version} with labels {labels}"
    )
    return True


def build_client(config: DeploymentConfig):
    try:
        from langfuse import Langfuse
    except ImportError:
        print("Error: langfuse package is required. Install it with: pip install langfuse")
        sys.exit(1)

    return Langfuse(
        public_key=config.public_key,
        secret_key=config.secret_key,
        host=config.host,
    )


def main() -> None:
    if not PROMPT_DIR.exists():
        print("No prompts/ directory found.")
        return

    prompt_files = sorted(PROMPT_DIR.glob("*.md"))
    if not prompt_files:
        print("No prompt markdown files found.")
        return

    config = read_deployment_config()
    client = build_client(config)
    success = True

    for prompt_file in prompt_files:
        try:
            definition = parse_prompt_file(prompt_file, label=config.prompt_label)
            print(
                f"Deploying {prompt_file.name} "
                f"to Langfuse prompt '{definition.name}' label '{definition.label}'..."
            )
            deploy_prompt(client, definition)
        except Exception as exc:
            print(f"❌ Error processing {prompt_file}: {exc}")
            success = False

    if success:
        print("All prompts deployed successfully.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
