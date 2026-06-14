#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

import requests


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required.")
        sys.exit(1)
    return value


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").lower()
    return slug or "action"


def display_name_for(action_id: str) -> str:
    return "_".join(part.capitalize() for part in action_id.split("_") if part)


def get_installed_functions(base_url: str, headers: dict) -> list:
    resp = requests.get(
        f"{base_url}/api/v1/functions/",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return []


def action_exists(installed_functions: list, action_id: str) -> bool:
    return any(function.get("id") == action_id for function in installed_functions)


def post_function(base_url: str, headers: dict, action_id: str, payload: dict, exists: bool):
    if exists:
        return requests.post(
            f"{base_url}/api/v1/functions/id/{action_id}/update",
            headers=headers,
            json=payload,
            timeout=30,
        )
    return requests.post(
        f"{base_url}/api/v1/functions/create",
        headers=headers,
        json=payload,
        timeout=30,
    )


def toggle_if_needed(base_url: str, headers: dict, action_id: str, state: dict) -> bool:
    success = True
    if not state.get("is_active", False):
        resp = requests.post(
            f"{base_url}/api/v1/functions/id/{action_id}/toggle",
            headers=headers,
            timeout=30,
        )
        success = success and resp.status_code in (200, 201, 204)
    if not state.get("is_global", False):
        resp = requests.post(
            f"{base_url}/api/v1/functions/id/{action_id}/toggle/global",
            headers=headers,
            timeout=30,
        )
        success = success and resp.status_code in (200, 201, 204)
    return success


def deploy_action(
    base_url: str, api_key: str, action_file: Path, installed_functions: list
) -> bool:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    action_id = slugify(action_file.stem)
    content = action_file.read_text(encoding="utf-8")
    payload = {
        "id": action_id,
        "name": display_name_for(action_id),
        "meta": {"description": f"Action for {action_id}"},
        "content": content,
    }

    exists = action_exists(installed_functions, action_id)
    action = "Updated" if exists else "Created"
    print(f"{'Updating' if exists else 'Creating'} action '{action_id}'...")
    resp = post_function(base_url, headers, action_id, payload, exists)

    if resp.status_code not in (200, 201, 204):
        print(
            f"Failed to {action.lower()} action '{action_id}': "
            f"{resp.status_code} {resp.text[:200]}..."
        )
        return False

    state = resp.json() if hasattr(resp, "json") else {}
    if not state:
        state = next(
            (function for function in installed_functions if function.get("id") == action_id),
            {},
        )
    if not toggle_if_needed(base_url, headers, action_id, state):
        print(f"Failed to activate action '{action_id}' globally.")
        return False

    print(f"{action} action '{action_id}'")
    return True


def main():
    base_url = require_env("OPENWEBUI_URL").rstrip("/")
    api_key = require_env("OPENWEBUI_API_KEY")

    action_dir = Path("actions")
    if not action_dir.exists():
        print("No actions/ directory found.")
        return

    headers = {"Authorization": f"Bearer {api_key}"}
    installed_functions = get_installed_functions(base_url, headers)

    success = True
    for py_file in sorted(action_dir.glob("*.py")):
        try:
            print(f"Deploying {py_file.name}...")
            success = deploy_action(base_url, api_key, py_file, installed_functions) and success
        except Exception as exc:
            print(f"Error processing {py_file}: {exc}")
            success = False

    if success:
        print("All actions deployed/updated successfully.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
