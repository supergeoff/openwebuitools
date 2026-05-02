#!/usr/bin/env python3
import os
import re
import json
import yaml
import requests
import sys
from pathlib import Path


def parse_md_file(path: Path) -> tuple[dict, str]:
    """Parse a markdown file with YAML frontmatter.

    Returns (frontmatter_dict, body_string).
    """
    content = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: no valid YAML frontmatter found")

    frontmatter = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return frontmatter, body


def get_existing_model(base_url: str, headers: dict, model_id: str) -> dict | None:
    resp = requests.get(
        f"{base_url}/api/v1/models/model",
        headers=headers,
        params={"id": model_id},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def deploy_model(base_url: str, api_key: str, model_data: dict):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model_id = model_data.get("id")

    existing = get_existing_model(base_url, headers, model_id)
    if existing:
        print(f"Model '{model_id}' already exists. Patching system prompt only...")
        # Preserve existing model config, only update the system prompt
        existing["params"]["system"] = model_data["params"]["system"]
        resp = requests.post(
            f"{base_url}/api/v1/models/model/update",
            headers=headers,
            json=existing,
            timeout=30,
        )
        action = "Updated"
    else:
        print(f"Creating model '{model_id}'...")
        resp = requests.post(
            f"{base_url}/api/v1/models/create",
            headers=headers,
            json=model_data,
            timeout=30,
        )
        action = "Created"

    if resp.status_code in (200, 201, 204):
        print(f"✅ {action} model '{model_id}'")
        return True

    print(
        f"❌ Failed to {action.lower()} model '{model_id}': {resp.status_code} {resp.text[:200]}..."
    )
    return False


def main():
    base_url = os.getenv("OPENWEBUI_URL", "http://localhost:3000").rstrip("/")
    api_key = os.getenv("OPENWEBUI_API_KEY")
    if not api_key:
        print("Error: OPENWEBUI_API_KEY environment variable is required.")
        sys.exit(1)

    models_dir = Path("models")
    if not models_dir.exists():
        print("No models/ directory found.")
        return

    success = True
    for md_file in sorted(models_dir.glob("*.md")):
        try:
            frontmatter, system_prompt = parse_md_file(md_file)
            slug = frontmatter.get("slug", md_file.stem)
            model_id = f"custom.{slug}"

            payload = {
                "id": model_id,
                "base_model_id": frontmatter["base_model_id"],
                "name": frontmatter["name"],
                "params": {
                    "system": system_prompt,
                    **frontmatter.get("params", {}),
                },
                "meta": frontmatter.get("meta", {}),
            }

            print(f"Deploying {md_file.name} ({model_id})...")
            if deploy_model(base_url, api_key, payload):
                print(f"Successfully processed {md_file.name}")
            else:
                success = False
        except Exception as e:
            print(f"Error processing {md_file}: {e}")
            success = False

    if success:
        print("All models deployed/updated successfully.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
