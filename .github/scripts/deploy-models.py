#!/usr/bin/env python3
"""Apply the declarative model configs of models/*.yaml to Open WebUI.

Each YAML file names a model id (a LiteLLM slug such as `auto`), the prompt modules of
prompts/ that form its system prompt, and the `meta` keys to set (toolIds, skillIds). The
script updates the config of that model itself: no custom.* model is created. Keys the YAML
does not name keep their live value (name, image, description, capabilities, terminal,
access grants). A model without a config record yet is created, readable by every user.

    python .github/scripts/deploy-models.py [--dry-run]

--dry-run assembles and prints what would be deployed without calling Open WebUI.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
PROMPTS_DIR = ROOT / "prompts"
LEADING_COMMENT = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)
PUBLIC_READ = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
GRANT_FIELDS = ("principal_type", "principal_id", "permission")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required.")
        sys.exit(1)
    return value


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("id", "prompt_modules"):
        if not config.get(key):
            raise ValueError(f"{path}: '{key}' is required")
    meta = config.get("meta") or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: 'meta' must be a mapping")
    config["meta"] = meta
    return config


def assemble_prompt(modules: list[str], prompts_dir: Path = PROMPTS_DIR) -> str:
    """Join the prompt modules in order, without the generated-file header comments."""
    parts = []
    for name in modules:
        path = prompts_dir / f"{name}.md"
        if not path.is_file():
            raise ValueError(f"prompt module '{name}' not found: {path}")
        text = LEADING_COMMENT.sub("", path.read_text(encoding="utf-8")).strip()
        if not text:
            raise ValueError(f"prompt module '{name}' is empty: {path}")
        parts.append(text)
    return "\n\n".join(parts)


def build_update(existing: dict, config: dict, system_prompt: str) -> dict:
    """Return the update form: the live record with the system prompt and meta keys set."""
    return {
        "id": existing["id"],
        "base_model_id": existing.get("base_model_id"),
        "name": existing.get("name") or config["id"],
        "params": {**copy.deepcopy(existing.get("params") or {}), "system": system_prompt},
        "meta": {**copy.deepcopy(existing.get("meta") or {}), **config["meta"]},
        "access_grants": [
            {field: grant[field] for field in GRANT_FIELDS if field in grant}
            for grant in existing.get("access_grants") or []
        ],
        "is_active": existing.get("is_active", True),
    }


def build_create(config: dict, system_prompt: str) -> dict:
    return {
        "id": config["id"],
        "base_model_id": None,
        "name": config.get("name") or config["id"],
        "params": {"system": system_prompt},
        "meta": dict(config["meta"]),
        "access_grants": copy.deepcopy(PUBLIC_READ),
        "is_active": True,
    }


def get_existing_model(base_url: str, headers: dict, model_id: str) -> dict | None:
    resp = requests.get(
        f"{base_url}/api/v1/models/model",
        headers=headers,
        params={"id": model_id},
        timeout=30,
    )
    if resp.status_code == 200 and resp.json():
        return resp.json()
    return None


def deploy_model(base_url: str, api_key: str, config: dict, system_prompt: str) -> bool:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model_id = config["id"]
    existing = get_existing_model(base_url, headers, model_id)
    if existing:
        payload = build_update(existing, config, system_prompt)
        url = f"{base_url}/api/v1/models/model/update"
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        action = "Updated"
    else:
        payload = build_create(config, system_prompt)
        resp = requests.post(f"{base_url}/api/v1/models/create", headers=headers, json=payload, timeout=30)
        action = "Created"

    if resp.status_code in (200, 201, 204):
        print(f"✅ {action} model '{model_id}'")
        return True
    print(f"❌ Failed to {action.lower()} model '{model_id}': {resp.status_code} {resp.text[:200]}...")
    return False


def describe(config: dict, system_prompt: str) -> str:
    lines = [
        f"model '{config['id']}': system prompt of {len(system_prompt)} characters "
        f"from {', '.join(config['prompt_modules'])}",
    ]
    for key, value in config["meta"].items():
        lines.append(f"  meta.{key} = {value}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Deploy models/*.yaml to Open WebUI.")
    parser.add_argument("--dry-run", action="store_true", help="assemble and print, do not deploy")
    args = parser.parse_args(argv)

    configs = sorted(MODELS_DIR.glob("*.yaml"))
    if not configs:
        print("No models/*.yaml found.")
        return

    if not args.dry_run:
        base_url = require_env("OPENWEBUI_URL").rstrip("/")
        api_key = require_env("OPENWEBUI_API_KEY")

    success = True
    for path in configs:
        try:
            config = load_config(path)
            system_prompt = assemble_prompt(config["prompt_modules"])
            print(describe(config, system_prompt))
            if not args.dry_run and not deploy_model(base_url, api_key, config, system_prompt):
                success = False
        except Exception as exc:
            print(f"❌ Error processing {path.name}: {exc}")
            success = False

    if not success:
        sys.exit(1)
    print("Dry run: nothing deployed." if args.dry_run else "All models deployed successfully.")


if __name__ == "__main__":
    main()
