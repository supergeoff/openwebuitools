#!/usr/bin/env python3
import os
import requests
import sys
from pathlib import Path

def get_installed_functions(base_url: str, headers: dict) -> list:
    resp = requests.get(
        f"{base_url}/api/v1/functions/",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return []

def pipe_exists(installed_functions: list, pipe_id: str) -> bool:
    return any(f.get("id") == pipe_id for f in installed_functions)

def deploy_pipe(base_url: str, api_key: str, pipe_file: Path, installed_functions: list):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Get pipe ID from filename
    pipe_id = pipe_file.stem
    
    with open(pipe_file, "r") as f:
        content = f.read()
        
    payload = {
        "id": pipe_id,
        "name": pipe_id.capitalize(),
        "meta": {"description": f"Pipe for {pipe_id}"},
        "content": content,
        "is_active": True,
        "is_global": True
    }

    if pipe_exists(installed_functions, pipe_id):
        print(f"Pipe '{pipe_id}' already exists. Updating...")
        # Get existing function info
        existing = next(f for f in installed_functions if f.get("id") == pipe_id)
        # Add id to payload for update
        payload["id"] = existing["id"]
        resp = requests.post(
            f"{base_url}/api/v1/functions/id/{pipe_id}/update",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Updated"
    else:
        print(f"Creating pipe '{pipe_id}'...")
        resp = requests.post(
            f"{base_url}/api/v1/functions/create",
            headers=headers,
            json=payload,
            timeout=30,
        )
        action = "Created"

    if resp.status_code in (200, 201, 204):
        print(f"✅ {action} pipe '{pipe_id}'")
        return True

    print(f"❌ Failed to {action.lower()} pipe '{pipe_id}': {resp.status_code} {resp.text[:200]}...")
    return False

def main():
    base_url = os.getenv("OPENWEBUI_URL", "http://localhost:3000").rstrip("/")
    api_key = os.getenv("OPENWEBUI_API_KEY")
    if not api_key:
        print("Error: OPENWEBUI_API_KEY environment variable is required.")
        sys.exit(1)

    pipe_dir = Path("pipe")
    if not pipe_dir.exists():
        print("No pipe/ directory found.")
        return

    headers = {"Authorization": f"Bearer {api_key}"}
    installed_functions = get_installed_functions(base_url, headers)

    success = True
    for py_file in pipe_dir.glob("*.py"):
        try:
            print(f"Deploying {py_file.name}...")
            if deploy_pipe(base_url, api_key, py_file, installed_functions):
                print(f"Successfully processed {py_file.name}")
            else:
                success = False
        except Exception as e:
            print(f"Error processing {py_file}: {e}")
            success = False

    if success:
        print("All pipes deployed/updated successfully.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
